"""Modelo do item e da relação entre itens: ``Item``, ``Relacao`` e ``TipoGabarito``.

Forma declarada em §3.1 do design. O item é o dado de entrada de **tudo** o que o protótipo
mede: TAI, TT, IIC, DSS e a decisão de regulação descendem, por caminhos diferentes, de
respostas a itens. É por isso que o perfil de um item não é informação descritiva — é
pré-condição de medida. Três campos ilustram o ponto, e cada um deles tem um erro de carga
próprio em ``erros.py``:

- ``tolerancia`` é obrigatória em gabarito numérico (R2.8). Sem ela o ``Motor_de_Correção``
  não tem critério de acerto e a TAI mede outra coisa;
- ``termos_essenciais`` é obrigatório em gabarito textual (R2.11). Sem ele o detector de
  vazamento da guarda não tem contra o que comparar, e guarda cega aprova vazamento;
- ``dicas`` tem exatamente os quatro níveis (R2.1). Nível faltando é dica indisponível em
  tempo de execução, o que degrada a assistência exatamente onde ela está sendo medida.

**Divisão de trabalho com o carregador.** O ``__post_init__`` abaixo recusa o item
inválido, mas não é ele quem produz as mensagens de R3.2: quando o item vem de arquivo, o
``carregador`` valida o mapa **antes** de construir o ``Item`` e devolve um erro que nomeia
arquivo, linha e campo. A verificação daqui existe para o outro caminho de entrada — item
construído em código, em teste ou em tarefa futura —, e é o que impede que a invariante
dependa de passar pelo carregador. Falha fechada nas duas portas (§7.2).

``Decimal`` e nunca ``float`` em ``tolerancia``: a tolerância entra em comparação de acerto
(R4.2), e ``0,05`` em binário de base 2 é ``0,05000000000000000277...``. A diferença decide
item de fronteira, e item de fronteira é o que separa acerto de erro na TAI.

Nota sobre ``hash``: ``Item`` é comparado por valor, mas **não** é hasheável, porque
``dicas`` é um ``Mapping``. Coleções de itens são indexadas por ``id``, que é único por
construção (R3.6) — ver ``Banco_de_Itens`` em §3.1.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum, unique
from typing import Final, Literal

from adia.tipos import Etapa, Nivel

# --------------------------------------------------------------------------- #
# Tipo de gabarito
# --------------------------------------------------------------------------- #


@unique
class TipoGabarito(StrEnum):
    """Natureza do gabarito, que determina **como** o acerto é julgado (§3.1, §3.2).

    - ``NUMERICO`` — julgado por tolerância declarada (R2.8, R4.2);
    - ``ALTERNATIVA`` — julgado por comparação exata com o gabarito e suas variações;
    - ``TEXTUAL`` — parte textual encaminhada a rubrica humana (R4.6, R13.2), e o único
      tipo que exige conjuntos de termos essenciais para a guarda (R2.11).

    ``StrEnum`` porque o valor é o texto gravado no arquivo de definição e lido de volta por
    ``tomllib``: o rótulo é formato de dado, não nome interno.
    """

    NUMERICO = "numerico"
    ALTERNATIVA = "alternativa"
    TEXTUAL = "textual"


# --------------------------------------------------------------------------- #
# Tipo de relação entre itens
# --------------------------------------------------------------------------- #

type TipoDeRelacao = Literal["equivalente", "transferencia"]
"""Natureza da relação declarada entre dois itens (§3.1).

- ``"equivalente"`` — isomorfismo estrutural: mesma habilidade, mesma dificuldade,
  identificador e enunciado distintos (R2.2). É o par que torna o desempenho assistido
  comparável ao independente;
- ``"transferencia"`` — mesma habilidade alvo em situação nova, **sem** isomorfismo. É o que
  alimenta a TT, e por isso R2.9 recusa que um item de transferência seja também marcado
  como isomorfo a um item praticado da mesma habilidade: isomorfia transforma transferência
  em repetição e infla a TT sem que nada pareça errado.
"""

EQUIVALENTE: Final[TipoDeRelacao] = "equivalente"
TRANSFERENCIA: Final[TipoDeRelacao] = "transferencia"

TIPOS_DE_RELACAO: Final = (EQUIVALENTE, TRANSFERENCIA)
"""Os dois tipos aceitos, na ordem em que a gramática os documenta."""


def tipo_de_relacao(valor: str) -> TipoDeRelacao | None:
    """Converte o texto lido do arquivo no tipo de relação, ou ``None`` se não for um deles.

    Existe para que a estreita de tipo aconteça em **um** lugar: comparar com uma coleção de
    textos não convence o verificador de que o resultado é um dos dois literais, e o atalho
    seria uma asserção de tipo — isto é, a promessa sem a verificação.
    """
    if valor == EQUIVALENTE:
        return EQUIVALENTE
    if valor == TRANSFERENCIA:
        return TRANSFERENCIA
    return None


# --------------------------------------------------------------------------- #
# Faixas declaradas
# --------------------------------------------------------------------------- #

DIFICULDADE_MINIMA: Final = 1
DIFICULDADE_MAXIMA: Final = 5
"""Faixa fechada da dificuldade: inteiro de 1 a 5, escala ordinal (R2.1, DO-01)."""


# --------------------------------------------------------------------------- #
# Item
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Item:
    """Um item do banco, com o perfil completo que a medida exige (§3.1, R2.1).

    Os campos opcionais não são opcionais por conveniência; cada ``None`` tem significado:
    ``tolerancia`` ausente só é legítima fora do gabarito numérico, ``unidade`` ausente
    significa grandeza adimensional, e ``incognita`` ausente significa item sem variável a
    proteger no detector algébrico da guarda.
    """

    id: str
    enunciado: str
    habilidade_alvo: str
    dificuldade: int
    tamanho_max_resposta: int
    tipo_gabarito: TipoGabarito
    gabarito: str
    tolerancia: Decimal | None
    unidade: str | None
    sinonimos_unidade: tuple[str, ...]
    variacoes_gabarito: tuple[str, ...]
    termos_essenciais: tuple[tuple[str, ...], ...]
    incognita: str | None
    etapas_permitidas: frozenset[Etapa]
    transferencia: bool
    dicas: Mapping[Nivel, str]

    def __post_init__(self) -> None:
        """Recusa item que não sustenta medida, qualquer que seja a porta de entrada.

        As mensagens aqui são curtas e **não citam conteúdo**: nenhum gabarito, variação,
        termo essencial, enunciado ou texto de dica aparece no texto da exceção, porque a
        exceção pode ser registrada em log e o log não é lugar de gabarito (§6 da gramática).
        """
        if not self.id.strip():
            raise ValueError("Item exige identificador não vazio (R2.1).")
        if not self.enunciado.strip():
            raise ValueError(f"o item {self.id!r} exige enunciado não vazio (R2.1).")
        if not self.habilidade_alvo.strip():
            raise ValueError(f"o item {self.id!r} exige habilidade alvo não vazia (R2.1).")
        if not DIFICULDADE_MINIMA <= self.dificuldade <= DIFICULDADE_MAXIMA:
            raise ValueError(
                f"a dificuldade do item {self.id!r} está fora da faixa de "
                f"{DIFICULDADE_MINIMA} a {DIFICULDADE_MAXIMA} (R2.1, DO-01): {self.dificuldade}."
            )
        if self.tamanho_max_resposta < 1:
            raise ValueError(
                f"o tamanho máximo de resposta do item {self.id!r} precisa ser positivo (R2.1): "
                f"{self.tamanho_max_resposta}."
            )
        if not self.gabarito.strip():
            raise ValueError(f"o item {self.id!r} exige gabarito não vazio (R2.1).")
        if not self.etapas_permitidas:
            raise ValueError(f"o item {self.id!r} exige conjunto não vazio de etapas permitidas (R2.4).")
        self._verificar_perfil()
        self._verificar_dicas()

    def _verificar_perfil(self) -> None:
        """Garante os campos que o tipo de gabarito torna obrigatórios (R2.8, R2.11)."""
        if self.tipo_gabarito is TipoGabarito.NUMERICO:
            if self.tolerancia is None:
                raise ValueError(f"o item numérico {self.id!r} exige tolerância declarada (R2.8).")
            if self.tolerancia < 0:
                raise ValueError(f"a tolerância do item {self.id!r} precisa ser não negativa (R2.8).")
        if self.tipo_gabarito is TipoGabarito.TEXTUAL and not self.termos_essenciais:
            raise ValueError(
                f"o item textual {self.id!r} exige ao menos um conjunto de termos essenciais (R2.11)."
            )
        if any(not conjunto for conjunto in self.termos_essenciais):
            raise ValueError(f"nenhum conjunto de termos essenciais do item {self.id!r} pode ser vazio (R2.11).")

    def _verificar_dicas(self) -> None:
        """Garante exatamente uma dica não vazia para cada nível de L1 a L4 (R2.1)."""
        faltantes = [nivel for nivel in Nivel if nivel not in self.dicas]
        if faltantes:
            nomes = ", ".join(nivel.name for nivel in faltantes)
            raise ValueError(f"o item {self.id!r} não declara dica pré-escrita para: {nomes} (R2.1).")
        vazias = [nivel.name for nivel in Nivel if not self.dicas[nivel].strip()]
        if vazias:
            raise ValueError(f"o item {self.id!r} declara dica vazia em: {', '.join(vazias)} (R2.1).")
        if len(self.dicas) != len(Nivel):
            raise ValueError(f"o item {self.id!r} declara dica em nível fora de L1 a L4 (R2.1).")

    @property
    def e_praticado(self) -> bool:
        """Se o item pode ser apresentado na prática assistida.

        É esta condição, e não um campo próprio, que aciona as exigências de pareamento de
        R2.2 e R2.6: item praticado precisa de equivalente e de transferência associados,
        porque é o desempenho nele que vai ser comparado com o desempenho sem IA.
        """
        return Etapa.PRATICA_ASSISTIDA in self.etapas_permitidas


# --------------------------------------------------------------------------- #
# Relação entre itens
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Relacao:
    """Associação declarada entre dois itens, escrita da origem para o destino (§3.1).

    A direção é informativa, **não** normativa, e a diferença é deliberada. Isomorfismo
    estrutural é simétrico por natureza; em ``"transferencia"``, quem é o item de
    transferência está declarado no próprio item, pelo campo ``transferencia``. Logo as
    verificações de R2.2, R2.6 e R2.9 examinam o par nas duas direções: exigir uma ordem de
    escrita criaria uma regra arbitrária cuja violação produziria a mensagem errada — "falta
    equivalente" para um par declarado de trás para frente.

    O que a gramática **não** admite é mais de uma relação sobre o mesmo par de itens, em
    qualquer direção: ``equivalente`` e ``transferencia`` sobre a mesma dupla são afirmações
    contraditórias, e qual valeria passaria a depender da ordem de leitura.
    """

    item_origem: str
    item_destino: str
    tipo: TipoDeRelacao

    def __post_init__(self) -> None:
        """Recusa relação de um item consigo mesmo, que não declara par nenhum."""
        if self.item_origem == self.item_destino:
            raise ValueError(f"a relação {self.tipo!r} do item {self.item_origem!r} aponta para ele mesmo.")
