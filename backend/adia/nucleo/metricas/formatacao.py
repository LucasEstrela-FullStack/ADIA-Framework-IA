"""Apresentação de métrica em tela (DO-06): beco sem saída no fluxo de dados.

Duas casas, meio para cima. Nunca alimenta comparação com limiar nem exportação, que
continuam sem arredondamento.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from adia.tipos import Indisponivel, Medida, e_disponivel

IIC_ALTO: Final = Decimal("0.8")
TAI_BAIXA: Final = Decimal("0.4")


def para_tela(valor: Medida) -> str:
    if isinstance(valor, Indisponivel):
        return "indisponível"
    return str(valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)).replace(".", ",")


def aviso_do_iic(iic: Medida, tai: Medida) -> str | None:
    """DO-05: IIC alto com TAI baixa vem de acertar pouco com e sem ajuda, não de independência."""
    if e_disponivel(iic) and e_disponivel(tai) and iic >= IIC_ALTO and tai < TAI_BAIXA:
        return "IIC alto com TAI baixa: desempenho baixo com e sem ajuda também produz IIC alto."
    return None
