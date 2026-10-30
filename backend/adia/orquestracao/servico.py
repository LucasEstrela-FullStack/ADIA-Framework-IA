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
from dataclasses import dataclass
from pathlib import Path

from adia.guarda.veredito import revela_resposta
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao
from adia.ia.subagentes.papeis import PAPEIS, pedido
from adia.nucleo.correcao.motor import MOTIVO_VAZIA, Julgamento, Resultado, corrigir
from adia.nucleo.itens.banco import BancoDeItens
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.nucleo.itens.modelo import Item
from adia.nucleo.regulacao.regra import ConjuntoDeLimiares
from adia.nucleo.sessao.gestor import OperacaoRecusada, ResumoDoCiclo, Sessao
from adia.persistencia.repositorio import DecisaoGravada, Proveniencia, Repositorio
from adia.tipos import Nivel

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
    ) -> None:
        arquivos = arquivos_de_itens(diretorio_de_itens)
        carga = carregar(arquivos)
        if not isinstance(carga, CargaConcluida):
            # A API recusa servir com banco inválido (design §7), nomeando o erro.
            raise RuntimeError(f"Banco de itens inválido: {carga}")
        self.carga = carga
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
        registro = self.repositorio.criar_sessao(
            sessao_id, participante_id, secrets.randbits(31), self.proveniencia
        )
        sessao = Sessao(self.banco, registro.condicao)
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
        sessao = Sessao(self._banco(gravada.semente_banco), registro.condicao)
        for evento in eventos:
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
                    if sessao.encerrada:
                        Repositorio.concluir(conexao, sessao_id)
            except BaseException:
                # A memória pode ter avançado sem o registro: o próximo acesso relê do banco.
                self._esquecer(sessao_id)
                raise
            return julgamento, resumo

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
