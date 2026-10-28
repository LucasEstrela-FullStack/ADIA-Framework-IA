"""Testes do Motor_de_Correção: fronteira da tolerância, formas declaradas e resposta inválida.

O que estes testes afirmam não é "o motor corrige". É que **o julgamento é decidido pelo que o
item declara**, e por nada mais. Cinco afirmações, cada uma protegendo uma medida diferente:

1. a tolerância declarada decide o acerto numérico, e a comparação é ``≤``: o desvio
   **exatamente igual** à tolerância é acerto, nas duas direções (R4.1). Um ``<`` no lugar do
   ``≤`` mudaria o veredito só no item de fronteira, que é precisamente o item que separa
   acerto de erro na TAI — defeito invisível em qualquer exemplo que não seja o da borda. Com
   ``tolerancia = 0``, que é o que o banco declara nas partes de contagem, a regra vira
   igualdade exata em valor, e não em texto: ``"7.000"`` é o gabarito ``"7"``;
2. o separador decimal é lido por regra declarada (ver ``interpretar_decimal``), e a regra tem
   um lado escolhido no caso ambíguo. ``4,05`` é o que um estudante brasileiro escreve e é
   aceito; ``1.500`` é um e meio, porque é assim que a notação canônica do projeto escreve um
   e meio com três casas. O que não tem leitura única não é número, e falha fechado;
3. forma declarada é forma aceita (R2.1): ``"quatro"`` acerta o item semente porque o banco a
   declara, e nenhuma tolerância alcançaria um numeral escrito em palavras. O que o banco
   **não** declarou não é aceito — ``"QUATRO"`` erra, porque dobrar a caixa seria inventar uma
   equivalência que o item não autoriza;
4. resposta vazia e resposta acima do tamanho máximo do item são **julgamento**, não erro:
   ``erro`` com motivo (R4.6), submissão julgada e não descartada. Descartar tiraria a
   tentativa do denominador da TAI e melhoraria o desempenho aparente do estudante;
5. o item textual não recebe veredito automático: a resposta vai inteira para
   ``partes_para_rubrica`` e o resultado é a indisponibilidade declarada (R4.7). Palavra-chave
   como oráculo de acerto seria pior que nenhum julgamento, porque pareceria um julgamento.

E uma sexta, que é de sigilo e não de medida: a justificativa nomeia o **critério** aplicado e
nunca o gabarito, suas variações ou o desvio medido — quem conhece a própria resposta e o
desvio conhece o gabarito. Mesma regra de ``itens/erros.py``.

R4.5 não tem asserção própria aqui, e não precisa: a fixture ``ollama_proibido`` é ``autouse``
em toda a suíte, de modo que qualquer chamada de inferência emitida por ``corrigir`` faria
estes testes falharem. O contrato ``nucleo-puro`` fecha o lado estático.

O item semente é o real, ``alg-eq-101`` de ``data/itens/praticados.adia.toml``, com os campos
que o arquivo declara — gabarito ``4``, tolerância ``0.05`` e variações ``["4", "4.0",
"quatro"]``. Os demais itens são construídos no teste: o banco inicial não tem nenhum item
``ALTERNATIVA`` nem ``TEXTUAL``, e esperar por conteúdo que não existe deixaria os dois
caminhos sem verificação. As Propriedades 36 e 37, sobre entradas geradas, são as tarefas 3.11
e 3.12.

**Validates: Requirements 4.1, 4.2, 4.3, 4.5, 4.6, 4.7**
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from types import MappingProxyType

import pytest

from adia.nucleo.correcao.motor import (
    MOTIVO_AGUARDANDO_RUBRICA,
    MOTIVO_EXCEDE_TAMANHO_MAXIMO,
    MOTIVO_VAZIA,
    Julgamento,
    Resultado,
    corrigir,
    e_julgado,
    interpretar_decimal,
)
from adia.nucleo.itens.carregador import PADRAO_DE_DECIMAL
from adia.nucleo.itens.modelo import Item, TipoGabarito
from adia.tipos import Etapa, Indisponivel, Nivel

# --------------------------------------------------------------------------- #
# Construção de item
# --------------------------------------------------------------------------- #

HABILIDADE = "equacao_linear"

DICAS = MappingProxyType(
    {
        Nivel.L1: "O que precisa continuar valendo nos dois lados de uma igualdade?",
        Nivel.L2: "Isto é uma equação do primeiro grau com uma incógnita.",
        Nivel.L3: "Desfaça a soma e só depois a multiplicação, nos dois membros.",
        Nivel.L4: "Em 5y + 2 = 17, subtraia 2 dos dois lados e divida por 5.",
    }
)
"""Catálogo de L1 a L4 que o modelo exige em todo item (R2.1), sem revelar gabarito."""


def item(
    identificador: str = "alg-eq-101",
    *,
    enunciado: str = "Resolva a equação 2x + 3 = 11 e informe o valor de x.",
    tipo_gabarito: TipoGabarito = TipoGabarito.NUMERICO,
    gabarito: str = "4",
    tolerancia: Decimal | None = Decimal("0.05"),
    variacoes: tuple[str, ...] = (),
    unidade: str | None = None,
    sinonimos_unidade: tuple[str, ...] = (),
    termos_essenciais: tuple[tuple[str, ...], ...] = (),
    tamanho_max_resposta: int = 120,
    etapas: Iterable[Etapa] = (Etapa.PRATICA_ASSISTIDA,),
) -> Item:
    """Item válido cujo perfil de gabarito é o que cada teste precisa variar.

    Os defaults são os do item semente, de modo que um teste que só investiga a tolerância não
    precise repetir treze campos que não têm nada a ver com o que ele afirma.
    """
    return Item(
        id=identificador,
        enunciado=enunciado,
        habilidade_alvo=HABILIDADE,
        dificuldade=2,
        tamanho_max_resposta=tamanho_max_resposta,
        tipo_gabarito=tipo_gabarito,
        gabarito=gabarito,
        tolerancia=tolerancia,
        unidade=unidade,
        sinonimos_unidade=sinonimos_unidade,
        variacoes_gabarito=variacoes,
        termos_essenciais=termos_essenciais,
        incognita="x",
        etapas_permitidas=frozenset(etapas),
        transferencia=False,
        dicas=DICAS,
    )


def item_semente() -> Item:
    """O item semente **real** do banco: ``alg-eq-101``, ``2x + 3 = 11``, gabarito 4.

    Campo a campo como ``data/itens/praticados.adia.toml`` o declara. Vale ter o item real
    aqui porque ele é o caso de fronteira de todo o protótipo: tolerância ``0.05`` sobre um
    gabarito inteiro é exatamente a situação em que o ``≤`` da comparação decide.
    """
    return item(variacoes=("4", "4.0", "quatro"))


def item_de_contagem() -> Item:
    """Item de tolerância zero, como as partes de contagem do banco.

    Fração de unidade não significa nada em contagem de canetas, e por isso o banco declara
    ``tolerancia = "0"``: a comparação é igualdade exata de **valor**.
    """
    return item(
        "alg-eq-401",
        enunciado="Quantas canetas João comprou?",
        gabarito="7",
        tolerancia=Decimal("0"),
        variacoes=("7", "sete"),
        unidade="canetas",
        sinonimos_unidade=("caneta",),
        tamanho_max_resposta=160,
    )


def item_de_alternativa() -> Item:
    """Item de gabarito de alternativa, ausente do banco inicial e exigido por R4.2."""
    return item(
        "alg-eq-501",
        enunciado="Qual operação isola a incógnita em 2x = 8?",
        tipo_gabarito=TipoGabarito.ALTERNATIVA,
        gabarito="b) dividir os dois membros por 2",
        tolerancia=None,
    )


def item_textual() -> Item:
    """Item de gabarito textual, ausente do banco inicial e exigido por R4.7.

    ``termos_essenciais`` é obrigatório no tipo (R2.11) e está aqui por isso — **não** como
    critério de acerto. É o que o teste do caminho da rubrica verifica: o motor não o usa para
    julgar.
    """
    return item(
        "alg-eq-601",
        enunciado="Explique por que a igualdade se mantém ao operar nos dois membros.",
        tipo_gabarito=TipoGabarito.TEXTUAL,
        gabarito="A operação aplicada aos dois membros preserva a igualdade.",
        tolerancia=None,
        termos_essenciais=(("igualdade", "membros"),),
        tamanho_max_resposta=400,
    )


def veredito(julgamento: Julgamento) -> Resultado:
    """O veredito de um julgamento que deveria ter sido automático."""
    resultado = julgamento.resultado
    assert e_julgado(resultado), f"sem veredito automático: {julgamento.justificativa}"
    return resultado


# --------------------------------------------------------------------------- #
# Tolerância numérica declarada (R4.1)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("resposta", ["4", "4.0", "4.04", "3.96", "4,04"])
def test_resposta_dentro_da_tolerancia_do_item_semente_e_acerto(resposta: str) -> None:
    """Com tolerância 0.05 sobre o gabarito 4, o que está dentro da faixa acerta (R4.1).

    A vírgula entra na lista de propósito: ``4,04`` é o que um estudante brasileiro escreve, e
    recusá-lo transformaria convenção de escrita em erro de conteúdo.
    """
    assert veredito(corrigir(item_semente(), resposta)) is Resultado.ACERTO


@pytest.mark.parametrize("resposta", ["4.051", "3.949", "5", "0", "-4"])
def test_resposta_fora_da_tolerancia_do_item_semente_e_erro(resposta: str) -> None:
    """Fora da faixa é erro, inclusive logo depois da borda e no sinal trocado (R4.1)."""
    assert veredito(corrigir(item_semente(), resposta)) is Resultado.ERRO


@pytest.mark.parametrize("resposta", ["4.05", "3.95"])
def test_desvio_exatamente_igual_a_tolerancia_e_acerto_nas_duas_direcoes(resposta: str) -> None:
    """A fronteira pertence ao acerto: a comparação é ``≤``, não ``<`` (R4.1).

    É o único teste deste arquivo que distingue ``≤`` de ``<``, e ele vale nas duas direções
    porque um ``abs`` esquecido na diferença só apareceria no desvio negativo. A Propriedade 37
    reforça a amostragem exatamente aqui.
    """
    assert veredito(corrigir(item_semente(), resposta)) is Resultado.ACERTO


@pytest.mark.parametrize(
    ("resposta", "esperado"),
    [
        ("7", Resultado.ACERTO),
        ("7.000", Resultado.ACERTO),
        ("7,0", Resultado.ACERTO),
        ("7.01", Resultado.ERRO),
        ("6.999", Resultado.ERRO),
    ],
)
def test_tolerancia_zero_exige_igualdade_de_valor_e_nao_de_texto(resposta: str, esperado: Resultado) -> None:
    """Tolerância zero é comparação exata — de valor, não de grafia (R4.1, R2.8).

    ``7.000`` e ``7`` são o mesmo número escrito de duas formas, e o acerto não pode depender
    de qual delas o estudante digitou. É o que a comparação em ``Decimal`` garante e que uma
    comparação de cadeias perderia; e é também o que separa este caso do de ``0.001`` de
    diferença, que com tolerância zero é erro.
    """
    assert veredito(corrigir(item_de_contagem(), resposta)) is esperado


# --------------------------------------------------------------------------- #
# Leitura do decimal escrito por humano
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("texto", ["0", "0.05", "12", "1.500", "+4", "-4.25", "1000.000"])
def test_toda_forma_da_gramatica_do_arquivo_e_lida_com_o_mesmo_valor(texto: str) -> None:
    """A notação aceita na resposta é **superconjunto** da notação do banco, com o mesmo valor.

    É a invariante que impede gabarito e resposta de serem interpretados por critérios
    diferentes: ``PADRAO_DE_DECIMAL`` descreve a tolerância escrita no arquivo, e o motor
    precisa ler o gabarito — que é texto no modelo — exatamente como o carregador leria. Se um
    dia a gramática do arquivo e a de leitura divergirem, é aqui que aparece.
    """
    assert PADRAO_DE_DECIMAL.match(texto) is not None, "o caso de teste saiu da gramática do arquivo"

    assert interpretar_decimal(texto) == Decimal(texto)


@pytest.mark.parametrize(
    ("texto", "valor"),
    [
        ("1.500", Decimal("1.5")),
        ("1,500", Decimal("1.5")),
        ("1.234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("1.234.567", Decimal("1234567")),
        ("1,234,567", Decimal("1234567")),
    ],
)
def test_regra_do_separador_resolve_o_caso_ambiguo_para_o_lado_decimal(texto: str, valor: Decimal) -> None:
    """Um separador é decimal; dois, o mais à direita decide; repetido, é milhar.

    O caso ambíguo real é o primeiro par: ``1.500`` e ``1,500`` têm duas leituras possíveis, e
    a regra declarada escolhe a decimal. A razão é concreta e não de gosto — ``format(Decimal,
    "f")``, que é a forma canônica do projeto, preserva zeros à direita, de modo que um e meio
    com três casas **é** ``1.500``. Ler isso como mil e quinhentos recusaria como errada uma
    resposta escrita na notação canônica do próprio projeto. O agrupamento de milhar continua
    disponível nas formas sem ambiguidade, que são as outras quatro.
    """
    assert interpretar_decimal(texto) == valor


@pytest.mark.parametrize("texto", ["1e3", "4.", ".5", "4 5", "- 4", "", "   ", "4.5.6", "1,23,456", "nan", "inf"])
def test_notacao_sem_leitura_unica_ou_fora_da_gramatica_nao_e_numero(texto: str) -> None:
    """O que não tem leitura única declarada não é número, e o julgamento falha fechado.

    ``nan`` e ``inf`` estão na lista porque ``Decimal`` os aceitaria sem reclamar, e ``nan``
    em comparação de tolerância devolveria ``False`` — erro silencioso em vez de recusa. O
    expoente fica fora pela mesma razão que ``PADRAO_DE_DECIMAL`` não o admite.
    """
    assert interpretar_decimal(texto) is None


def test_resposta_nao_numerica_e_erro_sem_motivo_de_rejeicao() -> None:
    """Resposta que não é número é resposta **errada**, não submissão rejeitada (R4.1, R4.6).

    A distinção decide o que a TAI conta. ``motivo_rejeicao`` descreve submissão malformada —
    vazia ou acima do limite —, e marcá-lo aqui faria uma tentativa legítima de responder
    "não sei" parecer uma submissão defeituosa no registro.
    """
    julgamento = corrigir(item_semente(), "não sei")

    assert veredito(julgamento) is Resultado.ERRO
    assert julgamento.motivo_rejeicao is None


# --------------------------------------------------------------------------- #
# Formas declaradas pelo item (R2.1) e unidade declarada
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("resposta", ["4", "4.0", "quatro"])
def test_variacao_declarada_no_item_e_acerto(resposta: str) -> None:
    """O item é a fonte da verdade sobre o que conta como forma aceita do gabarito (R2.1).

    ``"quatro"`` é o caso que justifica a precedência das formas declaradas sobre a tolerância:
    numeral escrito em palavras não é número, e nenhuma tolerância o alcançaria. O banco
    inicial declara o numeral em palavras em todos os itens, então este não é caminho
    hipotético.
    """
    assert veredito(corrigir(item_semente(), resposta)) is Resultado.ACERTO


@pytest.mark.parametrize("resposta", ["QUATRO", "Quatro", "quatro.", "cuatro"])
def test_forma_nao_declarada_no_item_e_erro(resposta: str) -> None:
    """Nenhuma normalização que o banco não declarou é inventada aqui (R2.1, R4.2).

    Dobrar a caixa ou remover pontuação aceitaria silenciosamente o que o item não aceitou, e a
    decisão sobre o que é equivalente deixaria de ser revisável no arquivo — passaria a morar
    no código, onde quem escreve o banco não a vê.
    """
    assert veredito(corrigir(item_semente(), resposta)) is Resultado.ERRO


@pytest.mark.parametrize("resposta", ["7", "7 canetas", "7canetas", "7 caneta", "7 CANETAS"])
def test_unidade_declarada_pode_acompanhar_o_numero(resposta: str) -> None:
    """A unidade e os sinônimos **declarados no item** acompanham o número sem custo (R2.1).

    Não é normalização inventada: os dois campos estão no item, e o estágio 1 de §3.11 faz o
    mesmo do outro lado — para a guarda, ``"7 canetas"`` revela o valor ``7``. Se a guarda
    afirma que aquele texto carrega o valor, o motor não pode afirmar que não é o valor.
    """
    assert veredito(corrigir(item_de_contagem(), resposta)) is Resultado.ACERTO


@pytest.mark.parametrize("resposta", ["7 lápis", "7 cm", "canetas"])
def test_unidade_diferente_da_declarada_falha_fechado(resposta: str) -> None:
    """Unidade que o item não declara não é removida, e o resto não é número (R4.1).

    O desfecho é erro, e deliberadamente: aceitar qualquer sufixo faria o motor ignorar a
    grandeza, e ``7 cm`` em um item que pede contagem de canetas não é a resposta certa com
    outra roupa.
    """
    assert veredito(corrigir(item_de_contagem(), resposta)) is Resultado.ERRO


# --------------------------------------------------------------------------- #
# Alternativa: comparação exata (R4.2)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("resposta", "esperado"),
    [
        ("b) dividir os dois membros por 2", Resultado.ACERTO),
        ("  b) dividir os dois membros por 2  ", Resultado.ACERTO),
        ("B) dividir os dois membros por 2", Resultado.ERRO),
        ("b", Resultado.ERRO),
        ("c) multiplicar os dois membros por 2", Resultado.ERRO),
    ],
)
def test_alternativa_compara_exatamente_com_a_alternativa_correta(resposta: str, esperado: Resultado) -> None:
    """Exata é exata: só o espaço em volta é removido (R4.2).

    O espaço em volta sai porque a regra de resposta vazia já trata espaço como ausência de
    conteúdo, e as duas regras precisam da mesma noção de conteúdo — do contrário uma resposta
    com ``\\n`` de editor de texto seria diferente da mesma resposta sem ele. O rótulo em caixa
    alta erra: o item que quiser aceitá-lo declara a forma em ``variacoes_gabarito``.
    """
    assert veredito(corrigir(item_de_alternativa(), resposta)) is esperado


def test_alternativa_aceita_a_variacao_que_o_item_declara() -> None:
    """Declarar ``"b"`` como variação é como o banco autoriza o rótulo sozinho (R2.1, R4.2).

    Mostra onde a decisão sobre equivalência deve morar: no arquivo, não no código. A
    comparação segue exata; o que mudou foi o conjunto de formas que o item declara.
    """
    alternativa = item(
        "alg-eq-502",
        tipo_gabarito=TipoGabarito.ALTERNATIVA,
        gabarito="b) dividir os dois membros por 2",
        tolerancia=None,
        variacoes=("b",),
    )

    assert veredito(corrigir(alternativa, "b")) is Resultado.ACERTO


# --------------------------------------------------------------------------- #
# Resposta vazia e resposta acima do tamanho máximo (R4.6)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("resposta", ["", "   ", "\n", " \t\n "])
def test_resposta_vazia_ou_so_com_espaco_e_erro_com_motivo(resposta: str) -> None:
    """Vazio nunca é acerto, e o motivo é registrado (R4.6).

    Espaço em branco é ausência de conteúdo, não conteúdo em branco: se ``"   "`` fosse julgada
    pelo critério do gabarito, um item cujo gabarito tivesse espaço seria acertável por engano.
    """
    julgamento = corrigir(item_semente(), resposta)

    assert veredito(julgamento) is Resultado.ERRO
    assert julgamento.motivo_rejeicao == MOTIVO_VAZIA


def test_vazia_prevalece_sobre_excesso_quando_as_duas_condicoes_valem() -> None:
    """Com as duas condições satisfeitas, o motivo registrado é ``vazia`` (R4.6).

    A precedência é declarada porque o caso existe — cinco espaços em um item de limite 1 — e
    porque ``vazia`` é o motivo mais informativo dos dois: o problema não é o tamanho, é que
    não há nada a julgar. Sem precedência, o motivo gravado dependeria da ordem em que alguém
    escreveu os ``if``, e o evento registraria causas diferentes para a mesma submissão.
    """
    julgamento = corrigir(item(tamanho_max_resposta=1), "     ")

    assert julgamento.motivo_rejeicao == MOTIVO_VAZIA


def test_resposta_acima_do_tamanho_maximo_do_item_e_erro_antes_do_criterio() -> None:
    """O limite é do **item**, e ele decide antes do gabarito (R4.6).

    A resposta escolhida vale numericamente o gabarito: ``4,000`` é 4, e seria acerto se o
    tamanho não decidisse primeiro. É o que prova que a verificação precede o critério, em vez
    de apenas coexistir com ele. Nada é descartado — o julgamento existe, com motivo —, porque
    §7.3 falha fechado no julgamento e aberto no percurso.
    """
    julgamento = corrigir(item(tamanho_max_resposta=3), "4,000")

    assert veredito(julgamento) is Resultado.ERRO
    assert julgamento.motivo_rejeicao == MOTIVO_EXCEDE_TAMANHO_MAXIMO


def test_espaco_em_volta_nao_conta_para_o_tamanho_maximo() -> None:
    """O tamanho é medido sobre o conteúdo, não sobre o texto cru (R4.6).

    As duas regras de R4.6 passam a usar a mesma noção de conteúdo, o que é o que impede
    ``"   "`` de ser vazia e excedente ao mesmo tempo. A consequência é benigna e vale
    registrar: a medida sobre o conteúdo nunca é maior que a crua, então o motor nunca recusa
    por tamanho uma resposta que o contador de caracteres da interface aceitou.
    """
    julgamento = corrigir(item(tamanho_max_resposta=1), "  4  ")

    assert veredito(julgamento) is Resultado.ACERTO
    assert julgamento.motivo_rejeicao is None


# --------------------------------------------------------------------------- #
# Justificativa textual encaminhada a humano (R4.7)
# --------------------------------------------------------------------------- #


def test_item_textual_encaminha_a_resposta_a_rubrica_sem_veredito_automatico() -> None:
    """Não há julgamento automático de texto argumentativo (R4.7, §7.3).

    As três coisas verificadas juntas são o conteúdo da decisão: **nenhum** veredito, a
    indisponibilidade com o motivo que §7.3 declara, e a resposta inteira encaminhada. Devolver
    ``acerto`` ou ``erro`` aqui seria pior que não julgar — alimentaria a TAI com um valor que
    ninguém mediu —, e julgar por presença de ``termos_essenciais`` usaria como oráculo de
    acerto um campo que R2.11 declara para a guarda de vazamento.
    """
    resposta = "A igualdade se mantém porque a mesma operação é aplicada aos dois membros."

    julgamento = corrigir(item_textual(), resposta)

    assert julgamento.resultado == Indisponivel(MOTIVO_AGUARDANDO_RUBRICA)
    assert not e_julgado(julgamento.resultado)
    assert julgamento.partes_para_rubrica == (resposta,)
    assert julgamento.motivo_rejeicao is None


def test_resposta_textual_vazia_e_rejeitada_antes_de_chegar_a_rubrica() -> None:
    """Justificativa vazia não tem o que um avaliador humano julgue (R4.6, R4.7).

    As verificações de R4.6 não dependem do tipo de gabarito, e esta é a razão: encaminhar uma
    parte vazia à rubrica consumiria tempo de professor para olhar nada.
    """
    julgamento = corrigir(item_textual(), "   ")

    assert veredito(julgamento) is Resultado.ERRO
    assert julgamento.motivo_rejeicao == MOTIVO_VAZIA
    assert julgamento.partes_para_rubrica == ()


@pytest.mark.parametrize("resposta", ["4", "4.0", "quatro", "5", "não sei", "", "4" * 200])
def test_nenhum_julgamento_de_item_numerico_encaminha_parte_a_rubrica(resposta: str) -> None:
    """Rubrica humana é caminho do item textual, e de nenhum outro (R4.7).

    Encaminhar parte de item numérico produziria fila de avaliação para o que a correção
    automática já julgou, e o professor passaria a revisar acerto de aritmética.
    """
    assert corrigir(item_semente(), resposta).partes_para_rubrica == ()


# --------------------------------------------------------------------------- #
# Justificativa: critério aplicado, nunca o gabarito (R4.3)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("resposta", ["137", "cento e trinta e sete", "140", "não sei", "", "1" * 300])
def test_justificativa_nao_cita_o_gabarito_nem_suas_variacoes(resposta: str) -> None:
    """A justificativa nomeia o critério e não o conteúdo do item (R4.3, R7.6).

    O ``Julgamento`` volta para quem apresenta a submissão ao estudante, e R4.3 pede
    justificativa "em termos do gabarito aplicado" — as duas coisas só são compatíveis se
    "em termos do gabarito" significar **qual critério decidiu**, e não qual é o valor. Mesma
    regra de ``itens/erros.py``, onde mensagem de erro não cita conteúdo, pelo mesmo motivo: o
    texto chega a log, a tela e, no limite, a uma captura de tela em sala.

    O gabarito deste item é ``137`` para que a verificação seja possível: com o gabarito ``4``
    do item semente, qualquer referência a requisito — ``R4.1``, ``R4.6`` — daria falso
    positivo, e o teste passaria a medir a grafia das citações em vez do sigilo.
    """
    com_gabarito_distintivo = item(
        "alg-eq-701",
        enunciado="Quantos ingressos foram vendidos?",
        gabarito="137",
        variacoes=("cento e trinta e sete",),
        tamanho_max_resposta=200,
    )

    justificativa = corrigir(com_gabarito_distintivo, resposta).justificativa

    assert "137" not in justificativa
    assert "cento e trinta e sete" not in justificativa


def test_justificativa_numerica_nomeia_a_tolerancia_aplicada() -> None:
    """A tolerância aplicada **pode** aparecer, e é o que torna a justificativa útil (R4.3).

    Dela não se deriva nenhum valor de gabarito, e §4.2 já grava ``tolerancia_aplicada`` em
    ``resposta_submetida`` — a tolerância não é segredo; o gabarito é. O desvio medido, ao
    contrário, fica fora: quem conhece a própria resposta e o desvio reconstrói o gabarito.
    """
    julgamento = corrigir(item_semente(), "5")

    assert "0.05" in julgamento.justificativa


def test_tolerancia_zero_e_nomeada_como_igualdade_exata_na_justificativa() -> None:
    """Com tolerância zero, dizer "tolerância 0" explica menos que dizer o que ela exige."""
    assert "igualdade exata" in corrigir(item_de_contagem(), "8").justificativa


# --------------------------------------------------------------------------- #
# Invariantes do valor devolvido
# --------------------------------------------------------------------------- #


def test_julgamento_recusa_motivo_de_rejeicao_ao_lado_de_acerto() -> None:
    """Motivo de rejeição só existe junto de ``erro`` (R4.6).

    A combinação proibida descreveria uma submissão rejeitada e aceita ao mesmo tempo, e o par
    ``(resultado, motivo_correcao)`` do evento ficaria contraditório no registro — com a
    contradição descoberta na leitura dos dados, meses depois da coleta.
    """
    with pytest.raises(ValueError, match="motivo de rejeição"):
        Julgamento(
            resultado=Resultado.ACERTO,
            justificativa="qualquer critério",
            motivo_rejeicao=MOTIVO_VAZIA,
            partes_para_rubrica=(),
        )


def test_julgamento_exige_justificativa_nao_vazia() -> None:
    """R4.3 pede a justificativa registrada; vazia seria o campo cumprido sem a informação."""
    with pytest.raises(ValueError, match="justificativa"):
        Julgamento(
            resultado=Resultado.ERRO,
            justificativa="   ",
            motivo_rejeicao=None,
            partes_para_rubrica=(),
        )
