"""Cliente do Serviço_de_Inferência_Local: disponibilidade e geração.

Toda chamada HTTP passa por ``ClienteOllama._transporte``, a costura única que a fixture
``ollama_proibido`` substitui pelo dublê (design §6.4). O endereço é fixo no laço local
(R24.8): nenhum dado de estudante sai da máquina.

shortcut: sem cache de disponibilidade, sem ``embutir`` e sem aquecimento na subida da API
(design §3.12); acrescentar quando o RAG entrar.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import httpx

MODELO_PADRAO = "llama3.2:1b"
"""Modelo de D14 (``docs/decisoes.md``)."""


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
            dados: dict[str, object] = resposta.json()
        except (httpx.HTTPError, ValueError) as erro:
            raise FalhaDeGeracao(str(erro)) from erro
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

    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        """Gera até 120 tokens, com tempo limite de 20 s (design §3.12)."""
        inicio = perf_counter()
        dados = self._transporte(
            "/api/generate",
            {
                "model": self.modelo,
                "system": sistema,
                "prompt": pedido,
                "stream": False,
                # num_gpu 0: o offload Vulkan na GPU integrada desta máquina derruba o
                # llama-server (0xc0000005); em CPU o modelo de 1B roda bem (D14).
                "options": {"num_predict": 120, "temperature": 0.3, "num_gpu": 0},
            },
            20.0,
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
