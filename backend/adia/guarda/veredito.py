"""Veredito da guarda: a dica revela a resposta do item? (D3, R7.2)

Falha fechada: na dúvida, a dica é descartada e a orquestração entrega a dica pré-escrita
do mesmo nível. Um falso positivo custa só a troca por texto revisado; um falso negativo
entrega a resposta e invalida a medida (DO-03).

Formas de vazamento reconhecidas, na ordem em que são testadas:

- ``literal``: o gabarito ou uma variação declarada escrita no texto (``quatro``);
- ``numero``: número dentro da tolerância do gabarito, inclusive com milhar (``1.500``);
- ``aritmetica``: expressão cujo resultado é o gabarito (``8 dividido por 2``), por DO-10;
- ``equacao``: equação linear na incógnita cuja solução é o gabarito (``2x = 8``), exceto a
  própria equação do enunciado, que repetir não entrega nada;
- ``orcamento``: a verificação passou de 2 s (DO-02), e na dúvida é vazamento;
- ``gabarito_ilegivel``: gabarito numérico que não se lê como número.
"""

from __future__ import annotations

import re
import time
from decimal import Decimal
from fractions import Fraction
from typing import Final

from adia.guarda.aritmetica import avaliar
from adia.nucleo.correcao.motor import dentro_da_tolerancia, interpretar_decimal
from adia.nucleo.itens.modelo import Item, TipoGabarito

ORCAMENTO_S: Final = 2.0
"""DO-02."""

_NUMERO: Final = re.compile(r"\d{1,3}(?:[. ]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")


def _normalizar(texto: str) -> str:
    return " ".join(texto.casefold().split())


def _leituras(trecho: str) -> set[Decimal]:
    """Todas as leituras de um número: ``1.500`` é 1,5 e também 1500. Na dúvida, as duas."""
    leituras: set[Decimal] = set()
    direta = interpretar_decimal(trecho.replace(" ", ""))
    if direta is not None:
        leituras.add(direta)
    if re.fullmatch(r"\d{1,3}(?:[. ]\d{3})+(?:,\d+)?", trecho):
        sem_milhar = interpretar_decimal(trecho.replace(".", "").replace(" ", ""))
        if sem_milhar is not None:
            leituras.add(sem_milhar)
    return leituras


def forma_do_vazamento(texto: str, item: Item) -> str | None:
    """Forma de vazamento encontrada em ``texto``, ou ``None`` quando a dica é legítima."""
    inicio = time.monotonic()
    normalizado = _normalizar(texto)
    for forma in (item.gabarito, *item.variacoes_gabarito):
        alvo = _normalizar(forma)
        if alvo and not _NUMERO.fullmatch(alvo) and re.search(rf"(?<!\w){re.escape(alvo)}(?!\w)", normalizado):
            return "literal"
    if item.tipo_gabarito is not TipoGabarito.NUMERICO:
        return None
    gabarito = interpretar_decimal(item.gabarito)
    if gabarito is None:
        return "gabarito_ilegivel"
    tolerancia = item.tolerancia if item.tolerancia is not None else Decimal(0)

    def bate(valor: Decimal) -> bool:
        return dentro_da_tolerancia(valor, gabarito, tolerancia)

    for trecho in _NUMERO.findall(texto):
        if any(bate(valor) for valor in _leituras(trecho)):
            return "numero"
    if time.monotonic() - inicio > ORCAMENTO_S:
        return "orcamento"

    def bate_fracao(valor: Fraction) -> bool:
        return bate(Decimal(valor.numerator) / Decimal(valor.denominator))

    resultado = avaliar(texto, item.incognita)
    if any(bate_fracao(valor) for valor in resultado.expressoes):
        return "aritmetica"
    do_enunciado = {equacao for _, equacao in avaliar(item.enunciado, item.incognita).solucoes}
    if any(bate_fracao(valor) and equacao not in do_enunciado for valor, equacao in resultado.solucoes):
        return "equacao"
    if time.monotonic() - inicio > ORCAMENTO_S:
        return "orcamento"
    return None


def revela_resposta(texto: str, item: Item) -> bool:
    """Verdadeiro quando ``texto`` entrega a resposta do item em alguma forma reconhecida."""
    return forma_do_vazamento(texto, item) is not None


__all__ = ["ORCAMENTO_S", "forma_do_vazamento", "revela_resposta"]
