"""API local do protótipo: sessões, respostas e dicas. Só no laço local (D11).

Rotas sob ``/api``; o servidor de desenvolvimento do Vite encaminha ``/api`` para a porta
8000 (``scripts/dev-backend.ps1`` e ``scripts/dev-frontend.ps1``).

D11 sem autenticação só vale com a API inalcançável de fora da máquina. Duas defesas:
- recusa de servir quando o servidor escuta em endereço que não é de laço local, para que
  ``--host 0.0.0.0`` não exponha dados de estudante à rede da escola;
- lista de ``Host`` permitidos, contra *DNS rebinding* a partir de uma página aberta no
  navegador do próprio estudante.
"""

from __future__ import annotations

import subprocess
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from adia.cli import DIRETORIO_DE_ITENS, encontrar_raiz
from adia.ia.cliente_ollama import ClienteOllama
from adia.ia.subagentes.papeis import LIMITE_DA_EXPLICACAO
from adia.nucleo.sessao.gestor import OperacaoRecusada, ResumoDoCiclo, Sessao
from adia.orquestracao.servico import Servico, SessaoInconsistente, SessaoInexistente
from adia.persistencia.repositorio import BANCO_DE_DADOS, ParticipanteDesconhecido, Repositorio
from adia.tipos import Indisponivel, Medida, Nivel

ENDERECOS_LOCAIS = frozenset({"127.0.0.1", "::1"})
HOSTS_PERMITIDOS = ["127.0.0.1", "localhost", "[::1]"]


class SoLacoLocal:
    """Recusa todo pedido quando o servidor não está escutando no laço local (D11)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        servidor = scope.get("server")
        if scope["type"] in {"http", "websocket"} and (servidor is None or servidor[0] not in ENDERECOS_LOCAIS):
            resposta = PlainTextResponse(
                "A API do ADIA só atende em 127.0.0.1 (D11). Suba com --host 127.0.0.1.", status_code=403
            )
            await resposta(scope, receive, send)
            return
        await self.app(scope, receive, send)


class NovaSessao(BaseModel):
    participante: str = Field(pattern=r"^P-\d{4}$")


class NovaResposta(BaseModel):
    resposta: str = Field(max_length=2000)
    confianca: int = Field(ge=0, le=10)
    justificativa: str = Field(default="", max_length=2000)


class PedidoDeDica(BaseModel):
    nivel: Literal[1, 2, 3, 4]
    explicacao: str = Field(default="", max_length=LIMITE_DA_EXPLICACAO)


def _medida(valor: Medida) -> str | None:
    """Medida em duas casas, meio para cima (DO-06); indisponível vira ``None``, nunca zero."""
    return None if isinstance(valor, Indisponivel) else str(valor.quantize(Decimal("0.01"), ROUND_HALF_UP))


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
    """Estado para a tela do estudante. A condição experimental não sai daqui (cegamento)."""
    item = sessao.item_atual
    return {
        "id": sessao_id,
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


def _commit(raiz: Path) -> str | None:
    """Commit do código em execução, com ``-dirty`` se houver alteração local (proveniência)."""
    try:
        saida = subprocess.run(
            ["git", "describe", "--always", "--dirty", "--abbrev=40"],
            cwd=raiz,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout.strip() or None


def _http(erro: Exception) -> HTTPException:
    if isinstance(erro, SessaoInexistente):
        return HTTPException(status_code=404, detail=str(erro))
    if isinstance(erro, ParticipanteDesconhecido):
        return HTTPException(status_code=404, detail="Código não encontrado. Confira o código com o pesquisador.")
    if isinstance(erro, SessaoInconsistente):
        return HTTPException(status_code=409, detail=f"Sessão não pode ser retomada: {erro}")
    return HTTPException(status_code=409, detail=str(erro))


_ERROS_DE_DOMINIO = (OperacaoRecusada, ParticipanteDesconhecido, SessaoInconsistente)


def criar_app(raiz: Path, cliente: ClienteOllama | None = None) -> FastAPI:
    servico = Servico(
        raiz / DIRETORIO_DE_ITENS,
        cliente or ClienteOllama(),
        Repositorio(raiz / BANCO_DE_DADOS),
        commit=_commit(raiz),
    )
    app = FastAPI(title="ADIA-CognitiveLoop", version="0.1.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=HOSTS_PERMITIDOS)
    app.add_middleware(SoLacoLocal)
    app.state.servico = servico

    @app.get("/api/saude")
    def saude() -> dict[str, object]:
        return {"ia_disponivel": servico.cliente.disponivel(), "modelo": servico.cliente.modelo}

    @app.post("/api/sessoes")
    def iniciar_sessao(corpo: NovaSessao) -> dict[str, object]:
        try:
            sessao_id, sessao = servico.iniciar(corpo.participante)
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro
        return _estado(sessao_id, sessao)

    @app.get("/api/sessoes/{sessao_id}")
    def ler_sessao(sessao_id: str) -> dict[str, object]:
        try:
            return _estado(sessao_id, servico.obter(sessao_id))
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro

    @app.post("/api/sessoes/{sessao_id}/respostas")
    def responder(sessao_id: str, corpo: NovaResposta) -> dict[str, object]:
        try:
            julgamento, resumo = servico.responder(sessao_id, corpo.resposta, corpo.confianca, corpo.justificativa)
            estado = _estado(sessao_id, servico.obter(sessao_id))
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro
        resultado = julgamento.resultado
        return {
            "resultado": None if isinstance(resultado, Indisponivel) else resultado.value,
            "ciclo_fechado": None if resumo is None else _ciclo(resumo),
            "estado": estado,
        }

    @app.post("/api/sessoes/{sessao_id}/dicas")
    def pedir_dica(sessao_id: str, corpo: PedidoDeDica) -> dict[str, object]:
        try:
            dica = servico.dica(sessao_id, Nivel(corpo.nivel), corpo.explicacao)
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro
        return {"nivel": int(dica.nivel), "texto": dica.texto, "origem": dica.origem, "motivo": dica.motivo}

    return app


@cache
def _app_do_projeto() -> FastAPI:
    raiz = encontrar_raiz()
    if raiz is None:
        raise RuntimeError("Raiz do projeto não encontrada (pyproject.toml e .python-version).")
    return criar_app(raiz)


def __getattr__(nome: str) -> FastAPI:
    # `uvicorn adia.api.app:app` cria o app só quando pedido: importar o módulo (testes,
    # ferramentas) não carrega o banco de itens nem abre o SQLite do projeto.
    if nome == "app":
        return _app_do_projeto()
    raise AttributeError(nome)
