"""Guarda do perfil do Hypothesis: o piso de §5.0 vale, e o desvio por teste não o rebaixa.

Os 37 arquivos de propriedade não declaram quantos exemplos rodam. O número vem do perfil
registrado e carregado em `backend/tests/conftest.py`, o que mantém o piso de §5.0 em um só
lugar — e cobra o preço de a configuração ficar longe de quem a usa. Estes dois testes são esse
preço pago: eles transformam "o perfil está carregado" em afirmação verificada, em vez de
intenção.

O modo de falha que eles existem para pegar é **silencioso**, e é por isso que valem o arquivo.
Perfil apagado, renomeado ou com o número rebaixado não quebra nada: as propriedades seguem
verdes, rodando menos exemplos, e o que se perde é a chance de encontrar o defeito. Nenhuma
propriedade reprova por isso, nenhum portão fica vermelho, e a perda não aparece em lugar nenhum
— exceto aqui.

O piso é escrito à mão abaixo, e **não** importado de `conftest.py`, de propósito: teste que lê
a mesma constante que verifica não verifica nada. 100 é o que §5.0 exige; a constante é como o
repositório tenta cumprir. São duas coisas, e o teste precisa das duas para comparar.

Sem linha `**Validates:**`, e isso é deliberado: o piso de exemplos é regra do design (§5.0 e
§6.2), não critério de aceitação de nenhum requisito. R29 e R30 são verificados pelas
propriedades, não por este arquivo — o que ele faz é garantir que elas rodem com o orçamento
que o design manda. Etiquetar um requisito aqui inflaria a matriz de rastreabilidade com uma
ligação que não existe.
"""

from __future__ import annotations

from typing import Final

from hypothesis import HealthCheck, settings

EXEMPLOS_EXIGIDOS: Final = 100
"""Piso de exemplos por propriedade, transcrito de §5.0: "no mínimo 100 exemplos"."""

EXEMPLOS_ADVERSARIOS: Final = 500
"""Orçamento de P22, P25, P26 e P28, transcrito de §5.0. Aqui serve de desvio de exemplo."""

SEM_PERFIL: Final = "nenhum perfil do Hypothesis carregado; ver o perfil em backend/tests/conftest.py"


def test_o_perfil_carregado_honra_o_piso_de_exemplos() -> None:
    """Toda propriedade que não declare o contrário roda com pelo menos 100 exemplos (§5.0).

    Afirmação sobre `settings.default`, que é o perfil **carregado** — e não sobre o perfil
    registrado. Registrar sem carregar é a forma mais fácil de o piso existir no repositório e
    não existir na execução, e a distinção não aparece em nenhum outro lugar da suíte.
    """
    carregado = settings.default

    assert carregado is not None, SEM_PERFIL
    assert carregado.max_examples >= EXEMPLOS_EXIGIDOS


def test_o_desvio_por_teste_preserva_o_orcamento_do_perfil() -> None:
    """`@settings(deadline=None)` numa propriedade não rebaixa o orçamento de exemplos.

    É a composição em que a convenção inteira se apoia: um `settings` criado depois do
    carregamento herda do perfil tudo o que não declara. Se a biblioteca passasse a herdar dos
    padrões de fábrica, cada desvio de §5.0 — `deadline=None` em P16, P17, P31 e P35, e os 500
    exemplos de P22, P25, P26 e P28 — levaria com ele o orçamento de exemplos, calado.

    Os dois desvios previstos são verificados juntos, porque a herança é a mesma nos dois
    sentidos: o que não é declarado vem do perfil, e o que é declarado prevalece.
    """
    carregado = settings.default
    com_prazo_livre = settings(deadline=None)
    com_orcamento_maior = settings(max_examples=EXEMPLOS_ADVERSARIOS)

    assert carregado is not None, SEM_PERFIL
    assert com_prazo_livre.max_examples == carregado.max_examples
    assert com_prazo_livre.deadline is None
    assert com_orcamento_maior.max_examples == EXEMPLOS_ADVERSARIOS
    assert com_orcamento_maior.deadline == carregado.deadline


def test_o_perfil_so_desliga_o_health_check_de_velocidade() -> None:
    """Só `too_slow` é suprimido; gerador que filtra demais ou gera grande demais ainda reprova."""
    carregado = settings.default
    assert carregado is not None, SEM_PERFIL
    assert list(carregado.suppress_health_check) == [HealthCheck.too_slow]
