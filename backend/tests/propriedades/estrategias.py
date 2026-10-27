"""Geradores nomeados do Hypothesis, compartilhados pelos arquivos de propriedade (§6.3).

Módulo único importado pelos testes de propriedade. Geradores **nomeados**, nunca `st.builds`
solto no corpo do teste, e a razão não é estilo: quando uma propriedade falha, o que chega a
quem diagnostica é o contraexemplo **encolhido**, e o encolhimento só produz algo legível se o
gerador conhecer o domínio. `st.builds(Item, ...)` montado no teste encolhe para o primeiro
valor que o construtor aceita, que em um item com dezesseis campos acoplados é um objeto que
não se lê — e um contraexemplo ilegível transforma uma propriedade vermelha em meia hora de
arqueologia. Os geradores daqui encolhem para o item mínimo compreensível: identificador de um
caractere, dificuldade 1, nenhuma coleção opcional, enunciado igual ao primeiro fragmento
declarado. `test_estrategias.py` afirma isso como teste, em vez de deixar como intenção.

## A restrição que decide o valor do módulo

O item gerado tem de ser um item que **`carregar` aceitaria**. `serializar_canonico` não
revalida o banco: ele escreve o que recebe. Um gerador que produzisse item inválido faria as
Propriedades 29 e 30 falharem pelo motivo errado — a propriedade reprovaria por item
malformado, não por defeito de serialização, e o contraexemplo apontaria para o lugar errado.
Daí a divisão em dois geradores de item, e não um:

- `itens` cobre o domínio inteiro de `Item`, **inclusive** etapas com `pratica_assistida`. Um
  item praticado exige equivalente isomorfo e item de transferência associados (R2.2, R2.6), e
  isso é propriedade do **banco**, não do item: serializado sozinho, ele é recusado por
  `ErroDeAssociacaoAusente`. É o gerador certo para quem monta o banco e para quem exercita o
  modelo em memória;
- `itens_carregaveis` é o mesmo gerador com `pratica_assistida` fora de `etapas_permitidas`, e
  o item resultante sobrevive a `serializar_canonico` + `carregar` **sozinho**, sem par. É o
  gerador das Propriedades 29 e 30.

Fora da associação, tudo o que a carga impõe está honrado por construção, não por filtro:
`id`, `habilidade_alvo` e `incognita` na forma de `PADRAO_DE_IDENTIFICADOR`; `tolerancia` só e
sempre em `numerico`; `termos_essenciais` só e sempre em `textual`, nenhum conjunto vazio;
`sinonimos_unidade` só com `unidade` declarada; `etapas_permitidas` não vazio; `dicas` em
exatamente L1 a L4, todas não vazias; `dificuldade` de 1 a 5; `tamanho_max_resposta` de 1 em
diante; coleções sem repetição. Gerar e filtrar seria a outra saída, e é pior em dois sentidos:
desperdiça exemplos e deixa o encolhimento perseguir a borda do filtro em vez do defeito.

**Coleção já sai na forma canônica.** `sinonimos_unidade`, `variacoes_gabarito` e
`termos_essenciais` são conjuntos escritos como lista: a leitura os devolve ordenados e sem
repetição (`_Leitor.conjunto_de_textos`). Gerar fora de ordem produziria item que vai e volta
**diferente** de si mesmo, e a comparação estrutural de R3.4 falharia sem que nada estivesse
errado no serializador. Quem precisa de ordem embaralhada — a ênfase de P30 em "coleções em
ordem arbitrária" — embaralha na própria propriedade, onde a intenção fica visível.

## Texto

`FRAGMENTOS_ADVERSARIOS` são as quinze classes por onde a escrita de TOML pode quebrar, as
mesmas de `backend/tests/unidade/test_serializador_canonico.py`. A duplicação é deliberada:
aquele arquivo as usa como casos dirigidos com texto esperado à mão, e este as usa como
material de composição; importar de um teste para o outro acoplaria dois arquivos que mudam por
razões diferentes. Elas entram em `enunciado`, `gabarito`, `unidade`, nas coleções e nas dicas,
e que isso atravessa a carga nos três tipos de gabarito é o que
`test_o_item_carregavel_sobrevive_a_serializacao_e_a_carga` afirma.

**Validates: Requirements 3.4, 3.5, 29.1, 29.2, 29.3**
"""

from __future__ import annotations

import string
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from hypothesis import strategies as st
from hypothesis.strategies import DrawFn, SearchStrategy

from adia.nucleo.itens.modelo import DIFICULDADE_MAXIMA, DIFICULDADE_MINIMA, Item, TipoGabarito
from adia.tipos import Condicao, Etapa, Indisponivel, Medida, Nivel

# --------------------------------------------------------------------------- #
# Constantes de geração
# --------------------------------------------------------------------------- #

QUATRO_CASAS: Final = Decimal("0.0001")
"""Quantização de R9.12: a regra compara limiares com quatro casas e `ROUND_HALF_UP`."""

FRONTEIRAS: Final = (
    Decimal("0.0000"),
    Decimal("0.2000"),
    Decimal("0.2500"),
    Decimal("0.4000"),
    Decimal("0.8000"),
    Decimal("1.0000"),
)
"""Valores em que `≥` trocado por `>` muda a decisão ou o aviso (R9.2 a R9.5, R11.8).

Amostragem uniforme em quatro casas sorteia `0,2500` uma vez em dez mil; reforçar a fronteira
é o que torna o caso de igualdade exata alcançável em cem exemplos.
"""

PESO_DE_INDISPONIBILIDADE: Final = 0.15
"""Fração de `Medida` sorteada como `Indisponivel`. Decisão operacional de §6.3."""

_ESCALA_DO_SORTEIO: Final = 100
"""Denominador do sorteio ponderado de `medidas`, em centésimos."""

TAMANHO_MAXIMO_DE_IDENTIFICADOR: Final = 64
"""Teto de `PADRAO_DE_IDENTIFICADOR`, em caracteres."""

INICIAIS_DE_IDENTIFICADOR: Final = string.ascii_letters + string.digits
CARACTERES_DE_IDENTIFICADOR: Final = INICIAIS_DE_IDENTIFICADOR + "._-"
"""Alfabeto de `id`, `habilidade_alvo` e `incognita`: ASCII, começando por letra ou dígito."""

TAMANHO_MAXIMO_DE_RESPOSTA: Final = 2000
"""Teto de `tamanho_max_resposta` nos geradores. A gramática só exige 1 ou mais; um teto
mantém o valor plausível e o contraexemplo legível."""

MOTIVOS_DE_INDISPONIBILIDADE: Final = (
    "denominador zero",
    "escopo sem resposta registrada",
    "métrica de entrada indisponível",
)
"""Os três motivos que R11.7 reconhece. `Indisponivel` recusa motivo vazio."""

FRAGMENTOS_PT_BR: Final = (
    "Resolva a equação 2x + 3 = 11 e informe o valor de x.",
    "Qual é a área do triângulo de base 6 cm e altura 4 cm?",
    "Mostre que x ∈ ℝ satisfaz −3 ≤ x ≤ 7, justificando cada passo.",
    "A razão entre as duas grandezas é 3/4; explique o que isso significa.",
    "Calcule ∑ dos cinco primeiros números ímpares e compare com 5².",
    "Por que a operação inversa preserva a igualdade dos dois lados?",
)
"""Enunciados em pt-BR com acentuação, pontuação e símbolos matemáticos (§5.5, P29).

Acentuação e símbolo não são enfeite de realismo: `ção`, `−` (menos matemático, distinto do
hífen), `≤`, `∑` e `ℝ` ocupam mais de um byte em UTF-8 e são onde a codificação do arquivo
aparece. O primeiro da lista é o alvo do encolhimento, e é por isso que ele é o caso semente
de `2x + 3 = 11` em vez de um texto qualquer.
"""

FRAGMENTOS_DE_DICA: Final = (
    "O que a igualdade afirma sobre os dois lados?",
    "Isto é uma equação do primeiro grau com uma incógnita.",
    "Isole a incógnita aplicando a mesma operação aos dois lados.",
    "Em 5y + 2 = 17, subtraia 2 dos dois lados e divida por 5.",
)
"""Um fragmento por grau de diretividade de L1 a L4 (R6.1), para que a dica gerada se leia
como dica. A carga só exige texto não vazio; o resto é legibilidade do contraexemplo."""

PALAVRAS_PT_BR: Final = (
    "isolar",
    "incógnita",
    "equação",
    "coeficiente",
    "operação inversa",
    "quatro",
    "±4",
    "x ∈ ℝ",
    "≤ 11",
)
"""Textos curtos de coleção: variação de gabarito, termo essencial, sinônimo de unidade."""

UNIDADES: Final = ("reais", "metros", "cm²", "m/s", "°C", "kg")
"""Unidades declaradas. `cm²`, `°C` e `m/s` existem para que o campo não seja só ASCII."""

ROTULOS_DE_ALTERNATIVA: Final = ("A", "B", "C", "D", "E")
"""Rótulos de alternativa, na forma em que o gabarito de alternativa os escreve."""

FRAGMENTOS_ADVERSARIOS: Final = (
    'aspas "duplas" no meio da frase',
    'três """ aspas seguidas, que fechariam o bloco',
    'seis """""" aspas seguidas',
    "barra invertida \\ e a dupla \\\\",
    'termina em aspas "',
    'termina em três """',
    "termina em barra invertida \\",
    "duas linhas\ne uma quebra no fim\n",
    "\nquebra de linha no começo",
    "espaços no fim   ",
    "tabulação\tno meio",
    "controles \x00\x01\x1f\x7f no meio",
    "retorno de carro \r\n do Windows",
    "acentuação e símbolos: ção, ±, −, ≤, ∑, ∈ ℝ",
    "enunciado longo " * 60,
)
"""As quinze classes de texto que quebram a escrita de TOML, não as quinze mais realistas.

São as mesmas de `backend/tests/unidade/test_serializador_canonico.py`, e cobrem o que P30
enfatiza — aspas, barras invertidas, texto que não cabe em uma linha — mais o que só aparece
olhando o byte: controle e retorno de carro. Retorno de carro é o caso instrutivo: literal no
arquivo, ele seria apagado pela normalização de `\\r\\n` da leitura, e o texto voltaria sem ele.
"""

POSICOES_DO_FRAGMENTO: Final = ("fim", "comeco")
"""Onde o fragmento adversário entra no texto. `fim` primeiro porque é o caso difícil: texto
terminado em aspa, em barra invertida, em espaço ou em quebra de linha é onde o delimitador de
fechamento do bloco encosta no conteúdo."""


# --------------------------------------------------------------------------- #
# Texto
# --------------------------------------------------------------------------- #


@st.composite
def textos_pt_br(draw: DrawFn, linhas_maximas: int = 3) -> str:
    """Texto em pt-BR, de uma a `linhas_maximas` linhas, com acentuação e símbolos (§5.5).

    Multilinha de propósito: o serializador escreve `enunciado` e dicas em bloco `\"\"\"`, e é a
    quebra de linha real que distingue o bloco da cadeia de uma linha. Encolhe para uma linha
    igual a `FRAGMENTOS_PT_BR[0]`.
    """
    linhas = draw(st.lists(st.sampled_from(FRAGMENTOS_PT_BR), min_size=1, max_size=linhas_maximas))
    return "\n".join(linhas)


@st.composite
def textos_adversarios(draw: DrawFn, nucleo: SearchStrategy[str] | None = None) -> str:
    """Texto com um dos quinze fragmentos adversários acoplado a um núcleo legível.

    O núcleo garante que o resultado tenha conteúdo não vazio mesmo quando o fragmento é só
    espaço em branco decorado — `texto` da carga recusa cadeia que `strip()` esvazia (R2.1).
    Acoplar em vez de usar o fragmento puro também é o que mantém o caso realista: o que
    quebra o escritor é a aspa **dentro** de uma frase, não a aspa isolada.
    """
    base = draw(nucleo if nucleo is not None else textos_pt_br())
    fragmento = draw(st.sampled_from(FRAGMENTOS_ADVERSARIOS))
    if draw(st.sampled_from(POSICOES_DO_FRAGMENTO)) == "fim":
        return f"{base} {fragmento}"
    return f"{fragmento} {base}"


def textos_de_conteudo() -> SearchStrategy[str]:
    """Texto de campo livre: pt-BR limpo ou pt-BR com fragmento adversário.

    Encolhe para o lado limpo, que é a ordem certa: quando a propriedade falha com texto
    adversário, a falha é sobre escape; quando falha com texto limpo, é sobre outra coisa, e
    descobrir qual das duas é o primeiro passo do diagnóstico.
    """
    return st.one_of(textos_pt_br(), textos_adversarios())


def textos_curtos() -> SearchStrategy[str]:
    """Texto de elemento de coleção: palavra ou expressão curta, limpa ou adversária."""
    curtos = st.sampled_from(PALAVRAS_PT_BR)
    return st.one_of(curtos, textos_adversarios(nucleo=curtos))


def enunciados() -> SearchStrategy[str]:
    """Enunciado de item em pt-BR, com acentuação e símbolos matemáticos (§5.5, P29).

    De uma a três linhas: o enunciado multilinha é o que exercita a cadeia em bloco `\"\"\"` do
    serializador, e o de uma linha é o caso para o qual o encolhimento caminha. Nome próprio
    ainda que o corpo seja `textos_de_conteudo`, porque é o nome que aparece no contraexemplo —
    e porque o dia em que o enunciado ganhar exigência própria, muda aqui e em nenhum outro
    lugar.
    """
    return textos_de_conteudo()


def textos_de_dica() -> SearchStrategy[str]:
    """Texto de uma dica pré-escrita, limpo ou com fragmento adversário."""
    dicas = st.sampled_from(FRAGMENTOS_DE_DICA)
    return st.one_of(dicas, textos_adversarios(nucleo=dicas))


# --------------------------------------------------------------------------- #
# Enumerações do domínio
# --------------------------------------------------------------------------- #


def niveis(minimo: Nivel = Nivel.L1, maximo: Nivel = Nivel.L4) -> SearchStrategy[Nivel]:
    """Nível de assistência na faixa fechada dada, encolhendo para `minimo`.

    Os parâmetros servem às propriedades de saturação, que precisam sortear dentro e fora da
    borda: P23 pede o par `(teto vigente, nível pedido)` com o pedido **acima** do teto, e isso
    é `niveis(maximo=teto)` contra `niveis(minimo=teto)`.
    """
    if minimo > maximo:
        raise ValueError(f"faixa de níveis vazia: {minimo.name} > {maximo.name}")
    return st.sampled_from([nivel for nivel in Nivel if minimo <= nivel <= maximo])


def etapas(excluir: Collection[Etapa] = ()) -> SearchStrategy[Etapa]:
    """Etapa do CognitiveLoop, opcionalmente sem as etapas excluídas.

    `excluir` existe porque algumas afirmações valem só de um lado da fronteira sem IA: R8.6
    filtra proficiência por `ETAPAS_SEM_IA`, e R2.2 só exige pareamento do item praticado.
    """
    candidatas = [etapa for etapa in Etapa if etapa not in excluir]
    if not candidatas:
        raise ValueError("nenhuma etapa restou depois da exclusão")
    return st.sampled_from(candidatas)


def etapas_permitidas(excluir: Collection[Etapa] = ()) -> SearchStrategy[frozenset[Etapa]]:
    """Conjunto **não vazio** de etapas permitidas (R2.4), encolhendo para um único membro.

    Não vazio por construção, e não por filtro: `etapas_permitidas` vazio é um dos erros de
    carga nomeados (`ErroDeEtapasVazias`), e um gerador que o produzisse faria toda propriedade
    de ida e volta falhar pelo motivo errado.
    """
    return st.sets(etapas(excluir), min_size=1).map(frozenset)


def condicoes() -> SearchStrategy[Condicao]:
    """Condição experimental atribuída à sessão (R14.1 a R14.4)."""
    return st.sampled_from(Condicao)


def tipos_de_gabarito() -> SearchStrategy[TipoGabarito]:
    """Natureza do gabarito: numérico, de alternativa ou textual."""
    return st.sampled_from(TipoGabarito)


# --------------------------------------------------------------------------- #
# Escalares de métrica
# --------------------------------------------------------------------------- #


def proporcoes(
    minimo: Decimal = Decimal("0"),
    maximo: Decimal = Decimal("1"),
    reforcar_fronteiras: bool = True,
) -> SearchStrategy[Decimal]:
    """Proporção em `Decimal` com **quatro casas**, as de R9.12, com fronteira reforçada.

    Quatro casas e nunca `float`: a regra de regulação compara `acerto_independente`, `gap` e
    viés com limiares depois de quantizar a quatro casas, e um `0,25` que chegasse como
    `0,2500000000000000138` dispararia *onloading* onde R9.12 diz que não dispara. O valor
    gerado já está na forma em que `decidir` compara.

    Com `reforcar_fronteiras`, a estratégia é a união de `FRONTEIRAS` com a uniforme. É o que
    torna alcançável o caso em que `≥` trocado por `>` muda a decisão.
    """
    if minimo > maximo:
        raise ValueError(f"faixa de proporções vazia: {minimo} > {maximo}")
    uniforme = st.decimals(
        min_value=minimo, max_value=maximo, places=4, allow_nan=False, allow_infinity=False
    )
    dentro = [valor for valor in FRONTEIRAS if minimo <= valor <= maximo]
    if not reforcar_fronteiras or not dentro:
        return uniforme
    return st.one_of(st.sampled_from(dentro), uniforme)


def indisponiveis() -> SearchStrategy[Indisponivel]:
    """Ausência declarada de base para afirmar um valor, com motivo não vazio (R11.7)."""
    return st.builds(Indisponivel, motivo=st.sampled_from(MOTIVOS_DE_INDISPONIBILIDADE))


@st.composite
def medidas(draw: DrawFn, indisponibilidade: float = PESO_DE_INDISPONIBILIDADE) -> Medida:
    """Valor de métrica: número exato ou `Indisponivel`, na proporção dada (R11.7).

    É o gerador que torna a Propriedade 13 verificável: métrica indisponível tem de propagar
    como indisponível, nunca virar zero. Propriedade de métrica que use `proporcoes` em vez de
    `medidas` testa o caminho em que tudo está disponível, e nada além dele.

    O peso é sorteado como inteiro em centésimos, e não como `float`: a proporção fica
    explícita no código, reprodutível e sem a aritmética binária que o resto do protótipo
    recusa. `indisponibilidade = 0` e `= 1` são os dois extremos úteis — o primeiro dá à
    propriedade de métrica o caminho em que tudo foi medido, o segundo dá a P13 o caso em que
    toda entrada está indisponível.

    O lado para o qual o encolhimento caminha é o **indisponível**, porque `Indisponivel` é o
    valor estruturalmente mais simples da união: duas escolhas contra as três ou mais de um
    decimal com quatro casas. Vale saber ao ler um contraexemplo de métrica — o primeiro a
    conferir é se a indisponibilidade é parte do defeito ou só o fundo do poço do encolhimento.
    """
    if not 0.0 <= indisponibilidade <= 1.0:
        raise ValueError(f"proporção de indisponibilidade fora de [0, 1]: {indisponibilidade}")
    corte = _ESCALA_DO_SORTEIO - round(indisponibilidade * _ESCALA_DO_SORTEIO)
    sorteio = draw(st.integers(min_value=0, max_value=_ESCALA_DO_SORTEIO - 1))
    if sorteio >= corte:
        return draw(indisponiveis())
    return draw(proporcoes())


# --------------------------------------------------------------------------- #
# Campos de item
# --------------------------------------------------------------------------- #


@st.composite
def identificadores(draw: DrawFn, tamanho_maximo: int = TAMANHO_MAXIMO_DE_IDENTIFICADOR) -> str:
    """Texto na forma de `PADRAO_DE_IDENTIFICADOR`: ASCII, até 64 caracteres (R3.6).

    A primeira posição é sorteada separadamente porque a gramática exige letra ou dígito ali —
    `.bordas` e `-x` não são identificadores. Encolhe para um caractere, o que mantém legível o
    contraexemplo de banco com vários itens.

    Unicidade é propriedade do **conjunto**, não do gerador: `id` é único em todo o banco
    (R3.6), e dois itens gerados independentemente podem colidir. Quem monta banco sorteia os
    identificadores com `unique=True` ou os distingue por prefixo.
    """
    if not 1 <= tamanho_maximo <= TAMANHO_MAXIMO_DE_IDENTIFICADOR:
        raise ValueError(f"tamanho de identificador fora de 1 a {TAMANHO_MAXIMO_DE_IDENTIFICADOR}")
    inicial = draw(st.sampled_from(INICIAIS_DE_IDENTIFICADOR))
    resto = draw(st.text(alphabet=CARACTERES_DE_IDENTIFICADOR, max_size=tamanho_maximo - 1))
    return inicial + resto


def dificuldades() -> SearchStrategy[int]:
    """Dificuldade na escala ordinal de 1 a 5 (R2.1, DO-01)."""
    return st.integers(min_value=DIFICULDADE_MINIMA, max_value=DIFICULDADE_MAXIMA)


def tamanhos_max_resposta() -> SearchStrategy[int]:
    """Tamanho máximo de resposta, em caracteres: 1 ou mais (R2.1)."""
    return st.integers(min_value=1, max_value=TAMANHO_MAXIMO_DE_RESPOSTA)


def tolerancias() -> SearchStrategy[Decimal]:
    """Tolerância numérica não negativa, em `Decimal` (R2.8).

    Encolhe para zero, que é a fronteira interessante: tolerância zero é comparação exata, e é
    onde um `≤` trocado por `<` em `corrigir` muda o acerto. Os valores notáveis entram ao lado
    da uniforme porque `0.05` é a tolerância do item semente e `1` é o caso em que a tolerância
    engole a diferença.

    Sem expoente, por construção: `PADRAO_DE_DECIMAL` não admite notação científica, e a forma
    canônica de `decimal_canonico` é `format(valor.normalize(), "f")`.
    """
    casas = st.integers(min_value=0, max_value=6)
    uniforme = casas.flatmap(
        lambda quantas: st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("100"),
            places=quantas,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    notaveis = st.sampled_from((Decimal("0"), Decimal("0.05"), Decimal("0.5"), Decimal("1")))
    return st.one_of(notaveis, uniforme)


def unidades() -> SearchStrategy[str]:
    """Unidade declarada do item, texto não vazio."""
    return st.sampled_from(UNIDADES)


def sinonimos_de_unidade(maximo: int = 2) -> SearchStrategy[tuple[str, ...]]:
    """Conjunto de sinônimos da unidade, já ordenado e sem repetição.

    Só tem sentido com `unidade` declarada — a carga recusa sinônimo órfão —, e é
    `perfis_de_gabarito` que mantém os dois juntos.
    """
    return _conjunto_de_textos(maximo)


def variacoes_de_gabarito(maximo: int = 3) -> SearchStrategy[tuple[str, ...]]:
    """Conjunto de variações aceitas do gabarito, já ordenado e sem repetição (R2.1)."""
    return _conjunto_de_textos(maximo)


def _conjunto_de_textos(maximo: int) -> SearchStrategy[tuple[str, ...]]:
    """Coleção de textos na forma canônica: ordenada, sem repetição, possivelmente vazia.

    Canônica na origem porque a leitura devolve `tuple(sorted(valores))` e recusa repetição: um
    conjunto gerado fora de ordem produziria item que vai e volta diferente de si mesmo, e a
    comparação estrutural de R3.4 falharia sem defeito no serializador.
    """
    return st.lists(textos_curtos(), max_size=maximo, unique=True).map(conjunto_ordenado)


def conjunto_ordenado(valores: list[str]) -> tuple[str, ...]:
    """Coleção de textos na forma em que a leitura a devolve: ordenada e sem repetição.

    Nomeada em vez de `lambda` porque o mapeador aparece no contraexemplo encolhido, e
    `conjunto_ordenado(['a', 'b'])` se lê onde `<lambda>(['a', 'b'])` não diz nada.
    """
    return tuple(sorted(set(valores)))


def conjuntos_de_termos_essenciais(
    conjuntos: int = 2, termos_por_conjunto: int = 3
) -> SearchStrategy[tuple[tuple[str, ...], ...]]:
    """Conjunto **não vazio** de conjuntos não vazios de termos essenciais (R2.11, R7.6).

    Dois níveis, canônicos nos dois: a leitura ordena o interno, ordena o externo e recusa
    repetição em ambos. Nenhum conjunto vazio, porque conjunto vazio é erro de carga — e,
    antes disso, porque é o que deixaria o detector de termos essenciais da guarda sem nada
    contra o que comparar.
    """
    interno = st.lists(
        textos_curtos(), min_size=1, max_size=termos_por_conjunto, unique=True
    ).map(conjunto_ordenado)
    return st.lists(interno, min_size=1, max_size=conjuntos, unique=True).map(conjuntos_ordenados)


def conjuntos_ordenados(grupos: list[tuple[str, ...]]) -> tuple[tuple[str, ...], ...]:
    """Coleção de coleções canônica no nível externo, com o interno já canônico."""
    return tuple(sorted(set(grupos)))


def gabaritos_numericos() -> SearchStrategy[str]:
    """Gabarito de item numérico: decimal em notação simples, escrito como texto.

    Texto, e não `Decimal`, porque `gabarito` é campo de texto na gramática — é o
    `Motor_de_Correção` que o interpreta sob a tolerância declarada (R4.2). Notação sem
    expoente para que o que está no arquivo seja o que um revisor humano lê.
    """
    casas = st.integers(min_value=0, max_value=3)
    return casas.flatmap(
        lambda quantas: st.decimals(
            min_value=Decimal("-1000"),
            max_value=Decimal("1000"),
            places=quantas,
            allow_nan=False,
            allow_infinity=False,
        )
    ).map(texto_decimal)


def texto_decimal(valor: Decimal) -> str:
    """Decimal em notação simples, sem expoente — a mesma forma de `decimal_canonico`."""
    return format(valor, "f")


@st.composite
def gabaritos_de_alternativa(draw: DrawFn) -> str:
    """Gabarito de item de alternativa: rótulo e texto da opção correta (§6.3)."""
    rotulo = draw(st.sampled_from(ROTULOS_DE_ALTERNATIVA))
    texto = draw(st.sampled_from(PALAVRAS_PT_BR))
    return f"{rotulo}) {texto}"


def gabaritos_textuais() -> SearchStrategy[str]:
    """Gabarito de item textual: resposta esperada em pt-BR, encaminhada a rubrica (R4.6)."""
    return textos_de_conteudo()


def gabaritos(tipo: TipoGabarito) -> SearchStrategy[str]:
    """Gabarito na forma que o tipo declarado exige."""
    match tipo:
        case TipoGabarito.NUMERICO:
            return gabaritos_numericos()
        case TipoGabarito.ALTERNATIVA:
            return gabaritos_de_alternativa()
        case TipoGabarito.TEXTUAL:
            return gabaritos_textuais()


def dicas_pre_escritas(textos: SearchStrategy[str] | None = None) -> SearchStrategy[Mapping[Nivel, str]]:
    """Catálogo de dicas com **exatamente** um texto não vazio por nível de L1 a L4 (R2.1).

    `st.fixed_dictionaries` sobre `Nivel` em vez de um dicionário sorteado: nível faltando é
    erro de carga (`ErroDeDicaAusente`) e também invariante do modelo, então um gerador que o
    produzisse não chegaria a construir um `Item`. A lacuna de que P28 precisa é geração de
    **catálogo**, não de item, e não vive aqui.
    """
    conteudo = textos_de_dica() if textos is None else textos
    return st.fixed_dictionaries({nivel: conteudo for nivel in Nivel}).map(catalogo_de_dicas)


def catalogo_de_dicas(dicas: dict[Nivel, str]) -> Mapping[Nivel, str]:
    """Catálogo imutável, na mesma forma que o carregador publica.

    Função nomeada, e não `MappingProxyType` direto nem `lambda`, porque o nome do mapeador
    aparece no contraexemplo: `dicas=catalogo_de_dicas({...})` se lê, `dicas=<lambda>({...})`
    não.
    """
    return MappingProxyType(dict(dicas))


# --------------------------------------------------------------------------- #
# Perfil de gabarito: os campos que o tipo acopla
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PerfilDeGabarito:
    """Os campos de `Item` que o tipo de gabarito mantém acoplados (R2.8, R2.11).

    Existem juntos porque a validade é conjunta, não campo a campo: `tolerancia` é obrigatória
    em `numerico` e proibida fora dele, `termos_essenciais` é exigido em `textual`, e
    `sinonimos_unidade` sem `unidade` é recusado. Sortear os cinco de forma independente
    produziria, na maioria dos exemplos, um item que a carga rejeita — e o encolhimento
    perseguiria a borda da validade em vez do defeito.
    """

    tipo_gabarito: TipoGabarito
    gabarito: str
    tolerancia: Decimal | None
    unidade: str | None
    sinonimos_unidade: tuple[str, ...]
    variacoes_gabarito: tuple[str, ...]
    termos_essenciais: tuple[tuple[str, ...], ...]


@st.composite
def perfis_de_gabarito(
    draw: DrawFn,
    tipo: TipoGabarito | None = None,
    com_unidade: bool | None = None,
    variacoes: int = 3,
    conjuntos_essenciais: int = 2,
) -> PerfilDeGabarito:
    """Perfil coerente com o tipo de gabarito, nos três tipos (§6.3).

    `tipo` fixa o tipo; `None` sorteia entre os três. `com_unidade` força a presença ou a
    ausência de `unidade`; `None` sorteia — e, quando a unidade não existe, os sinônimos são
    vazios por construção, que é a única combinação que a carga aceita.
    """
    escolhido = draw(tipos_de_gabarito()) if tipo is None else tipo
    quer_unidade = draw(st.booleans()) if com_unidade is None else com_unidade
    unidade = draw(unidades()) if quer_unidade else None
    return PerfilDeGabarito(
        tipo_gabarito=escolhido,
        gabarito=draw(gabaritos(escolhido)),
        tolerancia=draw(tolerancias()) if escolhido is TipoGabarito.NUMERICO else None,
        unidade=unidade,
        sinonimos_unidade=draw(sinonimos_de_unidade()) if unidade is not None else (),
        variacoes_gabarito=draw(variacoes_de_gabarito(maximo=variacoes)),
        termos_essenciais=(
            draw(conjuntos_de_termos_essenciais(conjuntos=conjuntos_essenciais))
            if escolhido is TipoGabarito.TEXTUAL
            else ()
        ),
    )


# --------------------------------------------------------------------------- #
# Item
# --------------------------------------------------------------------------- #


@st.composite
def itens(
    draw: DrawFn,
    tipo: TipoGabarito | None = None,
    com_unidade: bool | None = None,
    variacoes: int = 3,
    conjuntos_essenciais: int = 2,
    conjunto_de_etapas: SearchStrategy[frozenset[Etapa]] | None = None,
) -> Item:
    """Item do banco, cobrindo o domínio inteiro de `Item` (§3.1, R2.1).

    Toda invariante do **item** está honrada por construção: identificadores na forma de
    `PADRAO_DE_IDENTIFICADOR`, perfil coerente com o tipo de gabarito, coleções canônicas,
    dicas em exatamente L1 a L4, dificuldade de 1 a 5 e `tamanho_max_resposta` positivo.

    **O que este gerador pode produzir e a carga recusaria.** `etapas_permitidas` pode conter
    `pratica_assistida`, e aí o item é praticado: R2.2 e R2.6 exigem dele um equivalente
    isomorfo e um item de transferência da mesma habilidade, declarados como relação. Isso é
    invariante do **banco**, não do item, e o `Item` em memória é perfeitamente válido — mas
    serializado sozinho ele é recusado com `ErroDeAssociacaoAusente`. Para o item que sobrevive
    a `serializar_canonico` + `carregar` **sem par**, use `itens_carregaveis`.

    `tamanho_max_resposta` é sorteado sem relação com o tamanho do gabarito, de propósito: a
    gramática não acopla os dois, e o item em que a resposta correta não caberia no limite é
    exatamente o caso que o `Motor_de_Correção` tem de tratar como erro declarado (R4.6).
    """
    perfil = draw(
        perfis_de_gabarito(
            tipo=tipo,
            com_unidade=com_unidade,
            variacoes=variacoes,
            conjuntos_essenciais=conjuntos_essenciais,
        )
    )
    return Item(
        id=draw(identificadores()),
        enunciado=draw(enunciados()),
        habilidade_alvo=draw(identificadores()),
        dificuldade=draw(dificuldades()),
        tamanho_max_resposta=draw(tamanhos_max_resposta()),
        tipo_gabarito=perfil.tipo_gabarito,
        gabarito=perfil.gabarito,
        tolerancia=perfil.tolerancia,
        unidade=perfil.unidade,
        sinonimos_unidade=perfil.sinonimos_unidade,
        variacoes_gabarito=perfil.variacoes_gabarito,
        termos_essenciais=perfil.termos_essenciais,
        incognita=draw(st.none() | identificadores()),
        etapas_permitidas=draw(etapas_permitidas() if conjunto_de_etapas is None else conjunto_de_etapas),
        transferencia=draw(st.booleans()),
        dicas=draw(dicas_pre_escritas()),
    )


def itens_carregaveis(
    tipo: TipoGabarito | None = None,
    com_unidade: bool | None = None,
    variacoes: int = 3,
    conjuntos_essenciais: int = 2,
) -> SearchStrategy[Item]:
    """Item que `carregar` aceita **sozinho**, sem nenhum item par no arquivo (R3.1).

    É `itens` com `pratica_assistida` fora de `etapas_permitidas`, e a restrição é a única:
    todo o resto do domínio segue coberto, inclusive `transferencia = true`, que sem relação
    declarada não entra em conflito nenhum (R2.9).

    É o gerador das Propriedades 29 e 30. `serializar_canonico` não revalida o banco, então um
    item que a carga recusasse faria as duas falharem por item malformado em vez de por defeito
    de serialização — e o contraexemplo apontaria para o lugar errado.
    """
    return itens(
        tipo=tipo,
        com_unidade=com_unidade,
        variacoes=variacoes,
        conjuntos_essenciais=conjuntos_essenciais,
        conjunto_de_etapas=etapas_permitidas(excluir=(Etapa.PRATICA_ASSISTIDA,)),
    )
