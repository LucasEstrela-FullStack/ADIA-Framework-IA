"""API local do protótipo: sessões, respostas e dicas. Bind em 127.0.0.1 (D11).

Rotas sob ``/api``; o servidor de desenvolvimento do Vite encaminha ``/api`` para a porta
8000 (``scripts/dev-backend.ps1`` e ``scripts/dev-frontend.ps1``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from adia.cli import DIRETORIO_DE_ITENS, encontrar_raiz
from adia.ia.cliente_ollama import ClienteOllama
from adia.nucleo.sessao.gestor import OperacaoRecusada, ResumoDoCiclo, Sessao
from adia.orquestracao.servico import Servico
from adia.persistencia.repositorio import Repositorio
from adia.tipos import Condicao, Indisponivel, Medida, Nivel

_raiz = encontrar_raiz()
if _raiz is None:
    raise RuntimeError("Raiz do projeto não encontrada (pyproject.toml e .python-version).")
# data/adia.db fica fora do git pelo padrão *.db do .gitignore: contém dados de estudante.
servico = Servico(_raiz / DIRETORIO_DE_ITENS, ClienteOllama(), Repositorio(_raiz / "data" / "adia.db"))
app = FastAPI(title="ADIA-CognitiveLoop", version="0.1.0")


class NovaSessao(BaseModel):
    condicao: Condicao = Condicao.B


class NovaResposta(BaseModel):
    resposta: str = Field(max_length=2000)
    confianca: int = Field(ge=0, le=10)


class PedidoDeDica(BaseModel):
    nivel: Literal[1, 2, 3, 4]
    explicacao: str = Field(default="", max_length=2000)


def _medida(valor: Medida) -> str | None:
    """Medida como texto decimal; indisponível vira ``None`` com o motivo ao lado, nunca zero."""
    return None if isinstance(valor, Indisponivel) else str(valor.quantize(Decimal("0.0001")))


def _ciclo(resumo: ResumoDoCiclo) -> dict[str, object]:
    return {
        "ciclo": resumo.ciclo,
        "teto": resumo.teto.name,
        "tai": _medida(resumo.acerto_independente),
        "acerto_assistido": _medida(resumo.acerto_assistido),
        "transferencia": _medida(resumo.transferencia),
        "confianca": _medida(resumo.confianca),
        "dss": _medida(resumo.dss),
        "iic": _medida(resumo.iic),
        "gap": _medida(resumo.decisao.gap),
        "vies": _medida(resumo.decisao.vies),
        "decisao": resumo.decisao.tipo.value,
        "evidencia_incompleta": resumo.decisao.evidencia_incompleta,
        "teto_seguinte": resumo.teto_seguinte.name,
    }


def _estado(sessao_id: str, sessao: Sessao) -> dict[str, object]:
    item = sessao.item_atual
    return {
        "id": sessao_id,
        "condicao": sessao.condicao.value,
        "etapa": str(sessao.etapa),
        "ciclo": sessao.ciclo,
        "teto": int(sessao.teto),
        "com_ia": sessao.com_ia,
        "onloading": sessao.onloading,
        "justificativa_exigida": sessao.justificativa_exigida,
        "restantes": len(sessao.fila),
        "dicas_usadas": [int(n) for n in sessao.dicas_do_item],
        "item": None if item is None else {"id": item.id, "enunciado": item.enunciado},
        "ciclos": [_ciclo(c) for c in sessao.ciclos],
    }


def _recusa(erro: OperacaoRecusada) -> HTTPException:
    return HTTPException(status_code=409, detail=str(erro))


@app.get("/api/saude")
def saude() -> dict[str, object]:
    return {"ia_disponivel": servico.cliente.disponivel(), "modelo": servico.cliente.modelo}


@app.post("/api/sessoes")
def criar_sessao(corpo: NovaSessao) -> dict[str, object]:
    sessao_id, sessao = servico.criar(corpo.condicao)
    return _estado(sessao_id, sessao)


@app.get("/api/sessoes/{sessao_id}")
def ler_sessao(sessao_id: str) -> dict[str, object]:
    try:
        return _estado(sessao_id, servico.obter(sessao_id))
    except OperacaoRecusada as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro


@app.post("/api/sessoes/{sessao_id}/respostas")
def responder(sessao_id: str, corpo: NovaResposta) -> dict[str, object]:
    try:
        julgamento, resumo = servico.responder(sessao_id, corpo.resposta, corpo.confianca)
    except OperacaoRecusada as erro:
        raise _recusa(erro) from erro
    resultado = julgamento.resultado
    return {
        "resultado": None if isinstance(resultado, Indisponivel) else resultado.value,
        "ciclo_fechado": None if resumo is None else _ciclo(resumo),
        "estado": _estado(sessao_id, servico.obter(sessao_id)),
    }


@app.post("/api/sessoes/{sessao_id}/dicas")
def pedir_dica(sessao_id: str, corpo: PedidoDeDica) -> dict[str, object]:
    try:
        dica = servico.dica(sessao_id, Nivel(corpo.nivel), corpo.explicacao)
    except OperacaoRecusada as erro:
        raise _recusa(erro) from erro
    return {"nivel": int(dica.nivel), "texto": dica.texto, "origem": dica.origem, "motivo": dica.motivo}
