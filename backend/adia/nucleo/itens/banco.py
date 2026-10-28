"""Banco de itens em memória: ``obter``, ``conjunto_do_desafio`` e ``elegiveis_sem_ia``.

Forma declarada em §3.1 do design. O ``Carregador_de_Itens`` responde "este conteúdo é
válido?"; o ``Banco_de_Itens`` responde "quais itens este participante pode ver **agora**?".
A diferença é de natureza, não de grau: a primeira pergunta é sobre arquivos e se responde
uma vez na subida; a segunda é sobre histórico de um participante e se responde a cada etapa.
É por isso que as recusas daqui têm raiz própria em ``erros.py`` — ``ErroDeSelecao``, nunca
``ErroDeCarga`` — e viram ``409`` em vez de abortar o serviço (§7.2).

## Tudo ou nada, e o que o conjunto parcial custaria

``conjunto_do_desafio`` é a operação que a Propriedade 33 existe para cercar: ou **exatamente
um** equivalente elegível para cada item praticado do ciclo, mais ao menos um item de
transferência elegível da habilidade alvo, e nenhum outro item; ou um erro que identifica o
item praticado e a associação indisponível, **sem nenhum item devolvido** (R2.3, R2.10).

O conjunto parcial é a falha concreta que a regra fecha. Ele produziria desafio independente
de tamanho diferente do praticado, e o *gap* entre ``acerto_assistido`` e
``acerto_independente`` — que é entrada da regra de regulação (§3.4) — passaria a comparar
denominadores distintos. A decisão de teto do ciclo seguinte sairia de uma diferença que não
mede diferença nenhuma, e nada na tela pareceria errado. ``ConjuntoDoDesafio`` verifica a
cardinalidade no próprio construtor, de modo que nem este módulo nem um teste consigam
fabricar um conjunto parcial e chamá-lo de conjunto.

## Elegibilidade

Um candidato é elegível para o desafio independente quando cumpre as quatro condições, nesta
ordem de verificação, que é também a ordem de informação da recusa:

1. **qualifica** no critério de R2.2 — ``equivalente_qualifica`` ou ``transferencia_qualifica``
   em ``modelo.py``, que é o mesmo critério que o carregador aplica. Um só;
2. **admite a etapa**: ``DESAFIO_INDEPENDENTE`` está em ``etapas_permitidas`` (R2.4, R2.5);
3. **não foi praticado neste ciclo**: um item resolvido com assistência minutos antes não mede
   desempenho autônomo, e o par isomorfo existe justamente para que não precise medir;
4. **não foi apresentado antes em etapa sem IA** (R2.7): linha de base, desafio independente
   de qualquer ciclo, pós-teste e teste de retenção. O conjunto vem de quem chama, porque é
   histórico do participante e o banco não tem participante.

## A semente é injetada, e a escolha é estável

Quando mais de um candidato está elegível, qual deles entra no conjunto é decisão da semente
registrada na proveniência (R26.3, §4.3). O módulo **não** usa o estado global de ``random``:
cada escolha deriva de uma instância própria de ``random.Random``, semeada com a cadeia
``semente ⟂ contexto ⟂ id do candidato``.

Duas propriedades vêm dessa forma, e nenhuma delas viria de um gerador guardado como estado
do banco:

- **independência da ordem das chamadas.** Um ``random.Random`` mantido no banco avançaria a
  cada pedido, e a escolha do ciclo 3 passaria a depender de quantas vezes o ciclo 1 chamou o
  banco. O replay de R26.7 reproduziria a sequência só se repetisse a contagem de chamadas,
  que não está registrada em lugar nenhum;
- **estabilidade sob crescimento do banco.** A chave é por candidato, e não um embaralhamento
  da lista inteira, então acrescentar um item ao banco não reordena a preferência entre os que
  já existiam. É o que mantém a preferência de uma execução antiga legível depois da tarefa
  3.14 acrescentar itens.

Por construção, portanto: mesma semente e mesmo pedido, mesmas escolhas; sementes diferentes,
escolhas que de fato diferem quando há mais de um candidato elegível. As duas metades estão
verificadas em ``backend/tests/unidade/test_banco_de_itens.py``.

``random.Random`` é semeado com **cadeia de texto**, e não com uma tupla: o Python 3.11
removeu o semeamento a partir de objeto arbitrário, e para ``str`` a semente passa por
``sha512`` do texto em UTF-8 — determinística entre execuções, plataformas e valores de
``PYTHONHASHSEED``. O contrato ``nucleo-puro`` de ``backend/.importlinter`` proíbe ``secrets``,
``uuid`` e ``time`` em ``adia.nucleo``; ``random`` semeado explicitamente é o oposto do que a
proibição persegue — o que ela persegue é a aleatoriedade **implícita**.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from adia.nucleo.itens.carregador import CargaConcluida
from adia.nucleo.itens.erros import (
    ErroDeConjuntoIncompleto,
    ErroDeEtapaNaoPermitida,
    ErroDeItemDesconhecido,
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
from adia.tipos import ETAPAS_SEM_IA, Etapa

# --------------------------------------------------------------------------- #
# Parâmetros do conjunto do desafio
# --------------------------------------------------------------------------- #

ETAPA_DO_CONJUNTO: Final = Etapa.DESAFIO_INDEPENDENTE
"""Etapa para a qual o conjunto do desafio é montado.

Fixa, e não parâmetro, porque o conjunto do desafio **é** o desafio independente: R2.3 fala
da solicitação dos itens dessa etapa, e nenhuma outra tem equivalente pareado a item
praticado. O pós-teste não abre exceção — ``Etapa.POSTESTE`` é rótulo do conjunto sem IA do
terceiro ciclo (R12.3), e a etapa de fato executada continua sendo ``DESAFIO_INDEPENDENTE``,
como ``adia.tipos`` registra.
"""

TRANSFERENCIAS_NO_CONJUNTO: Final = 1
"""Quantos itens de transferência o conjunto leva.

R2.3 e R8.3 exigem "ao menos um", e o contrato de §3.1 não oferece parâmetro para pedir mais.
Entregar **exatamente** um é a leitura que mantém as duas metades de R2.3 verdadeiras ao mesmo
tempo: "ao menos um item de transferência" e "e nenhum outro item". Também mantém o tamanho do
conjunto igual a ``itens praticados + 1`` em todo ciclo e todo participante, o que é
pré-condição de comparar TT entre ciclos — com quantidade variável, uma TT de 0,5 significaria
coisas diferentes em dois ciclos do mesmo participante.

Se o protocolo passar a querer mais de um, este é o lugar: o número aparece uma vez.
"""

_SEPARADOR: Final = "\x1f"
"""Separador das partes da cadeia de semeadura. É o separador de unidade do ASCII, que não
ocorre em identificador nem em nome de habilidade (ver ``PADRAO_DE_IDENTIFICADOR``), de modo
que duas composições diferentes de contexto não podem produzir a mesma cadeia."""


# --------------------------------------------------------------------------- #
# Conjunto do desafio independente
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ParDoDesafio:
    """Correspondência entre um item praticado e o equivalente escolhido para ele.

    O par é explícito, e não um item solto numa lista, porque é a correspondência que torna
    afirmável a cardinalidade de R2.3 — "exatamente um item equivalente elegível **para cada**
    item praticado". Com uma lista de itens, "exatamente um por praticado" só poderia ser
    verificado por contagem, e contagem igual não é correspondência: dois equivalentes do mesmo
    praticado e nenhum do outro passariam pela contagem.

    ``praticado`` é identificador, e ``equivalente`` é o item inteiro: quem monta a tela precisa
    do enunciado do equivalente, e do praticado precisa apenas saber de qual item ele responde.
    """

    praticado: str
    equivalente: Item

    def __post_init__(self) -> None:
        """Recusa o par que não pareia nada: equivalente que é o próprio item praticado."""
        if self.praticado == self.equivalente.id:
            raise ValueError(
                f"o item {self.praticado!r} não pode ser equivalente de si mesmo (R2.2): o desafio "
                "independente mediria, sem assistência, o item que acabou de ser praticado com ela."
            )


@dataclass(frozen=True)
class ConjuntoDoDesafio:
    """Os itens do desafio independente de um ciclo, com a correspondência que os justifica.

    Tipo que §3.1 cita no retorno de ``conjunto_do_desafio`` sem definir; a forma abaixo é
    desta tarefa. O construtor verifica as invariantes que a Propriedade 33 afirma, e a
    verificação **no construtor** é o ponto: um conjunto parcial não é um valor que este tipo
    saiba representar, então nenhum caminho de código — nem um teste distraído — consegue
    produzir um e chamá-lo de conjunto do desafio. Falha fechada nas duas portas, como em
    ``Item.__post_init__``.

    O que está garantido em todo valor que exista:

    - ``pares`` não é vazio, cada item praticado aparece **uma** vez, e dois praticados nunca
      recebem o **mesmo** equivalente — se recebessem, o conjunto teria menos itens que o
      número de praticados e o desafio voltaria a ser de tamanho diferente do praticado;
    - ``transferencia`` tem ao menos um item, todos da habilidade alvo e marcados como de
      transferência (R2.3, R11.2 — a TT conta exatamente os itens marcados assim);
    - nenhum item aparece duas vezes no conjunto inteiro, e todos admitem a etapa do desafio
      (R2.5).
    """

    habilidade: str
    pares: tuple[ParDoDesafio, ...]
    transferencia: tuple[Item, ...]

    def __post_init__(self) -> None:
        """Verifica a cardinalidade exata e a disjunção que R2.3 e a Propriedade 33 exigem."""
        if not self.habilidade.strip():
            raise ValueError("o conjunto do desafio exige habilidade alvo não vazia (R2.3).")
        if not self.pares:
            raise ValueError(
                "o conjunto do desafio exige ao menos um par praticado/equivalente (R2.3): um ciclo "
                "sem item praticado não tem desempenho assistido com que comparar o independente."
            )
        if not self.transferencia:
            raise ValueError(
                "o conjunto do desafio exige ao menos um item de transferência da habilidade alvo "
                "(R2.3): sem ele não há base para a TT."
            )
        self._verificar_unicidade()
        self._verificar_perfil_de_transferencia()

    def _verificar_unicidade(self) -> None:
        """Recusa praticado repetido, equivalente compartilhado e item em duas posições."""
        praticados = [par.praticado for par in self.pares]
        if len(set(praticados)) != len(praticados):
            raise ValueError("o conjunto do desafio não admite o mesmo item praticado duas vezes (R2.3).")
        identificadores = [par.equivalente.id for par in self.pares]
        if len(set(identificadores)) != len(identificadores):
            raise ValueError(
                "dois itens praticados receberam o mesmo equivalente: o conjunto teria menos itens que "
                "o número de praticados, e R2.3 exige exatamente um equivalente para cada um."
            )
        todos = identificadores + [item.id for item in self.transferencia]
        if len(set(todos)) != len(todos):
            raise ValueError(
                "o conjunto do desafio não admite o mesmo item em duas posições: a TAI contaria a "
                "resposta uma vez e o denominador contaria o item duas (R11.1)."
            )

    def _verificar_perfil_de_transferencia(self) -> None:
        """Garante que os itens de transferência sejam de transferência, e da habilidade alvo."""
        for item in self.transferencia:
            if not item.transferencia:
                raise ValueError(
                    f"o item {item.id!r} está na posição de transferência e não declara "
                    "`transferencia = true`; a TT conta apenas itens marcados assim (R11.2)."
                )
            if item.habilidade_alvo != self.habilidade:
                raise ValueError(
                    f"o item de transferência {item.id!r} é da habilidade {item.habilidade_alvo!r} e o "
                    f"conjunto é da habilidade {self.habilidade!r}; R2.3 exige a mesma habilidade alvo."
                )
        for par in self.pares:
            if ETAPA_DO_CONJUNTO not in par.equivalente.etapas_permitidas:
                raise ValueError(
                    f"o item {par.equivalente.id!r} não admite a etapa {ETAPA_DO_CONJUNTO.value!r} (R2.5)."
                )
        for item in self.transferencia:
            if ETAPA_DO_CONJUNTO not in item.etapas_permitidas:
                raise ValueError(f"o item {item.id!r} não admite a etapa {ETAPA_DO_CONJUNTO.value!r} (R2.5).")

    @property
    def praticados(self) -> tuple[str, ...]:
        """Os itens praticados cobertos, na ordem em que foram solicitados."""
        return tuple(par.praticado for par in self.pares)

    @property
    def itens(self) -> tuple[Item, ...]:
        """Todos os itens do conjunto: os equivalentes na ordem dos pares, depois a transferência.

        É o conjunto completo e nada além dele, que é a metade positiva de R2.3 — "e nenhum
        outro item". A ordem é determinística e deliberada: o item de transferência vem por
        último porque exige adaptação da estrutura de solução, e abrir por ele mudaria o que a
        etapa mede antes de o estudante ter resolvido um isomorfo.
        """
        return tuple(par.equivalente for par in self.pares) + self.transferencia

    def equivalente_de(self, praticado: str) -> Item:
        """O equivalente escolhido para o item praticado dado.

        Levanta ``KeyError`` para item fora do conjunto, como qualquer busca por chave ausente:
        o conjunto já declara quais praticados cobre em ``praticados``.
        """
        for par in self.pares:
            if par.praticado == praticado:
                return par.equivalente
        raise KeyError(praticado)


type ResultadoDeObtencao = Item | ErroDeEtapaNaoPermitida | ErroDeItemDesconhecido
"""Ou o item pedido, ou a razão de ele não ser entregue.

**Divergência declarada em relação a §3.1**, que escreve ``Item | ErroDeEtapaNaoPermitida``.
O terceiro tipo cobre o identificador que não existe no banco, caso que o contrato não prevê e
que não desaparece por não estar previsto. A justificativa está em ``ErroDeItemDesconhecido``.
"""

type ResultadoDoConjunto = ConjuntoDoDesafio | ErroDeConjuntoIncompleto | ErroDeItemDesconhecido
"""Ou o conjunto inteiro, ou a razão de ele não ser montado. Nunca conjunto parcial (R2.10).

Mesma divergência de ``ResultadoDeObtencao``, pelo mesmo motivo: ``praticados`` são
identificadores, e um identificador pode não corresponder a item nenhum.
"""


# --------------------------------------------------------------------------- #
# Triagem de candidatos
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Triagem:
    """Candidatos elegíveis e a contabilidade de onde os demais foram perdidos.

    A contabilidade não é enfeite da mensagem: ela é o que distingue defeito de conteúdo de
    esgotamento legítimo. "Sem equivalente elegível" tem conserto no arquivo do item quando
    nenhum candidato qualifica, e conserto nenhum quando o participante já viu todos — e quem
    opera o protocolo precisa saber qual dos dois aconteceu antes de mexer em ``data/itens/``.
    """

    elegiveis: tuple[Item, ...]
    qualificados: int
    excluidos_por_etapa: int
    excluidos_por_pratica: int
    excluidos_por_apresentacao: int
    disputado: bool = False
    """Se os candidatos elegíveis existiam e não deram para todos os praticados.

    Campo próprio, e não contagem: a disputa não perde candidato nenhum — ela é a única causa
    em que todas as contagens de exclusão podem ser zero e ainda assim não há conjunto."""

    @property
    def lacuna(self) -> LacunaDoConjunto:
        """Causa declarada da ausência de candidato elegível, na precedência declarada.

        Do mais informativo para o menos: já apresentado, praticado no ciclo, fora da etapa,
        disputado, sem candidato qualificado. A ordem importa quando mais de uma causa coexiste,
        e tem duas razões:

        - "já apresentado" vem primeiro porque é a única que descreve a **execução em curso** em
          vez do conteúdo do banco — é a consequência esperada de R2.7 num banco pequeno, e não
          um arquivo a consertar. Uma disputa em que a apresentação anterior consumiu candidato é
          relatada como ``JA_APRESENTADO`` por isso: o conserto é o mesmo, e o operador precisa
          saber que R2.7 está apertando;
        - "disputado" vem antes de "sem candidato qualificado" porque na disputa havia candidato
          qualificado, e dizer o contrário seria falso.
        """
        if self.excluidos_por_apresentacao:
            return LacunaDoConjunto.JA_APRESENTADO
        if self.excluidos_por_pratica:
            return LacunaDoConjunto.PRATICADO_NO_CICLO
        if self.excluidos_por_etapa:
            return LacunaDoConjunto.FORA_DA_ETAPA
        if self.disputado:
            return LacunaDoConjunto.DISPUTADO
        return LacunaDoConjunto.SEM_CANDIDATO_QUALIFICADO


# --------------------------------------------------------------------------- #
# Banco de itens
# --------------------------------------------------------------------------- #


class BancoDeItens:
    """Banco de itens carregado, com as três consultas de §3.1.

    Construído a partir de uma ``CargaConcluida`` e da semente de seleção da proveniência.
    Não lê arquivo, não recarrega nada e não guarda estado mutável: os índices são montados uma
    vez no construtor, e as três consultas são funções do banco e dos seus argumentos. Isso é o
    que faz duas chamadas iguais devolverem valores iguais, independentemente do que aconteceu
    entre elas.

    A ``CargaConcluida`` é a entrada natural porque ela é o banco **já validado**: o carregador
    verificou gramática, identificador único, faixas, perfil por tipo de gabarito, integridade
    das relações, as associações de R2.2 e R2.6 e o conflito de R2.9 (§3.1). O banco não repete
    nenhuma dessas verificações — repetir significaria duas implementações do mesmo critério, e
    é por isso que o critério de qualificação de R2.2 mora em ``modelo.py`` e é importado pelos
    dois lados.
    """

    __slots__ = ("_itens", "_por_id", "_semente", "_vizinhos")

    def __init__(self, carga: CargaConcluida, semente: int) -> None:
        """Monta os índices de consulta sobre uma carga concluída, com a semente injetada.

        ``semente`` é a semente de seleção de itens registrada em ``proveniencia_execucao``
        (R26.3, §4.3). Ela entra aqui, e não em cada chamada, porque é parâmetro da **execução**
        e não do pedido: uma semente por chamada permitiria que dois pedidos da mesma execução
        usassem sementes diferentes, e aí a semente registrada na proveniência deixaria de
        descrever a seleção que de fato aconteceu.
        """
        self._itens: tuple[Item, ...] = carga.itens
        self._por_id: Mapping[str, Item] = MappingProxyType({item.id: item for item in carga.itens})
        self._semente = semente
        self._vizinhos: Mapping[tuple[str, TipoDeRelacao], tuple[Item, ...]] = _indexar_relacoes(carga)

    @property
    def semente(self) -> int:
        """A semente de seleção injetada, para o registro de proveniência (R26.3)."""
        return self._semente

    @property
    def itens(self) -> tuple[Item, ...]:
        """Todos os itens do banco, ordenados por identificador como na carga."""
        return self._itens

    # ----------------------------------------------------------------------- #
    # R2.5 — obter um item para uma etapa
    # ----------------------------------------------------------------------- #

    def obter(self, item_id: str, etapa: Etapa) -> ResultadoDeObtencao:
        """O item pedido, se ele existe e admite a etapa; o erro correspondente, se não (R2.5).

        Nenhum substituto é escolhido em tempo de execução, e §7.2 é explícito sobre isso: a
        etapa **não** inicia. Trocar o item fora da etapa por outro "parecido" faria a etapa
        rodar com itens que o protocolo não prescreveu, e a TAI do escopo passaria a descrever
        um conjunto diferente do registrado.

        A consulta não conhece participante, e portanto **não** aplica a exclusão de R2.7: ela
        responde "este item pode ser apresentado nesta etapa?", que é pergunta sobre o item.
        Quem precisa de elegibilidade por histórico chama ``elegiveis_sem_ia`` ou
        ``conjunto_do_desafio``.
        """
        item = self._por_id.get(item_id)
        if item is None:
            return ErroDeItemDesconhecido(item_id=item_id, etapa=etapa)
        if etapa not in item.etapas_permitidas:
            return ErroDeEtapaNaoPermitida(
                item_id=item_id, etapa=etapa, etapas_permitidas=item.etapas_permitidas
            )
        return item

    # ----------------------------------------------------------------------- #
    # R2.7 — itens elegíveis para uma etapa sem IA
    # ----------------------------------------------------------------------- #

    def elegiveis_sem_ia(self, etapa: Etapa, ja_apresentados: frozenset[str]) -> tuple[Item, ...]:
        """Itens que a etapa sem IA admite e que o participante ainda não viu (R2.7).

        R2.7 é a regra que impede o mesmo item de medir proficiência duas vezes: um item do
        desafio independente do ciclo 1 que reaparecesse no pós-teste mediria memória do item,
        não domínio da habilidade, e a razão de retenção de R11.6 compararia um conjunto com um
        subconjunto de si mesmo. A exclusão vale entre **todas** as etapas sem IA — linha de
        base, desafio independente de qualquer ciclo, pós-teste e teste de retenção.

        A ordem é a canônica por identificador, herdada da carga, e **não** depende da semente:
        o retorno é o universo elegível, não uma escolha. Semente é o que resolve empate entre
        candidatos na hora de escolher, e quem escolhe aqui é quem chama.

        Levanta ``ValueError`` para etapa com IA. A exclusão de R2.7 é definida sobre etapas sem
        IA, e devolver uma lista para a prática assistida seria responder sob uma regra que não
        vale ali — o estudante **deve** reencontrar o item praticado na mesma etapa.
        """
        if etapa not in ETAPAS_SEM_IA:
            permitidas = ", ".join(sorted(sem_ia.value for sem_ia in ETAPAS_SEM_IA))
            raise ValueError(
                f"a etapa {etapa.value!r} não é etapa sem IA; a exclusão de R2.7 só está definida "
                f"para {permitidas}."
            )
        return tuple(
            item
            for item in self._itens
            if etapa in item.etapas_permitidas and item.id not in ja_apresentados
        )

    # ----------------------------------------------------------------------- #
    # R2.3, R2.10 — o conjunto do desafio independente, tudo ou nada
    # ----------------------------------------------------------------------- #

    def conjunto_do_desafio(
        self, praticados: Sequence[str], habilidade: str, ja_apresentados: frozenset[str]
    ) -> ResultadoDoConjunto:
        """O conjunto inteiro do desafio independente de um ciclo, ou a recusa (R2.3, R2.10).

        Devolve exatamente um equivalente elegível para cada item de ``praticados``, mais
        ``TRANSFERENCIAS_NO_CONJUNTO`` item de transferência elegível da habilidade
        ``habilidade``, e nenhum outro item. Qualquer lacuna produz ``ErroDeConjuntoIncompleto``
        e **nenhum item**.

        **Ordem das verificações**, fixa para que o mesmo pedido produza sempre a mesma recusa:
        equivalentes antes de transferência, porque a lacuna de equivalente nomeia o item
        praticado que R2.10 pede; e a disputa entre praticados depois das duas, porque ela só
        existe quando há candidato elegível para todos.

        **Os dois papéis de ``habilidade``.** No lado da transferência, ``habilidade`` é
        normativa: é a habilidade alvo de que R2.3 exige o item de transferência. No lado do
        equivalente, o critério de R2.2 compara o candidato com o **item praticado**, de modo
        que cada praticado traz a sua própria habilidade. Pedido incoerente — praticados de uma
        habilidade e ``habilidade`` de outra — não é silenciosamente consertado: ele recusa, e a
        mensagem nomeia a habilidade pedida, que é o que permite ver o engano.

        Levanta ``ValueError`` para pedido que não descreve um ciclo: ``praticados`` vazio, ou
        com identificador repetido. Nenhum dos dois é indisponibilidade do banco, e devolvê-los
        como ``ErroDeConjuntoIncompleto`` faria a interface anunciar "conjunto indisponível"
        para um banco que tem todos os itens.
        """
        itens_praticados = self._praticados_do_pedido(praticados)
        if isinstance(itens_praticados, ErroDeItemDesconhecido):
            return itens_praticados
        no_ciclo = frozenset(praticados)

        triagens: dict[str, _Triagem] = {
            praticado.id: self._triar_equivalentes(praticado, no_ciclo, ja_apresentados)
            for praticado in itens_praticados
        }
        for praticado in itens_praticados:
            triagem = triagens[praticado.id]
            if not triagem.elegiveis:
                return self._recusar(praticados, habilidade, EQUIVALENTE, praticado.id, triagem)

        de_transferencia = self._triar_transferencia(habilidade, no_ciclo, ja_apresentados)
        if not de_transferencia.elegiveis:
            return self._recusar(praticados, habilidade, TRANSFERENCIA, None, de_transferencia)

        escolhidos, nao_atribuidos = _atribuir_equivalentes(
            tuple((identificador, triagem.elegiveis) for identificador, triagem in triagens.items())
        )
        if nao_atribuidos:
            disputado = nao_atribuidos[0]
            disputa = _disputa(triagens[disputado])
            return self._recusar(praticados, habilidade, EQUIVALENTE, disputado, disputa)

        tomados = {escolhido.id for escolhido in escolhidos.values()}
        transferencia = tuple(
            item for item in de_transferencia.elegiveis if item.id not in tomados
        )[:TRANSFERENCIAS_NO_CONJUNTO]
        if not transferencia:
            disputa = _disputa(de_transferencia)
            return self._recusar(praticados, habilidade, TRANSFERENCIA, None, disputa)

        return ConjuntoDoDesafio(
            habilidade=habilidade,
            pares=tuple(
                ParDoDesafio(praticado=identificador, equivalente=escolhidos[identificador])
                for identificador in praticados
            ),
            transferencia=transferencia,
        )

    # ----------------------------------------------------------------------- #
    # Internos
    # ----------------------------------------------------------------------- #

    def _praticados_do_pedido(self, praticados: Sequence[str]) -> tuple[Item, ...] | ErroDeItemDesconhecido:
        """Os itens praticados do pedido, ou o primeiro identificador que o banco não conhece."""
        if not praticados:
            raise ValueError(
                "o conjunto do desafio é montado a partir dos itens praticados do ciclo (R2.3); "
                "a sequência de praticados está vazia."
            )
        if len(set(praticados)) != len(praticados):
            raise ValueError(
                "a sequência de praticados tem identificador repetido; o ciclo apresenta cada item "
                "praticado uma vez, e repetir aqui mudaria a cardinalidade que R2.3 fixa."
            )
        encontrados: list[Item] = []
        for identificador in praticados:
            item = self._por_id.get(identificador)
            if item is None:
                return ErroDeItemDesconhecido(item_id=identificador, etapa=ETAPA_DO_CONJUNTO)
            encontrados.append(item)
        return tuple(encontrados)

    def _triar_equivalentes(
        self, praticado: Item, no_ciclo: frozenset[str], ja_apresentados: frozenset[str]
    ) -> _Triagem:
        """Equivalentes elegíveis do item praticado, em ordem de preferência da semente."""
        qualificados = tuple(
            candidato
            for candidato in self._vizinhos.get((praticado.id, EQUIVALENTE), ())
            if equivalente_qualifica(praticado, candidato)
        )
        contexto = (EQUIVALENTE, praticado.habilidade_alvo, praticado.id)
        return self._triar(qualificados, contexto, no_ciclo, ja_apresentados)

    def _triar_transferencia(
        self, habilidade: str, no_ciclo: frozenset[str], ja_apresentados: frozenset[str]
    ) -> _Triagem:
        """Itens de transferência elegíveis da habilidade alvo, em ordem de preferência da semente.

        O universo é a **habilidade**, não a relação declarada, e é o que §3.1 e R2.3 pedem: "ao
        menos um item de transferência elegível da mesma habilidade alvo". A relação declarada
        segue sendo exigida na carga, item praticado por item praticado (R2.6), mas na montagem
        do conjunto ela seria restrição sem efeito de medida — um item de transferência da mesma
        habilidade alvo mede transferência da mesma habilidade, esteja a relação escrita a partir
        deste praticado ou de outro. Fixar a relação aqui faria a disponibilidade do desafio
        depender de qual praticado o autor do arquivo escolheu como origem da relação, que a
        seção 4 da gramática declara informativa.
        """
        qualificados = tuple(
            candidato
            for candidato in self._itens
            if e_de_transferencia_da_habilidade(candidato, habilidade)
        )
        return self._triar(qualificados, (TRANSFERENCIA, habilidade), no_ciclo, ja_apresentados)

    def _triar(
        self,
        qualificados: Sequence[Item],
        contexto: Sequence[str],
        no_ciclo: frozenset[str],
        ja_apresentados: frozenset[str],
    ) -> _Triagem:
        """Aplica as três exclusões de elegibilidade e ordena o que sobra pela semente."""
        elegiveis: list[Item] = []
        fora_da_etapa = 0
        no_ciclo_contados = 0
        apresentados = 0
        for candidato in qualificados:
            if ETAPA_DO_CONJUNTO not in candidato.etapas_permitidas:
                fora_da_etapa += 1
            elif candidato.id in no_ciclo:
                no_ciclo_contados += 1
            elif candidato.id in ja_apresentados:
                apresentados += 1
            else:
                elegiveis.append(candidato)
        return _Triagem(
            elegiveis=self._ordenar_pela_semente(elegiveis, contexto),
            qualificados=len(qualificados),
            excluidos_por_etapa=fora_da_etapa,
            excluidos_por_pratica=no_ciclo_contados,
            excluidos_por_apresentacao=apresentados,
        )

    def _ordenar_pela_semente(self, candidatos: Sequence[Item], contexto: Sequence[str]) -> tuple[Item, ...]:
        """Ordem de preferência entre candidatos elegíveis, decidida pela semente injetada.

        A chave é calculada **por candidato**, com uma instância própria de ``random.Random``
        semeada pela cadeia ``semente ⟂ contexto ⟂ id``. Duas consequências, as duas desejadas:
        a ordem não depende de quantos candidatos existem, e acrescentar um item ao banco não
        reordena a preferência entre os que já estavam lá.

        O identificador entra como segundo componente da chave. Não é defesa contra colisão
        improvável de ponto flutuante: é o que garante que a ordenação seja **total**, de modo
        que a ordem não dependa da estabilidade do algoritmo de ordenação nem da ordem em que
        os candidatos chegaram.
        """
        return tuple(sorted(candidatos, key=lambda item: (self._chave(contexto, item.id), item.id)))

    def _chave(self, contexto: Sequence[str], item_id: str) -> float:
        """Chave de ordenação do candidato, determinística dada a semente e o contexto."""
        cadeia = _SEPARADOR.join((str(self._semente), *contexto, item_id))
        return random.Random(cadeia).random()

    def _recusar(
        self,
        praticados: Sequence[str],
        habilidade: str,
        associacao: TipoDeRelacao,
        item_praticado: str | None,
        triagem: _Triagem,
    ) -> ErroDeConjuntoIncompleto:
        """Monta a recusa do pedido inteiro, com a lacuna e a contabilidade da triagem."""
        return ErroDeConjuntoIncompleto(
            praticados=tuple(praticados),
            habilidade=habilidade,
            associacao=associacao,
            lacuna=triagem.lacuna,
            item_praticado=item_praticado,
            candidatos_qualificados=triagem.qualificados,
            excluidos_por_etapa=triagem.excluidos_por_etapa,
            excluidos_por_pratica=triagem.excluidos_por_pratica,
            excluidos_por_apresentacao=triagem.excluidos_por_apresentacao,
        )


# --------------------------------------------------------------------------- #
# Índice de relações e atribuição de equivalentes
# --------------------------------------------------------------------------- #


def _indexar_relacoes(carga: CargaConcluida) -> Mapping[tuple[str, TipoDeRelacao], tuple[Item, ...]]:
    """Vizinhos de cada item por tipo de relação, nas **duas** direções.

    A direção da relação é informativa, não normativa (seção 4 de ``docs/gramatica-itens.md``):
    isomorfismo é simétrico por natureza, e exigir que o autor escreva a relação a partir do
    item praticado faria a disponibilidade do desafio depender da ordem de escrita no arquivo.
    O carregador examina o par nas duas direções pelo mesmo motivo.

    Relação cuja ponta não corresponde a item carregado é ignorada em vez de levantar: o
    carregador já recusa esse arquivo (integridade de relação, §3.1), então o caso não ocorre em
    banco carregado — e um banco montado à mão num teste não deve explodir no construtor por um
    dado que a consulta simplesmente não tem como usar.
    """
    vizinhos: dict[tuple[str, TipoDeRelacao], list[Item]] = {}
    por_id = {item.id: item for item in carga.itens}
    for relacao in carga.relacoes:
        origem = por_id.get(relacao.item_origem)
        destino = por_id.get(relacao.item_destino)
        if origem is None or destino is None:
            continue
        vizinhos.setdefault((origem.id, relacao.tipo), []).append(destino)
        vizinhos.setdefault((destino.id, relacao.tipo), []).append(origem)
    return MappingProxyType({chave: tuple(itens) for chave, itens in vizinhos.items()})


def _disputa(triagem: _Triagem) -> _Triagem:
    """A mesma triagem, relatada como disputa: há candidato elegível, mas não para todos.

    Preserva a contabilidade e troca a lacuna, porque a causa é outra: ninguém perdeu candidato
    por etapa, por prática ou por apresentação anterior — os candidatos existem e são elegíveis,
    e o que falta é uma atribuição que dê um equivalente **distinto** a cada item praticado.
    """
    return _Triagem(
        elegiveis=(),
        qualificados=triagem.qualificados,
        excluidos_por_etapa=triagem.excluidos_por_etapa,
        excluidos_por_pratica=triagem.excluidos_por_pratica,
        excluidos_por_apresentacao=triagem.excluidos_por_apresentacao,
        disputado=True,
    )


def _atribuir_equivalentes(
    elegiveis_por_praticado: Sequence[tuple[str, tuple[Item, ...]]],
) -> tuple[Mapping[str, Item], tuple[str, ...]]:
    """Atribui a cada item praticado um equivalente **distinto**, e diz quem ficou sem.

    O problema não é a escolha de um candidato por praticado: é a escolha de candidatos
    **dois a dois distintos**, porque dois praticados que recebessem o mesmo equivalente
    produziriam um conjunto menor que o número de praticados — o desafio independente voltaria a
    ter tamanho diferente do praticado, que é exatamente o que R2.10 e a Propriedade 33 fecham.

    **Por que não guloso.** Percorrer os praticados e tomar o primeiro candidato livre falha num
    caso que tem solução: com ``E(p1) = {a, b}`` e ``E(p2) = {a}``, o guloso dá ``a`` a ``p1``,
    não sobra nada para ``p2`` e o pedido é recusado — embora ``p1 → b`` e ``p2 → a`` seja uma
    atribuição completa. Essa recusa não violaria a letra da Propriedade 33, que proíbe conjunto
    parcial e não exige sucesso; violaria o que a propriedade protege, porque abortaria um ciclo
    que o banco tinha itens para atender, e o aborto apareceria como lacuna de conteúdo que não
    existe.

    O que o algoritmo faz é um emparelhamento máximo em grafo bipartido por caminhos de
    aumento: ao encontrar um candidato já tomado, tenta reacomodar o dono em outro candidato
    antes de desistir. A reacomodação é o que resolve o caso acima. Com emparelhamento máximo, o
    pedido é recusado **somente** quando nenhuma atribuição completa existe, e aí a recusa é
    fato sobre o banco e não artefato da ordem de visita.

    O resultado é determinístico: os praticados são percorridos na ordem do pedido, e os
    candidatos na ordem de preferência da semente. O tamanho é o de um ciclo — poucos itens
    praticados e poucos candidatos cada —, de modo que o custo do emparelhamento máximo não tem
    relevância prática ao lado da recusa que ele evita.
    """
    candidatos_de = {praticado: elegiveis for praticado, elegiveis in elegiveis_por_praticado}
    dono_do_candidato: dict[str, str] = {}
    escolhido_de: dict[str, Item] = {}

    def aumentar(praticado: str, visitados: set[str]) -> bool:
        """Acomoda o praticado em algum candidato, reacomodando donos quando necessário."""
        for candidato in candidatos_de[praticado]:
            if candidato.id in visitados:
                continue
            visitados.add(candidato.id)
            dono = dono_do_candidato.get(candidato.id)
            if dono is None or aumentar(dono, visitados):
                dono_do_candidato[candidato.id] = praticado
                escolhido_de[praticado] = candidato
                return True
        return False

    nao_atribuidos: list[str] = []
    for praticado, _ in elegiveis_por_praticado:
        if not aumentar(praticado, set()):
            nao_atribuidos.append(praticado)
    return MappingProxyType(dict(escolhido_de)), tuple(nao_atribuidos)
