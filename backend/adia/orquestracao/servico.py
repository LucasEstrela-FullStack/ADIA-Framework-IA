"""Orquestração: sessões, correção e dicas, ligando o núcleo puro à IA e à guarda.

É a única camada que vê os dois lados da fronteira de D1: o texto do modelo nunca entra no
núcleo, e nenhuma decisão de regulação depende dele.

shortcut: sessões só em memória (perdidas ao reiniciar a API); trocar por SQLite com o
Registro_de_Eventos.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from adia.guarda.veredito import revela_resposta
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao
from adia.ia.subagentes.papeis import PAPEIS, pedido
from adia.nucleo.correcao.motor import Julgamento, Resultado, corrigir
from adia.nucleo.itens.banco import BancoDeItens
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.nucleo.sessao.gestor import OperacaoRecusada, ResumoDoCiclo, Sessao
from adia.tipos import Condicao, Nivel


@dataclass(frozen=True)
class Dica:
    nivel: Nivel
    texto: str
    origem: str
    """``ia`` quando o modelo gerou e a guarda aprovou; ``pre-escrita`` nos demais casos."""
    motivo: str | None = None


class Servico:
    def __init__(self, diretorio_de_itens: Path, cliente: ClienteOllama, semente: int = 20261030) -> None:
        carga = carregar(arquivos_de_itens(diretorio_de_itens))
        if not isinstance(carga, CargaConcluida):
            # A API recusa servir com banco inválido (design §7), nomeando o erro.
            raise RuntimeError(f"Banco de itens inválido: {carga}")
        self.banco = BancoDeItens(carga, semente)
        self.cliente = cliente
        self.sessoes: dict[str, Sessao] = {}

    def criar(self, condicao: Condicao) -> tuple[str, Sessao]:
        sessao_id = uuid.uuid4().hex[:12]
        self.sessoes[sessao_id] = Sessao(self.banco, condicao)
        return sessao_id, self.sessoes[sessao_id]

    def obter(self, sessao_id: str) -> Sessao:
        try:
            return self.sessoes[sessao_id]
        except KeyError:
            raise OperacaoRecusada("Sessão inexistente.") from None

    def responder(self, sessao_id: str, resposta: str, confianca: int) -> tuple[Julgamento, ResumoDoCiclo | None]:
        sessao = self.obter(sessao_id)
        item = sessao.item_atual
        if item is None:
            raise OperacaoRecusada("Sessão encerrada.")
        julgamento = corrigir(item, resposta)
        if julgamento.motivo_rejeicao is not None:
            raise OperacaoRecusada(julgamento.motivo_rejeicao)
        acerto = julgamento.resultado is Resultado.ACERTO if isinstance(julgamento.resultado, Resultado) else None
        return julgamento, sessao.responder(acerto, confianca)

    def dica(self, sessao_id: str, nivel: Nivel, explicacao: str = "") -> Dica:
        sessao = self.obter(sessao_id)
        item = sessao.registrar_dica(nivel, explicacao)
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
