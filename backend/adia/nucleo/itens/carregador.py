"""Carga dos arquivos de definição de itens: ``carregar`` e as nove rejeições de §3.1.

Lê ``data/itens/*.adia.toml`` com ``tomllib`` (D12) e devolve, ou o banco inteiro, ou **um**
erro que nomeia arquivo, linha e campo (R3.1, R3.2). A gramática normativa está em
``docs/gramatica-itens.md``; este módulo é a sua única implementação.

**A carga é atômica.** ``carregar`` devolve ``CargaConcluida`` com todos os itens de todos os
arquivos, ou um ``ErroDeCarga`` e nenhum item. Não existe modo "carregar o que deu", e isso
não é rigor por gosto: o banco de itens é entrada de tudo o que se mede, e um banco
parcialmente carregado produz TAI, TT, IIC e decisão de regulação descrevendo um conjunto de
itens diferente do que o protocolo descreve (§7.2). Publicar metade do banco seria pior que
não publicar nada, porque a execução prosseguiria e os números pareceriam válidos.

## Como a linha é apurada

R3.2 exige a linha, e ``tomllib`` só a oferece no erro de sintaxe. Para as falhas semânticas
o módulo mantém um índice próprio: ``_indexar`` varre o texto já aceito pelo interpretador e
registra a linha de cada cabeçalho ``[[item]]``, ``[[relacao]]``, ``[item.dicas]`` e de cada
chave dentro deles. A varredura respeita cadeias de bloco ``\"\"\"``, cadeias literais e
colchetes de lista, porque enunciado e dica são multilinha e uma linha de conteúdo pode
começar com ``[`` ou parecer uma chave.

Com isso, a linha é **exata** quando o campo existe no texto. Quando o campo está **ausente**
— tolerância que falta, nível de dica que falta, ``etapas_permitidas`` que ninguém escreveu —
não existe linha a apontar, e o erro aponta a linha do cabeçalho ``[[item]]`` que deveria
conter o campo. É aproximação declarada, não precisão fingida; a alternativa seria omitir a
linha e deixar quem corrige procurar o item à mão. Uma única falha fica sem linha: arquivo
inexistente ou ilegível, onde não há texto para indexar.

## Ordem das verificações

A ordem é fixa, para que o mesmo conjunto de arquivos produza sempre a **mesma** primeira
rejeição — reprodutibilidade de diagnóstico vale tanto quanto reprodutibilidade de métrica
(R26). Por arquivo, na ordem recebida: leitura e codificação, sintaxe, estrutura da raiz,
cada item na ordem de declaração com os campos em ordem fixa, identificador duplicado, e
depois cada relação. Com todos os arquivos lidos: integridade das relações, associações de
R2.2 e R2.6, e conflito de R2.9.

Três normalizações acontecem na leitura, e as três existem para a ida e volta de R3.4 e R3.5:
coleções são conjuntos escritos como lista, logo são **ordenadas** e não admitem repetição;
``\\r\\n`` é normalizado para ``\\n`` antes de interpretar; e o banco publicado sai ordenado
por identificador, independentemente da ordem dos arquivos recebidos.
"""

from __future__ import annotations

import re
import string
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Final, NoReturn

from adia.nucleo.itens.erros import (
    ErroDeAssociacaoAusente,
    ErroDeCarga,
    ErroDeConflitoDeRelacao,
    ErroDeDicaAusente,
    ErroDeEtapasVazias,
    ErroDeFaixa,
    ErroDeGramatica,
    ErroDeIdentificadorDuplicado,
    ErroDePerfilIncompleto,
    nome_do_tipo,
    valor_citavel,
)
from adia.nucleo.itens.modelo import (
    DIFICULDADE_MAXIMA,
    DIFICULDADE_MINIMA,
    EQUIVALENTE,
    TIPOS_DE_RELACAO,
    TRANSFERENCIA,
    Item,
    Relacao,
    TipoDeRelacao,
    TipoGabarito,
    tipo_de_relacao,
)
from adia.tipos import Etapa, Nivel

# --------------------------------------------------------------------------- #
# Vocabulário da gramática
# --------------------------------------------------------------------------- #

SUFIXO_DE_ARQUIVO: Final = ".adia.toml"
"""Sufixo dos arquivos de definição, conforme a árvore de §2.3 e D12."""

TABELA_DE_ITEM: Final = "item"
TABELA_DE_RELACAO: Final = "relacao"
TABELA_DE_DICAS: Final = "dicas"

CHAVES_DA_RAIZ: Final = frozenset({TABELA_DE_ITEM, TABELA_DE_RELACAO})
"""As duas únicas chaves de nível raiz. Qualquer outra é erro de gramática."""

CAMPOS_OBRIGATORIOS_DE_ITEM: Final = (
    "id",
    "enunciado",
    "habilidade_alvo",
    "dificuldade",
    "tamanho_max_resposta",
    "tipo_gabarito",
    "gabarito",
)
"""Campos sem os quais o item não existe (R2.1), na ordem de verificação."""

CAMPOS_OPCIONAIS_DE_ITEM: Final = (
    "tolerancia",
    "unidade",
    "sinonimos_unidade",
    "variacoes_gabarito",
    "termos_essenciais",
    "incognita",
    "transferencia",
)
"""Campos de ausência legítima. ``tolerancia`` e ``termos_essenciais`` deixam de ser
opcionais conforme o tipo de gabarito, e aí a falha é de perfil, não de gramática."""

CAMPOS_DE_ITEM: Final = (
    frozenset(CAMPOS_OBRIGATORIOS_DE_ITEM)
    | frozenset(CAMPOS_OPCIONAIS_DE_ITEM)
    | frozenset({"etapas_permitidas", TABELA_DE_DICAS})
)

CAMPOS_DE_RELACAO: Final = ("item_origem", "item_destino", "tipo")

PADRAO_DE_IDENTIFICADOR: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
"""Forma de ``id``, ``habilidade_alvo`` e ``incognita``: ASCII, sem espaço, até 64 caracteres.

A restrição a ASCII não é economia de teclado. ``habilidade_alvo`` é comparado por igualdade
exata no pareamento de R2.2, e ``"equação"`` escrito em NFC e em NFD são cadeias
**diferentes** com a mesma aparência na tela: o pareamento falharia sem que nada no arquivo
parecesse errado. Fechar o alfabeto elimina a classe inteira de defeito. Enunciado, dicas,
unidade e termos essenciais seguem em texto livre acentuado, que é onde a acentuação importa.
"""

PADRAO_DE_DECIMAL: Final = re.compile(r"^[+-]?\d+(\.\d+)?$")
"""Forma da tolerância: cadeia decimal em notação simples, com ponto como separador."""

_LINHA_DO_INTERPRETADOR: Final = re.compile(r"at line (\d+)")
"""Extrai a linha da mensagem de ``tomllib`` no Python 3.13, que não expõe ``lineno``."""

_CARACTERES_DE_CHAVE: Final = frozenset(string.ascii_letters + string.digits + "_-")


# --------------------------------------------------------------------------- #
# Resultado
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CargaConcluida:
    """Banco de itens publicado: todos os itens e todas as relações, de todos os arquivos.

    Ordenado por construção — itens por ``id``, relações pela tripla
    ``(origem, destino, tipo)`` — para que o conteúdo publicado não dependa da ordem em que
    os arquivos foram listados pelo sistema de arquivos. É essa estabilidade que o hash do
    banco de itens da proveniência pressupõe (§4.3, R26).
    """

    itens: tuple[Item, ...]
    relacoes: tuple[Relacao, ...]


type ResultadoDeCarga = CargaConcluida | ErroDeCarga
"""Ou o banco inteiro, ou a primeira rejeição. Nunca um banco parcial (§7.2)."""


def arquivos_de_itens(diretorio: Path) -> tuple[Path, ...]:
    """Arquivos de definição do diretório, em ordem estável de caminho.

    Ordenar aqui, e não em ``carregar``, mantém a função de carga indiferente à origem da
    lista: quem chama decide o conjunto, e a ordem do sistema de arquivos — que varia entre
    máquinas — não decide nada.
    """
    return tuple(sorted(diretorio.glob(f"*{SUFIXO_DE_ARQUIVO}")))


# --------------------------------------------------------------------------- #
# Rejeição interna
# --------------------------------------------------------------------------- #


class _Rejeicao(Exception):
    """Transporte interno do erro até ``carregar``, que o devolve como valor.

    A exceção não escapa do módulo: a fronteira pública é valor de retorno (§3.1). Dentro, a
    exceção evita que cada uma das dezenas de verificações carregue e propague um resultado
    parcial à mão — e propagação à mão é onde se perde uma verificação sem perceber.
    """

    def __init__(self, erro: ErroDeCarga) -> None:
        super().__init__(erro.mensagem)
        self.erro = erro


def _rejeitar(erro: ErroDeCarga) -> NoReturn:
    """Aborta a carga inteira com o erro dado."""
    raise _Rejeicao(erro)


# --------------------------------------------------------------------------- #
# Índice de linhas
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Bloco:
    """Linha do cabeçalho de um bloco e linha de cada chave declarada nele."""

    linha: int
    campos: Mapping[str, int]

    def linha_de(self, campo: str) -> int:
        """Linha da chave, ou a melhor aproximação disponível acima dela.

        A busca sobe o caminho pontilhado antes de desistir: ``dicas.L3`` ausente cai na linha
        do cabeçalho ``[item.dicas]``, e só um item sem tabela de dicas nenhuma cai na linha
        do ``[[item]]``. A diferença é prática — apontar a tabela de dicas põe quem corrige no
        lugar onde falta a linha, em vez de no começo de um item de trinta linhas.
        """
        caminho = campo
        while caminho:
            if caminho in self.campos:
                return self.campos[caminho]
            caminho = caminho.rpartition(".")[0]
        return self.linha


_BLOCO_DESCONHECIDO: Final = _Bloco(linha=1, campos=MappingProxyType({}))
"""Recurso de último caso, se a varredura e o interpretador discordarem na contagem."""


@dataclass(frozen=True)
class _Indice:
    """Linhas das construções de um arquivo, na ordem em que foram declaradas."""

    itens: tuple[_Bloco, ...]
    relacoes: tuple[_Bloco, ...]
    raiz: Mapping[str, int]

    def item(self, ordinal: int) -> _Bloco:
        """Bloco do item de índice dado na ordem de declaração."""
        return self.itens[ordinal] if ordinal < len(self.itens) else _BLOCO_DESCONHECIDO

    def relacao(self, ordinal: int) -> _Bloco:
        """Bloco da relação de índice dado na ordem de declaração."""
        return self.relacoes[ordinal] if ordinal < len(self.relacoes) else _BLOCO_DESCONHECIDO


def _fim_de_bloco(texto: str, i: int, linha: int) -> tuple[int, int]:
    """Posição após uma cadeia multilinha e a linha em que ela termina.

    Trata as duas armadilhas do TOML multilinha: a barra invertida de continuação, cuja quebra
    de linha também conta, e a sequência de aspas maior que três, em que o delimitador é o
    **último** trio da sequência.
    """
    aspa = texto[i]
    literal = aspa == "'"
    j = i + 3
    n = len(texto)
    while j < n:
        caractere = texto[j]
        if caractere == "\n":
            linha += 1
            j += 1
        elif not literal and caractere == "\\":
            if j + 1 < n and texto[j + 1] == "\n":
                linha += 1
            j += 2
        elif caractere == aspa:
            k = j
            while k < n and texto[k] == aspa:
                k += 1
            if k - j >= 3:
                return k, linha
            j = k
        else:
            j += 1
    return n, linha


def _fim_de_cadeia(texto: str, i: int) -> int:
    """Posição após uma cadeia de uma linha, que não atravessa a quebra de linha."""
    aspa = texto[i]
    literal = aspa == "'"
    j = i + 1
    n = len(texto)
    while j < n:
        caractere = texto[j]
        if caractere == "\n":
            return j
        if not literal and caractere == "\\":
            j += 2
            continue
        if caractere == aspa:
            return j + 1
        j += 1
    return n


def _ler_cabecalho(texto: str, i: int) -> tuple[str, bool, int]:
    """Nome do cabeçalho de tabela, se é lista de tabelas, e a posição após ele."""
    duplo = texto.startswith("[[", i)
    abertura = i + (2 if duplo else 1)
    fechamento = texto.find("]", abertura)
    if fechamento == -1:
        return "", duplo, len(texto)
    nome = texto[abertura:fechamento].strip()
    fim = fechamento + (2 if duplo and texto.startswith("]]", fechamento) else 1)
    return nome, duplo, fim


def _ler_chave(texto: str, i: int) -> tuple[str | None, int]:
    """Nome da chave que começa em ``i``, ou ``None`` se ali não há chave seguida de ``=``."""
    j = i
    n = len(texto)
    partes: list[str] = []
    atual: list[str] = []
    while j < n:
        caractere = texto[j]
        if caractere in _CARACTERES_DE_CHAVE:
            atual.append(caractere)
        elif caractere == ".":
            partes.append("".join(atual))
            atual = []
        elif caractere in " \t":
            pass
        else:
            break
        j += 1
    partes.append("".join(atual))
    if j >= n or texto[j] != "=" or not all(partes):
        return None, i + 1
    return ".".join(partes), j + 1


def _indexar(texto: str) -> _Indice:
    """Linha de cada cabeçalho e de cada chave de um texto já aceito pelo interpretador.

    A varredura é de caracteres, e não de linhas, porque linha é justamente o que não se pode
    presumir: dentro de uma cadeia de bloco — que é como enunciado e dicas são escritos — uma
    linha de conteúdo pode começar com ``[`` e passaria por cabeçalho de tabela. O mesmo vale
    para listas quebradas em várias linhas, de onde vem o controle de profundidade.
    """
    itens: list[dict[str, int]] = []
    linhas_de_item: list[int] = []
    relacoes: list[dict[str, int]] = []
    linhas_de_relacao: list[int] = []
    raiz: dict[str, int] = {}
    alvo: dict[str, int] | None = None
    prefixo = ""
    linha = 1
    profundidade = 0
    inicio_de_linha = True
    i = 0
    n = len(texto)
    while i < n:
        caractere = texto[i]
        if caractere == "\n":
            linha += 1
            inicio_de_linha = True
            i += 1
            continue
        if caractere in " \t\r":
            i += 1
            continue
        if caractere == "#":
            while i < n and texto[i] != "\n":
                i += 1
            continue
        if texto.startswith('"""', i) or texto.startswith("'''", i):
            i, linha = _fim_de_bloco(texto, i, linha)
            inicio_de_linha = False
            continue
        if caractere in "\"'":
            i = _fim_de_cadeia(texto, i)
            inicio_de_linha = False
            continue
        if caractere == "[" and profundidade == 0 and inicio_de_linha:
            nome, duplo, i = _ler_cabecalho(texto, i)
            raiz.setdefault(nome.split(".", 1)[0], linha)
            alvo, prefixo = _acolher_cabecalho(
                nome, duplo, linha, itens, linhas_de_item, relacoes, linhas_de_relacao
            )
            inicio_de_linha = False
            continue
        if caractere in "[{":
            profundidade += 1
            inicio_de_linha = False
            i += 1
            continue
        if caractere in "]}":
            profundidade = max(0, profundidade - 1)
            inicio_de_linha = False
            i += 1
            continue
        if inicio_de_linha and profundidade == 0 and caractere in _CARACTERES_DE_CHAVE:
            nome_da_chave, i = _ler_chave(texto, i)
            inicio_de_linha = False
            if nome_da_chave is not None:
                destino = raiz if alvo is None else alvo
                destino.setdefault(prefixo + nome_da_chave, linha)
            continue
        inicio_de_linha = False
        i += 1
    return _Indice(
        itens=tuple(
            _Bloco(linha=linha_do_bloco, campos=MappingProxyType(campos))
            for linha_do_bloco, campos in zip(linhas_de_item, itens, strict=True)
        ),
        relacoes=tuple(
            _Bloco(linha=linha_do_bloco, campos=MappingProxyType(campos))
            for linha_do_bloco, campos in zip(linhas_de_relacao, relacoes, strict=True)
        ),
        raiz=MappingProxyType(raiz),
    )


def _acolher_cabecalho(
    nome: str,
    duplo: bool,
    linha: int,
    itens: list[dict[str, int]],
    linhas_de_item: list[int],
    relacoes: list[dict[str, int]],
    linhas_de_relacao: list[int],
) -> tuple[dict[str, int] | None, str]:
    """Abre ou retoma o bloco a que as chaves seguintes pertencem, e o prefixo delas.

    ``[[item]]`` abre um bloco novo; ``[item.dicas]`` retoma o último item com prefixo
    ``dicas.``, que é como a linha de uma dica específica fica conhecida. Cabeçalho fora do
    vocabulário não recebe bloco: as chaves dele não têm onde ser registradas, e a estrutura
    da raiz vai recusá-lo de todo modo.
    """
    raiz_do_nome, _, resto = nome.partition(".")
    if raiz_do_nome == TABELA_DE_ITEM:
        return _acolher_em(duplo, resto, itens, linhas_de_item, linha)
    if raiz_do_nome == TABELA_DE_RELACAO:
        return _acolher_em(duplo, resto, relacoes, linhas_de_relacao, linha)
    return None, ""


def _acolher_em(
    duplo: bool,
    resto: str,
    blocos: list[dict[str, int]],
    linhas: list[int],
    linha: int,
) -> tuple[dict[str, int] | None, str]:
    """Bloco e prefixo para um cabeçalho da família ``item`` ou ``relacao``."""
    if duplo and not resto:
        blocos.append({})
        linhas.append(linha)
        return blocos[-1], ""
    if resto and blocos:
        blocos[-1].setdefault(resto, linha)
        return blocos[-1], f"{resto}."
    return None, ""


# --------------------------------------------------------------------------- #
# Leitura de arquivo
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Arquivo:
    """Um arquivo lido, interpretado e indexado."""

    caminho: Path
    documento: Mapping[str, object]
    indice: _Indice


def _ler_arquivo(caminho: Path) -> _Arquivo:
    """Lê, decodifica, interpreta e indexa um arquivo de definição.

    A marca de ordem de bytes é recusada explicitamente em vez de descartada: a gramática
    declara UTF-8 **sem** BOM, o serializador canônico escreve sem BOM, e aceitar a marca
    aqui faria o arquivo mudar de bytes entre uma leitura e uma reescrita sem que nada no
    conteúdo tivesse mudado — a ida e volta de R3.5 deixaria de valer por um detalhe
    invisível na tela.
    """
    try:
        bruto = caminho.read_bytes()
    except OSError as erro:
        _rejeitar(
            ErroDeGramatica.de(
                caminho,
                None,
                "arquivo",
                f"arquivo de definição não pôde ser lido ({erro.strerror or type(erro).__name__})",
            )
        )
    if bruto.startswith(b"\xef\xbb\xbf"):
        _rejeitar(
            ErroDeGramatica.de(
                caminho, 1, "arquivo", "arquivo começa com marca de ordem de bytes; a gramática exige UTF-8 sem BOM"
            )
        )
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError as erro:
        _rejeitar(
            ErroDeGramatica.de(
                caminho,
                bruto[: erro.start].count(b"\n") + 1,
                "arquivo",
                "arquivo não está em UTF-8 válido",
            )
        )
    texto = texto.replace("\r\n", "\n")
    try:
        documento = tomllib.loads(texto)
    except tomllib.TOMLDecodeError as erro:
        _rejeitar(
            ErroDeGramatica.de(
                caminho, _linha_do_interpretador(erro), "arquivo", f"sintaxe TOML inválida: {erro}"
            )
        )
    return _Arquivo(caminho=caminho, documento=documento, indice=_indexar(texto))


def _linha_do_interpretador(erro: tomllib.TOMLDecodeError) -> int | None:
    """Linha do erro de sintaxe, do atributo quando existe e da mensagem quando não.

    ``TOMLDecodeError`` só passou a expor ``lineno`` no Python 3.14; no 3.13, que é a versão
    fixada por D6, a posição vem no texto da mensagem. Ler o atributo primeiro mantém o
    código correto nas duas versões sem depender de qual está instalada.
    """
    do_atributo = getattr(erro, "lineno", None)
    if isinstance(do_atributo, int):
        return do_atributo
    encontrado = _LINHA_DO_INTERPRETADOR.search(str(erro))
    return int(encontrado.group(1)) if encontrado is not None else None


# --------------------------------------------------------------------------- #
# Leitura de campos
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Leitor:
    """Leitor dos campos de um bloco, com o que é preciso para localizar o erro.

    ``identificador`` é o ``id`` do item quando já conhecido, e vazio enquanto não é: os erros
    que nomeiam o item só existem depois que o ``id`` foi lido e aceito, e é por isso que ele
    é o primeiro campo da ordem de verificação.
    """

    arquivo: Path
    bloco: _Bloco
    dados: Mapping[str, object]
    identificador: str = ""

    def com_identificador(self, identificador: str) -> _Leitor:
        """Cópia do leitor que já sabe de qual item está falando."""
        return _Leitor(arquivo=self.arquivo, bloco=self.bloco, dados=self.dados, identificador=identificador)

    def linha_de(self, campo: str) -> int:
        """Linha do campo, ou a do cabeçalho do bloco quando o campo não foi escrito."""
        return self.bloco.linha_de(campo)

    def recusar(self, campo: str, motivo: str) -> NoReturn:
        """Aborta a carga com erro de gramática no campo dado."""
        _rejeitar(ErroDeGramatica.de(self.arquivo, self.linha_de(campo), campo, motivo))

    def presente(self, campo: str) -> bool:
        """Se o campo foi escrito no arquivo."""
        return campo in self.dados

    def obrigatorio(self, campo: str) -> object:
        """Valor do campo, recusando o arquivo quando ele está ausente."""
        if campo not in self.dados:
            self.recusar(campo, "campo obrigatório ausente")
        return self.dados[campo]

    def texto(self, campo: str) -> str:
        """Texto não vazio, obrigatório."""
        valor = self.obrigatorio(campo)
        if not isinstance(valor, str):
            self.recusar(campo, f"esperado texto; veio {nome_do_tipo(valor)}")
        if not valor.strip():
            self.recusar(campo, "texto vazio")
        return valor

    def texto_opcional(self, campo: str) -> str | None:
        """Texto não vazio, ou ``None`` quando o campo não foi escrito."""
        if campo not in self.dados:
            return None
        return self.texto(campo)

    def inteiro(self, campo: str) -> int:
        """Inteiro obrigatório. ``True`` e ``False`` não contam como inteiro."""
        valor = self.obrigatorio(campo)
        if isinstance(valor, bool) or not isinstance(valor, int):
            self.recusar(campo, f"esperado inteiro; veio {nome_do_tipo(valor)}")
        return valor

    def booleano(self, campo: str, padrao: bool) -> bool:
        """Booleano com valor padrão quando o campo não foi escrito."""
        if campo not in self.dados:
            return padrao
        valor = self.dados[campo]
        if not isinstance(valor, bool):
            self.recusar(campo, f"esperado booleano; veio {nome_do_tipo(valor)}")
        return valor

    def lista(self, campo: str) -> tuple[object, ...]:
        """Lista obrigatória, sem exigir nada dos elementos."""
        valor = self.obrigatorio(campo)
        if not isinstance(valor, list):
            self.recusar(campo, f"esperada lista; veio {nome_do_tipo(valor)}")
        return tuple(valor)

    def conjunto_de_textos(self, campo: str) -> tuple[str, ...]:
        """Coleção de textos não vazios, ordenada e sem repetição, ou vazia se ausente.

        Ordenar e recusar repetição não é capricho de forma: a coleção é um **conjunto**
        escrito como lista, e a ida e volta de R3.4 e R3.5 exige que ler e reescrever não
        mude nem a ordem nem o tamanho. Repetição silenciosamente descartada mudaria o
        tamanho.
        """
        if campo not in self.dados:
            return ()
        valores: list[str] = []
        for elemento in self.lista(campo):
            if not isinstance(elemento, str):
                self.recusar(campo, f"esperado texto em cada elemento; veio {nome_do_tipo(elemento)}")
            if not elemento.strip():
                self.recusar(campo, "elemento de texto vazio")
            if elemento in valores:
                self.recusar(campo, f"elemento repetido: {valor_citavel(campo, elemento)}")
            valores.append(elemento)
        return tuple(sorted(valores))

    def conjunto_de_conjuntos(self, campo: str) -> tuple[tuple[str, ...], ...]:
        """Coleção de coleções de textos, ordenada e sem repetição em nenhum dos dois níveis."""
        if campo not in self.dados:
            return ()
        conjuntos: list[tuple[str, ...]] = []
        for elemento in self.lista(campo):
            if not isinstance(elemento, list):
                self.recusar(campo, f"esperada lista de textos em cada elemento; veio {nome_do_tipo(elemento)}")
            interno: list[str] = []
            for termo in elemento:
                if not isinstance(termo, str):
                    self.recusar(campo, f"esperado texto em cada termo; veio {nome_do_tipo(termo)}")
                if not termo.strip():
                    self.recusar(campo, "termo vazio")
                if termo in interno:
                    self.recusar(campo, f"termo repetido: {valor_citavel(campo, termo)}")
                interno.append(termo)
            if not interno:
                self.recusar(campo, "conjunto vazio; cada conjunto declara ao menos um termo")
            ordenado = tuple(sorted(interno))
            if ordenado in conjuntos:
                self.recusar(campo, "conjunto repetido")
            conjuntos.append(ordenado)
        return tuple(sorted(conjuntos))

    def decimal(self, campo: str) -> Decimal:
        """Decimal escrito como cadeia, nunca como ponto flutuante de TOML.

        O ponto flutuante é recusado de propósito, e a tolerância é o motivo: ``0.05`` em base
        2 é ``0,05000000000000000277...``, e a tolerância decide o acerto de item de
        fronteira (R4.2). Item de fronteira é exatamente o que separa acerto de erro na TAI,
        então a diferença não é acadêmica.
        """
        valor = self.obrigatorio(campo)
        if isinstance(valor, float):
            self.recusar(
                campo,
                'esperada cadeia decimal (por exemplo "0.05"); ponto flutuante de TOML é recusado '
                "porque a base 2 não representa o valor decimal exato",
            )
        if not isinstance(valor, str):
            self.recusar(campo, f"esperada cadeia decimal; veio {nome_do_tipo(valor)}")
        if PADRAO_DE_DECIMAL.match(valor) is None:
            self.recusar(campo, "esperada cadeia decimal em notação simples, com ponto como separador")
        try:
            numero = Decimal(valor)
        except InvalidOperation:
            self.recusar(campo, "cadeia não representa um número decimal")
        if not numero.is_finite():
            self.recusar(campo, "esperado número finito")
        return numero

    def tabela(self, campo: str) -> Mapping[str, object] | None:
        """Subtabela do bloco, ou ``None`` quando o campo não foi escrito."""
        if campo not in self.dados:
            return None
        valor = self.dados[campo]
        if not isinstance(valor, dict):
            self.recusar(campo, f"esperada tabela; veio {nome_do_tipo(valor)}")
        return {str(chave): conteudo for chave, conteudo in valor.items()}

    def identificador_de(self, campo: str) -> str:
        """Texto na forma de identificador: ASCII, sem espaço, até 64 caracteres."""
        valor = self.texto(campo)
        if PADRAO_DE_IDENTIFICADOR.match(valor) is None:
            self.recusar(
                campo,
                f"{valor_citavel(campo, valor)} não é identificador válido: use de 1 a 64 caracteres "
                "ASCII entre letras, dígitos, ponto, hífen e sublinhado, começando por letra ou dígito",
            )
        return valor

    def sem_campos_estranhos(self, conhecidos: frozenset[str], rotulo: str) -> None:
        """Recusa chave fora do vocabulário, que de outro modo passaria por campo ausente.

        É a verificação que transforma erro de digitação em erro de carga. Sem ela,
        ``tolerância`` escrito com acento viraria um campo desconhecido ignorado e um item
        numérico **sem tolerância** — perfil incompleto apresentado como item válido.
        """
        for chave in self.dados:
            if chave not in conhecidos:
                _rejeitar(
                    ErroDeGramatica.de(
                        self.arquivo,
                        self.linha_de(chave),
                        chave,
                        f"chave desconhecida em {rotulo}; a gramática não a declara",
                    )
                )


# --------------------------------------------------------------------------- #
# Leitura de item
# --------------------------------------------------------------------------- #


def _ler_item(arquivo: _Arquivo, ordinal: int, dados: Mapping[str, object]) -> Item:
    """Interpreta um item declarado, na ordem fixa de verificação de campos."""
    leitor = _Leitor(arquivo=arquivo.caminho, bloco=arquivo.indice.item(ordinal), dados=dados)
    leitor.sem_campos_estranhos(CAMPOS_DE_ITEM, "item")
    identificador = leitor.identificador_de("id")
    leitor = leitor.com_identificador(identificador)

    enunciado = leitor.texto("enunciado")
    habilidade_alvo = leitor.identificador_de("habilidade_alvo")
    dificuldade = _na_faixa(
        leitor,
        "dificuldade",
        leitor.inteiro("dificuldade"),
        DIFICULDADE_MINIMA,
        DIFICULDADE_MAXIMA,
        f"de {DIFICULDADE_MINIMA} a {DIFICULDADE_MAXIMA}",
    )
    tamanho_max_resposta = _na_faixa(
        leitor, "tamanho_max_resposta", leitor.inteiro("tamanho_max_resposta"), 1, None, "de 1 em diante"
    )
    tipo_gabarito = _ler_tipo_de_gabarito(leitor)
    gabarito = leitor.texto("gabarito")

    tolerancia = _ler_tolerancia(leitor, tipo_gabarito)
    unidade = leitor.texto_opcional("unidade")
    sinonimos_unidade = leitor.conjunto_de_textos("sinonimos_unidade")
    if sinonimos_unidade and unidade is None:
        leitor.recusar("sinonimos_unidade", "sinônimos declarados sem `unidade`")
    variacoes_gabarito = leitor.conjunto_de_textos("variacoes_gabarito")
    termos_essenciais = _ler_termos_essenciais(leitor, tipo_gabarito)
    incognita = leitor.identificador_de("incognita") if leitor.presente("incognita") else None

    etapas_permitidas = _ler_etapas(leitor)
    transferencia = leitor.booleano("transferencia", padrao=False)
    dicas = _ler_dicas(leitor)

    try:
        return Item(
            id=identificador,
            enunciado=enunciado,
            habilidade_alvo=habilidade_alvo,
            dificuldade=dificuldade,
            tamanho_max_resposta=tamanho_max_resposta,
            tipo_gabarito=tipo_gabarito,
            gabarito=gabarito,
            tolerancia=tolerancia,
            unidade=unidade,
            sinonimos_unidade=sinonimos_unidade,
            variacoes_gabarito=variacoes_gabarito,
            termos_essenciais=termos_essenciais,
            incognita=incognita,
            etapas_permitidas=etapas_permitidas,
            transferencia=transferencia,
            dicas=MappingProxyType(dicas),
        )
    except ValueError as erro:  # pragma: no cover - rede de segurança
        # A invariante do modelo e as verificações acima afirmam a mesma coisa por dois
        # caminhos. Se um dia discordarem, a carga falha fechada em vez de publicar o item.
        leitor.recusar("item", f"invariante do item recusada: {erro}")


def _na_faixa(
    leitor: _Leitor, campo: str, valor: int, minimo: int, maximo: int | None, faixa: str
) -> int:
    """Valor dentro da faixa declarada, ou rejeição que nomeia o valor e a faixa."""
    if valor < minimo or (maximo is not None and valor > maximo):
        _rejeitar(
            ErroDeFaixa.de(leitor.arquivo, leitor.linha_de(campo), leitor.identificador, campo, valor, faixa)
        )
    return valor


def _ler_tipo_de_gabarito(leitor: _Leitor) -> TipoGabarito:
    """Tipo de gabarito declarado, entre os três da gramática."""
    valor = leitor.texto("tipo_gabarito")
    try:
        return TipoGabarito(valor)
    except ValueError:
        aceitos = ", ".join(tipo.value for tipo in TipoGabarito)
        leitor.recusar("tipo_gabarito", f"tipo de gabarito desconhecido; a gramática declara: {aceitos}")


def _ler_tolerancia(leitor: _Leitor, tipo_gabarito: TipoGabarito) -> Decimal | None:
    """Tolerância numérica, obrigatória em gabarito numérico e proibida fora dele (R2.8)."""
    if tipo_gabarito is not TipoGabarito.NUMERICO:
        if leitor.presente("tolerancia"):
            leitor.recusar(
                "tolerancia",
                f"tolerância só tem sentido em gabarito numérico; este item é {tipo_gabarito.value!r}",
            )
        return None
    if not leitor.presente("tolerancia"):
        _rejeitar(
            ErroDePerfilIncompleto.de(
                leitor.arquivo,
                leitor.linha_de("tolerancia"),
                leitor.identificador,
                "tolerancia",
                tipo_gabarito.value,
            )
        )
    tolerancia = leitor.decimal("tolerancia")
    if tolerancia < 0:
        _rejeitar(
            ErroDeFaixa.de(
                leitor.arquivo,
                leitor.linha_de("tolerancia"),
                leitor.identificador,
                "tolerancia",
                str(tolerancia),
                "valor real não negativo",
            )
        )
    return tolerancia


def _ler_termos_essenciais(leitor: _Leitor, tipo_gabarito: TipoGabarito) -> tuple[tuple[str, ...], ...]:
    """Conjuntos de termos essenciais, obrigatórios em gabarito textual (R2.11, R7.6)."""
    termos = leitor.conjunto_de_conjuntos("termos_essenciais")
    if tipo_gabarito is TipoGabarito.TEXTUAL and not termos:
        _rejeitar(
            ErroDePerfilIncompleto.de(
                leitor.arquivo,
                leitor.linha_de("termos_essenciais"),
                leitor.identificador,
                "termos_essenciais",
                tipo_gabarito.value,
            )
        )
    return termos


def _ler_etapas(leitor: _Leitor) -> frozenset[Etapa]:
    """Conjunto não vazio de etapas permitidas (R2.4).

    Ausência e lista vazia recebem o **mesmo** erro, porque descrevem o mesmo defeito: item
    que nenhuma etapa pode apresentar. Dar erro de gramática ao campo ausente esconderia a
    exigência de R2.4 atrás de uma mensagem genérica.
    """
    if not leitor.presente("etapas_permitidas"):
        _rejeitar(
            ErroDeEtapasVazias.de(leitor.arquivo, leitor.linha_de("etapas_permitidas"), leitor.identificador)
        )
    nomes = leitor.conjunto_de_textos("etapas_permitidas")
    if not nomes:
        _rejeitar(
            ErroDeEtapasVazias.de(leitor.arquivo, leitor.linha_de("etapas_permitidas"), leitor.identificador)
        )
    etapas: list[Etapa] = []
    for nome in nomes:
        try:
            etapas.append(Etapa(nome))
        except ValueError:
            aceitas = ", ".join(etapa.value for etapa in Etapa)
            leitor.recusar("etapas_permitidas", f"etapa desconhecida {nome!r}; a gramática declara: {aceitas}")
    return frozenset(etapas)


def _ler_dicas(leitor: _Leitor) -> dict[Nivel, str]:
    """Exatamente uma dica pré-escrita não vazia por nível de L1 a L4 (R2.1)."""
    tabela = leitor.tabela(TABELA_DE_DICAS) or {}
    conhecidos = frozenset(nivel.name for nivel in Nivel)
    for chave in tabela:
        if chave not in conhecidos:
            leitor.recusar(
                f"{TABELA_DE_DICAS}.{chave}",
                f"nível de dica desconhecido; a gramática declara: {', '.join(sorted(conhecidos))}",
            )
    dicas: dict[Nivel, str] = {}
    for nivel in Nivel:
        valor = tabela.get(nivel.name)
        if not isinstance(valor, str) or not valor.strip():
            _rejeitar(
                ErroDeDicaAusente.de(
                    leitor.arquivo,
                    leitor.linha_de(f"{TABELA_DE_DICAS}.{nivel.name}"),
                    leitor.identificador,
                    nivel,
                )
            )
        dicas[nivel] = valor
    return dicas


# --------------------------------------------------------------------------- #
# Leitura de relação
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _RelacaoLida:
    """Relação com a procedência que os erros de R2.6 e R2.9 precisam nomear."""

    relacao: Relacao
    arquivo: Path
    bloco: _Bloco

    @property
    def tipo(self) -> TipoDeRelacao:
        """Natureza declarada da relação."""
        return self.relacao.tipo

    @property
    def par(self) -> frozenset[str]:
        """O par de itens, sem direção, para a unicidade de relação por par."""
        return frozenset({self.relacao.item_origem, self.relacao.item_destino})


def _ler_relacao(arquivo: _Arquivo, ordinal: int, dados: Mapping[str, object]) -> _RelacaoLida:
    """Interpreta uma relação declarada."""
    bloco = arquivo.indice.relacao(ordinal)
    leitor = _Leitor(arquivo=arquivo.caminho, bloco=bloco, dados=dados)
    leitor.sem_campos_estranhos(frozenset(CAMPOS_DE_RELACAO), "relação")
    origem = leitor.identificador_de("item_origem")
    destino = leitor.identificador_de("item_destino")
    bruto = leitor.texto("tipo")
    tipo = tipo_de_relacao(bruto)
    if tipo is None:
        leitor.recusar("tipo", f"tipo de relação desconhecido; a gramática declara: {', '.join(TIPOS_DE_RELACAO)}")
    if origem == destino:
        leitor.recusar("item_destino", f"a relação de {origem!r} aponta para ele mesmo")
    return _RelacaoLida(
        relacao=Relacao(item_origem=origem, item_destino=destino, tipo=tipo), arquivo=arquivo.caminho, bloco=bloco
    )


# --------------------------------------------------------------------------- #
# Verificações entre itens e relações
# --------------------------------------------------------------------------- #


def _verificar_relacoes(relacoes: Sequence[_RelacaoLida], por_id: Mapping[str, Item]) -> None:
    """Garante que toda relação liga dois itens declarados, e no máximo uma por par.

    Uma segunda relação sobre o mesmo par — nas duas direções ou com os dois tipos — não é
    redundância inofensiva: ``equivalente`` e ``transferencia`` sobre o mesmo par são
    afirmações contraditórias sobre a mesma dupla de itens, e qual delas valeria passaria a
    depender da ordem de leitura.
    """
    vistos: dict[frozenset[str], _RelacaoLida] = {}
    for lida in relacoes:
        leitor = _Leitor(arquivo=lida.arquivo, bloco=lida.bloco, dados={})
        for campo, referencia in (
            ("item_origem", lida.relacao.item_origem),
            ("item_destino", lida.relacao.item_destino),
        ):
            if referencia not in por_id:
                leitor.recusar(campo, f"{referencia!r} não corresponde a nenhum item declarado")
        anterior = vistos.get(lida.par)
        if anterior is not None:
            leitor.recusar(
                "tipo",
                f"o par {sorted(lida.par)} já tem relação {anterior.tipo!r} declarada em "
                f"{anterior.arquivo}:{anterior.bloco.linha}; cada par admite no máximo uma relação",
            )
        vistos[lida.par] = lida


def _candidatos(
    item: Item, relacoes: Sequence[_RelacaoLida], tipo: TipoDeRelacao, por_id: Mapping[str, Item]
) -> list[Item]:
    """Itens ligados a este por uma relação do tipo dado, em qualquer das duas direções.

    A direção é dado do arquivo, mas não é critério de pareamento: isomorfismo estrutural é
    simétrico por natureza, e exigir que o autor escreva a relação a partir do item praticado
    criaria uma regra arbitrária cuja violação produziria a mensagem errada — "falta
    equivalente" para um par que está declarado, só de trás para frente. Em
    ``transferencia``, a direção segue informativa sem precisar ser normativa: o que qualifica
    o candidato é ``transferencia = true`` declarado **nele**.
    """
    encontrados: list[Item] = []
    for lida in relacoes:
        if lida.tipo != tipo:
            continue
        if lida.relacao.item_origem == item.id:
            encontrados.append(por_id[lida.relacao.item_destino])
        elif lida.relacao.item_destino == item.id:
            encontrados.append(por_id[lida.relacao.item_origem])
    return encontrados


def _equivalente_qualifica(praticado: Item, candidato: Item) -> bool:
    """Se o candidato cumpre o isomorfismo estrutural que R2.2 exige do equivalente."""
    return (
        candidato.id != praticado.id
        and candidato.habilidade_alvo == praticado.habilidade_alvo
        and candidato.dificuldade == praticado.dificuldade
        and candidato.enunciado != praticado.enunciado
    )


def _transferencia_qualifica(praticado: Item, candidato: Item) -> bool:
    """Se o candidato é item de transferência da mesma habilidade alvo (R2.2)."""
    return (
        candidato.id != praticado.id
        and candidato.habilidade_alvo == praticado.habilidade_alvo
        and candidato.transferencia
    )


def _verificar_associacoes(
    itens: Sequence[Item], relacoes: Sequence[_RelacaoLida], por_id: Mapping[str, Item], locais: Mapping[str, _Leitor]
) -> None:
    """Exige equivalente e transferência de todo item apresentado na prática assistida (R2.2, R2.6).

    A exigência vale só para o item praticado, e a razão está no que se mede: é o desempenho
    nele que vai ser comparado com o desempenho sem IA do mesmo ciclo. Sem equivalente não há
    com o que comparar; sem transferência não há TT. Relação declarada que não cumpre o
    critério conta como **ausência**, nunca como pareamento parcial, e o erro diz quantas
    relações foram examinadas e reprovadas.
    """
    for item in itens:
        if not item.e_praticado:
            continue
        leitor = locais[item.id]
        for associacao, qualifica in (
            (EQUIVALENTE, _equivalente_qualifica),
            (TRANSFERENCIA, _transferencia_qualifica),
        ):
            candidatos = _candidatos(item, relacoes, associacao, por_id)
            if not any(qualifica(item, candidato) for candidato in candidatos):
                _rejeitar(
                    ErroDeAssociacaoAusente.de(
                        leitor.arquivo,
                        leitor.linha_de("id"),
                        item.id,
                        associacao,
                        len(candidatos),
                    )
                )


def _verificar_conflitos(relacoes: Sequence[_RelacaoLida], por_id: Mapping[str, Item]) -> None:
    """Recusa item de transferência marcado como isomorfo a item praticado da mesma habilidade (R2.9).

    As duas direções são examinadas. A relação é dirigida no dado, mas o conflito não depende
    de quem foi escrito como origem: marcar o par como isomorfo de trás para frente produz a
    mesma repetição disfarçada de transferência, e a TT infla do mesmo jeito.
    """
    for lida in relacoes:
        if lida.tipo != EQUIVALENTE:
            continue
        origem = por_id[lida.relacao.item_origem]
        destino = por_id[lida.relacao.item_destino]
        for candidato, praticado in ((origem, destino), (destino, origem)):
            if (
                candidato.transferencia
                and praticado.e_praticado
                and candidato.habilidade_alvo == praticado.habilidade_alvo
            ):
                _rejeitar(
                    ErroDeConflitoDeRelacao.de(
                        lida.arquivo,
                        lida.bloco.linha_de("tipo"),
                        candidato.id,
                        praticado.id,
                        praticado.habilidade_alvo,
                    )
                )


# --------------------------------------------------------------------------- #
# Carga
# --------------------------------------------------------------------------- #


def carregar(caminhos: Sequence[Path]) -> ResultadoDeCarga:
    """Carrega o banco de itens dos arquivos dados, por inteiro ou nada (R3.1, §7.2).

    Devolve ``CargaConcluida`` com todos os itens e relações, ordenados, ou o primeiro
    ``ErroDeCarga`` na ordem fixa de verificação descrita no cabeçalho do módulo. Nenhum item
    é publicado quando qualquer arquivo falha, mesmo que os outros estejam perfeitos: a
    atomicidade é a diferença entre um banco incompleto medindo o conjunto errado e uma carga
    que não acontece.
    """
    try:
        return _carregar(caminhos)
    except _Rejeicao as rejeicao:
        return rejeicao.erro


def _carregar(caminhos: Sequence[Path]) -> CargaConcluida:
    """Corpo da carga, que sinaliza rejeição por exceção interna."""
    itens: list[Item] = []
    locais: dict[str, _Leitor] = {}
    relacoes: list[_RelacaoLida] = []

    for caminho in caminhos:
        arquivo = _ler_arquivo(caminho)
        _verificar_raiz(arquivo)
        for ordinal, dados in enumerate(_blocos(arquivo, TABELA_DE_ITEM)):
            item = _ler_item(arquivo, ordinal, dados)
            leitor = _Leitor(arquivo=caminho, bloco=arquivo.indice.item(ordinal), dados=dados, identificador=item.id)
            anterior = locais.get(item.id)
            if anterior is not None:
                _rejeitar(
                    ErroDeIdentificadorDuplicado.de(
                        caminho,
                        leitor.linha_de("id"),
                        item.id,
                        anterior.arquivo,
                        anterior.linha_de("id"),
                    )
                )
            locais[item.id] = leitor
            itens.append(item)
        for ordinal, dados in enumerate(_blocos(arquivo, TABELA_DE_RELACAO)):
            relacoes.append(_ler_relacao(arquivo, ordinal, dados))

    por_id = {item.id: item for item in itens}
    _verificar_relacoes(relacoes, por_id)
    _verificar_associacoes(itens, relacoes, por_id, locais)
    _verificar_conflitos(relacoes, por_id)

    return CargaConcluida(
        itens=tuple(sorted(itens, key=lambda item: item.id)),
        relacoes=tuple(
            sorted(
                (lida.relacao for lida in relacoes),
                key=lambda relacao: (relacao.item_origem, relacao.item_destino, relacao.tipo),
            )
        ),
    )


def _verificar_raiz(arquivo: _Arquivo) -> None:
    """Recusa chave de nível raiz fora de ``item`` e ``relacao``, e arquivo sem conteúdo."""
    for chave in arquivo.documento:
        if chave not in CHAVES_DA_RAIZ:
            _rejeitar(
                ErroDeGramatica.de(
                    arquivo.caminho,
                    arquivo.indice.raiz.get(chave, 1),
                    chave,
                    f"chave de nível raiz desconhecida; a gramática declara: {', '.join(sorted(CHAVES_DA_RAIZ))}",
                )
            )
    if not arquivo.documento:
        _rejeitar(
            ErroDeGramatica.de(
                arquivo.caminho, 1, "arquivo", "arquivo de definição sem nenhum item nem relação declarados"
            )
        )


def _blocos(arquivo: _Arquivo, chave: str) -> tuple[Mapping[str, object], ...]:
    """Lista de tabelas de uma chave da raiz, recusando forma que não seja lista de tabelas."""
    if chave not in arquivo.documento:
        return ()
    valor = arquivo.documento[chave]
    linha = arquivo.indice.raiz.get(chave, 1)
    if not isinstance(valor, list):
        _rejeitar(
            ErroDeGramatica.de(
                arquivo.caminho, linha, chave, f"esperada lista de tabelas `[[{chave}]]`; veio {nome_do_tipo(valor)}"
            )
        )
    blocos: list[Mapping[str, object]] = []
    for elemento in valor:
        if not isinstance(elemento, dict):
            _rejeitar(
                ErroDeGramatica.de(
                    arquivo.caminho,
                    linha,
                    chave,
                    f"esperada tabela em cada `[[{chave}]]`; veio {nome_do_tipo(elemento)}",
                )
            )
        blocos.append({str(nome): conteudo for nome, conteudo in elemento.items()})
    return tuple(blocos)
