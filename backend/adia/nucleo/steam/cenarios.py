"""Carga de ``data/steam/`` e correção das partes numéricas do projeto STEAM (R13.1 a R13.4).

A gramática é a de ``docs/gramatica-steam.md``; este módulo a aplica e recusa o conteúdo
inteiro na primeira violação, nomeando arquivo e campo. Nunca um conteúdo parcial: um cenário
que carregasse sem a rubrica tornaria a avaliação de R13.4 impossível de registrar.

Puro: lê os arquivos que recebe, sem relógio, sem rede e sem IA.

shortcut: a recusa nomeia arquivo e campo, mas não a linha do TOML como o carregador de itens;
vale apontar a linha quando o conteúdo STEAM passar de poucos arquivos.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final

from adia.nucleo.correcao.motor import dentro_da_tolerancia, interpretar_decimal, sem_unidade_declarada

SUFIXO: Final = ".adia.toml"
PARTES_MINIMAS: Final = 3
PARTES_MAXIMAS: Final = 5
_IDENTIFICADOR: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_DECIMAL: Final = re.compile(r"^[+-]?\d+(\.\d+)?$")


class ErroDeSteam(ValueError):
    """Conteúdo STEAM fora da gramática: a mensagem nomeia arquivo e campo."""


@dataclass(frozen=True)
class ParteNumerica:
    parte: str
    pergunta: str
    gabarito: Decimal
    tolerancia: Decimal
    variacoes_gabarito: tuple[str, ...]
    unidade: str | None
    sinonimos_unidade: tuple[str, ...]
    tamanho_max_resposta: int

    def corrigir(self, resposta: str) -> bool:
        """Acerto da parte pela regra do item numérico: forma declarada, depois tolerância (R13.2)."""
        texto = resposta.strip()
        if texto in {forma.strip() for forma in self.variacoes_gabarito}:
            return True
        valor = interpretar_decimal(sem_unidade_declarada(texto, self.unidade, self.sinonimos_unidade))
        if valor is None:
            valor = interpretar_decimal(self._sem_prefixo(texto))
        return valor is not None and dentro_da_tolerancia(valor, self.gabarito, self.tolerancia)

    def _sem_prefixo(self, texto: str) -> str:
        """Unidade declarada antes do número: ``R$ 101,40``, que o motor de itens não cobre.

        O motor só remove sufixo porque nenhum item declara unidade prefixada; o cenário
        declara ``R$``, e recusar a forma como o estudante escreve dinheiro inflaria o erro.
        """
        declaradas = () if self.unidade is None else (self.unidade, *self.sinonimos_unidade)
        for forma in sorted(declaradas, key=lambda f: (-len(f), f)):
            if len(texto) > len(forma) and texto[: len(forma)].casefold() == forma.casefold():
                return texto[len(forma) :].lstrip()
        return texto


@dataclass(frozen=True)
class NivelDaRubrica:
    nivel: str
    pontos: int
    descricao: str


@dataclass(frozen=True)
class Criterio:
    criterio: str
    descricao: str
    niveis: tuple[NivelDaRubrica, ...]

    def pontos(self, nivel: str) -> int | None:
        return next((n.pontos for n in self.niveis if n.nivel == nivel), None)


@dataclass(frozen=True)
class Rubrica:
    rubrica_id: str
    rubrica_versao: int
    titulo: str
    descricao: str
    criterios: tuple[Criterio, ...]

    @property
    def pontos_maximos(self) -> int:
        return sum(c.niveis[-1].pontos for c in self.criterios)


@dataclass(frozen=True)
class Cenario:
    id: str
    titulo: str
    habilidade_alvo: str
    areas: tuple[str, ...]
    enunciado: str
    partes: tuple[ParteNumerica, ...]
    pergunta_da_justificativa: str
    tamanho_max_justificativa: int
    rubrica: Rubrica


@dataclass(frozen=True)
class ConteudoSteam:
    cenarios: tuple[Cenario, ...]
    """Ordenados por ``id``: a escolha do cenário não depende da ordem dos arquivos."""
    rubricas: Mapping[tuple[str, int], Rubrica]

    def para_habilidade(self, habilidade: str) -> Cenario | None:
        """O cenário liberado para a habilidade da sessão, por igualdade exata (R13.1)."""
        return next((c for c in self.cenarios if c.habilidade_alvo == habilidade), None)


class _Campos:
    """Leitura de uma tabela TOML que recusa campo ausente, de tipo errado ou desconhecido."""

    def __init__(self, tabela: object, onde: str) -> None:
        if not isinstance(tabela, dict):
            raise ErroDeSteam(f"{onde}: esperava uma tabela")
        self._tabela: dict[str, object] = tabela
        self._onde = onde
        self._lidos: set[str] = set()

    def _erro(self, campo: str, mensagem: str) -> ErroDeSteam:
        return ErroDeSteam(f"{self._onde}, campo {campo!r}: {mensagem}")

    def _valor(self, campo: str) -> object:
        self._lidos.add(campo)
        if campo not in self._tabela:
            raise self._erro(campo, "obrigatório e ausente")
        return self._tabela[campo]

    def presente(self, campo: str) -> bool:
        self._lidos.add(campo)
        return campo in self._tabela

    def texto(self, campo: str) -> str:
        valor = self._valor(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise self._erro(campo, "esperava texto não vazio")
        return valor

    def identificador(self, campo: str) -> str:
        valor = self.texto(campo)
        if not _IDENTIFICADOR.match(valor):
            raise self._erro(campo, "identificador é ASCII, sem espaço")
        return valor

    def inteiro(self, campo: str, minimo: int) -> int:
        valor = self._valor(campo)
        if type(valor) is not int or valor < minimo:
            raise self._erro(campo, f"esperava inteiro maior ou igual a {minimo}")
        return valor

    def decimal(self, campo: str) -> Decimal:
        valor = self._valor(campo)
        if not isinstance(valor, str) or not _DECIMAL.match(valor):
            raise self._erro(campo, 'número é cadeia decimal com ponto, como "0.05"')
        return Decimal(valor)

    def textos(self, campo: str, *, identificadores: bool = False) -> tuple[str, ...]:
        valor = self._valor(campo)
        if not isinstance(valor, list) or not all(isinstance(v, str) and v.strip() for v in valor):
            raise self._erro(campo, "esperava lista de textos não vazios")
        if identificadores and not all(_IDENTIFICADOR.match(v) for v in valor):
            raise self._erro(campo, "identificador é ASCII, sem espaço")
        return tuple(valor)

    def tabela(self, campo: str) -> _Campos:
        return _Campos(self._valor(campo), f"{self._onde}, {campo}")

    def tabelas(self, campo: str, minimo: int, maximo: int | None = None) -> list[object]:
        valor = self._valor(campo)
        if not isinstance(valor, list) or len(valor) < minimo or (maximo is not None and len(valor) > maximo):
            limite = f"de {minimo} a {maximo}" if maximo is not None else f"{minimo} ou mais"
            raise self._erro(campo, f"esperava {limite} tabelas")
        return valor

    def fechar(self) -> None:
        sobras = sorted(set(self._tabela) - self._lidos)
        if sobras:
            raise self._erro(sobras[0], "campo desconhecido")


def _unicos(nomes: Sequence[str], onde: str, oque: str) -> None:
    repetidos = sorted({n for n in nomes if nomes.count(n) > 1})
    if repetidos:
        raise ErroDeSteam(f"{onde}: {oque} {repetidos[0]!r} repetido")


def _rubrica(tabela: object, onde: str) -> Rubrica:
    campos = _Campos(tabela, onde)
    rubrica_id = campos.identificador("rubrica_id")
    versao = campos.inteiro("rubrica_versao", 1)
    titulo = campos.texto("titulo")
    total = campos.inteiro("criterios_total", 2)
    descricao = campos.texto("descricao")
    criterios: list[Criterio] = []
    for i, bruto in enumerate(campos.tabelas("criterio", 2), start=1):
        local = f"{onde}, critério {i}"
        criterio = _Campos(bruto, local)
        nome = criterio.identificador("criterio")
        texto = criterio.texto("descricao")
        niveis: list[NivelDaRubrica] = []
        for j, nivel_bruto in enumerate(criterio.tabelas("nivel", 2), start=1):
            nivel = _Campos(nivel_bruto, f"{local}, nível {j}")
            niveis.append(
                NivelDaRubrica(nivel.identificador("nivel"), nivel.inteiro("pontos", 0), nivel.texto("descricao"))
            )
            nivel.fechar()
        criterio.fechar()
        _unicos([n.nivel for n in niveis], local, "nível")
        if any(a.pontos >= b.pontos for a, b in zip(niveis, niveis[1:], strict=False)):
            raise ErroDeSteam(f"{local}: os pontos dos níveis precisam crescer, sem repetir")
        criterios.append(Criterio(nome, texto, tuple(niveis)))
    campos.fechar()
    _unicos([c.criterio for c in criterios], onde, "critério")
    if total != len(criterios):
        raise ErroDeSteam(f"{onde}: criterios_total = {total}, mas há {len(criterios)} critérios declarados")
    return Rubrica(rubrica_id, versao, titulo, descricao, tuple(criterios))


def _parte(tabela: object, onde: str) -> ParteNumerica:
    campos = _Campos(tabela, onde)
    parte = ParteNumerica(
        parte=campos.identificador("parte"),
        pergunta=campos.texto("pergunta"),
        gabarito=campos.decimal("gabarito"),
        tolerancia=campos.decimal("tolerancia"),
        variacoes_gabarito=campos.textos("variacoes_gabarito"),
        unidade=campos.texto("unidade") if campos.presente("unidade") else None,
        sinonimos_unidade=campos.textos("sinonimos_unidade") if campos.presente("sinonimos_unidade") else (),
        tamanho_max_resposta=campos.inteiro("tamanho_max_resposta", 1),
    )
    campos.fechar()
    if parte.tolerancia < 0:
        raise ErroDeSteam(f"{onde}: tolerância negativa")
    if parte.sinonimos_unidade and parte.unidade is None:
        raise ErroDeSteam(f"{onde}: sinonimos_unidade exige unidade declarada")
    return parte


def _cenario(tabela: object, onde: str, rubricas: Mapping[tuple[str, int], Rubrica]) -> Cenario:
    campos = _Campos(tabela, onde)
    identificador = campos.identificador("id")
    titulo = campos.texto("titulo")
    habilidade = campos.identificador("habilidade_alvo")
    areas = campos.textos("areas", identificadores=True)
    if not areas:
        raise ErroDeSteam(f"{onde}, campo 'areas': conjunto não vazio")
    enunciado = campos.texto("enunciado")
    brutas = campos.tabelas("partes_numericas", PARTES_MINIMAS, PARTES_MAXIMAS)
    partes = tuple(_parte(p, f"{onde}, parte {i}") for i, p in enumerate(brutas, start=1))
    _unicos([p.parte for p in partes], onde, "parte")
    justificativa = campos.tabela("justificativa")
    pergunta = justificativa.texto("pergunta")
    tamanho = justificativa.inteiro("tamanho_max_resposta", 1)
    chave = (justificativa.identificador("rubrica_id"), justificativa.inteiro("rubrica_versao", 1))
    justificativa.fechar()
    campos.fechar()
    rubrica = rubricas.get(chave)
    if rubrica is None:
        raise ErroDeSteam(f"{onde}: a rubrica {chave[0]!r} versão {chave[1]} não está declarada em data/steam/")
    return Cenario(identificador, titulo, habilidade, areas, enunciado, partes, pergunta, tamanho, rubrica)


def arquivos_de_steam(diretorio: Path) -> tuple[Path, ...]:
    """Arquivos de conteúdo STEAM, em ordem de nome; diretório ausente é conteúdo vazio."""
    if not diretorio.is_dir():
        return ()
    return tuple(sorted(p for p in diretorio.iterdir() if p.is_file() and p.name.endswith(SUFIXO)))


def carregar(arquivos: Sequence[Path]) -> ConteudoSteam:
    """União dos arquivos: rubricas primeiro, porque o cenário aponta a rubrica de outro arquivo."""
    documentos: list[tuple[str, dict[str, object]]] = []
    for arquivo in arquivos:
        try:
            documento = tomllib.loads(arquivo.read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as erro:
            raise ErroDeSteam(f"{arquivo.name}: TOML inválido: {erro}") from erro
        desconhecidas = sorted(set(documento) - {"cenario", "rubrica"})
        if desconhecidas:
            raise ErroDeSteam(f"{arquivo.name}: construção de raiz desconhecida {desconhecidas[0]!r}")
        documentos.append((arquivo.name, documento))

    rubricas: dict[tuple[str, int], Rubrica] = {}
    for nome, documento in documentos:
        for i, bruta in enumerate(_Campos(documento, nome).tabelas("rubrica", 0) if "rubrica" in documento else []):
            rubrica = _rubrica(bruta, f"{nome}, rubrica {i + 1}")
            chave = (rubrica.rubrica_id, rubrica.rubrica_versao)
            if chave in rubricas:
                raise ErroDeSteam(f"{nome}: rubrica {chave[0]!r} versão {chave[1]} declarada duas vezes")
            rubricas[chave] = rubrica

    cenarios: list[Cenario] = []
    for nome, documento in documentos:
        for i, bruto in enumerate(_Campos(documento, nome).tabelas("cenario", 0) if "cenario" in documento else []):
            cenarios.append(_cenario(bruto, f"{nome}, cenário {i + 1}", rubricas))
    _unicos([c.id for c in cenarios], "data/steam", "cenário")
    return ConteudoSteam(tuple(sorted(cenarios, key=lambda c: c.id)), rubricas)
