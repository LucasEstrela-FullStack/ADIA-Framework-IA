"""Avaliador aritmético da guarda: expressões e equações lineares, sem ``eval`` (DO-10).

Gramática restrita, analisador descendente recursivo, aritmética em ``Fraction``. Cada valor
é uma forma linear ``a·v + b`` na incógnita do item, o que resolve com o mesmo analisador
as duas formas de vazamento sem gabarito escrito:

- expressão sem incógnita cujo resultado é o gabarito (``8 / 2``, ``11 - 3 dividido por 2``);
- equação linear na incógnita cuja solução é o gabarito (``2x = 8``), o passo intermediário
  que entrega a resposta sem escrevê-la.

Limites de DO-10: até 32 candidatas por texto, 64 tokens por candidata, profundidade 8 de
parênteses e expoente até 6. Divisão por zero e forma não linear descartam a candidata.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from typing import Final

MAX_CANDIDATAS: Final = 32
MAX_TOKENS: Final = 64
MAX_PROFUNDIDADE: Final = 8
MAX_EXPOENTE: Final = 6

_PALAVRAS: Final = (
    (r"\bmultiplicad[oa]s?\s+por\b", " * "),
    (r"\bdividid[oa]s?\s+por\b", " / "),
    (r"\bvezes\b", " * "),
    (r"\bmais\b", " + "),
    (r"\bmenos\b", " - "),
    (r"\b(?:é\s+)?igual\s+a\b", " = "),
    (r"[×·]", " * "),
    # `:` fica de fora: em texto corrido é pontuação ("Passo 2: 8 / 2") e viraria divisão.
    (r"÷", " / "),
    (r"[−–]", " - "),
)

_NUMERO: Final = r"\d+(?:,\d+)?"
# A incógnita é letra isolada: `2x` conta, o `x` final de `max` não.
_TOKEN: Final = re.compile(
    rf"(?P<num>{_NUMERO})|(?<![a-zà-ú])(?P<var>[a-z])(?![a-zà-ú])|(?P<op>[-+*/^()=])|(?P<outro>\S)"
)


@dataclass(frozen=True)
class Linear:
    """``a·v + b``. ``a == 0`` é constante."""

    a: Fraction
    b: Fraction


class _Descarte(Exception):
    """Candidata fora da gramática ou dos limites: ignorada, nunca propagada."""


def normalizar(texto: str) -> str:
    """Minúsculas, operadores por extenso trocados por símbolos e milhar com ponto removido.

    O ponto vira separador de milhar só no padrão ``1.500``; nos demais casos é fim de frase.
    """
    saida = texto.casefold()
    for padrao, simbolo in _PALAVRAS:
        saida = re.sub(padrao, simbolo, saida)
    saida = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", saida)
    saida = re.sub(r"(?<=\d)\.(?=\d)", ",", saida)
    return saida


def _tokens(texto: str, incognita: str | None) -> Iterator[tuple[str, str] | None]:
    """Tokens matemáticos; ``None`` marca a quebra entre trechos (palavra que não é conta)."""
    for casamento in _TOKEN.finditer(texto):
        tipo = casamento.lastgroup
        valor = casamento.group()
        if tipo == "num":
            yield ("num", valor)
        elif tipo == "var" and valor == incognita:
            yield ("var", valor)
        elif tipo == "op":
            yield ("op", valor)
        else:
            yield None


def _trechos(texto: str, incognita: str | None) -> list[list[tuple[str, str]]]:
    trechos: list[list[tuple[str, str]]] = [[]]
    for token in _tokens(texto, incognita):
        if token is None:
            if trechos[-1]:
                trechos.append([])
        else:
            trechos[-1].append(token)
    return [t for t in trechos if t]


class _Analisador:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        if len(tokens) > MAX_TOKENS:
            raise _Descarte
        self.tokens = tokens
        self.pos = 0
        self.profundidade = 0

    def _olhar(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _consumir(self) -> tuple[str, str]:
        token = self._olhar()
        if token is None:
            raise _Descarte
        self.pos += 1
        return token

    def analisar(self) -> Linear:
        valor = self._expr()
        if self.pos != len(self.tokens):
            raise _Descarte
        return valor

    def _expr(self) -> Linear:
        valor = self._termo()
        while (token := self._olhar()) is not None and token[1] in "+-":
            self._consumir()
            outro = self._termo()
            sinal = 1 if token[1] == "+" else -1
            valor = Linear(valor.a + sinal * outro.a, valor.b + sinal * outro.b)
        return valor

    def _termo(self) -> Linear:
        valor = self._potencia()
        while (token := self._olhar()) is not None and (
            token[1] in "*/" or token[0] in {"num", "var"} or token[1] == "("
        ):
            operador = self._consumir()[1] if token[1] in "*/" else "*"
            outro = self._potencia()
            valor = _multiplicar(valor, outro) if operador == "*" else _dividir(valor, outro)
        return valor

    def _potencia(self) -> Linear:
        base = self._unario()
        token = self._olhar()
        if token is not None and token[1] == "^":
            self._consumir()
            expoente = self._unario()
            if base.a != 0 or expoente.a != 0 or expoente.b.denominator != 1 or abs(expoente.b) > MAX_EXPOENTE:
                raise _Descarte
            if base.b == 0 and expoente.b < 0:
                raise _Descarte
            return Linear(Fraction(0), base.b ** int(expoente.b))
        return base

    def _unario(self) -> Linear:
        token = self._olhar()
        if token is not None and token[1] in "+-":
            self._consumir()
            valor = self._unario()
            return valor if token[1] == "+" else Linear(-valor.a, -valor.b)
        return self._primario()

    def _primario(self) -> Linear:
        tipo, valor = self._consumir()
        if tipo == "num":
            return Linear(Fraction(0), Fraction(valor.replace(",", ".")))
        if tipo == "var":
            return Linear(Fraction(1), Fraction(0))
        if valor == "(":
            self.profundidade += 1
            if self.profundidade > MAX_PROFUNDIDADE:
                raise _Descarte
            dentro = self._expr()
            if self._consumir()[1] != ")":
                raise _Descarte
            self.profundidade -= 1
            return dentro
        raise _Descarte


def _multiplicar(x: Linear, y: Linear) -> Linear:
    if x.a != 0 and y.a != 0:
        raise _Descarte  # não linear
    return Linear(x.a * y.b + y.a * x.b, x.b * y.b)


def _dividir(x: Linear, y: Linear) -> Linear:
    if y.a != 0 or y.b == 0:
        raise _Descarte
    return Linear(x.a / y.b, x.b / y.b)


def _aparar(tokens: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Tira operadores binários soltos nas pontas (``+ 3`` no meio de uma frase)."""
    inicio, fim = 0, len(tokens)
    while inicio < fim and tokens[inicio][1] in "+*/^=)":
        inicio += 1
    while fim > inicio and tokens[fim - 1][1] in "+-*/^=(":
        fim -= 1
    return tokens[inicio:fim]


@dataclass(frozen=True)
class Resultado:
    """Valores que o texto calcula, cada um com a forma que o produziu."""

    expressoes: tuple[Fraction, ...]
    solucoes: tuple[tuple[Fraction, str], ...]
    """Solução de cada equação na incógnita, com a equação normalizada sem espaços."""


def avaliar(texto: str, incognita: str | None) -> Resultado:
    """Resultados das expressões com operador e soluções das equações lineares do texto."""
    expressoes: list[Fraction] = []
    solucoes: list[tuple[Fraction, str]] = []
    candidatas = 0
    for trecho in _trechos(normalizar(texto), incognita):
        lados: list[list[tuple[str, str]]] = [[]]
        for token in trecho:
            if token[1] == "=":
                lados.append([])
            else:
                lados[-1].append(token)
        valores: list[Linear | None] = []
        for lado in lados:
            lado = _aparar(lado)
            candidatas += 1
            if candidatas > MAX_CANDIDATAS:
                return Resultado(tuple(expressoes), tuple(solucoes))
            try:
                valor = _Analisador(lado).analisar() if lado else None
            except _Descarte:
                valor = None
            valores.append(valor)
            if valor is not None and valor.a == 0 and any(t[0] == "op" for t in lado):
                expressoes.append(valor.b)
        for esquerda, direita in zip(valores, valores[1:], strict=False):
            if esquerda is None or direita is None or esquerda.a == direita.a:
                continue
            solucoes.append(((direita.b - esquerda.b) / (esquerda.a - direita.a), "".join(t[1] for t in trecho)))
    return Resultado(tuple(expressoes), tuple(solucoes))
