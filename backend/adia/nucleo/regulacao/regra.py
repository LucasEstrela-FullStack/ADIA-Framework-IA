"""Regra de regulação do teto de suporte: precedência, saturação e evidência incompleta.

A regra é a do ``README.md`` (seção *Regra de regulação*), avaliada nesta ordem, com
interrupção na primeira condição satisfeita:

1. ``gap > 0,25`` — ``ONLOADING``: teto mantido, explicação exigida antes da dica;
2. ``independente >= 0,8`` e ``|viés| <= 0,2`` — ``FADING``: teto desce um nível;
3. ``independente < 0,4`` — ``ESCALONAR``: teto sobe um nível;
4. qualquer outro caso — ``MANTER``.

Independente da decisão, ``viés > 0,25`` (excesso de confiança) liga a exigência de
justificativa da resposta. Toda medida é quantizada a quatro casas com ``ROUND_HALF_UP``
antes de comparar com limiar (R9.12), e medida indisponível decide ``MANTER`` com a
evidência incompleta registrada (R9.13): ausência de base nunca vira zero.

A decisão registrada e o teto aplicado são campos distintos: em ``L1`` com ``FADING`` (ou em
``L4`` com ``ESCALONAR``) a decisão é preservada e o teto satura (R9.6, R9.7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from adia.tipos import Condicao, Indisponivel, Medida, Nivel, TipoDecisao, e_disponivel

_QUATRO_CASAS = Decimal("0.0001")


@dataclass(frozen=True)
class ConjuntoDeLimiares:
    """Limiares da regra, editáveis pelo professor no painel (README)."""

    independente_fading: Decimal = Decimal("0.8")
    gap_maximo: Decimal = Decimal("0.25")
    vies_maximo_fading: Decimal = Decimal("0.2")
    independente_escalonar: Decimal = Decimal("0.4")
    vies_justificativa: Decimal = Decimal("0.25")
    versao: str = "readme-v1"


@dataclass(frozen=True)
class EntradaDeRegulacao:
    """Evidência de desempenho e de confiança de um ciclo, na forma que a regra consome.

    As três medidas são proporções entre 0 e 1; ``confianca_media`` já vem normalizada (a
    escala de 0 a 10 dividida por 10).
    """

    acerto_assistido: Medida
    acerto_independente: Medida
    confianca_media: Medida
    teto_anterior: Nivel
    limiares: ConjuntoDeLimiares = field(default_factory=ConjuntoDeLimiares)


@dataclass(frozen=True)
class DecisaoDeRegulacao:
    """Decisão registrada, distinta do teto aplicado (R9.6, R9.7)."""

    tipo: TipoDecisao
    teto_resultante: Nivel
    saturacao: bool
    onloading_ativado: bool
    justificativa_exigida: bool
    evidencia_incompleta: str | None
    gap: Medida
    vies: Medida
    limiares_versao: str


def _quantizar(valor: Decimal) -> Decimal:
    return valor.quantize(_QUATRO_CASAS, rounding=ROUND_HALF_UP)


def _deslocar(teto: Nivel, passo: int) -> tuple[Nivel, bool]:
    """Teto deslocado de ``passo`` níveis, e se a borda impediu o deslocamento."""
    alvo = int(teto) + passo
    if alvo < Nivel.L1 or alvo > Nivel.L4:
        return teto, True
    return Nivel(alvo), False


def decidir(entrada: EntradaDeRegulacao) -> DecisaoDeRegulacao:
    """Decide o ajuste do teto de suporte a partir da evidência do ciclo.

    A assinatura é a barreira: o parâmetro admite apenas um tipo declarado no lado puro,
    nunca ``Any`` nem ``object``. Afrouxá-la reprova o ``mypy`` pelo caminho descrito em
    ``backend/tests/conjuntos/tipos_fronteira.py``.
    """
    limiares = entrada.limiares
    assistido, independente, confianca = (
        entrada.acerto_assistido,
        entrada.acerto_independente,
        entrada.confianca_media,
    )
    if not (e_disponivel(assistido) and e_disponivel(independente) and e_disponivel(confianca)):
        motivos = [
            m.motivo for m in (assistido, independente, confianca) if isinstance(m, Indisponivel)
        ]
        ausente = Indisponivel("; ".join(motivos))
        return DecisaoDeRegulacao(
            tipo=TipoDecisao.MANTER,
            teto_resultante=entrada.teto_anterior,
            saturacao=False,
            onloading_ativado=False,
            justificativa_exigida=False,
            evidencia_incompleta=ausente.motivo,
            gap=ausente,
            vies=ausente,
            limiares_versao=limiares.versao,
        )

    independente = _quantizar(independente)
    gap = _quantizar(assistido - independente)
    vies = _quantizar(confianca - independente)

    if gap > limiares.gap_maximo:
        tipo, passo = TipoDecisao.ONLOADING, 0
    elif independente >= limiares.independente_fading and abs(vies) <= limiares.vies_maximo_fading:
        tipo, passo = TipoDecisao.FADING, -1
    elif independente < limiares.independente_escalonar:
        tipo, passo = TipoDecisao.ESCALONAR, 1
    else:
        tipo, passo = TipoDecisao.MANTER, 0

    teto, saturou = _deslocar(entrada.teto_anterior, passo)
    return DecisaoDeRegulacao(
        tipo=tipo,
        teto_resultante=teto,
        saturacao=saturou,
        onloading_ativado=tipo is TipoDecisao.ONLOADING,
        justificativa_exigida=vies > limiares.vies_justificativa,
        evidencia_incompleta=None,
        gap=gap,
        vies=vies,
        limiares_versao=limiares.versao,
    )


def aplicar(condicao: Condicao, decisao: DecisaoDeRegulacao, teto_anterior: Nivel) -> Nivel:
    """Teto do ciclo seguinte conforme a condição experimental (R14.1 a R14.4).

    Em A e C a decisão é só sombra: A fica em ``L4`` e C desce um nível por ciclo.
    """
    if condicao is Condicao.A:
        return Nivel.L4
    if condicao is Condicao.C:
        return _deslocar(teto_anterior, -1)[0]
    return decisao.teto_resultante
