"""Tipos de valor compartilhados: ``Nivel``, ``Etapa``, ``Condicao``, ``Medida`` e afins.

Camada mais baixa do contrato de camadas de ``backend/.importlinter`` (design §6.4): nada
aqui pode importar outro módulo de ``adia``, e este módulo não importa nada além de
``dataclasses``, ``decimal``, ``enum`` e ``typing``. O contrato ``nucleo-puro`` proíbe
``time``, ``uuid``, ``secrets``, ``socket`` e a camada de IA dentro de ``adia.nucleo``;
aqui a restrição é mais forte por construção — não há relógio, não há identificador, não há
aleatoriedade, não há E/S. Um tipo de valor que precisasse de qualquer uma dessas coisas
estaria no lugar errado.

O conteúdo segue §3.0 do design. Duas garantias do módulo valem mais que a lista de nomes,
e são elas que a tarefa 3.1 existe para fixar:

1. **Métrica indisponível não é representável como zero** (R11.7). ``Indisponivel`` e
   ``Decimal`` são **tipos diferentes**, não valores diferentes do mesmo tipo, e ``Medida``
   é a união dos dois. Quem recebe uma ``Medida`` não consegue somar, comparar, formatar
   como número nem passar adiante sem antes distinguir os dois casos — o ``mypy --strict``
   recusa. É essa barreira que torna a Propriedade 13 verdadeira; a convenção de uso, por
   si, não tornaria. A diferença que isso preserva no painel é a diferença entre "errou
   tudo" e "não há base para afirmar".
2. **``POSTESTE`` é rótulo, não etapa com itens próprios** (R12.3). O pós-teste é o
   conjunto de itens sem IA do terceiro ciclo. ``conjunto_de_respostas`` é o **único** lugar
   onde o rótulo se resolve, e é o que impede que o mesmo conjunto de respostas passe a ter
   duas fontes de verdade.

Por que ``Decimal`` e nunca ``float``: a regra de regulação compara ``acerto_independente``,
``gap`` e ``viés`` com limiares, e R9.12 exige arredondamento a quatro casas com
``ROUND_HALF_UP`` **antes** da comparação, com igualdade no limiar tendo significado
declarado. Binário de base 2 em comparação com limiar decimal é defeito latente: um
``0,25`` que chega como ``0,2500000000000000138`` dispara *onloading* onde R9.12 diz que não
dispara. O tipo fecha essa porta na origem (§3.4, R11.12, R11.13).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum, StrEnum, unique
from typing import Final, TypeIs

# --------------------------------------------------------------------------- #
# Teto de assistência
# --------------------------------------------------------------------------- #


@unique
class Nivel(IntEnum):
    """Nível de assistência da IA, em **ordem crescente de diretividade** (R6.1).

    - ``L1`` — pergunta metacognitiva. **Menor** diretividade: devolve a tarefa cognitiva
      ao estudante sem oferecer conteúdo.
    - ``L2`` — pista conceitual: nomeia o conceito envolvido.
    - ``L3`` — orientação procedural: indica o procedimento, sem executá-lo.
    - ``L4`` — exemplo resolvido análogo. **Maior** diretividade.

    ``IntEnum``, e não ``StrEnum``, porque a ordenação é usada como ordenação: *descer o
    teto* é caminhar na direção de ``L1``, *subir* é caminhar na direção de ``L4``, e a
    saturação de R9.6 e R9.7 é o comportamento nas duas bordas — em ``L1`` com indicação de
    descer, e em ``L4`` com indicação de subir, o teto fica onde está e a decisão é
    preservada no registro. Comparar níveis é operação de domínio, não detalhe de
    representação: ``nivel_pedido > teto_vigente`` é literalmente a recusa de R6.4.

    O inteiro também é a base do denominador do DSS, que R11.4 fixa em ``4 × itens
    praticados`` — isto é, ``Nivel.L4``.
    """

    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4


# --------------------------------------------------------------------------- #
# Etapas do CognitiveLoop
# --------------------------------------------------------------------------- #


@unique
class Etapa(StrEnum):
    """Etapa do CognitiveLoop dentro de uma sessão experimental (R12.1, R2.4).

    A **ordem de declaração não é a ordem do protocolo**, e contar com isso seria erro: a
    sequência é linha de base, três repetições de prática assistida, desafio independente e
    gatilho de *fading*, projeto STEAM e teste de retenção (R12.1), e ela pertence à máquina
    de estados do ``Gestor_de_Sessão`` (§3.3), não a esta enumeração. Enumeração é conjunto
    de rótulos; sequência com repetição é outra coisa.

    ``POSTESTE`` é o caso que exige leitura atenta. Ele **não** é uma etapa executável com
    itens próprios: é o rótulo que R12.3 manda aplicar ao conjunto de itens sem IA do
    terceiro ciclo. Existe aqui por duas razões concretas, e nenhuma delas é "ser mais uma
    etapa do percurso":

    - R2.4 exige que cada item declare um conjunto não vazio de etapas permitidas **entre
      elas o pós-teste**, e o ``Banco_de_Itens`` precisa de um rótulo para isso;
    - R8.6 e a Propriedade 21 enumeram o pós-teste entre as etapas sem IA, e
      ``ETAPAS_SEM_IA`` é o conjunto que elas usam.

    O que **não** acontece: nenhum evento do ``Registro_de_Eventos`` carrega
    ``Etapa.POSTESTE``. O evento registra a etapa de fato executada —
    ``DESAFIO_INDEPENDENTE`` com ``ciclo = 3`` —, e o rótulo se resolve em
    ``conjunto_de_respostas``. Gravar as mesmas respostas sob dois rótulos de etapa criaria
    as duas fontes de verdade que R12.3 descarta.
    """

    LINHA_DE_BASE = "linha_de_base"
    PRATICA_ASSISTIDA = "pratica_assistida"
    DESAFIO_INDEPENDENTE = "desafio_independente"
    GATILHO_FADING = "gatilho_fading"
    PROJETO_STEAM = "projeto_steam"
    POSTESTE = "posteste"
    TESTE_RETENCAO = "teste_retencao"


ETAPAS_SEM_IA: Final = frozenset(
    {
        Etapa.LINHA_DE_BASE,
        Etapa.DESAFIO_INDEPENDENTE,
        Etapa.POSTESTE,
        Etapa.TESTE_RETENCAO,
    }
)
"""Etapas em que nenhuma assistência da IA é oferecida (R8.6, R2.7, R23.4).

Este é o conjunto que sustenta três afirmações distintas, e por isso ele é declarado uma
única vez:

- a Propriedade 21: nenhuma chamada ao serviço de inferência local é emitida nestas etapas;
- R8.6 e R30.4: proficiência — TAI, TT e Retenção — sai **exclusivamente** de respostas
  registradas aqui, o que é o filtro de ``do_escopo`` em §3.5;
- R2.7: elegibilidade de item exclui o que o participante já viu em **qualquer** etapa sem
  IA, de modo que nenhum item do desafio independente reapareça no pós-teste ou na retenção.

A prática assistida, o gatilho de *fading* e o projeto STEAM ficam fora: os dois primeiros
por oferecerem dica dentro do teto, e o projeto STEAM por admitir apoio da IA em parte da
tarefa (R13). Incluir ``POSTESTE`` é o que faz o conjunto corresponder, literalmente, à
enumeração de R8.6 e da Propriedade 21; como nenhum evento carrega essa etapa, a inclusão
não muda o resultado de nenhum filtro — muda a legibilidade da correspondência com o
requisito.
"""


# --------------------------------------------------------------------------- #
# Condição experimental e decisão de regulação
# --------------------------------------------------------------------------- #


@unique
class Condicao(StrEnum):
    """Condição experimental atribuída à sessão (R14.1 a R14.4).

    - ``A`` — suporte constante: teto fixo em ``L4``, a regra de regulação **não** ajusta o
      teto, e a decisão que ela produziria é registrada como sombra (R14.2, R26.6).
    - ``B`` — ADIA regulado: a decisão da regra é aplicada ao teto do ciclo seguinte.
    - ``C`` — *fading* fixo: o teto desce por protocolo pré-determinado, independentemente
      do desempenho, e a decisão da regra também é registrada como sombra (R14.4).

    O registro sombra em A e C é o que permite comparar o que a regra teria decidido com o
    que o protocolo fez — e é por isso que a condição é dado da sessão, não configuração de
    ambiente.
    """

    A = "A"
    B = "B"
    C = "C"


@unique
class TipoDecisao(StrEnum):
    """Decisão de regulação produzida ao fim de um ciclo (R9.11, Propriedade 1).

    - ``FADING`` — reduzir o teto de assistência: o desempenho autônomo sustenta menos ajuda.
    - ``ONLOADING`` — exigir justificativa escrita antes da dica, pelo *gap* entre
      desempenho assistido e independente (R10.1).
    - ``ESCALONAR`` — ampliar o teto: o desempenho independente ficou abaixo do limiar.
    - ``MANTER`` — nenhum ajuste, inclusive quando a evidência está incompleta (R9.13).

    ``decidir`` produz **exatamente uma** dessas, mesmo quando mais de uma condição da regra
    é satisfeita ao mesmo tempo; a precedência declarada em §3.4 é o que resolve. A decisão
    registrada e o teto aplicado são campos distintos de ``DecisaoDeRegulacao``, e essa
    separação é o que permite a saturação de R9.6 e R9.7 existir sem contradição: em ``L1``
    com indicação de descer, a decisão continua ``FADING`` e o teto continua ``L1``.
    """

    FADING = "fading"
    ONLOADING = "onloading"
    ESCALONAR = "escalonar"
    MANTER = "manter"


# --------------------------------------------------------------------------- #
# Escopo de cálculo e a resolução do rótulo de pós-teste
# --------------------------------------------------------------------------- #


@unique
class EscopoDeCalculo(StrEnum):
    """Unidade pela qual TAI, TT e ICM são calculados e **identificados** (R11.1 a R11.3).

    Os escopos são a linha de base, o desafio independente de cada ciclo — qualificado pelo
    número do ciclo —, o pós-teste e o teste de retenção. Cada valor de métrica carrega o
    escopo que o produziu, porque uma TAI sem escopo não é comparável com nada.

    ``POSTESTE`` e ``DESAFIO_INDEPENDENTE`` com ``ciclo = 3`` apontam para o **mesmo**
    conjunto de respostas, com identificação distinta nas métricas (R12.3). A distinção não
    é redundância: a Retenção de R11.6 é ``TAI(teste_retencao) ÷ TAI(posteste)``, e o
    numerador e o denominador precisam de nomes estáveis que não dependam de saber que o
    protocolo tem três ciclos. ``conjunto_de_respostas`` é onde a equivalência vive.
    """

    LINHA_DE_BASE = "linha_de_base"
    DESAFIO_INDEPENDENTE = "desafio_independente"
    POSTESTE = "posteste"
    TESTE_RETENCAO = "teste_retencao"


CICLO_DO_POSTESTE: Final = 3
"""Ciclo cujo conjunto de itens sem IA recebe o rótulo de pós-teste (R12.1, R12.3).

O protocolo tem três ciclos, e é o terceiro que fecha a sessão antes do projeto STEAM. O
número aparece aqui uma única vez, e tudo que precisa dele passa por
``conjunto_de_respostas``.
"""


@dataclass(frozen=True)
class ConjuntoDeRespostas:
    """Par ``(etapa executada, ciclo)`` que identifica univocamente um grupo de respostas.

    É a **forma canônica** de nomear "de onde vieram estas respostas", e existe para que o
    rótulo de pós-teste tenha onde se resolver. Dois escopos distintos que apontem para o
    mesmo conjunto produzem este mesmo valor, e a igualdade de ``dataclass`` torna isso
    verificável em uma linha:

        conjunto_de_respostas(EscopoDeCalculo.POSTESTE)
        == conjunto_de_respostas(EscopoDeCalculo.DESAFIO_INDEPENDENTE, 3)

    ``etapa`` é sempre uma etapa **executada**, nunca ``Etapa.POSTESTE``: o rótulo já foi
    resolvido quando o valor existe. ``ciclo`` é ``None`` nas etapas que ocorrem uma única
    vez na sessão.
    """

    etapa: Etapa
    ciclo: int | None

    def __post_init__(self) -> None:
        """Recusa ciclo não positivo, que não corresponde a nenhuma repetição do protocolo."""
        if self.ciclo is not None and self.ciclo < 1:
            raise ValueError(f"ciclo deve ser inteiro positivo; recebido {self.ciclo!r}")
        if self.etapa is Etapa.POSTESTE:
            raise ValueError(
                "Etapa.POSTESTE é rótulo, não etapa executada (R12.3). A forma canônica do "
                "pós-teste é conjunto_de_respostas(EscopoDeCalculo.POSTESTE)."
            )


def conjunto_de_respostas(escopo: EscopoDeCalculo, ciclo: int | None = None) -> ConjuntoDeRespostas:
    """Resolve um escopo de cálculo no conjunto de respostas que o alimenta (R12.3).

    Único lugar do código em que o rótulo de pós-teste se resolve. ``POSTESTE`` e
    ``DESAFIO_INDEPENDENTE`` com ``ciclo = 3`` devolvem valores **iguais**, porque são o
    mesmo conjunto de respostas visto por dois nomes; os escopos seguem distintos nas
    métricas, que é o que R11.1 e R11.6 pedem.

    Para perguntar se uma execução em curso é o pós-teste, compare a forma canônica em vez
    de reescrever a regra::

        ConjuntoDeRespostas(etapa_executada, ciclo) == conjunto_de_respostas(EscopoDeCalculo.POSTESTE)

    Levanta ``ValueError`` quando o par escopo/ciclo não descreve nada: desafio independente
    sem ciclo, ciclo informado em escopo que ocorre uma única vez, ou pós-teste atribuído a
    um ciclo que não é o terceiro.
    """
    match escopo:
        case EscopoDeCalculo.LINHA_DE_BASE:
            _recusar_ciclo(escopo, ciclo)
            return ConjuntoDeRespostas(Etapa.LINHA_DE_BASE, None)
        case EscopoDeCalculo.DESAFIO_INDEPENDENTE:
            if ciclo is None:
                raise ValueError(
                    "o escopo de desafio independente é qualificado pelo ciclo (R11.1); informe o ciclo"
                )
            return ConjuntoDeRespostas(Etapa.DESAFIO_INDEPENDENTE, ciclo)
        case EscopoDeCalculo.POSTESTE:
            if ciclo is not None and ciclo != CICLO_DO_POSTESTE:
                raise ValueError(
                    f"o pós-teste é o conjunto sem IA do ciclo {CICLO_DO_POSTESTE} (R12.3); "
                    f"recebido ciclo {ciclo!r}"
                )
            return ConjuntoDeRespostas(Etapa.DESAFIO_INDEPENDENTE, CICLO_DO_POSTESTE)
        case EscopoDeCalculo.TESTE_RETENCAO:
            _recusar_ciclo(escopo, ciclo)
            return ConjuntoDeRespostas(Etapa.TESTE_RETENCAO, None)


def _recusar_ciclo(escopo: EscopoDeCalculo, ciclo: int | None) -> None:
    """Garante que escopos de ocorrência única não venham qualificados por ciclo."""
    if ciclo is not None:
        raise ValueError(f"o escopo {escopo.value!r} ocorre uma única vez na sessão e não admite ciclo")


# --------------------------------------------------------------------------- #
# Medida: valor numérico ou ausência declarada de base para afirmar
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Indisponivel:
    """Ausência de base para afirmar um valor, com o motivo que a produziu (R11.7).

    Não é um número ruim nem um número faltando: é a afirmação de que **não há** número.
    Denominador zero, escopo sem nenhuma resposta registrada e métrica de entrada
    indisponível produzem este valor, e a indisponibilidade **propaga** — IIC, viés, *gap* e
    Retenção derivados de entrada indisponível são indisponíveis (Propriedade 13).

    Três coisas que esta classe deliberadamente **não** tem, porque cada uma delas
    reabriria a confusão com zero:

    - não herda de ``Decimal``, ``int`` nem de número algum, então nenhuma aritmética a
      aceita;
    - não define ``__float__``, ``__int__``, ``__add__`` nem ordenação (``order`` fica em
      ``False``), então somar, comparar ou converter é erro de tipo, apontado pelo
      ``mypy --strict`` antes de qualquer execução;
    - não tem valor de verdade: ``__bool__`` levanta ``TypeError``, o que transforma
      ``medida or Decimal(0)`` e ``valor if medida else 0`` — as duas formas pelas quais
      zero se substitui a indisponível sem o verificador de tipo notar — em falha alta e
      imediata, no espírito de falha fechada de D3.

    O ``motivo`` é obrigatório e não vazio. A restrição não é estética: ela é o espelho do
    ``CHECK ((valor IS NULL) <> (indisponivel_motivo IS NULL))`` e do
    ``CHECK (length(indisponivel_motivo) > 0)`` do esquema de §4.3, e é o que R11.7 chama de
    registrar o motivo. Indisponível sem motivo seria zero com outro nome: o painel teria de
    exibir uma lacuna sem explicação, e §7.8 exige o motivo na tela.
    """

    motivo: str

    def __post_init__(self) -> None:
        """Recusa motivo vazio: R11.7 exige registrar **o motivo**, não apenas a ausência."""
        if not self.motivo.strip():
            raise ValueError(
                "Indisponivel exige motivo não vazio (R11.7): sem o motivo, a indisponibilidade "
                "chega ao painel como lacuna inexplicada e §7.8 não tem o que mostrar."
            )

    def __bool__(self) -> bool:
        """Sempre levanta: indisponível não tem valor de verdade (R11.7).

        O alvo é concreto. ``Decimal("0")`` é falso e ``Indisponivel`` seria verdadeiro, de
        modo que ``if medida:`` inverteria o significado dos dois casos sem que nenhum
        verificador reclamasse — uma TAI de exatamente zero, que é desempenho medido e
        legítimo, seria tratada como ausência, e a ausência como valor. Levantar aqui mata
        esse caminho na primeira execução em vez de na leitura do painel.
        """
        raise TypeError(
            "Indisponivel não tem valor de verdade (R11.7): `if medida:` confunde ausência de base "
            "com valor zero. Distinga os casos com `e_disponivel(medida)` ou `isinstance(...)`."
        )


type Medida = Decimal | Indisponivel
"""Valor de métrica: ou um número exato, ou a ausência declarada de base para afirmá-lo.

Nenhuma métrica indisponível vira zero (R11.7). A união é a barreira: quem recebe uma
``Medida`` não consegue somar, dividir, comparar com limiar, formatar como número nem passar
adiante sem antes distinguir os dois casos, porque o ``mypy --strict`` recusa a operação
sobre o lado ``Indisponivel``. A obrigação é do **tipo**, não da disciplina de quem escreve
o código — e é isso que a Propriedade 13 depende para poder ser verdadeira.

``Decimal`` e nunca ``float``: R11.12 e R11.13 exigem armazenamento e comparação sem
arredondamento, e R9.12 exige quantização a quatro casas com ``ROUND_HALF_UP`` antes de
comparar com limiar. Ver o cabeçalho do módulo.

Zero continua sendo um valor perfeitamente válido: ``Decimal("0")`` é uma ``Medida``
disponível e significa "mediu zero". O que o tipo impede é o contrário — que a ausência de
base para medir chegue ao painel ou ao CSV **vestida** de zero.
"""


def e_disponivel(medida: Medida) -> TypeIs[Decimal]:
    """Se a medida tem valor numérico, estreitando o tipo nos **dois** ramos.

    ``TypeIs`` é o detalhe que importa: no ramo verdadeiro a medida é ``Decimal``, e no ramo
    falso é ``Indisponivel`` — com acesso a ``motivo`` sem conversão nem asserção::

        if e_disponivel(tai):
            linha = para_tela(tai)
        else:
            linha = f"indisponível: {tai.motivo}"

    Existe para que a distinção obrigatória tenha **uma** forma idiomática, em vez de
    ``isinstance`` espalhado — e para que o ramo do ``else`` seja tipado, que é o que impede
    o atalho de ignorar o caso ausente.
    """
    return isinstance(medida, Decimal)
