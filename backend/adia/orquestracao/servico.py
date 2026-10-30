"""Orquestração: sessões, correção e dicas, ligando o núcleo puro à IA e à guarda.

É a única camada que vê os dois lados da fronteira de D1: o texto do modelo nunca entra no
núcleo, e nenhuma decisão de regulação depende dele.

Persistência: cada dica e cada resposta viram um evento no SQLite, gravado na mesma
transação em que a sessão em memória avança. A memória é só cache: uma sessão ausente dele
é reconstruída reaplicando os eventos, de modo que a API pode reiniciar sem perder nada.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from adia.guarda.veredito import revela_resposta
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao
from adia.ia.subagentes.papeis import PAPEIS, pedido
from adia.nucleo.correcao.motor import Julgamento, Resultado, corrigir
from adia.nucleo.itens.banco import BancoDeItens
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.nucleo.itens.modelo import Item
from adia.nucleo.sessao.gestor import OperacaoRecusada, ResumoDoCiclo, Sessao
from adia.persistencia.repositorio import RegistroDeSessao, Repositorio
from adia.tipos import Condicao, Nivel


@dataclass(frozen=True)
class Dica:
    nivel: Nivel
    texto: str
    origem: str
    """``ia`` quando o modelo gerou e a guarda aprovou; ``pre-escrita`` nos demais casos."""
    motivo: str | None = None


class SessaoInconsistente(RuntimeError):
    """Os eventos gravados não reproduzem a sessão com o banco de itens atual."""


class Servico:
    def __init__(
        self, diretorio_de_itens: Path, cliente: ClienteOllama, repositorio: Repositorio, semente: int = 20261030
    ) -> None:
        carga = carregar(arquivos_de_itens(diretorio_de_itens))
        if not isinstance(carga, CargaConcluida):
            # A API recusa servir com banco inválido (design §7), nomeando o erro.
            raise RuntimeError(f"Banco de itens inválido: {carga}")
        self.carga = carga
        self.semente = semente
        self.cliente = cliente
        self.repositorio = repositorio
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

    def _da_sessao(self, sessao_id: str) -> threading.RLock:
        with self._trava:
            return self._travas.setdefault(sessao_id, threading.RLock())

    @property
    def banco(self) -> BancoDeItens:
        return self._banco(self.semente)

    def criar(self, condicao: Condicao) -> tuple[str, Sessao]:
        sessao_id = uuid.uuid4().hex[:12]
        self.repositorio.criar_sessao(RegistroDeSessao(sessao_id, condicao, self.semente))
        sessao = Sessao(self.banco, condicao)
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

    def _esquecer(self, sessao_id: str) -> None:
        with self._trava:
            self._sessoes.pop(sessao_id, None)

    def _reconstruir(self, sessao_id: str) -> Sessao:
        lido = self.repositorio.ler_sessao(sessao_id)
        if lido is None:
            raise OperacaoRecusada("Sessão inexistente.")
        registro, eventos = lido
        sessao = Sessao(self._banco(registro.semente), registro.condicao)
        for evento in eventos:
            atual = sessao.item_atual
            if atual is None or atual.id != evento.item_id:
                raise SessaoInconsistente(
                    f"Sessão {sessao_id}: evento do item {evento.item_id} não corresponde ao item "
                    f"{None if atual is None else atual.id}. O banco de itens mudou desde a gravação?"
                )
            if evento.tipo == "dica":
                assert evento.nivel is not None
                sessao.registrar_dica(evento.nivel, evento.explicacao or "")
            else:
                assert evento.confianca is not None
                sessao.responder(evento.acerto, evento.confianca)
        return sessao

    def responder(self, sessao_id: str, resposta: str, confianca: int) -> tuple[Julgamento, ResumoDoCiclo | None]:
        with self._da_sessao(sessao_id):
            sessao = self.obter(sessao_id)
            item = sessao.item_atual
            if item is None:
                raise OperacaoRecusada("Sessão encerrada.")
            julgamento = corrigir(item, resposta)
            if julgamento.motivo_rejeicao is not None:
                raise OperacaoRecusada(julgamento.motivo_rejeicao)
            acerto = julgamento.resultado is Resultado.ACERTO if isinstance(julgamento.resultado, Resultado) else None
            try:
                with self.repositorio.transacao() as conexao:
                    Repositorio.registrar_resposta(conexao, sessao_id, sessao, resposta, acerto, confianca)
                    resumo = sessao.responder(acerto, confianca)
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
            return Dica(nivel, pre_escrita, "pre-escrita", f"IA indisponível: {erro}")
        if revela_resposta(gerada.texto, item):
            return Dica(nivel, pre_escrita, "pre-escrita", "guarda descartou a dica gerada")
        return Dica(nivel, gerada.texto, "ia")
