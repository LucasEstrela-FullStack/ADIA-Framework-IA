"""Poder por Monte Carlo: quantos alunos por condição detectam a diferença que o simulador supõe.

Para cada tamanho ``n``, gera ``replicas`` experimentos independentes com ``n`` alunos em cada
uma das duas condições do contraste e aplica o teste t de Welch bilateral ao desfecho por
aluno. O poder é a fração de experimentos com ``p < alfa``. O resultado vale para os efeitos
de ``Parametros``, que são suposições (DO-49): é planejamento, não evidência.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from scipy import stats

from adia.tipos import Condicao
from ml.simulador.aluno import Parametros
from ml.simulador.coorte import DESFECHOS, Conteudo, gerar

ALFA = 0.05
PODER_ALVO = 0.8


@dataclass(frozen=True)
class Linha:
    por_condicao: int
    poder: float
    diferenca: float
    """Média, entre réplicas, de média(segunda) − média(primeira)."""
    efeito: float
    """Média, entre réplicas, do d de Cohen com desvio combinado."""


def welch(primeira: Sequence[float], segunda: Sequence[float]) -> float:
    """Valor p bilateral do teste de Welch; 1 quando não há variação para testar."""
    if len(primeira) < 2 or len(segunda) < 2 or len(set(primeira)) + len(set(segunda)) == 2:
        return 1.0
    p = float(stats.ttest_ind(segunda, primeira, equal_var=False).pvalue)
    return 1.0 if math.isnan(p) else p


def cohen(primeira: Sequence[float], segunda: Sequence[float]) -> float:
    combinado = math.sqrt((statistics.variance(primeira) + statistics.variance(segunda)) / 2)
    diferenca = statistics.fmean(segunda) - statistics.fmean(primeira)
    return 0.0 if combinado == 0 else diferenca / combinado


def analisar(
    conteudo: Conteudo,
    tamanhos: Sequence[int],
    replicas: int,
    semente: int,
    desfecho: str = "posteste",
    contraste: tuple[Condicao, Condicao] = (Condicao.A, Condicao.B),
    alfa: float = ALFA,
    parametros: Parametros | None = None,
) -> list[Linha]:
    medir = DESFECHOS[desfecho]
    linhas: list[Linha] = []
    for n in tamanhos:
        significativos, diferencas, efeitos = 0, [], []
        for r in range(replicas):
            alunos = gerar(conteudo, n, semente * 1_000_003 + n * 1_009 + r, contraste, parametros)
            grupos = [
                [v for a in alunos if a.condicao == c and (v := medir(a)) is not None] for c in contraste
            ]
            significativos += welch(*grupos) < alfa
            diferencas.append(statistics.fmean(grupos[1]) - statistics.fmean(grupos[0]))
            efeitos.append(cohen(*grupos))
        linhas.append(Linha(n, significativos / replicas, statistics.fmean(diferencas), statistics.fmean(efeitos)))
    return linhas


def minimo(linhas: Sequence[Linha], alvo: float = PODER_ALVO) -> int | None:
    """Menor ``n`` por condição que alcança o poder alvo, ou ``None`` se nenhum alcança."""
    return next((linha.por_condicao for linha in linhas if linha.poder >= alvo), None)
