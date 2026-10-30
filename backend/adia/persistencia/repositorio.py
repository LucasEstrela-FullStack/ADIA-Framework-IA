"""Repositório SQLite: sessões e o registro append-only de eventos.

A sessão não é gravada como fotografia: ela é reconstruída reaplicando os eventos em
ordem (``Servico.obter``). Uma conexão por operação, porque a API atende rotas síncronas em
várias threads e o ``sqlite3`` não compartilha conexão entre threads; WAL deixa leitura e
escrita concorrentes.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from adia.nucleo.sessao.gestor import Sessao
from adia.tipos import Condicao, Etapa, Nivel


@dataclass(frozen=True)
class RegistroDeSessao:
    id: str
    condicao: Condicao
    semente: int


@dataclass(frozen=True)
class Evento:
    tipo: str
    item_id: str
    nivel: Nivel | None
    explicacao: str | None
    acerto: bool | None
    confianca: int | None


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _migracoes() -> list[tuple[int, str]]:
    pasta = files("adia.persistencia") / "migracoes"
    scripts = sorted((p for p in pasta.iterdir() if p.name.endswith(".sql")), key=lambda p: p.name)
    return [(int(p.name.split("_", 1)[0]), p.read_text(encoding="utf-8")) for p in scripts]


def _contexto(sessao: Sessao) -> tuple[str, int, str, int]:
    """Etapa, ciclo, item e teto no momento do evento, antes de a sessão avançar."""
    item = sessao.item_atual
    if item is None or not isinstance(sessao.etapa, Etapa):
        raise ValueError("evento sem item atual: a sessão está encerrada")
    return sessao.etapa.value, sessao.ciclo, item.id, int(sessao.teto)


class Repositorio:
    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        caminho.parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(caminho, timeout=5)
        try:
            conexao.execute("PRAGMA journal_mode = WAL")
            versao: int = conexao.execute("PRAGMA user_version").fetchone()[0]
            for numero, script in _migracoes():
                if numero > versao:
                    # executescript confirma o que estiver pendente; o BEGIN explícito faz
                    # a migração e o novo user_version entrarem juntos ou não entrarem.
                    conexao.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {numero};\nCOMMIT;")
        finally:
            conexao.close()

    @contextmanager
    def transacao(self) -> Iterator[sqlite3.Connection]:
        """Confirma ao sair sem erro; desfaz se o bloco levantar."""
        conexao = sqlite3.connect(self.caminho, timeout=5)
        try:
            conexao.execute("PRAGMA foreign_keys = ON")
            with conexao:
                yield conexao
        finally:
            conexao.close()

    def criar_sessao(self, registro: RegistroDeSessao) -> None:
        with self.transacao() as conexao:
            conexao.execute(
                "INSERT INTO sessao (id, condicao, semente, criada_em) VALUES (?, ?, ?, ?)",
                (registro.id, registro.condicao.value, registro.semente, _agora()),
            )

    def ler_sessao(self, sessao_id: str) -> tuple[RegistroDeSessao, list[Evento]] | None:
        with self.transacao() as conexao:
            linha = conexao.execute("SELECT condicao, semente FROM sessao WHERE id = ?", (sessao_id,)).fetchone()
            if linha is None:
                return None
            eventos = conexao.execute(
                "SELECT tipo, item_id, nivel, explicacao, acerto, confianca "
                "FROM evento WHERE sessao_id = ? ORDER BY id",
                (sessao_id,),
            ).fetchall()
        return RegistroDeSessao(sessao_id, Condicao(linha[0]), linha[1]), [
            Evento(
                tipo=e[0],
                item_id=e[1],
                nivel=None if e[2] is None else Nivel(e[2]),
                explicacao=e[3],
                acerto=None if e[4] is None else bool(e[4]),
                confianca=e[5],
            )
            for e in eventos
        ]

    @staticmethod
    def registrar_dica(
        conexao: sqlite3.Connection,
        sessao_id: str,
        sessao: Sessao,
        nivel: Nivel,
        explicacao: str,
        dica: tuple[str, str, str | None],
    ) -> None:
        """Grava a dica entregue: ``dica`` é (texto, origem, motivo)."""
        conexao.execute(
            "INSERT INTO evento (sessao_id, tipo, etapa, ciclo, item_id, teto, nivel, explicacao, "
            "texto_dica, origem, motivo, criado_em) VALUES (?, 'dica', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sessao_id, *_contexto(sessao), int(nivel), explicacao, *dica, _agora()),
        )

    @staticmethod
    def registrar_resposta(
        conexao: sqlite3.Connection,
        sessao_id: str,
        sessao: Sessao,
        resposta: str,
        acerto: bool | None,
        confianca: int,
    ) -> None:
        conexao.execute(
            "INSERT INTO evento (sessao_id, tipo, etapa, ciclo, item_id, teto, resposta, acerto, "
            "confianca, criado_em) VALUES (?, 'resposta', ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sessao_id,
                *_contexto(sessao),
                resposta,
                None if acerto is None else int(acerto),
                confianca,
                _agora(),
            ),
        )
