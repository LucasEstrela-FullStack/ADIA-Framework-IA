"""Benchmark curto dos modelos candidatos (R20): latência, falha, vazamento e amostras.

Mede o que dá para medir sem juiz humano e entrega o resto para leitura: as métricas saem
em tabela, e uma amostra das dicas de cada modelo vai junto para que o pesquisador julgue
português, pertinência e respeito ao nível. A escolha do modelo é do pesquisador; este
módulo só produz a evidência.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date

from adia.guarda.veredito import forma_do_vazamento
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao
from adia.ia.subagentes.papeis import PAPEIS, pedido
from adia.nucleo.itens.modelo import Item
from adia.tipos import Nivel

CANDIDATOS_PADRAO = ("llama3.2:1b", "qwen2.5:1.5b", "gemma3:1b")
AMOSTRAS_NO_RELATORIO = 3
"""Itens por modelo cujas dicas L1 a L3 saem por extenso no relatório."""


@dataclass(frozen=True)
class Geracao:
    item_id: str
    nivel: Nivel
    texto: str | None
    latencia_ms: int | None
    vazamento: str | None
    falha: str | None


@dataclass
class ResultadoDoModelo:
    modelo: str
    tamanho_bytes: int | None
    geracoes: list[Geracao] = field(default_factory=list)

    def _latencias(self) -> list[int]:
        return [g.latencia_ms for g in self.geracoes if g.latencia_ms is not None]

    @property
    def mediana_ms(self) -> float | None:
        latencias = self._latencias()
        return statistics.median(latencias) if latencias else None

    @property
    def p95_ms(self) -> float | None:
        latencias = sorted(self._latencias())
        return latencias[min(len(latencias) - 1, round(0.95 * (len(latencias) - 1)))] if latencias else None

    @property
    def falhas(self) -> int:
        return sum(g.falha is not None for g in self.geracoes)

    @property
    def vazamentos(self) -> int:
        return sum(g.vazamento is not None for g in self.geracoes)


def medir(
    cliente_de: Callable[[str], ClienteOllama],
    modelos: Sequence[str],
    itens: Sequence[Item],
    progresso: Callable[[str], None] = lambda _: None,
) -> list[ResultadoDoModelo]:
    """Gera L1 a L3 para cada item com cada modelo. Um aquecimento por modelo fica fora da medida."""
    resultados: list[ResultadoDoModelo] = []
    for modelo in modelos:
        cliente = cliente_de(modelo)
        try:
            tamanho = cliente.modelos_instalados().get(modelo)
        except FalhaDeGeracao:
            tamanho = None
        resultado = ResultadoDoModelo(modelo, tamanho)
        resultados.append(resultado)
        try:
            cliente.gerar("Responda em uma palavra.", "Diga oi.")  # carrega o modelo na memória
        except FalhaDeGeracao as erro:
            progresso(f"{modelo}: indisponível ({erro})")
            continue
        for item in itens:
            for nivel, papel in PAPEIS.items():
                try:
                    resposta = cliente.gerar(papel, pedido(item.enunciado, item.dicas[nivel], ""))
                except FalhaDeGeracao as erro:
                    resultado.geracoes.append(Geracao(item.id, nivel, None, None, None, str(erro)))
                    continue
                resultado.geracoes.append(
                    Geracao(
                        item.id,
                        nivel,
                        resposta.texto,
                        resposta.latencia_ms,
                        forma_do_vazamento(resposta.texto, item),
                        None,
                    )
                )
            progresso(f"{modelo}: {item.id} pronto")
    return resultados


def _ms(valor: float | None) -> str:
    return "—" if valor is None else f"{valor / 1000:.1f} s"


def relatorio(resultados: Sequence[ResultadoDoModelo], data: str) -> str:
    """Relatório em Markdown para `docs/relatorios/`."""
    linhas = [
        f"# Benchmark de modelos — {data}",
        "",
        "Dicas L1 a L3 para os itens praticados, geradas com os mesmos papéis e opções da API "
        "(CPU, `num_gpu: 0`, até 120 tokens). L4 não entra: é sempre o exemplo pré-escrito.",
        "",
        "| Modelo | Disco | Gerações | Falhas | Vazamentos pegos pela guarda | Mediana | p95 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in resultados:
        disco = "—" if r.tamanho_bytes is None else f"{r.tamanho_bytes / 1e9:.2f} GB"
        linhas.append(
            f"| `{r.modelo}` | {disco} | {len(r.geracoes)} | {r.falhas} | {r.vazamentos} | "
            f"{_ms(r.mediana_ms)} | {_ms(r.p95_ms)} |"
        )
    linhas += [
        "",
        "Vazamento pego pela guarda não chega ao estudante (vira dica pré-escrita), mas cada um "
        "é uma dica gerada perdida. O que a tabela não mede, e a amostra abaixo serve para "
        "julgar: português correto, pertinência ao problema e respeito ao nível pedido.",
    ]
    for r in resultados:
        linhas += ["", f"## Amostra: `{r.modelo}`", ""]
        itens_vistos: list[str] = []
        for g in r.geracoes:
            if g.item_id not in itens_vistos:
                if len(itens_vistos) == AMOSTRAS_NO_RELATORIO:
                    break
                itens_vistos.append(g.item_id)
            marca = f" — **guarda: {g.vazamento}**" if g.vazamento else ""
            texto = " ".join((g.texto or f"(falha: {g.falha})").split())
            linhas.append(f"- `{g.item_id}` {g.nivel.name}{marca}: {texto}")
    return "\n".join(linhas) + "\n"


def hoje() -> str:
    return date.today().isoformat()
