"""Teste de retenção: janela de DO-08, replay, prazo de DO-14 e exportação."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from adia.exportacao.csv_pesquisa import ler_metricas, medida_de
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.nucleo.sessao.gestor import OperacaoRecusada
from adia.nucleo.sessao.retencao import janela
from adia.orquestracao.exportar import exportar
from adia.orquestracao.servico import Servico
from adia.persistencia.repositorio import Repositorio
from adia.tipos import Etapa

_ITENS = Path(__file__).resolve().parents[3] / "data" / "itens"
_INICIO = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


class _ClienteFora(ClienteOllama):
    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        raise FalhaDeGeracao("dublê")


class _Relogio:
    def __init__(self) -> None:
        self.instante = _INICIO

    def __call__(self) -> datetime:
        return self.instante


def test_janela_fecha_antes_de_168_horas_e_marca_depois_de_216() -> None:
    fim = _INICIO
    assert not janela(fim, fim + timedelta(hours=167, minutes=59)).disponivel
    dentro = janela(fim, fim + timedelta(hours=168))
    assert dentro.disponivel and dentro.desvio_horas is None
    fora = janela(fim, fim + timedelta(hours=226))
    assert fora.disponivel and fora.desvio_horas == Decimal(10)
    assert dentro.abre_em == fim + timedelta(hours=168)


def _concluir(servico: Servico) -> str:
    sessao_id, sessao = servico.iniciar(servico.repositorio.criar_participantes("t", 1)[0])
    while not sessao.encerrada:
        item = sessao.item_atual
        assert item is not None
        servico.responder(sessao_id, item.gabarito, 10)
    return sessao_id


def _concluida_em(caminho: Path) -> datetime:
    with sqlite3.connect(caminho) as conexao:
        return datetime.fromisoformat(conexao.execute("SELECT concluida_em FROM sessao").fetchone()[0])


def test_retencao_completa_com_replay_prazo_e_exportacao(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    relogio = _Relogio()
    servico = Servico(_ITENS, _ClienteFora(), Repositorio(caminho), agora=relogio)
    sessao_id = _concluir(servico)
    concluida = _concluida_em(caminho)

    relogio.instante = concluida + timedelta(days=3)
    with pytest.raises(OperacaoRecusada, match="Volte nesse dia"):
        servico.iniciar_retencao(sessao_id)

    relogio.instante = concluida + timedelta(hours=170)
    sessao = servico.iniciar_retencao(sessao_id)
    assert sessao.etapa == Etapa.TESTE_RETENCAO and not sessao.com_ia
    vistos_antes = {r.item_id for r in sessao.respostas}
    primeiro = sessao.item_atual
    assert primeiro is not None and primeiro.id not in vistos_antes

    # Reinício no meio da retenção: o replay reabre a etapa e volta ao mesmo item.
    servico.responder(sessao_id, primeiro.gabarito, 10)
    reaberta = Servico(_ITENS, _ClienteFora(), Repositorio(caminho), agora=relogio).obter(sessao_id)
    assert reaberta.etapa == Etapa.TESTE_RETENCAO
    assert reaberta.item_atual == sessao.item_atual

    while not sessao.encerrada:
        item = sessao.item_atual
        assert item is not None
        servico.responder(sessao_id, item.gabarito, 10)
    assert sessao.retencao_concluida
    with pytest.raises(OperacaoRecusada):
        servico.iniciar_retencao(sessao_id)

    with sqlite3.connect(caminho) as conexao:
        ate, fim_ret, desvio = conexao.execute(
            "SELECT p.retencao_ate, s.retencao_concluida_em, s.retencao_desvio_horas "
            "FROM participante p JOIN sessao s ON s.participante_id = p.id"
        ).fetchone()
    assert datetime.fromisoformat(ate) - datetime.fromisoformat(fim_ret) == timedelta(days=180)
    assert desvio is None

    pasta = exportar(Servico(_ITENS, _ClienteFora(), Repositorio(caminho)), tmp_path / "saida").diretorio
    linhas = ler_metricas(next(pasta.glob("metricas_*.csv")).read_text(encoding="utf-8"))
    da_retencao = {linha["metrica"]: medida_de(linha) for linha in linhas if linha["etapa"] == "teste_retencao"}
    assert da_retencao["tai"] == Decimal(1)
    assert da_retencao["retencao"] == Decimal(1)
    assert da_retencao["horas_alem_da_janela"] == Decimal(0)


def test_retencao_fora_da_janela_abre_com_desvio_registrado(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    relogio = _Relogio()
    servico = Servico(_ITENS, _ClienteFora(), Repositorio(caminho), agora=relogio)
    sessao_id = _concluir(servico)
    relogio.instante = _concluida_em(caminho) + timedelta(hours=240)
    servico.iniciar_retencao(sessao_id)
    with sqlite3.connect(caminho) as conexao:
        desvio = conexao.execute("SELECT retencao_desvio_horas FROM sessao").fetchone()[0]
    assert Decimal(desvio) == Decimal(24)


def test_retencao_antes_de_terminar_as_rodadas_e_recusada(tmp_path: Path) -> None:
    servico = Servico(_ITENS, _ClienteFora(), Repositorio(tmp_path / "adia.db"))
    sessao_id, _ = servico.iniciar(servico.repositorio.criar_participantes("t", 1)[0])
    with pytest.raises(OperacaoRecusada, match="Termine as rodadas"):
        servico.iniciar_retencao(sessao_id)
