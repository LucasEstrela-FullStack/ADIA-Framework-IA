"""Propriedade 33: o conjunto do desafio independente vem inteiro ou não vem.

`p29_item_ida_e_volta.py` fixou a forma dos arquivos de propriedade — um arquivo, uma
propriedade, um teste; etiqueta na primeira linha do corpo; orçamento de exemplos vindo do
perfil de `backend/tests/conftest.py`; geradores nomeados em `estrategias.py`; afirmação de
apoio como teste separado e **sem** `@given`. Este arquivo segue aquela forma sem a repetir: o
que está documentado abaixo é o que é de P33.

O enunciado de §5.6 é uma **disjunção**, e as duas metades são afirmadas:

- **sucesso** — exatamente um equivalente elegível para cada item praticado do ciclo, mais ao
  menos um item de transferência elegível da mesma habilidade alvo, **e nenhum outro item**;
- **recusa** — `ErroDeConjuntoIncompleto` que identifica o item praticado e a associação
  indisponível, **sem nenhum item devolvido**.

O conjunto parcial é a falha que a propriedade existe para impedir. Ele produziria desafio
independente de tamanho diferente do praticado, e o *gap* entre `acerto_assistido` e
`acerto_independente` — entrada da regra de regulação (§3.4) — passaria a comparar denominadores
distintos. A decisão de teto do ciclo seguinte sairia de uma diferença que não mede diferença
nenhuma, e nada na tela pareceria errado.

## Por que a cardinalidade é afirmada contra o pedido, e não pelo tipo

`ConjuntoDoDesafio.__post_init__` verifica bastante: praticado repetido, equivalente servindo dois
praticados, item em duas posições, perfil e etapa dos itens de transferência. Mas há uma metade de
R2.3 que ele **não tem como** verificar, e vale dizer qual, porque é ela que decide a forma desta
propriedade: o construtor não vê a solicitação. Um conjunto com **menos pares que os itens
praticados do ciclo** é internamente coerente e passa pelo construtor sem queixa — ele é um
conjunto válido de um ciclo menor. Isto é, o conjunto parcial que §5.6 existe para impedir é
exatamente a forma de conjunto errado que o tipo de retorno não barra.

Daí a regra que o arquivo segue: toda afirmação de cardinalidade é feita contra o **pedido e o
banco**, nunca contra o valor devolvido. Correspondência praticado por praticado a partir dos
praticados pedidos; qualificação de R2.2 pelos predicados públicos de `modelo.py`; as três
exclusões de elegibilidade; a origem de cada item devolvido numa relação declarada; e o tamanho
`praticados + TRANSFERENCIAS_NO_CONJUNTO`. Uma propriedade que se contentasse com
`isinstance(resultado, ConjuntoDoDesafio)` estaria verificando o construtor — e passaria verde
sobre um banco que devolve meio conjunto.

## O que esta propriedade acrescenta aos casos dirigidos

`backend/tests/unidade/test_banco_de_itens.py` tem um caso dirigido para cada uma das lacunas, e
é lá que moram as afirmações sobre a **contabilidade** da recusa — quantos candidatos
qualificaram, quantos caíram por etapa, por prática e por apresentação. O que é novo aqui:

- a entrada é **gerada**: conteúdo de item no domínio inteiro de `Item` (três tipos de gabarito,
  tolerância decimal, coleções, acentuação, as quinze classes de texto adversário), quantidade
  variável de praticados, candidato compartilhado entre todos eles, itens de transferência
  excedentes, três concorrentes inelegíveis, histórico de R2.7 sobre os dispensáveis, semente de
  seleção sorteada e ordem do pedido permutada;
- a disjunção é afirmada **como disjunção**: o mesmo teste decide, pelo regime do banco, qual das
  duas metades exigir. Oito casos dirigidos afirmam oito pontos; a propriedade afirma que não há
  um nono ponto em que o banco devolva meio conjunto.

## Os regimes de geração, e a precedência que eles respeitam

§5.6 pede bancos em dois regimes: **completos**, em que o pedido tem de ter sucesso com
cardinalidade exata, e **com lacunas deliberadas**, em que ele tem de falhar com conjunto vazio.
As lacunas nomeadas são três, e a terceira tem duas realizações distintas no banco:

| Regime                        | O que falta                                        | Lacuna             |
|-------------------------------|----------------------------------------------------|--------------------|
| `SEM_EQUIVALENTE_DECLARADO`   | nenhuma relação `equivalente` toca o alvo          | sem candidato      |
| `EQUIVALENTES_DESQUALIFICADOS`| a relação existe e não cumpre R2.2                 | sem candidato      |
| `SEM_TRANSFERENCIA`           | a habilidade não tem item de transferência         | sem candidato      |
| `ELEGIBILIDADE_ESGOTADA`      | os candidatos existem e já foram apresentados      | já apresentado     |

As duas primeiras são a mesma lacuna de §5.6 — "equivalente ausente" — por dois caminhos que o
banco não distingue e o autor do arquivo sim: relação esquecida e relação escrita que não
qualifica. `_verificar_associacoes` do carregador trata a segunda como ausência, e aqui ela
existe para que a propriedade não passe a depender de a relação estar simplesmente faltando.

A lacuna **exata** é afirmada, e isso obriga a respeitar a precedência de `DO-34`
(`JA_APRESENTADO` > `PRATICADO_NO_CICLO` > `FORA_DA_ETAPA` > `DISPUTADO` >
`SEM_CANDIDATO_QUALIFICADO`): num banco com duas causas simultâneas, o banco relata a de maior
precedência, e afirmar a outra faria o teste falhar sobre código correto. As mutações abaixo são
construídas com isso em vista — `ELEGIBILIDADE_ESGOTADA` consome **todos** os candidatos do alvo,
de modo que `JA_APRESENTADO` é a causa de maior precedência presente, e as três lacunas de "sem
candidato" zeram a contagem de qualificados, que é a única forma de `SEM_CANDIDATO_QUALIFICADO`
ser a resposta correta.

## O limite que a propriedade não alcança

`LacunaDoConjunto.DISPUTADO` fica fora, e a razão é de método: gerar a disputa com desfecho
previsível exigiria do gerador a decisão de viabilidade do emparelhamento, isto é, o algoritmo do
banco reescrito dentro do teste — e um oráculo que é uma segunda cópia do código verificado não
verifica nada. O caso está em `test_candidato_disputado_e_reacomodado_em_vez_de_recusado`. Pela
mesma decisão de escopo ficam fora o pedido incoerente (praticados de uma habilidade e
`habilidade` de outra) e o conflito de R2.9, que é recusa de **carga** e não de seleção.

Nada aqui toca disco: o banco é montado em memória a partir de `CargaConcluida`, exatamente como
`BancoDeItens` o recebe depois de uma carga de verdade. É o que dispensa esta propriedade do
`deadline=None` que P29 e P30 precisam declarar — o corpo do teste é uma construção de índice
sobre poucos itens e uma chamada, e o prazo por exemplo da biblioteca mede o corpo, não a
geração.

**Validates: Requirements 2.3, 2.10**
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, replace
from enum import StrEnum, unique
from typing import Final

import pytest
from estrategias import PedidoDoDesafio, carga_ordenada, pedidos_do_desafio
from hypothesis import Phase, find, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import DrawFn

from adia.nucleo.itens.banco import (
    ETAPA_DO_CONJUNTO,
    TRANSFERENCIAS_NO_CONJUNTO,
    BancoDeItens,
    ConjuntoDoDesafio,
    ResultadoDoConjunto,
)
from adia.nucleo.itens.erros import (
    CODIGO_CONJUNTO_INDISPONIVEL,
    ErroDeConjuntoIncompleto,
    LacunaDoConjunto,
)
from adia.nucleo.itens.modelo import (
    EQUIVALENTE,
    TRANSFERENCIA,
    Item,
    TipoDeRelacao,
    e_de_transferencia_da_habilidade,
    equivalente_qualifica,
)


@unique
class Regime(StrEnum):
    """O regime de geração do banco, que decide qual metade da disjunção exigir (§5.6).

    `COMPLETO` é o primeiro membro porque é para ele que o encolhimento caminha: o banco que
    atende o pedido é o contraexemplo mais legível dos cinco, e é o único em que o conjunto
    devolvido aparece no relatório de falha.
    """

    COMPLETO = "completo"
    SEM_EQUIVALENTE_DECLARADO = "sem_equivalente_declarado"
    EQUIVALENTES_DESQUALIFICADOS = "equivalentes_desqualificados"
    SEM_TRANSFERENCIA = "sem_transferencia"
    ELEGIBILIDADE_ESGOTADA = "elegibilidade_esgotada"


@dataclass(frozen=True)
class RecusaEsperada:
    """O que a recusa tem de dizer em cada regime de lacuna (R2.10, DO-34)."""

    associacao: TipoDeRelacao
    lacuna: LacunaDoConjunto


RECUSA_ESPERADA: Final[Mapping[Regime, RecusaEsperada]] = {
    Regime.SEM_EQUIVALENTE_DECLARADO: RecusaEsperada(EQUIVALENTE, LacunaDoConjunto.SEM_CANDIDATO_QUALIFICADO),
    Regime.EQUIVALENTES_DESQUALIFICADOS: RecusaEsperada(EQUIVALENTE, LacunaDoConjunto.SEM_CANDIDATO_QUALIFICADO),
    Regime.SEM_TRANSFERENCIA: RecusaEsperada(TRANSFERENCIA, LacunaDoConjunto.SEM_CANDIDATO_QUALIFICADO),
    Regime.ELEGIBILIDADE_ESGOTADA: RecusaEsperada(EQUIVALENTE, LacunaDoConjunto.JA_APRESENTADO),
}
"""Desfecho exigido de cada lacuna. Fica ao lado do `Regime` para que um regime acrescentado sem
desfecho declarado apareça na revisão — e, antes dela, como `KeyError` no primeiro exemplo."""


# --------------------------------------------------------------------------- #
# Oráculo: o universo de candidatos, a partir do banco e do pedido
#
# O oráculo é sobre o **universo**, nunca sobre a escolha. Qual candidato elegível entra é decisão
# da semente e do emparelhamento máximo do banco, e reproduzir qualquer das duas aqui trocaria a
# propriedade por uma comparação do código com uma segunda cópia dele mesmo. O que as funções
# abaixo respondem é "de onde este item podia ter vindo?", e o critério de R2.2 vem inteiro de
# `modelo.py`, que é o mesmo que o carregador e o banco aplicam.
# --------------------------------------------------------------------------- #


def vizinhos_equivalentes(pedido: PedidoDoDesafio, praticado: str) -> tuple[Item, ...]:
    """Itens ligados ao praticado por relação `equivalente`, nas **duas** direções.

    As duas direções porque a direção da relação é informativa, não normativa (seção 4 de
    `docs/gramatica-itens.md`): isomorfismo é simétrico, e quem examina o par olha os dois
    sentidos. Um oráculo que olhasse só a origem declararia candidato inexistente o que o banco
    legitimamente encontra, e a propriedade reprovaria sobre código correto.
    """
    por_id = pedido.por_id
    ligados: list[Item] = []
    for relacao in pedido.carga.relacoes:
        if relacao.tipo != EQUIVALENTE:
            continue
        if relacao.item_origem == praticado:
            ligados.append(por_id[relacao.item_destino])
        elif relacao.item_destino == praticado:
            ligados.append(por_id[relacao.item_origem])
    return tuple(ligados)


def elegivel(pedido: PedidoDoDesafio, candidato: Item) -> bool:
    """As três exclusões de elegibilidade do desafio independente (R2.5, R2.3, R2.7).

    Admitir a etapa, não ser item praticado **neste** ciclo e não ter sido apresentado antes em
    etapa sem IA. A qualificação de R2.2 fica fora de propósito: ela depende do item praticado
    de referência, e é o par que a decide.
    """
    return (
        ETAPA_DO_CONJUNTO in candidato.etapas_permitidas
        and candidato.id not in pedido.praticados
        and candidato.id not in pedido.ja_apresentados
    )


def equivalentes_elegiveis(pedido: PedidoDoDesafio, praticado: str) -> frozenset[str]:
    """Candidatos a equivalente do praticado que o banco pode legitimamente escolher."""
    item_praticado = pedido.por_id[praticado]
    return frozenset(
        candidato.id
        for candidato in vizinhos_equivalentes(pedido, praticado)
        if equivalente_qualifica(item_praticado, candidato) and elegivel(pedido, candidato)
    )


def transferencias_elegiveis(pedido: PedidoDoDesafio) -> frozenset[str]:
    """Itens de transferência da habilidade alvo que o banco pode legitimamente escolher (R2.3)."""
    return frozenset(
        candidato.id
        for candidato in pedido.carga.itens
        if e_de_transferencia_da_habilidade(candidato, pedido.habilidade) and elegivel(pedido, candidato)
    )


# --------------------------------------------------------------------------- #
# As lacunas deliberadas de §5.6: mutações do banco completo
#
# Mutação do banco completo, e não um gerador próprio por regime, porque é o que torna o par
# comparável: o mesmo banco, o mesmo pedido, a mesma semente, e **uma** associação retirada. Se
# cada regime tivesse um gerador seu, uma recusa poderia vir de qualquer diferença entre os dois
# bancos, e a lacuna deixaria de ser a causa demonstrada.
# --------------------------------------------------------------------------- #


def sem_equivalente_declarado(pedido: PedidoDoDesafio, alvo: str) -> PedidoDoDesafio:
    """Retira toda relação `equivalente` que toca o alvo, em qualquer direção (R2.6).

    Nas duas direções porque o índice do banco é nos dois sentidos: deixar a relação escrita de
    trás para frente deixaria o candidato de pé, e a mutação não produziria lacuna nenhuma.

    Os demais praticados conservam o equivalente **privado**, que nenhuma mutação toca, de modo
    que o alvo é o único praticado sem candidato — e é por isso que `item_praticado` da recusa é
    previsível, em vez de depender da ordem do pedido.
    """
    restantes = tuple(
        relacao
        for relacao in pedido.carga.relacoes
        if not (relacao.tipo == EQUIVALENTE and alvo in (relacao.item_origem, relacao.item_destino))
    )
    return replace(pedido, carga=carga_ordenada(pedido.carga.itens, restantes))


def com_equivalentes_desqualificados(pedido: PedidoDoDesafio, alvo: str) -> PedidoDoDesafio:
    """Mantém as relações e copia o enunciado do alvo para cada candidato dele (R2.2).

    Enunciado igual é a cláusula de R2.2 que se rompe sem tocar em habilidade, dificuldade nem
    identificador — isto é, sem mexer no que o candidato é para **outro** praticado. Um candidato
    compartilhado continua qualificando para os demais, porque o enunciado dele passa a ser o do
    alvo e segue distinto do deles; o privado de cada um nunca é alcançado por esta mutação.

    É a lacuna que o carregador chama de associação ausente embora a relação esteja escrita
    (`_verificar_associacoes`): relação declarada que não cumpre o critério conta como ausência,
    nunca como pareamento parcial.
    """
    enunciado_do_alvo = pedido.por_id[alvo].enunciado
    desqualificados = {candidato.id for candidato in vizinhos_equivalentes(pedido, alvo)}
    itens = tuple(
        replace(item, enunciado=enunciado_do_alvo) if item.id in desqualificados else item
        for item in pedido.carga.itens
    )
    return replace(pedido, carga=carga_ordenada(itens, pedido.carga.relacoes))


def sem_item_de_transferencia(pedido: PedidoDoDesafio) -> PedidoDoDesafio:
    """Retira do banco todo item de transferência da habilidade alvo (R2.3).

    O critério de retirada é `e_de_transferencia_da_habilidade`, a mesma função que o banco usa
    para montar o universo: a mutação não pode deixar para trás um item que o banco considere de
    transferência e o teste não, porque aí o pedido teria sucesso e a propriedade reprovaria
    sobre código correto. Isso alcança também o concorrente que não admite a etapa do desafio, e
    é deliberado — ele é inelegível, não inexistente, e deixá-lo mudaria a lacuna de "sem
    candidato qualificado" para "fora da etapa".

    Os equivalentes ficam intactos, e as relações que apontavam para os itens retirados saem
    junto: relação pendurada em item ausente é dado que a carga recusa, e o banco a ignora — um
    banco que a trouxesse não seria a entrada que o código vê em produção.
    """
    retirados = {
        candidato.id
        for candidato in pedido.carga.itens
        if e_de_transferencia_da_habilidade(candidato, pedido.habilidade)
    }
    itens = tuple(item for item in pedido.carga.itens if item.id not in retirados)
    relacoes = tuple(
        relacao
        for relacao in pedido.carga.relacoes
        if relacao.item_origem not in retirados and relacao.item_destino not in retirados
    )
    return replace(pedido, carga=carga_ordenada(itens, relacoes))


def com_elegibilidade_esgotada(pedido: PedidoDoDesafio, alvo: str) -> PedidoDoDesafio:
    """Marca como já apresentado **todo** candidato a equivalente do alvo (R2.7).

    Todos, e não os que qualificam: o alvo precisa ficar sem candidato elegível, e um candidato
    que escapasse manteria o pedido de pé. Como o alvo sempre tem ao menos um candidato que
    qualifica e admite a etapa — o equivalente privado —, a contagem de excluídos por
    apresentação é no mínimo um, e `JA_APRESENTADO` é a lacuna de maior precedência presente
    (DO-34). É o que distingue esta lacuna de "sem equivalente declarado": aqui o banco tem o
    item, e o protocolo é que o consumiu.
    """
    consumidos = {candidato.id for candidato in vizinhos_equivalentes(pedido, alvo)}
    return replace(pedido, ja_apresentados=pedido.ja_apresentados | consumidos)


LACUNA_DE_EQUIVALENTE: Final[Mapping[Regime, Callable[[PedidoDoDesafio, str], PedidoDoDesafio]]] = {
    Regime.SEM_EQUIVALENTE_DECLARADO: sem_equivalente_declarado,
    Regime.EQUIVALENTES_DESQUALIFICADOS: com_equivalentes_desqualificados,
    Regime.ELEGIBILIDADE_ESGOTADA: com_elegibilidade_esgotada,
}
"""As lacunas que nomeiam um item praticado. A de transferência não entra: ela é da solicitação
e da habilidade alvo, não de um praticado em particular (DO-33)."""

REGIMES_DE_LACUNA: Final = tuple(regime for regime in Regime if regime is not Regime.COMPLETO)
"""Os quatro regimes com lacuna, derivados da enumeração em vez de listados: regime novo entra
no sorteio sem que ninguém precise lembrar de acrescentá-lo aqui."""


# --------------------------------------------------------------------------- #
# Geração
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CasoDoDesafio:
    """Um pedido de conjunto do desafio e o regime do banco que o atende ou o recusa.

    O regime viaja junto com o pedido porque é ele que diz **qual** metade da disjunção exigir, e
    deduzi-lo do banco no corpo do teste seria reconstruir no oráculo a decisão que o gerador
    acabou de tomar. `alvo` é o item praticado cuja associação foi retirada, e é `None` no banco
    completo e na lacuna de transferência — nos dois casos não existe praticado responsável.
    """

    pedido: PedidoDoDesafio
    regime: Regime
    alvo: str | None


@st.composite
def casos_do_desafio(draw: DrawFn) -> CasoDoDesafio:
    """Banco completo, ou o mesmo banco com uma lacuna deliberada (§5.6).

    O sorteio é em dois passos, e não um entre cinco regimes, porque §5.6 pede **dois** regimes
    de geração: metade dos exemplos em bancos completos, metade repartida entre as lacunas. Um
    sorteio uniforme entre os cinco deixaria a metade positiva — que é a mais rica em afirmações:
    cardinalidade, correspondência, "nenhum outro item" — com um quinto dos exemplos.

    Encolhe para o banco completo, que é o lado em que o contraexemplo traz o conjunto devolvido.
    """
    pedido = draw(pedidos_do_desafio())
    if not draw(st.booleans()):
        return CasoDoDesafio(pedido=pedido, regime=Regime.COMPLETO, alvo=None)
    regime = draw(st.sampled_from(REGIMES_DE_LACUNA))
    if regime is Regime.SEM_TRANSFERENCIA:
        return CasoDoDesafio(pedido=sem_item_de_transferencia(pedido), regime=regime, alvo=None)
    alvo = draw(st.sampled_from(pedido.praticados))
    return CasoDoDesafio(pedido=LACUNA_DE_EQUIVALENTE[regime](pedido, alvo), regime=regime, alvo=alvo)


# --------------------------------------------------------------------------- #
# As duas metades da disjunção
# --------------------------------------------------------------------------- #


def afirmar_conjunto_inteiro(pedido: PedidoDoDesafio, resultado: ResultadoDoConjunto) -> None:
    """O conjunto exato de R2.3, afirmado a partir do pedido e do banco.

    Nenhuma das afirmações abaixo consulta a verificação interna de `ConjuntoDoDesafio`: a
    correspondência vem do pedido, a qualificação vem de `modelo.py`, a origem de cada item vem
    das relações declaradas e o tamanho vem de `TRANSFERENCIAS_NO_CONJUNTO`. É o que faz a
    propriedade falar do algoritmo e não do construtor.
    """
    assert isinstance(resultado, ConjuntoDoDesafio), f"o banco completo devia atender o pedido: {resultado}"
    assert resultado.habilidade == pedido.habilidade, "o conjunto é da habilidade alvo pedida (R2.3)"

    # Exatamente um equivalente **para cada** item praticado: correspondência, não contagem.
    assert resultado.praticados == pedido.praticados, "um par para cada praticado, na ordem do pedido"
    for par in resultado.pares:
        praticado = pedido.por_id[par.praticado]
        vizinhos = {candidato.id for candidato in vizinhos_equivalentes(pedido, par.praticado)}
        assert par.equivalente.id in vizinhos, f"{par.equivalente.id!r} não é equivalente declarado do praticado"
        assert equivalente_qualifica(praticado, par.equivalente), f"{par.equivalente.id!r} não qualifica em R2.2"
        assert ETAPA_DO_CONJUNTO in par.equivalente.etapas_permitidas, f"{par.equivalente.id!r} fora da etapa (R2.5)"
        assert par.equivalente.id not in pedido.praticados, f"{par.equivalente.id!r} foi praticado neste ciclo"
        assert par.equivalente.id not in pedido.ja_apresentados, f"{par.equivalente.id!r} já apresentado (R2.7)"
    escolhidos = tuple(par.equivalente.id for par in resultado.pares)
    assert len(set(escolhidos)) == len(escolhidos), "dois praticados receberam o mesmo equivalente"

    # Ao menos um item de transferência elegível da mesma habilidade alvo.
    assert resultado.transferencia, "o conjunto exige item de transferência (R2.3)"
    de_transferencia = transferencias_elegiveis(pedido)
    for item in resultado.transferencia:
        assert e_de_transferencia_da_habilidade(item, pedido.habilidade), f"{item.id!r} não é de transferência"
        assert item.id in de_transferencia, f"{item.id!r} não é item de transferência elegível da habilidade"

    # ... e nenhum outro item.
    devolvidos = tuple(item.id for item in resultado.itens)
    assert len(set(devolvidos)) == len(devolvidos), "o mesmo item em duas posições do conjunto"
    assert len(devolvidos) == len(pedido.praticados) + TRANSFERENCIAS_NO_CONJUNTO, (
        f"o conjunto tem {len(devolvidos)} itens para {len(pedido.praticados)} praticados: "
        "R2.3 fixa um equivalente por praticado mais a transferência, e nenhum outro item"
    )


def nenhum_item_devolvido(recusa: ErroDeConjuntoIncompleto) -> bool:
    """Se nenhum campo da recusa carrega um `Item`.

    A forma de `ErroDeConjuntoIncompleto` já diz isso: ela declara identificadores, contagens e
    a causa, e nenhum campo de item. Mas "sem retornar conjunto parcial" é metade do enunciado, e
    metade de enunciado confiada à forma de uma `dataclass` é metade de enunciado não verificada —
    o dia em que alguém acrescentar à recusa "os itens que deram certo", para a tela não ficar
    vazia, esta função fica vermelha, e é o único lugar do repositório que ficaria.

    A varredura é por campo, e não uma lista de nomes, para que campo novo entre na verificação
    sem precisar ser acrescentado aqui.
    """
    return not any(_carrega_item(getattr(recusa, campo.name)) for campo in fields(recusa))


def _carrega_item(valor: object) -> bool:
    """Se o valor é um `Item` ou uma coleção que contém um."""
    if isinstance(valor, Item):
        return True
    if isinstance(valor, tuple | frozenset | list | set):
        return any(_carrega_item(membro) for membro in valor)
    return False


def afirmar_recusa_sem_itens(caso: CasoDoDesafio, resultado: ResultadoDoConjunto) -> None:
    """A recusa de R2.10: nenhum item, e a identificação que ela tem de trazer.

    O que o erro **identifica** é afirmado porque é o que R2.10 pede, e porque é a parte da
    recusa que se perde sem ninguém notar: uma recusa que dissesse apenas "conjunto
    indisponível" satisfaria o tipo e não diria onde está o conserto.
    """
    assert not isinstance(resultado, ConjuntoDoDesafio), f"o banco com lacuna devia recusar: {caso.regime.value}"
    assert isinstance(resultado, ErroDeConjuntoIncompleto), f"recusa inesperada: {resultado}"
    assert nenhum_item_devolvido(resultado), "a recusa devolveu item: é o conjunto parcial que R2.10 fecha"
    assert resultado.codigo == CODIGO_CONJUNTO_INDISPONIVEL

    esperada = RECUSA_ESPERADA[caso.regime]
    assert resultado.associacao == esperada.associacao, f"a associação indisponível em {caso.regime.value}"
    assert resultado.lacuna is esperada.lacuna, f"a causa relatada em {caso.regime.value} (DO-34)"
    assert resultado.praticados == caso.pedido.praticados, "a recusa identifica os praticados da solicitação"
    assert resultado.habilidade == caso.pedido.habilidade, "a recusa identifica a habilidade alvo"

    if esperada.associacao == EQUIVALENTE:
        assert caso.alvo is not None, "a lacuna de equivalente tem praticado alvo"
        assert resultado.item_praticado == caso.alvo, "a recusa identifica o item praticado (R2.10)"
        assert caso.alvo in resultado.mensagem, "a mensagem nomeia o item praticado"
    else:
        assert resultado.item_praticado is None, "não há praticado responsável pela transferência (DO-33)"
        assert caso.pedido.habilidade in resultado.mensagem, "a mensagem nomeia a habilidade alvo"


# --------------------------------------------------------------------------- #
# A propriedade
# --------------------------------------------------------------------------- #


@given(casos_do_desafio())
def test_o_conjunto_do_desafio_vem_inteiro_ou_nao_vem(caso: CasoDoDesafio) -> None:
    # Feature: adia-cognitiveloop-prototype, Property 33: conjunto do desafio é tudo ou nada
    """Ou o conjunto exato de R2.3, ou a recusa de R2.10 sem nenhum item (R2.3, R2.10).

    A disjunção é afirmada nas duas pontas, e o regime do banco é o que decide qual delas exigir
    — o que é mais forte do que afirmar a disjunção solta: um banco completo que recusasse o
    pedido satisfaz "ou uma, ou outra" e seria um defeito grave, porque abortaria um ciclo que o
    banco tinha itens para atender.

    O conjunto parcial é a falha que a propriedade existe para impedir, e ela aparece nos dois
    lados: no lado do sucesso, como conjunto de tamanho diferente de `praticados + 1` ou com
    equivalente repetido; no lado da recusa, como item devolvido junto com o erro.

    Sem `@settings`: o orçamento de 100 exemplos vem do perfil `propriedades` de
    `backend/tests/conftest.py`, e esta propriedade não pede desvio nenhum. O prazo por exemplo
    fica como está porque não há E/S no corpo — nenhum arquivo é lido ou escrito, o banco é
    montado em memória a partir de `CargaConcluida` — e o que o corpo faz é indexar poucos itens,
    fazer uma chamada e comparar valores.

    A folga está medida, e não suposta. Nesta máquina, com as estatísticas da própria biblioteca:
    18 a 81 ms por exemplo, dos quais 16 a 72 ms em **geração** — isto é, 2 a 9 ms de corpo,
    contra o prazo padrão de 200 ms. A distinção é o que dispensa o `deadline=None` que P29 e P30
    precisam declarar: o prazo da biblioteca mede o corpo, não a geração, e aqui o custo está
    todo na geração, onde sai um item completo por posição do banco pareado.
    """
    pedido = caso.pedido
    banco = BancoDeItens(pedido.carga, pedido.semente)

    resultado = banco.conjunto_do_desafio(pedido.praticados, pedido.habilidade, pedido.ja_apresentados)

    if caso.regime is Regime.COMPLETO:
        afirmar_conjunto_inteiro(pedido, resultado)
    else:
        afirmar_recusa_sem_itens(caso, resultado)


# --------------------------------------------------------------------------- #
# Afirmações de apoio: a ênfase de §5.6 tem exemplo
# --------------------------------------------------------------------------- #

BUSCA_DE_ENFASE: Final = settings(
    max_examples=200, phases=(Phase.generate,), deadline=None, derandomize=True
)
"""Orçamento das buscas de apoio. Sem a fase de encolhimento: o que se afirma é que a forma é
**alcançável**, e o exemplo mínimo não acrescenta nada a isso — só custa tempo no portão.
`derandomize`: com sorteio livre, um regime raro às vezes não aparecia em 200 exemplos e a
busca reprovava com `NoSuchExample` sem defeito nenhum. Com a sequência fixa, o resultado é o
mesmo em toda execução: um regime que some reprova sempre, e não uma vez em dez."""


def reconhecedor_de(regime: Regime) -> Callable[[CasoDoDesafio], bool]:
    """Reconhecedor do regime, para que a busca falhe dizendo qual regime deixou de ser gerado."""

    def no_regime(caso: CasoDoDesafio) -> bool:
        return caso.regime is regime

    return no_regime


@pytest.mark.parametrize("regime", list(Regime))
def test_a_geracao_alcanca_cada_regime_declarado(regime: Regime) -> None:
    """Os cinco regimes de §5.6 são alcançáveis, em vez de apenas pretendidos.

    Sem `@given`, porque não é a propriedade: é a guarda da **ênfase** dela. O modo de falha que
    ela pega é silencioso, e é o que a torna necessária. Um regime de lacuna que deixasse de ser
    gerado — mutação que não muta, sorteio que perde um membro, banco em que o alvo já não tem
    candidato a retirar — não quebra nada: P33 segue verde, afirmando menos, e o que se perde é a
    chance de encontrar o defeito. `find` reprova com `NoSuchExample`, que é o contrário de
    silencioso.
    """
    no_regime = reconhecedor_de(regime)

    assert no_regime(find(casos_do_desafio(), no_regime, settings=BUSCA_DE_ENFASE)), regime.value


def alcanca_mais_de_um_praticado(caso: CasoDoDesafio) -> bool:
    """Se o ciclo gerado tem mais de um item praticado, no banco completo."""
    return caso.regime is Regime.COMPLETO and len(caso.pedido.praticados) > 1


def alcanca_candidato_excedente(caso: CasoDoDesafio) -> bool:
    """Se o banco completo tem candidato elegível a mais do que o conjunto leva."""
    if caso.regime is not Regime.COMPLETO:
        return False
    pedido = caso.pedido
    sobra_equivalente = any(
        len(equivalentes_elegiveis(pedido, praticado)) > 1 for praticado in pedido.praticados
    )
    return sobra_equivalente or len(transferencias_elegiveis(pedido)) > TRANSFERENCIAS_NO_CONJUNTO


ENFASES_DO_BANCO_COMPLETO: Final = (
    ("mais de um item praticado", alcanca_mais_de_um_praticado),
    ("candidato elegível excedente", alcanca_candidato_excedente),
)
"""O que a metade positiva do enunciado precisa ver para não ser vazia, com o reconhecedor de
cada forma."""


@pytest.mark.parametrize(("enfase", "alcanca"), ENFASES_DO_BANCO_COMPLETO)
def test_a_geracao_alcanca_cada_enfase_do_banco_completo(
    enfase: str, alcanca: Callable[[CasoDoDesafio], bool]
) -> None:
    """As duas formas sem as quais a metade positiva afirmaria menos do que o enunciado diz.

    Com um praticado só, "exatamente um equivalente **para cada** praticado" é indistinguível de
    "um equivalente", e "dois praticados nunca recebem o mesmo" não tem como falhar. Sem candidato
    excedente, "e nenhum outro item" não tem o que recusar: levar todos os elegíveis e levar o
    exato seriam o mesmo conjunto. As duas formas são geração, não propriedade, e por isso estão
    aqui e não num segundo `@given`.
    """
    assert alcanca(find(casos_do_desafio(), alcanca, settings=BUSCA_DE_ENFASE)), enfase
