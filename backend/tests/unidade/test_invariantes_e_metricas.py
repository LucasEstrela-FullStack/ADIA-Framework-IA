"""Invariantes do `Item`, métricas do ciclo e ramos da guarda fora do banco inicial."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

from adia.guarda.veredito import revela_resposta
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.nucleo.itens.modelo import Item, TipoGabarito
from adia.nucleo.metricas.calculo import confianca_media, dss, iic, proporcao, taxa_de_acerto
from adia.tipos import Indisponivel, Nivel

_ITENS = Path(__file__).resolve().parents[3] / "data" / "itens"


@pytest.fixture(scope="module")
def item() -> Item:
    carga = carregar(arquivos_de_itens(_ITENS))
    assert isinstance(carga, CargaConcluida)
    return next(i for i in carga.itens if i.id == "alg-eq-101")


@pytest.mark.parametrize(
    "mudanca",
    [
        {"id": " "},
        {"enunciado": ""},
        {"habilidade_alvo": ""},
        {"dificuldade": 0},
        {"tamanho_max_resposta": 0},
        {"gabarito": " "},
        {"etapas_permitidas": frozenset()},
        {"tolerancia": None},
        {"tolerancia": Decimal("-1")},
        {"tipo_gabarito": TipoGabarito.TEXTUAL, "termos_essenciais": ()},
        {"termos_essenciais": ((),)},
        {"dicas": MappingProxyType({Nivel.L1: "a", Nivel.L2: "b", Nivel.L3: "c"})},
        {"dicas": MappingProxyType({Nivel.L1: "a", Nivel.L2: " ", Nivel.L3: "c", Nivel.L4: "d"})},
    ],
)
def test_item_que_nao_sustenta_medida_e_recusado(item: Item, mudanca: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(item, **mudanca)  # type: ignore[arg-type]


def test_metricas_sem_base_ficam_indisponiveis_e_nunca_zero() -> None:
    assert isinstance(proporcao(0, 0, "sem base"), Indisponivel)
    assert isinstance(confianca_media([], "sem respostas"), Indisponivel)
    assert isinstance(dss(3, 0), Indisponivel)
    assert isinstance(iic(Indisponivel("x"), Decimal(1)), Indisponivel)
    assert isinstance(iic(Decimal(1), Decimal(0)), Indisponivel)


def test_metricas_com_base() -> None:
    assert taxa_de_acerto([True, False, True, True], "-") == Decimal("0.75")
    assert confianca_media([10, 5], "-") == Decimal("0.75")
    assert dss(2, 4) == Decimal(2) / Decimal(16)
    assert iic(Decimal("0.9"), Decimal("0.6")) == Decimal(1)  # limitado a 1
    assert iic(Decimal("0.3"), Decimal("0.6")) == Decimal("0.5")


def test_guarda_em_item_nao_numerico_so_compara_as_formas_declaradas(item: Item) -> None:
    alternativa = replace(item, tipo_gabarito=TipoGabarito.ALTERNATIVA, gabarito="c", variacoes_gabarito=("c",))
    assert revela_resposta("A alternativa certa é a c.", alternativa)
    assert not revela_resposta("Compare as alternativas com 4 e 11.", alternativa)


def test_guarda_falha_fechado_com_gabarito_numerico_ilegivel(item: Item) -> None:
    ilegivel = replace(item, gabarito="x≈4", variacoes_gabarito=())
    assert revela_resposta("Pense no que a igualdade pede.", ilegivel)
