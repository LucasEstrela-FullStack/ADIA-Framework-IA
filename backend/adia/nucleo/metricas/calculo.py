"""Métricas de um conjunto de respostas: proporções em ``Decimal`` ou indisponíveis (R11.7)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from adia.tipos import Indisponivel, Medida, Nivel, e_disponivel


def proporcao(acertos: int, total: int, motivo: str) -> Medida:
    """``acertos / total``, ou indisponível quando não há base (denominador zero)."""
    if total == 0:
        return Indisponivel(motivo)
    return Decimal(acertos) / Decimal(total)


def taxa_de_acerto(acertos: Sequence[bool], motivo: str) -> Medida:
    return proporcao(sum(acertos), len(acertos), motivo)


def confianca_media(confiancas: Sequence[int], motivo: str) -> Medida:
    """Média da confiança de 0 a 10, normalizada para 0 a 1."""
    if not confiancas:
        return Indisponivel(motivo)
    return Decimal(sum(confiancas)) / Decimal(10 * len(confiancas))


def dss(dicas_usadas: int, itens_praticados: int) -> Medida:
    """Dose de Suporte Solicitada: dicas ÷ (nível máximo × itens praticados) (R11.4)."""
    return proporcao(dicas_usadas, int(Nivel.L4) * itens_praticados, "nenhum item praticado")


def iic(independente: Medida, assistido: Medida) -> Medida:
    """Índice de Independência Cognitiva: independente ÷ assistido, limitado a 1."""
    if not (e_disponivel(independente) and e_disponivel(assistido)):
        return Indisponivel("IIC depende de acerto independente e assistido disponíveis")
    if assistido == 0:
        return Indisponivel("acerto assistido zero")
    return min(Decimal(1), independente / assistido)
