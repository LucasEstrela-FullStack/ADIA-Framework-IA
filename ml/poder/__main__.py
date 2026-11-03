"""``uv run python -m ml.poder``: tabela de poder por tamanho de amostra, a partir de dados sintéticos."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from adia.caminhos import DIRETORIO_DE_ITENS, DIRETORIO_STEAM
from adia.tipos import Condicao
from ml.poder.analise import ALFA, PODER_ALVO, analisar, minimo
from ml.simulador.coorte import DESFECHOS, carregar_conteudo


def principal() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analisador = argparse.ArgumentParser(prog="python -m ml.poder", description=__doc__)
    analisador.add_argument("--tamanhos", type=int, nargs="+", default=[20, 40, 60, 80, 100])
    analisador.add_argument("--replicas", type=int, default=200)
    analisador.add_argument("--semente", type=int, default=1)
    analisador.add_argument("--desfecho", choices=list(DESFECHOS), default="posteste")
    analisador.add_argument("--contraste", nargs=2, choices=[c.value for c in Condicao], default=["A", "B"])
    analisador.add_argument("--destino", type=Path, default=Path("exportacoes") / "sinteticos" / "poder.csv")
    args = analisador.parse_args()
    primeira, segunda = (Condicao(c) for c in args.contraste)
    linhas = analisar(
        carregar_conteudo(DIRETORIO_DE_ITENS, DIRETORIO_STEAM), args.tamanhos, args.replicas, args.semente,
        args.desfecho, (primeira, segunda),
    )
    print(f"Dados sintéticos. Desfecho {args.desfecho}, {segunda} - {primeira}, Welch, alfa {ALFA}, "
          f"{args.replicas} réplicas.")
    print("n/condição  poder  diferença  d")
    for linha in linhas:
        print(f"{linha.por_condicao:>10}  {linha.poder:.3f}  {linha.diferenca:+.3f}    {linha.efeito:+.2f}")
    alcance = minimo(linhas)
    if alcance:
        print(f"Poder {PODER_ALVO} com {alcance} por condição.")
    else:
        print(f"Nenhum tamanho alcança poder {PODER_ALVO}.")
    args.destino.parent.mkdir(parents=True, exist_ok=True)
    with args.destino.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(["sintetico", "desfecho", "primeira", "segunda", "replicas", "por_condicao", "poder",
                           "diferenca", "efeito"])
        for linha in linhas:
            escritor.writerow([1, args.desfecho, primeira, segunda, args.replicas, linha.por_condicao,
                               f"{linha.poder:.4f}", f"{linha.diferenca:.4f}", f"{linha.efeito:.4f}"])
    print(f"gravado {args.destino}")


if __name__ == "__main__":
    principal()
