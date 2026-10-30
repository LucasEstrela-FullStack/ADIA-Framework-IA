"""Veredito da guarda: a dica gerada revela a resposta do item? (D3, R7.2)

Falha fechada: na dúvida, a dica é descartada e a orquestração entrega a dica pré-escrita
do mesmo nível. Um falso positivo custa só a troca por texto revisado; um falso negativo
entrega a resposta e invalida a medida.

shortcut: detecta o gabarito e as variações declaradas, literalmente ou como número dentro
da tolerância; não reconstrói aritmética implícita ("8 dividido por 2"). Substituir pelo
perfil completo de §3.11 quando o conjunto de verificação da guarda existir.
"""

from __future__ import annotations

import re
from decimal import Decimal

from adia.nucleo.correcao.motor import dentro_da_tolerancia, interpretar_decimal
from adia.nucleo.itens.modelo import Item, TipoGabarito

_NUMERO = re.compile(r"-?\d+(?:[.,]\d+)?")


def _normalizar(texto: str) -> str:
    return " ".join(texto.casefold().split())


def revela_resposta(texto: str, item: Item) -> bool:
    """Verdadeiro quando ``texto`` contém a resposta do item em alguma forma declarada."""
    normalizado = _normalizar(texto)
    for forma in (item.gabarito, *item.variacoes_gabarito):
        alvo = _normalizar(forma)
        if alvo and not _NUMERO.fullmatch(alvo) and re.search(rf"(?<!\w){re.escape(alvo)}(?!\w)", normalizado):
            return True
    if item.tipo_gabarito is not TipoGabarito.NUMERICO:
        return False
    gabarito = interpretar_decimal(item.gabarito)
    if gabarito is None:
        return True
    tolerancia = item.tolerancia if item.tolerancia is not None else Decimal(0)
    for trecho in _NUMERO.findall(texto):
        valor = interpretar_decimal(trecho)
        if valor is not None and dentro_da_tolerancia(valor, gabarito, tolerancia):
            return True
    return False
