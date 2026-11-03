"""Trajetórias do simulador como sequências para o DKT. Sem ``torch``: testável no portão padrão.

A unidade de conhecimento é o item, não a habilidade: o banco atual cobre uma habilidade só, e
DKT com uma unidade se reduz a uma média móvel (DO-50). Cada passo vira o índice de entrada
``item·4 + acerto·2 + assistido``; a assistência entra porque acerto com dica não é a mesma
evidência que acerto sozinho.
"""

from __future__ import annotations

import csv
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Passo:
    item: int
    acerto: bool
    assistido: bool

    def entrada(self) -> int:
        return self.item * 4 + int(self.acerto) * 2 + int(self.assistido)


@dataclass(frozen=True)
class Trajetorias:
    itens: tuple[str, ...]
    """Vocabulário: a posição é o índice do item no modelo."""
    alunos: tuple[str, ...]
    sequencias: tuple[tuple[Passo, ...], ...]


def ler(caminho: Path) -> Trajetorias:
    """Lê ``trajetorias.csv``; recusa arquivo com linha não sintética (R25)."""
    por_aluno: dict[str, list[tuple[int, str, bool, bool]]] = {}
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha["sintetico"] != "1":
                raise ValueError(f"{caminho}: linha não sintética do aluno {linha['aluno_id']!r}")
            por_aluno.setdefault(linha["aluno_id"], []).append(
                (int(linha["ordem"]), linha["item_id"], linha["acerto"] == "1", bool(linha["dicas"]))
            )
    itens = tuple(sorted({item for passos in por_aluno.values() for _, item, _, _ in passos}))
    indice = {item: i for i, item in enumerate(itens)}
    alunos = tuple(sorted(por_aluno))
    sequencias = tuple(
        tuple(Passo(indice[item], acerto, assistido) for _, item, acerto, assistido in sorted(por_aluno[a]))
        for a in alunos
    )
    return Trajetorias(itens, alunos, sequencias)


def dividir(total: int, fracao_de_teste: float, semente: int) -> tuple[list[int], list[int]]:
    """Separa por aluno, nunca por passo: o teste só tem alunos que o treino não viu."""
    ordem = list(range(total))
    random.Random(semente).shuffle(ordem)
    corte = max(1, round(total * fracao_de_teste))
    return sorted(ordem[corte:]), sorted(ordem[:corte])


def auc(rotulos: Sequence[bool], escores: Sequence[float]) -> float:
    """Área sob a curva ROC por postos (Mann-Whitney), com empates no posto médio."""
    positivos = sum(rotulos)
    negativos = len(rotulos) - positivos
    if positivos == 0 or negativos == 0:
        raise ValueError("AUC exige rótulos das duas classes")
    pares = sorted(zip(escores, rotulos, strict=True))
    soma_dos_postos, i = 0.0, 0
    while i < len(pares):
        j = i
        while j < len(pares) and pares[j][0] == pares[i][0]:
            j += 1
        posto_medio = (i + j + 1) / 2
        soma_dos_postos += posto_medio * sum(r for _, r in pares[i:j])
        i = j
    return (soma_dos_postos - positivos * (positivos + 1) / 2) / (positivos * negativos)
