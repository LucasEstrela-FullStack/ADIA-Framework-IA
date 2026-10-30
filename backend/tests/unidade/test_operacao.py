"""Operação do piloto: frontend servido pela API, backup do banco e teste com o Ollama ligado."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adia.api.app import criar_app
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.ia.subagentes.papeis import PAPEIS, pedido
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.persistencia.repositorio import BANCO_DE_DADOS, Repositorio
from adia.tipos import Nivel

_RAIZ = Path(__file__).resolve().parents[3]
_LOCAL = "http://127.0.0.1:8000"


class _ClienteFora(ClienteOllama):
    def disponivel(self) -> bool:
        return False

    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        raise FalhaDeGeracao("dublê")


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    shutil.copytree(_RAIZ / "data" / "itens", tmp_path / "data" / "itens")
    return tmp_path


def test_api_serve_o_frontend_construido_sem_esconder_as_rotas(raiz: Path) -> None:
    (raiz / "frontend" / "dist").mkdir(parents=True)
    (raiz / "frontend" / "dist" / "index.html").write_text("<p>ADIA</p>", encoding="utf-8")
    cliente = TestClient(criar_app(raiz, _ClienteFora()), base_url=_LOCAL)
    assert cliente.get("/").text == "<p>ADIA</p>"
    assert cliente.get("/api/saude").json()["ia_disponivel"] is False


def test_sem_frontend_construido_a_api_continua_de_pe(raiz: Path) -> None:
    cliente = TestClient(criar_app(raiz, _ClienteFora()), base_url=_LOCAL)
    assert cliente.get("/").status_code == 404
    assert cliente.get("/api/saude").status_code == 200


def test_backup_e_uma_copia_consistente(tmp_path: Path) -> None:
    repositorio = Repositorio(tmp_path / BANCO_DE_DADOS)
    repositorio.criar_participantes("t", 2)
    copia = repositorio.copiar(tmp_path / "backups")
    with sqlite3.connect(copia) as conexao:
        assert conexao.execute("SELECT count(*) FROM participante").fetchone() == (2,)
    assert copia.name.startswith("adia-") and copia.suffix == ".db"


@pytest.mark.ollama
def test_ollama_ligado_gera_dica_sem_vazar() -> None:
    """Rodar antes de cada coleta: `uv run pytest -m ollama`. Fica fora do portão."""
    cliente = ClienteOllama()
    assert cliente.disponivel(), f"Ollama sem o modelo {cliente.modelo}: rode `ollama pull {cliente.modelo}`"
    carga = carregar(arquivos_de_itens(_RAIZ / "data" / "itens"))
    assert isinstance(carga, CargaConcluida)
    item = next(i for i in carga.itens if i.e_praticado)
    resposta = cliente.gerar(PAPEIS[Nivel.L1], pedido(item.enunciado, item.dicas[Nivel.L1], ""))
    assert resposta.texto.strip()
    assert resposta.latencia_ms < 20_000
