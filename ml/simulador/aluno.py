"""Aluno simulado que percorre a ``Sessao`` real do núcleo (DO-49).

O modelo do aluno é deliberadamente simples e **todas as suas consequências são suposições**:

- Probabilidade de acerto logística, ``σ(θ − β·(dificuldade − 3) + apoio)``, com ``θ`` a
  proficiência latente do aluno.
- Na prática assistida, a dica de maior nível usada no item soma ``apoio`` ao logit do acerto
  e soma ``ganho`` a ``θ`` depois do item. Dica mais diretiva ajuda mais na hora e ensina
  menos: é a hipótese que o ADIA testa, não um resultado. Simulações nunca a confirmam.
- O perfil decide como o aluno pede dica: o dependente vai direto ao teto; os demais sobem
  nível a nível enquanto a chance estimada de acerto fica abaixo de 0,6.
- A confiança é ``σ(logit p + viés + ruído)`` em escala 0–10.
- A retenção desconta ``esquecimento`` de ``θ``.

Toda a sequência de etapas, tetos, onloading e justificativa vem do ``Gestor_de_Sessão``: o
simulador só escolhe dicas e informa o acerto, como o serviço faz com um aluno humano.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from adia.nucleo.itens.banco import BancoDeItens
from adia.nucleo.itens.modelo import Item
from adia.nucleo.sessao.gestor import Sessao
from adia.nucleo.steam.cenarios import Cenario
from adia.tipos import Condicao, Etapa, Nivel

DIFICULDADE_MEDIA = 3
LIMIAR_DE_PEDIDO = 0.6


@dataclass(frozen=True)
class Perfil:
    nome: str
    proficiencia: float
    """``θ`` inicial, em logit."""
    dependencia: float
    """Chance, por item, de ir direto à dica do teto."""
    vies_de_confianca: float
    """Somado ao logit da confiança: positivo é excesso de confiança."""


PERFIS: tuple[Perfil, ...] = (
    Perfil("autonomo", 0.5, 0.1, 0.0),
    Perfil("intermediario", 0.0, 0.4, 0.3),
    Perfil("dependente", -0.5, 0.8, 0.6),
)


@dataclass(frozen=True)
class Parametros:
    """Efeitos supostos. Mudá-los muda o efeito simulado; nenhum vem de dado empírico."""

    apoio: Mapping[Nivel, float] = field(
        default_factory=lambda: {Nivel.L1: 0.3, Nivel.L2: 0.6, Nivel.L3: 1.0, Nivel.L4: 2.0}
    )
    ganho: Mapping[Nivel, float] = field(
        default_factory=lambda: {Nivel.L1: 0.25, Nivel.L2: 0.2, Nivel.L3: 0.12, Nivel.L4: 0.04}
    )
    ganho_sem_dica: float = 0.2
    ganho_sem_ia: float = 0.03
    """Efeito de testagem: resolver sem ajuda também ensina um pouco."""
    discriminacao: float = 0.5
    esquecimento: float = 0.3
    ruido_de_confianca: float = 0.5
    desvio_da_proficiencia: float = 0.6
    """Desvio-padrão entre alunos do mesmo perfil."""


@dataclass(frozen=True)
class Passo:
    """Uma resposta da trajetória, na ordem em que a sessão a recebeu."""

    ordem: int
    etapa: str
    ciclo: int
    item_id: str
    habilidade: str
    dificuldade: int
    dicas: tuple[Nivel, ...]
    acerto: bool
    confianca: int


@dataclass(frozen=True)
class AlunoSimulado:
    aluno_id: str
    perfil: Perfil
    condicao: Condicao
    sessao: Sessao
    passos: tuple[Passo, ...]


def _sigmoide(x: float) -> float:
    return 1 / (1 + math.exp(-x))


@dataclass
class _Aluno:
    perfil: Perfil
    parametros: Parametros
    sorteio: random.Random
    theta: float

    def chance(self, dificuldade: int, apoio: float = 0.0) -> float:
        p = self.parametros
        return _sigmoide(self.theta - p.discriminacao * (dificuldade - DIFICULDADE_MEDIA) + apoio)

    def dicas(self, item: Item, teto: Nivel) -> list[Nivel]:
        if self.sorteio.random() < self.perfil.dependencia:
            return [teto]
        usadas: list[Nivel] = []
        for nivel in Nivel:
            if nivel > teto:
                break
            apoio = self.parametros.apoio[usadas[-1]] if usadas else 0.0
            if self.chance(item.dificuldade, apoio) >= LIMIAR_DE_PEDIDO:
                break
            usadas.append(nivel)
        return usadas

    def tentar(self, dificuldade: int, apoio: float = 0.0) -> tuple[bool, int]:
        p = self.chance(dificuldade, apoio)
        acerto = self.sorteio.random() < p
        logito = math.log(p / (1 - p)) + self.perfil.vies_de_confianca
        logito += self.sorteio.gauss(0, self.parametros.ruido_de_confianca)
        return acerto, round(10 * _sigmoide(logito))


def simular(
    aluno_id: str,
    perfil: Perfil,
    condicao: Condicao,
    banco: BancoDeItens,
    sorteio: random.Random,
    cenarios: Sequence[Cenario] = (),
    parametros: Parametros | None = None,
) -> AlunoSimulado:
    """Percorre a sessão inteira, do pré-teste à retenção, e devolve a trajetória."""
    p = parametros or Parametros()
    aluno = _Aluno(perfil, p, sorteio, sorteio.gauss(perfil.proficiencia, p.desvio_da_proficiencia))
    sessao = Sessao(banco, condicao, cenarios=tuple(cenarios))
    passos: list[Passo] = []

    def responder(item: Item, dicas: Sequence[Nivel], apoio: float) -> None:
        etapa, ciclo = str(sessao.etapa), sessao.ciclo
        acerto, confianca = aluno.tentar(item.dificuldade, apoio)
        sessao.responder(acerto, confianca, "resolvi passo a passo")
        passos.append(
            Passo(
                len(passos), etapa, ciclo, item.id, item.habilidade_alvo, item.dificuldade,
                tuple(dicas), acerto, confianca,
            )
        )

    while not sessao.encerrada:
        if sessao.etapa == Etapa.PROJETO_STEAM:
            assert sessao.cenario is not None
            sessao.submeter_steam(
                [sorteio.random() < aluno.chance(DIFICULDADE_MEDIA) for _ in sessao.cenario.partes]
            )
            continue
        item = sessao.item_atual
        assert item is not None
        if sessao.com_ia:
            dicas = aluno.dicas(item, sessao.teto)
            for nivel in dicas:
                sessao.registrar_dica(nivel, "tentei montar a conta")
            responder(item, dicas, p.apoio[max(dicas)] if dicas else 0.0)
            aluno.theta += p.ganho[max(dicas)] if dicas else p.ganho_sem_dica
        else:
            responder(item, (), 0.0)
            aluno.theta += p.ganho_sem_ia

    aluno.theta -= p.esquecimento
    sessao.iniciar_retencao()
    while (item := sessao.item_atual) is not None:
        responder(item, (), 0.0)
    return AlunoSimulado(aluno_id, perfil, condicao, sessao, tuple(passos))
