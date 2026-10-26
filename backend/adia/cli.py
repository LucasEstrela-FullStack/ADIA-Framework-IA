"""Interface de linha de comando do protótipo ADIA-CognitiveLoop.

O design §3.18 declara nove comandos. Nesta tarefa — 1.3, Fase 0 — apenas
`doutor` está implementado. Os demais são declarados aqui, informam a fase e a
tarefa em que entram e terminam com código diferente de zero: comando que ainda
não faz nada e termina com sucesso é falsa impressão de sucesso, e num
instrumento de pesquisa isso custa mais caro que a ausência do comando.

`doutor` atende R1.7 e R1.11. Reporta, para Python, `uv`, Node.js, `npm`, `git`
e Ollama, a versão exigida, a versão detectada e a situação entre `presente`,
`ausente` e `divergente`; classifica como `ausente` a ferramenta cujo comando de
versão não responder em 5 s (DO-16 em `docs/decisoes.md`); e termina com código
diferente de zero diante de qualquer ausente ou divergente.

**O comando não instala, não atualiza e não altera nenhuma ferramenta.** Ele só
observa e reporta. Corrigir é ação humana, e o relatório diz qual é o passo.

As versões exigidas são **lidas dos arquivos de fixação** — `.python-version`,
`.nvmrc` e o campo `engines.npm` de `package.json` — e nunca embutidas neste
módulo: versão exigida duplicada em código é versão exigida que vai divergir do
arquivo que a fixa. Para `uv`, `git` e Ollama o projeto não fixa versão; o
relatório traz a detectada e trata apenas a ausência como falha, sem inventar
piso mínimo.

A situação do Ollama é a do **executável**, não a do serviço. Serviço desligado
aparece como observação, não como falha: por D1 as etapas sem IA e o portão
local de §6.1 rodam integralmente com o Ollama fora (R23.5), e reprovar o
ambiente por isso contradiria a própria arquitetura.

Códigos de saída:

| Código | Significado |
| --- | --- |
| 0 | `doutor`: ambiente conforme |
| 1 | `doutor`: ferramenta ausente ou divergente, ou fixação ilegível |
| 2 | erro de uso da linha de comando (padrão do `argparse`) |
| 3 | comando declarado cuja implementação pertence a outra fase |

O relatório de `doutor` ganha os campos de fase posterior quando eles passarem a
existir: `sqlite3.sqlite_version` e `esquema_versao` na Fase 2 (design §4.3 e
§4.7) e `indice_rag` na Fase 4 (design §7.6). Nenhum deles tem o que reportar
antes de haver banco e índice.
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #

#: Tempo limite do comando de versão de cada ferramenta (R1.7, DO-16). Esgotado
#: o prazo, a ferramenta é classificada como `ausente`.
TEMPO_LIMITE_VERSAO_S: Final = 5.0

#: Tempo limite da sondagem do serviço de inferência local. É o mesmo tempo
#: limite de conexão que o design §7.6 fixa para `disponivel()`.
TEMPO_LIMITE_SERVICO_S: Final = 1.0

HOST_OLLAMA: Final = "127.0.0.1"
PORTA_OLLAMA: Final = 11434

ARQUIVO_PYTHON: Final = ".python-version"
ARQUIVO_NODE: Final = ".nvmrc"
ARQUIVO_NPM: Final = "package.json"

#: Marcas que identificam a raiz do projeto. As duas juntas, porque
#: `pyproject.toml` sozinho também aparece em subprojetos.
MARCAS_DA_RAIZ: Final = (ARQUIVO_PYTHON, "pyproject.toml")

CODIGO_OK: Final = 0
CODIGO_AMBIENTE_INVALIDO: Final = 1
CODIGO_NAO_IMPLEMENTADO: Final = 3

SEM_VERSAO_FIXADA: Final = "não fixada"
EXIGENCIA_INDETERMINADA: Final = "indeterminada"
SEM_FONTE: Final = "-"

#: Componentes de uma versão completa: `maior.menor.correção`.
_COMPONENTES_COMPLETOS: Final = 3

Situacao = Literal["presente", "ausente", "divergente"]

#: Primeiro número de versão pontuado que aparecer na saída do comando. Cobre
#: `v25.5.0`, `uv 0.11.1 (...)`, `git version 2.55.0.windows.3` e
#: `ollama version is 0.40.8` sem precisar de um padrão por ferramenta.
_VERSAO_NA_SAIDA: Final = re.compile(r"\d+(?:\.\d+)+")

#: Versão declarada num arquivo de fixação: `3.13`, `24`, `v24`. Estrito de
#: propósito: arquivo de fixação com conteúdo inesperado é problema a reportar,
#: não texto a interpretar.
_VERSAO_DECLARADA: Final = re.compile(r"v?(\d+(?:\.\d+){0,2})\Z")

#: Prefixo numérico de uma versão detectada, para comparação.
_PREFIXO_NUMERICO: Final = re.compile(r"v?(\d+(?:\.\d+)*)")

#: Operador e número de um intervalo do campo `engines`: `>=11`, `< 12`.
_TOKEN_INTERVALO: Final = re.compile(r"(>=|<)\s*v?(\d+(?:\.\d+){0,2})")


# --------------------------------------------------------------------------- #
# Modelo do relatório
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Faixa:
    """Faixa de versões aceitas, com piso inclusivo e teto exclusivo."""

    piso: tuple[int, int, int]
    teto: tuple[int, int, int] | None

    def contem(self, versao: tuple[int, int, int]) -> bool:
        """Informa se `versao` cai na faixa."""
        if versao < self.piso:
            return False
        return self.teto is None or versao < self.teto


@dataclass(frozen=True, slots=True)
class Exigencia:
    """Versão exigida de uma ferramenta e o arquivo que a fixa.

    `faixa` é `None` em dois casos distintos: quando o projeto não fixa versão
    para a ferramenta — `uv`, `git` e Ollama — e quando o arquivo de fixação não
    pôde ser lido. O segundo vem com `problema` preenchido, e só ele reprova.
    """

    texto: str
    fonte: str
    faixa: Faixa | None
    problema: str | None = None


@dataclass(frozen=True, slots=True)
class Deteccao:
    """O que a máquina respondeu quando perguntada pela versão."""

    versao: str | None
    motivo_ausencia: str | None = None
    observacao: str | None = None


@dataclass(frozen=True, slots=True)
class Verificacao:
    """Uma linha do relatório: ferramenta, exigência, detecção e situação."""

    ferramenta: str
    exigencia: Exigencia
    deteccao: Deteccao
    situacao: Situacao
    correcao: str


@dataclass(frozen=True, slots=True)
class Relatorio:
    """O relatório inteiro, mais os problemas que não são de ferramenta."""

    raiz: Path | None
    verificacoes: tuple[Verificacao, ...]
    problemas: tuple[str, ...]


# --------------------------------------------------------------------------- #
# Versões: leitura, comparação e classificação
# --------------------------------------------------------------------------- #


def _preencher(componentes: Sequence[int]) -> tuple[int, int, int]:
    """Completa com zeros até `maior.menor.correção`."""
    partes = [*componentes[:_COMPONENTES_COMPLETOS], 0, 0, 0]
    return (partes[0], partes[1], partes[2])


def _componentes(versao: str) -> tuple[int, ...]:
    return tuple(int(parte) for parte in versao.split("."))


def extrair_versao(saida: str) -> str | None:
    """Extrai da saída de um comando de versão o primeiro número pontuado."""
    achado = _VERSAO_NA_SAIDA.search(saida)
    return achado.group(0) if achado is not None else None


def numerar(versao: str) -> tuple[int, int, int] | None:
    """Converte `3.13.14` em `(3, 13, 14)`, ou devolve `None` se não der.

    Componentes além do terceiro são descartados: `2.55.0.windows.3` compara
    como `2.55.0`, que é o que a faixa exigida sabe discutir.
    """
    achado = _PREFIXO_NUMERICO.match(versao.strip())
    if achado is None:
        return None
    return _preencher(_componentes(achado.group(1)))


def faixa_por_prefixo(declarada: str) -> Faixa | None:
    """Monta a faixa aceita a partir de uma versão declarada por prefixo.

    `3.13` aceita de `3.13.0` até antes de `3.14.0`; `24` aceita de `24.0.0` até
    antes de `25.0.0`; `3.13.2` aceita apenas `3.13.2`. É a semântica de
    "precisão mínima de `maior.menor`" de R1.2 e de "precisão mínima de versão
    maior" de R1.5.
    """
    achado = _VERSAO_DECLARADA.fullmatch(declarada.strip())
    if achado is None:
        return None
    componentes = _componentes(achado.group(1))
    seguinte = (*componentes[:-1], componentes[-1] + 1)
    return Faixa(piso=_preencher(componentes), teto=_preencher(seguinte))


def faixa_de_intervalo(intervalo: str) -> Faixa | None:
    """Monta a faixa aceita a partir de um intervalo do campo `engines`.

    Reconhece `>=` e `<`, que é a forma usada em `package.json` (`">=11 <12"`).
    Qualquer outro operador devolve `None`, para que o relatório diga que não
    soube ler a exigência em vez de adivinhar uma.
    """
    piso: tuple[int, int, int] | None = None
    teto: tuple[int, int, int] | None = None
    coberto = 0
    for achado in _TOKEN_INTERVALO.finditer(intervalo):
        if intervalo[coberto : achado.start()].strip():
            return None
        coberto = achado.end()
        limite = _preencher(_componentes(achado.group(2)))
        if achado.group(1) == ">=":
            piso = limite
        else:
            teto = limite
    if intervalo[coberto:].strip() or piso is None:
        return None
    return Faixa(piso=piso, teto=teto)


def classificar(deteccao: Deteccao, exigencia: Exigencia) -> Situacao:
    """Decide a situação de uma ferramenta a partir do que foi observado.

    Sem versão detectada é `ausente` — inclusive quando o motivo foi o tempo
    limite de 5 s (R1.7). Com versão detectada e sem faixa exigida é `presente`:
    não há com o que divergir. Com faixa exigida, decide a faixa.
    """
    if deteccao.versao is None:
        return "ausente"
    if exigencia.faixa is None:
        return "presente"
    numero = numerar(deteccao.versao)
    if numero is None:
        return "ausente"
    return "presente" if exigencia.faixa.contem(numero) else "divergente"


def codigo_de_saida(relatorio: Relatorio) -> int:
    """Código de saída do `doutor` (R1.11).

    Zero só com as seis ferramentas `presente` e nenhum problema de fixação.
    Exigência que não pôde ser lida também reprova: ambiente que não se sabe
    verificar não é ambiente verificado.
    """
    if relatorio.problemas:
        return CODIGO_AMBIENTE_INVALIDO
    if any(verificacao.situacao != "presente" for verificacao in relatorio.verificacoes):
        return CODIGO_AMBIENTE_INVALIDO
    return CODIGO_OK


# --------------------------------------------------------------------------- #
# Raiz do projeto e arquivos de fixação
# --------------------------------------------------------------------------- #


def encontrar_raiz(inicio: Path | None = None) -> Path | None:
    """Sobe a árvore de diretórios até achar as marcas da raiz do projeto.

    Tenta, na ordem, o diretório informado, o diretório de trabalho e o
    diretório deste módulo. O terceiro é o que resolve a instalação editável,
    em que o pacote continua em `backend/adia/`.
    """
    partidas = [caminho for caminho in (inicio, Path.cwd(), Path(__file__).resolve().parent) if caminho is not None]
    for partida in partidas:
        resolvida = partida.resolve()
        for diretorio in (resolvida, *resolvida.parents):
            if all((diretorio / marca).is_file() for marca in MARCAS_DA_RAIZ):
                return diretorio
    return None


def _ler_texto(caminho: Path) -> str | None:
    try:
        return caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _indeterminada(fonte: str, problema: str) -> Exigencia:
    return Exigencia(
        texto=EXIGENCIA_INDETERMINADA,
        fonte=fonte,
        faixa=None,
        problema=problema,
    )


def _exigencia_por_prefixo(raiz: Path | None, arquivo: str) -> Exigencia:
    """Exigência lida de um arquivo que declara a versão por prefixo."""
    if raiz is None:
        return _indeterminada(arquivo, "raiz do projeto desconhecida")
    bruto = _ler_texto(raiz / arquivo)
    if bruto is None:
        return _indeterminada(arquivo, f"`{arquivo}` ausente ou ilegível")
    declarada = bruto.strip()
    faixa = faixa_por_prefixo(declarada)
    if faixa is None:
        return _indeterminada(
            arquivo,
            f"`{arquivo}` não declara versão reconhecível (conteúdo: {declarada!r})",
        )
    semversao = declarada.lstrip("v")
    completa = len(semversao.split(".")) >= _COMPONENTES_COMPLETOS
    return Exigencia(
        texto=semversao if completa else f"{semversao}.x",
        fonte=arquivo,
        faixa=faixa,
    )


def _exigencia_de_engines(raiz: Path | None, ferramenta: str) -> Exigencia:
    """Exigência lida de `engines.<ferramenta>` em `package.json`."""
    fonte = f"{ARQUIVO_NPM} engines.{ferramenta}"
    if raiz is None:
        return _indeterminada(fonte, "raiz do projeto desconhecida")
    bruto = _ler_texto(raiz / ARQUIVO_NPM)
    if bruto is None:
        return _indeterminada(fonte, f"`{ARQUIVO_NPM}` ausente ou ilegível")
    try:
        conteudo: object = json.loads(bruto)
    except json.JSONDecodeError as erro:
        return _indeterminada(fonte, f"`{ARQUIVO_NPM}` inválido na linha {erro.lineno}")
    if not isinstance(conteudo, dict):
        return _indeterminada(fonte, f"`{ARQUIVO_NPM}` não traz objeto JSON na raiz")
    engines: object = conteudo.get("engines")
    if not isinstance(engines, dict):
        return _indeterminada(fonte, f"`{ARQUIVO_NPM}` não declara `engines`")
    intervalo: object = engines.get(ferramenta)
    if not isinstance(intervalo, str):
        return _indeterminada(fonte, f"`engines.{ferramenta}` ausente")
    faixa = faixa_de_intervalo(intervalo)
    if faixa is None:
        return _indeterminada(
            fonte,
            f"`engines.{ferramenta}` usa intervalo não reconhecido ({intervalo!r})",
        )
    return Exigencia(texto=intervalo, fonte=fonte, faixa=faixa)


def _sem_exigencia() -> Exigencia:
    """Ferramenta para a qual o projeto não fixa versão."""
    return Exigencia(texto=SEM_VERSAO_FIXADA, fonte=SEM_FONTE, faixa=None)


# --------------------------------------------------------------------------- #
# Detecção
# --------------------------------------------------------------------------- #


def _detectar_por_comando(comando: str, *argumentos: str) -> Deteccao:
    """Pergunta a versão a uma ferramenta do PATH, sem alterar nada.

    `shutil.which` resolve a extensão pelo `PATHEXT`, o que importa no Windows:
    `npm` é `npm.cmd`, e sem a resolução o processo não seria encontrado.
    """
    executavel = shutil.which(comando)
    if executavel is None:
        return Deteccao(None, f"executável `{comando}` não encontrado no PATH")
    # Caminho absoluto resolvido do PATH, lista de argumentos e `shell=False`:
    # nada do que entra aqui vem de dado do usuário.
    try:
        concluido = subprocess.run(
            [executavel, *argumentos],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEMPO_LIMITE_VERSAO_S,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return Deteccao(
            None,
            f"o comando de versão não respondeu em {TEMPO_LIMITE_VERSAO_S:.0f} s",
        )
    except OSError as erro:
        return Deteccao(None, f"o comando de versão não executou ({erro.strerror or erro})")
    versao = extrair_versao(f"{concluido.stdout}\n{concluido.stderr}")
    if versao is not None:
        return Deteccao(versao)
    if concluido.returncode != 0:
        return Deteccao(None, f"o comando de versão falhou (código {concluido.returncode})")
    return Deteccao(None, "a saída do comando de versão não traz número reconhecível")


def _detectar_python() -> Deteccao:
    """Versão do interpretador que executa este comando.

    Não há subprocesso aqui, de propósito. O Python que interessa é o que `uv`
    provisionou em `.venv` e que está rodando a CLI (R1.2); `python --version`
    no PATH responderia por outra instalação e, no Windows, pode responder pelo
    atalho da loja de aplicativos.
    """
    return Deteccao(
        platform.python_version(),
        observacao=f"interpretador em execução: {sys.executable}",
    )


def _servico_ollama_responde() -> bool:
    """Sonda `GET /api/tags` no laço local, com 1 s de tempo limite."""
    pedido = f"GET /api/tags HTTP/1.0\r\nHost: {HOST_OLLAMA}:{PORTA_OLLAMA}\r\nConnection: close\r\n\r\n"
    try:
        with socket.create_connection((HOST_OLLAMA, PORTA_OLLAMA), timeout=TEMPO_LIMITE_SERVICO_S) as conexao:
            conexao.settimeout(TEMPO_LIMITE_SERVICO_S)
            conexao.sendall(pedido.encode("ascii"))
            return conexao.recv(5).startswith(b"HTTP/")
    except OSError:
        return False


def _detectar_ollama() -> Deteccao:
    """Versão do executável do Ollama, com o estado do serviço como observação.

    A situação reportada é a do executável. Serviço desligado é informação, não
    falha: linha de base, desafio independente, pós-teste, retenção e o portão
    local de §6.1 rodam integralmente com ele fora (R23.5).
    """
    deteccao = _detectar_por_comando("ollama", "--version")
    endereco = f"{HOST_OLLAMA}:{PORTA_OLLAMA}"
    if _servico_ollama_responde():
        observacao = f"serviço respondendo em {endereco}"
    else:
        observacao = f"serviço sem resposta em {endereco}; as etapas sem IA e o portão local rodam assim"
    return Deteccao(deteccao.versao, deteccao.motivo_ausencia, observacao)


# --------------------------------------------------------------------------- #
# Montagem do relatório
# --------------------------------------------------------------------------- #

_CORRECAO: Final[dict[str, str]] = {
    "Python": "instalar a linha exigida com `uv python install` e recriar o ambiente com `uv sync` (D6)",
    "uv": "instalar o `uv` pela documentação oficial e reabrir o terminal",
    "Node.js": "instalar a linha exigida com `nvm install` seguido de `nvm use`, ou pelo instalador oficial (D7)",
    "npm": "o `npm` acompanha o Node.js: corrigir a linha do Node resolve",
    "git": "instalar o Git para Windows e reabrir o terminal",
    "Ollama": "instalar o Ollama; a Fase 4 é a primeira que depende dele",
}


def montar_exigencias(raiz: Path | None) -> dict[str, Exigencia]:
    """Lê dos arquivos de fixação a versão exigida de cada ferramenta de R1.7.

    Função separada da detecção de propósito: ler exigência é operação sobre
    arquivos do repositório, e detectar é operação sobre a máquina. Separadas,
    a primeira é verificável sem depender da segunda.
    """
    return {
        "Python": _exigencia_por_prefixo(raiz, ARQUIVO_PYTHON),
        "uv": _sem_exigencia(),
        "Node.js": _exigencia_por_prefixo(raiz, ARQUIVO_NODE),
        "npm": _exigencia_de_engines(raiz, "npm"),
        "git": _sem_exigencia(),
        "Ollama": _sem_exigencia(),
    }


def _montar_deteccoes() -> dict[str, Deteccao]:
    """Pergunta a versão a cada ferramenta. Observa; não altera nada."""
    return {
        "Python": _detectar_python(),
        "uv": _detectar_por_comando("uv", "--version"),
        "Node.js": _detectar_por_comando("node", "--version"),
        "npm": _detectar_por_comando("npm", "--version"),
        "git": _detectar_por_comando("git", "--version"),
        "Ollama": _detectar_ollama(),
    }


def montar_relatorio(raiz: Path | None = None) -> Relatorio:
    """Observa as seis ferramentas de R1.7 e monta o relatório.

    Nada é instalado, atualizado ou alterado: cada ferramenta é apenas
    perguntada pela própria versão.
    """
    raiz_efetiva = raiz if raiz is not None else encontrar_raiz()
    exigencias = montar_exigencias(raiz_efetiva)
    deteccoes = _montar_deteccoes()

    verificacoes = tuple(
        Verificacao(
            ferramenta=ferramenta,
            exigencia=exigencia,
            deteccao=deteccoes[ferramenta],
            situacao=classificar(deteccoes[ferramenta], exigencia),
            correcao=_CORRECAO[ferramenta],
        )
        for ferramenta, exigencia in exigencias.items()
    )
    problemas = [
        f"{ferramenta}: {exigencia.problema}"
        for ferramenta, exigencia in exigencias.items()
        if exigencia.problema is not None
    ]
    if raiz_efetiva is None:
        marcas = " e ".join(f"`{marca}`" for marca in MARCAS_DA_RAIZ)
        problemas.insert(0, f"raiz do projeto não localizada: nenhum diretório acima tem {marcas}")
    return Relatorio(
        raiz=raiz_efetiva,
        verificacoes=verificacoes,
        problemas=tuple(problemas),
    )


# --------------------------------------------------------------------------- #
# Apresentação
# --------------------------------------------------------------------------- #

_CABECALHO: Final = (
    "Ferramenta",
    "Versão exigida",
    "Versão detectada",
    "Situação",
    "Fixada em",
)


def _renderizar_tabela(linhas: Sequence[Sequence[str]]) -> list[str]:
    """Tabela alinhada só com caracteres ASCII, por causa do console pt-BR."""
    colunas = range(len(linhas[0]))
    larguras = [max(len(linha[coluna]) for linha in linhas) for coluna in colunas]
    cabecalho, *corpo = linhas
    regua = ["-" * largura for largura in larguras]
    return [
        "  ".join(celula.ljust(largura) for celula, largura in zip(linha, larguras, strict=True)).rstrip()
        for linha in (cabecalho, regua, *corpo)
    ]


def formatar_relatorio(relatorio: Relatorio) -> list[str]:
    """Monta as linhas do relatório de `doutor`."""
    linhas = ["Verificação de ambiente - ADIA-CognitiveLoop"]
    if relatorio.raiz is not None:
        linhas.append(f"Raiz do projeto: {relatorio.raiz}")
    linhas.append("")
    linhas.extend(
        _renderizar_tabela(
            [
                _CABECALHO,
                *(
                    (
                        verificacao.ferramenta,
                        verificacao.exigencia.texto,
                        verificacao.deteccao.versao or "-",
                        verificacao.situacao,
                        verificacao.exigencia.fonte,
                    )
                    for verificacao in relatorio.verificacoes
                ),
            ]
        )
    )

    observacoes = [
        f"- {verificacao.ferramenta}: {verificacao.deteccao.observacao}"
        for verificacao in relatorio.verificacoes
        if verificacao.deteccao.observacao is not None
    ]
    if observacoes:
        linhas.extend(["", "Observações:", *observacoes])

    fora = [v for v in relatorio.verificacoes if v.situacao != "presente"]
    if fora:
        linhas.extend(["", "Ferramentas fora de conformidade:"])
        for verificacao in fora:
            motivo = verificacao.deteccao.motivo_ausencia or (
                f"versão {verificacao.deteccao.versao} fora da exigida {verificacao.exigencia.texto}"
            )
            linhas.append(f"- {verificacao.ferramenta} ({verificacao.situacao}): {motivo}")
            linhas.append(f"  Correção: {verificacao.correcao}")

    if relatorio.problemas:
        linhas.extend(["", "Problemas na leitura das versões exigidas:"])
        linhas.extend(f"- {problema}" for problema in relatorio.problemas)

    linhas.append("")
    if codigo_de_saida(relatorio) == CODIGO_OK:
        linhas.append("Ambiente conforme: as seis ferramentas exigidas estão presentes.")
    else:
        linhas.append(
            f"Ambiente não conforme: {len(fora)} de {len(relatorio.verificacoes)} "
            "ferramentas fora de conformidade. Nada foi instalado nem alterado."
        )
    return linhas


def _escrever(linhas: Sequence[str]) -> None:
    """Escreve a saída em UTF-8, sem deixar a página de código derrubar nada.

    No console do Windows a saída já é UTF-8 e isto não muda nada. Redirecionada
    para arquivo ou canalizada, a saída passaria a usar a página de código local
    e a acentuação chegaria errada ao PowerShell 5.1 em pt-BR; fixar UTF-8 aqui
    é a outra metade do `[Console]::OutputEncoding = [Text.Encoding]::UTF8` que
    os scripts de `scripts/` declaram (design §2.3). `errors="replace"` é rede
    de segurança: relatório com um caractere trocado ainda é relatório, mas um
    `UnicodeEncodeError` derrubaria o comando que existe para diagnosticar.
    """
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for linha in linhas:
        print(linha)


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #


def doutor() -> int:
    """Verifica o ambiente e reporta (R1.7, R1.11). Não altera nada."""
    relatorio = montar_relatorio()
    _escrever(formatar_relatorio(relatorio))
    return codigo_de_saida(relatorio)


#: Os nove comandos da tabela do design §3.18, na ordem em que ela os declara.
#: `itens` e `guarda` são grupos: a invocação completa leva subcomando.
COMANDOS: Final = (
    "doutor",
    "migrar",
    "itens",
    "guarda",
    "indexar",
    "replay",
    "exportar",
    "excluir-dados",
    "benchmark",
)


@dataclass(frozen=True, slots=True)
class Pendente:
    """Comando declarado no design §3.18 que entra numa fase posterior."""

    invocacao: str
    fase: str
    tarefa: str
    resumo: str


PENDENTES: Final[dict[str, Pendente]] = {
    "migrar": Pendente(
        "adia migrar",
        "Fase 2",
        "8.1",
        "aplica as migrações e grava a versão vigente de esquema",
    ),
    "itens validar": Pendente(
        "adia itens validar",
        "Fase 1",
        "3.3",
        "carrega `data/itens/*.adia.toml` com as validações de gramática",
    ),
    "itens formatar": Pendente(
        "adia itens formatar",
        "Fase 1",
        "3.3",
        "reescreve os itens na forma canônica do serializador",
    ),
    "guarda verificar": Pendente(
        "adia guarda verificar",
        "Fase 1",
        "6.8",
        "roda o conjunto declarado de verificação e reporta os dois portões",
    ),
    "indexar": Pendente(
        "adia indexar",
        "Fase 4",
        "13.4",
        "indexa `data/corpus/` com `bge-m3` e versiona o índice",
    ),
    "replay": Pendente(
        "adia replay",
        "Fase 2",
        "8.3",
        "reconstrói as projeções a partir dos eventos e compara com as vigentes",
    ),
    "exportar": Pendente(
        "adia exportar",
        "Fase 2",
        "8.8",
        "exporta os CSV de eventos e de métricas com proveniência embutida",
    ),
    "excluir-dados": Pendente(
        "adia excluir-dados",
        "Fase 2",
        "8.11",
        "exclui os dados de um pseudônimo e registra a execução na auditoria",
    ),
    "benchmark": Pendente(
        "adia benchmark",
        "Fase 4",
        "13.11",
        "mede os candidatos de modelo e produz o relatório do benchmark",
    ),
}


def relatar_pendente(pendente: Pendente) -> int:
    """Informa a fase e a tarefa do comando e termina com falha."""
    _escrever(
        [
            f"`{pendente.invocacao}` ainda não está implementado.",
            f"Entra na {pendente.fase}, tarefa {pendente.tarefa}: {pendente.resumo}.",
            "Nenhuma ação foi executada.",
        ]
    )
    return CODIGO_NAO_IMPLEMENTADO


# --------------------------------------------------------------------------- #
# Linha de comando
# --------------------------------------------------------------------------- #


def _ajuda_pendente(chave: str) -> str:
    pendente = PENDENTES[chave]
    return f"{pendente.resumo} (ainda não implementado: {pendente.fase}, tarefa {pendente.tarefa})"


def construir_analisador() -> argparse.ArgumentParser:
    """Declara os nove comandos do design §3.18."""
    analisador = argparse.ArgumentParser(
        prog="adia",
        description=(
            "Ferramentas de linha de comando do protótipo ADIA-CognitiveLoop. "
            "Nesta fase apenas `doutor` está implementado; os demais comandos "
            "informam a fase e a tarefa em que entram."
        ),
    )
    comandos = analisador.add_subparsers(dest="comando", metavar="comando", required=True)

    comandos.add_parser(
        "doutor",
        help=(
            "reporta versão exigida, detectada e situação de Python, uv, "
            "Node.js, npm, git e Ollama; não instala nem altera nada"
        ),
    )
    comandos.add_parser("migrar", help=_ajuda_pendente("migrar"))

    itens = comandos.add_parser("itens", help="operações sobre o banco de itens")
    subitens = itens.add_subparsers(dest="subcomando", metavar="subcomando", required=True)
    subitens.add_parser("validar", help=_ajuda_pendente("itens validar"))
    subitens.add_parser("formatar", help=_ajuda_pendente("itens formatar"))

    guarda = comandos.add_parser("guarda", help="operações sobre a guarda de vazamento")
    subguarda = guarda.add_subparsers(dest="subcomando", metavar="subcomando", required=True)
    subguarda.add_parser("verificar", help=_ajuda_pendente("guarda verificar"))

    for chave in ("indexar", "replay", "exportar", "excluir-dados", "benchmark"):
        comandos.add_parser(chave, help=_ajuda_pendente(chave))

    return analisador


def principal(argumentos: Sequence[str] | None = None) -> int:
    """Ponto de entrada do executável `adia` declarado em `pyproject.toml`."""
    analisador = construir_analisador()
    espaco = analisador.parse_args(argumentos)

    comando = str(espaco.comando)
    if comando == "doutor":
        return doutor()

    subcomando = getattr(espaco, "subcomando", None)
    chave = f"{comando} {subcomando}" if isinstance(subcomando, str) else comando
    pendente = PENDENTES.get(chave)
    if pendente is None:
        analisador.error(f"comando não reconhecido: {chave}")
    return relatar_pendente(pendente)


if __name__ == "__main__":
    sys.exit(principal())
