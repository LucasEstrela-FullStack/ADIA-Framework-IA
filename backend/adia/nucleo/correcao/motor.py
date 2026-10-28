"""Motor_de_Correção: ``Resultado``, ``Julgamento`` e ``corrigir``, função pura (§3.2, R4).

Julga uma resposta contra **o que o item declara** e nada mais. Não lê relógio, não sorteia,
não guarda estado, não toca disco e não fala com o ``Serviço_de_Inferência_Local`` (R4.5) —
o contrato ``nucleo-puro`` de ``backend/.importlinter`` verifica a parte estática disso, e a
fixture ``ollama_proibido`` verifica a execução. O determinismo de R4.4 é consequência: sem
estado e sem entrada oculta, o mesmo par ``(item, resposta)`` produz o mesmo ``Julgamento``.

Cinco decisões sustentam este módulo, e nenhuma delas é detalhe de implementação.

**1. A comparação numérica é exata e independente do contexto decimal.** A tolerância decide
o acerto de item de fronteira, e item de fronteira é o que separa acerto de erro na TAI. Por
isso ``tolerancia`` é ``Decimal`` no modelo, e por isso a diferença **não** é calculada com
``float`` nem com aritmética de ``Decimal`` sob o contexto ambiente: ``Decimal`` arredonda a
subtração conforme a precisão do contexto, que é estado global mutável e, portanto, entrada
oculta de uma função que precisa ser pura. ``dentro_da_tolerancia`` converte para ``Fraction``,
onde a subtração e a comparação são exatas e não dependem de contexto nenhum.

A comparação é ``≤``, e não ``<``: o desvio **exatamente igual** à tolerância conta como
acerto. Com ``tolerancia = 0`` — o que o banco declara nas partes de contagem, onde fração de
unidade não significa nada — a regra degenera em igualdade exata, que é o mesmo que o detector
D2 da guarda faz em §3.11. A Propriedade 37 reforça a amostragem exatamente nesse ponto.

**2. A notação aceita na resposta é declarada, e é um superconjunto da notação do banco.** A
resposta do estudante é prosa, não conteúdo de arquivo: um estudante brasileiro escreve
``4,5``. ``PADRAO_DE_DECIMAL`` descreve a tolerância **escrita no arquivo** (ponto, sem
agrupamento) e seria estreita demais aqui, então ``interpretar_decimal`` declara a gramática
de leitura da resposta — ver o docstring dela para a regra de separador e para o desempate que
§3.11 deixou pendente. O que importa aqui é a relação entre as duas: toda forma que
``PADRAO_DE_DECIMAL`` admite é lida por ``interpretar_decimal`` com **o mesmo valor**, de modo
que gabarito e resposta nunca são interpretados por critérios diferentes.

**3. O item é a fonte da verdade sobre o que conta como equivalente.** ``gabarito`` e
``variacoes_gabarito`` são comparados por igualdade, e as variações são consultadas **antes**
da tolerância: é o banco que declara que ``"quatro"`` e ``"4.0"`` são formas aceitas do
gabarito ``"4"`` (R2.1), e nenhuma normalização que o banco não declare é inventada aqui.
Nenhum léxico de numerais, nenhuma remoção de acento, nenhuma equivalência algébrica — isso é
território da ``Guarda_de_Vazamento`` (§3.11), que tem outro objetivo: lá o alvo é *recall*
sobre texto gerado, e errar para o lado inclusivo é falha fechada; aqui errar para o lado
inclusivo é **inflar a TAI**. A única normalização aplicada à resposta é a remoção do espaço
em volta, mais a remoção da ``unidade`` declarada quando ela aparece como sufixo — ver
``_sem_unidade_declarada``.

**4. A justificativa nomeia o critério aplicado, nunca o gabarito.** R4.3 exige registrar a
justificativa "em termos do gabarito aplicado", e o ``Julgamento`` volta para quem apresenta a
submissão ao estudante. As duas coisas só são compatíveis de uma forma: a justificativa diz
**qual critério decidiu** — tipo de gabarito, comparação exata ou tolerância, e qual tolerância
—, e não diz o valor do gabarito, qual variação casou, nem o desvio medido. O desvio é a parte
não óbvia: quem conhece a própria resposta e o desvio conhece o gabarito. A regra é a mesma de
``itens/erros.py``, onde mensagem de erro não cita conteúdo, e tem respaldo no registro: §4.2
dá a ``resposta_submetida`` os campos ``resultado``, ``motivo_correcao`` e
``tolerancia_aplicada``, e **não** dá o gabarito.

O que este módulo deliberadamente **não** decide é *se* o julgamento pode ser mostrado. Revelar
o resultado durante a prática assistida e revelar o resultado de um desafio independente já
submetido são atos diferentes (R5.6), e ``corrigir(item, resposta)`` não recebe etapa, ciclo
nem condição — logo não tem informação para decidir, e fabricar a decisão aqui seria pior que
não tomá-la. A decisão é de quem apresenta.

**5. Resposta inválida é julgamento, não erro.** Resposta vazia e resposta acima do
``tamanho_max_resposta`` do item produzem ``Julgamento`` com ``resultado = erro`` e
``motivo_rejeicao`` preenchido (R4.6), e não uma terceira família ao lado de ``ErroDeCarga`` e
``ErroDeSelecao``. A razão está em §7.3: o julgamento falha **fechado** — vazio nunca é acerto
—, mas o percurso falha **aberto** — a tentativa existiu, a submissão é aceita e persistida.
Transformar isso em erro tiraria a tentativa do denominador da TAI e melhoraria o desempenho
aparente do estudante sem que nada registrasse a melhora artificial. O limite é do **item**,
não do esquema do endpoint, e por isso não produz ``422``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum, unique
from fractions import Fraction
from typing import Final, TypeIs

from adia.nucleo.itens.carregador import decimal_canonico
from adia.nucleo.itens.modelo import Item, TipoGabarito
from adia.tipos import Indisponivel

# --------------------------------------------------------------------------- #
# Resultado do julgamento
# --------------------------------------------------------------------------- #


@unique
class Resultado(StrEnum):
    """Veredito da correção automática, no conjunto ``{acerto, erro}`` que R4.3 fixa.

    ``StrEnum`` porque o valor é o texto gravado em ``resposta_submetida.resultado``, cujo
    ``CHECK (resultado IN ('acerto', 'erro'))`` em §4.3 é literalmente este conjunto. Não há
    terceiro membro: "não sei julgar" não é veredito, e acrescentá-lo aqui faria toda contagem
    de acerto — TAI, TT, Retenção — passar a ter um caso que nenhuma delas sabe contar.
    """

    ACERTO = "acerto"
    ERRO = "erro"


type ResultadoDoJulgamento = Resultado | Indisponivel
"""Veredito, ou a ausência declarada de veredito automático.

**Divergência declarada em relação a §3.2**, que escreve ``resultado: Resultado``. O item de
gabarito ``TEXTUAL`` é o motivo: R4.7 manda corrigir apenas as partes de gabarito objetivo e
encaminhar a justificativa a avaliação humana, e um item ``TEXTUAL`` do modelo de §3.1 **não
tem** parte objetiva — tem um gabarito textual e conjuntos de termos essenciais, que R2.11
declara para a guarda de vazamento. Não existe, portanto, veredito automático honesto, e as
três alternativas são piores que a união:

- ``erro`` contaria como resposta errada o que ninguém julgou, e alimentaria a TAI com um zero
  que não foi medido;
- ``acerto`` inflaria a TAI pelo lado oposto;
- julgar por presença de ``termos_essenciais`` usaria como oráculo de acerto um campo que
  R2.11 e R7.6 declaram para a **guarda** — palavra-chave como critério de acerto seria pior
  que nenhum julgamento, porque pareceria um julgamento.

``Indisponivel`` é o vocabulário que o projeto já usa para isso (R11.7): ausência de base para
afirmar, com motivo, e nunca zero disfarçado. O tipo-união é a barreira — quem recebe um
``Julgamento`` não consegue contar o resultado sem antes distinguir os dois casos, porque o
``mypy --strict`` recusa. Ver o relato da tarefa: ``resposta_submetida.resultado`` é
``NOT NULL`` com ``CHECK`` em §4.3, de modo que a persistência do item ``TEXTUAL`` puro é uma
lacuna aberta no design, e esta união é o que a torna visível em vez de silenciosa.
"""


def e_julgado(resultado: ResultadoDoJulgamento) -> TypeIs[Resultado]:
    """Se houve veredito automático, estreitando o tipo nos **dois** ramos.

    Mesma forma de ``e_disponivel`` em ``adia.tipos``, e pela mesma razão: a distinção
    obrigatória ganha **uma** forma idiomática, e o ramo falso vem tipado, com acesso a
    ``motivo`` sem conversão nem asserção.
    """
    return isinstance(resultado, Resultado)


# --------------------------------------------------------------------------- #
# Motivos de rejeição e de indisponibilidade
# --------------------------------------------------------------------------- #

MOTIVO_VAZIA: Final = "vazia"
MOTIVO_EXCEDE_TAMANHO_MAXIMO: Final = "excede_tamanho_maximo"
"""Os dois motivos de rejeição de R4.6, com o texto que §7.3 fixa para ``motivo_correcao``."""

MOTIVOS_DE_REJEICAO: Final = (MOTIVO_VAZIA, MOTIVO_EXCEDE_TAMANHO_MAXIMO)
"""O conjunto fechado dos motivos, na ordem em que ``corrigir`` os verifica.

A ordem é a verificação: resposta só de espaço **e** mais longa que o limite do item satisfaz
as duas condições, e ``vazia`` prevalece porque é a mais informativa das duas — o problema não
é o tamanho, é que não há conteúdo. Sem precedência declarada, o motivo gravado dependeria da
ordem em que alguém escreveu os ``if``.
"""

MOTIVO_AGUARDANDO_RUBRICA: Final = "aguardando_rubrica"
"""Motivo da indisponibilidade do veredito que depende de avaliação humana (§7.3, R4.7).

É o mesmo motivo que §7.3 declara para a pontuação do projeto STEAM enquanto a rubrica não
chega, e reaproveitá-lo é deliberado: duas grafias do mesmo estado produziriam duas lacunas
diferentes na tela para a mesma causa.
"""


# --------------------------------------------------------------------------- #
# Justificativa: critério aplicado, nunca o gabarito
# --------------------------------------------------------------------------- #

JUSTIFICATIVA_DE_VAZIA: Final = (
    "resposta vazia: não há conteúdo a julgar, e vazio nunca é acerto; nenhum critério de "
    "gabarito foi aplicado (R4.6)."
)

JUSTIFICATIVA_DE_FORMA_DECLARADA: Final = (
    "gabarito numérico: a resposta coincide com uma das formas declaradas do gabarito, "
    "aceitas pelo próprio item (R2.1)."
)

JUSTIFICATIVA_DE_ALTERNATIVA_CORRETA: Final = (
    "gabarito de alternativa: a resposta coincide exatamente com uma das formas declaradas "
    "do gabarito (R4.2)."
)

JUSTIFICATIVA_DE_ALTERNATIVA_INCORRETA: Final = (
    "gabarito de alternativa: a resposta não coincide exatamente com nenhuma das formas "
    "declaradas do gabarito (R4.2)."
)

JUSTIFICATIVA_DE_RESPOSTA_NAO_NUMERICA: Final = (
    "gabarito numérico: a resposta não é interpretável como número decimal na notação aceita "
    "— ponto ou vírgula como separador decimal — e não coincide com nenhuma forma declarada "
    "do gabarito; nenhuma comparação por tolerância foi possível (R4.1)."
)

JUSTIFICATIVA_DE_GABARITO_NAO_NUMERICO: Final = (
    "gabarito numérico: o gabarito declarado no item não é interpretável como número decimal, "
    "e a comparação por tolerância não pôde ser aplicada; o julgamento falha fechado (R4.1)."
)

JUSTIFICATIVA_DE_TOLERANCIA_AUSENTE: Final = (
    "gabarito numérico: o item não declara tolerância, e sem ela não existe critério de acerto "
    "a aplicar; o julgamento falha fechado (R2.8, R4.1)."
)

JUSTIFICATIVA_DE_RUBRICA: Final = (
    "gabarito textual: a correção automática não pontua texto argumentativo; a resposta segue "
    "integralmente para avaliação por rubrica humana (R4.7)."
)


def _justificativa_de_excesso(caracteres: int, maximo: int) -> str:
    """Diz quanto veio e quanto o item admite. Nenhum dos dois números revela gabarito."""
    return (
        f"resposta com {caracteres} caracteres acima do tamanho máximo de {maximo} declarado "
        f"para o item; nenhum critério de gabarito foi aplicado (R4.6)."
    )


def _tolerancia_em_texto(tolerancia: Decimal) -> str:
    """Tolerância aplicada, na forma canônica do projeto, com o caso zero nomeado.

    ``decimal_canonico`` vem do carregador de propósito: é a forma em que a tolerância está
    **escrita no arquivo**, e escrever ``0.050`` aqui onde o banco declara ``0.05`` seria uma
    segunda grafia do mesmo valor — exatamente o que aquela função existe para evitar (R3.5).
    O preço é um acoplamento de ``correcao`` a ``itens``, que já existe por ``Item``.
    """
    canonica = decimal_canonico(tolerancia)
    if tolerancia.is_zero():
        return f"tolerância declarada de {canonica}, que exige igualdade exata"
    return f"tolerância declarada de {canonica}"


def _justificativa_numerica(tolerancia: Decimal, *, dentro: bool) -> str:
    """Critério numérico aplicado, com a tolerância e **sem** o desvio medido.

    O desvio fica fora por ser a via mais curta de vazamento: quem conhece a própria resposta
    e o desvio reconstrói o gabarito. A tolerância pode aparecer porque não se deriva dela
    nenhum valor de gabarito, e porque §4.2 já a grava em ``resposta_submetida``.
    """
    relacao = "está dentro da" if dentro else "excede a"
    return (
        f"gabarito numérico: o desvio entre a resposta e o gabarito {relacao} "
        f"{_tolerancia_em_texto(tolerancia)} (R4.1)."
    )


# --------------------------------------------------------------------------- #
# Julgamento
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Julgamento:
    """O que a correção automática produziu sobre uma submissão (§3.2, R4.3, R4.6, R4.7).

    Valor imutável e comparável por igualdade, o que é o que torna a Propriedade 36 escrevível
    em uma linha: dois julgamentos do mesmo par são iguais, campo a campo, inclusive na
    justificativa.
    """

    resultado: ResultadoDoJulgamento
    justificativa: str
    motivo_rejeicao: str | None
    partes_para_rubrica: tuple[str, ...]

    def __post_init__(self) -> None:
        """Garante as duas invariantes que o contrato afirma em prosa.

        A primeira é R4.3: há **sempre** justificativa registrada, e justificativa vazia seria
        o campo cumprido sem a informação. A segunda é R4.6: ``motivo_rejeicao`` só existe
        junto de ``erro``. Motivo ao lado de ``acerto`` descreveria uma submissão rejeitada e
        aceita ao mesmo tempo, e o par ``(resultado, motivo_correcao)`` do evento ficaria
        contraditório no registro.
        """
        if not self.justificativa.strip():
            raise ValueError("todo julgamento registra justificativa não vazia (R4.3).")
        if self.motivo_rejeicao is None:
            return
        if not self.motivo_rejeicao.strip():
            raise ValueError("motivo de rejeição, quando presente, é não vazio (R4.6).")
        if self.resultado is not Resultado.ERRO:
            raise ValueError(
                f"motivo de rejeição {self.motivo_rejeicao!r} exige resultado "
                f"{Resultado.ERRO.value!r} (R4.6)."
            )


# --------------------------------------------------------------------------- #
# Leitura de decimal escrito por humano
# --------------------------------------------------------------------------- #

_INTEIRO: Final = re.compile(r"^[+-]?\d+$")
_DECIMAL_SIMPLES: Final = re.compile(r"^[+-]?\d+[.,]\d+$")
_AGRUPADO_DECIMAL_PT_BR: Final = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+,\d+$")
_AGRUPADO_DECIMAL_EN_US: Final = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+\.\d+$")
_AGRUPADO_INTEIRO_PONTO: Final = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3}){2,}$")
_AGRUPADO_INTEIRO_VIRGULA: Final = re.compile(r"^[+-]?\d{1,3}(?:,\d{3}){2,}$")
"""As seis formas aceitas, na ordem em que ``interpretar_decimal`` as tenta."""


def interpretar_decimal(texto: str) -> Decimal | None:
    """Número decimal escrito por humano em pt-BR, ou ``None`` quando o texto não é número.

    **A regra de desempate do separador, que §3.11 deixou como pendência.** O separador
    decimal brasileiro é a vírgula e o do código e dos dados é o ponto (DO-23), então os dois
    são aceitos. O problema é a ambiguidade real: ``1.234`` pode ser mil duzentos e trinta e
    quatro ou um e duzentos e trinta e quatro milésimos. A regra declarada, em ordem:

    1. sem separador, inteiro: ``1234``;
    2. **um** separador, uma única ocorrência: ele é o **separador decimal**, e isto resolve
       ``1.234`` como ``1,234`` — ver abaixo por que esse lado;
    3. os **dois** separadores presentes: o mais à direita é o decimal e o outro é
       agrupamento, que é a mesma regra do estágio 1 de §3.11 — ``1.234,56`` e ``1,234.56``
       valem ambos mil duzentos e trinta e quatro e cinquenta e seis centésimos;
    4. um separador **repetido** em grupos de três: agrupamento de milhar, inteiro
       (``1.234.567``);
    5. qualquer outra coisa — notação científica, espaço no meio, ponto sem dígito de um dos
       lados, texto — não é número, e o ``None`` faz o julgamento falhar fechado.

    O passo 2 é o desempate, e ele é para o lado decimal por uma razão que não é de gosto:
    ``format(Decimal, "f")``, que é a forma canônica do projeto em ``decimal_canonico`` e em
    ``texto_decimal`` nas estratégias, **preserva zeros à direita**. Um e meio com três casas
    é exatamente ``1.500``. Ler ``1.500`` como mil e quinhentos recusaria como errada uma
    resposta escrita na notação canônica do próprio projeto, que é o pior dos dois erros
    possíveis aqui; e o agrupamento, que é a leitura descartada, continua disponível nas
    formas 3 e 4, onde não há ambiguidade nenhuma. Falha fechada no passo 5 cobre o resto: sem
    leitura única, não há acerto.

    A relação com ``PADRAO_DE_DECIMAL`` do carregador é de **superconjunto**: toda forma que
    a gramática do arquivo admite cai no passo 1 ou no passo 2 e produz o mesmo valor que
    ``Decimal`` produziria sobre o texto original. É isso que garante que gabarito e resposta
    não sejam lidos por critérios diferentes.
    """
    bruto = texto.strip()
    if _INTEIRO.match(bruto) is not None:
        return _para_decimal(bruto)
    if _DECIMAL_SIMPLES.match(bruto) is not None:
        return _para_decimal(bruto.replace(",", "."))
    if _AGRUPADO_DECIMAL_PT_BR.match(bruto) is not None:
        return _para_decimal(bruto.replace(".", "").replace(",", "."))
    if _AGRUPADO_DECIMAL_EN_US.match(bruto) is not None:
        return _para_decimal(bruto.replace(",", ""))
    if _AGRUPADO_INTEIRO_PONTO.match(bruto) is not None:
        return _para_decimal(bruto.replace(".", ""))
    if _AGRUPADO_INTEIRO_VIRGULA.match(bruto) is not None:
        return _para_decimal(bruto.replace(",", ""))
    return None


def _para_decimal(texto: str) -> Decimal | None:
    """Converte texto já reduzido à notação simples, recusando o que não for número finito.

    ``InvalidOperation`` e ``is_finite`` são redundantes diante das formas acima, e ficam
    porque a redundância é barata e a alternativa é confiar que seis expressões regulares
    nunca mudem juntas: ``nan`` e ``inf`` passariam por ``Decimal`` sem reclamação, e
    ``nan`` numa comparação de tolerância devolveria ``False`` silenciosamente.
    """
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    return valor if valor.is_finite() else None


def dentro_da_tolerancia(valor: Decimal, gabarito: Decimal, tolerancia: Decimal) -> bool:
    """Se o desvio entre resposta e gabarito **não excede** a tolerância declarada (R4.1).

    Critério único do acerto numérico, isolado em uma função por dois motivos: é o que a
    Propriedade 37 exercita na fronteira, e é o que R13.2 pede para as partes numéricas do
    projeto STEAM — que não são ``Item`` e, por isso, não entram por ``corrigir`` (ver o
    relato da tarefa).

    Duas escolhas, e a razão de cada uma:

    - ``≤`` e não ``<``: o desvio exatamente igual à tolerância é acerto, nas duas direções.
      Com ``tolerancia = 0`` a regra vira igualdade exata, que é o que as partes de contagem
      do banco declaram e o que o detector D2 da guarda faz em §3.11;
    - ``Fraction`` e não ``Decimal`` na subtração: a comparação de ``Decimal`` é exata, mas a
      **subtração** é arredondada pela precisão do contexto decimal vigente, que é estado
      global mutável. Uma função pura não pode ter o veredito dependendo de quem mexeu no
      contexto antes dela. A conversão de ``Decimal`` para ``Fraction`` é exata, e a aritmética
      de ``Fraction`` não tem contexto nem precisão a perder.
    """
    desvio = abs(Fraction(valor) - Fraction(gabarito))
    return desvio <= Fraction(tolerancia)


# --------------------------------------------------------------------------- #
# O que o item declara como forma aceita
# --------------------------------------------------------------------------- #


def formas_declaradas(item: Item) -> tuple[str, ...]:
    """Gabarito e suas variações declaradas, que são as formas que o item aceita (R2.1).

    O gabarito vem primeiro porque é a forma de referência; a ordem não afeta o julgamento,
    que é uma pertinência a conjunto.
    """
    return (item.gabarito, *item.variacoes_gabarito)


def _coincide_com_forma_declarada(item: Item, texto: str) -> bool:
    """Igualdade entre a resposta e alguma forma declarada, com espaço em volta removido.

    Comparação **exata** no resto: nada de dobrar caixa, remover acento ou colapsar espaço
    interno. O item é quem declara o que conta como equivalente, e o banco inicial mostra que
    a convenção é declarar — ``variacoes_gabarito = ["4", "4.0", "quatro"]`` no item semente,
    e a unidade sem acento listada ao lado da acentuada em ``sinonimos_unidade``. Normalização
    inventada aqui aceitaria silenciosamente o que o banco não aceitou.
    """
    return texto in {forma.strip() for forma in formas_declaradas(item)}


def _sem_unidade_declarada(texto: str, item: Item) -> str:
    """Resposta sem a ``unidade`` do item ou um de seus sinônimos, quando vêm como sufixo.

    ``"12 km"``, ``"12km"`` e ``"12 quilômetros"`` são a resposta ``12`` para um item que
    declara ``unidade = "quilômetros"`` com ``sinonimos_unidade = ["km", "quilometros"]``.
    Aceitar isso não é normalização inventada: a unidade e os sinônimos estão **declarados no
    item**, e o estágio 1 de §3.11 faz o mesmo do outro lado — a guarda considera que
    ``"4 reais"`` revela o valor ``4``. Se a guarda afirma que aquele texto carrega o valor, o
    motor não pode afirmar que não é o valor; a incoerência entre os dois é que seria defeito.

    Três limites, declarados:

    - só **sufixo**, e no máximo um: unidade prefixada (``"R$ 4,00"``) não é coberta, e nenhum
      item do banco declara unidade dessa forma;
    - a forma mais longa é tentada primeiro, para que ``"quilometros"`` não perca para
      ``"km"`` em um item que declare as duas; o desempate entre formas de mesmo comprimento é
      alfabético, e não a ordem de iteração de um conjunto, que varia entre processos — duas
      formas de mesmo comprimento não podem ser sufixo do mesmo texto, mas fazer o julgamento
      depender de ordem imprevisível é o tipo de coisa que a Propriedade 36 existe para pegar;
    - a comparação dobra a caixa dos dois lados, e o corte é feito por índice sobre o texto
      **original**, de modo que caixa cuja dobra muda o comprimento não desloque o corte — no
      pior caso o sufixo não casa, e o julgamento falha fechado.
    """
    if item.unidade is None:
        return texto
    declaradas = {item.unidade, *item.sinonimos_unidade}
    for forma in sorted(declaradas, key=lambda declarada: (-len(declarada), declarada)):
        corte = len(texto) - len(forma)
        if corte > 0 and texto[corte:].casefold() == forma.casefold():
            return texto[:corte].rstrip()
    return texto


# --------------------------------------------------------------------------- #
# Correção
# --------------------------------------------------------------------------- #


def corrigir(item: Item, resposta: str) -> Julgamento:
    """Julga a resposta contra o item, sem relógio, sem rede e sem IA (§3.2, R4).

    A ordem das verificações é parte do contrato, e não conveniência de escrita:

    1. **resposta vazia** (R4.6) — texto só com espaço é texto sem conteúdo, e vazio nunca é
       acerto. Vem primeiro porque é o motivo mais informativo quando mais de um se aplica;
    2. **tamanho acima do declarado no item** (R4.6) — medido sobre o conteúdo, isto é, com o
       espaço em volta já removido. A alternativa seria medir o texto cru, como faz o contador
       de caracteres da interface, e as duas regras passariam a usar noções diferentes de
       "conteúdo": ``"   "`` em um item de limite 1 seria simultaneamente vazia e excedente. A
       medida sobre o conteúdo nunca é maior que a medida crua, então o motor nunca recusa por
       tamanho uma resposta que a interface aceitou;
    3. **o critério do tipo de gabarito** — tolerância declarada em ``NUMERICO`` (R4.1),
       comparação exata em ``ALTERNATIVA`` (R4.2), encaminhamento a rubrica humana em
       ``TEXTUAL`` (R4.7).

    As duas primeiras **não** dependem do tipo de gabarito: valem igualmente para a resposta
    textual, porque justificativa vazia também não tem o que um avaliador humano julgue.
    """
    texto = resposta.strip()
    if not texto:
        return Julgamento(
            resultado=Resultado.ERRO,
            justificativa=JUSTIFICATIVA_DE_VAZIA,
            motivo_rejeicao=MOTIVO_VAZIA,
            partes_para_rubrica=(),
        )
    if len(texto) > item.tamanho_max_resposta:
        return Julgamento(
            resultado=Resultado.ERRO,
            justificativa=_justificativa_de_excesso(len(texto), item.tamanho_max_resposta),
            motivo_rejeicao=MOTIVO_EXCEDE_TAMANHO_MAXIMO,
            partes_para_rubrica=(),
        )
    match item.tipo_gabarito:
        case TipoGabarito.NUMERICO:
            return _julgar_numerico(item, texto)
        case TipoGabarito.ALTERNATIVA:
            return _julgar_alternativa(item, texto)
        case TipoGabarito.TEXTUAL:
            return _encaminhar_para_rubrica(texto)


def _julgar_numerico(item: Item, texto: str) -> Julgamento:
    """Aplica a tolerância declarada no item, com as formas declaradas tendo precedência (R4.1).

    A precedência é a decisão a registrar: ``variacoes_gabarito`` é consultado **antes** da
    tolerância porque é o item que declara o que conta como forma aceita do gabarito (R2.1), e
    porque há forma declarada que nenhuma tolerância alcança — ``"quatro"`` não é número. No
    banco inicial as duas vias concordam em todos os itens; se um dia divergirem, quem decide é
    a declaração do banco, e a divergência estará visível no arquivo em vez de enterrada aqui.

    Os dois ramos de perfil incompleto — sem tolerância, gabarito não numérico — são
    inalcançáveis por um item construído pelo modelo de §3.1 com ``tipo_gabarito = NUMERICO``
    no primeiro caso, e **alcançáveis** no segundo: nem o modelo nem o carregador verificam que
    o gabarito de item numérico é um número (ver o relato da tarefa). Os dois falham fechado.
    """
    if _coincide_com_forma_declarada(item, texto):
        return _julgado(Resultado.ACERTO, JUSTIFICATIVA_DE_FORMA_DECLARADA)
    if item.tolerancia is None:
        return _julgado(Resultado.ERRO, JUSTIFICATIVA_DE_TOLERANCIA_AUSENTE)
    gabarito = interpretar_decimal(item.gabarito)
    if gabarito is None:
        return _julgado(Resultado.ERRO, JUSTIFICATIVA_DE_GABARITO_NAO_NUMERICO)
    valor = interpretar_decimal(_sem_unidade_declarada(texto, item))
    if valor is None:
        return _julgado(Resultado.ERRO, JUSTIFICATIVA_DE_RESPOSTA_NAO_NUMERICA)
    dentro = dentro_da_tolerancia(valor, gabarito, item.tolerancia)
    return _julgado(
        Resultado.ACERTO if dentro else Resultado.ERRO,
        _justificativa_numerica(item.tolerancia, dentro=dentro),
    )


def _julgar_alternativa(item: Item, texto: str) -> Julgamento:
    """Compara a resposta exatamente com a alternativa correta e suas variações (R4.2).

    Exata é exata: ``"a"`` não casa com ``"A)"``, e dobrar a caixa aqui seria inventar uma
    equivalência que o item não declarou. O item que quiser aceitar o rótulo sozinho ou em
    caixa baixa declara a forma em ``variacoes_gabarito``, que é o lugar onde essa decisão é
    revisável por quem escreve o banco. Nenhuma unidade é removida: alternativa não tem
    grandeza, e o banco recusa ``unidade`` sem sentido no tipo.
    """
    acertou = _coincide_com_forma_declarada(item, texto)
    return _julgado(
        Resultado.ACERTO if acertou else Resultado.ERRO,
        JUSTIFICATIVA_DE_ALTERNATIVA_CORRETA if acertou else JUSTIFICATIVA_DE_ALTERNATIVA_INCORRETA,
    )


def _encaminhar_para_rubrica(texto: str) -> Julgamento:
    """Encaminha a resposta textual inteira a avaliação humana, sem veredito (R4.7, §7.3).

    O item ``TEXTUAL`` do modelo de §3.1 não tem parte de gabarito objetivo — tem gabarito
    textual e conjuntos de termos essenciais, que R2.11 declara para a guarda —, então a
    resposta inteira é uma única parte para a rubrica. ``partes_para_rubrica`` é coleção, e não
    um campo de texto, porque o projeto STEAM de R13.2 tem mais de uma parte; para um ``Item``
    há exatamente uma.

    Nenhum veredito automático é fabricado: ver ``ResultadoDoJulgamento``.
    """
    return Julgamento(
        resultado=Indisponivel(MOTIVO_AGUARDANDO_RUBRICA),
        justificativa=JUSTIFICATIVA_DE_RUBRICA,
        motivo_rejeicao=None,
        partes_para_rubrica=(texto,),
    )


def _julgado(resultado: Resultado, justificativa: str) -> Julgamento:
    """Julgamento com veredito: sem motivo de rejeição e sem parte para rubrica."""
    return Julgamento(
        resultado=resultado,
        justificativa=justificativa,
        motivo_rejeicao=None,
        partes_para_rubrica=(),
    )
