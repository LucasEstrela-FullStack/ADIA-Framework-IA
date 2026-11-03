"""Amostra de dicas geradas para revisão humana serve/não serve (DO-51).

Passa pelo caminho real da dica (papel do nível, trecho do RAG, guarda e filtro de
qualidade) e guarda também o texto cru do modelo, para que o pesquisador julgue inclusive o
que o filtro descartou. Gerações repetidas do mesmo item e nível saem uma vez só.
"""

from __future__ import annotations

import csv
from pathlib import Path

from adia.ia.cliente_ollama import ClienteOllama, RespostaDoModelo
from adia.orquestracao.servico import Servico
from adia.tipos import Nivel

COLUNAS = (
    "n",
    "item",
    "nivel",
    "enunciado",
    "dica_de_referencia",
    "gerada_pelo_modelo",
    "filtro",
    "serve (s/n)",
    "comentario",
)


class Gravador(ClienteOllama):
    """Cliente que guarda o último texto cru devolvido pelo modelo."""

    cru: str | None = None

    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        resposta = super().gerar(sistema, pedido)
        self.cru = resposta.texto
        return resposta


def amostrar(servico: Servico, gravador: Gravador, por_nivel: int = 2) -> list[dict[str, str]]:
    """Linhas da planilha: ``por_nivel`` gerações de L1 a L3 em cada item praticado."""
    linhas: list[dict[str, str]] = []
    vistas: set[tuple[str, Nivel, str]] = set()
    for item in (i for i in servico.carga.itens if i.e_praticado):
        for nivel in (Nivel.L1, Nivel.L2, Nivel.L3):
            for _ in range(por_nivel):
                gravador.cru = None
                dica = servico._gerar(item, nivel, "")
                cru = " ".join((gravador.cru or "").split())
                if (item.id, nivel, cru) in vistas:
                    continue
                vistas.add((item.id, nivel, cru))
                linhas.append(
                    {
                        "n": str(len(linhas) + 1),
                        "item": item.id,
                        "nivel": nivel.name,
                        "enunciado": item.enunciado,
                        "dica_de_referencia": item.dicas[nivel],
                        "gerada_pelo_modelo": cru,
                        "filtro": "passou" if dica.origem == "ia" else (dica.motivo or ""),
                        "serve (s/n)": "",
                        "comentario": "",
                    }
                )
    return linhas


def gravar(linhas: list[dict[str, str]], destino: Path) -> None:
    """CSV com ``;`` e BOM, para abrir direto no Excel em pt-BR."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
