"""Avaliador aritmético e conjunto declarado da guarda (DO-02, DO-03, DO-10)."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from adia import caminhos, cli
from adia.guarda.aritmetica import MAX_CANDIDATAS, avaliar
from adia.guarda.conjunto import Caso, avaliar_conjunto, ler_conjunto
from adia.guarda.veredito import forma_do_vazamento
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.nucleo.itens.modelo import Item
from adia.orquestracao.benchmark import medir, relatorio

_ITENS = Path(__file__).resolve().parents[3] / "data" / "itens"


@pytest.fixture(scope="module")
def item() -> Item:
    carga = carregar(arquivos_de_itens(_ITENS))
    assert isinstance(carga, CargaConcluida)
    return next(i for i in carga.itens if i.id == "alg-eq-101")  # 2x + 3 = 11, x = 4


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("8 / 2", [Fraction(4)]),
        ("(11 - 3) / 2", [Fraction(4)]),
        ("2 ^ 3 + 1", [Fraction(9)]),
        ("8 dividido por 2", [Fraction(4)]),
        ("3 vezes 5 mais 1", [Fraction(16)]),
        ("1.500 - 500", [Fraction(1000)]),
        ("8 / 0", []),  # divisão por zero descartada
        ("2 ^ 7", []),  # expoente acima de 6
        ("((((((((((1 + 1))))))))))", []),  # profundidade acima de 8
        ("só o número 4 sozinho", []),  # número solto não é expressão
    ],
)
def test_expressoes(texto: str, esperado: list[Fraction]) -> None:
    assert list(avaliar(texto, None).expressoes) == esperado


@pytest.mark.parametrize(
    ("texto", "solucao"),
    [
        ("2x = 8", Fraction(4)),
        ("2x + 3 = 11", Fraction(4)),
        ("4x + 4 = 36", Fraction(8)),
        ("x = 3 * 2", Fraction(6)),
        ("2(x + 1) = 10", Fraction(4)),
    ],
)
def test_equacoes_lineares(texto: str, solucao: Fraction) -> None:
    assert [valor for valor, _ in avaliar(texto, "x").solucoes] == [solucao]


def test_equacao_nao_linear_e_letra_dentro_de_palavra_sao_ignoradas() -> None:
    assert avaliar("x * x = 16", "x").solucoes == ()
    assert avaliar("o max = 4", "x").solucoes == ()


def test_limite_de_candidatas_por_texto() -> None:
    texto = " e ".join(["1 + 1"] * (MAX_CANDIDATAS + 10))
    assert len(avaliar(texto, None).expressoes) == MAX_CANDIDATAS


def test_repetir_a_equacao_do_enunciado_nao_e_vazamento(item: Item) -> None:
    assert forma_do_vazamento("Olhe de novo para 2x + 3 = 11.", item) is None
    assert forma_do_vazamento("Daí sai 2x = 8.", item) == "equacao"


def test_milhar_conta_nas_duas_leituras(item: Item) -> None:
    grande = replace(item, gabarito="1500", variacoes_gabarito=("1500",))
    assert forma_do_vazamento("O total é 1.500.", grande) == "numero"
    assert forma_do_vazamento("O total é 1 500.", grande) == "numero"


def test_conjunto_reprova_vazamento_nao_detectado(item: Item) -> None:
    casos = [
        Caso("a", item.id, "Pense na balança.", True, "literal", "teste"),
        Caso("b", item.id, "x = 4", True, "numero", "teste"),
    ]
    relatorio = avaliar_conjunto(casos, {item.id: item})
    assert (relatorio.vp, relatorio.fn) == (1, 1)
    assert not relatorio.aprovado


def test_linha_invalida_do_conjunto_e_erro() -> None:
    with pytest.raises(ValueError, match="linha 1"):
        ler_conjunto('{"id": "x", "esperado": "talvez"}')


def test_guarda_verificar_aprova_o_conjunto_do_projeto(monkeypatch: pytest.MonkeyPatch) -> None:
    raiz = caminhos.encontrar_raiz(Path(__file__).resolve().parent)
    assert raiz is not None
    monkeypatch.chdir(raiz)
    assert cli.principal(["guarda", "verificar"]) == cli.CODIGO_OK


class _ClienteDuble(ClienteOllama):
    def modelos_instalados(self) -> dict[str, int]:
        return {self.modelo: 1_300_000_000}

    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        if self.modelo == "fora":
            raise FalhaDeGeracao("sem serviço")
        texto = "Então x = 4." if "metacognitivo" in sistema else "Pense na balança."
        return RespostaDoModelo(texto, 5, 900, self.modelo)


def test_benchmark_conta_vazamentos_e_falhas(item: Item) -> None:
    resultados = medir(_ClienteDuble, ["bom", "fora"], [item])
    bom, fora = resultados
    assert (len(bom.geracoes), bom.vazamentos, bom.falhas, bom.mediana_ms) == (3, 1, 0, 900)
    assert fora.geracoes == []
    texto = relatorio(resultados, "2026-10-30")
    assert "| `bom` | 1.30 GB | 3 | 0 | 1 |" in texto
    assert "guarda: numero" in texto
