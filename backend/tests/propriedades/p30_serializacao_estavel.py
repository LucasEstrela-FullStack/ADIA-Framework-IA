"""Propriedade 30: o texto canônico de um banco de itens é estável byte a byte.

`p29_item_ida_e_volta.py` é o arquivo que fixou a forma dos arquivos de propriedade — um
arquivo, uma propriedade, um teste; etiqueta na primeira linha do corpo; orçamento de exemplos
vindo do perfil de `backend/tests/conftest.py`; geradores nomeados de `estrategias.py`;
`tempfile` em vez da fixture `tmp_path` e gravação em **bytes**. Este arquivo segue aquela forma
sem a repetir: o que está documentado abaixo é só o que é de P30.

## O que esta propriedade acrescenta

Os casos **dirigidos** de `backend/tests/unidade/test_serializador_canonico.py` já verificam a
mesma estabilidade com o texto esperado escrito à mão, as quinze classes de texto adversário
parametrizadas e uma tabela de doze decimais. É lá que mora a verificação da *forma* do texto, e
uma propriedade de estabilidade não a alcança: forma errada e estável passa nas duas
serializações. O que é novo aqui é a **ordem de construção** sobre entrada gerada no domínio
inteiro de `itens_carregaveis`, em banco de mais de um item, com `id` sorteado — e, dentro disso,
a ordem de inserção do catálogo de dicas, que **nenhum** caso dirigido embaralha: todos eles
constroem o catálogo em L1 a L4, que é justamente a ordem canônica.

P29 não alcança esse caso, e a razão vale registrar porque é a diferença entre as duas
propriedades. P29 compara **estrutura**, e a ordem de inserção de `dicas` é invisível para
`Item.__eq__`: `Mapping` compara por par chave-valor, não por ordem. Um escritor que emitisse a
subtabela de dicas na ordem de inserção — o que um escritor TOML genérico faz — produziria texto
diferente nas duas passadas e deixaria P29 **verde**, porque as duas cargas devolvem o catálogo
em ordem de `Nivel` de todo modo. É um defeito que só o texto vê, e verificá-lo é o que esta
propriedade existe para fazer.

## As três ordens que a construção decide

`Item` é `dataclass` congelada, logo a ordem dos **campos** não é escolha de quem constrói: não
existe ordem de inserção para embaralhar ali, e a ordem do arquivo é a de
`ORDEM_CANONICA_DE_ITEM`. A ênfase de §5.5 em "chaves em ordem embaralhada na construção" tem,
portanto, exatamente três realizações possíveis, e as três são construídas aqui:

- o **catálogo de dicas**, cuja ordem de inserção sobrevive no `Mapping` do item;
- a **sequência de itens** entregue ao serializador, que não é a ordem dos blocos no arquivo
  (ordenados por `id`, R3.6) nem a ordem em que a carga os devolve;
- a **ordem interna das coleções** — `sinonimos_unidade`, `variacoes_gabarito` e
  `termos_essenciais`, este nos dois níveis. `etapas_permitidas` fica fora por não ter ordem a
  embaralhar: é `frozenset`.

O embaralhamento é feito aqui, e não em `estrategias.py`, por decisão daquele módulo: ele produz
coleção já na forma canônica de propósito, porque a leitura devolve `tuple(sorted(...))` e uma
coleção gerada fora de ordem faria a comparação estrutural de P29 falhar sem que nada estivesse
errado no serializador. Quem precisa da ordem arbitrária embaralha onde a intenção fica visível.

Cada exemplo serializa o banco nas **duas** construções, canônica e embaralhada, porque é o par
separa os dois diagnósticos de uma P30 vermelha: texto do embaralhado diferente do texto do
canônico aponta para uma ordem que vazou da construção para o arquivo; textos iguais e segunda
serialização diferente aponta para a leitura.

## Por que os bytes do arquivo, e não a cadeia em memória

O enunciado pede igualdade "byte a byte, em UTF-8 sem BOM e com fim de linha `LF`", e as três
exigências são sobre o **arquivo** — é ele que vai a revisão humana e a `git` (R3, R3.3). Por
isso a comparação é contra os bytes lidos de volta do disco, e não contra a cadeia reencodificada:
`texto.encode("utf-8")` nunca produziria BOM nem `CRLF`, de modo que afirmar os dois sobre a
cadeia seria afirmar algo sobre a biblioteca padrão, não sobre o arquivo. A ausência de qualquer
`\\r` é mais forte do que a ausência de `CRLF`, e é deliberada: ela também pega o retorno de carro
**literal** vindo de `FRAGMENTOS_ADVERSARIOS`, que precisa sair escapado — literal no arquivo, ele
seria apagado pela normalização de `\\r\\n` da leitura, e o valor voltaria sem ele.

## O limite que a propriedade não alcança

Relações ficam fora, pela mesma decisão de escopo de P29: a geração que §5.5 pede é de itens, e
item praticado — o que exige relação, por R2.2 e R2.6 — está fora de `itens_carregaveis` por
construção. A ordenação das relações pela tripla é afirmada no caso dirigido.

O arquivo de entrada é sempre escrito por `serializar_canonico`, logo o texto que a carga lê já
está canônico; arquivo válido fora da forma canônica é de
`test_canonizar_reescreve_arquivo_fora_da_forma_canonica`. E a quarta construção que daria o mesmo
conteúdo com texto diferente — `Decimal("0.050")` no lugar de `Decimal("0.05")`, que `Item.__eq__`
também não distingue — fica onde já está verificada: na tabela de doze decimais de
`decimal_canonico` e no caso dirigido que canoniza `tolerancia = "0.050"`.

**Validates: Requirements 3.5**
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Final

import pytest
from estrategias import bancos, identificador_de
from hypothesis import find, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import DrawFn

from adia.nucleo.itens.carregador import (
    SUFIXO_DE_ARQUIVO,
    CargaConcluida,
    ResultadoDeCarga,
    carregar,
    serializar_canonico,
)
from adia.nucleo.itens.erros import ErroDeCarga
from adia.nucleo.itens.modelo import Item
from adia.tipos import Nivel

MAXIMO_DE_ITENS: Final = 3
"""Teto de itens por banco gerado.

Três, e não um, porque a ordem dos blocos é uma das três ordens que a construção decide: com um
item só, nada distinguiria "escreve por `id`" de "escreve na ordem recebida". Dois já dariam o
caso, em metade dos exemplos; o terceiro é o que torna a permutação não trivial na maioria deles
— cinco das seis permutações de três itens não são a identidade, contra uma das duas.

Pequeno porque cada exemplo custa três serializações do banco inteiro, mais uma gravação e uma
carga, e cada item acrescenta um bloco a cada uma delas. Nenhuma invariante nova aparece no
quarto item: a união entre arquivos, que é o que pede banco maior, é de P29.
"""

BOM_DE_UTF8: Final = b"\xef\xbb\xbf"
"""Marca de ordem de byte, que R3.3 proíbe no arquivo de definição."""

RETORNO_DE_CARRO: Final = b"\r"
"""Byte do `CR`. Sua ausência é a forma forte de "fim de linha `LF`": sem `CR` não há `CRLF`,
e o retorno de carro de `FRAGMENTOS_ADVERSARIOS` precisa sair escapado, não literal."""


# --------------------------------------------------------------------------- #
# Geração: o mesmo banco em duas construções
#
# Convenção herdada de P29: o que é candidato a migrar para `estrategias.py` no dia em que uma
# segunda propriedade precisar fica público; o encanamento do teste fica privado. O
# embaralhamento é público porque é a ênfase de §5.5 que esta propriedade constrói; a gravação e
# o desembrulho da carga são encanamento, e repetem os de P29 de propósito — `estrategias.py` é
# módulo de geradores, e acolher E/S nele apagaria o que o nome dele promete.
# --------------------------------------------------------------------------- #


@dataclasses.dataclass(frozen=True)
class ParDeConstrucoes:
    """O mesmo banco construído de duas formas: na ordem canônica e fora dela.

    "O mesmo" é afirmação de **conteúdo**, e a estrutura a expressa de forma desigual: coleção
    permutada torna as duas tuplas diferentes para `==`, e catálogo de dicas permutado **não**,
    porque `Mapping` não compara ordem. É essa assimetria que faz do par a entrada certa — a
    diferença existe no arquivo mesmo onde não existe na estrutura.
    """

    canonica: tuple[Item, ...]
    embaralhada: tuple[Item, ...]


def catalogo_na_ordem(niveis: Sequence[Nivel], dicas: Mapping[Nivel, str]) -> Mapping[Nivel, str]:
    """Catálogo com os mesmos quatro pares, inserido na ordem dada.

    Nomeada em vez de `lambda` pelo motivo de §6.3, e imutável como o catálogo que o carregador
    publica. `niveis` é a permutação sorteada: é ela, e só ela, que distingue este catálogo do
    que o item trazia — `Mapping` não compara ordem, então a diferença não existe para `==`.
    """
    return MappingProxyType({nivel: dicas[nivel] for nivel in niveis})


@st.composite
def construcoes_embaralhadas(draw: DrawFn, item: Item) -> Item:
    """O mesmo item com as coleções e o catálogo de dicas fora da ordem canônica.

    `st.permutations` em vez de um gerador novo de coleção, porque o que varia tem de ser a
    **ordem** e nada mais: um segundo sorteio produziria outro conteúdo, e aí o texto poderia
    sair diferente com razão. E porque a permutação encolhe **para** a ordem recebida, que é a
    canônica: o contraexemplo mínimo embaralha só o que precisa para falhar, e o que não é parte
    do defeito chega na ordem canônica, onde se lê.

    `dataclasses.replace` constrói um `Item` novo pelo `__init__`, logo `__post_init__` revalida:
    coleção fora de ordem não é item inválido (a leitura é que a canoniza), e um dia em que isso
    mudar, muda aqui, alto.
    """
    grupos = [tuple(draw(st.permutations(conjunto))) for conjunto in item.termos_essenciais]
    return dataclasses.replace(
        item,
        sinonimos_unidade=tuple(draw(st.permutations(item.sinonimos_unidade))),
        variacoes_gabarito=tuple(draw(st.permutations(item.variacoes_gabarito))),
        termos_essenciais=tuple(draw(st.permutations(grupos))),
        dicas=catalogo_na_ordem(draw(st.permutations(list(Nivel))), item.dicas),
    )


@st.composite
def pares_de_construcao(draw: DrawFn) -> ParDeConstrucoes:
    """Banco de itens carregáveis, na construção canônica e na embaralhada.

    A permutação da **sequência** é sorteada depois do embaralhamento de cada item, e separada
    dele, porque são duas ordens distintas: a de dentro do bloco e a dos blocos. Uma só delas
    embaralhada deixaria metade da ênfase sem exemplo.
    """
    canonica = draw(bancos(maximo=MAXIMO_DE_ITENS))
    embaralhados = [draw(construcoes_embaralhadas(item)) for item in canonica]
    return ParDeConstrucoes(canonica=canonica, embaralhada=tuple(draw(st.permutations(embaralhados))))


def _gravar(diretorio: Path, nome: str, texto: str) -> Path:
    """Grava o texto em UTF-8 sem BOM, em bytes, sem tradução de fim de linha (R3.3)."""
    caminho = diretorio / nome
    caminho.write_bytes(texto.encode("utf-8"))
    return caminho


def _banco(resultado: ResultadoDeCarga) -> CargaConcluida:
    """Desembrulha a carga, falhando com a mensagem da rejeição quando houver.

    A mensagem separa os dois diagnósticos de uma falha na carga: ela aponta para o gerador ou
    para a gramática, nunca para a estabilidade do texto, que é o que esta propriedade afirma.
    """
    if isinstance(resultado, ErroDeCarga):
        pytest.fail(f"a carga devia ter concluído: {resultado.mensagem}")
    return resultado


@given(pares_de_construcao())
@settings(deadline=None)
def test_a_serializacao_canonica_do_banco_e_estavel_byte_a_byte(par: ParDeConstrucoes) -> None:
    # Feature: adia-cognitiveloop-prototype, Property 30: serialização canônica é estável
    """Serializar, interpretar e serializar de novo dá o mesmo arquivo, byte a byte (R3.5).

    Cinco afirmações, que falham por motivos diferentes:

    - a segunda serialização é igual, **em bytes**, ao arquivo que a primeira produziu — é R3.5,
      e é a única das cinco que precisa da carga para falhar;
    - o arquivo contém exatamente os bytes do texto serializado, o que recusa tradução na
      gravação. Sem essa afirmação, `CRLF` em disco passaria calado: a leitura normaliza
      `\\r\\n`, as duas serializações seguiriam idênticas e o arquivo não seria o que R3.3 pede;
    - o arquivo não começa por BOM (R3.3);
    - não há `CR` em lugar nenhum, que é o fim de linha `LF` do enunciado e, de passagem, o
      retorno de carro de `FRAGMENTOS_ADVERSARIOS` saindo escapado em vez de literal;
    - o texto não depende da construção: o banco embaralhado produz o arquivo do banco canônico.
      É a ênfase de §5.5, e é ela que separa a ordem vazada da construção para o arquivo de uma
      instabilidade na leitura.

    `deadline=None` é desvio desta propriedade, e não da lista de §5.0, que nomeia as quatro que
    tocam o SQLite. A razão que a lista dá vale aqui: o prazo por exemplo mede latência de E/S —
    uma gravação e uma carga por exemplo, em diretório temporário do Windows, com antivírus no
    caminho — e latência de E/S não é corretude. A folga está medida: 8 a 47 ms por exemplo nesta
    máquina, contra o prazo padrão de 200 ms. O desvio protege contra o **pico**, não contra a
    média: um exemplo lento basta para pintar o portão de vermelho com uma mensagem sobre
    cronômetro, e `DeadlineExceeded` que não se reproduz volta como teste instável. Prazo frouxo
    foi rejeitado por ser a mesma medida com outro número; medir orçamento é de §2.5, com o
    marcador `desempenho`.
    """
    primeiro = serializar_canonico(par.embaralhada, [])
    with tempfile.TemporaryDirectory() as raiz:
        caminho = _gravar(Path(raiz), f"banco{SUFIXO_DE_ARQUIVO}", primeiro)
        gravado = caminho.read_bytes()
        interpretado = _banco(carregar([caminho]))
    segundo = serializar_canonico(interpretado.itens, interpretado.relacoes)

    assert segundo.encode("utf-8") == gravado
    assert gravado == primeiro.encode("utf-8")
    assert not gravado.startswith(BOM_DE_UTF8)
    assert RETORNO_DE_CARRO not in gravado
    assert primeiro == serializar_canonico(par.canonica, [])


# --------------------------------------------------------------------------- #
# Afirmação de apoio: a ênfase de §5.5 tem exemplo
# --------------------------------------------------------------------------- #


def _fora_de_ordem(colecao: tuple[str, ...]) -> bool:
    """Se a coleção não está na ordem em que a leitura a devolve."""
    return colecao != tuple(sorted(colecao))


def alguma_colecao_fora_de_ordem(par: ParDeConstrucoes) -> bool:
    """Se algum item traz coleção fora da ordem canônica, em qualquer dos dois níveis."""
    for item in par.embaralhada:
        if _fora_de_ordem(item.sinonimos_unidade) or _fora_de_ordem(item.variacoes_gabarito):
            return True
        if item.termos_essenciais != tuple(sorted(item.termos_essenciais)):
            return True
        if any(_fora_de_ordem(grupo) for grupo in item.termos_essenciais):
            return True
    return False


def algum_catalogo_fora_de_ordem(par: ParDeConstrucoes) -> bool:
    """Se algum catálogo de dicas foi inserido fora da ordem de `Nivel`."""
    return any(tuple(item.dicas) != tuple(Nivel) for item in par.embaralhada)


def sequencia_de_itens_fora_de_ordem(par: ParDeConstrucoes) -> bool:
    """Se a sequência entregue ao serializador não está na ordem de `id` do banco publicado."""
    identificadores = [identificador_de(item) for item in par.embaralhada]
    return identificadores != sorted(identificadores)


FORMAS_DE_EMBARALHAMENTO: Final = (
    ("coleção", alguma_colecao_fora_de_ordem),
    ("catálogo de dicas", algum_catalogo_fora_de_ordem),
    ("sequência de itens", sequencia_de_itens_fora_de_ordem),
)
"""As três ordens que a construção decide, com o reconhecedor de cada uma."""


@pytest.mark.parametrize(("forma", "fora_de_ordem"), FORMAS_DE_EMBARALHAMENTO)
def test_a_geracao_alcanca_cada_uma_das_tres_ordens_embaralhadas(
    forma: str, fora_de_ordem: Callable[[ParDeConstrucoes], bool]
) -> None:
    """Cada uma das três ordens é alcançável, em vez de apenas pretendida.

    Sem `@given`, porque não é a propriedade: é a guarda da **ênfase** dela. O modo de falha que
    ela pega é silencioso, e é o que a torna necessária. Embaralhamento que deixasse de embaralhar
    — coleção que só sai com um elemento, permutação trocada por uma cópia, `Nivel` reduzido a um
    nível — não quebra nada: P30 segue verde, afirmando a estabilidade sobre entrada que já estava
    na forma canônica, e o que se perde é a chance de encontrar o defeito. `find` reprova com
    `NoSuchExample` quando a forma deixa de ser alcançável, que é o contrário de silencioso.
    """
    assert fora_de_ordem(find(pares_de_construcao(), fora_de_ordem)), forma
