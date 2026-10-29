"""Forma de comparação dos conjuntos declarados de vazamento, compartilhada por dois deles.

Este módulo é **auxiliar de teste**, não produção: ele não tem o prefixo `test_` e não é
coletado pelo pytest, como `tipos_fronteira.py` e `tipos_medida.py` ao lado, e é importado
como módulo de topo — `from vazamento import ocorre_como_token` — do mesmo jeito que
`propriedades/estrategias.py` é importado pelos arquivos de propriedade, porque o pytest
insere o diretório do teste em `sys.path` e não há `__init__.py` em diretório de teste algum.

**Por que existe, em vez de uma cópia em cada arquivo.** Dois conjuntos declarados fazem a
mesma pergunta — este texto reproduz uma resposta que o estudante deveria produzir? —, sobre
conteúdos diferentes: `test_banco_inicial_de_itens.py` varre as dicas pré-escritas de cada
item contra o gabarito do item (R7.11), e `test_cenario_steam_inicial.py` varre o enunciado
do cenário STEAM e o texto da rubrica contra o gabarito de cada parte numérica (R13.2). Duas
cópias da regra de comparação seriam dois lugares para errar: fortalecer uma e esquecer a
outra deixaria metade do conteúdo varrido por um critério mais fraco, e nada ficaria vermelho.

**O que este módulo não é.** A detecção completa de R7.2 — separador decimal e de milhar,
unidade declarada, numeral em palavras, equivalência algébrica dentro da tolerância e
expressão aritmética cujo resultado é o gabarito (R7.9) — é da `Guarda_de_Vazamento`, que é
código de produção de tarefa posterior. Aqui está apenas a forma **literal**, que é a
primeira das várias, e é o que o conteúdo versionado precisa cumprir no portão.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["normalizar", "ocorre_como_token", "sem_acento"]


def sem_acento(texto: str) -> str:
    """Texto decomposto e sem marcas combinantes: `três` e `tres` passam a ser a mesma cadeia."""
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(caractere for caractere in decomposto if not unicodedata.combining(caractere))


def normalizar(texto: str) -> str:
    """Forma de comparação: insensível a caixa **e** a acentuação.

    As duas insensibilidades são a escolha deliberadamente mais forte, e cada uma fecha um
    vazamento real: `Quatro` no começo de frase, e `três` digitado sem acento. O preço é
    aceitar falso positivo — um texto legítimo que contenha a palavra do gabarito por outra
    razão reprova —, e é o preço certo: aqui o falso positivo custa reescrever uma frase, e o
    falso negativo custa entregar a resposta ao estudante.
    """
    return sem_acento(texto).casefold()


def ocorre_como_token(texto: str, alvo: str) -> bool:
    """Se o alvo aparece no texto delimitado, isto é, sem letra nem dígito em volta.

    A delimitação é o que separa vazamento de coincidência de dígito: com gabarito `4`, a
    forma `x = 4` e a forma `4,0` reprovam, e `14` não. Sem ela, qualquer número que contivesse
    o dígito do gabarito reprovaria, o que tornaria o conjunto declarado inútil por excesso.

    A contrapartida vale ser dita, porque ela dirige a escrita do conteúdo: a varredura só
    cobre a cadeia **inteira** que lhe é dada. Um numeral de mais de uma palavra, como
    `seiscentos e vinte`, só reprova se o texto trouxer a expressão completa; e é por isso que
    o conteúdo declara o numeral em palavras entre as formas aceitas em vez de confiar em que
    ninguém o escreva.
    """
    agulha = normalizar(alvo)
    if not agulha:
        return False
    return re.search(rf"(?<![0-9a-z]){re.escape(agulha)}(?![0-9a-z])", normalizar(texto)) is not None
