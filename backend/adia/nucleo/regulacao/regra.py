"""Regra de regulação do teto de suporte: precedência, saturação e evidência incompleta.

**Esqueleto da Fase 0.** Só a *assinatura* de ``decidir`` está aqui, e ela existe desde já
porque é ela que a camada 2 da verificação de isolamento afirma (design §6.4): o teste de
tipo negativo de ``backend/tests/conjuntos/tipos_fronteira.py`` precisa de um alvo real
para que o ``mypy`` tenha o que recusar. Sem o alvo, a proteção só entraria em vigor na
Fase 2, e a Fase 0 é justamente onde o design quer a fronteira armada.

O corpo é da **tarefa 4.1**, que acrescenta ``ConjuntoDeLimiares``, os campos de
``EntradaDeRegulacao`` e de ``DecisaoDeRegulacao`` listados em §3.4, a ordem de avaliação
com interrupção na primeira condição satisfeita, o arredondamento a quatro casas em
``Decimal`` e a saturação em L1 e L4. A **tarefa 4.2** acrescenta ``aplicar``.

Os campos ficam de fora deste esqueleto de propósito: eles dependem de ``Medida``,
``Nivel`` e ``Condicao``, que são da tarefa 3.1 em ``adia.tipos``. O que a fronteira de
tipo precisa é do nome do parâmetro de ``decidir`` ser um tipo **nominal** declarado no
lado puro — e isso já é verdade com as classes vazias abaixo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntradaDeRegulacao:
    """Evidência de desempenho e de confiança de um ciclo, na forma que a regra consome.

    Campos na tarefa 4.1 (§3.4): ``acerto_assistido``, ``acerto_independente``,
    ``confianca_media``, ``gap``, ``vies``, ``teto_anterior`` e ``limiares``.
    """


@dataclass(frozen=True)
class DecisaoDeRegulacao:
    """Decisão registrada, distinta do teto aplicado (R9.6, R9.7).

    Campos na tarefa 4.1 (§3.4): ``tipo``, ``ajuste_indicado``, ``teto_resultante``,
    ``saturacao``, ``onloading_ativado``, ``evidencia_incompleta`` e ``limiares_versao``.
    """


def decidir(entrada: EntradaDeRegulacao) -> DecisaoDeRegulacao:
    """Decide o ajuste do teto de suporte a partir da evidência do ciclo.

    A assinatura é a barreira: o parâmetro admite apenas um tipo declarado no lado puro,
    nunca ``Any`` nem ``object``. Afrouxá-la reprova o ``mypy`` pelo caminho descrito em
    ``backend/tests/conjuntos/tipos_fronteira.py``.
    """
    raise NotImplementedError("A regra de decisão é implementada na tarefa 4.1 (design §3.4).")
