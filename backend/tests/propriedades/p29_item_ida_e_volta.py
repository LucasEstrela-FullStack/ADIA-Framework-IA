"""Propriedade 29: o banco de itens sobrevive a interpretar, serializar e interpretar de novo.

Primeiro arquivo de propriedade do repositório, e por isso ele fixa a forma dos outros 36. O
que é convenção, e não substância de P29, está marcado como tal:

1. **Um arquivo, uma propriedade, um teste.** §5.0 exige um único teste de propriedade por
   propriedade. Afirmação de apoio que não seja a propriedade entra como teste separado e sem
   `@given`, nunca como segundo `@given` no mesmo arquivo.
2. **Etiqueta na primeira linha do corpo**, no formato de §5.0, *antes* da docstring. Comentário
   não é instrução, então a cadeia seguinte continua sendo a docstring do teste; a etiqueta é o
   que liga o teste à seção do design que o enuncia, e essa ligação é a primeira coisa que vê
   quem abre o arquivo na altura do teste.
3. **Orçamento de exemplos vem do perfil**, registrado em `backend/tests/conftest.py`. O único
   `@settings` que aparece aqui é o desvio desta propriedade, com a justificativa colada nele.
4. **Geradores vêm de `estrategias.py`.** O que é composto neste arquivo é composto a partir
   deles e fica nomeado, para que o contraexemplo encolhido continue legível (§6.3).
5. **`tempfile`, nunca a fixture `tmp_path`.** Fixture de escopo de função sob `@given` é
   reprovada pela própria biblioteca, e com razão: ela seria criada uma vez e compartilhada por
   todos os exemplos. E a gravação é em **bytes**, porque `write_text` no Windows traduziria
   `LF` em `CRLF` e o arquivo deixaria de ser o que `serializar_canonico` produziu (R3.3).

## O que esta propriedade acrescenta ao caso dirigido

`backend/tests/unidade/test_serializador_canonico.py` já verifica a mesma ida e volta em casos
**dirigidos**, com texto esperado escrito à mão — e é lá que mora a verificação da *forma* do
texto, que uma propriedade de ida e volta não vê: forma errada e estável passa nos dois
sentidos. O que aqui é novo é o **banco**, no plural que o enunciado usa:

- vários itens, cujos identificadores são distintos e sorteados, de modo que a ordenação por
  `id` do banco publicado (R3.6, §3.1) não coincide com a ordem em que os itens foram escritos;
- vários **arquivos**, com os itens distribuídos em rodízio entre eles, de modo que a ordem de
  publicação não coincide nem com a ordem dos arquivos nem com a ordem dentro de um arquivo.
  É esta a entrada em que um item perdido entre a leitura e a escrita aparece — num banco de um
  item só, nem a ordenação nem a união entre arquivos é exercitada;
- conteúdo de item sorteado no domínio inteiro de `itens_carregaveis`, e não os três itens
  escolhidos à mão do caso dirigido: os três tipos de gabarito, tolerância decimal, coleções nos
  dois níveis, acentuação, símbolos matemáticos e as quinze classes de texto adversário.

## O limite que a propriedade não alcança

Os arquivos de entrada são escritos por `serializar_canonico`, logo a entrada é sempre texto
**já canônico**. Arquivo válido mas fora da forma canônica — chave fora de ordem, cadeia de uma
linha, `tolerancia = "0.050"` — fica coberto pelo caso dirigido
`test_canonizar_reescreve_arquivo_fora_da_forma_canonica`, e não por aqui: gerá-lo exigiria um
escritor de TOML arbitrário no teste, e a geração que §5.5 pede para P29 é de **itens**. Vale
saber ao ler esta propriedade verde: ela afirma que a ida e volta preserva o banco, não que
toda escrita possível do mesmo banco seja interpretada igual.

Relações ficam fora por decisão de escopo: a geração de §5.5 não as menciona, e item praticado
— o que as exige, por R2.2 e R2.6 — está fora de `itens_carregaveis` por construção. A ida e
volta de relação é afirmada no caso dirigido, com o trio válido montado à mão.

**Validates: Requirements 3.4**
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest
from estrategias import bancos, identificador_de
from hypothesis import given, settings
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

MAXIMO_DE_ITENS: Final = 4
"""Teto de itens por banco gerado.

Pequeno de propósito. O que o banco precisa exercitar é a união entre arquivos e a ordenação por
`id`, e quatro itens repartidos em três arquivos já dão as duas coisas. Dobrar o teto
multiplicaria o custo de cada exemplo — são duas cargas completas e até quatro gravações por
exemplo — sem alcançar nenhuma invariante nova.
"""

MAXIMO_DE_ARQUIVOS: Final = 3
"""Teto de arquivos por banco gerado.

Dois arquivos verificam que a união junta um par; o terceiro é o que distingue isso de "a união
percorre a lista de arquivos". E com o teto de itens acima, o rodízio reparte quatro itens em 2,
1 e 1 — partes de tamanhos diferentes, que é a forma em que um deslize de contagem por arquivo
aparece e que uma partição uniforme esconderia.
"""


# --------------------------------------------------------------------------- #
# Geração da partição
#
# Convenção de nome deste arquivo: o que é candidato a migrar para `estrategias.py` no dia em
# que uma segunda propriedade precisar dele fica público; o encanamento do teste fica privado.
# P30 (tarefa 3.6) exerceu essa fronteira, e ela se moveu onde devia: a estratégia `bancos` e a
# chave `identificador_de` agora vêm de `estrategias.py`, porque unicidade e ordenação por `id`
# são exigência do **banco** (R3.6) e não substância de nenhuma das duas propriedades. O que
# ficou aqui é o que é de P29: a **partição** entre arquivos, que é a entrada de que só a união
# de R3.3 precisa, e as duas gravações e cargas que ela custa.
# --------------------------------------------------------------------------- #


def _repartir(do_banco: Sequence[Item], arquivos: int) -> tuple[tuple[Item, ...], ...]:
    """Distribui os itens entre `arquivos` partes, em rodízio, sem deixar parte vazia.

    Rodízio, e não um índice de arquivo sorteado por item, por três razões. Nenhuma parte sai
    vazia — e arquivo vazio é erro de carga, o que faria a propriedade reprovar por banco
    inválido em vez de por defeito de ida e volta. O **entrelaçamento** é garantido em todo
    exemplo, em vez de ocasional: itens vizinhos na lista caem em arquivos diferentes, de modo
    que nenhum arquivo fica com um trecho contíguo da lista gerada e a correspondência entre
    arquivo e posição na ordem publicada se rompe por construção, não por sorte. E o sorteio
    fica com uma decisão a menos, o que encolhe melhor.
    """
    partes: list[list[Item]] = [[] for _ in range(arquivos)]
    for ordinal, item in enumerate(do_banco):
        partes[ordinal % arquivos].append(item)
    return tuple(tuple(parte) for parte in partes)


@st.composite
def particoes(draw: DrawFn) -> tuple[tuple[Item, ...], ...]:
    """Banco de itens carregáveis repartido entre um e `MAXIMO_DE_ARQUIVOS` arquivos.

    Encolhe para um item em um arquivo, que é o banco mínimo compreensível. A contagem de arquivos
    é limitada ao número de itens para que nenhuma parte saia vazia — arquivo vazio é erro de
    carga, e a propriedade reprovaria por banco inválido em vez de por defeito de ida e volta.
    """
    do_banco = draw(bancos(maximo=MAXIMO_DE_ITENS))
    arquivos = draw(st.integers(min_value=1, max_value=min(MAXIMO_DE_ARQUIVOS, len(do_banco))))
    return _repartir(do_banco, arquivos)


def _gravar(diretorio: Path, nome: str, texto: str) -> Path:
    """Grava o texto em UTF-8 sem BOM, em bytes, sem tradução de fim de linha (R3.3)."""
    caminho = diretorio / nome
    caminho.write_bytes(texto.encode("utf-8"))
    return caminho


def _banco(resultado: ResultadoDeCarga) -> CargaConcluida:
    """Desembrulha a carga, falhando com a mensagem da rejeição quando houver.

    A mensagem é o que separa os dois diagnósticos possíveis de uma P29 vermelha: carga
    rejeitada aponta para o gerador ou para a gramática, e banco diferente aponta para a
    serialização. Sem a mensagem, as duas chegam como o mesmo `AssertionError`.
    """
    if isinstance(resultado, ErroDeCarga):
        pytest.fail(f"a carga devia ter concluído: {resultado.mensagem}")
    return resultado


@given(particoes())
@settings(deadline=None)
def test_o_banco_sobrevive_a_ida_e_volta_de_interpretacao(particao: tuple[tuple[Item, ...], ...]) -> None:
    # Feature: adia-cognitiveloop-prototype, Property 29: itens sobrevivem à ida e volta de
    # interpretação
    """Carregar, serializar e carregar de novo devolve o mesmo banco, por estrutura (R3.4).

    A comparação é **estrutural**, nunca textual: `Item` é `dataclass` congelada, e a igualdade
    compara campo a campo, inclusive `tolerancia` em `Decimal` e o catálogo de dicas. Igualdade
    de texto é a Propriedade 30, e afirmá-la aqui tornaria as duas a mesma propriedade.

    Três afirmações, que falham por motivos diferentes:

    - o banco reinterpretado é igual ao interpretado — a ida e volta de R3.4;
    - as relações atravessam junto, o que recusa relação inventada na escrita (o banco gerado
      não declara nenhuma, e é esse `()` que tem de voltar dos dois lados);
    - o banco interpretado é o conjunto gerado, ordenado por `id` — é o que pega item perdido
      entre arquivos na união e ordem de publicação que depende da ordem de escrita.

    `deadline=None` é desvio desta propriedade, e não da lista de §5.0. A lista nomeia P16, P17,
    P31 e P35, que são as que tocam o SQLite, mas a razão que ela dá vale aqui inteira: o prazo
    por exemplo da biblioteca mede latência de E/S — aqui, até quatro gravações e duas cargas
    completas por exemplo, em diretório temporário do Windows, com antivírus no caminho — e
    latência de E/S não é corretude.

    A folga existe e está medida: 9 a 37 ms por exemplo nesta máquina, contra o prazo padrão de
    200 ms. O desvio é seguro contra o **pico**, não contra a média — um exemplo lento basta
    para pintar o portão de vermelho com uma mensagem sobre cronômetro, e o modo de falha é
    pior que o sintoma, porque `DeadlineExceeded` que não se reproduz volta como teste instável.
    O prazo frouxo foi rejeitado por ser a mesma medida com outro número. Medir orçamento é de
    §2.5, com o marcador `desempenho`.
    """
    with tempfile.TemporaryDirectory() as raiz:
        diretorio = Path(raiz)
        caminhos = [
            _gravar(diretorio, f"banco-{ordinal}{SUFIXO_DE_ARQUIVO}", serializar_canonico(parte, []))
            for ordinal, parte in enumerate(particao)
        ]

        interpretado = _banco(carregar(caminhos))
        reescrito = _gravar(
            diretorio,
            f"reescrito{SUFIXO_DE_ARQUIVO}",
            serializar_canonico(interpretado.itens, interpretado.relacoes),
        )
        reinterpretado = _banco(carregar([reescrito]))

    gerados = tuple(item for parte in particao for item in parte)

    assert reinterpretado.itens == interpretado.itens
    assert reinterpretado.relacoes == interpretado.relacoes
    assert interpretado.itens == tuple(sorted(gerados, key=identificador_de))
