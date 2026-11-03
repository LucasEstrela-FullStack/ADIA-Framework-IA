"""Raiz do projeto e caminhos relativos a ela.

Módulo à parte para que a API e a CLI achem a raiz sem que uma importe a outra: o servidor
não precisa carregar `argparse`, `socket` e o resto do `doutor`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

ARQUIVO_PYTHON: Final = ".python-version"

#: Marcas que identificam a raiz do projeto. As duas juntas, porque
#: `pyproject.toml` sozinho também aparece em subprojetos.
MARCAS_DA_RAIZ: Final = (ARQUIVO_PYTHON, "pyproject.toml")

#: Diretório do banco de itens, relativo à raiz do projeto (design §2.3, D12).
DIRETORIO_DE_ITENS: Final = Path("data") / "itens"
DIRETORIO_STEAM: Final = Path("data") / "steam"
DIRETORIO_CORPUS: Final = Path("data") / "corpus"
INDICE_RAG: Final = Path("data") / "indice_rag" / "indice.db"
"""Derivado do corpus por ``adia indexar``; fora do git por ``data/indice_rag/``."""
CHAVE_DO_PROFESSOR: Final = Path("data") / "privado" / "professor.chave"
"""Chave das rotas do professor, gerada por ``adia professor chave``; fora do git por ``data/privado/``."""

#: Conjunto declarado de verificação da guarda (docs/conjunto-verificacao-guarda.md).
CONJUNTO_DA_GUARDA: Final = Path("data") / "guarda" / "conjunto_verificacao.jsonl"


def encontrar_raiz(inicio: Path | None = None) -> Path | None:
    """Sobe a árvore de diretórios até achar as marcas da raiz do projeto.

    Tenta, na ordem, o diretório informado, o diretório de trabalho e o
    diretório deste módulo. O terceiro é o que resolve a instalação editável,
    em que o pacote continua em `backend/adia/`.
    """
    partidas = [caminho for caminho in (inicio, Path.cwd(), Path(__file__).resolve().parent) if caminho is not None]
    for partida in partidas:
        resolvida = partida.resolve()
        for diretorio in (resolvida, *resolvida.parents):
            if all((diretorio / marca).is_file() for marca in MARCAS_DA_RAIZ):
                return diretorio
    return None
