"""Sub-agentes: papéis do mesmo modelo, um por nível de ajuda (README, *Níveis de ajuda*).

O roteamento é por nível: a regra de regulação decide o nível e cada nível tem um papel.
L4 (exemplo resolvido) não chama o modelo: o exemplo pré-escrito do item já é análogo e
revisado, e um exemplo gerado é o caminho mais curto para vazar a resposta.

shortcut: sem o classificador TF-IDF do roteador (design §3.8) e sem RAG; a dica
pré-escrita do item entra no pedido como material de apoio no lugar do trecho recuperado.
"""

from __future__ import annotations

from adia.tipos import Nivel

_BASE = (
    "Você é um tutor de matemática para estudantes brasileiros. Responda em português do "
    "Brasil, em no máximo duas frases curtas, falando diretamente com o estudante. "
    "Nunca calcule nem informe o valor final da incógnita, nem o resultado do problema."
)

PAPEIS: dict[Nivel, str] = {
    Nivel.L1: _BASE
    + " Papel metacognitivo: faça UMA pergunta que leve o estudante a pensar no que já sabe "
    "e no que o problema pede. Não explique conceitos nem passos.",
    Nivel.L2: _BASE
    + " Papel conceitual: explique o conceito matemático envolvido, sem dizer qual operação "
    "fazer primeiro.",
    Nivel.L3: _BASE
    + " Papel procedural: indique apenas o primeiro passo da resolução, sem executá-lo.",
}


def pedido(enunciado: str, apoio: str, explicacao: str) -> str:
    """Texto enviado ao modelo para o problema, com o material de apoio do nível."""
    partes = [f"Problema: {enunciado}", f"Material de apoio (não copie literalmente): {apoio}"]
    if explicacao.strip():
        partes.append(f"O estudante explicou o que já tentou: {explicacao.strip()}")
    partes.append("Escreva a dica.")
    return "\n".join(partes)
