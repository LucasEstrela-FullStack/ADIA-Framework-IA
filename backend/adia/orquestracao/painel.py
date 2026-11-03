"""Painel do pesquisador: relatório HTML autocontido, gerado pela CLI e lido fora da API.

Fica fora da API de propósito: a API não tem autenticação (D11) e o estudante usa a mesma
máquina, então uma rota de painel mostraria condição e desempenho a quem não pode vê-los.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from html import escape
from typing import Final

from adia.nucleo.metricas.atalhos import PADROES, Contagem, EventoDoLog, contar
from adia.nucleo.metricas.formatacao import aviso_do_iic, para_tela
from adia.nucleo.sessao.gestor import FIM, ResumoDoCiclo, Sessao
from adia.orquestracao.servico import Servico, SessaoInconsistente
from adia.tipos import Etapa, Medida

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
td.calor { text-align:center; }
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
    if sessao.etapa == Etapa.PROJETO_STEAM:
        return "no projeto STEAM"
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


def _bloco(
    sessao_id: str,
    criada_em: str,
    participante: str,
    condicao: str,
    limiares: str,
    sessao: Sessao,
    steam: tuple[Medida, Medida] | None = None,
) -> str:
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
    if steam is not None:
        partes.append(f"<p>Projeto STEAM: partes numéricas {para_tela(steam[0])}, rubrica {para_tela(steam[1])}</p>")
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


def _eventos_do_log(linhas: list[dict[str, object]]) -> list[EventoDoLog]:
    return [
        EventoDoLog(
            str(linha["tipo"]),
            str(linha["etapa"]),
            str(linha["item_id"]),
            None if linha["nivel"] is None else int(str(linha["nivel"])),
            datetime.fromisoformat(str(linha["criado_em"])),
        )
        for linha in linhas
    ]


def _mapa_de_calor(linhas: list[tuple[str, dict[tuple[str, str], Contagem]]]) -> str:
    """Participante por linha, habilidade e padrão por coluna, cor pela taxa (DO-48)."""
    habilidades = sorted({habilidade for _, contagens in linhas for habilidade, _ in contagens})
    if not habilidades:
        return (
            "<section><h2>Mapa de calor de atalhos cognitivos</h2>"
            "<p class='sutil'>Sem respostas ainda.</p></section>"
        )
    colunas = [(h, p) for h in habilidades for p in PADROES]
    cabecalho = "<th>Participante</th>" + "".join(
        f"<th title='{escape(p.condicao)}'>{escape(h)} · {escape(p.nome)}</th>" for h, p in colunas
    )
    corpo: list[str] = []
    for participante, contagens in linhas:
        celulas = [f"<td>{escape(participante)}</td>"]
        for h, p in colunas:
            c = contagens.get((h, p.id))
            if c is None or c.oportunidades == 0:
                celulas.append("<td class='calor sutil'>—</td>")
                continue
            taxa = round(100 * c.ocorrencias / c.oportunidades)
            celulas.append(
                f"<td class='calor' style='background:color-mix(in srgb, var(--aviso) {taxa}%, transparent)'"
                f" title='{c.ocorrencias} de {c.oportunidades}'>{c.ocorrencias}/{c.oportunidades}</td>"
            )
        corpo.append("<tr>" + "".join(celulas) + "</tr>")
    return (
        "<section><h2>Mapa de calor de atalhos cognitivos</h2>"
        "<p class='sutil'>Ocorrências sobre oportunidades de cada padrão; quanto mais forte a cor, maior a"
        " proporção. Os padrões estão em docs/atalhos-cognitivos.md (DO-48) e descrevem comportamento nas"
        " tarefas do estudo, não esforço nem capacidade (R25.8).</p>"
        f"<div class='tabela'><table><thead><tr>{cabecalho}</tr></thead><tbody>{''.join(corpo)}</tbody></table></div>"
        "</section>"
    )


def gerar_painel(servico: Servico) -> str:
    repositorio = servico.repositorio
    blocos: list[str] = []
    por_condicao: Counter[str] = Counter()
    recusadas: list[str] = []
    habilidade_de = {item.id: item.habilidade_alvo for item in servico.carga.itens}
    atalhos: list[tuple[str, dict[tuple[str, str], Contagem]]] = []
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
        eventos = _eventos_do_log(repositorio.eventos_para_exportar(sessao_id))
        atalhos.append(
            (registro.participante_id, contar(eventos, datetime.fromisoformat(criada_em), habilidade_de))
        )
        blocos.append(
            _bloco(
                sessao_id,
                criada_em,
                registro.participante_id,
                condicao,
                registro.proveniencia.limiares_versao,
                sessao,
                servico.medidas_steam(sessao_id, sessao),
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
    pendentes = sum(1 for s in repositorio.submissoes_steam() if not s.avaliadores)
    rubrica = (
        f"<p class='aviso'>Projetos STEAM aguardando rubrica do professor: {pendentes}.</p>" if pendentes else ""
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
        f"<p class='aviso'>{escape(AVISO_R25_8)}</p>{recusa}{rubrica}{_mapa_de_calor(atalhos)}"
        f"{corpo}</main></body></html>\n"
    )
