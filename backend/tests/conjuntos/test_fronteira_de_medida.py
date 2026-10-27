"""Conjunto declarado da fronteira de tipo entre valor medido e ausência de base (R11.7).

`tipos_medida.py`, ao lado, é o arquivo que o `mypy` verifica; este é o que o `pytest`
executa. A separação é a mesma de `tipos_fronteira.py` e `test_contratos_de_import.py`, e
pela mesma razão: uma execução de `uv run pytest` isolada não roda `mypy` nenhum, e sem a
verificação abaixo a barreira de R11.7 seria, naquele caminho, um arquivo que ninguém
executa.

O que está sob verificação não é o valor de uma métrica: é a **impossibilidade** de uma
métrica indisponível se passar por zero. Essa impossibilidade é a pré-condição da
Propriedade 13 — se o tipo admitisse a confusão, nenhuma propriedade sobre propagação de
indisponibilidade valeria em todos os caminhos, só nos que alguém lembrou de tratar. O
painel é onde a diferença aparece: "errou tudo" e "não há base para afirmar" são afirmações
distintas, e zero no lugar da segunda é número inventado (§7.8).

**Validates: Requirements 11.7**
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[3]
_TIPOS_MEDIDA = _RAIZ / "backend" / "tests" / "conjuntos" / "tipos_medida.py"

# As operações proibidas, pelo código de erro que cada uma produz. A lista é declarada aqui
# em vez de lida do arquivo porque apagar uma função de `tipos_medida.py` deixaria o `mypy`
# verde sobre menos barreira — exatamente como `lint-imports` fica verde sobre zero
# contratos. Acrescentar operação proibida exige acrescentá-la aqui.
_IGNORES_DECLARADOS = (
    "type: ignore[operator]",  # somar e comparar com limiar
    "type: ignore[arg-type]",  # converter em número, e zero posando de ausência
    "type: ignore[attr-defined]",  # quantizar a ausência (R9.12)
    "type: ignore[return-value]",  # devolver a ausência onde se promete número
    "type: ignore[union-attr]",  # ler `motivo` sem distinguir os casos
)


def _executar(argumentos: list[str]) -> subprocess.CompletedProcess[str]:
    """Roda o comando na raiz do repositório, com a saída decodificada em UTF-8.

    As mensagens do projeto são em pt-BR e os nomes do domínio são acentuados; sem fixar a
    codificação, a saída chegaria ilegível no console desta máquina (cp1252) e a mensagem de
    falha perderia justamente a linha que o `mypy` apontou.
    """
    ambiente = dict(os.environ)
    ambiente["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        argumentos,
        cwd=_RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
        check=False,
    )


def test_indisponivel_continua_recusado_como_numero_pelo_mypy() -> None:
    """A barreira de R11.7 continua de pé, nos dois sentidos que a sustentam.

    Verde significa duas coisas ao mesmo tempo: cada operação de `tipos_medida.py`
    **ainda** é um erro de tipo, e cada `type: ignore` que a silencia **ainda** é
    necessário. `warn_unused_ignores`, que vem com `--strict`, é o que liga a segunda
    metade: no dia em que `Indisponivel` ganhar `__add__`, `__float__`, ordenação ou herança
    de `Decimal`, os erros desaparecem, os `ignore` ficam sem uso e este teste fica
    vermelho. A correção, nesse dia, é em `adia/tipos.py` — não neste arquivo.
    """
    caminho = _TIPOS_MEDIDA.relative_to(_RAIZ).as_posix()
    resultado = _executar([sys.executable, "-m", "mypy", "--strict", caminho])

    assert resultado.returncode == 0, (
        f"a fronteira entre valor medido e ausência de base mudou de comportamento em {caminho}.\n"
        "Aviso de `unused-ignore` significa que `Indisponivel` passou a se comportar como número, "
        "ou que `Medida` deixou de obrigar a distinguir os dois casos — e aí a métrica indisponível "
        "voltou a ser representável como zero (R11.7, Propriedade 13). Erro de tipo não coberto "
        "significa que um `type: ignore` foi removido ou trocou de código.\n"
        f"código de saída {resultado.returncode}\n"
        f"--- saída ---\n{resultado.stdout}\n"
        f"--- erros ---\n{resultado.stderr}"
    )


@pytest.mark.parametrize("ignore", _IGNORES_DECLARADOS)
def test_as_operacoes_proibidas_continuam_declaradas(ignore: str) -> None:
    """Operação apagada de `tipos_medida.py` deixaria o `mypy` verde sobre menos barreira."""
    assert _TIPOS_MEDIDA.is_file(), f"{_TIPOS_MEDIDA} desapareceu"
    assert ignore in _TIPOS_MEDIDA.read_text(encoding="utf-8"), (
        f"`{ignore}` saiu de {_TIPOS_MEDIDA.name}. A verificação do mypy continuaria verde, "
        "porque sobrou menos coisa para recusar — e é assim que uma barreira de tipo se "
        "dissolve sem nenhum teste ficar vermelho."
    )


def test_o_modulo_de_tipo_negativo_nao_e_coletavel_pelo_pytest() -> None:
    """O nome sem prefixo `test_` é deliberado: o arquivo é verificado, não executado."""
    assert not _TIPOS_MEDIDA.name.startswith("test_"), (
        "renomear tipos_medida.py com prefixo `test_` faria o pytest coletá-lo, e a coleta "
        "importa o módulo — as expressões silenciadas por `type: ignore` continuariam sem "
        "executar, mas o arquivo passaria a parecer um teste de execução, que é justamente o "
        "que ele não é: não há o que executar numa afirmação de impossibilidade."
    )
