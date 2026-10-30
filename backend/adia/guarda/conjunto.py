"""Conjunto declarado de verificação da guarda e os dois portões de R7.11 (DO-03).

O conjunto é ``data/guarda/conjunto_verificacao.jsonl`` mais o catálogo inteiro de dicas
pré-escritas, que entra como legítimo: catálogo que vaza é protótipo que vaza.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from adia.guarda.veredito import forma_do_vazamento
from adia.nucleo.itens.modelo import Item

FORMAS_OBRIGATORIAS: Final = frozenset({"literal", "numero", "aritmetica", "equacao"})
"""Composição mínima: ao menos um caso de vazamento por forma que a guarda reconhece."""

ACERTO_LEGITIMO_MINIMO: Final = Decimal("0.95")


@dataclass(frozen=True)
class Caso:
    id: str
    item_id: str
    texto: str
    vazamento: bool
    forma: str | None
    procedencia: str


@dataclass
class Relatorio:
    vp: int = 0
    fn: int = 0
    vn: int = 0
    fp: int = 0
    formas_cobertas: set[str] = field(default_factory=set)
    erros: list[str] = field(default_factory=list)

    @property
    def acerto_legitimo(self) -> Decimal:
        total = self.vn + self.fp
        return Decimal(self.vn) / Decimal(total) if total else Decimal(0)

    @property
    def formas_faltantes(self) -> frozenset[str]:
        return FORMAS_OBRIGATORIAS - self.formas_cobertas

    @property
    def aprovado(self) -> bool:
        return (
            self.fn == 0
            and self.vp > 0
            and self.acerto_legitimo >= ACERTO_LEGITIMO_MINIMO
            and not self.formas_faltantes
        )


def ler_conjunto(texto: str) -> list[Caso]:
    """Uma linha JSON por caso. Linha inválida é erro, nunca caso ignorado."""
    casos: list[Caso] = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if not linha.strip():
            continue
        try:
            dado = json.loads(linha)
            esperado = dado["esperado"]
            if esperado not in {"vazamento", "legitimo"}:
                raise ValueError(f"esperado inválido: {esperado!r}")
            casos.append(
                Caso(
                    id=str(dado["id"]),
                    item_id=str(dado["item_id"]),
                    texto=str(dado["texto"]),
                    vazamento=esperado == "vazamento",
                    forma=None if dado.get("forma") is None else str(dado["forma"]),
                    procedencia=str(dado["procedencia"]),
                )
            )
        except (ValueError, KeyError, TypeError) as erro:
            raise ValueError(f"linha {numero} do conjunto da guarda: {erro}") from erro
    return casos


def casos_do_catalogo(itens: Iterable[Item]) -> list[Caso]:
    return [
        Caso(f"catalogo:{item.id}:{nivel.name}", item.id, texto, False, None, "catálogo pré-escrito")
        for item in itens
        for nivel, texto in sorted(item.dicas.items())
    ]


def avaliar_conjunto(casos: Iterable[Caso], itens: Mapping[str, Item]) -> Relatorio:
    relatorio = Relatorio()
    for caso in casos:
        item = itens.get(caso.item_id)
        if item is None:
            relatorio.erros.append(f"{caso.id}: item {caso.item_id} não existe no banco")
            relatorio.fn += int(caso.vazamento)
            continue
        forma = forma_do_vazamento(caso.texto, item)
        if caso.vazamento:
            if forma is None:
                relatorio.fn += 1
                relatorio.erros.append(f"{caso.id}: vazamento ({caso.forma}) NÃO detectado")
            else:
                relatorio.vp += 1
                if caso.forma is not None and forma == caso.forma:
                    relatorio.formas_cobertas.add(forma)
        elif forma is None:
            relatorio.vn += 1
        else:
            relatorio.fp += 1
            relatorio.erros.append(f"{caso.id}: dica legítima descartada como {forma}")
    return relatorio
