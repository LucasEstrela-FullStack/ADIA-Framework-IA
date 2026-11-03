"""Atalhos cognitivos: padrões mensuráveis no registro de eventos (R19.2, DO-48).

Cada padrão é uma condição sobre o log, sem julgamento humano e sem modelo de linguagem, e
vem com a sua oportunidade: o número de vezes em que ele *poderia* ter acontecido. O mapa de
calor mostra ocorrências sobre oportunidades, para que um estudante que respondeu mais itens
não pareça ter mais atalhos só por isso. Indicador de comportamento, não diagnóstico (R25.8).

Puro: os instantes vêm do registro, não do relógio.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from adia.tipos import ETAPAS_SEM_IA


@dataclass(frozen=True)
class Padrao:
    id: str
    nome: str
    condicao: str


DICA_ALTA_DIRETA: Final = Padrao(
    "dica_alta_direta",
    "Dica alta direta",
    "a primeira dica pedida no item é L3 ou L4; oportunidade: item respondido com alguma dica",
)
RESPOSTA_APOS_EXEMPLO: Final = Padrao(
    "resposta_logo_apos_exemplo",
    "Resposta logo após o exemplo",
    "a resposta chega menos de 20 s depois da última dica L4 do item; oportunidade: item com L4",
)
RESPOSTA_RELAMPAGO: Final = Padrao(
    "resposta_relampago",
    "Resposta relâmpago sem IA",
    "em etapa sem IA, a resposta chega menos de 5 s depois da resposta anterior ou do início; "
    "oportunidade: resposta em etapa sem IA",
)
PADROES: Final = (DICA_ALTA_DIRETA, RESPOSTA_APOS_EXEMPLO, RESPOSTA_RELAMPAGO)

APOS_EXEMPLO: Final = timedelta(seconds=20)
RELAMPAGO: Final = timedelta(seconds=5)
"""Pontos de partida provisórios de DO-48, a revisar com dados do piloto."""


@dataclass(frozen=True)
class EventoDoLog:
    tipo: str
    """``dica`` ou ``resposta``."""
    etapa: str
    item_id: str
    nivel: int | None
    criado_em: datetime


@dataclass(frozen=True)
class Contagem:
    ocorrencias: int = 0
    oportunidades: int = 0

    def mais(self, ocorreu: bool) -> Contagem:
        return Contagem(self.ocorrencias + int(ocorreu), self.oportunidades + 1)


def contar(
    eventos: Sequence[EventoDoLog], inicio: datetime, habilidade_de: Mapping[str, str]
) -> dict[tuple[str, str], Contagem]:
    """Contagem por ``(habilidade alvo, id do padrão)`` de uma sessão, em ordem de registro.

    ``inicio`` é a criação da sessão: a primeira resposta mede o tempo a partir dele. Item
    fora de ``habilidade_de`` conta na habilidade ``"desconhecida"``, em vez de sumir.
    """
    contagens: dict[tuple[str, str], Contagem] = {}
    dicas: dict[str, list[tuple[int, datetime]]] = {}
    anterior = inicio

    def registrar(habilidade: str, padrao: Padrao, ocorreu: bool) -> None:
        chave = (habilidade, padrao.id)
        contagens[chave] = contagens.get(chave, Contagem()).mais(ocorreu)

    for evento in eventos:
        if evento.tipo == "dica":
            if evento.nivel is not None:
                dicas.setdefault(evento.item_id, []).append((evento.nivel, evento.criado_em))
            continue
        habilidade = habilidade_de.get(evento.item_id, "desconhecida")
        do_item = dicas.pop(evento.item_id, [])
        if do_item:
            registrar(habilidade, DICA_ALTA_DIRETA, do_item[0][0] >= 3)
        exemplos = [instante for nivel, instante in do_item if nivel == 4]
        if exemplos:
            registrar(habilidade, RESPOSTA_APOS_EXEMPLO, evento.criado_em - exemplos[-1] < APOS_EXEMPLO)
        if evento.etapa in ETAPAS_SEM_IA:  # StrEnum: o rótulo gravado compara igual ao membro
            registrar(habilidade, RESPOSTA_RELAMPAGO, evento.criado_em - anterior < RELAMPAGO)
        anterior = evento.criado_em
    return contagens
