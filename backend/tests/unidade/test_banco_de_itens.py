"""Testes do banco de itens: etapa permitida, elegibilidade sem IA e o conjunto tudo ou nada.

O que estes testes afirmam não é "o banco encontra itens". É que **nenhum item chega ao
estudante fora do lugar que o protocolo prescreveu**, e que o desafio independente ou vem
inteiro ou não vem. As duas afirmações protegem medidas diferentes:

1. item pedido para etapa que ele não admite é recusado, e **nenhum substituto** é escolhido
   em tempo de execução (R2.5, §7.2). Substituir faria a etapa rodar com itens que o protocolo
   não prescreveu, e a TAI do escopo descreveria outro conjunto;
2. item já apresentado em etapa sem IA é inelegível em qualquer outra etapa sem IA (R2.7).
   Sem isso, o pós-teste mediria memória do item, e a razão de retenção de R11.6 compararia um
   conjunto com um subconjunto de si mesmo;
3. o conjunto do desafio é **tudo ou nada** (R2.3, R2.10): exatamente um equivalente elegível
   por item praticado, mais ao menos um item de transferência da habilidade alvo, e nenhum
   outro item — ou um erro que nomeia o item praticado e a associação indisponível, com
   **nenhum item devolvido**. Conjunto parcial produziria desafio de tamanho diferente do
   praticado, e o *gap* que alimenta a regra de regulação ficaria incomparável;
4. a seleção é reproduzível pela semente injetada (R26.3): mesma semente e mesmo pedido,
   mesmas escolhas; sementes diferentes, escolhas que de fato diferem.

As três lacunas que a Propriedade 33 enumera — equivalente ausente, transferência ausente,
elegibilidade esgotada por apresentação anterior — têm um teste cada, e em todos a verificação
é a mesma: o retorno é a recusa, e não um conjunto menor.

Os bancos são montados a partir de `CargaConcluida` construída no teste, e não de
`data/itens/`. O banco inicial é da tarefa 3.14, e depender dele aqui trocaria a verificação
do banco pela verificação do conteúdo. As propriedades P32 e P33, sobre entradas geradas, são
as tarefas 3.8 e 3.9.

**Validates: Requirements 2.3, 2.5, 2.7, 2.10, 26.3**
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from types import MappingProxyType

import pytest

from adia.nucleo.itens.banco import (
    BancoDeItens,
    ConjuntoDoDesafio,
    ParDoDesafio,
    ResultadoDeObtencao,
    ResultadoDoConjunto,
)
from adia.nucleo.itens.carregador import CargaConcluida
from adia.nucleo.itens.erros import (
    ErroDeCarga,
    ErroDeConjuntoIncompleto,
    ErroDeEtapaNaoPermitida,
    ErroDeItemDesconhecido,
    ErroDeSelecao,
    LacunaDoConjunto,
)
from adia.nucleo.itens.modelo import EQUIVALENTE, TRANSFERENCIA, Item, Relacao, TipoGabarito
from adia.tipos import Etapa, Nivel

# --------------------------------------------------------------------------- #
# Construção de banco
# --------------------------------------------------------------------------- #

HABILIDADE = "equacao_linear"
"""Habilidade alvo de todos os itens, salvo quando o teste pede outra."""

DESAFIO = Etapa.DESAFIO_INDEPENDENTE
PRATICA = Etapa.PRATICA_ASSISTIDA

DICAS = MappingProxyType(
    {
        Nivel.L1: "O que a igualdade está afirmando sobre os dois lados?",
        Nivel.L2: "Isto é uma equação do primeiro grau com uma incógnita.",
        Nivel.L3: "Isole a incógnita aplicando a mesma operação aos dois lados.",
        Nivel.L4: "Em 5y + 2 = 17, subtraia 2 dos dois lados e divida por 5.",
    }
)
"""Catálogo de L1 a L4 que o modelo exige em todo item (R2.1), sem revelar gabarito."""


def item(
    identificador: str,
    *,
    habilidade: str = HABILIDADE,
    dificuldade: int = 2,
    etapas: Iterable[Etapa] = (DESAFIO,),
    transferencia: bool = False,
    enunciado: str | None = None,
) -> Item:
    """Item válido, com enunciado derivado do identificador.

    O enunciado é distinto por item de propósito: R2.2 exige enunciado **distinto** entre o
    praticado e o equivalente, e dois itens com o mesmo texto não qualificariam como par — o
    teste falharia por um motivo que não é o que ele investiga.
    """
    return Item(
        id=identificador,
        enunciado=enunciado if enunciado is not None else f"Resolva o item {identificador}.",
        habilidade_alvo=habilidade,
        dificuldade=dificuldade,
        tamanho_max_resposta=120,
        tipo_gabarito=TipoGabarito.NUMERICO,
        gabarito="4",
        tolerancia=Decimal("0.01"),
        unidade=None,
        sinonimos_unidade=(),
        variacoes_gabarito=(),
        termos_essenciais=(),
        incognita="x",
        etapas_permitidas=frozenset(etapas),
        transferencia=transferencia,
        dicas=DICAS,
    )


def banco_de(itens: Sequence[Item], relacoes: Sequence[Relacao], semente: int = 7) -> BancoDeItens:
    """Banco montado sobre uma carga ordenada como o carregador a publica."""
    carga = CargaConcluida(
        itens=tuple(sorted(itens, key=lambda lido: lido.id)),
        relacoes=tuple(sorted(relacoes, key=lambda lida: (lida.item_origem, lida.item_destino, lida.tipo))),
    )
    return BancoDeItens(carga, semente)


def banco_minimo(semente: int = 7) -> BancoDeItens:
    """Banco com um praticado, um equivalente e um item de transferência.

    É o trio mínimo que R2.2 e R2.6 exigem de todo item praticado, e o conjunto do desafio que
    ele sustenta tem tamanho 2: um equivalente e uma transferência.
    """
    return banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("e1"),
            item("t1", transferencia=True),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
        ],
        semente,
    )


def obtido(resultado: ResultadoDeObtencao) -> Item:
    """O item de uma obtenção que deveria ter sido aceita."""
    assert isinstance(resultado, Item), f"obtenção recusada: {resultado}"
    return resultado


def recusa_de_obtencao(resultado: ResultadoDeObtencao) -> ErroDeEtapaNaoPermitida | ErroDeItemDesconhecido:
    """O erro de uma obtenção que deveria ter sido recusada, garantindo que nada foi devolvido."""
    assert not isinstance(resultado, Item), "a obtenção deveria ter sido recusada"
    return resultado


def conjunto(resultado: ResultadoDoConjunto) -> ConjuntoDoDesafio:
    """O conjunto de uma solicitação que deveria ter sido atendida."""
    assert isinstance(resultado, ConjuntoDoDesafio), f"conjunto recusado: {resultado}"
    return resultado


def recusa_do_conjunto(resultado: ResultadoDoConjunto) -> ErroDeConjuntoIncompleto:
    """O erro de uma solicitação recusada, garantindo que **nenhum** item veio junto.

    A verificação de "conjunto vazio, nunca parcial" é esta: o valor devolvido não é um
    `ConjuntoDoDesafio`, e portanto não carrega item nenhum — o tipo do retorno é o que torna o
    conjunto parcial irrepresentável, e não uma convenção de quem chama (R2.10).
    """
    assert not isinstance(resultado, ConjuntoDoDesafio), "a solicitação deveria ter sido recusada"
    assert isinstance(resultado, ErroDeConjuntoIncompleto), f"recusa inesperada: {resultado}"
    return resultado


def escolhas(resultado: ResultadoDoConjunto) -> tuple[str, ...]:
    """Identificadores do conjunto, na ordem em que o banco os devolveu."""
    return tuple(lido.id for lido in conjunto(resultado).itens)


# --------------------------------------------------------------------------- #
# R2.5 — obter item para uma etapa
# --------------------------------------------------------------------------- #


def test_obter_devolve_o_item_na_etapa_que_ele_admite() -> None:
    """Item pedido para etapa presente em `etapas_permitidas` é entregue (R2.5)."""
    banco = banco_minimo()

    assert obtido(banco.obter("e1", DESAFIO)).id == "e1"
    assert obtido(banco.obter("p1", PRATICA)).id == "p1"


def test_obter_recusa_a_etapa_fora_das_permitidas_e_nao_escolhe_substituto() -> None:
    """Etapa ausente de `etapas_permitidas` recusa, nomeando item e etapa (R2.5, §7.2).

    A recusa nomeia também as etapas que o item admite, que é a informação que falta para
    corrigir o pedido. Nenhum substituto é escolhido: o retorno é erro, não outro item.
    """
    banco = banco_minimo()

    erro = recusa_de_obtencao(banco.obter("p1", DESAFIO))

    assert isinstance(erro, ErroDeEtapaNaoPermitida)
    assert erro.item_id == "p1"
    assert erro.etapa is DESAFIO
    assert erro.etapas_permitidas == frozenset({PRATICA})
    assert erro.codigo == "ITEM_FORA_DA_ETAPA"
    assert "p1" in erro.mensagem
    assert DESAFIO.value in erro.mensagem


def test_obter_recusa_identificador_que_o_banco_nao_conhece() -> None:
    """Identificador inexistente recusa com erro próprio, não como etapa não permitida.

    Acréscimo declarado ao contrato de §3.1. Tratar o desconhecido como etapa não permitida
    mandaria quem depura olhar as `etapas_permitidas` de um item que não existe.
    """
    banco = banco_minimo()

    erro = recusa_de_obtencao(banco.obter("inexistente", DESAFIO))

    assert isinstance(erro, ErroDeItemDesconhecido)
    assert erro.item_id == "inexistente"
    assert erro.codigo == "ITEM_DESCONHECIDO"


def test_nenhum_erro_de_selecao_deriva_de_erro_de_carga() -> None:
    """As duas famílias de erro têm raízes separadas, e a separação tem consequência (§7.2).

    O caminho de subida da API aborta diante de `ErroDeCarga`: banco que não carrega não é
    servido. Se a recusa de um pedido fosse capturável como falha de carga, um item pedido na
    etapa errada derrubaria o serviço inteiro — e, na direção oposta, um arquivo malformado
    apareceria ao estudante como `409` em vez de impedir a execução.

    A afirmação é sobre a **hierarquia**, e não sobre uma instância, porque o `mypy --strict`
    com `warn_unreachable` já prova que a interseção dos dois tipos é vazia: um
    `isinstance(erro, ErroDeCarga)` sobre um erro de seleção é código morto, e o verificador
    recusa. Esta verificação é a mesma invariante em tempo de execução, legível para quem lê o
    teste sem rodar o mypy.
    """
    for classe in (ErroDeEtapaNaoPermitida, ErroDeItemDesconhecido, ErroDeConjuntoIncompleto):
        assert ErroDeSelecao in classe.__mro__
        assert ErroDeCarga not in classe.__mro__


# --------------------------------------------------------------------------- #
# R2.7 — elegibilidade nas etapas sem IA
# --------------------------------------------------------------------------- #


def test_elegiveis_sem_ia_filtra_pela_etapa_pedida() -> None:
    """Só entram os itens cujas `etapas_permitidas` contêm a etapa (R2.4, R2.5)."""
    banco = banco_de(
        [
            item("a", etapas=(DESAFIO,)),
            item("b", etapas=(Etapa.LINHA_DE_BASE,)),
            item("c", etapas=(DESAFIO, Etapa.TESTE_RETENCAO)),
        ],
        [],
    )

    assert [lido.id for lido in banco.elegiveis_sem_ia(DESAFIO, frozenset())] == ["a", "c"]
    assert [lido.id for lido in banco.elegiveis_sem_ia(Etapa.LINHA_DE_BASE, frozenset())] == ["b"]
    assert [lido.id for lido in banco.elegiveis_sem_ia(Etapa.TESTE_RETENCAO, frozenset())] == ["c"]


def test_elegiveis_sem_ia_exclui_o_item_ja_apresentado_em_etapa_sem_ia() -> None:
    """Item visto em qualquer etapa sem IA sai da elegibilidade das demais (R2.7).

    É a regra que impede o item do desafio independente do ciclo 1 de reaparecer no pós-teste,
    onde ele mediria memória do item em vez de domínio da habilidade.
    """
    banco = banco_de([item("a"), item("b"), item("c")], [])

    elegiveis = banco.elegiveis_sem_ia(DESAFIO, frozenset({"a", "c"}))

    assert [lido.id for lido in elegiveis] == ["b"]


def test_elegiveis_sem_ia_recusa_etapa_com_ia() -> None:
    """A exclusão de R2.7 só está definida para etapas sem IA.

    Na prática assistida o estudante **deve** reencontrar o item praticado, de modo que
    responder ali seria responder sob uma regra que não vale naquela etapa.
    """
    banco = banco_minimo()

    with pytest.raises(ValueError, match="não é etapa sem IA"):
        banco.elegiveis_sem_ia(PRATICA, frozenset())


# --------------------------------------------------------------------------- #
# R2.3 — o conjunto completo
# --------------------------------------------------------------------------- #


def test_conjunto_tem_um_equivalente_por_praticado_e_a_transferencia_da_habilidade() -> None:
    """Cardinalidade exata de R2.3: um equivalente por praticado, mais um de transferência."""
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("p2", etapas=(PRATICA,)),
            item("e1"),
            item("e2"),
            item("t1", transferencia=True),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p2", "e2", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
            Relacao("p2", "t1", TRANSFERENCIA),
        ],
    )

    montado = conjunto(banco.conjunto_do_desafio(["p1", "p2"], HABILIDADE, frozenset()))

    assert montado.praticados == ("p1", "p2")
    assert montado.equivalente_de("p1").id == "e1"
    assert montado.equivalente_de("p2").id == "e2"
    assert [lido.id for lido in montado.transferencia] == ["t1"]
    assert [lido.id for lido in montado.itens] == ["e1", "e2", "t1"]
    assert len(montado.itens) == len(montado.praticados) + 1


def test_o_conjunto_nao_traz_nenhum_outro_item_do_banco() -> None:
    """"E nenhum outro item" (R2.3): o banco tem mais candidatos e o conjunto segue com dois."""
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("e1"),
            item("e2"),
            item("t1", transferencia=True),
            item("t2", transferencia=True),
            item("x1"),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p1", "e2", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
        ],
    )

    montado = conjunto(banco.conjunto_do_desafio(["p1"], HABILIDADE, frozenset()))

    assert len(montado.pares) == 1
    assert len(montado.transferencia) == 1
    assert montado.equivalente_de("p1").id in {"e1", "e2"}
    assert "x1" not in {lido.id for lido in montado.itens}


def test_o_conjunto_exclui_o_item_ja_apresentado_e_escolhe_outro_equivalente() -> None:
    """A elegibilidade de R2.7 vale dentro do conjunto, e sobrando candidato o conjunto sai."""
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("e1"),
            item("e2"),
            item("t1", transferencia=True),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p1", "e2", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
        ],
    )

    montado = conjunto(banco.conjunto_do_desafio(["p1"], HABILIDADE, frozenset({"e1"})))

    assert montado.equivalente_de("p1").id == "e2"


# --------------------------------------------------------------------------- #
# R2.10 — as lacunas, todas com conjunto vazio
# --------------------------------------------------------------------------- #


def test_recusa_quando_falta_equivalente_para_algum_praticado() -> None:
    """Primeira lacuna de P33: um praticado sem nenhum equivalente qualificado (R2.10).

    A recusa nomeia **qual** praticado e **qual** associação, que é o que R2.10 exige, e o
    segundo praticado ter equivalente não produz conjunto parcial com ele.
    """
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("p2", etapas=(PRATICA,)),
            item("e1"),
            item("t1", transferencia=True),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
        ],
    )

    erro = recusa_do_conjunto(banco.conjunto_do_desafio(["p1", "p2"], HABILIDADE, frozenset()))

    assert erro.associacao == EQUIVALENTE
    assert erro.item_praticado == "p2"
    assert erro.lacuna is LacunaDoConjunto.SEM_CANDIDATO_QUALIFICADO
    assert erro.praticados == ("p1", "p2")
    assert erro.codigo == "CONJUNTO_INDISPONIVEL"
    assert "p2" in erro.mensagem


def test_recusa_quando_a_habilidade_nao_tem_item_de_transferencia() -> None:
    """Segunda lacuna de P33: equivalentes completos e nenhuma transferência (R2.10).

    `item_praticado` é `None` porque a exigência de transferência é da solicitação e da
    habilidade alvo, não de um praticado em particular; a identificação que R2.10 pede fica com
    `praticados` e `habilidade`.
    """
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("e1"),
            item("t_outra", habilidade="geometria", transferencia=True),
        ],
        [Relacao("p1", "e1", EQUIVALENTE)],
    )

    erro = recusa_do_conjunto(banco.conjunto_do_desafio(["p1"], HABILIDADE, frozenset()))

    assert erro.associacao == TRANSFERENCIA
    assert erro.item_praticado is None
    assert erro.habilidade == HABILIDADE
    assert erro.praticados == ("p1",)
    assert HABILIDADE in erro.mensagem


def test_recusa_quando_a_apresentacao_anterior_esgota_a_elegibilidade() -> None:
    """Terceira lacuna de P33: havia candidato, e R2.7 consumiu o último (R2.7, R2.10).

    A lacuna é distinguível de "sem equivalente declarado", e a distinção é operacional: esta
    não se conserta no arquivo do item, e sim ampliando o banco.
    """
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("e1"),
            item("e2"),
            item("t1", transferencia=True),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p1", "e2", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
        ],
    )

    erro = recusa_do_conjunto(banco.conjunto_do_desafio(["p1"], HABILIDADE, frozenset({"e1", "e2"})))

    assert erro.associacao == EQUIVALENTE
    assert erro.item_praticado == "p1"
    assert erro.lacuna is LacunaDoConjunto.JA_APRESENTADO
    assert erro.candidatos_qualificados == 2
    assert erro.excluidos_por_apresentacao == 2


def test_recusa_quando_o_equivalente_nao_admite_a_etapa_do_desafio() -> None:
    """Candidato que qualifica em R2.2 mas não admite a etapa é inelegível (R2.4, R2.5)."""
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("e1", etapas=(Etapa.LINHA_DE_BASE,)),
            item("t1", transferencia=True),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
        ],
    )

    erro = recusa_do_conjunto(banco.conjunto_do_desafio(["p1"], HABILIDADE, frozenset()))

    assert erro.lacuna is LacunaDoConjunto.FORA_DA_ETAPA
    assert erro.excluidos_por_etapa == 1


def test_item_praticado_no_ciclo_nao_serve_de_equivalente_de_outro_praticado() -> None:
    """Praticado neste ciclo é inelegível, com lacuna própria.

    Apresentar `p2` como desafio de `p1` faria o desafio medir, sem assistência, um item
    resolvido com assistência minutos antes — que é o que o par isomorfo existe para evitar.
    """
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA, DESAFIO)),
            item("p2", etapas=(PRATICA, DESAFIO)),
            item("t1", transferencia=True),
        ],
        [
            Relacao("p1", "p2", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
        ],
    )

    erro = recusa_do_conjunto(banco.conjunto_do_desafio(["p1", "p2"], HABILIDADE, frozenset()))

    assert erro.lacuna is LacunaDoConjunto.PRATICADO_NO_CICLO
    assert erro.excluidos_por_pratica == 1


# --------------------------------------------------------------------------- #
# Atribuição de equivalentes dois a dois distintos
# --------------------------------------------------------------------------- #


def test_candidato_disputado_e_reacomodado_em_vez_de_recusado() -> None:
    """O caso em que a escolha gulosa falharia embora exista atribuição completa.

    `p1` pode receber `e1` ou `e2`; `p2` só pode receber `e1`. Tomar o primeiro candidato livre
    para `p1` deixaria `p2` sem nada e recusaria um pedido que o banco tem itens para atender.
    O emparelhamento máximo reacomoda `p1` e atende os dois.
    """
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("p2", etapas=(PRATICA,)),
            item("e1"),
            item("e2"),
            item("t1", transferencia=True),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p1", "e2", EQUIVALENTE),
            Relacao("p2", "e1", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
        ],
    )

    montado = conjunto(banco.conjunto_do_desafio(["p1", "p2"], HABILIDADE, frozenset()))

    assert montado.equivalente_de("p2").id == "e1"
    assert montado.equivalente_de("p1").id == "e2"


def test_recusa_quando_nenhuma_atribuicao_completa_existe() -> None:
    """Dois praticados disputando o único candidato: recusa, e com lacuna de disputa.

    Aqui a recusa é fato sobre o banco, e não artefato da ordem de visita: nenhuma atribuição
    dá equivalente distinto aos dois. A lacuna `DISPUTADO` distingue este caso de "sem
    equivalente", porque o conserto é outro — o banco precisa de mais um isomorfo.
    """
    banco = banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("p2", etapas=(PRATICA,)),
            item("e1"),
            item("t1", transferencia=True),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p2", "e1", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
        ],
    )

    erro = recusa_do_conjunto(banco.conjunto_do_desafio(["p1", "p2"], HABILIDADE, frozenset()))

    assert erro.associacao == EQUIVALENTE
    assert erro.item_praticado == "p2"
    assert erro.lacuna is LacunaDoConjunto.DISPUTADO


# --------------------------------------------------------------------------- #
# R26.3 — determinismo da semente injetada
# --------------------------------------------------------------------------- #


def banco_com_escolha(semente: int) -> BancoDeItens:
    """Banco em que a semente de fato decide: dois equivalentes e dois de transferência."""
    return banco_de(
        [
            item("p1", etapas=(PRATICA,)),
            item("e1"),
            item("e2"),
            item("t1", transferencia=True),
            item("t2", transferencia=True),
        ],
        [
            Relacao("p1", "e1", EQUIVALENTE),
            Relacao("p1", "e2", EQUIVALENTE),
            Relacao("p1", "t1", TRANSFERENCIA),
            Relacao("p1", "t2", TRANSFERENCIA),
        ],
        semente,
    )


def test_a_mesma_semente_produz_as_mesmas_escolhas(semente: int) -> None:
    """Mesma semente e mesmo pedido, mesmo conjunto — em duas instâncias independentes (R26.3)."""
    primeiro = banco_com_escolha(semente).conjunto_do_desafio(["p1"], HABILIDADE, frozenset())
    segundo = banco_com_escolha(semente).conjunto_do_desafio(["p1"], HABILIDADE, frozenset())

    assert escolhas(primeiro) == escolhas(segundo)


def test_sementes_diferentes_produzem_escolhas_que_de_fato_diferem() -> None:
    """A semente **decide**: em alguma faixa de sementes, a escolha muda (R26.3).

    Sem esta metade, uma seleção que ignorasse a semente passaria no teste de reprodutibilidade
    — "sempre o primeiro em ordem alfabética" é perfeitamente reproduzível e não é escolha
    semeada. A faixa é fixa e a verificação é determinística: não há sorteio no teste.
    """
    observadas = {
        escolhas(banco_com_escolha(valor).conjunto_do_desafio(["p1"], HABILIDADE, frozenset()))
        for valor in range(32)
    }

    assert len(observadas) > 1


def test_a_escolha_nao_depende_de_quantas_chamadas_vieram_antes(semente: int) -> None:
    """Chamadas anteriores não deslocam a escolha: não há gerador acumulando estado no banco.

    Um `random.Random` guardado no banco avançaria a cada pedido, e a escolha do ciclo 3
    passaria a depender de quantas vezes o ciclo 1 chamou o banco — contagem que não está
    registrada em lugar nenhum, e sem a qual o replay de R26.7 não reproduz a seleção.
    """
    banco = banco_com_escolha(semente)
    primeiro = escolhas(banco.conjunto_do_desafio(["p1"], HABILIDADE, frozenset()))

    banco.conjunto_do_desafio(["p1"], HABILIDADE, frozenset({"e1"}))
    banco.elegiveis_sem_ia(DESAFIO, frozenset())

    assert escolhas(banco.conjunto_do_desafio(["p1"], HABILIDADE, frozenset())) == primeiro


def test_o_banco_informa_a_semente_injetada(semente: int) -> None:
    """A semente que decidiu a seleção é legível no banco, para o registro de proveniência (R26.3)."""
    assert banco_minimo(semente).semente == semente


# --------------------------------------------------------------------------- #
# Pedido que não descreve um ciclo
# --------------------------------------------------------------------------- #


def test_pedido_sem_praticados_e_defeito_de_quem_chama() -> None:
    """Sequência vazia levanta, em vez de anunciar conjunto indisponível.

    Não é indisponibilidade do banco: o banco tem todos os itens. Devolver
    `ErroDeConjuntoIncompleto` faria a interface culpar o conteúdo por um pedido malformado.
    """
    banco = banco_minimo()

    with pytest.raises(ValueError, match="praticados está vazia"):
        banco.conjunto_do_desafio([], HABILIDADE, frozenset())


def test_pedido_com_praticado_repetido_e_defeito_de_quem_chama() -> None:
    """Identificador repetido levanta: o ciclo apresenta cada praticado uma vez (R2.3)."""
    banco = banco_minimo()

    with pytest.raises(ValueError, match="identificador repetido"):
        banco.conjunto_do_desafio(["p1", "p1"], HABILIDADE, frozenset())


def test_praticado_desconhecido_recusa_com_erro_proprio() -> None:
    """Praticado que não existe no banco não é lacuna de associação, e sim referência inválida."""
    banco = banco_minimo()

    resultado = banco.conjunto_do_desafio(["inexistente"], HABILIDADE, frozenset())

    assert isinstance(resultado, ErroDeItemDesconhecido)
    assert resultado.item_id == "inexistente"


# --------------------------------------------------------------------------- #
# O construtor do conjunto torna o conjunto parcial irrepresentável
# --------------------------------------------------------------------------- #


def test_conjunto_recusa_o_mesmo_equivalente_para_dois_praticados() -> None:
    """Equivalente compartilhado faria o conjunto menor que o número de praticados (R2.3).

    A verificação está no construtor de propósito: conjunto parcial não é um valor que o tipo
    saiba representar, e assim nenhum caminho de código consegue produzir um e chamá-lo de
    conjunto do desafio.
    """
    compartilhado = item("e1")

    with pytest.raises(ValueError, match="mesmo equivalente"):
        ConjuntoDoDesafio(
            habilidade=HABILIDADE,
            pares=(
                ParDoDesafio(praticado="p1", equivalente=compartilhado),
                ParDoDesafio(praticado="p2", equivalente=compartilhado),
            ),
            transferencia=(item("t1", transferencia=True),),
        )


def test_conjunto_recusa_posicao_de_transferencia_sem_item_de_transferencia() -> None:
    """Item na posição de transferência precisa declarar `transferencia = true` (R11.2).

    A TT conta exatamente os itens marcados assim; um item comum nessa posição entraria no
    denominador de uma métrica que ele não alimenta.
    """
    with pytest.raises(ValueError, match="transferencia = true"):
        ConjuntoDoDesafio(
            habilidade=HABILIDADE,
            pares=(ParDoDesafio(praticado="p1", equivalente=item("e1")),),
            transferencia=(item("t1", transferencia=False),),
        )


def test_conjunto_recusa_par_do_item_com_ele_mesmo() -> None:
    """Equivalente igual ao praticado não pareia nada (R2.2)."""
    with pytest.raises(ValueError, match="equivalente de si mesmo"):
        ParDoDesafio(praticado="e1", equivalente=item("e1"))
