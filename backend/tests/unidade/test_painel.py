"""Painel do pesquisador, apresentação em tela (DO-05, DO-06) e CLI de limiares."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from adia import caminhos, cli
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.nucleo.metricas.formatacao import aviso_do_iic, para_tela
from adia.orquestracao.painel import AVISO_R25_8, gerar_painel
from adia.orquestracao.servico import Servico
from adia.persistencia.repositorio import Repositorio
from adia.tipos import Indisponivel

_ITENS = Path(__file__).resolve().parents[3] / "data" / "itens"


class _ClienteFora(ClienteOllama):
    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        raise FalhaDeGeracao("dublê")


@pytest.mark.parametrize(
    ("valor", "texto"),
    [
        (Decimal("0.125"), "0,13"),  # meio para cima, não meio para o par
        (Decimal("0.135"), "0,14"),
        (Decimal(1), "1,00"),
        (Indisponivel("sem base"), "indisponível"),
    ],
)
def test_para_tela_duas_casas_meio_para_cima(valor: Decimal | Indisponivel, texto: str) -> None:
    assert para_tela(valor) == texto


def test_aviso_do_iic_so_com_iic_alto_e_tai_baixa() -> None:
    assert aviso_do_iic(Decimal("0.9"), Decimal("0.3")) is not None
    assert aviso_do_iic(Decimal("0.9"), Decimal("0.5")) is None
    assert aviso_do_iic(Decimal("0.5"), Decimal("0.3")) is None
    assert aviso_do_iic(Indisponivel("x"), Decimal("0.3")) is None


def test_painel_mostra_condicao_metricas_sombra_e_aviso(tmp_path: Path) -> None:
    servico = Servico(_ITENS, _ClienteFora(), Repositorio(tmp_path / "adia.db"))
    for codigo in servico.repositorio.criar_participantes("t", 3):
        sessao_id, sessao = servico.iniciar(codigo)
        while not sessao.encerrada:
            item = sessao.item_atual
            assert item is not None
            # Acerta na prática e erra no desafio; a justificativa cobre o excesso de confiança em B.
            certo = sessao.com_ia
            servico.responder(sessao_id, item.gabarito if certo else "999", 5, "fiz a conta")
    html = gerar_painel(servico)
    assert AVISO_R25_8 in html
    assert "Sessões por condição: A: 1, B: 1, C: 1" in html
    assert "(sombra)" in html  # A e C registram a decisão sem aplicar
    assert "P-0001" in html and "ciclos concluídos, retenção pendente" in html


def test_cli_de_limiares_grava_versao_nova(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for marca in caminhos.MARCAS_DA_RAIZ:
        (tmp_path / marca).write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert cli.principal(["limiares", "--independente-fading", "0,85"]) == cli.CODIGO_OK
    assert Repositorio(tmp_path / "data" / "adia.db").limiares().independente_fading == Decimal("0.85")
    assert cli.principal(["limiares", "--gap-maximo", "2"]) == cli.CODIGO_BANCO_INVALIDO
