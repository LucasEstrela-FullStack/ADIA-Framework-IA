"""Orquestração: sessões, correção e dicas, ligando o núcleo puro à IA e à guarda.

É a única camada que vê os dois lados da fronteira de D1: o texto do modelo nunca entra no
núcleo, e nenhuma decisão de regulação depende dele.

Persistência: cada dica, resposta e decisão de ciclo vira linha no SQLite, gravada na mesma
transação em que a sessão em memória avança. A memória é só cache: uma sessão ausente dele
é reconstruída reaplicando os eventos, e o replay confere etapa, ciclo, teto e decisão
contra o que foi gravado. Divergência é erro, nunca correção silenciosa.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from adia.guarda.veredito import revela_resposta
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao
from adia.ia.subagentes.papeis import PAPEIS, pedido
from adia.nucleo.correcao.motor import MOTIVO_AGUARDANDO_RUBRICA, MOTIVO_VAZIA, Julgamento, Resultado, corrigir
from adia.nucleo.itens.banco import BancoDeItens
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.nucleo.itens.modelo import Item
from adia.nucleo.metricas.calculo import taxa_de_acerto
from adia.nucleo.regulacao.regra import ConjuntoDeLimiares
from adia.nucleo.sessao.gestor import OperacaoRecusada, ResumoDoCiclo, Sessao
from adia.nucleo.sessao.retencao import JanelaDaRetencao, janela
from adia.nucleo.steam.cenarios import ErroDeSteam, Rubrica, arquivos_de_steam
from adia.nucleo.steam.cenarios import carregar as carregar_steam
from adia.persistencia.repositorio import (
    AvaliacaoNova,
    AvaliacaoRepetida,
    DecisaoGravada,
    Proveniencia,
    Repositorio,
    SubmissaoGravada,
)
from adia.tipos import Etapa, Indisponivel, Medida, Nivel

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Dica:
    nivel: Nivel
    texto: str
    origem: str
    """``ia`` quando o modelo gerou e a guarda aprovou; ``pre-escrita`` nos demais casos."""
    motivo: str | None = None


class SessaoInexistente(OperacaoRecusada):
    """Identificador de sessão que o banco não conhece."""


class SubmissaoInexistente(OperacaoRecusada):
    """Identificador de submissão STEAM que o banco não conhece."""


class SessaoInconsistente(RuntimeError):
    """Os dados gravados não reproduzem a sessão com o código e o banco de itens atuais."""


def hash_do_banco(arquivos: tuple[Path, ...]) -> str:
    """SHA-256 dos nomes e bytes dos arquivos de itens, em ordem estável."""
    resumo = hashlib.sha256()
    for arquivo in arquivos:
        resumo.update(arquivo.name.encode("utf-8") + b"\0" + arquivo.read_bytes() + b"\0")
    return resumo.hexdigest()


class Servico:
    def __init__(
        self,
        diretorio_de_itens: Path,
        cliente: ClienteOllama,
        repositorio: Repositorio,
        commit: str | None = None,
        semente: int = 20261030,
        diretorio_steam: Path | None = None,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        arquivos = arquivos_de_itens(diretorio_de_itens)
        carga = carregar(arquivos)
        if not isinstance(carga, CargaConcluida):
            # A API recusa servir com banco inválido (design §7), nomeando o erro.
            raise RuntimeError(f"Banco de itens inválido: {carga}")
        self.carga = carga
        try:
            self.steam = carregar_steam(arquivos_de_steam(diretorio_steam) if diretorio_steam else ())
        except ErroDeSteam as erro:
            raise RuntimeError(f"Conteúdo STEAM inválido: {erro}") from erro
        habilidades = {item.habilidade_alvo for item in carga.itens}
        for cenario in self.steam.cenarios:
            if cenario.habilidade_alvo not in habilidades:
                # R13.1: cenário de habilidade que nenhum item cobre nunca seria liberado.
                raise RuntimeError(
                    f"Cenário STEAM {cenario.id!r}: nenhum item cobre a habilidade {cenario.habilidade_alvo!r}."
                )
        self._agora = agora
        self.cliente = cliente
        self.repositorio = repositorio
        self.proveniencia = Proveniencia(
            semente_banco=semente,
            hash_banco_itens=hash_do_banco(arquivos),
            commit_codigo=commit,
            modelo=cliente.modelo,
            limiares_versao=ConjuntoDeLimiares().versao,
        )
        self._sessoes: dict[str, Sessao] = {}
        self._bancos: dict[int, BancoDeItens] = {}
        # Uma trava por sessão: pedidos da mesma sessão em fila (memória e registro avançam
        # juntos), e a geração de uma dica não bloqueia as outras sessões.
        self._trava = threading.Lock()
        self._travas: dict[str, threading.RLock] = {}

    def _banco(self, semente: int) -> BancoDeItens:
        with self._trava:
            if semente not in self._bancos:
                self._bancos[semente] = BancoDeItens(self.carga, semente)
            return self._bancos[semente]

    @property
    def banco(self) -> BancoDeItens:
        return self._banco(self.proveniencia.semente_banco)

    def _da_sessao(self, sessao_id: str) -> threading.RLock:
        with self._trava:
            return self._travas.setdefault(sessao_id, threading.RLock())

    def _esquecer(self, sessao_id: str) -> None:
        with self._trava:
            self._sessoes.pop(sessao_id, None)

    def iniciar(self, participante_id: str) -> tuple[str, Sessao]:
        """Sessão do participante: a existente, se houver, ou uma nova com condição sorteada."""
        existente = self.repositorio.sessao_do_participante(participante_id)
        if existente is not None:
            return existente, self.obter(existente)
        sessao_id = uuid.uuid4().hex[:12]
        limiares = self.repositorio.limiares()
        proveniencia = replace(self.proveniencia, limiares_versao=limiares.versao)
        registro = self.repositorio.criar_sessao(sessao_id, participante_id, secrets.randbits(31), proveniencia)
        sessao = Sessao(self.banco, registro.condicao, limiares, cenarios=self.steam.cenarios)
        with self._trava:
            self._sessoes[sessao_id] = sessao
        return sessao_id, sessao

    def obter(self, sessao_id: str) -> Sessao:
        with self._da_sessao(sessao_id):
            sessao = self._sessoes.get(sessao_id)
            if sessao is None:
                sessao = self._reconstruir(sessao_id)
                with self._trava:
                    self._sessoes[sessao_id] = sessao
            return sessao

    def _reconstruir(self, sessao_id: str) -> Sessao:
        lido = self.repositorio.ler_sessao(sessao_id)
        if lido is None:
            raise SessaoInexistente("Sessão inexistente.")
        registro, eventos, decisoes = lido
        gravada = registro.proveniencia
        if gravada.hash_banco_itens != self.proveniencia.hash_banco_itens:
            raise SessaoInconsistente(
                f"Sessão {sessao_id} foi gravada com outro banco de itens "
                f"({gravada.hash_banco_itens[:12]}, atual {self.proveniencia.hash_banco_itens[:12]})."
            )
        sessao = Sessao(
            self._banco(gravada.semente_banco),
            registro.condicao,
            self.repositorio.limiares(gravada.limiares_versao),
            cenarios=self.steam.cenarios,
        )
        steam = self.repositorio.acertos_steam(sessao_id)

        def aplicar_steam() -> None:
            # A submissão fica fora do registro de eventos: entra assim que o replay chega à etapa.
            if steam is None or sessao.etapa != Etapa.PROJETO_STEAM:
                return
            if sessao.cenario is None or sessao.cenario.id != steam[0]:
                raise SessaoInconsistente(f"Sessão {sessao_id}: o projeto STEAM gravado é de outro cenário.")
            try:
                sessao.submeter_steam(steam[1])
            except OperacaoRecusada as erro:
                raise SessaoInconsistente(f"Sessão {sessao_id}: o replay recusou o projeto STEAM: {erro}") from erro

        for evento in eventos:
            aplicar_steam()
            if evento.etapa == Etapa.TESTE_RETENCAO and sessao.encerrada:
                sessao.iniciar_retencao()
            atual = sessao.item_atual
            esperado = (str(sessao.etapa), sessao.ciclo, None if atual is None else atual.id, sessao.teto)
            if esperado != (evento.etapa, evento.ciclo, evento.item_id, evento.teto):
                raise SessaoInconsistente(
                    f"Sessão {sessao_id}: o replay chegou a {esperado}, mas o evento gravado diz "
                    f"{(evento.etapa, evento.ciclo, evento.item_id, evento.teto)}."
                )
            try:
                if evento.tipo == "dica":
                    assert evento.nivel is not None
                    sessao.registrar_dica(evento.nivel, evento.explicacao or "")
                    continue
                assert evento.confianca is not None
                resumo = sessao.responder(evento.acerto, evento.confianca, evento.justificativa or "")
            except OperacaoRecusada as erro:
                raise SessaoInconsistente(f"Sessão {sessao_id}: o replay recusou um evento gravado: {erro}") from erro
            if resumo is not None:
                self._conferir(sessao_id, resumo, decisoes.get(resumo.ciclo))
        aplicar_steam()
        if steam is not None and sessao.steam is None:
            raise SessaoInconsistente(f"Sessão {sessao_id}: há projeto STEAM gravado, mas o replay não chegou a ele.")
        if registro.retencao_iniciada_em is not None and sessao.encerrada and not sessao.retencao_concluida:
            sessao.iniciar_retencao()  # aberta e ainda sem resposta
        return sessao

    def janela_da_retencao(self, sessao_id: str) -> JanelaDaRetencao | None:
        """Janela de DO-08 da sessão, ou ``None`` enquanto os ciclos não terminaram."""
        lido = self.repositorio.ler_sessao(sessao_id)
        if lido is None:
            raise SessaoInexistente("Sessão inexistente.")
        concluida = lido[0].concluida_em
        return None if concluida is None else janela(concluida, self._agora())

    def iniciar_retencao(self, sessao_id: str) -> Sessao:
        with self._da_sessao(sessao_id):
            sessao = self.obter(sessao_id)
            if sessao.etapa == Etapa.TESTE_RETENCAO:
                return sessao  # já aberta: abrir de novo é retomar
            situacao = self.janela_da_retencao(sessao_id)
            if situacao is None:
                raise OperacaoRecusada("Termine as rodadas antes da última parte.")
            if not situacao.disponivel:
                raise OperacaoRecusada(
                    f"A última parte abre em {situacao.abre_em.astimezone():%d/%m/%Y às %H:%M}. "
                    "Volte nesse dia com o mesmo código."
                )
            try:
                with self.repositorio.transacao() as conexao:
                    desvio = None if situacao.desvio_horas is None else str(situacao.desvio_horas)
                    Repositorio.iniciar_retencao(conexao, sessao_id, self._agora(), desvio)
                    sessao.iniciar_retencao()
            except BaseException:
                self._esquecer(sessao_id)
                raise
            return sessao

    @staticmethod
    def _conferir(sessao_id: str, resumo: ResumoDoCiclo, gravada: DecisaoGravada | None) -> None:
        recalculada = DecisaoGravada(resumo.decisao.tipo.value, resumo.teto_seguinte, resumo.decisao.limiares_versao)
        if recalculada != gravada:
            raise SessaoInconsistente(
                f"Sessão {sessao_id}, ciclo {resumo.ciclo}: decisão recalculada {recalculada} "
                f"difere da gravada {gravada}."
            )

    def responder(
        self, sessao_id: str, resposta: str, confianca: int, justificativa: str = ""
    ) -> tuple[Julgamento, ResumoDoCiclo | None]:
        with self._da_sessao(sessao_id):
            sessao = self.obter(sessao_id)
            item = sessao.item_atual
            if item is None:
                raise OperacaoRecusada("Você já terminou. Pode fechar esta tela.")
            julgamento = corrigir(item, resposta)
            if julgamento.motivo_rejeicao == MOTIVO_VAZIA:
                raise OperacaoRecusada("Escreva sua resposta antes de enviar.")
            if julgamento.motivo_rejeicao is not None:
                raise OperacaoRecusada(
                    f"Sua resposta passou de {item.tamanho_max_resposta} caracteres. Escreva só o resultado."
                )
            acerto = julgamento.resultado is Resultado.ACERTO if isinstance(julgamento.resultado, Resultado) else None
            try:
                with self.repositorio.transacao() as conexao:
                    Repositorio.registrar_resposta(
                        conexao, sessao_id, sessao, resposta, justificativa, acerto, confianca
                    )
                    resumo = sessao.responder(acerto, confianca, justificativa)
                    if resumo is not None:
                        Repositorio.registrar_decisao(conexao, sessao_id, resumo, sessao.condicao)
                    if sessao.encerrada and sessao.retencao_concluida:
                        Repositorio.concluir_retencao(conexao, sessao_id)
                    elif sessao.encerrada:
                        Repositorio.concluir(conexao, sessao_id)
            except BaseException:
                # A memória pode ter avançado sem o registro: o próximo acesso relê do banco.
                self._esquecer(sessao_id)
                raise
            return julgamento, resumo

    def submeter_steam(self, sessao_id: str, respostas: Mapping[str, str], justificativa: str) -> Sessao:
        """Corrige as partes numéricas, grava a submissão e encerra os ciclos (R13.2, R13.3)."""
        with self._da_sessao(sessao_id):
            sessao = self.obter(sessao_id)
            cenario = sessao.cenario
            if sessao.etapa != Etapa.PROJETO_STEAM or cenario is None:
                raise OperacaoRecusada("O projeto não está aberto para este código.")
            partes: list[dict[str, str]] = []
            for parte in cenario.partes:
                valor = respostas.get(parte.parte, "").strip()
                if not valor:
                    raise OperacaoRecusada("Responda todas as partes antes de enviar.")
                if len(valor) > parte.tamanho_max_resposta:
                    raise OperacaoRecusada(
                        f"Uma resposta passou de {parte.tamanho_max_resposta} caracteres. Escreva só o resultado."
                    )
                resultado = "acerto" if parte.corrigir(valor) else "erro"
                partes.append(
                    {"parte": parte.parte, "valor": valor, "resultado": resultado, "tolerancia": str(parte.tolerancia)}
                )
            texto = justificativa.strip()
            if not texto:
                raise OperacaoRecusada("Escreva a justificativa antes de enviar.")
            if len(texto) > cenario.tamanho_max_justificativa:
                raise OperacaoRecusada(f"A justificativa passou de {cenario.tamanho_max_justificativa} caracteres.")
            try:
                with self.repositorio.transacao() as conexao:
                    Repositorio.registrar_steam(conexao, sessao_id, sessao, partes, texto)
                    sessao.submeter_steam([p["resultado"] == "acerto" for p in partes])
                    Repositorio.concluir(conexao, sessao_id)
            except BaseException:
                self._esquecer(sessao_id)
                raise
            return sessao

    def medidas_steam(self, sessao_id: str, sessao: Sessao) -> tuple[Medida, Medida] | None:
        """``(partes, rubrica)`` do projeto submetido, cada uma entre 0 e 1; ``None`` antes da submissão.

        As duas ficam separadas, sem nota composta: o peso de cada uma na pontuação de R13.7 é
        decisão de pesquisa. A rubrica é a média das avaliações concluídas, uma por avaliador, e
        fica indisponível com ``aguardando_rubrica`` até a primeira.
        """
        if sessao.steam is None:
            return None
        partes = taxa_de_acerto(list(sessao.steam), "projeto STEAM sem partes numéricas")
        notas = self.repositorio.notas_da_rubrica(sessao_id)
        if not notas:
            return partes, Indisponivel(MOTIVO_AGUARDANDO_RUBRICA)
        return partes, sum((Decimal(p) / Decimal(m) for p, m in notas), Decimal(0)) / len(notas)

    def rubrica_de(self, submissao: SubmissaoGravada) -> Rubrica:
        rubrica = self.steam.rubricas.get((submissao.rubrica_id, submissao.rubrica_versao))
        if rubrica is None:
            raise OperacaoRecusada(
                f"A rubrica {submissao.rubrica_id} versão {submissao.rubrica_versao} não está mais em data/steam/."
            )
        return rubrica

    def submissao(self, submissao_id: int) -> SubmissaoGravada:
        encontradas = self.repositorio.submissoes_steam(submissao_id)
        if not encontradas:
            raise SubmissaoInexistente("Submissão inexistente.")
        return encontradas[0]

    def avaliar(self, submissao_id: int, avaliador_id: str, niveis: Mapping[str, str]) -> AvaliacaoNova:
        """Pontua a justificativa com a versão da rubrica fixada na submissão (R13.4).

        Todos os critérios são exigidos de uma vez: avaliação parcial não é registrada, então
        toda linha gravada já está concluída.
        """
        submissao = self.submissao(submissao_id)
        rubrica = self.rubrica_de(submissao)
        pontuacoes: list[tuple[str, str, int]] = []
        for criterio in rubrica.criterios:
            nivel = niveis.get(criterio.criterio)
            pontos = None if nivel is None else criterio.pontos(nivel)
            if nivel is None or pontos is None:
                raise OperacaoRecusada("Escolha um nível válido em todos os critérios da rubrica.")
            pontuacoes.append((criterio.criterio, nivel, pontos))
        avaliacao = AvaliacaoNova(
            submissao_id,
            avaliador_id,
            rubrica.rubrica_versao,
            tuple(pontuacoes),
            len(rubrica.criterios),
            rubrica.pontos_maximos,
        )
        try:
            self.repositorio.registrar_avaliacao(avaliacao)
        except AvaliacaoRepetida as erro:
            raise OperacaoRecusada(f"{avaliador_id} já avaliou esta submissão.") from erro
        return avaliacao

    def dica(self, sessao_id: str, nivel: Nivel, explicacao: str = "") -> Dica:
        with self._da_sessao(sessao_id):
            sessao = self.obter(sessao_id)
            ja_registrada = nivel in sessao.dicas_do_item
            item = sessao.registrar_dica(nivel, explicacao)
            try:
                dica = self._gerar(item, nivel, explicacao)
                with self.repositorio.transacao() as conexao:
                    Repositorio.registrar_dica(
                        conexao, sessao_id, sessao, nivel, explicacao, (dica.texto, dica.origem, dica.motivo)
                    )
            except BaseException:
                if not ja_registrada:
                    self._esquecer(sessao_id)
                raise
            return dica

    def _gerar(self, item: Item, nivel: Nivel, explicacao: str) -> Dica:
        pre_escrita = item.dicas[nivel]
        papel = PAPEIS.get(nivel)
        if papel is None:
            return Dica(nivel, pre_escrita, "pre-escrita", "exemplo resolvido revisado")
        try:
            gerada = self.cliente.gerar(papel, pedido(item.enunciado, pre_escrita, explicacao))
        except FalhaDeGeracao as erro:
            # O detalhe (URL, exceção) fica só no log local; o registro de pesquisa leva o motivo fixo.
            _log.warning("geração indisponível: %s", erro)
            return Dica(nivel, pre_escrita, "pre-escrita", "IA indisponível")
        if revela_resposta(gerada.texto, item):
            return Dica(nivel, pre_escrita, "pre-escrita", "guarda descartou a dica gerada")
        return Dica(nivel, gerada.texto, "ia")
