"""Modelo_DKT e a leitura das trajetórias sintéticas (DO-50)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ml.dkt.dados import Passo, auc, dividir, ler
from ml.simulador.coorte import Conteudo, carregar_conteudo, exportar, gerar


@pytest.fixture(scope="module")
def trajetorias_csv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    conteudo: Conteudo = carregar_conteudo(Path("data") / "itens", Path("data") / "steam")
    destino = tmp_path_factory.mktemp("sinteticos")
    return exportar(gerar(conteudo, 4, 2), destino, 2)[1]


def test_le_uma_sequencia_por_aluno_na_ordem(trajetorias_csv: Path) -> None:
    trajetorias = ler(trajetorias_csv)
    assert len(trajetorias.alunos) == len(trajetorias.sequencias) == 12
    assert all(0 <= p.item < len(trajetorias.itens) for s in trajetorias.sequencias for p in s)
    assert any(p.assistido for s in trajetorias.sequencias for p in s)
    assert Passo(3, True, False).entrada() == 14


def test_recusa_linha_nao_sintetica(trajetorias_csv: Path, tmp_path: Path) -> None:
    linhas = trajetorias_csv.read_text(encoding="utf-8").splitlines()
    linhas[1] = "0" + linhas[1][1:]
    humano = tmp_path / "trajetorias.csv"
    humano.write_bytes(("\n".join(linhas) + "\n").encode())
    with pytest.raises(ValueError, match="não sintética"):
        ler(humano)


def test_divide_por_aluno_sem_sobreposicao() -> None:
    treino, teste = dividir(10, 0.2, 1)
    assert len(teste) == 2 and set(treino).isdisjoint(teste) and sorted(treino + teste) == list(range(10))
    assert dividir(10, 0.2, 1) == (treino, teste)


def test_auc() -> None:
    assert auc([False, False, True, True], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc([True, False], [0.5, 0.5]) == 0.5
    assert auc([False, True, False, True], [0.1, 0.4, 0.5, 0.8]) == 0.75
    with pytest.raises(ValueError):
        auc([True, True], [0.1, 0.2])


def test_treina_preve_e_recarrega(trajetorias_csv: Path, tmp_path: Path) -> None:
    pytest.importorskip("torch")
    from ml.dkt.modelo import carregar, prever, salvar, treinar

    trajetorias = ler(trajetorias_csv)
    treino, teste = dividir(len(trajetorias.alunos), 0.25, 1)
    modelo = treinar(trajetorias, treino, epocas=2, oculto=8)
    rotulos, escores = prever(modelo, trajetorias, teste)
    assert len(rotulos) == len(escores) == sum(len(trajetorias.sequencias[i]) - 1 for i in teste)
    assert all(0 < e < 1 for e in escores)
    salvar(modelo, trajetorias, "v", tmp_path / "dkt.pt")
    recarregado, itens, versao = carregar(tmp_path / "dkt.pt")
    assert (itens, versao) == (list(trajetorias.itens), "v")
    assert prever(recarregado, trajetorias, teste) == (rotulos, escores)
