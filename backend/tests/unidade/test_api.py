"""API local: fronteira de rede (D11), cegamento da condição e mapeamento de erros."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adia.api.app import criar_app
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.persistencia.repositorio import BANCO_DE_DADOS, Repositorio

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


@pytest.fixture
def app(raiz: Path) -> FastAPI:
    return criar_app(raiz, _ClienteFora())


def test_recusa_servir_fora_do_laco_local(app: FastAPI) -> None:
    resposta = TestClient(app, base_url="http://10.0.0.5:8000").get("/api/saude", headers={"host": "127.0.0.1"})
    assert resposta.status_code == 403


def test_recusa_host_estranho_contra_dns_rebinding(app: FastAPI) -> None:
    resposta = TestClient(app, base_url=_LOCAL).get("/api/saude", headers={"host": "atacante.example"})
    assert resposta.status_code == 400


def test_fluxo_com_participante_cadastrado_sem_expor_a_condicao(app: FastAPI, raiz: Path) -> None:
    cliente = TestClient(app, base_url=_LOCAL)
    assert cliente.post("/api/sessoes", json={"participante": "P-0001"}).status_code == 404
    assert cliente.post("/api/sessoes", json={"participante": "Joana"}).status_code == 422

    codigo = Repositorio(raiz / BANCO_DE_DADOS).criar_participantes("turma", 1)[0]
    estado = cliente.post("/api/sessoes", json={"participante": codigo}).json()
    assert "condicao" not in estado
    assert estado["etapa"] == "linha_de_base"

    assert cliente.post(f"/api/sessoes/{estado['id']}/dicas", json={"nivel": 1}).status_code == 409
    assert cliente.post("/api/sessoes/nao-existe/respostas", json={"resposta": "1", "confianca": 5}).status_code == 404
    resposta = cliente.post(f"/api/sessoes/{estado['id']}/respostas", json={"resposta": "1", "confianca": 5})
    assert resposta.status_code == 200
    assert resposta.json()["estado"]["restantes"] == estado["restantes"] - 1
