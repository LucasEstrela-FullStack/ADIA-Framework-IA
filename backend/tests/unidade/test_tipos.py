"""Testes dos tipos de valor compartilhados de `adia.tipos` (R11.7, R12.3, §3.0).

Tipo de valor tem pouca lógica para testar, e testar enumeração membro a membro seria
duplicar a declaração. O que estes testes afirmam é o que **não** é evidente na leitura e o
que outras partes do protótipo vão presumir:

- a ordenação de `Nivel` é ordenação de verdade, porque descer o teto é caminhar para L1 e a
  saturação de R9.6 e R9.7 é o comportamento nas bordas;
- `ETAPAS_SEM_IA` é exatamente o conjunto que R8.6 e a Propriedade 21 enumeram, nem mais
  nem menos — um membro a mais abriria caminho de IA onde a proficiência é medida, um a
  menos tiraria respostas legítimas do cálculo;
- `POSTESTE` resolve no desafio independente do terceiro ciclo, e os dois nomes apontam para
  o mesmo conjunto de respostas sem que existam duas fontes de verdade (R12.3);
- zero e indisponível são coisas distintas em tempo de execução, e não só para o
  verificador de tipo (R11.7). A parte que o verificador garante está em
  `backend/tests/conjuntos/tipos_medida.py`; aqui fica a parte que se observa executando;
- os rótulos das enumerações são o **formato de registro** do evento e da exportação, não
  nomes internos: `StrEnum` e `IntEnum` escrevem o próprio texto, e um `Enum` comum
  escreveria `Condicao.A` no CSV sem que nenhum verificador reclamasse (R11.12, R26).

**Validates: Requirements 11.7, 12.3**
"""

from __future__ import annotations

import dataclasses
import operator
from decimal import Decimal

import pytest

from adia.tipos import (
    CICLO_DO_POSTESTE,
    ETAPAS_SEM_IA,
    Condicao,
    ConjuntoDeRespostas,
    EscopoDeCalculo,
    Etapa,
    Indisponivel,
    Medida,
    Nivel,
    TipoDecisao,
    conjunto_de_respostas,
    e_disponivel,
)

# --------------------------------------------------------------------------- #
# Nivel — a ordenação é usada como ordenação
# --------------------------------------------------------------------------- #


def test_a_diretividade_cresce_de_l1_a_l4() -> None:
    """L1 metacognitivo é a menor diretividade; L4 exemplo resolvido é a maior (R6.1)."""
    assert list(Nivel) == [Nivel.L1, Nivel.L2, Nivel.L3, Nivel.L4]
    assert Nivel.L1 < Nivel.L2 < Nivel.L3 < Nivel.L4
    assert min(Nivel) is Nivel.L1
    assert max(Nivel) is Nivel.L4


def test_descer_o_teto_caminha_para_l1_e_subir_caminha_para_l4() -> None:
    """A regra de regulação compara níveis e a saturação é o comportamento nas bordas."""
    assert Nivel(Nivel.L3 - 1) is Nivel.L2
    assert Nivel(Nivel.L3 + 1) is Nivel.L4
    assert Nivel.L1 == min(Nivel.L1, Nivel.L2)  # borda inferior de R9.6
    assert Nivel.L4 == max(Nivel.L4, Nivel.L3)  # borda superior de R9.7


def test_o_nivel_maximo_e_o_denominador_do_dss() -> None:
    """R11.4 fixa o denominador em `4 × itens praticados`, e 4 é `Nivel.L4`."""
    assert int(Nivel.L4) == 4

# --------------------------------------------------------------------------- #
# ETAPAS_SEM_IA — exatamente a enumeração de R8.6 e da Propriedade 21
# --------------------------------------------------------------------------- #

# O conjunto reescrito à mão, a partir da enumeração literal de R8.6 — "linha de base,
# desafio independente, pós-teste e teste de retenção" — e da Propriedade 21, que nomeia as
# mesmas quatro. Reescrever em vez de derivar do módulo é o ponto do teste: derivar faria
# esta afirmação concordar com qualquer alteração de `ETAPAS_SEM_IA`, inclusive com a errada.
ETAPAS_ENUMERADAS_PELOS_REQUISITOS = frozenset(
    {
        Etapa.LINHA_DE_BASE,
        Etapa.DESAFIO_INDEPENDENTE,
        Etapa.POSTESTE,
        Etapa.TESTE_RETENCAO,
    }
)

# O complemento, também à mão: prática assistida e gatilho de *fading* oferecem dica dentro
# do teto vigente, e o projeto STEAM admite apoio da IA em parte da tarefa (R13).
ETAPAS_COM_IA = frozenset(
    {
        Etapa.PRATICA_ASSISTIDA,
        Etapa.GATILHO_FADING,
        Etapa.PROJETO_STEAM,
    }
)


def test_etapas_sem_ia_e_exatamente_o_conjunto_que_os_requisitos_enumeram() -> None:
    """Nem mais nem menos (R8.6, Propriedade 21).

    Um membro a mais abriria caminho de IA onde a proficiência é medida; um a menos tiraria
    respostas legítimas do cálculo de TAI, TT e Retenção.
    """
    assert ETAPAS_SEM_IA == ETAPAS_ENUMERADAS_PELOS_REQUISITOS


def test_a_particao_entre_com_e_sem_ia_cobre_todas_as_etapas_declaradas() -> None:
    """Etapa nova obriga a decidir de que lado ela fica, em vez de cair no lado sem IA.

    Sem esta afirmação, acrescentar membro a `Etapa` o deixaria fora de `ETAPAS_SEM_IA` por
    omissão — e a omissão é indistinguível da decisão de que ali há IA.
    """
    assert ETAPAS_SEM_IA.isdisjoint(ETAPAS_COM_IA)
    assert ETAPAS_SEM_IA | ETAPAS_COM_IA == frozenset(Etapa)


def test_o_conjunto_e_imutavel_e_nenhum_modulo_o_amplia_em_execucao() -> None:
    """`frozenset` e não `set`: a lista de etapas sem IA não é configurável em execução."""
    assert isinstance(ETAPAS_SEM_IA, frozenset)
    assert not hasattr(ETAPAS_SEM_IA, "add")
    assert not hasattr(ETAPAS_SEM_IA, "discard")


def _resolver(escopo: EscopoDeCalculo) -> ConjuntoDeRespostas:
    """Resolve o escopo informando ciclo apenas onde o escopo exige um (R11.1)."""
    if escopo is EscopoDeCalculo.DESAFIO_INDEPENDENTE:
        return conjunto_de_respostas(escopo, 1)
    return conjunto_de_respostas(escopo)


@pytest.mark.parametrize("escopo", list(EscopoDeCalculo))
def test_todo_escopo_de_calculo_se_apoia_em_respostas_de_etapa_sem_ia(escopo: EscopoDeCalculo) -> None:
    """R8.6: proficiência sai exclusivamente de respostas registradas em etapas sem IA.

    A varredura sobre `EscopoDeCalculo` também cobre a resolução: escopo acrescentado à
    enumeração e esquecido em `conjunto_de_respostas` não tem como passar por aqui.
    """
    assert _resolver(escopo).etapa in ETAPAS_SEM_IA


# --------------------------------------------------------------------------- #
# POSTESTE — rótulo sobre o desafio independente do terceiro ciclo (R12.3)
# --------------------------------------------------------------------------- #


def test_o_posteste_resolve_no_desafio_independente_do_terceiro_ciclo() -> None:
    """R12.3: o pós-teste é o conjunto de itens sem IA do terceiro ciclo, não outro conjunto."""
    conjunto = conjunto_de_respostas(EscopoDeCalculo.POSTESTE)

    assert conjunto.etapa is Etapa.DESAFIO_INDEPENDENTE
    assert conjunto.ciclo == CICLO_DO_POSTESTE
    assert CICLO_DO_POSTESTE == 3


def test_os_dois_nomes_apontam_para_o_mesmo_conjunto_sem_duas_fontes_de_verdade() -> None:
    """A igualdade é a afirmação: um conjunto de respostas, dois nomes (R12.3).

    `len({...}) == 1` é o que diz "um", e não dois que por acaso coincidem: se os valores
    divergissem em etapa ou em ciclo, o conjunto teria dois elementos e a mesma resposta
    passaria a ser contada sob dois rótulos.
    """
    pelo_rotulo = conjunto_de_respostas(EscopoDeCalculo.POSTESTE)
    pelo_ciclo = conjunto_de_respostas(EscopoDeCalculo.DESAFIO_INDEPENDENTE, CICLO_DO_POSTESTE)

    assert pelo_rotulo == pelo_ciclo
    assert hash(pelo_rotulo) == hash(pelo_ciclo)
    assert len({pelo_rotulo, pelo_ciclo}) == 1


def test_a_identificacao_nas_metricas_segue_distinta_do_conjunto_de_respostas() -> None:
    """R11.1 e R11.6: mesmo conjunto, nomes distintos — a Retenção divide um escopo pelo outro.

    A distinção não é redundância. `Retenção = TAI(teste_retencao) ÷ TAI(posteste)` precisa
    de um denominador com nome estável, que não dependa de quem calcula saber que o
    protocolo tem três ciclos. As duas contagens abaixo são a afirmação inteira: dois nomes,
    um conjunto.
    """
    nomes_nas_metricas = {EscopoDeCalculo.POSTESTE, EscopoDeCalculo.DESAFIO_INDEPENDENTE}
    conjuntos_de_respostas = {
        conjunto_de_respostas(EscopoDeCalculo.POSTESTE),
        conjunto_de_respostas(EscopoDeCalculo.DESAFIO_INDEPENDENTE, CICLO_DO_POSTESTE),
    }

    assert len(nomes_nas_metricas) == 2
    assert len(conjuntos_de_respostas) == 1
    assert conjunto_de_respostas(EscopoDeCalculo.POSTESTE) != conjunto_de_respostas(
        EscopoDeCalculo.TESTE_RETENCAO
    )


@pytest.mark.parametrize("ciclo", [1, 2])
def test_so_o_terceiro_ciclo_e_o_posteste(ciclo: int) -> None:
    """Os desafios independentes dos dois primeiros ciclos não são o pós-teste da sessão."""
    assert conjunto_de_respostas(EscopoDeCalculo.DESAFIO_INDEPENDENTE, ciclo) != conjunto_de_respostas(
        EscopoDeCalculo.POSTESTE
    )


def test_o_posteste_aceita_o_terceiro_ciclo_explicito_e_recusa_qualquer_outro() -> None:
    """Informar o ciclo é redundante, mas informar o ciclo errado é afirmação falsa."""
    assert conjunto_de_respostas(EscopoDeCalculo.POSTESTE, CICLO_DO_POSTESTE) == conjunto_de_respostas(
        EscopoDeCalculo.POSTESTE
    )
    with pytest.raises(ValueError, match="pós-teste é o conjunto sem IA do ciclo"):
        conjunto_de_respostas(EscopoDeCalculo.POSTESTE, 2)


def test_nenhum_conjunto_de_respostas_carrega_o_rotulo_de_posteste() -> None:
    """O rótulo existe na enumeração de etapas e não existe no par que identifica respostas.

    As duas metades importam. `Etapa.POSTESTE` está em `ETAPAS_SEM_IA` porque é assim que o
    conjunto corresponde, literalmente, à enumeração de R8.6 e da Propriedade 21, e porque
    R2.4 exige um rótulo de pós-teste nas etapas permitidas de um item. Mas nenhum evento
    carrega essa etapa: o evento registra `DESAFIO_INDEPENDENTE` com `ciclo = 3`, e é em
    `conjunto_de_respostas` que o rótulo se resolve. Gravar as mesmas respostas sob dois
    rótulos de etapa é a segunda fonte de verdade que R12.3 descarta.
    """
    assert Etapa.POSTESTE in ETAPAS_SEM_IA

    with pytest.raises(ValueError, match="rótulo, não etapa executada"):
        ConjuntoDeRespostas(Etapa.POSTESTE, CICLO_DO_POSTESTE)

    for escopo in EscopoDeCalculo:
        assert _resolver(escopo).etapa is not Etapa.POSTESTE


def test_o_ciclo_e_exigido_onde_qualifica_e_recusado_onde_nao_existe() -> None:
    """Escopo mal qualificado é erro, não valor silencioso: ciclo ausente não vira ciclo 1."""
    with pytest.raises(ValueError, match="informe o ciclo"):
        conjunto_de_respostas(EscopoDeCalculo.DESAFIO_INDEPENDENTE)

    with pytest.raises(ValueError, match="uma única vez na sessão"):
        conjunto_de_respostas(EscopoDeCalculo.LINHA_DE_BASE, 1)

    with pytest.raises(ValueError, match="uma única vez na sessão"):
        conjunto_de_respostas(EscopoDeCalculo.TESTE_RETENCAO, CICLO_DO_POSTESTE)


@pytest.mark.parametrize("ciclo", [0, -1])
def test_ciclo_nao_positivo_nao_descreve_repeticao_nenhuma_do_protocolo(ciclo: int) -> None:
    """O protocolo tem três ciclos numerados de 1; `0` e negativos não nomeiam conjunto algum."""
    with pytest.raises(ValueError, match="inteiro positivo"):
        ConjuntoDeRespostas(Etapa.DESAFIO_INDEPENDENTE, ciclo)


def test_o_conjunto_de_respostas_serve_de_chave_estavel_para_a_metrica() -> None:
    """Cada valor de métrica carrega o escopo que o produziu (R11.1); a chave tem de ser uma.

    Guardar a TAI sob o par do terceiro ciclo e encontrá-la pelo nome do pós-teste é a forma
    mais curta de mostrar que a equivalência vale onde ela é usada — e `dataclasses.replace`
    mostra que mudar o ciclo produz outro valor em vez de alterar este.
    """
    por_escopo = {conjunto_de_respostas(EscopoDeCalculo.DESAFIO_INDEPENDENTE, CICLO_DO_POSTESTE): "TAI"}
    assert por_escopo[conjunto_de_respostas(EscopoDeCalculo.POSTESTE)] == "TAI"

    conjunto = conjunto_de_respostas(EscopoDeCalculo.POSTESTE)
    assert dataclasses.replace(conjunto, ciclo=1).ciclo == 1
    assert conjunto.ciclo == CICLO_DO_POSTESTE

    # Nome do campo em variável, e não literal, porque a atribuição direta não passa pelo
    # `mypy --strict` e `setattr` com nome constante é armadilha que o `ruff` sinaliza (B010).
    campo_do_ciclo = "ciclo"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(conjunto, campo_do_ciclo, 1)


# --------------------------------------------------------------------------- #
# Medida — zero e indisponível são distintos em execução, não só no verificador
# --------------------------------------------------------------------------- #

ZERO = Decimal("0")
"""Zero medido: desempenho legítimo de quem errou tudo no escopo."""

MOTIVO = "denominador zero: nenhum item sem IA registrado no escopo"
"""Motivo de indisponibilidade na forma que R11.7 exige registrar."""


def test_zero_e_medida_disponivel_e_significa_mediu_zero() -> None:
    """A simetria que R11.7 pede nos dois sentidos: zero continua sendo valor, não ausência."""
    medida: Medida = ZERO

    assert e_disponivel(medida)
    assert ZERO.quantize(Decimal("0.0001")) == Decimal("0.0000")


def test_a_ausencia_nao_e_numero_em_execucao() -> None:
    """O que `tipos_medida.py` prova no verificador, aqui se observa executando (R11.7).

    As ausências de `__float__`, `__int__` e `__add__` são verificadas diretamente porque
    são elas que o cabeçalho de `adia/tipos.py` promete: herdar de `Decimal` ou ganhar
    qualquer uma delas seria o caminho por onde a ausência voltaria a somar como zero.
    """
    ausente = Indisponivel(MOTIVO)
    medida: Medida = ausente

    assert not e_disponivel(medida)
    assert not isinstance(medida, Decimal)
    assert not hasattr(ausente, "__float__")
    assert not hasattr(ausente, "__int__")
    assert not hasattr(ausente, "__add__")
    assert ausente.motivo == MOTIVO


def test_somar_dividir_e_ordenar_a_ausencia_falham_sobre_a_ausencia() -> None:
    """As operações que a regra de regulação e as métricas derivadas fazem (§3.4, P13).

    As duas primeiras passam por `operator` porque a forma infixa não é escrevível aqui — o
    `mypy --strict` a recusa, e é justamente essa recusa que `tipos_medida.py` fixa. Mesmo
    assim elas valem como teste de execução: é por um caminho dinâmico, que o verificador
    não acompanha, que uma ausência chegaria a uma soma.

    A ordenação não tem contraparte de execução escrevível, e a razão é a própria garantia:
    `Indisponivel` não satisfaz o protocolo de comparação, então nem a chamada por
    `operator.lt` compila. O que se observa aqui é a causa estrutural — `order=False` no
    `dataclass`, logo nenhum comparador próprio. `hasattr` não serviria: `object` já fornece
    os quatro como fachada que devolve `NotImplemented`, e por isso a busca é em `vars`.
    """
    ausente = Indisponivel(MOTIVO)

    with pytest.raises(TypeError):
        operator.add(ausente, Decimal("1"))

    with pytest.raises(TypeError):
        operator.truediv(ZERO, ausente)

    for comparador in ("__lt__", "__le__", "__gt__", "__ge__"):
        assert comparador not in vars(Indisponivel)


def test_a_ausencia_nao_tem_valor_de_verdade() -> None:
    """`medida or Decimal(0)` falha alto em vez de silenciosamente virar zero (R11.7, D3).

    A armadilha é concreta e está na primeira linha: `Decimal("0")` é **falso**. Se
    `Indisponivel` fosse verdadeiro, como todo objeto é por padrão, `if medida:` inverteria
    o significado dos dois casos — a TAI de exatamente zero, que é desempenho medido, seria
    tratada como ausência, e a ausência como valor.
    """
    ausente = Indisponivel(MOTIVO)

    assert bool(ZERO) is False

    with pytest.raises(TypeError, match="valor de verdade"):
        bool(ausente)

    with pytest.raises(TypeError, match="valor de verdade"):
        _ = ausente or ZERO

    with pytest.raises(TypeError, match="valor de verdade"):
        _ = not ausente


def test_zero_e_a_ausencia_nao_se_confundem_por_igualdade() -> None:
    """Nem a ausência passa por zero, nem zero passa pela ausência."""
    ausente: Medida = Indisponivel(MOTIVO)
    zero: Medida = ZERO

    assert ausente != zero
    assert zero != ausente
    assert zero == Decimal("0.0000")


def test_a_ausencia_exige_motivo_porque_sem_motivo_seria_zero_com_outro_nome() -> None:
    """R11.7 manda registrar **o motivo**; §7.8 exige o motivo na tela, no lugar do valor."""
    for motivo in ("", " ", "\t\n"):
        with pytest.raises(ValueError, match="motivo não vazio"):
            Indisponivel(motivo)


def test_a_ausencia_e_congelada_e_o_motivo_integra_a_identidade() -> None:
    """Duas indisponibilidades com motivos diferentes não são o mesmo valor."""
    ausente = Indisponivel(MOTIVO)

    assert ausente == Indisponivel(MOTIVO)
    assert ausente != Indisponivel("escopo sem nenhuma resposta registrada")

    campo_do_motivo = "motivo"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(ausente, campo_do_motivo, "outro motivo")


def test_e_disponivel_torna_os_dois_ramos_alcancaveis() -> None:
    """A distinção obrigatória tem uma forma idiomática, e o ramo da ausência é tipado.

    O laço roda os dois casos pela mesma expressão, que é o uso real: quem apresenta uma
    medida não sabe de antemão qual dos dois lados chegou.
    """
    medidas: tuple[Medida, ...] = (ZERO, Indisponivel(MOTIVO))

    apresentadas = []
    for medida in medidas:
        if e_disponivel(medida):
            apresentadas.append(str(medida.quantize(Decimal("0.01"))))
        else:
            apresentadas.append(f"indisponível: {medida.motivo}")

    assert apresentadas == ["0.00", f"indisponível: {MOTIVO}"]


# --------------------------------------------------------------------------- #
# Os rótulos são o formato de registro, não nomes internos
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("rotulo", "texto"),
    [
        (Etapa.DESAFIO_INDEPENDENTE, "desafio_independente"),
        (Etapa.POSTESTE, "posteste"),
        (EscopoDeCalculo.POSTESTE, "posteste"),
        (Condicao.A, "A"),
        (Condicao.B, "B"),
        (Condicao.C, "C"),
        (TipoDecisao.FADING, "fading"),
        (TipoDecisao.ONLOADING, "onloading"),
        (TipoDecisao.ESCALONAR, "escalonar"),
        (TipoDecisao.MANTER, "manter"),
    ],
)
def test_o_rotulo_se_escreve_como_o_proprio_texto(rotulo: str, texto: str) -> None:
    """`StrEnum`, e não `Enum`: a interpolação é o que vai ao evento e ao CSV (R11.12, R26).

    `f"{...}"` é a metade que importa. Com `Enum` comum a igualdade com o texto já falharia,
    mas com `IntEnum`-como-`Enum` a interpolação é o caminho que escapa calado: o CSV
    receberia `Condicao.A` onde o protocolo declara `A`, e nenhum verificador reclamaria.
    """
    assert rotulo == texto
    assert f"{rotulo}" == texto


def test_o_nivel_se_escreve_como_o_proprio_inteiro() -> None:
    """`IntEnum`: o teto vai ao registro como `4`, não como `Nivel.L4`.

    A variável anotada como `int` é o segundo lado disso: o membro é aceito onde se espera
    inteiro, que é o que torna `4 × itens praticados` de R11.4 escrevível com `Nivel.L4`.
    """
    assert f"{Nivel.L4}" == "4"

    denominador_do_dss: int = Nivel.L4
    assert denominador_do_dss == 4


def test_os_vocabularios_de_rotulo_nao_colidem_onde_nao_devem() -> None:
    """Colisão de rótulo entre vocabulários distintos tornaria a linha do registro ambígua.

    A exceção é deliberada e está na última afirmação: todo rótulo de escopo **é** um rótulo
    de etapa, e é por isso que `Etapa.POSTESTE` precisa existir. O escopo nomeia o conjunto
    de respostas de uma etapa sem IA; se o vocabulário divergisse, `conjunto_de_respostas`
    teria de traduzir nomes além de resolver o rótulo de pós-teste.
    """
    etapas = {str(etapa) for etapa in Etapa}
    decisoes = {str(decisao) for decisao in TipoDecisao}
    condicoes = {str(condicao) for condicao in Condicao}

    assert decisoes.isdisjoint(etapas)
    assert condicoes.isdisjoint(etapas)
    assert condicoes.isdisjoint(decisoes)
    assert {str(escopo) for escopo in EscopoDeCalculo} <= etapas
