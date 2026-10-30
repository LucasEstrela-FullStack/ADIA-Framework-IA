"""Persistência SQLite: a sessão sobrevive ao reinício e o registro é append-only."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.nucleo.sessao.gestor import OperacaoRecusada
from adia.orquestracao.servico import Servico, SessaoInconsistente
from adia.persistencia.repositorio import Repositorio
from adia.tipos import Condicao, Etapa, Nivel

_ITENS = Path(__file__).resolve().parents[3] / "data" / "itens"


class _ClienteFora(ClienteOllama):
    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        raise FalhaDeGeracao("dublê sem serviço")


def _servico(caminho: Path) -> Servico:
    return Servico(_ITENS, _ClienteFora(), Repositorio(caminho))


def _gabarito(servico: Servico, sessao_id: str) -> str:
    item = servico.obter(sessao_id).item_atual
    assert item is not None
    return item.gabarito


def test_sessao_reconstruida_apos_reinicio_e_identica(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    primeiro = _servico(caminho)
    sessao_id, sessao = primeiro.criar(Condicao.B)
    while sessao.etapa != Etapa.PRATICA_ASSISTIDA or sessao.ciclo != 2:
        if sessao.com_ia and not sessao.dicas_do_item:
            primeiro.dica(sessao_id, Nivel.L2)
        primeiro.responder(sessao_id, _gabarito(primeiro, sessao_id), 7)
    primeiro.dica(sessao_id, Nivel.L1)  # dica pendente no item atual

    reiniciado = _servico(caminho).obter(sessao_id)
    assert reiniciado.etapa == sessao.etapa
    assert reiniciado.ciclo == sessao.ciclo
    assert reiniciado.teto == sessao.teto
    assert reiniciado.item_atual == sessao.item_atual
    assert reiniciado.dicas_do_item == (Nivel.L1,)
    assert reiniciado.respostas == sessao.respostas
    assert reiniciado.ciclos == sessao.ciclos


def test_sessao_inexistente_e_recusada(tmp_path: Path) -> None:
    with pytest.raises(OperacaoRecusada):
        _servico(tmp_path / "adia.db").obter("nao-existe")


def test_registro_de_eventos_e_append_only(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    servico = _servico(caminho)
    sessao_id, _ = servico.criar(Condicao.A)
    servico.responder(sessao_id, "0", 5)
    with sqlite3.connect(caminho) as conexao:
        for comando in ("UPDATE evento SET acerto = 1", "DELETE FROM evento"):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                conexao.execute(comando)


def test_evento_que_nao_bate_com_o_banco_falha_fechado(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    sessao_id, _ = _servico(caminho).criar(Condicao.B)
    with sqlite3.connect(caminho) as conexao:
        conexao.execute(
            "INSERT INTO evento (sessao_id, tipo, etapa, ciclo, item_id, teto, resposta, confianca, criado_em) "
            "VALUES (?, 'resposta', 'linha_de_base', 0, 'item-de-outro-banco', 4, '1', 5, 'x')",
            (sessao_id,),
        )
    with pytest.raises(SessaoInconsistente):
        _servico(caminho).obter(sessao_id)


def test_migracao_e_idempotente(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    Repositorio(caminho)
    Repositorio(caminho)
    with sqlite3.connect(caminho) as conexao:
        assert conexao.execute("PRAGMA user_version").fetchone()[0] == 1
