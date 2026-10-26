"""Teste de tipo negativo da fronteira entre a camada de IA e o núcleo puro (R30.3).

Camada 2 das três que verificam o isolamento da IA (design §6.4). Este módulo é
**verificado pelo mypy e não é executado pelo pytest** — daí a ausência do prefixo
``test_`` no nome do arquivo, que é deliberada e não um descuido de nomenclatura.

O que ele afirma não é um comportamento: é uma **impossibilidade**. A chamada abaixo é hoje
um erro de tipo, silenciado por ``type: ignore[arg-type]``. Com ``warn_unused_ignores``, que
``--strict`` liga, o mypy reprova quando um ``type: ignore`` deixa de ser necessário. Então,
no dia em que a fronteira afrouxar — ``decidir`` ganhar um parâmetro ``Any`` ou ``object``,
``EntradaDeRegulacao`` virar protocolo estrutural, ``RespostaDoModelo`` ganhar
compatibilidade com ela —, o erro desaparece, o ``ignore`` fica sem uso e o ``mypy`` falha.
Verde aqui significa "a travessia continua impossível de escrever".

Um teste comum verifica o que acontece; aqui importa o que não pode nem ser escrito. É por
isso que a asserção não cabe em ``assert``: não há o que executar.

O ``import`` sob ``TYPE_CHECKING`` fecha o outro lado do problema. Sem ele, um arquivo de
teste do lado puro carregaria ``adia.ia`` em tempo de execução só para que este módulo
existisse — e a camada 3 (``ollama_proibido``) passaria a conviver com um import que ela
existe para tornar desnecessário.

Verificado por ``uv run mypy --strict backend/tests/conjuntos/tipos_fronteira.py``, e
também sob ``pytest`` por ``test_contratos_de_import.py``, porque o passo 2 do portão
(``scripts/verificar.ps1``) cobre apenas ``backend/adia``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adia.ia.cliente_ollama import RespostaDoModelo
    from adia.nucleo.regulacao.regra import decidir

    def _fronteira(resposta: RespostaDoModelo) -> None:
        """A travessia proibida, escrita uma única vez para que o mypy a recuse."""
        decidir(resposta)  # type: ignore[arg-type]
