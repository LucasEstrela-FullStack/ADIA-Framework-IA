"""Conjunto declarado da estrutura do repositório e do `.gitignore` (R1.1, R1.8).

R1 não tem propriedade associada na matriz de rastreabilidade do design: §6.1 verifica
ambiente e estrutura por exemplos e conjuntos declarados, e as 37 propriedades são conjunto
fechado e numerado. Daí este arquivo viver em `conjuntos/`.

**O que se afirma, e por que não basta olhar o disco.** R1.1 exige os cinco diretórios
*rastreados pelo controle de versão*, não existentes na máquina de quem executa. A diferença
é inteira: `frontend/` e `ml/` ainda não têm código, e um diretório vazio é invisível ao git;
um diretório ignorado também. Nos dois casos quem clonar o repositório não recebe a
estrutura, e a reprodutibilidade que R1.1 pede não acontece. Por isso a pergunta é feita ao
git — `git ls-files` e `git check-ignore` —, nunca ao sistema de arquivos.

**O que conta como rastreado, aqui.** A união do índice com os arquivos não ignorados:
`git ls-files --cached --others --exclude-standard`. Exigir presença no índice afirmaria que
alguém já fez *commit*, o que é propriedade do histórico e não da estrutura — a suíte
passaria a reprovar numa árvore de trabalho correta só porque o *commit* ainda não saiu, e
voltaria a passar sem que nada da estrutura tivesse mudado. A união responde exatamente ao
que R1.1 quer saber: o git carrega esta estrutura, ou ela escapa dele? As duas formas de
escapar — vazio e ignorado — continuam reprovando, e é isso que importa.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[3]

# Os cinco diretórios nomeados em R1.1, na ordem do requisito.
_DIRETORIOS_EXIGIDOS = ("docs", "backend", "frontend", "ml", "data")

# R1.8, segunda metade: o `.gitignore` não pode excluir fixação de versão nem bloqueio. Os
# arquivos do frontend que faltam — `frontend/package.json` e `frontend/package-lock.json` —
# entram na tarefa 11.1; os da raiz já existem e são os que R1.2, R1.5 e R1.6 fixam.
_FIXACAO_E_BLOQUEIO = (
    ".gitignore",
    ".python-version",
    ".nvmrc",
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
)

# R1.8, primeira metade: as cinco categorias que têm de ficar fora do controle de versão.
# Os caminhos são representativos e não precisam existir no disco — `git check-ignore`
# responde sobre o padrão, não sobre o arquivo. Um por padrão relevante, para que a falha
# nomeie qual categoria vazou em vez de dizer apenas que o `.gitignore` mudou.
_DEVEM_FICAR_FORA: dict[str, tuple[str, ...]] = {
    "artefatos de build": (
        "backend/adia/__pycache__/cli.cpython-313.pyc",
        "dist/adia-0.1.0.tar.gz",
        "backend/adia.egg-info/PKG-INFO",
        "frontend/dist/index.js",
        "frontend/tsconfig.tsbuildinfo",
    ),
    "ambientes virtuais": (
        ".venv/Scripts/python.exe",
        "venv/bin/python",
    ),
    "pesos de modelos e índices vetoriais": (
        "ml/modelos/llama3.2-1b.gguf",
        "ml/checkpoints/dkt-epoca-10.pt",
        "ml/dkt/modelo.safetensors",
        "data/indice_rag/corpus.faiss",
    ),
    "bancos SQLite": (
        "data/adia.db",
        "data/adia.sqlite3",
        "backend/adia.db-wal",
    ),
    "exportações de dados de estudante": (
        "data/sessoes/coorte-a.csv",
        "data/estudantes/p01.json",
        "exportacoes/eventos.csv",
        "data/eventos.export.csv",
    ),
    # DO-19: diretório inteiro, `.gitkeep` incluído — a negação `!.gitkeep` não pode reabri-lo.
    "vínculo entre pseudônimo e identidade": (
        "data/identidade/vinculo.csv",
        "data/identidade/.gitkeep",
        "data/privado/vinculo-identidade.csv",
    ),
}


def _git(*argumentos: str) -> subprocess.CompletedProcess[str]:
    """Roda o git na raiz do repositório, com a saída decodificada em UTF-8.

    Os nomes de arquivo do projeto são acentuados; sem fixar a codificação, a saída chegaria
    ilegível nesta máquina (console em cp1252) e a mensagem de falha perderia o caminho que
    deveria apontar.
    """
    ambiente = dict(os.environ)
    ambiente["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        ["git", *argumentos],
        cwd=_RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
        check=False,
    )


def _carregados_pelo_git(prefixo: str) -> list[str]:
    """Arquivos sob `prefixo` que o git carrega: os do índice, mais os não ignorados."""
    resultado = _git("ls-files", "--cached", "--others", "--exclude-standard", "--", prefixo)
    assert resultado.returncode == 0, f"git ls-files falhou em {prefixo!r}: {resultado.stderr}"
    return [linha for linha in resultado.stdout.splitlines() if linha]


def _ignorados(caminhos: Sequence[str]) -> set[str]:
    """Subconjunto de `caminhos` que o `.gitignore` exclui.

    `--no-index` é deliberado: sem ele, o git responde "não ignorado" para qualquer caminho
    já presente no índice, e o veredito passaria a depender do que foi versionado em vez do
    que o `.gitignore` declara. R1.8 é sobre os padrões.
    """
    resultado = _git("check-ignore", "--no-index", "--", *caminhos)
    # 0 = pelo menos um ignorado; 1 = nenhum ignorado; acima disso é erro de verdade, que
    # não pode ser lido como "nada é ignorado".
    assert resultado.returncode in (0, 1), f"git check-ignore falhou: {resultado.stderr}"
    return {linha for linha in resultado.stdout.splitlines() if linha}


@pytest.mark.parametrize("diretorio", _DIRETORIOS_EXIGIDOS)
def test_os_cinco_diretorios_estao_rastreados(diretorio: str) -> None:
    """R1.1: o git carrega os cinco, inclusive os que ainda não têm código."""
    carregados = _carregados_pelo_git(diretorio)
    assert carregados, (
        f"`{diretorio}/` não é rastreado pelo controle de versão (R1.1). O git não carrega "
        "nenhum arquivo sob ele: ou o diretório está vazio — e diretório vazio não existe "
        "para o git —, ou tudo o que há dentro está ignorado. A convenção do projeto para "
        "diretório ainda sem código é um `.gitkeep` dentro dele."
    )


@pytest.mark.parametrize("diretorio", _DIRETORIOS_EXIGIDOS)
def test_os_cinco_diretorios_nao_estao_ignorados(diretorio: str) -> None:
    """R1.1: nenhum dos cinco pode entrar numa regra de exclusão."""
    assert not _ignorados([diretorio]), (
        f"`{diretorio}/` casa com um padrão do `.gitignore` (R1.1). Um diretório que existe "
        "no disco mas está ignorado não satisfaz o requisito: quem clonar o repositório não "
        "recebe a estrutura."
    )


@pytest.mark.parametrize("arquivo", _FIXACAO_E_BLOQUEIO)
def test_a_fixacao_de_versao_e_o_bloqueio_nao_estao_ignorados(arquivo: str) -> None:
    """R1.8: o `.gitignore` não exclui os arquivos de fixação de versão nem os de bloqueio."""
    assert (_RAIZ / arquivo).is_file(), f"`{arquivo}` não existe na raiz do repositório"
    assert not _ignorados([arquivo]), (
        f"`{arquivo}` está ignorado (R1.8). Fixação de versão e arquivo de bloqueio fora do "
        "controle de versão fazem a instalação a partir do repositório resolver versões "
        "diferentes das auditadas, que é exatamente o que R1.6 existe para impedir."
    )


@pytest.mark.parametrize("categoria", list(_DEVEM_FICAR_FORA))
def test_o_gitignore_mantem_fora_as_cinco_categorias(categoria: str) -> None:
    """R1.8: build, ambiente virtual, pesos de modelo, banco SQLite e exportação de dados."""
    esperados = _DEVEM_FICAR_FORA[categoria]
    escaparam = sorted(set(esperados) - _ignorados(esperados))
    assert not escaparam, (
        f"categoria `{categoria}` escapou do `.gitignore` (R1.8): {escaparam}. "
        "Com dado de estudante ou peso de modelo versionado, o repositório deixa de poder "
        "ser compartilhado — e, no caso do dado, o estrago não se desfaz com um `git rm`."
    )
