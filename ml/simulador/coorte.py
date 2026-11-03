"""Coorte sintética sobre o banco de itens e os cenários STEAM reais, e sua exportação."""

from __future__ import annotations

import csv
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from adia.nucleo.itens.banco import BancoDeItens
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.nucleo.steam.cenarios import Cenario, arquivos_de_steam
from adia.nucleo.steam.cenarios import carregar as carregar_steam
from adia.tipos import Condicao, Etapa, Medida
from ml.simulador.aluno import PERFIS, AlunoSimulado, Parametros, simular


@dataclass(frozen=True)
class Conteudo:
    carga: CargaConcluida
    cenarios: tuple[Cenario, ...]


def carregar_conteudo(diretorio_de_itens: Path, diretorio_steam: Path) -> Conteudo:
    carga = carregar(arquivos_de_itens(diretorio_de_itens))
    if not isinstance(carga, CargaConcluida):
        raise RuntimeError(f"Banco de itens inválido: {carga}")
    return Conteudo(carga, carregar_steam(arquivos_de_steam(diretorio_steam)).cenarios)


def gerar(
    conteudo: Conteudo,
    por_condicao: int,
    semente: int,
    condicoes: Sequence[Condicao] = tuple(Condicao),
    parametros: Parametros | None = None,
) -> list[AlunoSimulado]:
    """``por_condicao`` alunos em cada condição, perfil sorteado; mesma semente, mesma coorte."""
    sorteio = random.Random(semente)
    alunos: list[AlunoSimulado] = []
    for condicao in condicoes:
        for i in range(por_condicao):
            banco = BancoDeItens(conteudo.carga, sorteio.getrandbits(31))
            alunos.append(
                simular(
                    f"S-{condicao}-{i + 1:04d}", sorteio.choice(PERFIS), condicao, banco, sorteio,
                    conteudo.cenarios, parametros,
                )
            )
    return alunos


def _numero(medida: Medida) -> float | None:
    return float(medida) if isinstance(medida, Decimal) else None


def _posteste(aluno: AlunoSimulado) -> float | None:
    return _numero(aluno.sessao.ciclos[-1].acerto_independente)


def _retencao(aluno: AlunoSimulado) -> float | None:
    resumos = [r for r in aluno.sessao.resumos_sem_ia() if r.etapa == Etapa.TESTE_RETENCAO]
    return _numero(resumos[0].acerto) if resumos else None


def _ganho(aluno: AlunoSimulado) -> float | None:
    base = _numero(aluno.sessao.resumos_sem_ia()[0].acerto)
    pos = _posteste(aluno)
    return None if base is None or pos is None else pos - base


DESFECHOS: dict[str, Callable[[AlunoSimulado], float | None]] = {
    "posteste": _posteste,
    "retencao": _retencao,
    "ganho": _ganho,
}
"""Desfechos por aluno que a análise de poder sabe comparar entre condições."""


def _texto(valor: float | None) -> str:
    return "" if valor is None else f"{valor:.4f}"


def exportar(alunos: Sequence[AlunoSimulado], destino: Path, semente: int) -> tuple[Path, Path]:
    """Grava ``alunos.csv`` e ``trajetorias.csv``; toda linha leva ``sintetico=1`` (R25)."""
    destino.mkdir(parents=True, exist_ok=True)
    caminho_alunos, caminho_passos = destino / "alunos.csv", destino / "trajetorias.csv"
    with caminho_alunos.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(
            ["sintetico", "semente", "aluno_id", "perfil", "condicao", *DESFECHOS, "iic_final", "dss_final"]
        )
        for aluno in alunos:
            final = aluno.sessao.ciclos[-1]
            escritor.writerow(
                [1, semente, aluno.aluno_id, aluno.perfil.nome, aluno.condicao]
                + [_texto(f(aluno)) for f in DESFECHOS.values()]
                + [_texto(_numero(final.iic)), _texto(_numero(final.dss))]
            )
    with caminho_passos.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(
            ["sintetico", "aluno_id", "condicao", "ordem", "etapa", "ciclo", "item_id", "habilidade",
             "dificuldade", "dicas", "acerto", "confianca"]
        )
        for aluno in alunos:
            for passo in aluno.passos:
                escritor.writerow(
                    [1, aluno.aluno_id, aluno.condicao, passo.ordem, passo.etapa, passo.ciclo, passo.item_id,
                     passo.habilidade, passo.dificuldade, "|".join(f"L{int(n)}" for n in passo.dicas),
                     int(passo.acerto), passo.confianca]
                )
    return caminho_alunos, caminho_passos
