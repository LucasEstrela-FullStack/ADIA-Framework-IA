"""Regra de regulação do README: precedência, saturação, arredondamento e indisponível."""

from __future__ import annotations

from decimal import Decimal

import pytest

from adia.nucleo.regulacao.regra import DecisaoDeRegulacao, EntradaDeRegulacao, aplicar, decidir
from adia.tipos import Condicao, Indisponivel, Medida, Nivel, TipoDecisao


def _decidir(assistido: Medida, independente: Medida, confianca: Medida, teto: Nivel = Nivel.L3) -> DecisaoDeRegulacao:
    return decidir(EntradaDeRegulacao(assistido, independente, confianca, teto))


@pytest.mark.parametrize(
    ("assistido", "independente", "confianca", "esperado"),
    [
        ("1", "0.5", "0.5", TipoDecisao.ONLOADING),  # gap 0,5 vence as demais condições
        ("0.9", "0.8", "0.9", TipoDecisao.FADING),
        ("0.8", "0.8", "1", TipoDecisao.FADING),  # |viés| = 0,2 exato: igualdade no limiar conta
        ("0.8", "0.8", "0.5", TipoDecisao.MANTER),  # viés −0,3: subconfiança barra o fading
        ("0.5", "0.3", "0.3", TipoDecisao.ESCALONAR),
        ("0.55", "0.3", "0.3", TipoDecisao.ESCALONAR),  # gap 0,25 exato não é onloading
        ("0.6", "0.6", "0.6", TipoDecisao.MANTER),
    ],
)
def test_precedencia(assistido: str, independente: str, confianca: str, esperado: TipoDecisao) -> None:
    assert _decidir(Decimal(assistido), Decimal(independente), Decimal(confianca)).tipo is esperado


def test_arredonda_a_quatro_casas_antes_do_limiar() -> None:
    # 0,79995 arredonda para 0,8000 com meio para cima (R9.12).
    assert _decidir(Decimal("0.8"), Decimal("0.79995"), Decimal("0.8")).tipo is TipoDecisao.FADING


def test_satura_em_l1_preservando_a_decisao() -> None:
    decisao = _decidir(Decimal(1), Decimal(1), Decimal(1), Nivel.L1)
    assert (decisao.tipo, decisao.teto_resultante, decisao.saturacao) == (TipoDecisao.FADING, Nivel.L1, True)


def test_satura_em_l4_ao_escalonar() -> None:
    decisao = _decidir(Decimal(0), Decimal(0), Decimal(0), Nivel.L4)
    assert (decisao.tipo, decisao.teto_resultante, decisao.saturacao) == (TipoDecisao.ESCALONAR, Nivel.L4, True)


def test_vies_alto_exige_justificativa() -> None:
    decisao = _decidir(Decimal("0.6"), Decimal("0.6"), Decimal("0.9"))
    assert decisao.justificativa_exigida
    assert decisao.tipo is TipoDecisao.MANTER


def test_indisponivel_mantem_o_teto_e_registra_o_motivo() -> None:
    decisao = _decidir(Indisponivel("sem itens"), Decimal(1), Decimal(1))
    assert (decisao.tipo, decisao.teto_resultante) == (TipoDecisao.MANTER, Nivel.L3)
    assert decisao.evidencia_incompleta == "sem itens"
    assert isinstance(decisao.gap, Indisponivel)


@pytest.mark.parametrize(
    ("condicao", "esperado"), [(Condicao.A, Nivel.L4), (Condicao.B, Nivel.L4), (Condicao.C, Nivel.L2)]
)
def test_aplicar_por_condicao(condicao: Condicao, esperado: Nivel) -> None:
    # A regra indica escalonar de L3 para L4; só B segue a regra, C desce por protocolo.
    decisao = _decidir(Decimal("0.3"), Decimal("0.3"), Decimal("0.3"))
    assert aplicar(condicao, decisao, Nivel.L3) is esperado
