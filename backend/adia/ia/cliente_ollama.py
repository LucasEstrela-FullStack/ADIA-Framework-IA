"""Cliente do Serviço_de_Inferência_Local: disponibilidade, geração e embeddings.

Toda chamada HTTP passa por ``ClienteOllama._transporte``, a costura única que a fixture
``ollama_proibido`` substitui pelo dublê (design §6.4). O endereço é fixo no laço local
(R24.8): nenhum dado de estudante sai da máquina.

shortcut: sem o cache de 5 s da disponibilidade (DO-09) e sem aquecimento na subida da API
(design §3.12); acrescentar quando a latência da primeira dica aparecer no piloto.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import httpx

MODELO_PADRAO = "qwen2.5:3b"
"""Modelo de D14 (``docs/decisoes.md``), trocado pelo benchmark de 2026-11-04. O recuo é o
``qwen2.5:1.5b``, quando o p95 na máquina do piloto passa de 20 s (``docs/piloto.md``)."""

TEMPO_LIMITE_DA_GERACAO = 30.0
"""Segundos. Com 20 s, 4 de 62 gerações do 3b estouravam; ao estourar, vem a pré-escrita."""

MODELO_DE_EMBEDDINGS = "bge-m3"
"""Modelo de embeddings do RAG (DO-11)."""


@dataclass(frozen=True)
class RespostaDoModelo:
    """Saída bruta do serviço de inferência, do lado probabilístico da fronteira.

    Que esta classe **não** seja aceita por ``adia.nucleo.regulacao.regra.decidir`` é o que
    a camada 2 afirma. Dar a ela qualquer compatibilidade com ``EntradaDeRegulacao`` — por
    herança, por protocolo estrutural ou por alias — reprova o ``mypy``, e é essa a
    intenção: a travessia não deve ser escrevível.
    """

    texto: str
    tokens: int
    latencia_ms: int
    modelo: str


class FalhaDeGeracao(Exception):
    """O serviço não respondeu, respondeu com erro ou estourou o tempo limite."""


class ClienteOllama:
    """Única porta de saída para o serviço de inferência local (§3.12)."""

    BASE = "http://127.0.0.1:11434"
    """Endereço do serviço local. A porta 11434 é a que a camada 3 proíbe por destino."""

    def __init__(self, modelo: str = MODELO_PADRAO) -> None:
        self.modelo = modelo

    def _transporte(self, caminho: str, corpo: dict[str, object] | None, tempo_limite: float) -> dict[str, object]:
        """Emite o pedido HTTP ao serviço local e devolve a resposta decodificada."""
        try:
            if corpo is None:
                resposta = httpx.get(self.BASE + caminho, timeout=tempo_limite)
            else:
                resposta = httpx.post(self.BASE + caminho, json=corpo, timeout=tempo_limite)
            resposta.raise_for_status()
            dados: object = resposta.json()
        except (httpx.HTTPError, ValueError) as erro:
            raise FalhaDeGeracao(str(erro)) from erro
        if not isinstance(dados, dict):
            raise FalhaDeGeracao("resposta do serviço não é um objeto JSON")
        return dados

    def disponivel(self) -> bool:
        """Se o serviço responde e tem o modelo configurado instalado."""
        try:
            dados = self._transporte("/api/tags", None, 1.0)
        except FalhaDeGeracao:
            return False
        modelos = dados.get("models")
        if not isinstance(modelos, list):
            return False
        return any(isinstance(m, dict) and m.get("name") == self.modelo for m in modelos)

    def modelos_instalados(self) -> dict[str, int]:
        """Modelos do serviço local com o tamanho em disco, em bytes (R20.2, R24.6)."""
        modelos = self._transporte("/api/tags", None, 1.0).get("models")
        if not isinstance(modelos, list):
            raise FalhaDeGeracao("resposta inesperada de /api/tags")
        return {
            str(m["name"]): int(m["size"])
            for m in modelos
            if isinstance(m, dict) and "name" in m and isinstance(m.get("size"), int)
        }

    def digest(self, modelo: str) -> str | None:
        """Identificador da versão instalada do modelo, para a proveniência do índice (R26.4)."""
        modelos = self._transporte("/api/tags", None, 1.0).get("models")
        if not isinstance(modelos, list):
            raise FalhaDeGeracao("resposta inesperada de /api/tags")
        for m in modelos:
            if isinstance(m, dict) and m.get("name") in {modelo, f"{modelo}:latest"}:
                digest = m.get("digest")
                return digest if isinstance(digest, str) else None
        return None

    def embutir(self, textos: list[str], modelo: str = MODELO_DE_EMBEDDINGS) -> list[list[float]]:
        """Um vetor por texto, na ordem, por ``POST /api/embed`` (DO-11)."""
        dados = self._transporte("/api/embed", {"model": modelo, "input": textos, "options": {"num_gpu": 0}}, 120.0)
        vetores = dados.get("embeddings")
        if (
            not isinstance(vetores, list)
            or len(vetores) != len(textos)
            or not all(isinstance(v, list) and v and all(isinstance(x, int | float) for x in v) for v in vetores)
        ):
            raise FalhaDeGeracao("resposta inesperada de /api/embed")
        return [[float(x) for x in v] for v in vetores]

    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        """Gera até 120 tokens, com tempo limite de ``TEMPO_LIMITE_DA_GERACAO`` (design §3.12)."""
        inicio = perf_counter()
        dados = self._transporte(
            "/api/generate",
            {
                "model": self.modelo,
                "system": sistema,
                "prompt": pedido,
                "stream": False,
                # num_gpu 0: o offload Vulkan na GPU integrada desta máquina derruba o
                # llama-server (0xc0000005); em CPU o 3B responde em ~10 s e o 1,5B em ~3 s (D14).
                "options": {"num_predict": 120, "temperature": 0.3, "num_gpu": 0},
            },
            TEMPO_LIMITE_DA_GERACAO,
        )
        texto = dados.get("response")
        if not isinstance(texto, str) or not texto.strip():
            raise FalhaDeGeracao("resposta vazia do modelo")
        tokens = dados.get("eval_count")
        return RespostaDoModelo(
            texto=texto.strip(),
            tokens=tokens if isinstance(tokens, int) else 0,
            latencia_ms=int((perf_counter() - inicio) * 1000),
            modelo=self.modelo,
        )
