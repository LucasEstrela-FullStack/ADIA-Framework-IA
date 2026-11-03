"""Simulador_de_Alunos e análise de poder (DO-49)."""

from __future__ import annotations

import csv
import random
from pathlib import Path

import pytest
from ml.poder.analise import Linha, analisar, cohen, minimo, welch
from ml.simulador.aluno import Perfil, simular
from ml.simulador.coorte import DESFECHOS, Conteudo, carregar_conteudo, exportar, gerar

from adia.nucleo.itens.banco import BancoDeItens
from adia.tipos import Condicao, Nivel


@pytest.fixture(scope="module")
def conteudo() -> Conteudo:
    return carregar_conteudo(Path("data") / "itens", Path("data") / "steam")


@pytest.mark.parametrize("condicao", list(Condicao))
def test_percorre_a_sessao_inteira_ate_a_retencao(conteudo: Conteudo, condicao: Condicao) -> None:
    aluno = gerar(conteudo, 1, 5, (condicao,))[0]
    sessao = aluno.sessao
    assert sessao.encerrada and sessao.retencao_concluida
    assert len(sessao.ciclos) == 3
    assert [(p.item_id, p.acerto, p.confianca) for p in aluno.passos] == [
        (r.item_id, r.acerto, r.confianca) for r in sessao.respostas
    ]
    assert all(0 <= p.confianca <= 10 for p in aluno.passos)


def test_mesma_semente_mesma_coorte(conteudo: Conteudo) -> None:
    def assinatura(semente: int) -> list[tuple[object, ...]]:
        return [(a.perfil.nome, a.passos) for a in gerar(conteudo, 2, semente)]

    assert assinatura(9) == assinatura(9)
    assert assinatura(9) != assinatura(10)


def test_dependente_vai_direto_ao_teto(conteudo: Conteudo) -> None:
    perfil = Perfil("so_teto", 0.0, 1.0, 0.0)
    banco = BancoDeItens(conteudo.carga, 3)
    aluno = simular("S-1", perfil, Condicao.C, banco, random.Random(1), conteudo.cenarios)
    assistidos = [p for p in aluno.passos if p.etapa == "pratica_assistida"]
    assert assistidos and all(len(p.dicas) == 1 for p in assistidos)
    assert {p.dicas[0] for p in assistidos} < set(Nivel)  # C desce o teto: nem tudo é L4


def test_exportacao_marca_toda_linha_como_sintetica(conteudo: Conteudo, tmp_path: Path) -> None:
    alunos = gerar(conteudo, 2, 4)
    caminho_alunos, caminho_passos = exportar(alunos, tmp_path, 4)
    linhas_alunos = list(csv.DictReader(caminho_alunos.open(encoding="utf-8")))
    linhas_passos = list(csv.DictReader(caminho_passos.open(encoding="utf-8")))
    assert len(linhas_alunos) == 2 * len(Condicao)
    assert len(linhas_passos) == sum(len(a.passos) for a in alunos)
    assert {r["sintetico"] for r in linhas_alunos + linhas_passos} == {"1"}
    assert all(r[d] for r in linhas_alunos for d in DESFECHOS)


def test_welch_e_cohen() -> None:
    assert welch([0.0, 0.1, 0.2, 0.1], [0.9, 1.0, 0.8, 0.9]) < 0.05
    assert welch([0.5, 0.5], [0.5, 0.5]) == 1.0
    assert welch([0.5], [0.1, 0.2]) == 1.0
    assert cohen([0.0, 1.0], [1.0, 2.0]) == pytest.approx(1 / (0.5**0.5))
    assert cohen([1.0, 1.0], [1.0, 1.0]) == 0.0


def test_analise_de_poder(conteudo: Conteudo) -> None:
    linhas = analisar(conteudo, [4, 6], 3, 1)
    assert [linha.por_condicao for linha in linhas] == [4, 6]
    assert all(0 <= linha.poder <= 1 for linha in linhas)
    assert minimo([Linha(10, 0.5, 0, 0), Linha(20, 0.85, 0, 0)]) == 20
    assert minimo([Linha(10, 0.5, 0, 0)]) is None
