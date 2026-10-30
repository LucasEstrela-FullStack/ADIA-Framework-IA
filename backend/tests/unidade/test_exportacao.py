"""Exportador_CSV: formato de docs/colunas-csv.md, ida e volta (R16.5) e minimização."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from adia.exportacao.csv_pesquisa import (
    COLUNAS_EVENTOS,
    COLUNAS_METRICAS,
    decimal_exportado,
    ler_metricas,
    medida_de,
)
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.orquestracao.exportar import exportar
from adia.orquestracao.servico import Servico
from adia.persistencia.repositorio import Repositorio
from adia.tipos import Indisponivel, Nivel

_ITENS = Path(__file__).resolve().parents[3] / "data" / "itens"


class _ClienteFora(ClienteOllama):
    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        raise FalhaDeGeracao("dublê")


@pytest.mark.parametrize(
    ("valor", "texto"),
    [
        (Decimal("0.75"), "0.750000"),
        (Decimal(1), "1.000000"),
        (Decimal(2) / Decimal(3), "0.6666666666666666666666666667"),  # sem arredondar a mais
        (Decimal("-0.2"), "-0.200000"),
    ],
)
def test_decimal_com_seis_casas_no_minimo(valor: Decimal, texto: str) -> None:
    assert decimal_exportado(valor) == texto


@pytest.fixture
def exportados(tmp_path: Path) -> Path:
    servico = Servico(_ITENS, _ClienteFora(), Repositorio(tmp_path / "adia.db"))
    sessao_id, sessao = servico.iniciar(servico.repositorio.criar_participantes("t", 1)[0])
    while not sessao.encerrada:
        if sessao.com_ia and not sessao.dicas_do_item:
            servico.dica(sessao_id, Nivel.L1, "meu nome é Joana e tentei somar")
        item = sessao.item_atual
        assert item is not None
        servico.responder(sessao_id, item.gabarito, 8)
    resultado = exportar(servico, tmp_path / "saida")
    assert (resultado.exportadas, resultado.recusadas) == (1, ())
    return resultado.diretorio


def _ler(pasta: Path, prefixo: str) -> tuple[list[str], list[dict[str, str]]]:
    arquivo = next(pasta.glob(f"{prefixo}_*.csv"))
    conteudo = arquivo.read_bytes()
    assert b"\r\n" not in conteudo
    leitor = csv.DictReader(conteudo.decode("utf-8").splitlines())
    return list(leitor.fieldnames or []), list(leitor)


def test_eventos_seguem_o_cabecalho_e_nao_exportam_texto_livre(exportados: Path) -> None:
    colunas, linhas = _ler(exportados, "eventos")
    assert tuple(colunas) == COLUNAS_EVENTOS
    assert len(linhas) == 31 + 12  # 31 respostas e uma dica por item praticado
    conteudo = (next(exportados.glob("eventos_*.csv"))).read_text(encoding="utf-8")
    assert "Joana" not in conteudo
    dicas = [linha for linha in linhas if linha["tipo"] == "dica"]
    assert {linha["explicacao_presente"] for linha in dicas} == {"1"}
    assert {linha["exportacao_id"] for linha in linhas} == {exportados.name}
    assert all(linha["segundos_desde_anterior"] for linha in linhas if linha["tipo"] == "resposta")


def test_metricas_ida_e_volta(exportados: Path) -> None:
    colunas, linhas = _ler(exportados, "metricas")
    assert tuple(colunas) == COLUNAS_METRICAS
    assert len(linhas) == 3 * 9 + 3  # nove por ciclo, mais tai, confiança e brier da linha de base
    reimportadas = ler_metricas(next(exportados.glob("metricas_*.csv")).read_text(encoding="utf-8"))
    por_nome = {(linha["ciclo"], linha["metrica"]): medida_de(linha) for linha in reimportadas}
    assert por_nome[("1", "tai")] == Decimal(1)
    assert por_nome[("1", "confianca_media")] == Decimal("0.8")
    assert por_nome[("1", "brier")] == Decimal("0.04")
    assert all(not isinstance(valor, Indisponivel) for valor in por_nome.values())


def test_indisponivel_volta_indisponivel() -> None:
    linha = {"valor": "", "indisponivel_motivo": "nenhum item praticado"}
    medida = medida_de(linha)
    assert isinstance(medida, Indisponivel)
    assert medida.motivo == "nenhum item praticado"
