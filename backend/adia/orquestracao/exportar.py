"""Exportação de todas as sessões: lê o registro, recalcula pelo replay e grava os CSV.

As métricas saem do replay, e não de uma cópia gravada, porque o replay já é conferido
contra as decisões gravadas (DO-38): uma sessão que não se reproduz não é exportada.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

from adia.exportacao.csv_pesquisa import ProvenienciaDaExportacao, Sessao, eventos_csv, metricas_csv
from adia.orquestracao.servico import Servico, SessaoInconsistente


@dataclass(frozen=True)
class ResultadoDaExportacao:
    diretorio: Path
    exportadas: int
    recusadas: tuple[str, ...]


def exportar(servico: Servico, destino: Path) -> ResultadoDaExportacao:
    """Grava ``eventos_{id}.csv`` e ``metricas_{id}.csv`` de cada sessão em ``destino/<exportacao_id>/``."""
    repositorio = servico.repositorio
    exportacao_id = uuid.uuid4().hex[:12]
    pasta = destino / exportacao_id
    pasta.mkdir(parents=True, exist_ok=False)
    exportadas = 0
    recusadas: list[str] = []
    for sessao_id, criada_em in repositorio.sessoes():
        lido = repositorio.ler_sessao(sessao_id)
        if lido is None:
            continue
        registro = lido[0]
        try:
            reconstruida = servico.obter(sessao_id)
        except SessaoInconsistente:
            recusadas.append(sessao_id)
            continue
        gravada = registro.proveniencia
        prov = ProvenienciaDaExportacao(
            exportacao_id=exportacao_id,
            exportado_em=datetime.now(UTC).isoformat(timespec="seconds"),
            prototipo_versao=version("adia"),
            commit_sha=gravada.commit_codigo or "",
            limiares_versao=gravada.limiares_versao,
            banco_itens_hash=gravada.hash_banco_itens,
            esquema_versao=str(repositorio.versao_do_esquema()),
        )
        sessao = Sessao(sessao_id, registro.participante_id, registro.condicao.value, criada_em)
        (pasta / f"eventos_{sessao_id}.csv").write_text(
            eventos_csv(sessao, repositorio.eventos_para_exportar(sessao_id), prov), encoding="utf-8", newline=""
        )
        (pasta / f"metricas_{sessao_id}.csv").write_text(
            metricas_csv(
                sessao,
                reconstruida.ciclos,
                reconstruida.resumos_sem_ia(),
                prov,
                None if registro.retencao_desvio_horas is None else Decimal(registro.retencao_desvio_horas),
                servico.medidas_steam(sessao_id, reconstruida),
            ),
            encoding="utf-8",
            newline="",
        )
        exportadas += 1
    return ResultadoDaExportacao(pasta, exportadas, tuple(recusadas))
