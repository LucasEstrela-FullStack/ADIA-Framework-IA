"""Mapa de calor de atalhos cognitivos: padrões sobre o log e a tabela do painel (R19.2, DO-48)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.nucleo.metricas.atalhos import Contagem, EventoDoLog, contar
from adia.orquestracao.painel import gerar_painel
from adia.orquestracao.servico import Servico
from adia.persistencia.repositorio import Repositorio
from adia.tipos import Etapa, Nivel

_ITENS = Path(__file__).resolve().parents[3] / "data" / "itens"
_INICIO = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)


def _em(segundos: float) -> datetime:
    return _INICIO + timedelta(seconds=segundos)


def _dica(item: str, nivel: int, segundos: float, etapa: str = "pratica_assistida") -> EventoDoLog:
    return EventoDoLog("dica", etapa, item, nivel, _em(segundos))


def _resposta(item: str, segundos: float, etapa: str = "pratica_assistida") -> EventoDoLog:
    return EventoDoLog("resposta", etapa, item, None, _em(segundos))


def test_padroes_contam_ocorrencias_sobre_oportunidades() -> None:
    eventos = [
        _resposta("b1", 3, "linha_de_base"),  # relâmpago: 3 s desde o início
        _resposta("b2", 60, "linha_de_base"),
        _dica("p1", 4, 70),  # alta direta, e exemplo seguido de resposta em 10 s
        _resposta("p1", 80),
        _dica("p2", 1, 100),
        _dica("p2", 4, 110),  # escalou pela escada: não é alta direta; resposta 40 s depois
        _resposta("p2", 150),
        _resposta("p3", 152),  # sem dica: nenhuma oportunidade dos dois padrões de dica
        _resposta("d1", 154, "desafio_independente"),  # 2 s depois da anterior: relâmpago
        _resposta("x9", 400, "desafio_independente"),
    ]
    habilidade = {"b1": "eq", "b2": "eq", "p1": "eq", "p2": "eq", "p3": "eq", "d1": "eq"}
    contagens = contar(eventos, _INICIO, habilidade)
    assert contagens[("eq", "dica_alta_direta")] == Contagem(1, 2)
    assert contagens[("eq", "resposta_logo_apos_exemplo")] == Contagem(1, 2)
    assert contagens[("eq", "resposta_relampago")] == Contagem(2, 3)
    assert contagens[("desconhecida", "resposta_relampago")] == Contagem(0, 1), "item sem habilidade não some"


def test_sem_eventos_nao_ha_contagem() -> None:
    assert contar([], _INICIO, {}) == {}


class _ClienteFora(ClienteOllama):
    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        raise FalhaDeGeracao("dublê")


def test_painel_mostra_o_mapa_de_calor(tmp_path: Path) -> None:
    servico = Servico(_ITENS, _ClienteFora(), Repositorio(tmp_path / "adia.db"))
    assert "Sem respostas ainda" in gerar_painel(servico)
    participante = servico.repositorio.criar_participantes("turma", 1)[0]
    sessao_id, sessao = servico.iniciar(participante)
    while sessao.etapa != Etapa.PRATICA_ASSISTIDA:
        item = sessao.item_atual
        assert item is not None
        servico.responder(sessao_id, item.gabarito, 5)
    servico.dica(sessao_id, Nivel.L4)
    item = sessao.item_atual
    assert item is not None
    servico.responder(sessao_id, item.gabarito, 5)

    html = gerar_painel(servico)
    assert "Mapa de calor de atalhos cognitivos" in html
    assert f"<td>{participante}</td>" in html
    assert "equacao_linear · Dica alta direta" in html
    assert "title='1 de 1'>1/1</td>" in html, "L4 como primeira dica e resposta logo depois"
    assert "não esforço nem capacidade (R25.8)" in html
