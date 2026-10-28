"""Conjunto declarado do banco inicial de itens: ele sustenta o protocolo e não vaza gabarito.

Este arquivo carrega `data/itens/` **de verdade** — e é o único da suíte que faz isso. Todos
os outros testes do banco e do carregador montam itens em `tmp_path` ou em memória, de
propósito: lá o que está sob verificação é o código. Aqui o que está sob verificação é o
**conteúdo**, e conteúdo só é verificável contra o conteúdo real.

Três afirmações, e as três protegem coisas que falhariam no meio de uma coleta:

1. **o banco sustenta uma execução completa do protocolo.** A simulação acumula
   `ja_apresentados` do começo ao fim — linha de base, três ciclos de desafio independente, e
   teste de retenção — e exige que **nenhuma** etapa seja recusada. Sem isto, "o banco parece
   grande o bastante" é uma impressão: R2.7 torna inelegível, em qualquer etapa sem IA, todo
   item já apresentado em **outra** etapa sem IA, de modo que a contagem que basta para a
   primeira etapa pode não bastar para a quarta. O modo de falha é `ErroDeConjuntoIncompleto`
   com lacuna `JA_APRESENTADO`, e ele apareceria em sala, no terceiro ciclo;
2. **os conjuntos sem IA são disjuntos por declaração**, e não por sorte de contagem. Um item
   da linha de base que também declarasse `desafio_independente` poderia ser consumido na
   linha de base e faltar depois. Manter os conjuntos separados no próprio campo
   `etapas_permitidas` é o que torna a afirmação 1 estável diante de qualquer ordem de
   seleção, inclusive de outra semente;
3. **nenhuma dica pré-escrita revela o gabarito do próprio item.** O catálogo pré-escrito é a
   contingência de toda falha de geração (R7.3, R7.6): quando a guarda reprova o texto
   gerado, é a dica deste arquivo que chega ao estudante. Dica pré-escrita que vaza é vazamento
   garantido, não provável. A verificação completa é da `Guarda_de_Vazamento` (R7.11, design
   §6.5); aqui é o conjunto declarado dela começando a existir.

**Por que quatro itens praticados por ciclo.** O desafio independente de um ciclo tem um
equivalente por item praticado mais um item de transferência, logo cinco itens, e
`acerto_independente` assume os valores 0, 0,20, 0,40, 0,60, 0,80 e 1. O limiar de *fading* é
`indep >= 0,8`: com menos de quatro praticados por ciclo ele só seria alcançável com acerto
perfeito, e as Condições B e C deixariam de se distinguir de forma observável. A afirmação 1
verifica o tamanho do conjunto, que é o que sustenta essa escala.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 2.10, 7.11**
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Final

import pytest

from adia.nucleo.itens.banco import BancoDeItens, ConjuntoDoDesafio
from adia.nucleo.itens.carregador import arquivos_de_itens, carregar
from adia.nucleo.itens.erros import ErroDeCarga
from adia.nucleo.itens.modelo import Item
from adia.tipos import ETAPAS_SEM_IA, Etapa, Nivel

_RAIZ: Final = Path(__file__).resolve().parents[3]
_DIRETORIO_DE_ITENS: Final = _RAIZ / "data" / "itens"

HABILIDADE: Final = "equacao_linear"
"""Única habilidade do banco inicial. Entra como argumento normativo em `conjunto_do_desafio`."""

SEMENTE: Final = 20260302
"""Semente de seleção injetada, a mesma de `conftest.SEMENTE_FIXA` (R26.3).

Fixa de propósito: a satisfazibilidade do protocolo **não** pode depender de sorte na escolha
entre candidatos. O teste `test_a_execucao_completa_independe_da_semente` repete a simulação
com outras sementes, e é ele que transforma "funcionou com esta" em "funciona com qualquer uma".
"""

ITENS_POR_ETAPA: Final = 4
"""Itens praticados por ciclo, e também o tamanho da linha de base e do teste de retenção."""

CICLOS: Final = 3
"""Ciclos do CognitiveLoop (R12.1). O terceiro é o que R12.3 rotula como pós-teste."""

TAMANHO_DO_DESAFIO: Final = ITENS_POR_ETAPA + 1
"""Quatro equivalentes mais um item de transferência (R2.3). É o denominador de `acerto_independente`."""

DICAS_POR_ITEM: Final = len(Nivel)


# --------------------------------------------------------------------------- #
# Carga do banco real
# --------------------------------------------------------------------------- #


def _banco(semente: int = SEMENTE) -> BancoDeItens:
    """O banco de `data/itens/`, carregado com todas as validações da gramática.

    A carga é a mesma de `adia itens validar`: se o conteúdo violar a gramática, R2.2, R2.6 ou
    R2.9, este teste falha antes de qualquer afirmação sobre o protocolo — que é a ordem certa,
    porque banco que não carrega não é banco pequeno, é banco inválido.
    """
    arquivos = arquivos_de_itens(_DIRETORIO_DE_ITENS)
    if not arquivos:
        raise AssertionError(f"nenhum arquivo de definição em {_DIRETORIO_DE_ITENS}")
    carga = carregar(arquivos)
    if isinstance(carga, ErroDeCarga):
        raise AssertionError(f"o banco inicial não carrega: {carga.mensagem}")
    return BancoDeItens(carga, semente)


@pytest.fixture(scope="module")
def banco() -> BancoDeItens:
    """Banco carregado uma vez por módulo: a leitura de disco não é o que se verifica aqui."""
    return _banco()


def _ciclos_de_praticados(banco: BancoDeItens) -> tuple[tuple[str, ...], ...]:
    """Os itens praticados repartidos em ciclos de `ITENS_POR_ETAPA`, por identificador.

    A composição dos ciclos **não** está declarada no banco: qual item praticado entra em qual
    ciclo é decisão do `Gestor_de_Sessão` (§3.3), não do conteúdo. Por isso a partição é
    derivada aqui, da ordem canônica por identificador, em vez de escrita à mão: uma lista fixa
    continuaria verde se o conteúdo fosse renomeado, e passaria a verificar outro banco.
    """
    praticados = [item.id for item in banco.itens if item.e_praticado]
    esperados = ITENS_POR_ETAPA * CICLOS
    assert len(praticados) == esperados, (
        f"o protocolo pratica {ITENS_POR_ETAPA} itens em cada um dos {CICLOS} ciclos; "
        f"o banco declara {len(praticados)} item(ns) com `pratica_assistida`."
    )
    return tuple(
        tuple(praticados[inicio : inicio + ITENS_POR_ETAPA])
        for inicio in range(0, esperados, ITENS_POR_ETAPA)
    )


def _tomar(banco: BancoDeItens, etapa: Etapa, ja_apresentados: frozenset[str]) -> tuple[str, ...]:
    """Os `ITENS_POR_ETAPA` itens que a etapa sem IA consome, ou a recusa explicada.

    A escolha é o prefixo da ordem canônica, e não uma amostra aleatória, porque o que se
    verifica é a **disponibilidade**: se o universo elegível tem itens suficientes, qualquer
    escolha serve, e prefixo é a escolha que não introduz uma segunda fonte de variação.
    """
    elegiveis = banco.elegiveis_sem_ia(etapa, ja_apresentados)
    assert len(elegiveis) >= ITENS_POR_ETAPA, (
        f"a etapa {etapa.value!r} precisa de {ITENS_POR_ETAPA} itens elegíveis e tem "
        f"{len(elegiveis)}; com {len(ja_apresentados)} item(ns) já apresentado(s), a exclusão "
        f"de R2.7 esgotou o conjunto."
    )
    return tuple(item.id for item in elegiveis[:ITENS_POR_ETAPA])


def _executar_protocolo(banco: BancoDeItens) -> dict[str, tuple[str, ...]]:
    """Simula a execução inteira e devolve o que cada etapa sem IA consumiu.

    A ordem é a de R12.1 e o acúmulo de `ja_apresentados` atravessa as etapas, que é o ponto:
    cada etapa é pedida ao banco **depois** de tudo o que já foi apresentado, exatamente como
    o `Gestor_de_Sessão` pedirá.
    """
    consumido: dict[str, tuple[str, ...]] = {}
    ja_apresentados: set[str] = set()

    consumido["linha_de_base"] = _tomar(banco, Etapa.LINHA_DE_BASE, frozenset(ja_apresentados))
    ja_apresentados.update(consumido["linha_de_base"])

    for numero, praticados in enumerate(_ciclos_de_praticados(banco), start=1):
        conjunto = banco.conjunto_do_desafio(praticados, HABILIDADE, frozenset(ja_apresentados))
        if not isinstance(conjunto, ConjuntoDoDesafio):
            raise AssertionError(
                f"o desafio independente do ciclo {numero} foi recusado: {conjunto.mensagem}"
            )
        assert len(conjunto.pares) == ITENS_POR_ETAPA
        assert len(conjunto.transferencia) == 1
        identificadores = tuple(item.id for item in conjunto.itens)
        assert len(identificadores) == TAMANHO_DO_DESAFIO
        consumido[f"desafio_independente_{numero}"] = identificadores
        ja_apresentados.update(identificadores)

    consumido["teste_retencao"] = _tomar(banco, Etapa.TESTE_RETENCAO, frozenset(ja_apresentados))
    return consumido


# --------------------------------------------------------------------------- #
# 1. O banco sustenta uma execução completa do protocolo
# --------------------------------------------------------------------------- #


def test_o_banco_inicial_sustenta_uma_execucao_completa_do_protocolo(banco: BancoDeItens) -> None:
    """Nenhuma etapa sem IA é recusada, e nenhum item é apresentado duas vezes (R2.3, R2.7, R2.10).

    É a afirmação que transforma "o banco parece grande o bastante" em fato verificado. As duas
    metades são inseparáveis: um banco que recusa a última etapa falha na coleta, e um banco que
    repete item entre etapas sem IA mede memória do item em vez de domínio da habilidade — e aí
    a razão de retenção de R11.6 compararia um conjunto com um subconjunto de si mesmo.
    """
    consumido = _executar_protocolo(banco)

    assert set(consumido) == {
        "linha_de_base",
        "desafio_independente_1",
        "desafio_independente_2",
        "desafio_independente_3",
        "teste_retencao",
    }

    for etapa, identificadores in consumido.items():
        assert len(set(identificadores)) == len(identificadores), f"item repetido dentro de {etapa}"

    apresentados = [identificador for identificadores in consumido.values() for identificador in identificadores]
    repetidos = sorted({identificador for identificador in apresentados if apresentados.count(identificador) > 1})
    assert not repetidos, f"itens apresentados em mais de uma etapa sem IA: {repetidos}"

    total = ITENS_POR_ETAPA + CICLOS * TAMANHO_DO_DESAFIO + ITENS_POR_ETAPA
    assert len(apresentados) == total


def test_a_execucao_completa_independe_da_semente() -> None:
    """A satisfazibilidade não depende de qual candidato a semente preferiu (R26.3).

    `conjunto_do_desafio` usa a semente para ordenar candidatos elegíveis. Verificar uma única
    semente deixaria em aberto a possibilidade de o banco ter folga suficiente para **uma**
    ordem de escolha e não para outra — e a semente da coleta é registrada na proveniência, não
    escolhida para funcionar.
    """
    for semente in (0, 1, 7, SEMENTE, 2 ** 31 - 1):
        consumido = _executar_protocolo(_banco(semente))
        apresentados = [
            identificador for identificadores in consumido.values() for identificador in identificadores
        ]
        assert len(apresentados) == len(set(apresentados)), f"semente {semente} repetiu item entre etapas"


# --------------------------------------------------------------------------- #
# 2. Os conjuntos sem IA são disjuntos por declaração
# --------------------------------------------------------------------------- #


def test_nenhum_item_declara_mais_de_uma_etapa_sem_ia(banco: BancoDeItens) -> None:
    """Linha de base, desafio e retenção têm itens próprios, separados no próprio campo (R2.4, R2.7).

    A disjunção por declaração é mais forte que a disjunção por contagem. Um item que declarasse
    `linha_de_base` **e** `desafio_independente` seria elegível nas duas, e bastaria a linha de
    base consumi-lo para que faltasse um equivalente no ciclo correspondente — recusa do
    conjunto inteiro, no meio da coleta, por uma folga que parecia existir.
    """
    for item in banco.itens:
        sem_ia = item.etapas_permitidas & ETAPAS_SEM_IA
        assert len(sem_ia) <= 1, (
            f"o item {item.id!r} declara mais de uma etapa sem IA: "
            f"{sorted(etapa.value for etapa in sem_ia)}"
        )


def test_nenhum_item_declara_o_posteste(banco: BancoDeItens) -> None:
    """`Etapa.POSTESTE` é rótulo, não etapa com itens próprios (R12.3, design §3.0).

    O pós-teste é o nome que R12.3 manda aplicar ao desafio independente do terceiro ciclo; o
    evento registrado é `DESAFIO_INDEPENDENTE` com `ciclo = 3`. Declarar `posteste` em algum
    item criaria um conjunto elegível para um rótulo que nenhuma etapa executa — e, porque
    `POSTESTE` está em `ETAPAS_SEM_IA`, esse conjunto seria tratado como etapa sem IA legítima
    por `elegiveis_sem_ia`, com itens que ninguém apresenta.
    """
    declaram = [item.id for item in banco.itens if Etapa.POSTESTE in item.etapas_permitidas]
    assert not declaram, f"itens que declaram `posteste`: {declaram}"
    assert banco.elegiveis_sem_ia(Etapa.POSTESTE, frozenset()) == ()


# --------------------------------------------------------------------------- #
# 3. Nenhuma dica pré-escrita revela o gabarito
# --------------------------------------------------------------------------- #


def _sem_acento(texto: str) -> str:
    """Texto decomposto e sem marcas combinantes: `três` e `tres` passam a ser a mesma cadeia."""
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(caractere for caractere in decomposto if not unicodedata.combining(caractere))


def _normalizar(texto: str) -> str:
    """Forma de comparação: insensível a caixa **e** a acentuação.

    As duas insensibilidades são a escolha deliberadamente mais forte, e cada uma fecha um
    vazamento real: `Quatro` no começo de frase, e `três` digitado sem acento. O preço é
    aceitar falso positivo — uma dica legítima que contenha a palavra do gabarito por outra
    razão reprova —, e é o preço certo: aqui o falso positivo custa reescrever uma frase, e o
    falso negativo custa entregar a resposta ao estudante.
    """
    return _sem_acento(texto).casefold()


def _ocorre_como_token(texto: str, alvo: str) -> bool:
    """Se o alvo aparece no texto delimitado, isto é, sem letra nem dígito em volta.

    A delimitação é o que separa vazamento de coincidência de dígito: com gabarito `4`, a
    forma `x = 4` e a forma `4,0` reprovam, e `14` não. Sem ela, qualquer número que contivesse
    o dígito do gabarito reprovaria, o que tornaria o conjunto declarado inútil por excesso.

    Esta é a forma **literal** de detecção, que é a primeira das várias de R7.2. A normalização
    numérica completa — separador decimal, separador de milhar, unidade declarada, numeral em
    palavras, equivalência algébrica dentro da tolerância e expressão aritmética cujo resultado
    é o gabarito (R7.9) — é da `Guarda_de_Vazamento`, não daqui. O que o banco faz para
    cooperar com ela é declarar o numeral em palavras entre as `variacoes_gabarito`, de modo que
    a varredura abaixo já cubra `quatro` além de `4`.
    """
    agulha = _normalizar(alvo)
    if not agulha:
        return False
    return re.search(rf"(?<![0-9a-z]){re.escape(agulha)}(?![0-9a-z])", _normalizar(texto)) is not None


def _proibidos(item: Item) -> tuple[tuple[str, str], ...]:
    """Cadeias que nenhuma dica do item pode conter, cada uma com o **nome** do campo de origem.

    O nome, e nunca o valor, é o que vai para a mensagem de falha. A regra é a mesma da seção 6
    da gramática: `gabarito`, `variacoes_gabarito`, `termos_essenciais`, `enunciado` e texto de
    dica não são interpolados em diagnóstico, porque o diagnóstico vai para o terminal, para o
    log de subida da API e, no pior caso, para uma captura de tela em sala.
    """
    proibidos = [("gabarito", item.gabarito)]
    proibidos.extend(
        (f"variacoes_gabarito[{indice}]", variacao)
        for indice, variacao in enumerate(item.variacoes_gabarito)
    )
    return tuple(proibidos)


def test_nenhuma_dica_pre_escrita_revela_o_gabarito_do_item(banco: BancoDeItens) -> None:
    """As quatro dicas de cada item não contêm o gabarito nem variação declarada dele (R2.1, R7.11).

    A varredura é do conjunto inteiro, item por item, e inclui L4 — que é onde isto se perde. O
    exemplo resolvido de L4 precisa usar **outros números**: para `2x + 3 = 11`, um L4 que
    resolvesse `2x + 3 = 11` entregaria `x = 4` com todos os passos. A dica pré-escrita existe
    justamente porque a geração não é confiável nesse ponto — na auditoria inicial deste projeto
    o modelo local recebeu este item com instrução explícita de não revelar a incógnita e
    devolveu o valor dela.

    Um vazamento que esta varredura **não** cobre, por não ser afirmação sobre um item só: o
    gabarito de um item aparecendo no L4 de outro. Ele não é detectável por contagem de dígitos
    — gabaritos de uma casa colidem com os dígitos de qualquer exemplo — e o que o fecha é
    estrutural: nenhuma equação usada como exemplo em L4 coincide com a equação de nenhum item
    do banco, de modo que resolver o exemplo não resolve item algum.
    """
    vazamentos: list[str] = []
    dicas_varridas = 0
    comparacoes = 0

    for item in banco.itens:
        proibidos = _proibidos(item)
        assert proibidos, f"o item {item.id!r} não declara gabarito a proteger"
        for nivel in Nivel:
            texto = item.dicas[nivel]
            dicas_varridas += 1
            for campo, proibido in proibidos:
                comparacoes += 1
                if _ocorre_como_token(texto, proibido):
                    vazamentos.append(f"{item.id} {nivel.name}: contém `{campo}`")
            for indice, conjunto in enumerate(item.termos_essenciais):
                comparacoes += 1
                if all(_ocorre_como_token(texto, termo) for termo in conjunto):
                    vazamentos.append(f"{item.id} {nivel.name}: contém `termos_essenciais[{indice}]` inteiro")

    assert dicas_varridas == DICAS_POR_ITEM * len(banco.itens)
    assert comparacoes >= 3 * dicas_varridas, (
        "cada item declara gabarito e ao menos duas variações, logo a varredura faz ao menos "
        f"três comparações por dica; fez {comparacoes} em {dicas_varridas} dica(s)."
    )
    assert not vazamentos, "dicas pré-escritas que reproduzem o gabarito do próprio item: " + "; ".join(vazamentos)


def test_todos_os_enunciados_do_banco_sao_distintos(banco: BancoDeItens) -> None:
    """Dois itens com o mesmo enunciado não qualificam como par isomorfo (R2.2).

    A exigência de R2.2 é sobre o par praticado/equivalente, mas verificá-la no conjunto inteiro
    custa uma linha e fecha o caso em que um item foi duplicado por descuido na escrita do
    conteúdo: identificadores diferentes, texto igual, e o estudante reencontrando no desafio
    independente exatamente o enunciado que praticou.
    """
    enunciados = [item.enunciado for item in banco.itens]
    assert len(set(enunciados)) == len(enunciados)
