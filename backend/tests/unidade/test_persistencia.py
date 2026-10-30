"""Persistência SQLite: replay conferido, atribuição balanceada, decisões gravadas e exclusão."""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from adia.ia.cliente_ollama import MODELO_PADRAO, ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.orquestracao.servico import Servico, SessaoInconsistente, SessaoInexistente
from adia.persistencia.repositorio import ParticipanteDesconhecido, Repositorio, sortear_condicao
from adia.tipos import Condicao, Etapa, Nivel

_ITENS = Path(__file__).resolve().parents[3] / "data" / "itens"


class _ClienteFora(ClienteOllama):
    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        raise FalhaDeGeracao("dublê sem serviço")


def _servico(caminho: Path) -> Servico:
    return Servico(_ITENS, _ClienteFora(), Repositorio(caminho))


def _participante(servico: Servico, coorte: str = "teste") -> str:
    return servico.repositorio.criar_participantes(coorte, 1)[0]


def _responder_certo(servico: Servico, sessao_id: str) -> None:
    item = servico.obter(sessao_id).item_atual
    assert item is not None
    # Confiança 10 com acerto pleno: viés zero, então o ciclo decide fading.
    servico.responder(sessao_id, item.gabarito, 10)


def _linhas(caminho: Path, consulta: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(caminho) as conexao:
        return conexao.execute(consulta).fetchall()


def test_sessao_reconstruida_apos_reinicio_e_identica(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    primeiro = _servico(caminho)
    sessao_id, sessao = primeiro.iniciar(_participante(primeiro))
    while sessao.etapa != Etapa.PRATICA_ASSISTIDA or sessao.ciclo != 2:
        if sessao.com_ia and not sessao.dicas_do_item:
            primeiro.dica(sessao_id, Nivel.L2)
        _responder_certo(primeiro, sessao_id)
    primeiro.dica(sessao_id, Nivel.L1)  # dica pendente no item atual

    reiniciado = _servico(caminho).obter(sessao_id)
    assert (reiniciado.etapa, reiniciado.ciclo, reiniciado.teto) == (sessao.etapa, sessao.ciclo, sessao.teto)
    assert reiniciado.item_atual == sessao.item_atual
    assert reiniciado.dicas_do_item == (Nivel.L1,)
    assert reiniciado.respostas == sessao.respostas
    assert reiniciado.ciclos == sessao.ciclos


def test_mesmo_participante_retoma_a_mesma_sessao(tmp_path: Path) -> None:
    servico = _servico(tmp_path / "adia.db")
    participante = _participante(servico)
    primeiro, _ = servico.iniciar(participante)
    _responder_certo(servico, primeiro)
    segundo, sessao = _servico(tmp_path / "adia.db").iniciar(participante)
    assert segundo == primeiro
    assert len(sessao.respostas) == 1


def test_participante_nao_cadastrado_e_recusado(tmp_path: Path) -> None:
    with pytest.raises(ParticipanteDesconhecido):
        _servico(tmp_path / "adia.db").iniciar("P-9999")


def test_sessao_inexistente_e_recusada(tmp_path: Path) -> None:
    with pytest.raises(SessaoInexistente):
        _servico(tmp_path / "adia.db").obter("nao-existe")


@pytest.mark.parametrize(
    ("contagens", "possiveis"),
    [
        ({Condicao.A: 0, Condicao.B: 0, Condicao.C: 0}, {Condicao.A, Condicao.B, Condicao.C}),
        ({Condicao.A: 1, Condicao.B: 0, Condicao.C: 1}, {Condicao.B}),
        ({Condicao.A: 2, Condicao.B: 1, Condicao.C: 1}, {Condicao.B, Condicao.C}),
    ],
)
def test_sorteio_so_entre_as_condicoes_de_menor_contagem(
    contagens: dict[Condicao, int], possiveis: set[Condicao]
) -> None:
    assert {sortear_condicao(contagens, semente) for semente in range(200)} == possiveis


def test_atribuicao_balanceada_por_coorte(tmp_path: Path) -> None:
    servico = _servico(tmp_path / "adia.db")
    for coorte in ("turma-a", "turma-b"):
        for codigo in servico.repositorio.criar_participantes(coorte, 7):
            servico.iniciar(codigo)
    for coorte in ("turma-a", "turma-b"):
        linhas = _linhas(
            tmp_path / "adia.db",
            "SELECT s.condicao FROM sessao s JOIN participante p ON p.id = s.participante_id "
            f"WHERE p.coorte = '{coorte}'",
        )
        contagem = Counter(str(linha[0]) for linha in linhas)
        assert max(contagem.values()) - min(contagem.values()) <= 1
        assert sum(contagem.values()) == 7


def test_decisao_de_cada_ciclo_gravada_com_a_proveniencia(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    servico = _servico(caminho)
    sessao_id, sessao = servico.iniciar(_participante(servico))
    while not sessao.encerrada:
        _responder_certo(servico, sessao_id)
    decisoes = _linhas(caminho, "SELECT ciclo, decisao, aplicada FROM decisao_ciclo ORDER BY ciclo")
    aplicada = int(sessao.condicao is Condicao.B)
    assert decisoes == [(1, "fading", aplicada), (2, "fading", aplicada), (3, "fading", aplicada)]
    proveniencia = _linhas(caminho, "SELECT hash_banco_itens, modelo, limiares_versao, concluida_em FROM sessao")
    assert len(str(proveniencia[0][0])) == 64
    assert proveniencia[0][1:3] == (MODELO_PADRAO, "readme-v1")
    assert proveniencia[0][3] is not None
    assert _linhas(caminho, "SELECT retencao_ate FROM participante")[0][0] is not None


def test_registro_de_eventos_e_append_only(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    servico = _servico(caminho)
    sessao_id, _ = servico.iniciar(_participante(servico))
    servico.responder(sessao_id, "0", 5)
    with sqlite3.connect(caminho) as conexao:
        for comando in ("UPDATE evento SET acerto = 1", "DELETE FROM evento", "DELETE FROM decisao_ciclo"):
            try:
                conexao.execute(comando)
            except sqlite3.IntegrityError as erro:
                assert "append-only" in str(erro)
    assert len(_linhas(caminho, "SELECT id FROM evento")) == 1


def test_evento_que_nao_bate_com_o_replay_falha_fechado(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    servico = _servico(caminho)
    sessao_id, sessao = servico.iniciar(_participante(servico))
    item = sessao.item_atual
    assert item is not None
    with sqlite3.connect(caminho) as conexao:
        # Mesmo item, teto adulterado: o replay tem de recusar, não aceitar o teto atual.
        conexao.execute(
            "INSERT INTO evento (sessao_id, tipo, etapa, ciclo, item_id, teto, resposta, confianca, criado_em) "
            "VALUES (?, 'resposta', 'linha_de_base', 0, ?, 2, '1', 5, 'x')",
            (sessao_id, item.id),
        )
    with pytest.raises(SessaoInconsistente):
        _servico(caminho).obter(sessao_id)


def test_banco_de_itens_alterado_impede_a_retomada(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    servico = _servico(caminho)
    sessao_id, _ = servico.iniciar(_participante(servico))
    with sqlite3.connect(caminho) as conexao:
        conexao.execute("UPDATE sessao SET hash_banco_itens = 'outro' WHERE id = ?", (sessao_id,))
    with pytest.raises(SessaoInconsistente, match="outro banco de itens"):
        _servico(caminho).obter(sessao_id)


def test_exclusao_apaga_tudo_do_participante_e_registra(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    servico = _servico(caminho)
    alvo, outro = servico.repositorio.criar_participantes("turma", 2)
    for codigo in (alvo, outro):
        sessao_id, sessao = servico.iniciar(codigo)
        while not sessao.encerrada:
            _responder_certo(servico, sessao_id)

    apagados = servico.repositorio.excluir_participante(alvo, "pedido")

    assert apagados == 31
    assert _linhas(caminho, "SELECT id FROM participante") == [(outro,)]
    assert len(_linhas(caminho, "SELECT 1 FROM sessao")) == 1
    assert len(_linhas(caminho, "SELECT 1 FROM decisao_ciclo")) == 3
    assert len(_linhas(caminho, "SELECT 1 FROM evento")) == 31
    assert _linhas(caminho, "SELECT participante_id, motivo, eventos FROM exclusao") == [(alvo, "pedido", 31)]
    assert _linhas(caminho, "SELECT 1 FROM exclusao_em_curso") == []


def test_expirados_so_depois_do_prazo(tmp_path: Path) -> None:
    servico = _servico(tmp_path / "adia.db")
    codigo = _participante(servico)
    sessao_id, sessao = servico.iniciar(codigo)
    while not sessao.encerrada:
        _responder_certo(servico, sessao_id)
    prazo = datetime.fromisoformat(str(_linhas(tmp_path / "adia.db", "SELECT retencao_ate FROM participante")[0][0]))
    concluida = datetime.fromisoformat(str(_linhas(tmp_path / "adia.db", "SELECT concluida_em FROM sessao")[0][0]))
    assert prazo - concluida == timedelta(days=180)
    assert servico.repositorio.expirados(prazo - timedelta(seconds=1)) == []
    assert servico.repositorio.expirados(prazo + timedelta(seconds=1)) == [codigo]


def test_migracao_e_idempotente(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    Repositorio(caminho)
    Repositorio(caminho)
    assert _linhas(caminho, "PRAGMA user_version") == [(1,)]
