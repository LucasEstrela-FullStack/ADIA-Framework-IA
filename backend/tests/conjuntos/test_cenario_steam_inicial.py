"""Conjunto declarado do cenário STEAM inicial: ele é liberável, corrigível e não vaza gabarito.

Este arquivo lê `data/steam/` **de verdade**, como `test_banco_inicial_de_itens.py` lê
`data/itens/`, e pela mesma razão: o que está sob verificação aqui é **conteúdo**, e conteúdo
só é verificável contra o conteúdo real. Ele também é, por enquanto, a **única** verificação
que o conteúdo STEAM tem — não existe `adia steam validar`, porque o carregador de cenários é
de tarefa posterior. Enquanto ele não existe, as afirmações abaixo são o portão.

Quatro coisas se afirmam, e cada uma corresponde a uma forma de o conteúdo nascer inútil:

1. **o cenário é liberável.** R13.1 manda liberar o projeto STEAM associado à habilidade alvo
   da sessão, e a associação é por igualdade exata de `habilidade_alvo`. Um cenário que aponte
   para habilidade que nenhum item cobre nunca é liberado por sessão alguma — ou, pior, é
   liberado numa sessão cuja habilidade praticada é outra, e aí a pontuação STEAM de R13.7
   deixa de medir transferência do que foi praticado;
2. **cada parte numérica é corrigível.** R13.2 manda corrigir as partes numéricas aplicando a
   tolerância declarada em cada parte, e o critério é `dentro_da_tolerancia` do
   `Motor_de_Correção`, que opera sobre `Decimal`. Gabarito ou tolerância que
   `interpretar_decimal` não leia é parte que nasce incorrigível: o conteúdo pareceria
   completo no arquivo e falharia na submissão, com o estudante do outro lado;
3. **a justificativa tem rubrica, e a rubrica tem critérios e níveis.** R13.3 encaminha a
   justificativa à rubrica, e R13.4 exige a pontuação de **todos** os critérios para concluir
   a avaliação. O esquema de `avaliacao_rubrica` (§4.3) põe isso em restrição —
   `CHECK (concluida = 0 OR criterios_pontuados = criterios_total)` —, de modo que o arquivo
   de rubrica é a fonte de `criterios_total` e da versão que entra na chave única da
   avaliação. Referência pendurada, versão ausente ou total que não bate com os critérios
   declarados tornam a avaliação impossível de registrar;
4. **nenhum texto entrega resposta.** O enunciado do cenário vai ao **estudante** e o texto da
   rubrica vai ao **professor**; nenhum dos dois precisa conter gabarito de parte numérica. Um
   nível de rubrica descrito como "identificou corretamente que o valor é tal" entregaria a
   resposta a quem lê, e o conteúdo é versionado — o vazamento ficaria no repositório.

**Por que não há afirmação sobre a aritmética do cenário.** Conferir que a resposta declarada
de uma parte decorre dos números do enunciado exigiria reimplementar o modelo da situação no
teste, e o teste passaria a verificar a própria cópia. O que sustenta a aritmética é a
derivação registrada em `docs/gramatica-steam.md`, seção 3.1, onde cada parte aparece com a
expressão que a produz.

**Validates: Requirements 13.1, 13.2, 13.3, 13.4**
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterator, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest
from vazamento import ocorre_como_token

from adia.nucleo.correcao.motor import dentro_da_tolerancia, interpretar_decimal
from adia.nucleo.itens.carregador import arquivos_de_itens, carregar
from adia.nucleo.itens.erros import ErroDeCarga

_RAIZ: Final = Path(__file__).resolve().parents[3]
_DIRETORIO_DE_STEAM: Final = _RAIZ / "data" / "steam"
_DIRETORIO_DE_ITENS: Final = _RAIZ / "data" / "itens"

SUFIXO: Final = ".adia.toml"
"""Mesmo sufixo dos arquivos de item, declarado aqui por conta própria.

A igualdade de texto com `carregador.SUFIXO_DE_ARQUIVO` é deliberada — é o sufixo de conteúdo
do projeto —, e a declaração separada também: importar a constante do carregador de itens
amarraria o conteúdo STEAM a uma gramática que não é a dele.
"""

CONSTRUCOES_DE_RAIZ: Final = frozenset({"cenario", "rubrica"})
"""As duas construções de nível raiz. Chave desconhecida é erro, pela razão da seção 1 da
gramática de itens: `rubrcia` escrito errado, se ignorado, produziria um arquivo que carrega
sem a rubrica que ele existe para declarar."""

PARTES_MINIMAS: Final = 3
PARTES_MAXIMAS: Final = 5
"""Faixa sensata de partes numéricas. Menos de três não distingue acerto parcial de acerto
total — a pontuação de R13.7 passaria a ter três valores possíveis —, e mais de cinco
transforma o projeto de transferência em lista de exercícios."""

CRITERIOS_MINIMOS: Final = 2
NIVEIS_MINIMOS: Final = 2
"""Pisos da rubrica. Rubrica de um critério é uma nota; nível único não discrimina nada, e
`pontuacoes` registraria sempre o mesmo valor."""

_IDENTIFICADOR: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
"""Mesma forma do `id` de item (gramática de itens, seção 2), e pela mesma razão declarada
em `DO-23`: `habilidade_alvo` é comparado por **igualdade exata** na liberação de R13.1, e
`"equação"` em NFC e em NFD são cadeias diferentes com a mesma aparência na tela."""

_DECIMAL: Final = re.compile(r"[+-]?\d+(?:\.\d+)?\Z")
"""Forma de dados de um número no arquivo: dígitos, ponto como separador decimal, sem
expoente. É a forma que a gramática de itens exige da tolerância, e vale aqui pelo mesmo
motivo de R4.2 e `DO-23` — o valor binário mais próximo de `0.05` é `0,05000000000000000277…`,
e a tolerância decide o acerto de parte de fronteira."""

CHAVES_DE_RESPOSTA: Final = frozenset({"gabarito", "variacoes_gabarito", "tolerancia"})
"""Campos que **são** a resposta, e por isso ficam fora da varredura de vazamento. Todo o
resto do documento é texto varrido — inclusive identificador, título e unidade, porque uma
parte chamada `litros_620` vazaria tanto quanto uma frase."""


# --------------------------------------------------------------------------- #
# Leitura dos arquivos
# --------------------------------------------------------------------------- #
#
# As funções abaixo **não** são o carregador de cenários STEAM. Elas leem o que o teste precisa
# afirmar e param aí: não publicam modelo, não ordenam, não produzem erro com caminho e linha.
# O carregador, com a gramática que ele recusa, é de tarefa posterior; antecipá-lo aqui faria o
# teste verificar a leitura que ele mesmo escreveu.


def _arquivos() -> tuple[Path, ...]:
    """Arquivos de conteúdo STEAM, em ordem estável de caminho."""
    return tuple(sorted(_DIRETORIO_DE_STEAM.glob(f"*{SUFIXO}")))


def _documentos() -> tuple[tuple[str, Mapping[str, object]], ...]:
    """Cada arquivo interpretado, com o nome que vai para a mensagem de falha."""
    arquivos = _arquivos()
    assert arquivos, f"nenhum arquivo `*{SUFIXO}` em {_DIRETORIO_DE_STEAM}"
    lidos: list[tuple[str, Mapping[str, object]]] = []
    for caminho in arquivos:
        documento: Mapping[str, object] = tomllib.loads(caminho.read_text(encoding="utf-8"))
        lidos.append((caminho.name, documento))
    return tuple(lidos)


def _tabelas(dono: Mapping[str, object], chave: str, onde: str) -> tuple[Mapping[str, object], ...]:
    """Coleção de tabelas sob `chave`, exigida não vazia."""
    valor = dono.get(chave)
    assert isinstance(valor, list) and valor, f"{onde}: `{chave}` ausente ou vazio"
    tabelas: list[Mapping[str, object]] = []
    for indice, elemento in enumerate(valor):
        assert isinstance(elemento, dict), f"{onde}: `{chave}[{indice}]` não é tabela"
        tabelas.append(elemento)
    return tuple(tabelas)


def _tabela(dono: Mapping[str, object], chave: str, onde: str) -> Mapping[str, object]:
    """Subtabela única sob `chave`."""
    valor = dono.get(chave)
    assert isinstance(valor, dict), f"{onde}: `{chave}` ausente ou não é tabela"
    return valor


def _texto(dono: Mapping[str, object], chave: str, onde: str) -> str:
    """Cadeia não vazia sob `chave`. Em branco conta como **ausente**, como em R2.1."""
    valor = dono.get(chave)
    assert isinstance(valor, str), f"{onde}: campo `{chave}` ausente ou não é cadeia"
    assert valor.strip(), f"{onde}: campo `{chave}` declarado em branco"
    return valor


def _inteiro(dono: Mapping[str, object], chave: str, onde: str) -> int:
    """Inteiro sob `chave`. `bool` é recusado: em Python ele passaria por `int`."""
    valor = dono.get(chave)
    assert isinstance(valor, int) and not isinstance(valor, bool), (
        f"{onde}: campo `{chave}` ausente ou não é inteiro"
    )
    return valor


def _identificador(dono: Mapping[str, object], chave: str, onde: str) -> str:
    """Cadeia sob `chave` na forma de identificador: ASCII, sem espaço."""
    valor = _texto(dono, chave, onde)
    assert _IDENTIFICADOR.match(valor) is not None, (
        f"{onde}: `{chave}` fora da forma de identificador (ASCII, sem espaço, até 64 caracteres)"
    )
    return valor


def _lista_de_texto(dono: Mapping[str, object], chave: str, onde: str) -> tuple[str, ...]:
    """Coleção de cadeias não vazias sob `chave`, sem repetição.

    Repetição é recusada em vez de descartada, pela razão da seção 2 da gramática de itens:
    coleção é conjunto escrito como lista, e repetição silenciosamente descartada mudaria o
    tamanho entre uma leitura e a seguinte.
    """
    valor = dono.get(chave)
    assert isinstance(valor, list) and valor, f"{onde}: `{chave}` ausente ou vazio"
    itens: list[str] = []
    for indice, elemento in enumerate(valor):
        assert isinstance(elemento, str) and elemento.strip(), f"{onde}: `{chave}[{indice}]` vazio ou não é cadeia"
        itens.append(elemento)
    assert len(set(itens)) == len(itens), f"{onde}: `{chave}` com repetição"
    return tuple(itens)


def _lista_de_identificadores(dono: Mapping[str, object], chave: str, onde: str) -> tuple[str, ...]:
    """Coleção de identificadores sob `chave`, exigida não vazia e sem repetição."""
    itens = _lista_de_texto(dono, chave, onde)
    for indice, elemento in enumerate(itens):
        assert _IDENTIFICADOR.match(elemento) is not None, f"{onde}: `{chave}[{indice}]` fora da forma ASCII"
    return itens


def _cenarios(documentos: tuple[tuple[str, Mapping[str, object]], ...]) -> tuple[tuple[str, Mapping[str, object]], ...]:
    """Todos os cenários de todos os arquivos, cada um com o arquivo de origem."""
    return tuple(
        (nome, cenario)
        for nome, documento in documentos
        if "cenario" in documento
        for cenario in _tabelas(documento, "cenario", nome)
    )


def _rubricas(documentos: tuple[tuple[str, Mapping[str, object]], ...]) -> tuple[tuple[str, Mapping[str, object]], ...]:
    """Todas as rubricas de todos os arquivos, cada uma com o arquivo de origem."""
    return tuple(
        (nome, rubrica)
        for nome, documento in documentos
        if "rubrica" in documento
        for rubrica in _tabelas(documento, "rubrica", nome)
    )


@pytest.fixture(scope="module")
def documentos() -> tuple[tuple[str, Mapping[str, object]], ...]:
    """Arquivos lidos uma vez por módulo: a leitura de disco não é o que se verifica aqui."""
    return _documentos()


@pytest.fixture(scope="module")
def cenarios(
    documentos: tuple[tuple[str, Mapping[str, object]], ...],
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    """Os cenários declarados, com o arquivo de origem de cada um."""
    return _cenarios(documentos)


@pytest.fixture(scope="module")
def rubricas(
    documentos: tuple[tuple[str, Mapping[str, object]], ...],
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    """As rubricas declaradas, com o arquivo de origem de cada uma."""
    return _rubricas(documentos)


# --------------------------------------------------------------------------- #
# 0. Forma dos arquivos
# --------------------------------------------------------------------------- #


def test_cada_arquivo_e_utf8_sem_bom_e_termina_em_lf() -> None:
    """Codificação e fim de linha, afirmados nos **bytes** (gramática de itens, seção 1).

    A marca de ordem de bytes é invisível na tela e faz o conteúdo mudar de bytes entre uma
    leitura e uma reescrita sem que nada do conteúdo mude; `CRLF` no arquivo versionado
    contraria o `* text=auto eol=lf` que o repositório declara, e produziria diferença de
    `git` em toda linha no primeiro `checkout` de outra máquina.
    """
    for caminho in _arquivos():
        bytes_do_arquivo = caminho.read_bytes()
        assert not bytes_do_arquivo.startswith(b"\xef\xbb\xbf"), f"{caminho.name}: marca de ordem de bytes"
        assert b"\r" not in bytes_do_arquivo, f"{caminho.name}: fim de linha CRLF"
        assert bytes_do_arquivo.endswith(b"\n"), f"{caminho.name}: falta a quebra de linha final"


def test_o_diretorio_declara_cenario_e_rubrica(
    documentos: tuple[tuple[str, Mapping[str, object]], ...],
    cenarios: tuple[tuple[str, Mapping[str, object]], ...],
    rubricas: tuple[tuple[str, Mapping[str, object]], ...],
) -> None:
    """As duas construções existem, e nenhuma chave de raiz fora das duas (R13.1, R13.4)."""
    for nome, documento in documentos:
        desconhecidas = sorted(set(documento) - CONSTRUCOES_DE_RAIZ)
        assert not desconhecidas, f"{nome}: chave(s) de raiz fora da gramática: {desconhecidas}"

    assert cenarios, "nenhum `[[cenario]]` declarado: sem cenário não há projeto STEAM a liberar (R13.1)"
    assert rubricas, "nenhuma `[[rubrica]]` declarada: sem rubrica a justificativa não é avaliável (R13.3)"

    identificadores = [_identificador(cenario, "id", nome) for nome, cenario in cenarios]
    assert len(set(identificadores)) == len(identificadores), f"`id` de cenário repetido: {identificadores}"

    versoes = [
        (_identificador(rubrica, "rubrica_id", nome), _inteiro(rubrica, "rubrica_versao", nome))
        for nome, rubrica in rubricas
    ]
    assert len(set(versoes)) == len(versoes), (
        f"par (`rubrica_id`, `rubrica_versao`) repetido: {versoes}. A chave única de "
        "`avaliacao_rubrica` é por submissão, avaliador e versão (§4.3), logo duas rubricas "
        "com o mesmo par seriam duas definições para a mesma avaliação registrada."
    )


# --------------------------------------------------------------------------- #
# 1. O cenário é liberável: a habilidade alvo existe no banco de itens
# --------------------------------------------------------------------------- #


def _habilidades_do_banco_de_itens() -> frozenset[str]:
    """Habilidades que o banco de `data/itens/` cobre, pela carga real do carregador."""
    arquivos = arquivos_de_itens(_DIRETORIO_DE_ITENS)
    assert arquivos, f"nenhum arquivo de definição em {_DIRETORIO_DE_ITENS}"
    carga = carregar(arquivos)
    if isinstance(carga, ErroDeCarga):
        raise AssertionError(f"o banco inicial não carrega: {carga.mensagem}")
    return frozenset(item.habilidade_alvo for item in carga.itens)


def test_a_habilidade_alvo_do_cenario_existe_no_banco_de_itens(
    cenarios: tuple[tuple[str, Mapping[str, object]], ...],
) -> None:
    """R13.1: o cenário se liga à habilidade da sessão, e ela tem de ser uma habilidade real.

    A comparação é com o banco carregado de verdade, e não com uma constante escrita aqui: uma
    constante continuaria verde depois de a habilidade ser renomeada no conteúdo, e passaria a
    afirmar algo sobre um banco que não existe mais. Cenário apontando para habilidade que
    nenhum item cobre é liberado por R13.1 e não mede transferência de nada.
    """
    habilidades = _habilidades_do_banco_de_itens()
    for nome, cenario in cenarios:
        onde = f"{nome}:{_identificador(cenario, 'id', nome)}"
        alvo = _identificador(cenario, "habilidade_alvo", onde)
        assert alvo in habilidades, (
            f"{onde}: `habilidade_alvo` = {alvo!r} não é coberta por nenhum item de "
            f"`data/itens/`. Habilidades do banco: {sorted(habilidades)}."
        )
        _texto(cenario, "titulo", onde)
        _texto(cenario, "enunciado", onde)
        assert _lista_de_identificadores(cenario, "areas", onde), (
            f"{onde}: `areas` vazio. O projeto STEAM é tarefa **interdisciplinar** por "
            "definição, e declarar as áreas é o que torna isso auditável em vez de implícito "
            "na prosa do enunciado."
        )


# --------------------------------------------------------------------------- #
# 2. Cada parte numérica é corrigível pelo Motor_de_Correção
# --------------------------------------------------------------------------- #


def _partes(cenario: Mapping[str, object], onde: str) -> tuple[Mapping[str, object], ...]:
    """As partes numéricas do cenário."""
    return _tabelas(cenario, "partes_numericas", onde)


def test_cada_parte_numerica_declara_identificador_gabarito_e_tolerancia(
    cenarios: tuple[tuple[str, Mapping[str, object]], ...],
) -> None:
    """R13.2: parte sem identificador, sem gabarito ou sem tolerância não é corrigível.

    Os três campos são o que o evento `steam_submetido` carrega por parte — `parte`, `valor`,
    `resultado` e `tolerancia` (§4.4) —, de modo que o identificador é a chave pela qual o
    resultado de cada parte é registrado. Duas partes com o mesmo identificador fariam o
    registro de uma sobrescrever o da outra, e a pontuação de R13.7 passaria a contar menos
    partes do que o estudante respondeu.
    """
    for nome, cenario in cenarios:
        onde = f"{nome}:{_identificador(cenario, 'id', nome)}"
        partes = _partes(cenario, onde)
        assert PARTES_MINIMAS <= len(partes) <= PARTES_MAXIMAS, (
            f"{onde}: {len(partes)} parte(s) numérica(s), fora da faixa de "
            f"{PARTES_MINIMAS} a {PARTES_MAXIMAS}."
        )
        identificadores = [_identificador(parte, "parte", onde) for parte in partes]
        assert len(set(identificadores)) == len(identificadores), (
            f"{onde}: identificador de parte repetido: {identificadores}"
        )
        for parte in partes:
            onde_parte = f"{onde}.{_identificador(parte, 'parte', onde)}"
            _texto(parte, "pergunta", onde_parte)
            assert _inteiro(parte, "tamanho_max_resposta", onde_parte) >= 1, (
                f"{onde_parte}: `tamanho_max_resposta` tem de ser positivo"
            )
            gabarito = _texto(parte, "gabarito", onde_parte)
            tolerancia = _texto(parte, "tolerancia", onde_parte)
            assert _DECIMAL.match(gabarito) is not None, (
                f"{onde_parte}: `gabarito` fora da forma de dados (dígitos e ponto decimal, sem expoente)"
            )
            assert _DECIMAL.match(tolerancia) is not None, (
                f"{onde_parte}: `tolerancia` fora da forma de dados. Cadeia decimal, nunca ponto "
                "flutuante de TOML: o valor binário mais próximo de 0,05 não é 0,05, e a "
                "tolerância decide o acerto de parte de fronteira (R4.2)."
            )
            if "unidade" in parte:
                _texto(parte, "unidade", onde_parte)
                if "sinonimos_unidade" in parte:
                    _lista_de_texto(parte, "sinonimos_unidade", onde_parte)
            else:
                assert "sinonimos_unidade" not in parte, (
                    f"{onde_parte}: `sinonimos_unidade` sem `unidade` declarada"
                )


def test_cada_gabarito_e_cada_tolerancia_sao_lidos_pelo_motor_de_correcao(
    cenarios: tuple[tuple[str, Mapping[str, object]], ...],
) -> None:
    """R13.2: o critério de acerto da parte é `dentro_da_tolerancia`, e ele opera sobre `Decimal`.

    Três afirmações encadeadas, e nenhuma delas é redundante com a forma textual verificada
    acima. `interpretar_decimal` é a função que o conteúdo precisa satisfazer **de fato**, e
    ela recusa notação científica e separador ambíguo por regra declarada: a leitura de um
    único separador é **decimal**, de modo que `1.500` vale um e meio, e não mil e quinhentos.
    Depois, cada forma numérica declarada entre as variações é comparada ao gabarito pela
    tolerância da própria parte — é o que pega a variação transcrita errada, que passaria pela
    expressão regular e aceitaria como certa uma resposta que não é.

    A terceira afirmação é sobre cobertura da varredura de vazamento, e não sobre correção:
    gabarito inteiro precisa declarar o numeral em palavras entre as formas aceitas. Foi a
    convenção adotada no banco de itens justamente para que a varredura cubra `quatro` além de
    `4`, e aqui ela vale pelo mesmo motivo. Gabarito decimal fica de fora porque não tem
    grafia única em palavras — `cento e um reais e quarenta centavos` é uma entre várias.
    """
    for nome, cenario in cenarios:
        onde = f"{nome}:{_identificador(cenario, 'id', nome)}"
        for parte in _partes(cenario, onde):
            onde_parte = f"{onde}.{_identificador(parte, 'parte', onde)}"

            gabarito = interpretar_decimal(_texto(parte, "gabarito", onde_parte))
            assert gabarito is not None, f"{onde_parte}: `gabarito` não é número para `interpretar_decimal`"

            tolerancia = interpretar_decimal(_texto(parte, "tolerancia", onde_parte))
            assert tolerancia is not None, f"{onde_parte}: `tolerancia` não é número para `interpretar_decimal`"
            assert tolerancia >= Decimal(0), f"{onde_parte}: `tolerancia` negativa (R2.8)"

            formas = _lista_de_texto(parte, "variacoes_gabarito", onde_parte)
            em_palavras = 0
            for indice, forma in enumerate(formas):
                valor = interpretar_decimal(forma)
                if valor is None:
                    em_palavras += 1
                    continue
                assert dentro_da_tolerancia(valor, gabarito, tolerancia), (
                    f"{onde_parte}: `variacoes_gabarito[{indice}]` é número fora da tolerância "
                    "declarada da própria parte, logo seria recusado como erro se o estudante o "
                    "escrevesse."
                )
            if gabarito == gabarito.to_integral_value():
                assert em_palavras >= 1, (
                    f"{onde_parte}: gabarito inteiro sem numeral em palavras entre as "
                    "`variacoes_gabarito`. Sem ele a varredura de vazamento cobre só os dígitos."
                )


# --------------------------------------------------------------------------- #
# 3. A justificativa vai à rubrica, e a rubrica exige todos os critérios
# --------------------------------------------------------------------------- #


def test_a_justificativa_e_pedida_e_aponta_para_uma_rubrica_declarada(
    cenarios: tuple[tuple[str, Mapping[str, object]], ...],
    rubricas: tuple[tuple[str, Mapping[str, object]], ...],
) -> None:
    """R13.3: há justificativa em texto livre, e ela tem rubrica identificada **e versionada**.

    A versão não é enfeite de catálogo: ela entra na chave `UNIQUE (submissao_id, avaliador_id,
    rubrica_versao)` de `avaliacao_rubrica` (§4.3). Referência pendurada — rubrica que o
    conteúdo não declara, ou versão que não existe — produziria avaliação impossível de
    registrar no momento em que o professor terminasse de pontuar.
    """
    declaradas = {
        (_identificador(rubrica, "rubrica_id", nome), _inteiro(rubrica, "rubrica_versao", nome))
        for nome, rubrica in rubricas
    }
    for nome, cenario in cenarios:
        onde = f"{nome}:{_identificador(cenario, 'id', nome)}"
        justificativa = _tabela(cenario, "justificativa", onde)
        onde_just = f"{onde}.justificativa"
        _texto(justificativa, "pergunta", onde_just)
        assert _inteiro(justificativa, "tamanho_max_resposta", onde_just) >= 1, (
            f"{onde_just}: `tamanho_max_resposta` tem de ser positivo"
        )
        referencia = (
            _identificador(justificativa, "rubrica_id", onde_just),
            _inteiro(justificativa, "rubrica_versao", onde_just),
        )
        assert referencia in declaradas, (
            f"{onde_just}: aponta para a rubrica {referencia}, que não está declarada em "
            f"`data/steam/`. Declaradas: {sorted(declaradas)}."
        )


def test_a_rubrica_declara_criterios_com_niveis_e_o_total_bate(
    rubricas: tuple[tuple[str, Mapping[str, object]], ...],
) -> None:
    """R13.4: critérios e níveis declarados, e `criterios_total` igual à contagem real.

    `criterios_total` aparece duas vezes de propósito — escrito no arquivo e contado a partir
    dos critérios — porque é ele que vai para a coluna de mesmo nome e, com
    `CHECK (concluida = 0 OR criterios_pontuados = criterios_total)`, decide se a avaliação
    pode concluir. Um critério apagado do arquivo sem o total ser corrigido faria a avaliação
    concluir com um critério **não** pontuado, que é exatamente o que R13.4 proíbe; um total
    maior que os critérios declarados tornaria toda avaliação impossível de concluir.

    Os pontos são verificados **crescentes e distintos** por nível. Dois níveis valendo o mesmo
    não distinguem desempenho nenhum, e ordem decrescente num arquivo escrito à mão é erro de
    transcrição que nada mais pegaria: o professor veria a escala invertida na tela e a
    pontuação registrada premiaria o pior nível.
    """
    for nome, rubrica in rubricas:
        onde = f"{nome}:{_identificador(rubrica, 'rubrica_id', nome)}"
        versao = _inteiro(rubrica, "rubrica_versao", onde)
        assert versao > 0, f"{onde}: `rubrica_versao` tem de ser positiva (§4.3, CHECK rubrica_versao > 0)"
        _texto(rubrica, "titulo", onde)
        _texto(rubrica, "descricao", onde)

        criterios = _tabelas(rubrica, "criterio", onde)
        assert len(criterios) >= CRITERIOS_MINIMOS, f"{onde}: {len(criterios)} critério(s), mínimo {CRITERIOS_MINIMOS}"
        assert _inteiro(rubrica, "criterios_total", onde) == len(criterios), (
            f"{onde}: `criterios_total` declarado difere dos critérios declarados "
            f"({len(criterios)}). É esse número que `avaliacao_rubrica` grava, e é com ele que "
            "R13.4 decide se a avaliação pode concluir."
        )

        nomes = [_identificador(criterio, "criterio", onde) for criterio in criterios]
        assert len(set(nomes)) == len(nomes), f"{onde}: identificador de critério repetido: {nomes}"

        for criterio in criterios:
            onde_criterio = f"{onde}.{_identificador(criterio, 'criterio', onde)}"
            _texto(criterio, "descricao", onde_criterio)
            niveis = _tabelas(criterio, "nivel", onde_criterio)
            assert len(niveis) >= NIVEIS_MINIMOS, f"{onde_criterio}: {len(niveis)} nível(is), mínimo {NIVEIS_MINIMOS}"

            rotulos = [_identificador(nivel, "nivel", onde_criterio) for nivel in niveis]
            assert len(set(rotulos)) == len(rotulos), f"{onde_criterio}: identificador de nível repetido: {rotulos}"

            pontos: list[int] = []
            for nivel in niveis:
                onde_nivel = f"{onde_criterio}.{_identificador(nivel, 'nivel', onde_criterio)}"
                _texto(nivel, "descricao", onde_nivel)
                valor = _inteiro(nivel, "pontos", onde_nivel)
                assert valor >= 0, f"{onde_nivel}: `pontos` negativo"
                pontos.append(valor)
            assert pontos == sorted(set(pontos)), (
                f"{onde_criterio}: `pontos` dos níveis não são crescentes e distintos: {pontos}"
            )


# --------------------------------------------------------------------------- #
# 4. Nenhum texto do cenário ou da rubrica revela gabarito de parte numérica
# --------------------------------------------------------------------------- #


def _textos(valor: object, caminho: str) -> Iterator[tuple[str, str]]:
    """Cada cadeia do documento, com o caminho do campo que a contém.

    O caminho — e nunca o valor — é o que vai para a mensagem de falha, pela regra da seção 6
    da gramática de itens: gabarito e texto de conteúdo não são interpolados em diagnóstico,
    porque o diagnóstico vai para o terminal, para o log de subida da API e, no pior caso, para
    uma captura de tela em sala.
    """
    if isinstance(valor, str):
        yield caminho, valor
    elif isinstance(valor, dict):
        for chave, interno in valor.items():
            nome = str(chave)
            if nome in CHAVES_DE_RESPOSTA:
                continue
            yield from _textos(interno, f"{caminho}.{nome}")
    elif isinstance(valor, list):
        for indice, interno in enumerate(valor):
            yield from _textos(interno, f"{caminho}[{indice}]")


def _formas_proibidas(cenarios: tuple[tuple[str, Mapping[str, object]], ...]) -> tuple[tuple[str, str], ...]:
    """Cadeias que nenhum texto pode conter, cada uma com o **nome** do campo de origem."""
    proibidas: list[tuple[str, str]] = []
    for nome, cenario in cenarios:
        onde = _identificador(cenario, "id", nome)
        for parte in _partes(cenario, onde):
            identificador = _identificador(parte, "parte", onde)
            proibidas.append((f"{identificador}.gabarito", _texto(parte, "gabarito", onde)))
            proibidas.extend(
                (f"{identificador}.variacoes_gabarito[{indice}]", forma)
                for indice, forma in enumerate(_lista_de_texto(parte, "variacoes_gabarito", onde))
            )
    return tuple(proibidas)


def test_nenhum_texto_do_cenario_ou_da_rubrica_revela_gabarito_de_parte(
    documentos: tuple[tuple[str, Mapping[str, object]], ...],
    cenarios: tuple[tuple[str, Mapping[str, object]], ...],
) -> None:
    """O enunciado vai ao estudante e a rubrica vai ao professor; nenhum dos dois traz resposta.

    A varredura é de **todo** o texto dos arquivos de `data/steam/` contra **todas** as formas
    aceitas de **todas** as partes, e não só do enunciado contra o gabarito da parte
    correspondente. Dois vazamentos justificam a amplitude. Um nível de rubrica descrito como
    "percebeu que o valor é tal" entrega a resposta a quem lê, e a rubrica é lida na mesma
    tela em que o professor acompanha a turma. E a pergunta de uma parte que citasse o
    resultado de outra entregaria aquela outra — o enunciado é um só, e o estudante responde
    todas as partes a partir dele.

    O que esta varredura **não** cobre, e qual é a contrapartida escrita no conteúdo: numeral de
    mais de uma palavra só reprova se o texto trouxer a expressão completa, e nenhuma
    detecção textual separa o gabarito de um item do banco de um número qualquer do cenário —
    gabaritos de uma casa colidem com os dígitos de qualquer situação realista. O que fecha
    esse lado é estrutural, e está registrado em `docs/gramatica-steam.md`: nenhuma resposta de
    parte numérica é um número que o enunciado informe, e os numerais de uma palavra do texto
    (`cinco`, `uma`) não são resposta de parte alguma.
    """
    proibidas = _formas_proibidas(cenarios)
    assert len(proibidas) >= 2 * PARTES_MINIMAS, (
        f"{len(proibidas)} forma(s) a varrer: cada parte declara gabarito e ao menos uma "
        "variação, logo a varredura tem no mínimo duas formas por parte."
    )

    textos = tuple(
        (f"{nome}{caminho}", texto) for nome, documento in documentos for caminho, texto in _textos(documento, "")
    )
    caminhos = {caminho for caminho, _ in textos}
    assert any(caminho.endswith(".enunciado") for caminho in caminhos), "o enunciado do cenário não foi varrido"
    assert any(".justificativa.pergunta" in caminho for caminho in caminhos), "a justificativa não foi varrida"
    assert any(".nivel[" in caminho and caminho.endswith(".descricao") for caminho in caminhos), (
        "nenhuma descrição de nível de rubrica foi varrida"
    )

    vazamentos = [
        f"{caminho}: contém `{campo}`"
        for caminho, texto in textos
        for campo, forma in proibidas
        if ocorre_como_token(texto, forma)
    ]
    assert not vazamentos, "textos de `data/steam/` que reproduzem resposta de parte numérica: " + "; ".join(
        vazamentos
    )
