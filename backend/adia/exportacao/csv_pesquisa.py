"""Exportador_CSV: eventos e métricas de uma sessão, com proveniência embutida (R16).

Puro: recebe as linhas do registro e os resumos já recalculados, devolve o texto dos dois
arquivos. Regras de ``docs/colunas-csv.md``: UTF-8, ``\\n``, ponto decimal, ISO 8601 com
fuso, métrica com no mínimo seis casas e sem arredondamento, indisponível com valor vazio e
motivo preenchido, só pseudônimos, e as seis últimas colunas repetindo a proveniência.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from adia.nucleo.sessao.gestor import ResumoDoCiclo, ResumoSemIA
from adia.tipos import Indisponivel, Medida

CASAS_MINIMAS: Final = 6


@dataclass(frozen=True)
class ProvenienciaDaExportacao:
    exportacao_id: str
    exportado_em: str
    prototipo_versao: str
    commit_sha: str
    limiares_versao: str
    banco_itens_hash: str
    esquema_versao: str


@dataclass(frozen=True)
class Sessao:
    id: str
    participante_id: str
    condicao: str
    criada_em: str


COLUNAS_EVENTOS: Final = (
    "sessao_id",
    "participante_id",
    "condicao",
    "ciclo",
    "etapa",
    "sequencia",
    "tipo",
    "item_id",
    "teto",
    "nivel",
    "origem",
    "motivo",
    "texto_dica",
    "resposta",
    "acerto",
    "confianca",
    "explicacao_presente",
    "justificativa_presente",
    "segundos_desde_anterior",
    "criado_em",
    "exportacao_id",
    "exportado_em",
    "prototipo_versao",
    "commit_sha",
    "limiares_versao",
    "banco_itens_hash",
)

COLUNAS_METRICAS: Final = (
    "sessao_id",
    "participante_id",
    "condicao",
    "ciclo",
    "etapa",
    "metrica",
    "valor",
    "indisponivel_motivo",
    "decisao",
    "teto",
    "teto_indicado",
    "teto_aplicado",
    "decisao_aplicada",
    "exportacao_id",
    "exportado_em",
    "prototipo_versao",
    "commit_sha",
    "limiares_versao",
    "esquema_versao",
)


def decimal_exportado(valor: Decimal) -> str:
    """Notação fixa com no mínimo seis casas; casas a mais ficam, nunca são arredondadas."""
    texto = format(valor, "f")
    inteiro, _, fracao = texto.partition(".")
    return f"{inteiro}.{fracao.ljust(CASAS_MINIMAS, '0')}"


def _medida(valor: Medida) -> tuple[str, str]:
    if isinstance(valor, Indisponivel):
        return "", valor.motivo
    return decimal_exportado(valor), ""


def _escrever(colunas: Sequence[str], linhas: Sequence[Mapping[str, object]]) -> str:
    saida = io.StringIO()
    escritor = csv.DictWriter(saida, fieldnames=colunas, lineterminator="\n")
    escritor.writeheader()
    for linha in linhas:
        escritor.writerow({chave: "" if valor is None else valor for chave, valor in linha.items()})
    return saida.getvalue()


def _proveniencia(prov: ProvenienciaDaExportacao, ultima: str) -> dict[str, object]:
    return {
        "exportacao_id": prov.exportacao_id,
        "exportado_em": prov.exportado_em,
        "prototipo_versao": prov.prototipo_versao,
        "commit_sha": prov.commit_sha,
        "limiares_versao": prov.limiares_versao,
        ultima: getattr(prov, ultima),
    }


def eventos_csv(sessao: Sessao, eventos: Sequence[Mapping[str, object]], prov: ProvenienciaDaExportacao) -> str:
    """Uma linha por dica ou resposta registrada.

    Os textos livres do estudante (explicação antes da dica, justificativa da resposta) não
    saem: só a presença deles, por minimização (R25.6). ``segundos_desde_anterior`` é o tempo
    entre uma resposta e a anterior (ou o início da sessão); inclui pausas e recarregamentos.
    """
    anterior = datetime.fromisoformat(sessao.criada_em)
    linhas: list[dict[str, object]] = []
    for sequencia, evento in enumerate(eventos, start=1):
        criado = datetime.fromisoformat(str(evento["criado_em"]))
        segundos: str | None = None
        if evento["tipo"] == "resposta":
            segundos = decimal_exportado(Decimal(str((criado - anterior).total_seconds())))
            anterior = criado
        linhas.append(
            {
                "sessao_id": sessao.id,
                "participante_id": sessao.participante_id,
                "condicao": sessao.condicao,
                "ciclo": evento["ciclo"],
                "etapa": evento["etapa"],
                "sequencia": sequencia,
                "tipo": evento["tipo"],
                "item_id": evento["item_id"],
                "teto": evento["teto"],
                "nivel": evento["nivel"],
                "origem": evento["origem"],
                "motivo": evento["motivo"],
                "texto_dica": evento["texto_dica"],
                "resposta": evento["resposta"],
                "acerto": evento["acerto"],
                "confianca": evento["confianca"],
                "explicacao_presente": int(bool(evento["explicacao"])) if evento["tipo"] == "dica" else None,
                "justificativa_presente": int(bool(evento["justificativa"])) if evento["tipo"] == "resposta" else None,
                "segundos_desde_anterior": segundos,
                "criado_em": evento["criado_em"],
                **_proveniencia(prov, "banco_itens_hash"),
            }
        )
    return _escrever(COLUNAS_EVENTOS, linhas)


def metricas_csv(
    sessao: Sessao,
    ciclos: Sequence[ResumoDoCiclo],
    sem_ia: Sequence[ResumoSemIA],
    prov: ProvenienciaDaExportacao,
    desvio_horas: Decimal | None = None,
) -> str:
    """Formato longo: uma linha por métrica de cada ciclo, com a decisão do ciclo ao lado.

    A linha de base sai com ``ciclo = 0`` e a retenção com o ciclo do pós-teste e a etapa
    ``teste_retencao``, sem decisão. ``horas_alem_da_janela`` é a marca de DO-08: 0 dentro
    das 216 h, e as horas excedentes quando a retenção abriu fora de protocolo.
    """
    linhas: list[dict[str, object]] = []

    def sem_decisao(ciclo: int, etapa: str, nome: str, valor: Medida) -> None:
        texto, motivo = _medida(valor)
        linhas.append(
            {
                "sessao_id": sessao.id,
                "participante_id": sessao.participante_id,
                "condicao": sessao.condicao,
                "ciclo": ciclo,
                "etapa": etapa,
                "metrica": nome,
                "valor": texto,
                "indisponivel_motivo": motivo,
                **_proveniencia(prov, "esquema_versao"),
            }
        )

    for resumo_sem_ia in sem_ia:
        etapa = resumo_sem_ia.etapa.value
        sem_decisao(resumo_sem_ia.ciclo, etapa, "tai", resumo_sem_ia.acerto)
        sem_decisao(resumo_sem_ia.ciclo, etapa, "confianca_media", resumo_sem_ia.confianca)
        sem_decisao(resumo_sem_ia.ciclo, etapa, "brier", resumo_sem_ia.brier)
        if resumo_sem_ia.retencao is not None:
            sem_decisao(resumo_sem_ia.ciclo, etapa, "retencao", resumo_sem_ia.retencao)
            sem_decisao(resumo_sem_ia.ciclo, etapa, "horas_alem_da_janela", desvio_horas or Decimal(0))
    for resumo in ciclos:
        decisao = resumo.decisao
        metricas: tuple[tuple[str, str, Medida], ...] = (
            ("acerto_assistido", "pratica_assistida", resumo.acerto_assistido),
            ("dss", "pratica_assistida", resumo.dss),
            ("tai", "desafio_independente", resumo.acerto_independente),
            ("tt", "desafio_independente", resumo.transferencia),
            ("confianca_media", "desafio_independente", resumo.confianca),
            ("brier", "desafio_independente", resumo.brier),
            ("iic", "desafio_independente", resumo.iic),
            ("gap", "desafio_independente", decisao.gap),
            ("vies", "desafio_independente", decisao.vies),
        )
        for nome, etapa, valor in metricas:
            texto, motivo = _medida(valor)
            linhas.append(
                {
                    "sessao_id": sessao.id,
                    "participante_id": sessao.participante_id,
                    "condicao": sessao.condicao,
                    "ciclo": resumo.ciclo,
                    "etapa": etapa,
                    "metrica": nome,
                    "valor": texto,
                    "indisponivel_motivo": motivo,
                    "decisao": decisao.tipo.value,
                    "teto": int(resumo.teto),
                    "teto_indicado": int(decisao.teto_resultante),
                    "teto_aplicado": int(resumo.teto_seguinte),
                    "decisao_aplicada": int(sessao.condicao == "B"),
                    **_proveniencia(prov, "esquema_versao"),
                }
            )
    return _escrever(COLUNAS_METRICAS, linhas)


def ler_metricas(texto: str) -> list[dict[str, str]]:
    """Reimportação do arquivo de métricas (R16.5)."""
    return list(csv.DictReader(io.StringIO(texto)))


def medida_de(linha: Mapping[str, str]) -> Medida:
    """A ``Medida`` de uma linha reimportada: indisponível volta indisponível, nunca zero."""
    if linha["valor"] == "":
        return Indisponivel(linha["indisponivel_motivo"])
    return Decimal(linha["valor"])
