"""Filtro de qualidade da dica gerada: ela cumpre o que o nível pede? (DO-51)

Roda depois do veredito de vazamento e, como ele, falha fechada: a dica gerada fora do
padrão vira a dica pré-escrita do mesmo nível, que é revisada. As regras são de forma, não
de mérito pedagógico, para continuarem determinísticas:

- ``curta``: menos de ``PALAVRAS_MINIMAS`` palavras ("Isolar x.") não orienta ninguém;
- ``sem_pergunta``: L1 é pergunta metacognitiva, e sem ``?`` virou ordem ou explicação;
- ``operacao_no_conceito``: L2 nomeia o conceito, e verbo de operação no imperativo
  ("subtraia", "vamos dividir", "você deve somar") é passo de resolução, trabalho do L3;
- ``escreve_conta``: sinal ``=`` na dica é equação ou conta escrita, que nenhum nível
  gerado pede, e as dicas pré-escritas não usam;
- ``repete_o_enunciado``: copiar um trecho do enunciado com número ("resolva a equação
  4(y - 2) = 28") não acrescenta nada ao que o estudante já tem na tela.
"""

from __future__ import annotations

import re
from typing import Final

from adia.nucleo.itens.modelo import Item
from adia.tipos import Nivel

PALAVRAS_MINIMAS: Final = 6
JANELA_DO_ENUNCIADO: Final = 5
"""Palavras seguidas do enunciado que, repetidas na dica, contam como cópia."""

_VERBOS: Final = r"(?:subtra|som|adicion|divid|multiplic|distribu|mov|isol)"
_OPERACAO: Final = re.compile(
    # Imperativo, "vamos + infinitivo" e 1ª do plural: passo de resolução. Infinitivo e
    # gerúndio soltos ficam de fora, porque a explicação de conceito também os usa.
    r"\b(?:subtraia|some|adicione|divida|multiplique|distribua|mova|isole"
    r"|subtraímos|somamos|adicionamos|dividimos|multiplicamos|distribuímos|movemos|isolamos)\b"
    rf"|\b(?:vamos|você deve|você precisa|deve-se|precisa-se) {_VERBOS}\w*"
)


def _palavras(texto: str) -> list[str]:
    return texto.lower().replace("?", " ").replace(".", " ").replace(",", " ").replace(":", " ").split()


def motivo_de_pobreza(texto: str, item: Item, nivel: Nivel) -> str | None:
    """Motivo pelo qual a dica gerada não serve ao nível, ou ``None`` se serve."""
    palavras = _palavras(texto)
    if len(palavras) < PALAVRAS_MINIMAS:
        return "curta"
    if nivel == Nivel.L1 and "?" not in texto:
        return "sem_pergunta"
    if nivel == Nivel.L2 and _OPERACAO.search(texto.lower()):
        return "operacao_no_conceito"
    enunciado = _palavras(item.enunciado)
    corrida = " " + " ".join(palavras) + " "
    for inicio in range(len(enunciado) - JANELA_DO_ENUNCIADO + 1):
        janela = enunciado[inicio : inicio + JANELA_DO_ENUNCIADO]
        # Só conta cópia com número: o contexto em palavras ("o perímetro de um retângulo")
        # a dica pode retomar; a equação ou os dados do problema, não.
        if any(c.isdigit() for c in "".join(janela)) and " " + " ".join(janela) + " " in corrida:
            return "repete_o_enunciado"
    if "=" in texto:
        return "escreve_conta"
    return None
