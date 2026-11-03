"""API local do protótipo: sessões, respostas, dicas e projeto STEAM. Só no laço local (D11).

Rotas sob ``/api``; o servidor de desenvolvimento do Vite encaminha ``/api`` para a porta
8000 (``scripts/dev-backend.ps1`` e ``scripts/dev-frontend.ps1``).

D11 sem autenticação só vale com a API inalcançável de fora da máquina. Duas defesas:
- recusa de servir quando o servidor escuta em endereço que não é de laço local, para que
  ``--host 0.0.0.0`` não exponha dados de estudante à rede da escola;
- lista de ``Host`` permitidos, contra *DNS rebinding* a partir de uma página aberta no
  navegador do próprio estudante.

As rotas do professor (``/api/professor``) exigem ainda a chave de ``adia professor chave``: o
estudante usa a mesma máquina, e o laço local sozinho não separa os dois papéis.
"""

from __future__ import annotations

import logging
import secrets
import subprocess
from functools import cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from adia.caminhos import (
    CHAVE_DO_PROFESSOR,
    DIRETORIO_CORPUS,
    DIRETORIO_DE_ITENS,
    DIRETORIO_STEAM,
    INDICE_RAG,
    encontrar_raiz,
)
from adia.ia.cliente_ollama import ClienteOllama
from adia.ia.rag.indice import abrir, arquivos_do_corpus
from adia.ia.subagentes.papeis import LIMITE_DA_EXPLICACAO
from adia.nucleo.sessao.gestor import OperacaoRecusada, Sessao
from adia.orquestracao.servico import Servico, SessaoInconsistente, SessaoInexistente, SubmissaoInexistente
from adia.persistencia.repositorio import BANCO_DE_DADOS, ParticipanteDesconhecido, Repositorio, SubmissaoGravada
from adia.tipos import Etapa, Nivel

_log = logging.getLogger(__name__)

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


_Curto = Annotated[str, Field(max_length=64)]


class SubmissaoSteam(BaseModel):
    partes: dict[_Curto, Annotated[str, Field(max_length=200)]] = Field(max_length=10)
    justificativa: str = Field(max_length=4000)


class NovaAvaliacao(BaseModel):
    avaliador: str = Field(pattern=r"^PROF-\d{2}$")
    niveis: dict[_Curto, _Curto] = Field(max_length=20)


class PedidoDeDica(BaseModel):
    nivel: Literal[1, 2, 3, 4]
    explicacao: str = Field(default="", max_length=LIMITE_DA_EXPLICACAO)


def _estado(sessao_id: str, sessao: Sessao, servico: Servico) -> dict[str, object]:
    """Estado para a tela do estudante.

    Sem condição, sem métricas e sem decisão de regulação: o estudante não vê em que grupo
    está nem o próprio desempenho entre ciclos, igual nas três condições. Mostrar desempenho
    seria uma intervenção a mais, fora do protocolo, e é decisão de pesquisa ainda aberta.
    Os números ficam no banco para o painel do pesquisador.
    """
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
        "item": None
        if item is None
        else {"id": item.id, "enunciado": item.enunciado, "tamanho_max": item.tamanho_max_resposta},
        "steam": _steam(sessao) if sessao.etapa == Etapa.PROJETO_STEAM else None,
        "retencao": _retencao(sessao_id, sessao, servico) if sessao.encerrada else None,
    }


def _steam(sessao: Sessao) -> dict[str, object] | None:
    """O cenário como o estudante o lê: sem gabarito, tolerância nem rubrica."""
    cenario = sessao.cenario
    if cenario is None:
        return None
    return {
        "titulo": cenario.titulo,
        "enunciado": cenario.enunciado,
        "partes": [
            {"parte": p.parte, "pergunta": p.pergunta, "unidade": p.unidade, "tamanho_max": p.tamanho_max_resposta}
            for p in cenario.partes
        ],
        "justificativa": {
            "pergunta": cenario.pergunta_da_justificativa,
            "tamanho_max": cenario.tamanho_max_justificativa,
        },
    }


def _submissao(submissao: SubmissaoGravada, servico: Servico) -> dict[str, object]:
    """Submissão para o professor: cega para participante e condição."""
    cenario = next((c for c in servico.steam.cenarios if c.id == submissao.cenario_id), None)
    return {
        "id": submissao.id,
        "cenario": submissao.cenario_id if cenario is None else cenario.titulo,
        "criado_em": submissao.criado_em,
        "avaliadores": list(submissao.avaliadores),
    }


def _retencao(sessao_id: str, sessao: Sessao, servico: Servico) -> dict[str, object]:
    """Última parte (teste de 7 dias): se já foi feita, se abriu e quando abre."""
    janela = servico.janela_da_retencao(sessao_id)
    return {
        "concluida": sessao.retencao_concluida,
        "disponivel": janela is not None and janela.disponivel,
        "abre_em": None if janela is None else janela.abre_em.isoformat(),
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
    if isinstance(erro, SessaoInexistente | SubmissaoInexistente):
        return HTTPException(status_code=404, detail=str(erro))
    if isinstance(erro, ParticipanteDesconhecido):
        return HTTPException(status_code=404, detail="Código não encontrado. Confira o código com o pesquisador.")
    if isinstance(erro, SessaoInconsistente):
        return HTTPException(status_code=409, detail=f"Sessão não pode ser retomada: {erro}")
    return HTTPException(status_code=409, detail=str(erro))


_ERROS_DE_DOMINIO = (OperacaoRecusada, ParticipanteDesconhecido, SessaoInconsistente)


def criar_app(raiz: Path, cliente: ClienteOllama | None = None) -> FastAPI:
    corpus = arquivos_do_corpus(raiz / DIRETORIO_CORPUS)
    rag = abrir(raiz / INDICE_RAG, corpus)
    if corpus and rag is None:
        # Sem índice as dicas seguem só com o material do item: avisa, mas não impede a coleta.
        _log.warning("índice do RAG ausente ou de outro corpus: rode `uv run adia indexar`")
    servico = Servico(
        raiz / DIRETORIO_DE_ITENS,
        cliente or ClienteOllama(),
        Repositorio(raiz / BANCO_DE_DADOS),
        commit=_commit(raiz),
        diretorio_steam=raiz / DIRETORIO_STEAM,
        rag=rag,
    )

    def professor(x_chave_professor: Annotated[str | None, Header()] = None) -> None:
        # Lida a cada pedido: gerar uma chave nova revoga a anterior sem reiniciar o servidor.
        arquivo = raiz / CHAVE_DO_PROFESSOR
        if not arquivo.is_file():
            raise HTTPException(status_code=503, detail="Chave do professor não gerada: rode adia professor chave.")
        chave = arquivo.read_text(encoding="utf-8").strip()
        if not x_chave_professor or not secrets.compare_digest(x_chave_professor.encode(), chave.encode()):
            raise HTTPException(status_code=401, detail="Chave do professor incorreta.")

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
        return _estado(sessao_id, sessao, servico)

    @app.get("/api/sessoes/{sessao_id}")
    def ler_sessao(sessao_id: str) -> dict[str, object]:
        try:
            return _estado(sessao_id, servico.obter(sessao_id), servico)
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro

    @app.post("/api/sessoes/{sessao_id}/respostas")
    def responder(sessao_id: str, corpo: NovaResposta) -> dict[str, object]:
        try:
            _, resumo = servico.responder(sessao_id, corpo.resposta, corpo.confianca, corpo.justificativa)
            estado = _estado(sessao_id, servico.obter(sessao_id), servico)
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro
        # O acerto não volta para a tela: só o número da rodada que acabou de fechar.
        return {"ciclo_concluido": None if resumo is None else resumo.ciclo, "estado": estado}

    @app.post("/api/sessoes/{sessao_id}/retencao")
    def iniciar_retencao(sessao_id: str) -> dict[str, object]:
        try:
            return _estado(sessao_id, servico.iniciar_retencao(sessao_id), servico)
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro

    @app.post("/api/sessoes/{sessao_id}/steam")
    def submeter_steam(sessao_id: str, corpo: SubmissaoSteam) -> dict[str, object]:
        try:
            return _estado(sessao_id, servico.submeter_steam(sessao_id, corpo.partes, corpo.justificativa), servico)
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro

    @app.get("/api/professor/submissoes", dependencies=[Depends(professor)])
    def listar_submissoes() -> list[dict[str, object]]:
        return [_submissao(s, servico) for s in servico.repositorio.submissoes_steam()]

    @app.get("/api/professor/submissoes/{submissao_id}", dependencies=[Depends(professor)])
    def ler_submissao(submissao_id: int) -> dict[str, object]:
        try:
            submissao = servico.submissao(submissao_id)
            rubrica = servico.rubrica_de(submissao)
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro
        cenario = next((c for c in servico.steam.cenarios if c.id == submissao.cenario_id), None)
        return {
            **_submissao(submissao, servico),
            "pergunta": None if cenario is None else cenario.pergunta_da_justificativa,
            "justificativa": submissao.justificativa,
            "rubrica": {
                "titulo": rubrica.titulo,
                "descricao": rubrica.descricao,
                "criterios": [
                    {
                        "criterio": c.criterio,
                        "descricao": c.descricao,
                        "niveis": [{"nivel": n.nivel, "pontos": n.pontos, "descricao": n.descricao} for n in c.niveis],
                    }
                    for c in rubrica.criterios
                ],
            },
        }

    @app.post("/api/professor/submissoes/{submissao_id}/avaliacoes", dependencies=[Depends(professor)])
    def avaliar(submissao_id: int, corpo: NovaAvaliacao) -> dict[str, object]:
        try:
            avaliacao = servico.avaliar(submissao_id, corpo.avaliador, corpo.niveis)
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro
        return {"pontos": sum(p for _, _, p in avaliacao.pontuacoes), "pontos_maximos": avaliacao.pontos_maximos}

    @app.post("/api/sessoes/{sessao_id}/dicas")
    def pedir_dica(sessao_id: str, corpo: PedidoDeDica) -> dict[str, object]:
        try:
            dica = servico.dica(sessao_id, Nivel(corpo.nivel), corpo.explicacao)
        except _ERROS_DE_DOMINIO as erro:
            raise _http(erro) from erro
        return {"nivel": int(dica.nivel), "texto": dica.texto, "origem": dica.origem, "motivo": dica.motivo}

    # No piloto não há Vite: a mesma porta serve o frontend construído (`npm run build`).
    # Montado por último, para que `/api` continue com as rotas acima.
    construido = raiz / "frontend" / "dist"
    if (construido / "index.html").is_file():
        app.mount("/", StaticFiles(directory=construido, html=True), name="frontend")

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
