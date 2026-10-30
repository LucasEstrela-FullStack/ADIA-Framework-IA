"""Triagem de dependências que exigem rede — conjunto declarado (R24.8, R24.9).

O que este arquivo é: o **portão** da triagem registrada em `docs/decisoes.md`
como DO-17. R24.9 manda rejeitar a dependência que exija acesso à rede em tempo
de execução e registrar a exclusão; uma triagem que vivesse só no documento
seria uma triagem que ninguém reexecuta, e a primeira dependência nova entraria
em silêncio. Aqui ela é código que roda no passo 6 do portão local (§6.1).

As três classes que a triagem separa, porque confundi-las torna a verificação
inútil:

1. **Rede na preparação** é aceita. Baixar distribuição do PyPI, baixar o
   binário do navegador uma única vez — acontece antes da coleta, com a máquina
   deliberadamente conectada, e não durante a sessão de um participante. Não é
   objeto de R24.8, que fala de requisição emitida pelo protótipo em execução.
2. **Rede em execução para laço local** é aceita e é o projeto: `httpx` falando
   com o Ollama em `127.0.0.1:11434`, `uvicorn` escutando em `127.0.0.1:8000`
   (D11).
3. **Rede em execução para destino externo** é o que se rejeita: telemetria,
   verificação de atualização, download de peso ou de conjunto de dados sob
   demanda, busca de recurso remoto.

O método que produziu a tabela `TRIAGEM` está em DO-17 e foi, em resumo: o fecho
completo de `uv.lock` (não a lista de dependências diretas, porque o risco mora
no que entra de carona), varrido em três passadas sobre o código instalado —
importação de módulo de rede (`socket`, `ssl`, `urllib`, `http.client`,
`requests`, `aiohttp`), literal de URL com hospedeiro externo, e leitura de
variável de ambiente de telemetria ou de download. Cada achado foi lido no
código fonte antes de receber veredito. Nenhum veredito vem de reputação do
pacote.

Um veredito `RESTRITA` não é concessão: é a constatação de que a distribuição
tem uma sub-API que alcança destino externo e que o resto dela não alcança.
`scikit-learn` é o caso típico — `TfidfVectorizer` e `LogisticRegression`, que é
o que §3.8 usa, não tocam a rede; `sklearn.datasets.fetch_openml` baixa de
`openml.org`. Rejeitar a distribuição inteira custaria o classificador roteador
e não compraria nada que a proibição da sub-API não compre. Por isso cada
entrada `RESTRITA` carrega os trechos proibidos, e
`test_o_codigo_do_projeto_nao_usa_api_restrita` varre `backend/` e `ml/` em
busca deles: é essa varredura que transforma a restrição em barreira.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pytest

from adia import caminhos, cli

# --------------------------------------------------------------------------- #
# Localização dos arquivos que a triagem lê
# --------------------------------------------------------------------------- #

_RAIZ = caminhos.encontrar_raiz(Path(__file__).resolve().parent)
assert _RAIZ is not None, "a triagem precisa da raiz do projeto para ler uv.lock e pyproject.toml"
RAIZ: Final = _RAIZ

ARQUIVO_BLOQUEIO: Final = RAIZ / "uv.lock"
ARQUIVO_PROJETO: Final = RAIZ / "pyproject.toml"
ARQUIVO_DECISOES: Final = RAIZ / "docs" / "decisoes.md"

#: Lançadores que precisam declarar as variáveis de ambiente de DO-17. O portão
#: local e o servidor da API são os dois processos que carregam `fastapi`.
LANCADORES: Final = ("scripts/verificar.ps1", "scripts/dev-backend.ps1")

#: Diretórios de código próprio varridos em busca de uso de API restrita.
ARVORES_DE_CODIGO: Final = ("backend", "ml")

#: Nome da distribuição do próprio projeto em `uv.lock`, que não se tria.
PROJETO: Final = "adia"

# --------------------------------------------------------------------------- #
# A política: o que conta como destino aceitável
# --------------------------------------------------------------------------- #

#: Os únicos destinos que R24.8 admite. `0.0.0.0` e `::` ficam **fora** de
#: propósito: são endereços de escuta em todas as interfaces, não de laço local,
#: e é exatamente o engano que D11 manda a aplicação recusar na partida.
DESTINOS_ACEITOS: Final = frozenset({"127.0.0.1", "localhost", "::1"})

SEM_REDE: Final = "sem-rede"
LACO_LOCAL: Final = "laco-local"
RESTRITA: Final = "restrita"
VEREDITOS: Final = frozenset({SEM_REDE, LACO_LOCAL, RESTRITA})


@dataclass(frozen=True)
class Veredito:
    """Resultado da triagem de uma distribuição do fecho de `uv.lock`."""

    classe: str
    razao: str
    #: Trechos cuja presença no código do projeto reabriria o caminho externo.
    #: Só faz sentido com `classe == RESTRITA`, e a consistência é verificada.
    proibidos: tuple[str, ...] = field(default_factory=tuple)


def _sem_rede(razao: str) -> Veredito:
    return Veredito(SEM_REDE, razao)


def _laco_local(razao: str) -> Veredito:
    return Veredito(LACO_LOCAL, razao)


def _restrita(razao: str, *proibidos: str) -> Veredito:
    return Veredito(RESTRITA, razao, proibidos)


# --------------------------------------------------------------------------- #
# A tabela de triagem: um veredito por distribuição do fecho
# --------------------------------------------------------------------------- #
#
# A cobertura é verificada nos dois sentidos. Distribuição no bloqueio sem
# entrada aqui reprova o portão — é assim que a dependência nova é obrigada a
# passar pela triagem em vez de entrar calada. Entrada aqui sem distribuição no
# bloqueio também reprova, para que a tabela não apodreça com pacote que já saiu.

TRIAGEM: Final[dict[str, Veredito]] = {
    # ---- a pilha que fala rede, e só com o laço local -------------------- #
    "httpx": _laco_local(
        "cliente do Serviço_de_Inferência_Local (§3.12). O transporte é injetável e "
        "recusa destino fora do laço local; é a dependência que R24.8 existe para delimitar"
    ),
    "httpcore": _laco_local("transporte do `httpx`: é quem abre o socket que o `httpx` usa"),
    "anyio": _laco_local("primitivas de socket assíncrono usadas pelo `httpcore` e pelo `starlette`"),
    "uvicorn": _laco_local("servidor da API_ADIA, com bind fixo em 127.0.0.1:8000 (D11)"),
    "import-linter": _laco_local(
        "`importlinter/ui/server.py` sobe um visualizador de grafo com bind em `localhost` e porta "
        "efêmera. O portão usa `lint-imports --config`, que não toca essa interface"
    ),
    # ---- aceitas com restrição de uso ------------------------------------ #
    "fastapi": _restrita(
        "0.162 traz configuração automática de OpenTelemetry que exportaria rastros, métricas e "
        "registros por OTLP para `OTEL_EXPORTER_OTLP_ENDPOINT`. Três portas a separam de nós, "
        "todas fechadas: `auto_configure` é falso sem `FASTAPI_OTEL_AUTO_CONFIGURE=true`, não há "
        "ponto de exportação configurado, e o exportador exige o extra `fastapi[opentelemetry]`, "
        "que a declaração de dependência não pede. O caminho de serviço em si não abre conexão",
        "FASTAPI_OTEL_AUTO_CONFIGURE",
        "auto_configure",
        "OTEL_EXPORTER_OTLP",
    ),
    "scikit-learn": _restrita(
        "`sklearn.datasets` baixa conjuntos de exemplo de `openml.org`, `ndownloader.figshare.com` "
        "e `archive.ics.uci.edu` por `urlopen` e `urlretrieve`. O uso do projeto é "
        "`TfidfVectorizer` mais `LogisticRegression` (§3.8), que não tocam a rede",
        "sklearn.datasets",
        "from sklearn import datasets",
        "fetch_openml",
        "fetch_covtype",
        "fetch_lfw",
        "fetch_20newsgroups",
        "fetch_california_housing",
        "fetch_olivetti_faces",
        "fetch_rcv1",
        "fetch_kddcup99",
        "fetch_species_distributions",
    ),
    "numpy": _restrita(
        "`numpy.lib.DataSource` aceita caminho `http://` e o abre com `urlopen`. A aritmética das "
        "métricas e a busca exaustiva de D13 não passam por lá",
        "numpy.lib.DataSource",
        "np.DataSource",
        "numpy.lib._datasource",
    ),
    "scipy": _restrita(
        "`scipy.datasets` baixa conjuntos de exemplo. O caminho está estruturalmente morto aqui: "
        "ele exige `pooch`, que a triagem mantém fora do bloqueio",
        "scipy.datasets",
        "from scipy import datasets",
    ),
    "hypothesis": _restrita(
        "`GitHubArtifactDatabase` busca o banco de exemplos em `api.github.com` com `GITHUB_TOKEN`. "
        "O padrão é `DirectoryBasedExampleDatabase`, que grava em `.hypothesis/` no disco local",
        "GitHubArtifactDatabase",
    ),
    "pytest": _restrita(
        "`--pastebin` publica o relatório da sessão em `https://bpa.st`. Num protótipo que processa "
        "produção textual de estudantes, essa opção é vazamento de dado, não só saída de rede",
        "--pastebin",
    ),
    "torch": _restrita(
        "`torch.hub` baixa pesos pré-treinados sob demanda. O Modelo_DKT é uma LSTM treinada do "
        "zero em CPU (R28.1, R28.2), sem peso de terceiro; e o contrato `torch-fora-do-servidor` "
        "já mantém `torch` fora do processo da API",
        "torch.hub",
        "load_state_dict_from_url",
        "pretrained=True",
    ),
    "opentelemetry-api": _restrita(
        "entra de carona com o `fastapi` 0.162. É apenas a interface: sem `opentelemetry-sdk` e sem "
        "exportador, os provedores são implementações nulas e nada sai do processo. A exclusão dos "
        "dois pacotes que o ativariam está em `EXCLUIDAS`",
        "opentelemetry.sdk",
        "opentelemetry.exporter",
    ),
    "fsspec": _restrita(
        "entra com o `torch`. Os sistemas de arquivo remotos exigem `aiohttp` ou `requests`, que a "
        "triagem mantém fora do bloqueio; sobra o acesso a arquivo local",
        "fsspec.implementations.http",
    ),
    # ---- sem rede em tempo de execução ----------------------------------- #
    "annotated-doc": _sem_rede("anotação de tipo"),
    "annotated-types": _sem_rede("anotação de tipo"),
    "certifi": _sem_rede("apenas o pacote de certificados raiz: um arquivo de dados, sem código de rede"),
    "click": _sem_rede(
        "linha de comando do `uvicorn` e do `import-linter`. `click.launch` entrega uma URL ao "
        "sistema operacional por `os.startfile`, sem abrir socket no processo, e nada no projeto a chama"
    ),
    "cloudpickle": _sem_rede("serialização de função para o paralelismo do `joblib`"),
    "colorama": _sem_rede("cor no console do Windows"),
    "coverage": _sem_rede("mede cobertura; o único uso de `socket` é `gethostname()` para rótulo do relatório"),
    "filelock": _sem_rede("trava de arquivo entre processos"),
    "grimp": _sem_rede("constrói o grafo de imports lendo o código fonte do disco"),
    "h11": _sem_rede("máquina de estados de HTTP/1.1 sem entrada e saída própria; quem abre o socket é o `httpcore`"),
    "idna": _sem_rede("codificação de nome de domínio internacionalizado; transforma texto, não resolve nome"),
    "iniconfig": _sem_rede("leitura de arquivo de configuração"),
    "jinja2": _sem_rede("gabaritos de texto, usados pelo `torch` na geração de código do compilador"),
    "joblib": _sem_rede(
        "serializa o classificador roteador e paraleliza em processos locais. O `urllib` que importa é "
        "`urllib.parse.quote`, para escapar nome de função em caminho de cache"
    ),
    "librt": _sem_rede("extensão binária de apoio do `mypy`: base64, strings, tempo e vetores"),
    "markdown-it-py": _sem_rede("analisador de Markdown do `rich`"),
    "markupsafe": _sem_rede("escape de HTML para o `jinja2`"),
    "mdurl": _sem_rede("normalização de URL como texto, sem requisição"),
    "mpmath": _sem_rede("aritmética de precisão arbitrária para o `sympy`"),
    "mypy": _sem_rede(
        "verificador de tipo. `mypy/ipc.py` usa socket só no modo daemon e, em Windows, por cano "
        "nomeado do `_winapi`; o portão invoca `mypy --strict`, sem daemon"
    ),
    "mypy-extensions": _sem_rede("anotação de tipo"),
    "narwhals": _sem_rede("camada de compatibilidade entre bibliotecas de quadro de dados, usada pelo `scikit-learn`"),
    "networkx": _sem_rede("grafos em memória, usados pelo `torch` no rastreamento do grafo de computação"),
    "packaging": _sem_rede("compara versão e analisa marcador de ambiente; o `urllib` que importa é de análise de URL"),
    "pathspec": _sem_rede("casamento de padrão de caminho no estilo do `.gitignore`"),
    "pluggy": _sem_rede("sistema de ganchos do `pytest`"),
    "pydantic": _sem_rede("validação e serialização de esquema"),
    "pydantic-core": _sem_rede("núcleo de validação do `pydantic`, em Rust"),
    "pygments": _sem_rede("realce de sintaxe; os `urllib` que aparecem são nomes embutidos de léxicos"),
    "pytest-cov": _sem_rede("integra `coverage` ao `pytest`; o `socket` é `gethostname()` para rótulo"),
    "rich": _sem_rede("formatação de texto no terminal, para o relatório do `import-linter`"),
    "ruff": _sem_rede("analisador estático em binário único, sem verificação de versão nova"),
    "setuptools": _sem_rede("infraestrutura de construção, exigida pelo `torch` em tempo de importação"),
    "sortedcontainers": _sem_rede("estrutura de dados ordenada do `hypothesis`"),
    "starlette": _sem_rede(
        "camada ASGI sob o `fastapi`: traduz requisição e resposta, sem abrir conexão. Quem fala "
        "com o socket é o `uvicorn`"
    ),
    "sympy": _sem_rede("álgebra simbólica, usada pelo `torch` nas formas dinâmicas"),
    "threadpoolctl": _sem_rede("limita o número de linhas de execução das bibliotecas nativas de álgebra"),
    "tomli-w": _sem_rede("escrita do TOML canônico dos itens (D12)"),
    "typing-extensions": _sem_rede("anotação de tipo"),
    "typing-inspection": _sem_rede("introspecção de anotação de tipo"),
}

# --------------------------------------------------------------------------- #
# As exclusões: o que a triagem mantém fora do bloqueio (R24.9)
# --------------------------------------------------------------------------- #
#
# É aqui que R24.9 se cumpre. Rejeitar uma dependência, num projeto bloqueado por
# `uv.lock`, significa que o nome dela não aparece no fecho — e o portão falha no
# dia em que aparecer, com o nome e a razão na mensagem. As entradas não são
# hipóteses: cada uma é o pacote que ativaria um caminho de rede externo que a
# varredura encontrou de fato no código instalado, ou a alternativa de projeto
# que o design descartou e que teria trazido esse caminho.

EXCLUIDAS: Final[dict[str, str]] = {
    "opentelemetry-sdk": (
        "completa o `opentelemetry-api` com provedores reais e é a metade que falta para o "
        "`fastapi` exportar telemetria. Sem ela, os provedores são nulos"
    ),
    "opentelemetry-exporter-otlp-proto-http": (
        "exportador OTLP sobre HTTP que o `fastapi[opentelemetry]` instala. É o pacote que "
        "efetivamente emitiria a requisição para o coletor"
    ),
    "opentelemetry-exporter-otlp": "metapacote dos exportadores OTLP, pela mesma razão",
    "opentelemetry-instrumentation": (
        "instrumentação automática de bibliotecas; arrasta SDK e exportador por dependência"
    ),
    "pooch": (
        "baixa e põe em cache os conjuntos de exemplo de `scipy.datasets`. Mantê-la fora deixa "
        "`scipy.datasets` em `ImportError`, que é a forma mais forte de proibição"
    ),
    "requests": (
        "segundo cliente HTTP, sem o transporte restrito ao laço local que o `httpx` do projeto "
        "recebe (§3.12). Também habilitaria o sistema de arquivo remoto do `fsspec`. Já é módulo "
        "proibido nos contratos `nucleo-puro` e `guarda-pura`"
    ),
    "aiohttp": "cliente HTTP assíncrono; habilitaria `fsspec.implementations.http`, pela mesma razão",
    "huggingface-hub": (
        "consulta o hub por padrão para resolver e baixar modelo. Os embeddings vêm do `bge-m3` "
        "servido pelo Ollama no laço local (D13, DO-11), e os pesos do DKT são treinados aqui"
    ),
    "transformers": "arrasta `huggingface-hub` e baixa configuração e pesos sob demanda",
    "sentence-transformers": (
        "arrasta `huggingface-hub` e baixaria o modelo de embeddings, duplicando fora do laço "
        "local o que DO-11 obtém por `POST /api/embed` do Ollama"
    ),
    "torchvision": "baixa pesos pré-treinados por `torch.hub`; o Modelo_DKT não usa visão nem peso de terceiro",
    "torchaudio": "mesma razão do `torchvision`",
    "ollama": (
        "cliente oficial em Python do Ollama. Não é rejeitado por alcançar destino externo — ele "
        "fala com o laço local — e sim porque embutiria o cliente em vez de deixá-lo injetável: os "
        "contratos `nucleo-puro` e `guarda-pura` o proíbem ao lado do `httpx` justamente para que a "
        "fixture `ollama_proibido` tenha um único transporte a substituir (§3.12, §6.4)"
    ),
}

# --------------------------------------------------------------------------- #
# As variáveis de ambiente que desligam telemetria e download automático
# --------------------------------------------------------------------------- #
#
# A lista é curta porque só entra nela variável que uma biblioteca do fecho
# **de fato** lê. `DO_NOT_TRACK`, `HF_HUB_OFFLINE` e `TRANSFORMERS_OFFLINE` ficam
# fora: a varredura não encontrou leitor para a primeira, e as outras duas
# pertencem a bibliotecas que `EXCLUIDAS` mantém ausentes — declará-las seria
# encenar uma defesa.
#
# As duas que sobram são lidas por `fastapi/telemetry/_runtime.py`, verificado
# linha a linha. Elas são a segunda linha de defesa, não a primeira: a primeira é
# a ausência do SDK e do exportador, que faz a exportação levantar `FastAPIError`
# em vez de sair pela rede.

VARIAVEIS_DE_AMBIENTE: Final[dict[str, str]] = {
    # Lida em `_configure_from_environment`: com `true`, a configuração automática
    # retorna sem registrar exportador nenhum, mesmo que o resto esteja ligado.
    "OTEL_SDK_DISABLED": "true",
    # Lida no construtor do `FastAPI`. Vazia ou diferente de `true` já basta; o
    # valor explícito existe para que o lançador declare a intenção em vez de
    # depender de ausência.
    "FASTAPI_OTEL_AUTO_CONFIGURE": "false",
}

# --------------------------------------------------------------------------- #
# Leitura do bloqueio e do projeto
# --------------------------------------------------------------------------- #


def _normalizar(nome: str) -> str:
    """Normaliza nome de distribuição como a PEP 503 manda."""
    return re.sub(r"[-_.]+", "-", nome).lower()


def fecho_do_bloqueio() -> dict[str, str]:
    """Nome e versão de cada distribuição resolvida em `uv.lock`, fora do projeto.

    O fecho, e não a lista de dependências diretas de `pyproject.toml`, porque é
    no que entra de carona que mora o risco: `opentelemetry-api` chegou com o
    `fastapi` e `fsspec` chega com o `torch`, nenhum dos dois pedido por nome.
    """
    bloqueio = tomllib.loads(ARQUIVO_BLOQUEIO.read_text(encoding="utf-8"))
    pacotes: dict[str, str] = {}
    for pacote in bloqueio["package"]:
        nome = _normalizar(str(pacote["name"]))
        if nome == PROJETO:
            continue
        pacotes[nome] = str(pacote.get("version", "?"))
    return pacotes


def dependencias_declaradas() -> tuple[str, ...]:
    """Toda dependência declarada em `pyproject.toml`, nos três grupos."""
    projeto = tomllib.loads(ARQUIVO_PROJETO.read_text(encoding="utf-8"))
    declaradas: list[str] = list(projeto["project"]["dependencies"])
    for itens in projeto["project"].get("optional-dependencies", {}).values():
        declaradas.extend(itens)
    for itens in projeto.get("dependency-groups", {}).values():
        declaradas.extend(itens)
    return tuple(declaradas)


# --------------------------------------------------------------------------- #
# Cobertura da triagem
# --------------------------------------------------------------------------- #


def test_toda_distribuicao_do_fecho_tem_veredito_de_triagem() -> None:
    """Dependência nova não entra calada: sem veredito, o portão fecha (R24.9)."""
    fecho = fecho_do_bloqueio()
    sem_veredito = sorted(set(fecho) - set(TRIAGEM))
    assert not sem_veredito, (
        "distribuições no fecho de uv.lock sem veredito de triagem: "
        f"{', '.join(sem_veredito)}. Leia o código instalado de cada uma, decida entre "
        f"{SEM_REDE}, {LACO_LOCAL} e {RESTRITA}, ou acrescente a EXCLUIDAS com a razão, "
        "e registre a decisão em docs/decisoes.md (DO-17)."
    )


def test_a_tabela_de_triagem_nao_guarda_pacote_que_ja_saiu() -> None:
    """Tabela que descreve pacote ausente é tabela que ninguém mais confere."""
    fecho = fecho_do_bloqueio()
    sobrando = sorted(set(TRIAGEM) - set(fecho))
    assert not sobrando, f"vereditos sem distribuição correspondente em uv.lock: {', '.join(sobrando)}"


def test_todo_veredito_usa_uma_das_tres_classes() -> None:
    for nome, veredito in TRIAGEM.items():
        assert veredito.classe in VEREDITOS, f"{nome}: classe desconhecida {veredito.classe!r}"
        assert veredito.razao.strip(), f"{nome}: veredito sem razão registrada"


def test_so_veredito_restrito_declara_trecho_proibido() -> None:
    """Restrição sem trecho proibido não é verificável; trecho sem restrição confunde."""
    for nome, veredito in TRIAGEM.items():
        if veredito.classe == RESTRITA:
            assert veredito.proibidos, f"{nome}: veredito {RESTRITA} precisa nomear o que fica proibido"
        else:
            assert not veredito.proibidos, f"{nome}: trecho proibido só cabe em veredito {RESTRITA}"


# --------------------------------------------------------------------------- #
# A rejeição exigida por R24.9
# --------------------------------------------------------------------------- #


def test_nenhuma_dependencia_excluida_entrou_no_fecho() -> None:
    """R24.9: a dependência que exige rede em execução é rejeitada pelo ambiente.

    Num projeto bloqueado por `uv.lock`, rejeitar é não constar do fecho. Este é
    o teste que dá efeito à rejeição: ele falha no commit que trouxer o pacote,
    e não meses depois, quando alguém reler o documento.
    """
    fecho = fecho_do_bloqueio()
    intrusas = sorted(set(fecho) & set(EXCLUIDAS))
    assert not intrusas, "\n".join(
        [
            "dependências rejeitadas pela triagem presentes em uv.lock:",
            *(f"  - {nome} {fecho[nome]}: {EXCLUIDAS[nome]}" for nome in intrusas),
            "Remova a dependência ou, se a exclusão deixou de valer, reabra DO-17 em docs/decisoes.md.",
        ]
    )


def test_cada_exclusao_traz_a_razao_registrada() -> None:
    for nome, razao in EXCLUIDAS.items():
        assert _normalizar(nome) == nome, f"{nome}: nome de distribuição fora da forma normalizada"
        assert razao.strip(), f"{nome}: exclusão sem razão"


def test_fastapi_e_declarado_sem_os_extras_de_telemetria() -> None:
    """`fastapi[standard]` e `fastapi[opentelemetry]` trariam SDK e exportador."""
    for declarada in dependencias_declaradas():
        if declarada.startswith("fastapi"):
            assert "[" not in declarada, (
                f"dependência declarada com extras: {declarada!r}. Os extras `standard` e "
                "`opentelemetry` instalam o exportador OTLP, que EXCLUIDAS rejeita."
            )


# --------------------------------------------------------------------------- #
# Destinos aceitos
# --------------------------------------------------------------------------- #


def test_so_a_pilha_declarada_fala_rede_em_tempo_de_execucao() -> None:
    """R24.8: a lista de quem pode abrir conexão é fechada e nomeada.

    Vale como declaração, não como repetição da tabela: se uma distribuição
    passar de `sem-rede` para `laco-local` numa versão nova, a mudança aparece
    aqui, no lugar em que alguém precisa aprová-la.
    """
    com_rede = {nome for nome, veredito in TRIAGEM.items() if veredito.classe == LACO_LOCAL}
    assert com_rede == {"httpx", "httpcore", "anyio", "uvicorn", "import-linter"}


def test_destinos_aceitos_sao_apenas_de_laco_local() -> None:
    """Endereço de escuta em todas as interfaces não é destino de laço local."""
    assert DESTINOS_ACEITOS == {"127.0.0.1", "localhost", "::1"}
    assert "0.0.0.0" not in DESTINOS_ACEITOS  # noqa: S104 - a asserção é justamente que não entra
    assert "::" not in DESTINOS_ACEITOS
    assert cli.HOST_OLLAMA in DESTINOS_ACEITOS


# --------------------------------------------------------------------------- #
# As restrições de uso, varridas contra o código do projeto
# --------------------------------------------------------------------------- #


def _arquivos_de_codigo() -> list[Path]:
    """Código próprio do projeto, menos este arquivo.

    Este arquivo fica fora porque é ele que **declara** os trechos proibidos: a
    tabela `TRIAGEM` os cita por necessidade, e varrê-la acusaria a si mesma.
    """
    aqui = Path(__file__).resolve()
    arquivos: list[Path] = []
    for arvore in ARVORES_DE_CODIGO:
        arquivos.extend(
            caminho
            for caminho in sorted((RAIZ / arvore).rglob("*.py"))
            if caminho.resolve() != aqui and "__pycache__" not in caminho.parts
        )
    return arquivos


def test_o_codigo_do_projeto_nao_usa_api_restrita() -> None:
    """A restrição de um veredito `RESTRITA` vale sobre `backend/` e `ml/`.

    É esta varredura que impede a triagem de ser papel. `import-linter` não
    alcança o caso: ele reduz pacote externo ao nome de topo, e é por isso que
    `backend/.importlinter` proíbe `urllib` inteiro em vez de `urllib.request`.
    `sklearn.datasets` e `torch.hub` não são expressáveis como contrato, então a
    verificação é textual, sobre o código fonte.
    """
    restricoes = {
        trecho: nome for nome, veredito in TRIAGEM.items() for trecho in veredito.proibidos if veredito.proibidos
    }
    achados: list[str] = []
    for arquivo in _arquivos_de_codigo():
        texto = arquivo.read_text(encoding="utf-8")
        relativo = arquivo.relative_to(RAIZ).as_posix()
        for numero, linha in enumerate(texto.splitlines(), start=1):
            for trecho, distribuicao in restricoes.items():
                if trecho in linha:
                    achados.append(f"  {relativo}:{numero}: {trecho!r} ({distribuicao})")
    assert not achados, "\n".join(
        [
            "uso de API restrita pela triagem de rede (DO-17):",
            *achados,
            "Essas APIs alcançam destino fora do laço local. Se o uso for legítimo, a decisão é de DO-17.",
        ]
    )


def test_a_configuracao_do_pytest_nao_liga_o_envio_para_pastebin() -> None:
    """`--pastebin` publicaria o relatório da sessão em serviço externo."""
    projeto = tomllib.loads(ARQUIVO_PROJETO.read_text(encoding="utf-8"))
    addopts = str(projeto["tool"]["pytest"]["ini_options"].get("addopts", ""))
    assert "--pastebin" not in addopts


@pytest.mark.parametrize("lancador", LANCADORES)
def test_os_lancadores_declaram_as_variaveis_que_desligam_telemetria(lancador: str) -> None:
    """A segunda linha de defesa só vale se estiver no processo que sobe, não no documento."""
    texto = (RAIZ / lancador).read_text(encoding="utf-8")
    for variavel, valor in VARIAVEIS_DE_AMBIENTE.items():
        esperado = f'$env:{variavel} = "{valor}"'
        assert esperado in texto, f"{lancador} não declara {esperado}"


# --------------------------------------------------------------------------- #
# O registro exigido por R24.9
# --------------------------------------------------------------------------- #


def test_a_triagem_esta_registrada_em_docs_decisoes() -> None:
    """R24.9 nomeia `docs/decisoes.md` como destino obrigatório da exclusão.

    O requisito manda registrar lá, então o registro é parte do portão: tabela e
    documento não podem divergir. Sem isto, acrescentar uma exclusão sem
    documentá-la passaria no portão, e o arquivo que R24.9 elege como fonte
    ficaria incompleto sem que nada acusasse.
    """
    texto = ARQUIVO_DECISOES.read_text(encoding="utf-8")
    assert "DO-17" in texto, "a triagem de rede entra em docs/decisoes.md como DO-17"
    nao_registradas = sorted(nome for nome in EXCLUIDAS if nome not in texto)
    assert not nao_registradas, (
        f"exclusões ausentes de docs/decisoes.md: {', '.join(nao_registradas)}. "
        "R24.9 exige a exclusão registrada lá, com a razão."
    )
    restritas = sorted(nome for nome, veredito in TRIAGEM.items() if veredito.classe == RESTRITA)
    sem_registro = [nome for nome in restritas if nome not in texto]
    assert not sem_registro, f"dependências aceitas com restrição ausentes de docs/decisoes.md: {sem_registro}"


# --------------------------------------------------------------------------- #
# Verificação comportamental: importar não pode abrir conexão externa
# --------------------------------------------------------------------------- #
#
# As verificações acima são estáticas: leem tabela, bloqueio e código fonte. Esta
# observa o comportamento, porque tabela é afirmação sobre o código instalado e
# afirmação sobre código instalado precisa ser medida pelo menos uma vez.
#
# Roda em subprocesso por uma razão só: a guarda precisa estar de pé **antes** do
# primeiro `import`, e num processo de `pytest` os módulos já foram importados
# pela coleta. A guarda intercepta as quatro portas de saída — `connect`,
# `connect_ex`, `create_connection` e `getaddrinfo` — e deixa passar apenas os
# destinos de laço local, que é precisamente o que R24.8 permite.

_GUARDA = '''
import importlib, importlib.util, json, socket, sys

LOCAIS = {"127.0.0.1", "::1", "localhost", "0.0.0.0", "::", ""}
violacoes = []

_connect, _connect_ex = socket.socket.connect, socket.socket.connect_ex
_create_connection, _getaddrinfo = socket.create_connection, socket.getaddrinfo


def _host(endereco):
    return str(endereco[0]) if isinstance(endereco, tuple) and endereco else str(endereco)


def _barrar(porta, endereco):
    alvo = _host(endereco)
    if alvo not in LOCAIS:
        violacoes.append(porta + " -> " + alvo)
        raise OSError("saida de rede barrada pela triagem: " + porta + " -> " + alvo)


def connect(self, endereco):
    _barrar("socket.connect", endereco)
    return _connect(self, endereco)


def connect_ex(self, endereco):
    _barrar("socket.connect_ex", endereco)
    return _connect_ex(self, endereco)


def create_connection(endereco, *a, **k):
    _barrar("socket.create_connection", endereco)
    return _create_connection(endereco, *a, **k)


def getaddrinfo(host, porta, *a, **k):
    _barrar("socket.getaddrinfo", (host,))
    return _getaddrinfo(host, porta, *a, **k)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.create_connection = create_connection
socket.getaddrinfo = getaddrinfo

ausentes = []
for nome in json.loads(sys.argv[1]):
    if importlib.util.find_spec(nome.split(".")[0]) is None:
        ausentes.append(nome)
        continue
    importlib.import_module(nome)

print(json.dumps({"violacoes": violacoes, "ausentes": ausentes}))
'''

#: Superfície de execução do protótipo, mais as ferramentas que o portão carrega.
#: `torch` entra na lista e pode faltar: o extra `ml` fica fora da sincronização
#: padrão de propósito (orçamento de disco de §2.5), e o teste trata a ausência
#: como ausência, não como aprovação.
SUPERFICIE: Final = (
    "adia",
    "adia.cli",
    "fastapi",
    "starlette",
    "pydantic",
    "uvicorn",
    "httpx",
    "tomli_w",
    "numpy",
    "scipy",
    "sklearn",
    "sklearn.feature_extraction.text",
    "sklearn.linear_model",
    "joblib",
    "hypothesis",
    "torch",
)

#: Distribuições que podem faltar no ambiente sincronizado por padrão.
OPCIONAIS: Final = frozenset({"torch"})


def test_importar_a_superficie_de_execucao_nao_abre_conexao_externa() -> None:
    """R24.8: nenhum módulo do protótipo emite requisição ao ser carregado."""
    concluido = subprocess.run(  # noqa: S603 - executável é o próprio interpretador do ambiente
        [sys.executable, "-c", _GUARDA, json.dumps(list(SUPERFICIE))],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
        cwd=RAIZ,
    )
    assert concluido.returncode == 0, (
        "a importação da superfície de execução falhou sob a guarda de rede:\n"
        f"{concluido.stdout}\n{concluido.stderr}"
    )
    resultado = json.loads(concluido.stdout.strip().splitlines()[-1])
    assert resultado["violacoes"] == [], f"saída de rede durante a importação: {resultado['violacoes']}"
    ausentes = {nome.split(".")[0] for nome in resultado["ausentes"]}
    assert ausentes <= OPCIONAIS, f"módulos da superfície ausentes do ambiente: {sorted(ausentes)}"
