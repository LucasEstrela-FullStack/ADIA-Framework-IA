"""Filtro de qualidade da dica gerada (DO-51)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adia.guarda.qualidade import motivo_de_pobreza
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.nucleo.itens.modelo import Item
from adia.tipos import Nivel


@pytest.fixture(scope="module")
def itens() -> tuple[Item, ...]:
    carga = carregar(arquivos_de_itens(Path("data") / "itens"))
    assert isinstance(carga, CargaConcluida)
    return carga.itens


def _item(itens: tuple[Item, ...], enunciado_com: str) -> Item:
    return next(i for i in itens if enunciado_com in i.enunciado)


def test_toda_dica_pre_escrita_passa_no_filtro(itens: tuple[Item, ...]) -> None:
    """A dica de reserva não pode reprovar no critério que a convoca."""
    for item in itens:
        for nivel in (Nivel.L1, Nivel.L2, Nivel.L3):
            assert motivo_de_pobreza(item.dicas[nivel], item, nivel) is None, (item.id, nivel)


@pytest.mark.parametrize(
    ("nivel", "texto", "motivo"),
    [
        (Nivel.L3, "Isolar x.", "curta"),
        (Nivel.L1, "Tente lembrar o que a igualdade afirma sobre a incógnita.", "sem_pergunta"),
        (Nivel.L2, "A igualdade é uma balança: subtraia o termo constante dos dois lados.", "operacao_no_conceito"),
        (Nivel.L2, "Na balança, vamos dividir os dois lados pelo coeficiente da incógnita.", "operacao_no_conceito"),
        (Nivel.L2, "É uma balança, e para resolver você deve somar o mesmo aos dois lados.", "operacao_no_conceito"),
        (Nivel.L2, "Agora, resolva a equação 2x + 3 = 11 com calma e atenção.", "repete_o_enunciado"),
        (Nivel.L3, "Junte os termos parecidos até chegar em algo como 2x = 8 do outro lado.", "escreve_conta"),
        (Nivel.L1, "O que a igualdade afirma sobre a incógnita, e o que precisa valer nos dois lados?", None),
        (Nivel.L2, "Soma e multiplicação se desfazem por operações inversas, sem quebrar a igualdade.", None),
        (Nivel.L3, "Subtraia o termo constante dos dois lados para manter a igualdade.", None),
    ],
)
def test_motivos(itens: tuple[Item, ...], nivel: Nivel, texto: str, motivo: str | None) -> None:
    assert motivo_de_pobreza(texto, _item(itens, "2x + 3 = 11"), nivel) == motivo
