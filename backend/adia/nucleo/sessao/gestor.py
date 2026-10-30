"""Gestor_de_Sessão: percurso do CognitiveLoop, teto vigente e registro das respostas.

Percurso: linha de base, depois ``CICLOS`` repetições de prática assistida seguida de
desafio independente, com o gatilho de *fading* ao fim de cada desafio (R12.1). Puro: sem
relógio, sem rede, sem IA. Quem chama corrige a resposta e informa o acerto.

shortcut: termina após o terceiro ciclo; projeto STEAM e teste de retenção de 7 dias ficam
fora do percurso, e o estado vive só em memória. Acrescentar com a persistência em SQLite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from adia.nucleo.itens.banco import BancoDeItens, ConjuntoDoDesafio
from adia.nucleo.itens.modelo import Item
from adia.nucleo.metricas.calculo import confianca_media, dss, iic, taxa_de_acerto
from adia.nucleo.regulacao.regra import DecisaoDeRegulacao, EntradaDeRegulacao, aplicar, decidir
from adia.tipos import Condicao, Etapa, Medida, Nivel

CICLOS = 3
FIM = "fim"


class OperacaoRecusada(Exception):
    """Operação fora do que a etapa atual permite (pedido de dica sem IA, acima do teto...)."""


@dataclass(frozen=True)
class Resposta:
    etapa: Etapa
    ciclo: int
    item_id: str
    acerto: bool | None
    """``None`` quando o item não tem correção automática (gabarito textual)."""
    confianca: int
    dicas: tuple[Nivel, ...]


@dataclass(frozen=True)
class ResumoDoCiclo:
    ciclo: int
    teto: Nivel
    acerto_assistido: Medida
    acerto_independente: Medida
    transferencia: Medida
    confianca: Medida
    dss: Medida
    iic: Medida
    decisao: DecisaoDeRegulacao
    teto_seguinte: Nivel


@dataclass
class Sessao:
    banco: BancoDeItens
    condicao: Condicao
    etapa: Etapa | str = Etapa.LINHA_DE_BASE
    ciclo: int = 0
    teto: Nivel = Nivel.L4
    """L4 é o teto inicial do primeiro ciclo nas três condições (R9.10)."""
    fila: list[Item] = field(default_factory=list)
    respostas: list[Resposta] = field(default_factory=list)
    ciclos: list[ResumoDoCiclo] = field(default_factory=list)
    onloading: bool = False
    justificativa_exigida: bool = False
    _dicas_do_item: list[Nivel] = field(default_factory=list)
    _conjunto: ConjuntoDoDesafio | None = None

    def __post_init__(self) -> None:
        self.fila = list(self.banco.elegiveis_sem_ia(Etapa.LINHA_DE_BASE, frozenset()))

    @property
    def encerrada(self) -> bool:
        return self.etapa == FIM

    @property
    def item_atual(self) -> Item | None:
        return self.fila[0] if self.fila else None

    @property
    def com_ia(self) -> bool:
        return self.etapa == Etapa.PRATICA_ASSISTIDA

    @property
    def dicas_do_item(self) -> tuple[Nivel, ...]:
        return tuple(self._dicas_do_item)

    def registrar_dica(self, nivel: Nivel, explicacao: str = "") -> Item:
        """Valida o pedido de dica do item atual e o registra (R6.4, R10.1)."""
        item = self.item_atual
        if item is None or not self.com_ia:
            raise OperacaoRecusada("A IA está desativada nesta etapa.")
        if nivel > self.teto:
            raise OperacaoRecusada(f"Nível {nivel.name} acima do teto vigente {self.teto.name}.")
        if self.onloading and not self._dicas_do_item and not explicacao.strip():
            raise OperacaoRecusada("Explique o que você já tentou antes de pedir a primeira dica.")
        if nivel not in self._dicas_do_item:
            self._dicas_do_item.append(nivel)
        return item

    def responder(self, acerto: bool | None, confianca: int) -> ResumoDoCiclo | None:
        """Registra a resposta do item atual e avança. Devolve o resumo quando um ciclo fecha."""
        item = self.item_atual
        if item is None or self.encerrada:
            raise OperacaoRecusada("Sessão encerrada.")
        if not 0 <= confianca <= 10:
            raise OperacaoRecusada("Confiança deve estar entre 0 e 10.")
        assert isinstance(self.etapa, Etapa)
        self.respostas.append(
            Resposta(self.etapa, self.ciclo, item.id, acerto, confianca, tuple(self._dicas_do_item))
        )
        self._dicas_do_item.clear()
        self.fila.pop(0)
        if self.fila:
            return None
        return self._avancar()

    def _apresentados(self) -> frozenset[str]:
        return frozenset(r.item_id for r in self.respostas)

    def _avancar(self) -> ResumoDoCiclo | None:
        if self.etapa == Etapa.DESAFIO_INDEPENDENTE:
            resumo = self._fechar_ciclo()
            if self.ciclo == CICLOS:
                self.etapa = FIM
                return resumo
            self._iniciar_pratica()
            return resumo
        if self.etapa == Etapa.LINHA_DE_BASE:
            self._iniciar_pratica()
            return None
        self._iniciar_desafio()
        return None

    def _iniciar_pratica(self) -> None:
        praticados = sorted((i for i in self.banco.itens if i.e_praticado), key=lambda i: i.id)
        por_ciclo = len(praticados) // CICLOS
        self.ciclo += 1
        self.etapa = Etapa.PRATICA_ASSISTIDA
        self.fila = praticados[(self.ciclo - 1) * por_ciclo : self.ciclo * por_ciclo]

    def _iniciar_desafio(self) -> None:
        praticados = [r.item_id for r in self.respostas if r.ciclo == self.ciclo]
        habilidade = self.banco.obter(praticados[0], Etapa.PRATICA_ASSISTIDA)
        assert isinstance(habilidade, Item)
        conjunto = self.banco.conjunto_do_desafio(
            praticados, habilidade.habilidade_alvo, self._apresentados()
        )
        if not isinstance(conjunto, ConjuntoDoDesafio):
            raise OperacaoRecusada(conjunto.mensagem)
        self._conjunto = conjunto
        self.etapa = Etapa.DESAFIO_INDEPENDENTE
        self.fila = [par.equivalente for par in conjunto.pares] + list(conjunto.transferencia)

    def _fechar_ciclo(self) -> ResumoDoCiclo:
        def acertos(etapa: Etapa, transferencia: bool | None = None) -> list[bool]:
            ids_transferencia = {i.id for i in self._conjunto.transferencia} if self._conjunto else set()
            return [
                r.acerto
                for r in self.respostas
                if r.ciclo == self.ciclo
                and r.etapa == etapa
                and r.acerto is not None
                and (transferencia is None or (r.item_id in ids_transferencia) == transferencia)
            ]

        pratica = [r for r in self.respostas if r.ciclo == self.ciclo and r.etapa == Etapa.PRATICA_ASSISTIDA]
        desafio = [r for r in self.respostas if r.ciclo == self.ciclo and r.etapa == Etapa.DESAFIO_INDEPENDENTE]
        assistido = taxa_de_acerto(acertos(Etapa.PRATICA_ASSISTIDA), "nenhum item praticado corrigido")
        independente = taxa_de_acerto(acertos(Etapa.DESAFIO_INDEPENDENTE), "nenhum item do desafio corrigido")
        confianca = confianca_media([r.confianca for r in desafio], "sem respostas no desafio")
        decisao = decidir(EntradaDeRegulacao(assistido, independente, confianca, self.teto))
        teto_seguinte = aplicar(self.condicao, decisao, self.teto)
        resumo = ResumoDoCiclo(
            ciclo=self.ciclo,
            teto=self.teto,
            acerto_assistido=assistido,
            acerto_independente=independente,
            transferencia=taxa_de_acerto(
                acertos(Etapa.DESAFIO_INDEPENDENTE, transferencia=True), "sem item de transferência"
            ),
            confianca=confianca,
            dss=dss(sum(len(r.dicas) for r in pratica), len(pratica)),
            iic=iic(independente, assistido),
            decisao=decisao,
            teto_seguinte=teto_seguinte,
        )
        self.ciclos.append(resumo)
        self.teto = teto_seguinte
        # Em A e C a decisão é sombra: onloading e justificativa só valem na condição B.
        self.onloading = self.condicao is Condicao.B and decisao.onloading_ativado
        self.justificativa_exigida = self.condicao is Condicao.B and decisao.justificativa_exigida
        return resumo
