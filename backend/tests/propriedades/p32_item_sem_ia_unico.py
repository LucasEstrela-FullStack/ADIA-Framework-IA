"""Propriedade 32: item apresentado numa etapa sem IA não reaparece em outra.

`p29_item_ida_e_volta.py` fixou a forma dos arquivos de propriedade — um arquivo, uma
propriedade, um teste; etiqueta na primeira linha do corpo; orçamento de exemplos vindo do perfil
de `backend/tests/conftest.py`; geradores nomeados em `estrategias.py`; afirmação de apoio como
teste separado e **sem** `@given`. Este arquivo segue aquela forma sem a repetir.

O enunciado de §5.6 é sobre o **participante**, não sobre um pedido: para todo participante, um
item apresentado em uma etapa sem IA nunca é apresentado a esse mesmo participante em outra etapa
sem IA — entre linha de base, desafio independente de qualquer ciclo, pós-teste e teste de
retenção. O oráculo é a interseção vazia entre os conjuntos apresentados nessas etapas.

O que a regra protege é a medida. Um item do desafio independente do ciclo 1 que reaparecesse no
pós-teste mediria memória do item, não domínio da habilidade, e a razão de retenção de R11.6 —
`TAI(retenção) ÷ TAI(pós-teste)` — compararia um conjunto com um subconjunto de si mesmo. Nada na
tela pareceria errado: as duas TAI sairiam com denominador cheio.

## A sessão é simulada, e por quê

A máquina de estados que conduz a sessão é o `Gestor_de_Sessão` de §3.3, e ele é a tarefa 6.1 —
`backend/adia/nucleo/sessao/gestor.py` ainda não existe. "Sessão completa" aqui é, portanto, a
sequência de pedidos ao `Banco_de_Itens` na ordem de R12.1, com `ja_apresentados` **acumulado**
entre as etapas: linha de base, três repetições de prática assistida e desafio independente,
projeto STEAM, teste de retenção. É exatamente como o gestor chamará o banco, e é a mesma
simulação que `backend/tests/conjuntos/test_banco_inicial_de_itens.py` faz sobre o banco real de
`data/itens/` — lá para verificar **conteúdo**, aqui sobre banco **gerado**, para verificar
código.

A prática assistida e o projeto STEAM não aparecem na simulação porque não consomem item de etapa
sem IA: a primeira reapresenta o item praticado, que é o oposto do que R2.7 regula, e o segundo
roda sobre `data/steam/`. Quando a tarefa 6.1 chegar, o gestor é que passa a fazer esta sequência,
e a Propriedade 34 compara a máquina dele com o modelo de referência de §3.3; o que P32 fixa é o
contrato do banco que a máquina vai usar.

## O pós-teste é rótulo, e isso decide a forma do teste

`Etapa.POSTESTE` existe em `adia.tipos` e **não** é etapa com itens próprios: R12.3 manda rotular
como pós-teste o conjunto sem IA do terceiro ciclo, e o evento registra `DESAFIO_INDEPENDENTE` com
`ciclo = 3`. Nenhum item de `data/itens/` declara `posteste`, deliberadamente.

Logo o pós-teste **não** é uma quinta chamada ao banco: ele é o desafio independente do ciclo 3
sob outro nome. A simulação faz cinco pedidos — linha de base, três desafios, retenção — e o
pós-teste é um dos três do meio. Isso está afirmado, não apenas comentado: os conjuntos
apresentados são indexados por `ConjuntoDeRespostas`, a forma canônica de `adia.tipos`, e
`conjunto_de_respostas(EscopoDeCalculo.POSTESTE)` resolve na **mesma** chave que
`conjunto_de_respostas(EscopoDeCalculo.DESAFIO_INDEPENDENTE, 3)`. Uma propriedade que pedisse ao
banco um conjunto de pós-teste à parte afirmaria algo que o protocolo não faz, e — pior — passaria
verde, porque dois conjuntos distintos de um banco grande o bastante são disjuntos por acidente.

## O teste de retenção é o caso delicado, e o mínimo viável é onde ele morde

§5.6 nomeia o caso: a retenção "reusa a estrutura do pós-teste sem poder reusar os itens". Ela
pede a mesma quantidade de itens que o pós-teste apresentou (R12.4) **depois** de a linha de base
e os três ciclos terem consumido os seus. É a última etapa, é onde a elegibilidade está mais
apertada, e é onde um banco pequeno falha.

A aritmética do mínimo viável está declarada em `estrategias.sessoes_completas` e resumida aqui:
com `c` ciclos, `p` praticados por ciclo, `b` itens na linha de base e `d = p + 1` itens no
conjunto do desafio, o consumo sem IA é `b + c·d + d`, e R2.7 proíbe reaproveitar qualquer um
deles. O banco mínimo tem `b + c·p + d` itens não-transferência e `c` itens de transferência — a
soma é exatamente o consumo, de modo que **todo** item sem IA é apresentado uma vez e nenhum
sobra. No mínimo viável a retenção recebe exatamente o que pediu, nem um item a mais, e a
propriedade afirma esse zero de folga em vez de esperá-lo.

Um banco com folga enorme passaria em P32 sem nunca exercitar R2.7: a etapa seguinte encontraria
candidato de qualquer forma. É por isso que o regime do mínimo viável é um quarto dos exemplos e
não um acidente do sorteio, e por isso que `test_a_geracao_alcanca_cada_regime_declarado` existe.

## O que a propriedade afirma quando uma etapa é legitimamente recusada

Abaixo do mínimo viável, uma etapa não tem itens elegíveis em número suficiente. A recusa é
**legítima** — é R2.7 funcionando num banco pequeno, não defeito —, e o enunciado de §5.6 continua
verdadeiro sob a leitura que este arquivo adota: a interseção vazia é afirmada sobre o que de fato
foi **apresentado**, e uma etapa recusada não apresenta nada.

"Nada" é a parte que precisa ser afirmada, e não deduzida. As duas metades:

- no desafio independente, a recusa é do próprio banco, e `conjunto_do_desafio` é tudo ou nada por
  contrato (R2.10, Propriedade 33): `ErroDeConjuntoIncompleto` e nenhum item;
- na linha de base e na retenção, o banco publica o universo elegível e quem escolhe é quem chama.
  A decisão da simulação — e, quando a tarefa 6.1 chegar, do gestor — é **não** apresentar um
  conjunto parcial: R12.4 pede para a retenção a estrutura do pós-teste, e meia retenção não é uma
  retenção, é um denominador menor que o do numerador que vai ser comparado com ele.

Qual etapa é recusada em cada regime está declarado em `RECUSA_ESPERADA`, e é afirmado como
igualdade — nem uma etapa a mais, nem a menos. Afirmar apenas "alguma etapa foi recusada" deixaria
passar o banco que recusa tudo.

## Nada aqui toca disco

O banco é montado em memória a partir de `CargaConcluida`, exatamente como `BancoDeItens` o recebe
depois de uma carga de verdade. O corpo do teste indexa poucos itens, faz cinco chamadas e compara
conjuntos. É o que dispensa o `deadline=None` que P29 e P30 precisam declarar, e a folga está
medida em vez de suposta — ver a docstring do teste.

**Validates: Requirements 2.7, 12.4, 26.3**
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum, unique
from itertools import combinations
from typing import Final

import pytest
from estrategias import CICLOS_DO_PROTOCOLO, SessaoCompleta, carga_ordenada, sessoes_completas
from hypothesis import Phase, find, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import DrawFn

from adia.nucleo.itens.banco import BancoDeItens, ConjuntoDoDesafio
from adia.nucleo.itens.modelo import TRANSFERENCIA, Item, Relacao
from adia.tipos import (
    CICLO_DO_POSTESTE,
    ETAPAS_SEM_IA,
    ConjuntoDeRespostas,
    EscopoDeCalculo,
    Etapa,
    conjunto_de_respostas,
)

PEDIDOS_AO_BANCO: Final = 2 + CICLOS_DO_PROTOCOLO
"""Quantas vezes uma sessão pede itens sem IA ao banco: linha de base, os três desafios, retenção.

Cinco, e não seis: o pós-teste é rótulo do desafio do terceiro ciclo (R12.3), não um sexto pedido.
É a constante que `afirmar_que_o_posteste_e_rotulo` usa para fechar essa porta.
"""


# --------------------------------------------------------------------------- #
# Regimes de geração: a ênfase de §5.6 em banco de tamanho variável
# --------------------------------------------------------------------------- #


@unique
class Regime(StrEnum):
    """Aperto do banco gerado, que decide qual desfecho exigir da sessão (§5.6).

    `MINIMO_VIAVEL` é o primeiro membro porque é para ele que o encolhimento caminha, e porque é
    a ênfase do enunciado: é o banco em que nenhuma etapa tem escolha, logo o único em que um
    defeito de acúmulo de `ja_apresentados` tem como aparecer.

    Os dois regimes abaixo do mínimo são o mesmo banco mínimo com **um** item a menos, cada um em
    um reservatório, e o nome diz qual etapa a falta alcança. Que seja o terceiro ciclo — e não o
    primeiro — na falta de transferência não é escolha: os ciclos consomem um item de
    transferência cada, e com um a menos é o último que fica sem.
    """

    MINIMO_VIAVEL = "minimo_viavel"
    COM_FOLGA = "com_folga"
    SEM_ITEM_PARA_A_RETENCAO = "sem_item_para_a_retencao"
    SEM_TRANSFERENCIA_NO_TERCEIRO_CICLO = "sem_transferencia_no_terceiro_ciclo"


RECUSA_ESPERADA: Final[Mapping[Regime, ConjuntoDeRespostas | None]] = {
    Regime.MINIMO_VIAVEL: None,
    Regime.COM_FOLGA: None,
    Regime.SEM_ITEM_PARA_A_RETENCAO: conjunto_de_respostas(EscopoDeCalculo.TESTE_RETENCAO),
    Regime.SEM_TRANSFERENCIA_NO_TERCEIRO_CICLO: conjunto_de_respostas(EscopoDeCalculo.POSTESTE),
}
"""A etapa que cada regime recusa, ou `None` quando a sessão atravessa inteira.

Fica ao lado do `Regime` para que um regime acrescentado sem desfecho declarado apareça na
revisão — e, antes dela, como `KeyError` no primeiro exemplo.

O segundo regime recusa o **pós-teste**, e o valor escrito aqui é literalmente
`conjunto_de_respostas(EscopoDeCalculo.POSTESTE)`: a forma canônica de `adia.tipos` resolve o
rótulo no desafio independente do ciclo 3, que é a etapa que de fato fica sem item de
transferência. Escrever `DESAFIO_INDEPENDENTE` com `ciclo = 3` aqui daria o mesmo valor e diria
menos.
"""


# --------------------------------------------------------------------------- #
# As mutações para baixo do mínimo viável
#
# Mutação do banco mínimo, e não um gerador por regime, pela razão de P33: é o que torna o par
# comparável. O mesmo banco, o mesmo roteiro, a mesma semente, e **um** item retirado. Se cada
# regime tivesse gerador próprio, a recusa poderia vir de qualquer diferença entre os dois bancos,
# e a falta deixaria de ser a causa demonstrada.
# --------------------------------------------------------------------------- #


def sem_item_para_a_retencao(sessao: SessaoCompleta) -> SessaoCompleta:
    """Retira um item do pool sem IA, e com ele o único que sobraria para a retenção (R2.7, R12.4).

    A retenção é a etapa alcançada, e isso é aritmética e não sorte: a linha de base toma `b`, os
    três ciclos tomam `c · p` equivalentes, e o que resta para a retenção no banco mínimo é
    exatamente `d`. Com um item a menos restam `d − 1`, e `d − 1 < d`. Os ciclos seguem atendidos,
    porque antes do último deles o pool ainda tem `2p` itens para os `p` que ele pede.

    O item retirado é o **último** do pool. Qualquer um serviria — os itens do pool são
    intercambiáveis por construção, todos qualificam como equivalente de todo praticado e todos
    admitem as três etapas sem IA executáveis —, e o último é o que se lê no contraexemplo sem
    exigir contar.
    """
    return _sem_o_item(sessao, sessao.pool_sem_ia[-1])


def sem_transferencia_no_terceiro_ciclo(sessao: SessaoCompleta) -> SessaoCompleta:
    """Retira um item de transferência, e com ele o do terceiro ciclo — o pós-teste (R2.3, R12.3).

    Com `c − 1` itens de transferência, os dois primeiros ciclos consomem os dois que existem e o
    terceiro não tem nenhum elegível: `conjunto_do_desafio` recusa o pedido inteiro, sem conjunto
    parcial (R2.10). É a recusa do **pós-teste**, que é o caso mais informativo dos dois: a sessão
    perde o denominador da razão de retenção de R11.6 e ainda assim segue para a retenção, que
    encontra itens — o pool não foi tocado, e o ciclo recusado não consumiu nada dele.

    As relações `transferencia` que apontavam para o item retirado são **reapontadas** para o
    primeiro item de transferência, em vez de removidas. Sem isso os itens praticados do terceiro
    ciclo ficariam sem transferência associada, e R2.6 recusaria a carga: o banco deixaria de ser
    um banco que a carga aceita, que é a entrada que o código vê em produção. O reapontamento não
    cria relação duplicada, porque cada praticado tem uma única relação `transferencia` e só os do
    terceiro ciclo apontavam para o item retirado.
    """
    alvo = sessao.de_transferencia[-1]
    remanescente = sessao.de_transferencia[0]
    relacoes = tuple(
        Relacao(relacao.item_origem, remanescente, TRANSFERENCIA)
        if relacao.item_destino == alvo
        else relacao
        for relacao in sessao.carga.relacoes
        if relacao.item_origem != alvo
    )
    return _sem_o_item(sessao, alvo, relacoes)


def _sem_o_item(
    sessao: SessaoCompleta, alvo: str, relacoes: tuple[Relacao, ...] | None = None
) -> SessaoCompleta:
    """O mesmo banco sem o item alvo, com as relações que o tocavam resolvidas.

    `relacoes` já reescritas, quando quem chama precisa preservar uma associação (ver
    `sem_transferencia_no_terceiro_ciclo`); `None` descarta toda relação que toca o alvo, que é o
    que a falta no pool pede — relação pendurada em item ausente é dado que a carga recusa.

    A folga da sessão resultante é negativa, e nada precisa ser dito a respeito: `SessaoCompleta`
    deriva a folga do tamanho dos reservatórios, de modo que retirar um item **é** descer abaixo
    do mínimo.
    """
    sobreviventes = (
        relacoes
        if relacoes is not None
        else tuple(
            relacao
            for relacao in sessao.carga.relacoes
            if alvo not in (relacao.item_origem, relacao.item_destino)
        )
    )
    return replace(
        sessao,
        carga=carga_ordenada(
            tuple(item for item in sessao.carga.itens if item.id != alvo), sobreviventes
        ),
        pool_sem_ia=tuple(item for item in sessao.pool_sem_ia if item != alvo),
        de_transferencia=tuple(item for item in sessao.de_transferencia if item != alvo),
    )


MUTACAO: Final[Mapping[Regime, Callable[[SessaoCompleta], SessaoCompleta]]] = {
    Regime.SEM_ITEM_PARA_A_RETENCAO: sem_item_para_a_retencao,
    Regime.SEM_TRANSFERENCIA_NO_TERCEIRO_CICLO: sem_transferencia_no_terceiro_ciclo,
}
"""Os regimes abaixo do mínimo e a mutação de cada um. Os dois viáveis não aparecem: o banco deles
é o que o gerador produz, sem mutação nenhuma."""


# --------------------------------------------------------------------------- #
# Geração
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CasoDaSessao:
    """Uma sessão gerada e o regime de aperto do banco dela.

    O regime viaja junto porque é ele que diz qual desfecho exigir, e deduzi-lo do banco no corpo
    do teste seria reconstruir no oráculo a decisão que o gerador acabou de tomar. A coerência
    entre os dois é verificada no construtor, que é o que impede o regime de mentir sobre o banco.
    """

    sessao: SessaoCompleta
    regime: Regime

    def __post_init__(self) -> None:
        """Recusa o par em que o regime declarado não descreve o aperto do banco."""
        esperado_abaixo = self.regime in MUTACAO
        if self.sessao.esta_abaixo_do_minimo != esperado_abaixo:
            raise ValueError(
                f"o regime {self.regime.value!r} e o banco discordam: folga do pool "
                f"{self.sessao.folga_do_pool_sem_ia}, folga de transferência "
                f"{self.sessao.folga_de_transferencia}."
            )
        if self.regime is Regime.MINIMO_VIAVEL and not self.sessao.e_minimo_viavel:
            raise ValueError("o regime do mínimo viável exige folga zero nos dois reservatórios.")


@st.composite
def casos_da_sessao(draw: DrawFn) -> CasoDaSessao:
    """Sessão completa em um dos quatro regimes de aperto, sorteados em partes iguais.

    O regime é sorteado **primeiro**, e é o que decide os limites de folga do gerador. A
    alternativa — sortear a folga e deduzir o regime — faria o mínimo viável aparecer em um exemplo
    a cada nove, porque ele exige folga zero nos **dois** reservatórios, e a ênfase de §5.6
    ficaria com 11% dos exemplos em vez de 25%.

    `COM_FOLGA` pede folga em ambos os reservatórios, e não em um só. A forma com sobra em um e
    aperto no outro é justamente o que os dois regimes abaixo do mínimo exercitam, um item mais
    adiante: lá a falta chega a zero e a etapa é recusada, que é a fronteira que interessa.
    """
    regime = draw(st.sampled_from(Regime))
    if regime is Regime.COM_FOLGA:
        return CasoDaSessao(sessao=draw(sessoes_completas(folga_minima=1)), regime=regime)
    sessao = draw(sessoes_completas(folga_maxima=0))
    if regime is Regime.MINIMO_VIAVEL:
        return CasoDaSessao(sessao=sessao, regime=regime)
    return CasoDaSessao(sessao=MUTACAO[regime](sessao), regime=regime)


# --------------------------------------------------------------------------- #
# A sessão simulada: a ordem de R12.1 com `ja_apresentados` acumulado
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EtapaExecutada:
    """O que uma etapa sem IA apresentou ao participante, ou a recusa que a impediu.

    `conjunto` é a forma canônica de `adia.tipos`, e não o par solto de etapa e ciclo, porque é
    ela que resolve o rótulo de pós-teste num único lugar (R12.3).

    `disponiveis` é o tamanho do universo elegível que o banco ofereceu, e é `None` no desafio
    independente: `conjunto_do_desafio` é tudo ou nada e não publica universo — ele devolve o
    conjunto ou a recusa. A distinção não é detalhe de registro, é o que permite afirmar o zero de
    folga da retenção sem inventar um número para os ciclos.
    """

    conjunto: ConjuntoDeRespostas
    pedidos: int
    apresentados: tuple[str, ...]
    disponiveis: int | None
    recusa: str | None

    @property
    def recusada(self) -> bool:
        """Se a etapa não apresentou nada por falta de item elegível."""
        return self.recusa is not None

    @property
    def nome(self) -> str:
        """Identificação curta da etapa, para a mensagem de falha."""
        if self.conjunto.ciclo is None:
            return self.conjunto.etapa.value
        return f"{self.conjunto.etapa.value}#{self.conjunto.ciclo}"


def executar_sessao(banco: BancoDeItens, sessao: SessaoCompleta) -> tuple[EtapaExecutada, ...]:
    """Pede ao banco os itens de cada etapa sem IA, na ordem de R12.1, acumulando o consumo.

    O acúmulo é o ponto inteiro desta função: cada etapa é pedida ao banco **depois** de tudo o
    que já foi apresentado, que é como o `Gestor_de_Sessão` pedirá. Um `ja_apresentados` que não
    acumulasse deixaria a propriedade verde sem verificar R2.7 — a exclusão existiria no banco e
    nunca receberia o histórico que a aciona.

    Devolve as cinco etapas na ordem do protocolo, inclusive as recusadas, porque "nada foi
    apresentado" é afirmação que a propriedade faz e não pode fazer sobre uma etapa ausente da
    lista.
    """
    executadas: list[EtapaExecutada] = []
    ja_apresentados: set[str] = set()

    def registrar(etapa: EtapaExecutada) -> None:
        executadas.append(etapa)
        ja_apresentados.update(etapa.apresentados)

    registrar(
        _tomar_da_etapa(
            banco,
            sessao,
            Etapa.LINHA_DE_BASE,
            conjunto_de_respostas(EscopoDeCalculo.LINHA_DE_BASE),
            sessao.na_linha_de_base,
            frozenset(ja_apresentados),
        )
    )
    for numero in range(1, CICLOS_DO_PROTOCOLO + 1):
        registrar(_desafio_do_ciclo(banco, sessao, numero, frozenset(ja_apresentados)))
    registrar(
        _tomar_da_etapa(
            banco,
            sessao,
            Etapa.TESTE_RETENCAO,
            conjunto_de_respostas(EscopoDeCalculo.TESTE_RETENCAO),
            sessao.na_retencao,
            frozenset(ja_apresentados),
        )
    )
    return tuple(executadas)


def _tomar_da_etapa(
    banco: BancoDeItens,
    sessao: SessaoCompleta,
    etapa: Etapa,
    conjunto: ConjuntoDeRespostas,
    quantos: int,
    ja_apresentados: frozenset[str],
) -> EtapaExecutada:
    """Os itens que uma etapa servida por `elegiveis_sem_ia` apresenta, ou a recusa.

    Com menos itens elegíveis do que a etapa pede, **nada** é apresentado. É decisão de quem
    chama, não do banco, e a razão está no cabeçalho do módulo: R12.4 pede para a retenção a
    estrutura do pós-teste, e um conjunto parcial produziria uma TAI com denominador menor que o
    do numerador com que ela vai ser comparada.
    """
    elegiveis = banco.elegiveis_sem_ia(etapa, ja_apresentados)
    if len(elegiveis) < quantos:
        return EtapaExecutada(
            conjunto=conjunto,
            pedidos=quantos,
            apresentados=(),
            disponiveis=len(elegiveis),
            recusa=(
                f"a etapa {etapa.value!r} pede {quantos} itens e tem {len(elegiveis)} elegíveis; "
                f"com {len(ja_apresentados)} item(ns) já apresentado(s), R2.7 esgotou o conjunto"
            ),
        )
    return EtapaExecutada(
        conjunto=conjunto,
        pedidos=quantos,
        apresentados=_escolher(elegiveis, quantos, sessao.semente, etapa),
        disponiveis=len(elegiveis),
        recusa=None,
    )


def _escolher(
    elegiveis: Sequence[Item], quantos: int, semente: int, etapa: Etapa
) -> tuple[str, ...]:
    """Quais dos itens elegíveis a etapa apresenta, decidido pela semente injetada (R26.3).

    `elegiveis_sem_ia` devolve o universo em ordem canônica e **não** aplica a semente, porque
    quem escolhe é quem chama — é o que a própria operação documenta. A escolha aqui é derivada da
    semente sorteada, e não o prefixo da ordem canônica, por uma razão de força da propriedade: a
    interseção vazia tem de valer para qualquer ordem de preferência, não para uma. Com o prefixo,
    a linha de base e a retenção seriam verificadas sob uma única escolha, e um defeito que
    dependesse de **qual** item foi tomado nunca apareceria.

    A semente entra composta com a etapa para que linha de base e retenção não repitam a mesma
    preferência; derivada da semente da sessão, de modo que o contraexemplo reproduz a escolha.
    """
    sorteio = random.Random(f"{semente}:{etapa.value}")
    return tuple(sorteio.sample([item.id for item in elegiveis], quantos))


def _desafio_do_ciclo(
    banco: BancoDeItens, sessao: SessaoCompleta, numero: int, ja_apresentados: frozenset[str]
) -> EtapaExecutada:
    """O conjunto do desafio independente de um ciclo, ou a recusa de R2.10 sem nenhum item.

    O ciclo rotulado como pós-teste não recebe tratamento especial, e é isso que R12.3 pede: o
    rótulo se resolve em `conjunto_de_respostas`, não num pedido diferente ao banco.
    """
    conjunto = conjunto_de_respostas(EscopoDeCalculo.DESAFIO_INDEPENDENTE, numero)
    resultado = banco.conjunto_do_desafio(
        sessao.ciclos[numero - 1], sessao.habilidade, ja_apresentados
    )
    if not isinstance(resultado, ConjuntoDoDesafio):
        return EtapaExecutada(
            conjunto=conjunto,
            pedidos=sessao.no_desafio,
            apresentados=(),
            disponiveis=None,
            recusa=resultado.mensagem,
        )
    return EtapaExecutada(
        conjunto=conjunto,
        pedidos=sessao.no_desafio,
        apresentados=tuple(item.id for item in resultado.itens),
        disponiveis=None,
        recusa=None,
    )


# --------------------------------------------------------------------------- #
# O oráculo
# --------------------------------------------------------------------------- #


def afirmar_que_o_posteste_e_rotulo(executadas: Sequence[EtapaExecutada]) -> None:
    """A sessão fez cinco pedidos ao banco, e o pós-teste é um deles — o do ciclo 3 (R12.3).

    Três afirmações, e cada uma fecha uma forma de errar o rótulo: a contagem de pedidos impede
    que o pós-teste tenha itens próprios; a identidade entre as duas chaves impede que ele seja
    um conjunto paralelo com os mesmos itens; e a cobertura contra `ETAPAS_SEM_IA` impede que uma
    etapa sem IA fique fora da simulação — se a enumeração ganhar um membro, esta linha fica
    vermelha, e é a única do repositório que ficaria.
    """
    assert len(executadas) == PEDIDOS_AO_BANCO, (
        f"a sessão pediu itens {len(executadas)} vezes; o protocolo pede {PEDIDOS_AO_BANCO}: linha "
        "de base, os três desafios independentes e a retenção. O pós-teste é rótulo (R12.3)"
    )
    por_conjunto = {etapa.conjunto: etapa for etapa in executadas}
    assert len(por_conjunto) == len(executadas), "dois pedidos com o mesmo conjunto de respostas"

    posteste = conjunto_de_respostas(EscopoDeCalculo.POSTESTE)
    terceiro = conjunto_de_respostas(EscopoDeCalculo.DESAFIO_INDEPENDENTE, CICLO_DO_POSTESTE)
    assert posteste == terceiro, "o pós-teste é o conjunto sem IA do terceiro ciclo (R12.3)"
    assert por_conjunto[posteste] is por_conjunto[terceiro], (
        "o pós-teste e o desafio do terceiro ciclo são o mesmo conjunto apresentado, não dois"
    )

    etapas = {etapa.conjunto.etapa for etapa in executadas} | {Etapa.POSTESTE}
    assert etapas == ETAPAS_SEM_IA, (
        f"a simulação cobre {sorted(etapa.value for etapa in etapas)} e as etapas sem IA são "
        f"{sorted(etapa.value for etapa in ETAPAS_SEM_IA)} (R2.7)"
    )


def afirmar_etapa_inteira_ou_nenhuma(executadas: Sequence[EtapaExecutada]) -> None:
    """Cada etapa apresentou exatamente o que pediu, ou nada: conjunto parcial não é opção.

    É a metade do enunciado que a interseção vazia não alcança. Uma etapa que apresentasse metade
    dos itens teria interseção vazia com todas as outras e satisfaria o oráculo de §5.6 — e teria
    produzido uma TAI sobre um denominador que não é o do protocolo.
    """
    for etapa in executadas:
        assert len(set(etapa.apresentados)) == len(etapa.apresentados), (
            f"item repetido dentro de {etapa.nome}: {sorted(etapa.apresentados)}"
        )
        if etapa.recusada:
            assert etapa.apresentados == (), (
                f"{etapa.nome} foi recusada e apresentou {sorted(etapa.apresentados)}: "
                f"conjunto parcial não é conjunto ({etapa.recusa})"
            )
        else:
            assert len(etapa.apresentados) == etapa.pedidos, (
                f"{etapa.nome} pediu {etapa.pedidos} itens e apresentou "
                f"{len(etapa.apresentados)}: {sorted(etapa.apresentados)}"
            )


def afirmar_intersecao_vazia(executadas: Sequence[EtapaExecutada]) -> None:
    """O oráculo de §5.6: interseção vazia entre os conjuntos apresentados nas etapas sem IA.

    Par a par, e não apenas pela contagem da união, porque a mensagem é o que se lê primeiro: a
    contagem diria que há um item repetido, e o par diz **qual** item e entre **quais** etapas —
    que é a diferença entre "R2.7 falhou" e "o consumo do ciclo 2 não chegou à retenção".

    A contagem da união vem depois, como fecho: ela é consequência das duas afirmações anteriores,
    e existe para que a falha de um caso não visto pelos pares — se alguma vier a existir —
    apareça como número em vez de passar.
    """
    apresentando = [etapa for etapa in executadas if not etapa.recusada]
    for anterior, seguinte in combinations(apresentando, 2):
        comuns = frozenset(anterior.apresentados) & frozenset(seguinte.apresentados)
        assert not comuns, (
            f"{sorted(comuns)} apresentado(s) em {anterior.nome} e em {seguinte.nome}: R2.7 torna "
            "inelegível, em qualquer etapa sem IA, o item já apresentado ao participante em outra"
        )
    todos = [identificador for etapa in apresentando for identificador in etapa.apresentados]
    assert len(set(todos)) == len(todos), (
        f"a sessão apresentou {len(todos)} itens e {len(set(todos))} distintos"
    )


def afirmar_desfecho_do_regime(caso: CasoDaSessao, executadas: Sequence[EtapaExecutada]) -> None:
    """A etapa recusada é exatamente a que o regime do banco prevê, e nenhuma outra.

    Igualdade, e não pertinência: nos regimes viáveis a sessão atravessa inteira, e um banco que
    recusasse uma etapa com itens para atendê-la abortaria a coleta em sala sem que a interseção
    vazia deixasse de valer. Nos regimes abaixo do mínimo, a recusa prevista é uma só, e a lista
    completa é o que impede que uma segunda recusa passe calada.
    """
    recusadas = tuple(etapa.conjunto for etapa in executadas if etapa.recusada)
    esperada = RECUSA_ESPERADA[caso.regime]
    detalhe = {etapa.nome: etapa.recusa for etapa in executadas if etapa.recusada}
    if esperada is None:
        assert not recusadas, (
            f"o banco do regime {caso.regime.value!r} atende a sessão inteira; recusou: {detalhe}"
        )
    else:
        assert recusadas == (esperada,), (
            f"o regime {caso.regime.value!r} recusa só {esperada}; recusou: {detalhe}"
        )


def afirmar_aperto_do_minimo_viavel(
    sessao: SessaoCompleta, executadas: Sequence[EtapaExecutada]
) -> None:
    """No mínimo viável nenhuma etapa tem folga, e a retenção recebe o exato que pediu.

    É a guarda de que a aritmética declarada em `estrategias.sessoes_completas` é a aritmética que
    o gerador construiu — sem ela, "banco próximo do mínimo viável" seria intenção. O que se
    afirma:

    - a união dos conjuntos apresentados é **todo** item sem IA do banco, e nada sobra. Segue da
      interseção vazia mais a aritmética, e é afirmada em vez de deduzida porque é o número que
      acusaria um pool superdimensionado por engano de contagem;
    - o universo elegível da retenção tem exatamente o tamanho do pedido dela. Zero de folga na
      **última** etapa é o aperto que §5.6 chama de caso delicado, e é a condição sob a qual um
      defeito de acúmulo deixa de ser invisível: com um item de sobra, a retenção ainda acharia
      item mesmo tendo recebido um histórico incompleto.
    """
    apresentados = frozenset(
        identificador for etapa in executadas for identificador in etapa.apresentados
    )
    assert apresentados == sessao.itens_sem_ia, (
        "no mínimo viável todo item sem IA é apresentado uma vez; sobraram "
        f"{sorted(sessao.itens_sem_ia - apresentados)} e apareceram de fora "
        f"{sorted(apresentados - sessao.itens_sem_ia)}"
    )
    assert len(apresentados) == sessao.consumo_sem_ia, (
        f"o consumo declarado é {sessao.consumo_sem_ia} itens e a sessão apresentou "
        f"{len(apresentados)}"
    )
    retencao = _etapa_de(executadas, conjunto_de_respostas(EscopoDeCalculo.TESTE_RETENCAO))
    assert retencao.disponiveis == retencao.pedidos, (
        f"a retenção pediu {retencao.pedidos} itens e tinha {retencao.disponiveis} elegíveis; no "
        "mínimo viável a última etapa não tem folga nenhuma (§5.6)"
    )


def _etapa_de(
    executadas: Sequence[EtapaExecutada], conjunto: ConjuntoDeRespostas
) -> EtapaExecutada:
    """A etapa executada de um conjunto de respostas. `StopIteration` é falha de simulação."""
    return next(etapa for etapa in executadas if etapa.conjunto == conjunto)


# --------------------------------------------------------------------------- #
# A propriedade
# --------------------------------------------------------------------------- #


@given(casos_da_sessao())
def test_o_item_de_uma_etapa_sem_ia_nao_reaparece_em_outra(caso: CasoDaSessao) -> None:
    # Feature: adia-cognitiveloop-prototype, Property 32: item sem IA não reaparece
    """Nenhum item é apresentado ao participante em duas etapas sem IA (R2.7, R12.4, R26.3).

    A sessão inteira é executada contra o banco gerado — linha de base, os três desafios
    independentes de R12.1 e o teste de retenção —, com `ja_apresentados` acumulado entre as
    etapas, e o oráculo exige interseção vazia entre os conjuntos apresentados.

    As quatro afirmações não são quatro propriedades: são o enunciado de §5.6 e as três coisas sem
    as quais ele passaria verde afirmando menos. O rótulo de pós-teste, porque uma simulação que
    pedisse ao banco um conjunto de pós-teste à parte compararia dois conjuntos disjuntos por
    acidente. O "inteira ou nenhuma", porque meia etapa tem interseção vazia com todas as outras.
    O desfecho por regime, porque um banco que recusasse tudo também teria interseção vazia.

    A semente de seleção é sorteada (R26.3): ela decide qual candidato elegível entra quando há
    mais de um, no desafio pelo banco e nas outras etapas por `_escolher`. Com semente fixa, a
    propriedade valeria para uma ordem de preferência em vez de para qualquer uma.

    Sem `@settings`: o orçamento de 100 exemplos vem do perfil `propriedades` de
    `backend/tests/conftest.py`, e esta propriedade não pede desvio nenhum. O prazo por exemplo
    fica como está porque não há E/S no corpo — nenhum arquivo é lido ou escrito, o banco é
    montado em memória a partir de `CargaConcluida` — e o que o corpo faz é indexar até duas dezenas
    de itens, fazer cinco chamadas e comparar conjuntos.

    A folga está medida, e não suposta. Nesta máquina, com as estatísticas da própria biblioteca:
    63 a 152 ms por exemplo, dos quais 56 a 124 ms em **geração** — isto é, 7 a 28 ms de corpo,
    contra o prazo padrão de 200 ms. A distinção é o que dispensa o `deadline=None` que P29 e P30
    precisam declarar: o prazo da biblioteca mede o corpo, não a geração, e aqui o custo está todo
    na geração, onde sai um item completo por posição do banco de sessão — até duas dezenas delas,
    contra as dez de P33.
    """
    sessao = caso.sessao
    banco = BancoDeItens(sessao.carga, sessao.semente)

    executadas = executar_sessao(banco, sessao)

    afirmar_que_o_posteste_e_rotulo(executadas)
    afirmar_etapa_inteira_ou_nenhuma(executadas)
    afirmar_intersecao_vazia(executadas)
    afirmar_desfecho_do_regime(caso, executadas)
    if caso.regime is Regime.MINIMO_VIAVEL:
        afirmar_aperto_do_minimo_viavel(sessao, executadas)


# --------------------------------------------------------------------------- #
# Afirmações de apoio: as duas ênfases de §5.6 têm exemplo
# --------------------------------------------------------------------------- #

BUSCA_DE_ENFASE: Final = settings(max_examples=200, phases=(Phase.generate,), deadline=None)
"""Orçamento das buscas de apoio. Sem a fase de encolhimento: o que se afirma é que a forma é
**alcançável**, e o exemplo mínimo não acrescenta nada a isso — só custa tempo no portão."""


def reconhecedor_de(regime: Regime) -> Callable[[CasoDaSessao], bool]:
    """Reconhecedor do regime, para que a busca falhe dizendo qual regime deixou de ser gerado."""

    def no_regime(caso: CasoDaSessao) -> bool:
        return caso.regime is regime

    return no_regime


@pytest.mark.parametrize("regime", list(Regime))
def test_a_geracao_alcanca_cada_regime_declarado(regime: Regime) -> None:
    """Os quatro regimes de aperto são alcançáveis, em vez de apenas pretendidos.

    Sem `@given`, porque não é a propriedade: é a guarda da **ênfase** dela. O modo de falha que
    ela pega é silencioso, e é o que a torna necessária. Um regime que deixasse de ser gerado —
    mutação que não muta, limite de folga que não aperta, sorteio que perde um membro — não quebra
    nada: P32 segue verde, afirmando menos, e o que se perde é a chance de encontrar o defeito.
    `find` reprova com `NoSuchExample`, que é o contrário de silencioso.

    O membro em risco é `MINIMO_VIAVEL`, e é o que §5.6 destaca: um banco com folga enorme
    satisfaz a interseção vazia sem nunca exercitar R2.7, porque a etapa seguinte encontra
    candidato de qualquer forma.
    """
    no_regime = reconhecedor_de(regime)

    assert no_regime(find(casos_da_sessao(), no_regime, settings=BUSCA_DE_ENFASE)), regime.value


def alcanca_banco_maior_que_o_minimo(caso: CasoDaSessao) -> bool:
    """Se o banco gerado tem mais itens do que o mínimo que o protocolo exige dele."""
    return len(caso.sessao.carga.itens) > _tamanho_minimo(caso.sessao)


def alcanca_banco_no_tamanho_minimo(caso: CasoDaSessao) -> bool:
    """Se o banco gerado tem exatamente o mínimo: nenhuma etapa com item de sobra."""
    return len(caso.sessao.carga.itens) == _tamanho_minimo(caso.sessao)


def _tamanho_minimo(sessao: SessaoCompleta) -> int:
    """Itens de um banco no mínimo viável para o roteiro desta sessão: praticados e os dois pools."""
    praticados = CICLOS_DO_PROTOCOLO * sessao.praticados_por_ciclo
    return praticados + sessao.minimo_do_pool_sem_ia + sessao.minimo_de_transferencia


TAMANHOS_DO_BANCO: Final = (
    ("banco no tamanho mínimo viável", alcanca_banco_no_tamanho_minimo),
    ("banco maior que o mínimo viável", alcanca_banco_maior_que_o_minimo),
)
"""As duas pontas da ênfase "banco de itens de tamanho variável, inclusive bancos próximos do
mínimo viável" de §5.6, com o reconhecedor de cada uma."""


@pytest.mark.parametrize(("enfase", "alcanca"), TAMANHOS_DO_BANCO)
def test_a_geracao_alcanca_as_duas_pontas_do_tamanho_do_banco(
    enfase: str, alcanca: Callable[[CasoDaSessao], bool]
) -> None:
    """Tamanho variável é afirmado nas duas pontas, porque uma só não é variação.

    A ponta de baixo é a que a propriedade precisa, e a de cima é a que mostra que a de baixo não
    é a única: um gerador travado no mínimo exercitaria R2.7 e nunca a escolha entre candidatos
    que a semente de R26.3 decide; um travado no banco folgado faria o contrário.
    """
    assert alcanca(find(casos_da_sessao(), alcanca, settings=BUSCA_DE_ENFASE)), enfase


def alcanca_aperto_na_retencao(caso: CasoDaSessao) -> bool:
    """Se a retenção rodou com universo elegível do tamanho exato do pedido dela.

    Roda a sessão dentro do reconhecedor porque o aperto da **última** etapa não se lê no banco:
    ele é o resíduo de tudo o que as etapas anteriores consumiram, que é precisamente o que §5.6
    chama de caso delicado.
    """
    banco = BancoDeItens(caso.sessao.carga, caso.sessao.semente)
    retencao = _etapa_de(
        executar_sessao(banco, caso.sessao), conjunto_de_respostas(EscopoDeCalculo.TESTE_RETENCAO)
    )
    return not retencao.recusada and retencao.disponiveis == retencao.pedidos


def test_a_geracao_alcanca_o_aperto_da_retencao() -> None:
    """A retenção é de fato executada com zero itens de sobra, em vez de só supostamente.

    É a ênfase mais fácil de perder sem notar. Bastaria um item a mais no pool — um erro de um na
    aritmética do mínimo viável, do tipo que ninguém revê — para a última etapa passar a ter folga,
    e aí a propriedade continuaria verde afirmando a interseção vazia sobre um banco que nunca
    chega a apertar. O que esta busca afirma é que o resíduo chega a zero com a etapa **atendida**:
    apertada, não recusada.
    """
    assert alcanca_aperto_na_retencao(
        find(casos_da_sessao(), alcanca_aperto_na_retencao, settings=BUSCA_DE_ENFASE)
    )
