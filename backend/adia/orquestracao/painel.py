"""Painel do pesquisador: relatório HTML autocontido, gerado pela CLI e lido fora da API.

Fica fora da API de propósito: a API não tem autenticação (D11) e o estudante usa a mesma
máquina, então uma rota de painel mostraria condição e desempenho a quem não pode vê-los.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from html import escape
from typing import Final

from adia.nucleo.metricas.formatacao import aviso_do_iic, para_tela
from adia.nucleo.sessao.gestor import FIM, ResumoDoCiclo, Sessao
from adia.orquestracao.servico import Servico, SessaoInconsistente
from adia.tipos import Etapa

AVISO_R25_8: Final = (
    "As métricas descrevem desempenho em tarefas deste estudo e não constituem diagnóstico "
    "psicológico, avaliação clínica nem medida de inteligência (R25.8). O IIC deve ser lido "
    "sempre ao lado da TAI."
)

_ESTILO: Final = """
:root { --fundo:#f6f5f1; --sup:#fff; --txt:#1d1d1b; --sutil:#5f5e58; --borda:#dcd9d0; --aviso:#8a5a00; }
@media (prefers-color-scheme: dark) {
  :root { --fundo:#171816; --sup:#21231f; --txt:#ecebe6; --sutil:#a5a49c; --borda:#3a3c36; --aviso:#e7b450; }
}
body { margin:0; background:var(--fundo); color:var(--txt); font:15px/1.5 system-ui, "Segoe UI", sans-serif; }
main { max-width:1100px; margin:0 auto; padding:24px 16px 48px; }
section { background:var(--sup); border:1px solid var(--borda); border-radius:10px; padding:16px; margin:16px 0; }
.sutil { color:var(--sutil); }
.aviso { color:var(--aviso); }
.tabela { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:.9rem; font-variant-numeric:tabular-nums; }
th, td { text-align:left; padding:4px 8px; border-bottom:1px solid var(--borda); white-space:nowrap; }
h1 { margin:0 0 4px; }
h2 { margin:0 0 8px; font-size:1.05rem; }
"""

_COLUNAS: Final = (
    "Ciclo",
    "Teto",
    "Com IA",
    "DSS",
    "TAI",
    "TT",
    "Confiança",
    "Brier",
    "IIC",
    "Gap",
    "Viés",
    "Decisão",
    "Teto seguinte",
)


def _situacao(sessao: Sessao) -> str:
    if sessao.etapa == FIM:
        return "retenção concluída" if sessao.retencao_concluida else "ciclos concluídos, retenção pendente"
    if sessao.etapa == Etapa.LINHA_DE_BASE:
        return "linha de base"
    if sessao.etapa == Etapa.TESTE_RETENCAO:
        return "na retenção"
    return f"ciclo {sessao.ciclo}, {str(sessao.etapa).replace('_', ' ')}"


def _linha_do_ciclo(ciclo: ResumoDoCiclo, aplicada: bool, aviso: bool) -> str:
    celulas = [
        str(ciclo.ciclo),
        ciclo.teto.name,
        para_tela(ciclo.acerto_assistido),
        para_tela(ciclo.dss),
        para_tela(ciclo.acerto_independente),
        para_tela(ciclo.transferencia),
        para_tela(ciclo.confianca),
        para_tela(ciclo.brier),
        para_tela(ciclo.iic) + (" (ver aviso)" if aviso else ""),
        para_tela(ciclo.decisao.gap),
        para_tela(ciclo.decisao.vies),
        ciclo.decisao.tipo.value + ("" if aplicada else " (sombra)"),
        ciclo.teto_seguinte.name,
    ]
    return "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in celulas) + "</tr>"


def _bloco(sessao_id: str, criada_em: str, participante: str, condicao: str, limiares: str, sessao: Sessao) -> str:
    partes = [
        f"<section><h2>{escape(participante)} · condição {escape(condicao)}</h2>",
        f"<p class='sutil'>Sessão {escape(sessao_id)} · criada em {escape(criada_em[:16].replace('T', ' '))} UTC"
        f" · limiares {escape(limiares)} · {escape(_situacao(sessao))}</p>",
    ]
    for resumo in sessao.resumos_sem_ia():
        nome = "Linha de base" if resumo.etapa == Etapa.LINHA_DE_BASE else "Retenção"
        extra = "" if resumo.retencao is None else f" · retenção {para_tela(resumo.retencao)}"
        partes.append(
            f"<p>{nome}: TAI {para_tela(resumo.acerto)}, confiança {para_tela(resumo.confianca)}, "
            f"Brier {para_tela(resumo.brier)}{escape(extra)}</p>"
        )
    avisos: list[str] = []
    linhas: list[str] = []
    for ciclo in sessao.ciclos:
        aviso = aviso_do_iic(ciclo.iic, ciclo.acerto_independente)
        if aviso:
            avisos.append(f"Ciclo {ciclo.ciclo}: {aviso}")
        linhas.append(_linha_do_ciclo(ciclo, condicao == "B", aviso is not None))
    if linhas:
        cabecalho = "".join(f"<th>{escape(c)}</th>" for c in _COLUNAS)
        partes.append(
            f"<div class='tabela'><table><thead><tr>{cabecalho}</tr></thead>"
            f"<tbody>{''.join(linhas)}</tbody></table></div>"
        )
    else:
        partes.append("<p class='sutil'>Nenhum ciclo concluído ainda.</p>")
    partes.extend(f"<p class='aviso'>{escape(a)}</p>" for a in avisos)
    partes.append("</section>")
    return "".join(partes)


def gerar_painel(servico: Servico) -> str:
    repositorio = servico.repositorio
    blocos: list[str] = []
    por_condicao: Counter[str] = Counter()
    recusadas: list[str] = []
    for sessao_id, criada_em in repositorio.sessoes():
        lido = repositorio.ler_sessao(sessao_id)
        if lido is None:
            continue
        registro = lido[0]
        try:
            sessao = servico.obter(sessao_id)
        except SessaoInconsistente:
            recusadas.append(sessao_id)
            continue
        condicao = registro.condicao.value
        por_condicao[condicao] += 1
        blocos.append(
            _bloco(
                sessao_id,
                criada_em,
                registro.participante_id,
                condicao,
                registro.proveniencia.limiares_versao,
                sessao,
            )
        )
    limiares = repositorio.limiares()
    contagem = ", ".join(f"{c}: {por_condicao.get(c, 0)}" for c in ("A", "B", "C"))
    gerado = datetime.now(UTC).astimezone().strftime("%d/%m/%Y %H:%M")
    recusa = (
        f"<p class='aviso'>Sessões que não se reproduzem com o código atual: {escape(', '.join(recusadas))}</p>"
        if recusadas
        else ""
    )
    corpo = "".join(blocos) or "<section><p>Nenhuma sessão ainda.</p></section>"
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>Painel do pesquisador</title><style>{_ESTILO}</style></head><body><main>"
        f"<h1>Painel do pesquisador</h1><p class='sutil'>Gerado em {gerado}. Sessões por condição: {contagem}."
        f" Limiares vigentes: {escape(limiares.versao)} (fading com TAI a partir de"
        f" {para_tela(limiares.independente_fading)}, escalonar com TAI abaixo de"
        f" {para_tela(limiares.independente_escalonar)}).</p>"
        f"<p class='aviso'>{escape(AVISO_R25_8)}</p>{recusa}{corpo}</main></body></html>\n"
    )
