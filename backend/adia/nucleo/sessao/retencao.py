"""Janela do teste de retenção (DO-08), sem relógio: o instante atual vem de quem chama."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final

ABRE: Final = timedelta(hours=168)
FECHA: Final = timedelta(hours=216)


@dataclass(frozen=True)
class JanelaDaRetencao:
    abre_em: datetime
    disponivel: bool
    desvio_horas: Decimal | None
    """Horas além das 216 h; ``None`` dentro da janela. Fora da janela a porta abre com marca."""


def janela(posteste_concluido_em: datetime, agora: datetime) -> JanelaDaRetencao:
    """Antes de 168 h fecha; de 168 a 216 h abre; depois de 216 h abre e registra o desvio."""
    decorrido = agora - posteste_concluido_em
    desvio = None
    if decorrido > FECHA:
        desvio = Decimal(str((decorrido - FECHA).total_seconds())) / Decimal(3600)
    return JanelaDaRetencao(posteste_concluido_em + ABRE, decorrido >= ABRE, desvio)
