"""Camadas 1 e 2 do isolamento da IA, executadas também sob `pytest` (R30.3, R7.2, R21.5).

As duas camadas estáticas do design §6.4 já têm um portão: `scripts/verificar.ps1` roda
`lint-imports` no passo 3 e `mypy --strict` no passo 2. Este arquivo existe porque o portão
não é o único jeito de rodar a suíte, e as duas camadas têm cada uma o seu furo quando a
execução é só `uv run pytest`:

- **Camada 1.** O próprio `backend/.importlinter` registra a intenção no cabeçalho: os
  contratos são invocados daqui "para que uma execução de `pytest` isolada não perca a
  verificação".
- **Camada 2.** O passo 2 do portão verifica `backend/adia` — e só. O teste de tipo
  negativo mora em `backend/tests/conjuntos/tipos_fronteira.py`, **fora** desse caminho,
  então nem o portão nem `uv run pytest` o alcançariam por conta própria. Sem a verificação
  abaixo, a camada 2 seria um arquivo que ninguém executa.

Os dois primeiros testes separam duas falhas que não se confundem: contrato **removido** do
arquivo de configuração e contrato **quebrado** pelo código. Um `lint-imports` verde sobre
zero contratos também é verde, e é por isso que o conjunto declarado dos cinco é afirmado à
parte.
"""

from __future__ import annotations

import configparser
import os
import subprocess
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[3]
_CONFIG_CONTRATOS = _RAIZ / "backend" / ".importlinter"
_TIPOS_FRONTEIRA = _RAIZ / "backend" / "tests" / "conjuntos" / "tipos_fronteira.py"

_PREFIXO_DE_SECAO = "importlinter:contract:"

# Os cinco contratos de §6.4, pelo identificador de seção — não pelo `name`, que é texto de
# relatório e pode ser reescrito sem consequência. Acrescentar um contrato ao arquivo exige
# acrescentá-lo aqui: é o que torna a lista um conjunto *declarado* em vez de um espelho do
# que houver no disco.
_CONTRATOS_DECLARADOS = frozenset(
    {
        "camadas",
        "nucleo-puro",
        "guarda-pura",
        "roteador-nao-alcanca-a-regra",
        "torch-fora-do-servidor",
        "api-sem-cli",
    }
)

# `importlinter.cli.lint_imports` é a função que o console script `lint-imports` chama, e a
# própria documentação dela a descreve como a entrada principal do verificador. Rodar por
# `sys.executable` em vez de procurar o executável no `PATH` garante que o `import-linter`
# verificado é o do mesmo ambiente que executa o teste; e um processo separado mantém fora
# do processo do `pytest` dois efeitos colaterais da função — a inserção do diretório
# corrente em `sys.path` e a reconfiguração do `logging`.
_CODIGO_LINT = (
    "import sys;"
    " from importlinter.cli import lint_imports;"
    " sys.exit(lint_imports(config_filename='backend/.importlinter', no_logo=True))"
)


def _executar(argumentos: list[str]) -> subprocess.CompletedProcess[str]:
    """Roda o comando na raiz do repositório, com a saída decodificada em UTF-8.

    Os nomes dos contratos são acentuados e as mensagens do projeto são em pt-BR; sem fixar
    a codificação, a saída chegaria ilegível no console desta máquina (cp1252) e a mensagem
    de falha perderia justamente o nome do contrato que quebrou.
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


def _relatorio(resultado: subprocess.CompletedProcess[str]) -> str:
    return (
        f"código de saída {resultado.returncode}\n"
        f"--- saída ---\n{resultado.stdout}\n"
        f"--- erros ---\n{resultado.stderr}"
    )


def test_os_contratos_continuam_declarados() -> None:
    """Contrato apagado do arquivo deixaria o `lint-imports` verde sem verificar nada."""
    configuracao = configparser.ConfigParser()
    lidos = configuracao.read(_CONFIG_CONTRATOS, encoding="utf-8")
    assert lidos, f"não foi possível ler {_CONFIG_CONTRATOS}"

    encontrados = frozenset(
        secao.removeprefix(_PREFIXO_DE_SECAO)
        for secao in configuracao.sections()
        if secao.startswith(_PREFIXO_DE_SECAO)
    )

    assert encontrados == _CONTRATOS_DECLARADOS, (
        "o conjunto de contratos de backend/.importlinter mudou. "
        f"Ausentes: {sorted(_CONTRATOS_DECLARADOS - encontrados)}. "
        f"Não declarados neste teste: {sorted(encontrados - _CONTRATOS_DECLARADOS)}"
    )


def test_os_contratos_de_import_continuam_intactos() -> None:
    """Camada 1: o grafo de imports respeita as camadas e as proibições de §6.4."""
    resultado = _executar([sys.executable, "-c", _CODIGO_LINT])

    quebrados = [linha.strip() for linha in resultado.stdout.splitlines() if linha.strip().endswith("BROKEN")]
    resumo = [linha.strip() for linha in resultado.stdout.splitlines() if linha.strip().startswith("Contracts:")]

    assert resultado.returncode == 0, (
        "contrato de import quebrado.\n"
        f"Quebrados: {quebrados or '(nenhum nomeado; a falha pode ser de configuração)'}\n"
        f"Resumo: {resumo}\n{_relatorio(resultado)}"
    )


def test_o_teste_de_tipo_negativo_continua_recusado_pelo_mypy() -> None:
    """Camada 2: a travessia de `tipos_fronteira.py` continua impossível de escrever.

    Verde significa duas coisas ao mesmo tempo: a chamada `decidir(resposta)` **ainda** é um
    erro de tipo, e o `type: ignore[arg-type]` que a silencia **ainda** é necessário. Afrouxar
    a fronteira derruba a segunda metade, porque `warn_unused_ignores` vem com `--strict`.
    """
    caminho = _TIPOS_FRONTEIRA.relative_to(_RAIZ).as_posix()
    resultado = _executar([sys.executable, "-m", "mypy", "--strict", caminho])

    assert resultado.returncode == 0, (
        f"a fronteira de tipo mudou de comportamento em {caminho}.\n"
        "Erro de `arg-type` ainda presente significa que o `type: ignore` foi removido; "
        "aviso de `unused-ignore` significa que a fronteira afrouxou e a travessia passou a "
        "ser escrevível — nesse caso a correção é na assinatura, não neste arquivo.\n"
        f"{_relatorio(resultado)}"
    )


@pytest.mark.parametrize("marca", ["TYPE_CHECKING", "type: ignore[arg-type]"])
def test_o_modulo_de_tipo_negativo_preserva_o_mecanismo(marca: str) -> None:
    """As duas marcas que fazem o arquivo funcionar, afirmadas contra remoção silenciosa."""
    assert _TIPOS_FRONTEIRA.is_file(), f"{_TIPOS_FRONTEIRA} desapareceu"
    assert marca in _TIPOS_FRONTEIRA.read_text(encoding="utf-8"), (
        f"`{marca}` saiu de {_TIPOS_FRONTEIRA.name}. Sem o `type: ignore`, o mypy acusa a "
        "chamada e o portão fica vermelho por motivo errado; sem o `TYPE_CHECKING`, um "
        "arquivo do lado puro passa a carregar `adia.ia` em tempo de execução."
    )


def test_o_modulo_de_tipo_negativo_nao_e_coletavel_pelo_pytest() -> None:
    """O nome sem prefixo `test_` é deliberado: o arquivo é verificado, não executado."""
    assert not _TIPOS_FRONTEIRA.name.startswith("test_"), (
        "renomear tipos_fronteira.py com prefixo `test_` faria o pytest coletá-lo, e a "
        "coleta importa o módulo — o `if TYPE_CHECKING` ficaria sem efeito e o lado puro "
        "passaria a carregar `adia.ia` só para que a asserção de tipo existisse."
    )
