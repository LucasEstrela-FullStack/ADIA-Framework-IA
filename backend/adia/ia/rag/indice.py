"""Índice do RAG: segmentação do corpus, embeddings ``bge-m3`` e busca exaustiva (DO-11, D13).

O índice mora num SQLite próprio, fora do banco de pesquisa: é derivado do corpus e se
reconstrói com ``adia indexar``, sem dado de estudante. A versão registra modelo, digest do
modelo e hash do corpus (R26.4); um índice cujo hash não bate com o corpus atual não é usado.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

from adia.ia.cliente_ollama import MODELO_DE_EMBEDDINGS, ClienteOllama

SUFIXO: Final = ".md"
MINIMO: Final = 400
MAXIMO: Final = 600
SOBREPOSICAO: Final = 80
LOTE: Final = 16
"""Trechos por pedido de embeddings: o lote limita a memória e o tempo de cada chamada."""

_ESQUEMA: Final = """
CREATE TABLE rag_indice (
    versao         TEXT PRIMARY KEY,
    modelo         TEXT NOT NULL,
    modelo_digest  TEXT,
    hash_corpus    TEXT NOT NULL,
    dimensoes      INTEGER NOT NULL,
    criado_em      TEXT NOT NULL
) STRICT;
CREATE TABLE rag_trecho (
    id       INTEGER PRIMARY KEY,
    arquivo  TEXT NOT NULL,
    texto    TEXT NOT NULL,
    vetor    BLOB NOT NULL
) STRICT;
"""


@dataclass(frozen=True)
class Trecho:
    id: int
    arquivo: str
    texto: str


@dataclass(frozen=True)
class Indice:
    versao: str
    trechos: tuple[Trecho, ...]
    vetores: npt.NDArray[np.float32]
    """Uma linha por trecho, normalizada em L2: o produto interno é o cosseno."""

    def consultar(self, vetor: Sequence[float], k: int) -> list[Trecho]:
        """Os ``k`` trechos mais próximos, do mais para o menos, por passagem exaustiva (D13)."""
        consulta = _normalizado(np.asarray([vetor], dtype=np.float32))[0]
        notas = self.vetores @ consulta
        return [self.trechos[i] for i in np.argsort(-notas, kind="stable")[:k]]


def arquivos_do_corpus(diretorio: Path) -> tuple[Path, ...]:
    if not diretorio.is_dir():
        return ()
    return tuple(sorted(p for p in diretorio.iterdir() if p.is_file() and p.name.endswith(SUFIXO)))


def hash_do_corpus(arquivos: Sequence[Path]) -> str:
    resumo = hashlib.sha256()
    for arquivo in arquivos:
        resumo.update(arquivo.name.encode("utf-8") + b"\0" + arquivo.read_bytes() + b"\0")
    return resumo.hexdigest()


def segmentar(texto: str) -> list[str]:
    """Trechos de 400 a 600 caracteres com 80 de sobreposição, cortados em fronteira de palavra.

    Prefere cortar no fim de frase dentro da faixa; sem fim de frase, no último espaço. O
    último trecho pode ser menor que 400 quando o texto acaba. O começo do trecho seguinte
    recua 80 caracteres e avança até o início de palavra, para não começar no meio de uma.
    """
    corrido = " ".join(texto.split())
    trechos: list[str] = []
    inicio = 0
    while inicio < len(corrido):
        fim = min(inicio + MAXIMO, len(corrido))
        if fim < len(corrido):
            janela = corrido[inicio + MINIMO : fim]
            ponto = max(janela.rfind(". "), janela.rfind("? "), janela.rfind("! "))
            espaco = janela.rfind(" ")
            corte = ponto + 1 if ponto >= 0 else espaco
            fim = inicio + MINIMO + corte if corte >= 0 else fim
        trechos.append(corrido[inicio:fim].strip())
        if fim >= len(corrido):
            break
        proximo = fim - SOBREPOSICAO
        espaco = corrido.find(" ", proximo)
        inicio = espaco + 1 if 0 <= espaco < fim else fim
    return trechos


def _normalizado(matriz: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    return (matriz / np.where(normas == 0, 1, normas)).astype(np.float32)


def construir(arquivos: Sequence[Path], destino: Path, cliente: ClienteOllama) -> Indice:
    """Segmenta, pede os embeddings e grava o índice inteiro de uma vez (troca atômica do arquivo)."""
    trechos = [
        Trecho(0, arquivo.name, texto)
        for arquivo in arquivos
        for texto in segmentar(arquivo.read_text(encoding="utf-8"))
    ]
    trechos = [Trecho(i, t.arquivo, t.texto) for i, t in enumerate(trechos, start=1)]
    if not trechos:
        raise ValueError("corpus vazio: nada a indexar")
    vetores: list[list[float]] = []
    for i in range(0, len(trechos), LOTE):
        vetores.extend(cliente.embutir([t.texto for t in trechos[i : i + LOTE]]))
    matriz = _normalizado(np.asarray(vetores, dtype=np.float32))
    hash_corpus = hash_do_corpus(arquivos)
    digest = cliente.digest(MODELO_DE_EMBEDDINGS)
    versao = f"{MODELO_DE_EMBEDDINGS}@{(digest or 'desconhecido').removeprefix('sha256:')[:12]}:{hash_corpus[:12]}"

    destino.parent.mkdir(parents=True, exist_ok=True)
    provisorio = destino.with_suffix(".tmp")
    provisorio.unlink(missing_ok=True)
    conexao = sqlite3.connect(provisorio)
    try:
        with conexao:
            conexao.executescript(_ESQUEMA)
            conexao.execute(
                "INSERT INTO rag_indice VALUES (?, ?, ?, ?, ?, ?)",
                (
                    versao,
                    MODELO_DE_EMBEDDINGS,
                    digest,
                    hash_corpus,
                    matriz.shape[1],
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )
            conexao.executemany(
                "INSERT INTO rag_trecho VALUES (?, ?, ?, ?)",
                [(t.id, t.arquivo, t.texto, matriz[n].astype("<f4").tobytes()) for n, t in enumerate(trechos)],
            )
    finally:
        conexao.close()
    os.replace(provisorio, destino)
    return Indice(versao, tuple(trechos), matriz)


def abrir(destino: Path, arquivos: Sequence[Path]) -> Indice | None:
    """O índice gravado, ou ``None`` quando não existe ou foi feito de outro corpus."""
    if not destino.is_file():
        return None
    conexao = sqlite3.connect(f"file:{destino.as_posix()}?mode=ro", uri=True)
    try:
        meta = conexao.execute("SELECT versao, hash_corpus, dimensoes FROM rag_indice").fetchone()
        linhas = conexao.execute("SELECT id, arquivo, texto, vetor FROM rag_trecho ORDER BY id").fetchall()
    finally:
        conexao.close()
    if meta is None or meta[1] != hash_do_corpus(arquivos) or not linhas:
        return None
    vetores = np.stack([np.frombuffer(linha[3], dtype="<f4") for linha in linhas]).astype(np.float32)
    if vetores.shape[1] != meta[2]:
        return None
    return Indice(str(meta[0]), tuple(Trecho(int(i), str(a), str(t)) for i, a, t, _ in linhas), vetores)
