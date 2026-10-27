"""Teste de tipo negativo de ``Medida``: indisponível não é número e não é zero (R11.7).

Mesmo mecanismo do ``tipos_fronteira.py`` ao lado, aplicado a outra fronteira. Este módulo
é **verificado pelo mypy e não é executado pelo pytest** — daí a ausência do prefixo
``test_`` no nome do arquivo, que é deliberada. Quem o executa é
``test_fronteira_de_medida.py``, por ``mypy --strict`` em processo separado.

O que ele afirma não é um comportamento: é uma **impossibilidade**. Cada expressão abaixo é
hoje um erro de tipo, silenciado por um ``type: ignore`` com o código exato do erro. Com
``warn_unused_ignores``, que ``--strict`` liga, o mypy reprova quando um ``type: ignore``
deixa de ser necessário. Então, no dia em que ``Indisponivel`` ganhar ``__add__``,
``__float__``, ordenação, herança de ``Decimal`` ou qualquer outra forma de se passar por
número — e no dia em que ``Medida`` deixar de ser união e voltar a ser ``Decimal`` com zero
no lugar da ausência —, o erro desaparece, o ``ignore`` fica sem uso e o portão fica
vermelho. Verde aqui significa "continua impossível de escrever".

Por que isso precisa de um arquivo próprio em vez de um ``assert``: a garantia de R11.7 é
sobre o que o código **não pode expressar**. Um teste de execução só alcança o caminho que
alguém escreveu; a barreira de tipo alcança o caminho que ninguém escreveu ainda. É a
diferença entre "nesta função a indisponibilidade é tratada" e "não existe função em que
ela possa ser esquecida".

Sem ``TYPE_CHECKING``, ao contrário do módulo vizinho, e a diferença é de propósito. Lá o
guarda existe para que um arquivo do lado puro não carregue ``adia.ia`` em tempo de
execução. Aqui o importado é ``adia.tipos``, a camada mais baixa, sem efeito colateral
algum: nenhuma das funções abaixo é chamada por ninguém, então nenhuma expressão silenciada
executa.
"""

from __future__ import annotations

from decimal import Decimal

from adia.tipos import Indisponivel, Medida, e_disponivel

# --------------------------------------------------------------------------- #
# Indisponível não é número
# --------------------------------------------------------------------------- #


def _somar_indisponivel(ausente: Indisponivel) -> Decimal:
    """Aritmética sobre a ausência: o caminho por onde um zero implícito entraria."""
    return ausente + Decimal("1")  # type: ignore[operator]


def _comparar_indisponivel_com_limiar(ausente: Indisponivel) -> bool:
    """Comparação com limiar é o uso que a regra de regulação faz de uma medida (§3.4)."""
    return ausente < Decimal("0.5")  # type: ignore[operator]


def _converter_indisponivel_em_numero(ausente: Indisponivel) -> float:
    """Conversão numérica: a forma mais curta de transformar ausência em `0.0`."""
    return float(ausente)  # type: ignore[arg-type]


def _quantizar_indisponivel(ausente: Indisponivel) -> None:
    """R9.12 quantiza a quatro casas antes de comparar; a ausência não tem o que quantizar.

    O resultado vai para uma variável anotada em vez de ser devolvido porque o método
    inexistente tem tipo ``Any``, e devolvê-lo acusaria ``no-any-return`` por cima do erro
    que esta função existe para fixar. A anotação mantém o alvo em ``attr-defined``, que é o
    erro que desaparece se ``Indisponivel`` virar número.
    """
    _quantizada: Decimal = ausente.quantize(Decimal("0.0001"))  # type: ignore[attr-defined]


def _indisponivel_onde_se_espera_numero(ausente: Indisponivel) -> Decimal:
    """A ausência não satisfaz uma assinatura que promete número."""
    return ausente  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Zero não é indisponível
# --------------------------------------------------------------------------- #


def _motivo_da_ausencia(ausente: Indisponivel) -> str:
    """Alvo legítimo: quem exige a ausência exige o motivo dela (R11.7, §7.8)."""
    return ausente.motivo


def _zero_posando_de_ausencia() -> str:
    """A simetria que fecha R11.7: zero também não pode ocupar o lugar da ausência."""
    return _motivo_da_ausencia(Decimal("0"))  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Quem consome `Medida` é obrigado a distinguir os dois casos
# --------------------------------------------------------------------------- #


def _usar_medida_sem_distinguir(medida: Medida) -> Decimal:
    """Sem estreitar o tipo, nem a aritmética da métrica derivada é escrevível (P13)."""
    return medida * Decimal("2")  # type: ignore[operator]


def _ler_motivo_sem_distinguir(medida: Medida) -> str:
    """E o caminho inverso também não: ``motivo`` não existe no lado disponível."""
    return medida.motivo  # type: ignore[union-attr]


def _devolver_medida_como_numero(medida: Medida) -> Decimal:
    """Repassar a medida adiante como número exige o ramo da ausência, sempre."""
    return medida  # type: ignore[return-value]


def _distinguir_e_o_unico_caminho(medida: Medida) -> str:
    """O contraponto que torna o resto legível: com `e_disponivel`, os dois ramos tipam.

    Nenhum ``type: ignore`` aqui, e é esse contraste que mostra que a barreira não é
    intransponível — é só obrigatória. ``TypeIs`` estreita para ``Decimal`` no ramo
    verdadeiro e para ``Indisponivel`` no falso, de modo que ``motivo`` é alcançável sem
    conversão nem asserção.
    """
    if e_disponivel(medida):
        return str(medida.quantize(Decimal("0.01")))
    return f"indisponível: {medida.motivo}"
