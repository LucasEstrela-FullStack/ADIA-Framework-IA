"""`adia participantes criar` e `adia excluir-dados` sobre um projeto temporário."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from adia import caminhos, cli


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for marca in caminhos.MARCAS_DA_RAIZ:
        (tmp_path / marca).write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_cria_participantes_e_exclui_com_registro(projeto: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.principal(["participantes", "criar", "--coorte", "turma-a", "--quantidade", "2"]) == cli.CODIGO_OK
    assert "P-0001" in capsys.readouterr().out

    assert cli.principal(["excluir-dados", "--participante", "P-0001"]) == cli.CODIGO_OK
    assert cli.principal(["excluir-dados", "--participante", "P-0001"]) == cli.CODIGO_BANCO_INVALIDO

    with sqlite3.connect(projeto / "data" / "adia.db") as conexao:
        assert conexao.execute("SELECT id FROM participante").fetchall() == [("P-0002",)]
        assert conexao.execute("SELECT participante_id, motivo FROM exclusao").fetchall() == [("P-0001", "pedido")]


def test_excluir_dados_exige_um_alvo(projeto: Path) -> None:
    with pytest.raises(SystemExit) as capturado:
        cli.principal(["excluir-dados"])
    assert capturado.value.code != cli.CODIGO_OK
