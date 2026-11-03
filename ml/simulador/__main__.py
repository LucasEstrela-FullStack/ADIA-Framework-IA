"""``uv run python -m ml.simulador``: gera uma coorte sintética em ``exportacoes/sinteticos/``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from adia.caminhos import DIRETORIO_DE_ITENS, DIRETORIO_STEAM
from ml.simulador.coorte import carregar_conteudo, exportar, gerar


def principal() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analisador = argparse.ArgumentParser(prog="python -m ml.simulador", description=__doc__)
    analisador.add_argument("--alunos", type=int, default=30, help="alunos por condição (padrão 30)")
    analisador.add_argument("--semente", type=int, default=1)
    analisador.add_argument("--destino", type=Path, default=Path("exportacoes") / "sinteticos")
    args = analisador.parse_args()
    alunos = gerar(carregar_conteudo(DIRETORIO_DE_ITENS, DIRETORIO_STEAM), args.alunos, args.semente)
    for caminho in exportar(alunos, args.destino, args.semente):
        print(f"gravado {caminho}")


if __name__ == "__main__":
    principal()
