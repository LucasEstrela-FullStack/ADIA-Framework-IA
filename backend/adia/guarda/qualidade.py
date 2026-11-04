"""Filtro de qualidade da dica gerada: ela cumpre o que o nível pede? (DO-51)

Roda depois do veredito de vazamento e, como ele, falha fechada: a dica gerada fora do
padrão vira a dica pré-escrita do mesmo nível, que é revisada. As regras são de forma, não
de mérito pedagógico, para continuarem determinísticas:

- ``curta``: menos de ``PALAVRAS_MINIMAS`` palavras ("Isolar x.") não orienta ninguém;
- ``cortada``: sem pontuação final, a geração bateu no limite de tokens no meio da frase
  (acontece quando o modelo copia o trecho do material);
- ``sem_pergunta``: L1 é pergunta metacognitiva, e sem ``?`` virou ordem ou explicação;
- ``pergunta_fechada``: L1 terminado em ", certo?" ou ", né?", ou que começa por
  "você" ("Você já resolveu...?"), pede um sim, não faz pensar;
- ``cita_o_pedido``: "dica de referência" é rótulo do pedido ao modelo, que o estudante
  não conhece, e "Dica:" no início é o rótulo do campo, não parte da dica;
- ``operacao_no_conceito``: L2 nomeia o conceito, e verbo de operação no imperativo
  ("subtraia", "vamos dividir", "você deve somar") é passo de resolução, trabalho do L3;
- ``inverte_a_operacao``: mandar subtrair um número que o enunciado só subtrai (ou somar
  um que ele só soma) é a operação errada, e leva o estudante ao resultado errado;
- ``numero_fora_do_enunciado``: número que o enunciado não tem ("comece somando 20" em
  9m + 2 = 5m + 30) é conta feita pelo modelo ou número inventado, e as duas coisas confundem;
- ``escreve_conta``: sinal ``=`` na dica é equação ou conta escrita, que nenhum nível
  gerado pede, e as dicas pré-escritas não usam. A equação do próprio enunciado, citada
  pelo L2, não conta;
- ``repete_o_enunciado``: copiar um trecho do enunciado com número ("resolva a equação
  4(y - 2) = 28") não acrescenta nada ao que o estudante já tem na tela. Não vale no L2:
  nas revisões de 2026-11-03 e 2026-11-04, o L2 que cita a equação ao explicar o conceito
  servia, e os descartes indevidos eram quase todos dele.
"""

from __future__ import annotations

import re
from typing import Final

from adia.nucleo.itens.modelo import Item
from adia.tipos import Nivel

PALAVRAS_MINIMAS: Final = 5
"""Com 5, "Subtraia 2t dos dois lados." orienta e passa; "Isolar x." não."""
JANELA_DO_ENUNCIADO: Final = 5
"""Palavras seguidas do enunciado que, repetidas na dica, contam como cópia."""

_VERBOS: Final = r"(?:subtra|som|adicion|divid|multiplic|distribu|mov|isol|desfa)"
_OPERACAO: Final = re.compile(
    # Imperativo, "vamos + infinitivo" e 1ª do plural: passo de resolução. Infinitivo e
    # gerúndio soltos ficam de fora, porque a explicação de conceito também os usa.
    r"\b(?:subtraia|some|adicione|divida|multiplique|distribua|mova|isole"
    r"|subtraímos|somamos|adicionamos|desfazemos|dividimos|multiplicamos|distribuímos|movemos|isolamos)\b"
    rf"|\b(?:vamos|precisamos|devemos|você deve|você precisa|deve-se|precisa-se|você) {_VERBOS}\w*"
)
_EQUACAO: Final = re.compile(r"[\w()]+(?: [-+*/] [\w()]+)* = [\w()]+(?: [-+*/] [\w()]+)*")
_FECHADA: Final = re.compile(r",\s*(?:certo|né|não é|correto|ok)\s*\?|^você\b[^.:!?]*\?")
_POR_EXTENSO: Final = {
    "um": "1", "dois": "2", "três": "3", "quatro": "4", "cinco": "5",
    "seis": "6", "sete": "7", "oito": "8", "nove": "9", "dez": "10",
}
_MANDA: Final = re.compile(
    # Número com letra colada ("subtraia 2t") é termo com a incógnita, não constante.
    r"\b(subtraia|subtrair|subtraindo|subtraímos|some|somar|somando|somamos"
    r"|adicione|adicionar|adicionando|adicionamos) (\d+|" + "|".join(_POR_EXTENSO) + r")(?![\w])"
)


def _inverte_a_operacao(texto: str, enunciado: str) -> bool:
    for verbo, numero in _MANDA.findall(texto.lower()):
        numero = _POR_EXTENSO.get(numero, numero)
        somado = re.search(rf"\+\s*{numero}(?![\w])", enunciado)
        subtraido = re.search(rf"-\s*{numero}(?![\w])", enunciado)
        subtrai = verbo.startswith("subtra")
        if (subtrai and subtraido and not somado) or (not subtrai and somado and not subtraido):
            return True
    return False


def _palavras(texto: str) -> list[str]:
    return texto.lower().replace("?", " ").replace(".", " ").replace(",", " ").replace(":", " ").split()


def motivo_de_pobreza(texto: str, item: Item, nivel: Nivel) -> str | None:
    """Motivo pelo qual a dica gerada não serve ao nível, ou ``None`` se serve."""
    palavras = _palavras(texto)
    if len(palavras) < PALAVRAS_MINIMAS:
        return "curta"
    if texto.rstrip()[-1:] not in ('.', '?', '!', '"', ')', '»'):
        return "cortada"
    if nivel == Nivel.L1 and "?" not in texto:
        return "sem_pergunta"
    if nivel == Nivel.L1 and _FECHADA.search(texto.lower()):
        return "pergunta_fechada"
    if "referência" in texto.lower() or texto.lower().lstrip().startswith("dica:"):
        return "cita_o_pedido"
    if nivel == Nivel.L2 and _OPERACAO.search(texto.lower()):
        return "operacao_no_conceito"
    if _inverte_a_operacao(texto, item.enunciado):
        return "inverte_a_operacao"
    enunciado = _palavras(item.enunciado)
    corrida = " " + " ".join(palavras) + " "
    for inicio in range(len(enunciado) - JANELA_DO_ENUNCIADO + 1) if nivel != Nivel.L2 else ():
        janela = enunciado[inicio : inicio + JANELA_DO_ENUNCIADO]
        # Só conta cópia com número: o contexto em palavras ("o perímetro de um retângulo")
        # a dica pode retomar; a equação ou os dados do problema, não.
        if any(c.isdigit() for c in "".join(janela)) and " " + " ".join(janela) + " " in corrida:
            return "repete_o_enunciado"
    citada = texto
    for equacao in _EQUACAO.findall(item.enunciado):
        citada = citada.replace(equacao, "")
    if "=" in citada:
        return "escreve_conta"
    if set(re.findall(r"\d+", texto)) - set(re.findall(r"\d+", item.enunciado)):
        return "numero_fora_do_enunciado"
    return None
