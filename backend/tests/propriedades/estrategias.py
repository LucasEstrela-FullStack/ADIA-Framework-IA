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
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Protocol

from hypothesis import strategies as st
from hypothesis.strategies import DrawFn, SearchStrategy

from adia.nucleo.itens.banco import TRANSFERENCIAS_NO_CONJUNTO
from adia.nucleo.itens.carregador import CargaConcluida
from adia.nucleo.itens.modelo import (
    DIFICULDADE_MAXIMA,
    DIFICULDADE_MINIMA,
    EQUIVALENTE,
    TRANSFERENCIA,
    Item,
    Relacao,
    TipoGabarito,
    equivalente_qualifica,
    transferencia_qualifica,
)
from adia.tipos import (
    CICLO_DO_POSTESTE,
    ETAPAS_SEM_IA,
    Condicao,
    Etapa,
    Indisponivel,
    Medida,
    Nivel,
)

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

# --------------------------------------------------------------------------- #
# Banco: o conjunto de itens, que é onde a unicidade de `id` vive
# --------------------------------------------------------------------------- #
#
# As duas peças abaixo nasceram em `p29_item_ida_e_volta.py`, com a fronteira de nome que
# aquele arquivo declara — o que é candidato a migrar fica público, o encanamento do teste fica
# privado —, e migraram para cá quando P30 (tarefa 3.6) passou a precisar das duas. Unicidade de
# `id` não é substância de nenhuma das duas propriedades: é exigência do **banco** (R3.6), que
# vale para qualquer propriedade que monte um. Repetida em cada arquivo, ela é o tipo de
# restrição que divergiria sem ninguém notar — e o preço da divergência é uma propriedade
# reprovando por banco inválido em vez de pelo defeito que ela procura.


def identificador_de(item: Item) -> str:
    """Chave de unicidade e de ordenação do banco: o `id` do item (R3.6).

    Função nomeada em vez de `lambda` por dois motivos. O primeiro é que ela aparece dos dois
    lados de quem a usa — na unicidade da geração e na ordem esperada do banco publicado —, e as
    duas têm de ser a mesma chave, ou a propriedade afirmaria uma ordem que não é a do banco. O
    segundo é o de §6.3: mapeador nomeado se lê no contraexemplo encolhido.
    """
    return item.id


@st.composite
def bancos(draw: DrawFn, maximo: int) -> tuple[Item, ...]:
    """Banco de um a `maximo` itens carregáveis, com `id` distinto (R3.6).

    `unique_by` sobre o `id` porque unicidade é propriedade do **conjunto** e não do gerador,
    como `identificadores` documenta: dois itens sorteados independentemente podem colidir, e
    identificador duplicado é erro de carga — a propriedade reprovaria por banco inválido.

    Itens **carregáveis**, pelo mesmo motivo de `itens_carregaveis` existir: item praticado exige
    equivalente e transferência declarados como relação (R2.2, R2.6), e um banco gerado sem
    relação nenhuma seria recusado por associação ausente. Banco com item praticado é geração de
    **relação**, que as propriedades de ida e volta deixam fora de escopo por decisão de §5.5.

    `maximo` não tem padrão de propósito: o teto de itens é decisão de **orçamento** de quem
    chama — custa uma serialização, e às vezes uma gravação e uma carga, por item — e um padrão
    aqui esconderia essa decisão no lugar em que ela não pode ser justificada. Encolhe para um
    item, que é o banco mínimo compreensível.
    """
    if maximo < 1:
        raise ValueError(f"o banco gerado tem ao menos um item; teto pedido: {maximo}")
    do_banco = draw(
        st.lists(itens_carregaveis(), min_size=1, max_size=maximo, unique_by=identificador_de)
    )
    return tuple(do_banco)


# --------------------------------------------------------------------------- #
# Banco com relações declaradas: a entrada de `conjunto_do_desafio`
# --------------------------------------------------------------------------- #
#
# `bancos` acima produz o banco que as propriedades de ida e volta pedem: itens carregáveis
# **sozinhos**, com `id` distinto, nenhuma relação declarada e `pratica_assistida` fora de
# `etapas_permitidas`. É também o banco que `conjunto_do_desafio` não tem como atender — sem
# item praticado não existe ciclo, e sem relação declarada não existe candidato a equivalente.
#
# O que segue é o banco da outra forma, com a estrutura que §3.1 consome: itens praticados, um
# equivalente **privado** para cada um, equivalentes compartilhados entre todos, itens de
# transferência da habilidade alvo, concorrentes que não devem entrar no conjunto, e as
# relações declaradas. Ele mora aqui, e não no arquivo da Propriedade 33, pela mesma razão que
# `bancos` e `identificador_de` subiram de `p29_item_ida_e_volta.py`: a estrutura é exigência do
# **banco** (R2.2, R2.6), não substância de nenhuma propriedade. A Propriedade 32 (tarefa 3.8)
# precisa de bancos com esta mesma estrutura para perseguir o item sem IA entre as etapas, e
# duas construções do mesmo trio divergiriam na primeira correção feita em um lado só — com o
# preço de sempre, uma propriedade reprovando por banco inválido em vez de pelo defeito que
# procura. O que **não** sobe é a mutação: as lacunas deliberadas de §5.6 são de quem as
# enuncia, e ficam no arquivo da Propriedade 33.
#
# A construção é conferida com os predicados públicos de `modelo.py` — `equivalente_qualifica` e
# `transferencia_qualifica`, os mesmos que o carregador e o banco aplicam —, em `assert` dentro
# do gerador. Reimplementar o critério de R2.2 aqui daria o pior dos dois mundos: um gerador que
# concorda consigo mesmo e discorda do código que a propriedade verifica.

MAXIMO_DE_PRATICADOS: Final = 3
"""Teto de itens praticados no ciclo gerado.

Um praticado é o ciclo mínimo e o alvo do encolhimento. Dois é o que torna afirmável "**um**
equivalente para **cada** praticado", que com um só é indistinguível de "um equivalente". Três é
o que separa "dois a dois distintos" de "distinto do outro". Acima disso nenhuma invariante nova
aparece, e cada praticado custa dois itens gerados — ele e o equivalente privado — por exemplo.
"""

EQUIVALENTES_COMPARTILHADOS: Final = 1
"""Teto de equivalentes declarados para **todos** os itens praticados ao mesmo tempo.

O candidato compartilhado é o que põe à prova a atribuição dois a dois distinta do banco: só com
equivalentes privados, qualquer escolha serve e o emparelhamento nunca é exercido. Um basta para
criar a disputa, e como cada praticado conserva o privado, uma atribuição completa existe
sempre. É isso que mantém o banco completo **completo** sem que o gerador precise raciocinar
sobre viabilidade — isto é, sem uma segunda cópia do emparelhamento do banco dentro do teste.
"""

TRANSFERENCIAS_EXCEDENTES: Final = 1
"""Itens de transferência além do primeiro, que é o reservado.

O excedente é o que dá à metade "e nenhum outro item" de R2.3 algo a recusar: com um único item
de transferência no banco, levar todos e levar um são a mesma coisa. O primeiro nunca é marcado
como já apresentado, e é por isso que o banco completo continua atendendo o pedido.
"""

SEMENTE_MAXIMA: Final = 2**31 - 1
"""Teto da semente de seleção sorteada (R26.3).

Sorteada, e não fixa, porque é ela que decide **qual** candidato elegível entra quando há mais de
um: semente fixa afirmaria a propriedade sobre uma única ordem de preferência. O teto não tem
significado de domínio — `random.Random` aceita qualquer inteiro — e existe para que o
contraexemplo traga um número que se lê.
"""

TAMANHO_DA_HABILIDADE: Final = 8
"""Teto do nome de habilidade alvo gerado. A habilidade entra em comparação de igualdade e em
nada mais; o teto curto mantém o contraexemplo legível sem perder a gramática do identificador.
"""

SUFIXO_DE_OUTRA_HABILIDADE: Final = ".outra"
"""Sufixo que deriva uma segunda habilidade, distinta da alvo por construção.

Derivada em vez de sorteada de propósito: duas habilidades sorteadas independentemente podem
colidir, e um concorrente que caísse na habilidade alvo deixaria de ser concorrente. O ponto é
`PADRAO_DE_IDENTIFICADOR` admitir `.` fora da primeira posição, de modo que o derivado continua
sendo um identificador válido.
"""

ETAPAS_DO_DESAFIO: Final = frozenset({Etapa.DESAFIO_INDEPENDENTE})
"""Etapas permitidas do equivalente e do item de transferência.

A etapa para a qual o conjunto é montado é fixa (`banco.ETAPA_DO_CONJUNTO`), e um candidato que
não a admitisse seria inelegível por R2.4 e R2.5 — o banco completo deixaria de ser completo.
"""

ID_CONCORRENTE_SEM_RELACAO: Final = "x.sem_relacao"
ID_CONCORRENTE_DE_OUTRA_HABILIDADE: Final = "y.outra_habilidade"
ID_CONCORRENTE_FORA_DA_ETAPA: Final = "z.fora_da_etapa"
"""Os três concorrentes, cada um inelegível por um motivo diferente (R2.2, R2.3, R2.5).

Identificador falante, e não sorteado: o identificador do concorrente é o que se lê primeiro num
contraexemplo em que ele apareceu no conjunto, e `x.sem_relacao` diz por que ele não devia estar
lá onde um `id` sorteado exigiria reconstruir o banco à mão para descobrir.

Cada um fecha uma porta distinta: o primeiro qualifica em tudo menos a relação declarada, o
segundo é item de transferência de outra habilidade, e o terceiro é item de transferência da
habilidade alvo que não admite a etapa do desafio.
"""


@st.composite
def _itens_pareados(
    draw: DrawFn,
    identificador: str,
    habilidade: str,
    dificuldade: int,
    etapas: frozenset[Etapa],
    transferencia: bool,
) -> Item:
    """Item do banco pareado, com o papel fixado por quem chama e o resto do domínio sorteado.

    O corpo é `itens`, de modo que gabarito, tolerância, unidade, coleções, incógnita e dicas
    seguem cobrindo o domínio inteiro; o que esta função fixa são os cinco campos que decidem o
    **papel** do item no pareamento: identificador, habilidade alvo, dificuldade, etapas
    permitidas e a marca de transferência.

    O enunciado recebe o identificador como sufixo, e é o que garante a cláusula de enunciado
    distinto de R2.2 por construção em vez de por sorte: os identificadores são distintos no
    banco, logo os enunciados também. Sem isso, dois itens sorteados do mesmo conjunto de
    fragmentos colidiriam, o equivalente deixaria de qualificar e o banco "completo" recusaria o
    pedido — a propriedade falharia por banco mal construído, não por defeito do banco de itens.

    As coleções saem no tamanho mínimo que preserva o domínio — uma variação de gabarito, um
    conjunto de termos essenciais —, e é decisão de orçamento: o banco pareado sai com um item
    completo por posição, até dez por exemplo, e cada elemento de coleção custa um sorteio de
    texto. O acoplamento que importa segue intacto, porque é `perfis_de_gabarito` que o mantém:
    tolerância só em numérico, termos essenciais só em textual, sinônimo só com unidade. Quem
    precisa de coleção grande é a serialização canônica, e ali o banco é outro (`bancos`).
    """
    base = draw(itens(conjunto_de_etapas=st.just(etapas), variacoes=1, conjuntos_essenciais=1))
    return replace(
        base,
        id=identificador,
        habilidade_alvo=habilidade,
        dificuldade=dificuldade,
        enunciado=f"{base.enunciado} [{identificador}]",
        transferencia=transferencia,
    )


@st.composite
def _concorrentes(draw: DrawFn, habilidade: str, dificuldade: int) -> tuple[Item, ...]:
    """Itens que o conjunto não deve levar, cada um inelegível por um motivo diferente.

    Sorteados um a um, e não todos ou nenhum, para que o encolhimento chegue ao banco mínimo —
    um praticado, um equivalente, uma transferência — em vez de arrastar os três concorrentes
    para dentro de todo contraexemplo.
    """
    presentes: list[Item] = []
    if draw(st.booleans()):
        presentes.append(
            draw(
                _itens_pareados(
                    ID_CONCORRENTE_SEM_RELACAO, habilidade, dificuldade, ETAPAS_DO_DESAFIO, transferencia=False
                )
            )
        )
    if draw(st.booleans()):
        presentes.append(
            draw(
                _itens_pareados(
                    ID_CONCORRENTE_DE_OUTRA_HABILIDADE,
                    habilidade + SUFIXO_DE_OUTRA_HABILIDADE,
                    dificuldade,
                    ETAPAS_DO_DESAFIO,
                    transferencia=True,
                )
            )
        )
    if draw(st.booleans()):
        presentes.append(
            draw(
                _itens_pareados(
                    ID_CONCORRENTE_FORA_DA_ETAPA,
                    habilidade,
                    dificuldade,
                    frozenset({Etapa.LINHA_DE_BASE}),
                    transferencia=True,
                )
            )
        )
    return tuple(presentes)


def carga_ordenada(itens_do_banco: tuple[Item, ...], relacoes: tuple[Relacao, ...]) -> CargaConcluida:
    """Carga na ordem em que o carregador a publica: itens por `id`, relações pela tripla.

    A ordem é contrato de `CargaConcluida`, e não detalhe: é dela que depende o hash do banco na
    proveniência (§4.3). Quem monta carga em teste — para gerar, ou para mutar o banco gerado —
    passa por aqui, e assim a entrada do `BancoDeItens` é indistinguível de uma carga de verdade.
    """
    return CargaConcluida(
        itens=tuple(sorted(itens_do_banco, key=identificador_de)),
        relacoes=tuple(sorted(relacoes, key=lambda relacao: (relacao.item_origem, relacao.item_destino, relacao.tipo))),
    )


# --------------------------------------------------------------------------- #
# A forma do contraexemplo: `repr` dos agregados que carregam o banco
# --------------------------------------------------------------------------- #
#
# `PedidoDoDesafio` e `SessaoCompleta` carregam `CargaConcluida` inteira, e o `repr` que o
# `dataclass` gera despeja todo campo recursivamente: enunciado, quatro dicas, gabarito,
# variações, termos essenciais e etapas de cada item, vezes até duas dezenas de itens. Medido,
# são 10 a 38 kB por contraexemplo de sessão, e os maiores passam do teto de 30 kB em que a
# própria biblioteca avisa que gastou tempo montando um `repr` que não serve para nada.
#
# E não serve mesmo: o que estas propriedades afirmam é **quais identificadores** foram
# apresentados em quais etapas, e tamanho de reservatório. Nenhuma asserção dos oráculos cita o
# enunciado de um item. Quem precisar do item inteiro o tem pela semente mais a forma, que é o
# que estes `repr` mostram.


class _Impressora(Protocol):
    """O mínimo do pretty-printer da biblioteca de que `_repr_pretty_` precisa.

    Protocolo em vez de `from hypothesis.vendor.pretty import RepresentationPrinter`: o módulo
    é uma cópia vendida dentro da biblioteca, e depender do caminho dela acoplaria este arquivo
    a um detalhe de empacotamento que muda sem aviso. As duas operações usadas são as do
    protocolo de impressão que o IPython definiu e a biblioteca honra.
    """

    def text(self, texto: str) -> None:
        """Escreve texto sem quebrar."""
        ...

    def break_(self) -> None:
        """Quebra a linha, respeitando a indentação do nível em que o objeto aparece."""
        ...


def _forma_em_linhas(nome: str, nota: str, linhas: Sequence[str]) -> str:
    """Chamada de construtor quebrada em uma informação por linha, com uma nota no cabeçalho.

    Uma linha por informação porque é o que se lê num relatório de falha: o `repr` de linha
    única obriga a contar vírgulas para achar o reservatório que estourou. A nota do cabeçalho é
    o que se lê primeiro, e é o aperto do banco em palavras.

    A forma é uma chamada de construtor, com os campos reais como argumento e o que é derivado
    como comentário. Assim o `repr` não mente sobre o que o tipo guarda — `d`, `r` e as folgas
    são propriedades calculadas, não campos — e continua sendo Python válido, que é o que
    mantém a saída legível em qualquer leitor que a analise.
    """
    corpo = "\n".join(f"    {linha}" for linha in linhas)
    return f"{nome}(  # {nota}\n{corpo}\n)"


def _imprimir_em_linhas(texto: str, impressora: _Impressora) -> None:
    """Entrega o `repr` ao pretty-printer da biblioteca, uma linha por vez.

    **Sem isto o `__repr__` da classe não chega ao contraexemplo.** A biblioteca não imprime o
    `repr` do objeto: ela reconhece `dataclass` por `__dataclass_fields__` e despeja todo campo
    de `init` recursivamente com `getattr`, sem olhar para `__repr__`. É por isso que
    `repr=False` no decorador e `field(repr=False)` no campo pesado **não** resolvem — os dois
    mexem no `repr` que o `dataclass` gera, e o relatório de falha não passa por ele.

    O gancho que a biblioteca consulta **antes** do ramo de `dataclass` é `_repr_pretty_`, o
    protocolo de impressão do IPython. Daí a forma desta correção: `__repr__` escreve a forma,
    para quem usa `repr` — mensagem de asserção dos oráculos, `print`, log —, e `_repr_pretty_`
    o repassa linha por linha, para quem lê o contraexemplo. Quem apagar um dos dois perde
    metade da saída sem que nada fique vermelho.
    """
    for indice, linha in enumerate(texto.splitlines()):
        if indice:
            impressora.break_()
        impressora.text(linha)


def _conjunto_em_linha(valores: Collection[str]) -> str:
    """`frozenset` de identificadores em ordem determinística, na forma em que o Python o escreve.

    Ordenado, e não na ordem de iteração do conjunto: contraexemplo que troca de aparência entre
    duas execuções da mesma semente confunde mais do que ajuda.
    """
    if not valores:
        return "frozenset()"
    return "frozenset({" + ", ".join(repr(valor) for valor in sorted(valores)) + "})"


@dataclass(frozen=True, repr=False)
class PedidoDoDesafio:
    """Banco com relações declaradas e a solicitação de desafio independente de um ciclo.

    Os cinco campos são exatamente o que `BancoDeItens` e `conjunto_do_desafio` consomem, e a
    razão de virem juntos é que nenhum deles é verificável sozinho: um banco sem pedido não diz
    quais itens foram praticados, e um pedido sem banco não diz se há com que atendê-lo.

    `ja_apresentados` é o histórico do participante (R2.7), e no banco completo ele contém apenas
    itens **dispensáveis** — nunca o equivalente privado de um praticado, nunca o primeiro item
    de transferência. É o que torna o banco completo um banco que atende o pedido ao mesmo tempo
    que a exclusão de R2.7 está de fato em exercício.
    """

    carga: CargaConcluida
    praticados: tuple[str, ...]
    habilidade: str
    ja_apresentados: frozenset[str]
    semente: int

    @property
    def por_id(self) -> Mapping[str, Item]:
        """Itens do banco indexados por identificador, para quem precisa do item praticado."""
        return MappingProxyType({item.id: item for item in self.carga.itens})

    def __repr__(self) -> str:
        """O pedido pela **forma**: contagens do banco, papéis pelo prefixo, nada do conteúdo.

        O `repr` padrão deste tipo mede 2,4 a 13,6 kB, abaixo do teto em que a biblioteca avisa
        e bem acima do que alguém lê. O conteúdo do item é irrelevante para diagnosticar P33 —
        o oráculo dela é sobre **quais** itens o conjunto levou e sobre a cardinalidade de R2.3
        —, e o papel de cada um está no prefixo do identificador por construção: `p1` praticado,
        `e1` equivalente privado, `c1` candidato compartilhado, `t1` de transferência.
        """
        return _forma_em_linhas(
            "PedidoDoDesafio",
            f"{len(self.praticados)} praticado(s), banco de {len(self.carga.itens)} itens "
            f"e {len(self.carga.relacoes)} relações",
            (
                f"habilidade={self.habilidade!r},",
                f"semente={self.semente},",
                f"praticados={self.praticados!r},  # na ordem do pedido",
                f"ja_apresentados={_conjunto_em_linha(self.ja_apresentados)},  # R2.7",
                f"carga={tuple(item.id for item in self.carga.itens)!r},  # o papel está no prefixo",
            ),
        )

    def _repr_pretty_(self, impressora: _Impressora, ciclo: bool) -> None:
        """A forma acima no contraexemplo, que é onde ela precisa chegar (ver `_imprimir_em_linhas`)."""
        _imprimir_em_linhas("PedidoDoDesafio(...)" if ciclo else repr(self), impressora)


@st.composite
def pedidos_do_desafio(draw: DrawFn, maximo_de_praticados: int = MAXIMO_DE_PRATICADOS) -> PedidoDoDesafio:
    """Banco **completo** e o pedido que ele atende inteiro: a metade positiva de R2.3.

    "Completo" é afirmação forte, e é garantida por construção, não por filtro nem por sorte:

    - cada item praticado tem um equivalente **privado** — declarado equivalente só dele — que
      qualifica em R2.2, admite a etapa do desafio e nunca é marcado como já apresentado. Logo
      uma atribuição completa de equivalentes dois a dois distintos existe sempre, e o
      emparelhamento máximo do banco a encontra;
    - a habilidade alvo tem um item de transferência reservado, que nunca é marcado como já
      apresentado e nunca é candidato a equivalente — a marca `transferencia = true` não aparece
      em nenhum item ligado por relação `equivalente`, o que também é o que R2.9 exige;
    - os itens praticados são os do pedido, sem repetição, e a habilidade do pedido é a deles.

    O que varia em volta disso é o que dá substância à propriedade: a quantidade de praticados, o
    candidato compartilhado que cria disputa, os itens de transferência excedentes, os três
    concorrentes inelegíveis, o histórico de R2.7 sobre os dispensáveis, a semente de seleção, a
    ordem do pedido e — por `_itens_pareados` — o domínio inteiro de `Item` em cada item.

    Os itens praticados podem ou não admitir **também** o desafio independente. Quando admitem, o
    banco declara a cadeia de relações `equivalente` entre praticados vizinhos, e aí cada um é
    candidato qualificado do outro: é o único jeito de a exclusão "praticado neste ciclo" de R2.3
    estar em exercício em vez de pressuposta. Sem a etapa, o candidato cairia antes, por R2.5, e a
    afirmação de que nenhum praticado serve de equivalente de outro seria vazia.

    Fora de escopo, declarado: pedido **incoerente** — praticados de uma habilidade e `habilidade`
    de outra — e o esgotamento por disputa (`LacunaDoConjunto.DISPUTADO`). O primeiro não é lacuna
    de banco, e o segundo exigiria do gerador a decisão de viabilidade do emparelhamento, isto é,
    o algoritmo do banco reescrito no teste. Os dois estão em casos dirigidos em
    `backend/tests/unidade/test_banco_de_itens.py`.
    """
    if maximo_de_praticados < 1:
        raise ValueError(f"o ciclo gerado tem ao menos um item praticado; teto pedido: {maximo_de_praticados}")

    habilidade = draw(identificadores(tamanho_maximo=TAMANHO_DA_HABILIDADE))
    dificuldade = draw(dificuldades())
    quantos = draw(st.integers(min_value=1, max_value=maximo_de_praticados))
    tambem_no_desafio = draw(st.booleans())
    compartilhados = draw(st.integers(min_value=0, max_value=EQUIVALENTES_COMPARTILHADOS))
    excedentes = draw(st.integers(min_value=0, max_value=TRANSFERENCIAS_EXCEDENTES))

    etapas_do_praticado = frozenset({Etapa.PRATICA_ASSISTIDA}) | (
        ETAPAS_DO_DESAFIO if tambem_no_desafio else frozenset()
    )
    praticados = [
        draw(_itens_pareados(f"p{ordem}", habilidade, dificuldade, etapas_do_praticado, transferencia=False))
        for ordem in range(1, quantos + 1)
    ]
    privados = [
        draw(_itens_pareados(f"e{ordem}", habilidade, dificuldade, ETAPAS_DO_DESAFIO, transferencia=False))
        for ordem in range(1, quantos + 1)
    ]
    do_pool = [
        draw(_itens_pareados(f"c{ordem}", habilidade, dificuldade, ETAPAS_DO_DESAFIO, transferencia=False))
        for ordem in range(1, compartilhados + 1)
    ]
    de_transferencia = [
        draw(_itens_pareados(f"t{ordem}", habilidade, dificuldade, ETAPAS_DO_DESAFIO, transferencia=True))
        for ordem in range(1, excedentes + 2)
    ]
    concorrentes = draw(_concorrentes(habilidade, dificuldade))

    relacoes: list[Relacao] = []
    for praticado, privado in zip(praticados, privados, strict=True):
        assert equivalente_qualifica(praticado, privado), f"{privado.id} não qualifica como equivalente"
        assert transferencia_qualifica(praticado, de_transferencia[0]), "a transferência reservada não qualifica"
        relacoes.append(Relacao(praticado.id, privado.id, EQUIVALENTE))
        relacoes.append(Relacao(praticado.id, de_transferencia[0].id, TRANSFERENCIA))
        for compartilhado in do_pool:
            assert equivalente_qualifica(praticado, compartilhado), f"{compartilhado.id} não qualifica"
            relacoes.append(Relacao(praticado.id, compartilhado.id, EQUIVALENTE))
    for anterior, seguinte in zip(praticados, praticados[1:], strict=False):
        assert equivalente_qualifica(anterior, seguinte), "a cadeia entre praticados não qualifica"
        relacoes.append(Relacao(anterior.id, seguinte.id, EQUIVALENTE))

    dispensaveis = [item.id for item in (*do_pool, *de_transferencia[1:], *concorrentes)]
    ja_apresentados = draw(st.sets(st.sampled_from(dispensaveis))) if dispensaveis else set()

    return PedidoDoDesafio(
        carga=carga_ordenada(
            (*praticados, *privados, *do_pool, *de_transferencia, *concorrentes), tuple(relacoes)
        ),
        praticados=tuple(draw(st.permutations([praticado.id for praticado in praticados]))),
        habilidade=habilidade,
        ja_apresentados=frozenset(ja_apresentados),
        semente=draw(st.integers(min_value=0, max_value=SEMENTE_MAXIMA)),
    )


# --------------------------------------------------------------------------- #
# Sessão completa: o banco que atravessa as quatro etapas sem IA
# --------------------------------------------------------------------------- #
#
# `pedidos_do_desafio` acima gera **um** ciclo. A Propriedade 32 precisa da sessão inteira —
# linha de base, os três ciclos de R12.1 e o teste de retenção —, porque o que ela persegue não
# é a cardinalidade de um pedido e sim a exclusão de R2.7 **entre** etapas: o item apresentado
# numa etapa sem IA não reaparece em outra. Isso só é afirmável sobre uma sequência de pedidos
# com `ja_apresentados` acumulado do começo ao fim.
#
# A estrutura mora aqui pela fronteira que P29 declarou e que `pedidos_do_desafio` exerceu: o
# que é exigência do **banco** sobe para este módulo, e o que é substância da propriedade fica
# no arquivo dela. Banco de sessão é exigência do banco — R2.2 e R2.6 pedem equivalente e
# transferência declarados para cada item praticado, R12.1 fixa os três ciclos, e a aritmética
# do mínimo viável abaixo é consequência de R2.3 e R2.7, não de P32. O `Gestor_de_Sessão` de
# §3.3 (tarefa 6.1) consome banco desta forma, e as Propriedades 34 e 35 com ele. O que **não**
# sobe é a simulação do protocolo nem a mutação para baixo do mínimo viável: a primeira é o
# oráculo de P32, a segunda é a ênfase dela.
#
# ## A aritmética do mínimo viável
#
# Com `c` ciclos, `p` itens praticados por ciclo, `b` itens na linha de base e `d = p + 1` itens
# no conjunto do desafio (R2.3: um equivalente por praticado mais um de transferência), o
# consumo das etapas sem IA de uma sessão é
#
#     b  +  c · d  +  r          com  r = d  (R12.4: a retenção reusa a estrutura do pós-teste)
#
# e R2.7 proíbe que qualquer desses itens seja reaproveitado em outra etapa sem IA. Logo o banco
# mínimo é aquele em que o consumo **esgota** o banco, e ele se reparte em dois reservatórios,
# porque equivalente e item de transferência não são intercambiáveis — R2.9 recusa o item
# marcado `transferencia = true` declarado isomorfo a um praticado:
#
#     pool sem IA (não-transferência) :  b + c · p + r
#     itens de transferência          :  c                 (um por ciclo; R2.7 proíbe o reuso)
#
# A soma dos dois é exatamente o consumo, de modo que no banco mínimo **todo** item sem IA é
# apresentado uma vez e nenhum sobra. É o banco em que nenhuma etapa tem folga — e o único em
# que um defeito de acúmulo de `ja_apresentados` aparece, porque num banco folgado a etapa
# seguinte encontra candidato de qualquer forma e a propriedade passa sem exercitar R2.7.
#
# ## Onde o aperto cai, e por que é a retenção
#
# O pool sem IA é um só, compartilhado pelas três etapas que o consomem, e os itens dele
# declaram as **três** etapas sem IA executáveis. É deliberadamente mais adversário que
# `data/itens/`, onde os conjuntos são disjuntos por declaração: com o pool compartilhado, a
# única coisa que mantém as etapas disjuntas é R2.7. E como a retenção é a **última** a pedir,
# ela recebe exatamente o que sobrou — `r` itens, nem um a mais. É o caso delicado que §5.6
# nomeia: a retenção reusa a estrutura do pós-teste sem poder reusar os itens.
#
# Os itens de transferência declaram **só** o desafio independente, e isso mantém os dois
# reservatórios separados: um item de transferência elegível na linha de base faria a etapa
# inicial comer do orçamento dos ciclos, e aí a viabilidade do banco mínimo passaria a depender
# de qual item a linha de base escolheu. A composição do conjunto da retenção — quantos dos `r`
# itens dela são de transferência — é decisão do `Gestor_de_Sessão` (tarefa 6.2) e não do banco,
# que para a retenção oferece uma operação só, `elegiveis_sem_ia`.

CICLOS_DO_PROTOCOLO: Final = 3
"""Ciclos de prática assistida e desafio independente numa sessão (R12.1).

Três, e o terceiro é o que R12.3 rotula como pós-teste — rótulo sobre o conjunto sem IA daquele
ciclo, **não** uma quarta chamada ao banco. Ver `adia.tipos.CICLO_DO_POSTESTE`, que é onde o
número do ciclo rotulado mora no código de produção.
"""

MAXIMO_DE_PRATICADOS_POR_CICLO: Final = 2
"""Teto de itens praticados por ciclo na sessão gerada.

Um é o ciclo mínimo e o alvo do encolhimento; dois é o que torna afirmável que os equivalentes
de um mesmo ciclo são distintos entre si. Acima de dois nenhuma invariante nova de P32 aparece —
a cardinalidade do conjunto do desafio é de P33, que vai a três —, e cada praticado acrescenta
dois itens gerados ao banco (ele e a vaga de equivalente que o pool precisa ter), em três
ciclos.
"""

MAXIMO_DA_LINHA_DE_BASE: Final = 2
"""Teto de itens da linha de base na sessão gerada.

Independente do tamanho do ciclo de propósito: a linha de base mede proficiência antes da
intervenção e nada no protocolo amarra o tamanho dela ao do desafio. Variá-la é metade do que dá
ao banco o **tamanho variável** que §5.6 pede; a outra metade é a folga.
"""

FOLGA_MAXIMA: Final = 2
"""Itens excedentes por reservatório, acima do mínimo viável.

A folga é o que separa "banco próximo do mínimo viável" de "banco com sobra": em zero, nenhuma
etapa tem escolha; acima de zero, a etapa seguinte encontra candidato mesmo quando a anterior
consumiu o preferido. Dois basta para as duas formas, e cada unidade custa um item gerado.
"""

ETAPAS_EXECUTAVEIS_SEM_IA: Final = ETAPAS_SEM_IA - frozenset({Etapa.POSTESTE})
"""As etapas sem IA que de fato consomem itens do banco: linha de base, desafio e retenção.

Derivada de `ETAPAS_SEM_IA` em vez de escrita à mão, e com **uma** subtração: `Etapa.POSTESTE` é
rótulo do conjunto sem IA do terceiro ciclo (R12.3), não etapa com itens próprios. Nenhum item
de `data/itens/` declara `posteste`, e `test_nenhum_item_declara_o_posteste` afirma isso sobre o
banco real; o banco gerado segue a mesma regra. Se `ETAPAS_SEM_IA` ganhar um membro, ele aparece
aqui sem que ninguém precise lembrar — que é o oposto de uma lista fixa de três etapas.
"""

ETAPAS_DO_POOL_SEM_IA: Final = frozenset(ETAPAS_EXECUTAVEIS_SEM_IA)
"""Etapas permitidas de todo item do pool sem IA: as três, em todo item.

É a configuração mais apertada que o banco admite, e é escolhida por isso. Com as três etapas em
cada item, linha de base, desafio e retenção disputam o **mesmo** universo, e a única coisa que
os mantém disjuntos é a exclusão de R2.7 — um defeito nela aparece como item repetido, não como
etapa recusada. O banco real faz o contrário (um item declara uma etapa sem IA só), e a diferença
é deliberada: lá o que se verifica é o conteúdo, aqui é o código.
"""

ID_DO_PRATICADO: Final = "p"
ID_DO_POOL_SEM_IA: Final = "s"
ID_DA_TRANSFERENCIA: Final = "t"
"""Prefixos dos identificadores gerados, por papel no banco.

Falantes e sequenciais — `p1`, `s4`, `t2` — e não sorteados, pela razão de §6.3: o que se lê
primeiro num contraexemplo é o identificador, e `s4` já diz de qual reservatório o item saiu.
"""


@dataclass(frozen=True, repr=False)
class SessaoCompleta:
    """Banco e roteiro de uma sessão inteira do protocolo, na ordem de R12.1.

    Os campos são o que o `BancoDeItens` e o futuro `Gestor_de_Sessão` consomem; as propriedades
    derivadas são a aritmética do mínimo viável, calculada aqui uma vez em vez de repetida em
    cada afirmação de quem usa o banco.

    A **folga é derivada**, não armazenada, e isso é o que permite que a mutação de P32 — retirar
    um item de um reservatório — produza uma `SessaoCompleta` legítima com folga negativa, sem
    que nada precise ser dito duas vezes. `esta_abaixo_do_minimo` responde pelo banco que vai
    recusar uma etapa; `e_minimo_viavel`, pelo banco em que nenhuma etapa tem escolha.

    O que o construtor garante: três ciclos, todos do mesmo tamanho e não vazios, nenhum item
    praticado repetido entre ciclos, linha de base não vazia, reservatórios disjuntos e todo
    identificador citado presente na carga. O que ele **não** garante é tamanho: banco abaixo do
    mínimo é um valor válido deste tipo, e dizer o contrário impediria de construí-lo.
    """

    carga: CargaConcluida
    habilidade: str
    ciclos: tuple[tuple[str, ...], ...]
    na_linha_de_base: int
    pool_sem_ia: tuple[str, ...]
    de_transferencia: tuple[str, ...]
    semente: int

    def __post_init__(self) -> None:
        """Verifica a forma do roteiro e a coerência dos reservatórios com a carga."""
        if len(self.ciclos) != CICLOS_DO_PROTOCOLO:
            raise ValueError(
                f"o protocolo tem {CICLOS_DO_PROTOCOLO} ciclos (R12.1); o roteiro traz {len(self.ciclos)}."
            )
        tamanhos = {len(ciclo) for ciclo in self.ciclos}
        if tamanhos != {self.praticados_por_ciclo} or self.praticados_por_ciclo < 1:
            raise ValueError(
                "todo ciclo pratica a mesma quantidade de itens, e nenhum ciclo é vazio; "
                f"tamanhos encontrados: {sorted(tamanhos)}."
            )
        if self.na_linha_de_base < 1:
            raise ValueError("a linha de base apresenta ao menos um item (R12.1).")
        praticados = [identificador for ciclo in self.ciclos for identificador in ciclo]
        if len(set(praticados)) != len(praticados):
            raise ValueError("o mesmo item praticado aparece em mais de um ciclo do roteiro.")
        compartilhados = set(self.pool_sem_ia) & set(self.de_transferencia)
        if compartilhados:
            raise ValueError(
                f"os dois reservatórios sem IA são disjuntos; em ambos: {sorted(compartilhados)}. "
                "R2.9 recusa o item de transferência declarado isomorfo a um praticado."
            )
        conhecidos = set(self.por_id)
        citados = set(praticados) | set(self.pool_sem_ia) | set(self.de_transferencia)
        if not citados <= conhecidos:
            raise ValueError(f"identificador citado e ausente da carga: {sorted(citados - conhecidos)}.")

    @property
    def por_id(self) -> Mapping[str, Item]:
        """Itens do banco indexados por identificador."""
        return MappingProxyType({item.id: item for item in self.carga.itens})

    @property
    def praticados_por_ciclo(self) -> int:
        """`p` — itens praticados em cada ciclo."""
        return len(self.ciclos[0]) if self.ciclos else 0

    @property
    def no_desafio(self) -> int:
        """`d = p + 1` — tamanho do conjunto do desafio independente de um ciclo (R2.3)."""
        return self.praticados_por_ciclo + TRANSFERENCIAS_NO_CONJUNTO

    @property
    def na_retencao(self) -> int:
        """`r = d` — itens do teste de retenção, pela estrutura do pós-teste (R12.4)."""
        return self.no_desafio

    @property
    def minimo_do_pool_sem_ia(self) -> int:
        """`b + c · p + r` — itens não-transferência sem os quais alguma etapa é recusada."""
        return self.na_linha_de_base + CICLOS_DO_PROTOCOLO * self.praticados_por_ciclo + self.na_retencao

    @property
    def minimo_de_transferencia(self) -> int:
        """`c` — um item de transferência por ciclo, porque R2.7 proíbe reaproveitar o anterior."""
        return CICLOS_DO_PROTOCOLO

    @property
    def folga_do_pool_sem_ia(self) -> int:
        """Itens do pool além do mínimo. Zero é o mínimo viável; negativo, o banco insuficiente."""
        return len(self.pool_sem_ia) - self.minimo_do_pool_sem_ia

    @property
    def folga_de_transferencia(self) -> int:
        """Itens de transferência além do mínimo, na mesma convenção de sinal."""
        return len(self.de_transferencia) - self.minimo_de_transferencia

    @property
    def e_minimo_viavel(self) -> bool:
        """Se nenhuma etapa sem IA tem folga: o consumo esgota os dois reservatórios."""
        return self.folga_do_pool_sem_ia == 0 and self.folga_de_transferencia == 0

    @property
    def esta_abaixo_do_minimo(self) -> bool:
        """Se algum reservatório não dá para todas as etapas, e uma delas será recusada."""
        return self.folga_do_pool_sem_ia < 0 or self.folga_de_transferencia < 0

    @property
    def consumo_sem_ia(self) -> int:
        """`b + c · d + r` — itens que as etapas sem IA apresentam numa sessão sem recusa."""
        return self.na_linha_de_base + CICLOS_DO_PROTOCOLO * self.no_desafio + self.na_retencao

    @property
    def itens_sem_ia(self) -> frozenset[str]:
        """Todo item do banco elegível em alguma etapa sem IA, nos dois reservatórios."""
        return frozenset(self.pool_sem_ia) | frozenset(self.de_transferencia)

    @property
    def _aperto(self) -> str:
        """O aperto do banco em palavras, que é a primeira coisa a saber num contraexemplo.

        Os três estados são exclusivos por construção: `e_minimo_viavel` exige folga zero nos
        dois reservatórios e `esta_abaixo_do_minimo` exige folga negativa em algum.
        """
        if self.esta_abaixo_do_minimo:
            return "abaixo do mínimo"
        if self.e_minimo_viavel:
            return "mínimo viável"
        return "com folga"

    def __repr__(self) -> str:
        """A sessão pela **forma**: o aperto, a aritmética, os papéis e os ciclos — sem conteúdo.

        O `repr` que o `dataclass` gera para este tipo mede 10 a 38 kB, porque despeja
        `CargaConcluida` inteira, e é o que faz a biblioteca avisar que montou um `repr` grande
        demais para ser útil. Ele é grande e, pior, não responde nenhuma das perguntas que um
        contraexemplo de P32 levanta — quais identificadores foram apresentados em quais etapas,
        e quanta folga cada reservatório tinha.

        O que entra, nessa ordem de leitura: o aperto e o tamanho do banco no cabeçalho; a
        habilidade e a semente, que são com o que o caso se reproduz; a aritmética do mínimo
        viável na linha dos ciclos, com os nomes que a seção acima usa (`c`, `p`, `d`, `r`); os
        praticados de cada ciclo, um ciclo por linha; e os dois reservatórios com tamanho,
        mínimo e folga de cada um.

        O que não entra: nada de `Item` além do identificador. Nenhum enunciado, dica, gabarito,
        variação, termo essencial ou tolerância — e o identificador basta porque é curto e
        falante por construção (`p1`, `s5`, `t1`), e é a única coisa que as asserções dos
        oráculos citam.
        """
        rotulo = ", rotulado pós-teste (R12.3)"
        ciclos = tuple(
            f"    {ciclo!r},  # ciclo {numero}{rotulo if numero == CICLO_DO_POSTESTE else ''}"
            for numero, ciclo in enumerate(self.ciclos, start=1)
        )
        return _forma_em_linhas(
            "SessaoCompleta",
            f"{self._aperto}; consumo {self.consumo_sem_ia}, banco de "
            f"{len(self.carga.itens)} itens e {len(self.carga.relacoes)} relações",
            (
                f"habilidade={self.habilidade!r},",
                f"semente={self.semente},",
                f"na_linha_de_base={self.na_linha_de_base},  # b",
                f"ciclos=(  # c={len(self.ciclos)}, p={self.praticados_por_ciclo}, "
                f"d={self.no_desafio}, r={self.na_retencao}",
                *ciclos,
                "),",
                f"pool_sem_ia={self.pool_sem_ia!r},  # {len(self.pool_sem_ia)} itens, "
                f"mínimo {self.minimo_do_pool_sem_ia}, folga {self.folga_do_pool_sem_ia}",
                f"de_transferencia={self.de_transferencia!r},  # {len(self.de_transferencia)} itens, "
                f"mínimo {self.minimo_de_transferencia}, folga {self.folga_de_transferencia}",
            ),
        )

    def _repr_pretty_(self, impressora: _Impressora, ciclo: bool) -> None:
        """A forma acima no contraexemplo, que é onde ela precisa chegar (ver `_imprimir_em_linhas`)."""
        _imprimir_em_linhas("SessaoCompleta(...)" if ciclo else repr(self), impressora)


@st.composite
def sessoes_completas(
    draw: DrawFn, folga_minima: int = 0, folga_maxima: int = FOLGA_MAXIMA
) -> SessaoCompleta:
    """Banco e roteiro de uma sessão que o protocolo atravessa inteira, sem recusa.

    "Sem recusa" é garantido por construção, e não por filtro nem por sorte. Os dois
    reservatórios têm ao menos o mínimo declarado em `SessaoCompleta`, e três escolhas tornam a
    satisfazibilidade independente de **qual** candidato cada etapa preferiu:

    - todo item do pool qualifica como equivalente de **todo** item praticado — mesma habilidade
      alvo, mesma dificuldade, identificador e enunciado distintos (R2.2) —, de modo que o
      emparelhamento de um ciclo encontra atribuição completa sempre que restarem `p` itens no
      pool, sem que o gerador precise decidir viabilidade;
    - os itens do pool são intercambiáveis entre as três etapas que o consomem, porque declaram
      as três (`ETAPAS_DO_POOL_SEM_IA`). Logo a ordem em que linha de base, ciclos e retenção
      tomam deles não muda quantos sobram;
    - os itens de transferência ficam fora do universo das outras etapas, o que impede a linha de
      base de comer do orçamento dos ciclos.

    `folga_minima` e `folga_maxima` são o controle de **aperto**, e são parâmetro em vez de
    sorteio fixo porque quem enuncia a propriedade é que decide o regime: `folga_maxima=0` dá o
    banco no mínimo viável, que é a ênfase de §5.6, e `folga_minima=1` dá o banco com sobra.
    Deixar os dois ao sorteio uniforme faria o mínimo viável aparecer em um exemplo a cada nove,
    que é pouco para a forma que a propriedade existe para exercitar.

    A semente de seleção é **sorteada** (R26.3): é ela que decide qual candidato elegível entra
    quando há mais de um, e verificar uma semente fixa afirmaria a propriedade sobre uma única
    ordem de preferência.

    Fora de escopo, declarado: item praticado que **também** admite o desafio independente, e com
    ele a exclusão "praticado neste ciclo" de R2.3 — isso é de P33, que o gera em
    `pedidos_do_desafio`. Aqui o item praticado declara só a prática assistida, como em
    `data/itens/`, e o que fica em exercício é a exclusão entre etapas, que é de P32.
    """
    if folga_minima > folga_maxima:
        raise ValueError(f"folga mínima {folga_minima} acima da máxima {folga_maxima}")
    if folga_minima < 0:
        raise ValueError(f"a folga mínima do banco gerado não é negativa; pedida: {folga_minima}")

    habilidade = draw(identificadores(tamanho_maximo=TAMANHO_DA_HABILIDADE))
    dificuldade = draw(dificuldades())
    por_ciclo = draw(st.integers(min_value=1, max_value=MAXIMO_DE_PRATICADOS_POR_CICLO))
    na_linha_de_base = draw(st.integers(min_value=1, max_value=MAXIMO_DA_LINHA_DE_BASE))
    folgas = st.integers(min_value=folga_minima, max_value=folga_maxima)
    no_pool = (
        na_linha_de_base
        + CICLOS_DO_PROTOCOLO * por_ciclo
        + por_ciclo
        + TRANSFERENCIAS_NO_CONJUNTO
        + draw(folgas)
    )
    de_transferencia = CICLOS_DO_PROTOCOLO + draw(folgas)

    praticados = [
        draw(
            _itens_pareados(
                f"{ID_DO_PRATICADO}{ordem}",
                habilidade,
                dificuldade,
                frozenset({Etapa.PRATICA_ASSISTIDA}),
                transferencia=False,
            )
        )
        for ordem in range(1, CICLOS_DO_PROTOCOLO * por_ciclo + 1)
    ]
    pool = [
        draw(
            _itens_pareados(
                f"{ID_DO_POOL_SEM_IA}{ordem}",
                habilidade,
                dificuldade,
                ETAPAS_DO_POOL_SEM_IA,
                transferencia=False,
            )
        )
        for ordem in range(1, no_pool + 1)
    ]
    transferencias = [
        draw(
            _itens_pareados(
                f"{ID_DA_TRANSFERENCIA}{ordem}",
                habilidade,
                dificuldade,
                ETAPAS_DO_DESAFIO,
                transferencia=True,
            )
        )
        for ordem in range(1, de_transferencia + 1)
    ]

    ciclos = tuple(
        tuple(draw(st.permutations([item.id for item in praticados[inicio : inicio + por_ciclo]])))
        for inicio in range(0, len(praticados), por_ciclo)
    )
    relacoes = _relacoes_da_sessao(praticados, pool, transferencias, ciclos)

    return SessaoCompleta(
        carga=carga_ordenada((*praticados, *pool, *transferencias), relacoes),
        habilidade=habilidade,
        ciclos=ciclos,
        na_linha_de_base=na_linha_de_base,
        pool_sem_ia=tuple(item.id for item in pool),
        de_transferencia=tuple(item.id for item in transferencias),
        semente=draw(st.integers(min_value=0, max_value=SEMENTE_MAXIMA)),
    )


def _relacoes_da_sessao(
    praticados: Sequence[Item],
    pool: Sequence[Item],
    transferencias: Sequence[Item],
    ciclos: Sequence[Sequence[str]],
) -> tuple[Relacao, ...]:
    """As associações de R2.2 e R2.6 do banco de sessão, conferidas pelos predicados públicos.

    Cada item praticado é ligado a **todo** item do pool por relação `equivalente`, e ao item de
    transferência do próprio ciclo por relação `transferencia`. As duas escolhas têm razão:

    - ligar a todo o pool é o que faz o universo de candidatos de um ciclo ser o pool inteiro
      menos o já apresentado. Com equivalentes privados por praticado, o consumo de um ciclo
      nunca alcançaria os candidatos do seguinte, e a exclusão de R2.7 ficaria sem efeito
      observável entre ciclos — que é metade do que P32 existe para verificar;
    - uma relação `transferencia` por praticado basta para R2.6, e a do próprio ciclo é a que se
      lê. A montagem do conjunto não consulta essa relação: `_triar_transferencia` toma o
      universo pela habilidade alvo e pela marca do item (R2.3), e a relação é exigência de
      carga.

    Nenhum par recebe duas relações, porque os reservatórios são disjuntos — `Relacao` declara
    que `equivalente` e `transferencia` sobre a mesma dupla são afirmações contraditórias.

    A conferência é por `equivalente_qualifica` e `transferencia_qualifica`, os mesmos predicados
    que o carregador e o banco aplicam. Reimplementar o critério de R2.2 aqui daria um gerador
    que concorda consigo mesmo e discorda do código que a propriedade verifica.
    """
    relacoes: list[Relacao] = []
    por_ciclo_do_praticado = {
        identificador: numero for numero, ciclo in enumerate(ciclos) for identificador in ciclo
    }
    for praticado in praticados:
        for candidato in pool:
            assert equivalente_qualifica(praticado, candidato), (
                f"{candidato.id} não qualifica como equivalente de {praticado.id} (R2.2)"
            )
            relacoes.append(Relacao(praticado.id, candidato.id, EQUIVALENTE))
        do_ciclo = transferencias[por_ciclo_do_praticado[praticado.id]]
        assert transferencia_qualifica(praticado, do_ciclo), (
            f"{do_ciclo.id} não qualifica como transferência de {praticado.id} (R2.2)"
        )
        relacoes.append(Relacao(praticado.id, do_ciclo.id, TRANSFERENCIA))
    return tuple(relacoes)
