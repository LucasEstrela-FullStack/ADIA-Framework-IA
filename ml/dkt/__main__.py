"""``uv run --extra ml python -m ml.dkt``: treina o DKT em trajetórias sintéticas e mede a AUC."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from ml.dkt.dados import auc, dividir, ler
from ml.dkt.modelo import prever, salvar, treinar


def principal() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analisador = argparse.ArgumentParser(prog="python -m ml.dkt", description=__doc__)
    analisador.add_argument(
        "--trajetorias", type=Path, default=Path("exportacoes") / "sinteticos" / "trajetorias.csv"
    )
    analisador.add_argument("--epocas", type=int, default=30)
    analisador.add_argument("--oculto", type=int, default=64)
    analisador.add_argument("--semente", type=int, default=1)
    analisador.add_argument("--teste", type=float, default=0.2, help="fração de alunos no teste (padrão 0,2)")
    analisador.add_argument("--destino", type=Path, default=Path("ml") / "modelos" / "dkt.pt")
    args = analisador.parse_args()

    trajetorias = ler(args.trajetorias)
    treino, teste = dividir(len(trajetorias.alunos), args.teste, args.semente)
    modelo = treinar(trajetorias, treino, args.epocas, args.oculto, semente=args.semente)
    rotulos, escores = prever(modelo, trajetorias, teste)

    # Linha de base: taxa de acerto de cada item no treino, sem história do aluno.
    contagem: dict[int, list[int]] = {}
    for i in treino:
        for passo in trajetorias.sequencias[i][1:]:
            contagem.setdefault(passo.item, []).append(int(passo.acerto))
    media = {item: sum(v) / len(v) for item, v in contagem.items()}
    base = [media.get(p.item, 0.5) for i in teste for p in trajetorias.sequencias[i][1:]]

    versao = f"{hashlib.sha256(args.trajetorias.read_bytes()).hexdigest()[:12]}:s{args.semente}"
    print(f"Dados sintéticos: {len(trajetorias.alunos)} alunos, {len(trajetorias.itens)} itens, "
          f"{len(treino)} no treino, {len(teste)} no teste.")
    print(f"AUC no teste: DKT {auc(rotulos, escores):.3f}, linha de base por item {auc(rotulos, base):.3f}.")
    salvar(modelo, trajetorias, versao, args.destino)
    print(f"gravado {args.destino} (versão {versao})")


if __name__ == "__main__":
    principal()
