"""Testes do serializador canônico: a forma do texto e as duas idas e voltas de R3.4 e R3.5.

O que estes testes afirmam não é "o serializador escreve TOML". É que existe **uma** escrita
por conteúdo. R3.5 é a exigência difícil de R3 — serializar, interpretar e serializar de novo
tem de produzir texto *idêntico* —, e ela só vale se cada liberdade do formato estiver fechada
por uma escolha: ordem de chaves, estilo de cadeia, ordem de coleção, escrita do decimal, fim
de linha e linha em branco. Cada teste abaixo fecha uma dessas liberdades.

A forma canônica não é preferência de estilo. O banco de itens é revisado em texto e
versionado (R3), e duas escritas do mesmo conteúdo produzem diferença de `git` sem mudança de
conteúdo — o que torna a revisão do conteúdo impossível de separar do ruído. No outro extremo,
um decimal escrito como ponto flutuante de TOML muda a tolerância que decide o acerto de item
de fronteira (R4.2), e aí a diferença aparece na TAI.

As Propriedades 29 e 30 (tarefas 3.5 e 3.6) verificam as mesmas duas idas e voltas sobre
entrada gerada. Aqui os casos são **dirigidos**, com o texto esperado escrito à mão: é o que
pega a mudança de forma que uma propriedade de ida e volta não vê, porque uma forma errada e
estável passa nas duas.

**Validates: Requirements 3.1, 3.3, 3.4, 3.5**
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

from adia.nucleo.itens.carregador import (
    CAMPOS_DE_ITEM,
    CAMPOS_DE_RELACAO,
    ORDEM_CANONICA_DE_ITEM,
    TABELA_DE_DICAS,
    CargaConcluida,
    canonizar,
    carregar,
    decimal_canonico,
    serializar_canonico,
)
from adia.nucleo.itens.erros import ErroDeCarga, ErroDeGramatica
from adia.nucleo.itens.modelo import Item, Relacao, TipoGabarito
from adia.tipos import Etapa, Nivel

# --------------------------------------------------------------------------- #
# Itens de referência
# --------------------------------------------------------------------------- #

DICAS: Mapping[Nivel, str] = MappingProxyType(
    {
        Nivel.L1: "O que a igualdade afirma sobre os dois lados?",
        Nivel.L2: "Isto é uma equação do primeiro grau com uma incógnita.",
        Nivel.L3: "Isole a incógnita aplicando a mesma operação aos dois lados.",
        Nivel.L4: "Em 5y + 2 = 17, subtraia 2 dos dois lados e divida por 5.",
    }
)


def item(
    identificador: str = "alg-eq-001",
    *,
    enunciado: str = "Resolva a equação 2x + 3 = 11 e informe o valor de x.",
    habilidade_alvo: str = "equacao_linear",
    dificuldade: int = 2,
    tamanho_max_resposta: int = 120,
    tipo_gabarito: TipoGabarito = TipoGabarito.NUMERICO,
    gabarito: str = "4",
    tolerancia: Decimal | None = Decimal("0.05"),
    unidade: str | None = None,
    sinonimos_unidade: tuple[str, ...] = (),
    variacoes_gabarito: tuple[str, ...] = (),
    termos_essenciais: tuple[tuple[str, ...], ...] = (),
    incognita: str | None = "x",
    etapas_permitidas: frozenset[Etapa] = frozenset({Etapa.LINHA_DE_BASE}),
    transferencia: bool = False,
    dicas: Mapping[Nivel, str] = DICAS,
) -> Item:
    """Item válido com os campos dados, construído **em código** e não lido de arquivo.

    Construir em código é o ponto: o serializador precisa produzir a mesma forma a partir de
    um item que nunca passou pelo carregador, porque é esse o caminho de R3.5 — serializar
    objetos, não reescrever texto.
    """
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
        dicas=dicas,
    )


def item_completo() -> Item:
    """Item que declara **todos** os campos da gramática, inclusive os opcionais.

    É o único item em que a ordem canônica é verificável por inteiro: campo opcional ausente
    não é escrito, e um item mínimo não diria nada sobre o lugar dele.
    """
    return item(
        unidade="reais",
        sinonimos_unidade=("real", "R$"),
        variacoes_gabarito=("quatro", "4"),
        termos_essenciais=(("isolar", "incognita"),),
        etapas_permitidas=frozenset({Etapa.PRATICA_ASSISTIDA, Etapa.LINHA_DE_BASE}),
    )


def trio_valido() -> tuple[tuple[Item, ...], tuple[Relacao, ...]]:
    """Praticado, equivalente e transferência: o mínimo que satisfaz R2.2 e R2.6."""
    praticado = item(
        "alg-eq-001",
        etapas_permitidas=frozenset({Etapa.PRATICA_ASSISTIDA, Etapa.LINHA_DE_BASE}),
        variacoes_gabarito=("quatro", "4"),
    )
    equivalente = item(
        "alg-eq-002",
        enunciado="Determine x em 3x - 6 = 9.",
        etapas_permitidas=frozenset({Etapa.DESAFIO_INDEPENDENTE}),
        gabarito="5",
    )
    transferencia = item(
        "alg-eq-003",
        enunciado="Uma corrida custa 3 reais por km mais 6 de bandeirada.\nQual a distância de 15 reais?",
        etapas_permitidas=frozenset({Etapa.DESAFIO_INDEPENDENTE, Etapa.TESTE_RETENCAO}),
        tipo_gabarito=TipoGabarito.TEXTUAL,
        tolerancia=None,
        termos_essenciais=(("km", "bandeirada"), ("razao",)),
        unidade="km",
        sinonimos_unidade=("quilômetros", "km"),
        gabarito="3 km, descontada a bandeirada",
        transferencia=True,
    )
    relacoes = (
        Relacao("alg-eq-001", "alg-eq-002", "equivalente"),
        Relacao("alg-eq-001", "alg-eq-003", "transferencia"),
    )
    return (praticado, equivalente, transferencia), relacoes


def escrever(diretorio: Path, nome: str, texto: str) -> Path:
    """Grava o texto em UTF-8 sem BOM, sem tradução de fim de linha."""
    caminho = diretorio / nome
    caminho.write_bytes(texto.encode("utf-8"))
    return caminho


def banco(resultado: CargaConcluida | ErroDeCarga) -> CargaConcluida:
    """Desembrulha a carga, falhando com a mensagem da rejeição quando houver."""
    if isinstance(resultado, ErroDeCarga):
        pytest.fail(f"a carga devia ter concluído: {resultado.mensagem}")
    return resultado


def textos(resultado: Mapping[Path, str] | ErroDeCarga) -> Mapping[Path, str]:
    """Desembrulha a canonização, falhando com a mensagem da rejeição quando houver."""
    if isinstance(resultado, ErroDeCarga):
        pytest.fail(f"a canonização devia ter concluído: {resultado.mensagem}")
    return resultado


# --------------------------------------------------------------------------- #
# A forma do texto, conferida contra texto esperado
# --------------------------------------------------------------------------- #

ESPERADO_DE_ITEM: str = "\n".join(
    (
        "[[item]]",
        'id = "alg-eq-001"',
        'enunciado = """',
        "Resolva a equação 2x + 3 = 11 e informe o valor de x.\\",
        '"""',
        'habilidade_alvo = "equacao_linear"',
        "dificuldade = 2",
        "tamanho_max_resposta = 120",
        'tipo_gabarito = "numerico"',
        'gabarito = "4"',
        'tolerancia = "0.05"',
        'unidade = "reais"',
        'sinonimos_unidade = ["R$", "real"]',
        'variacoes_gabarito = ["4", "quatro"]',
        'termos_essenciais = [["incognita", "isolar"]]',
        'incognita = "x"',
        'etapas_permitidas = ["linha_de_base", "pratica_assistida"]',
        "transferencia = false",
        "",
        "[item.dicas]",
        'L1 = """',
        "O que a igualdade afirma sobre os dois lados?\\",
        '"""',
        'L2 = """',
        "Isto é uma equação do primeiro grau com uma incógnita.\\",
        '"""',
        'L3 = """',
        "Isole a incógnita aplicando a mesma operação aos dois lados.\\",
        '"""',
        'L4 = """',
        "Em 5y + 2 = 17, subtraia 2 dos dois lados e divida por 5.\\",
        '"""',
        "",
    )
)
"""Texto canônico esperado de um item com **todos** os campos escritos.

Escrito à mão de propósito. Um teste que comparasse a saída com a própria saída verificaria
apenas que a função é determinística; a forma só fica fixada quando alguém a escreve e o teste
passa a reprovar a mudança dela.
"""


def test_item_completo_sai_na_forma_canonica_esperada() -> None:
    """A forma do texto é a declarada em §3.1: ordem de esquema, blocos, listas em linha."""
    assert serializar_canonico([item_completo()], []) == ESPERADO_DE_ITEM


def test_relacao_sai_nos_tres_campos_da_ordem_do_esquema() -> None:
    itens, relacoes = trio_valido()
    texto = serializar_canonico(itens, relacoes)

    assert texto.endswith(
        "\n".join(
            (
                "[[relacao]]",
                'item_origem = "alg-eq-001"',
                'item_destino = "alg-eq-003"',
                'tipo = "transferencia"',
                "",
            )
        )
    )


def test_a_ordem_canonica_cobre_o_esquema_e_nao_e_alfabetica() -> None:
    """A ordem é a da gramática. Campo novo no esquema sem lugar na ordem reprova aqui.

    O alvo é a omissão silenciosa: um campo acrescentado a `Item` e à gramática, mas não a
    `ORDEM_CANONICA_DE_ITEM`, simplesmente **não seria escrito** — e a ida e volta de R3.4
    perderia o campo sem que nenhum erro aparecesse.
    """
    assert set(ORDEM_CANONICA_DE_ITEM) | {TABELA_DE_DICAS} == CAMPOS_DE_ITEM
    assert ORDEM_CANONICA_DE_ITEM != tuple(sorted(ORDEM_CANONICA_DE_ITEM))
    assert ORDEM_CANONICA_DE_ITEM[0] == "id"
    assert CAMPOS_DE_RELACAO == ("item_origem", "item_destino", "tipo")


def test_campos_sao_escritos_na_ordem_do_esquema() -> None:
    """A ordem das chaves no texto é a do esquema, e não a ordem de nenhum dicionário."""
    texto = serializar_canonico([item_completo()], [])

    posicoes = [texto.index(f"{campo} = ") for campo in ORDEM_CANONICA_DE_ITEM]

    assert posicoes == sorted(posicoes)
    assert len(posicoes) == len(ORDEM_CANONICA_DE_ITEM), "o item de referência declara todos os campos"


def test_enunciado_e_dicas_saem_em_bloco_mesmo_com_uma_linha() -> None:
    """Uma única forma por conteúdo: bloco sempre, e não "bloco quando multilinha" (R3.5)."""
    texto = serializar_canonico([item(enunciado="Uma linha só.")], [])

    assert 'enunciado = """\n' in texto
    for nivel in Nivel:
        assert f'{nivel.name} = """\\n' not in texto
        assert f'{nivel.name} = """\n' in texto


def test_o_bloco_nao_acrescenta_quebra_de_linha_ao_valor() -> None:
    """A barra invertida final descarta a quebra que o bloco acrescentaria.

    É o defeito mais fácil de não notar numa ida e volta: a tela mostra o mesmo texto e o
    valor ganhou um `\\n` no fim. Sem a barra, todo enunciado voltaria diferente do escrito.
    """
    texto = serializar_canonico([item(enunciado="Sem quebra no fim.")], [])
    documento = tomllib.loads(texto)

    assert documento["item"][0]["enunciado"] == "Sem quebra no fim."


def test_tolerancia_sai_como_cadeia_decimal_e_nunca_como_flutuante() -> None:
    """Ponto flutuante de TOML não representa `0.05`, e a tolerância decide o acerto (R4.2)."""
    texto = serializar_canonico([item(tolerancia=Decimal("0.05"))], [])
    documento = tomllib.loads(texto)

    assert 'tolerancia = "0.05"' in texto
    assert "tolerancia = 0.05" not in texto
    assert documento["item"][0]["tolerancia"] == "0.05"


def test_o_texto_usa_lf_sem_bom_e_termina_em_uma_unica_quebra() -> None:
    itens, relacoes = trio_valido()
    texto = serializar_canonico(itens, relacoes)
    bytes_gravados = texto.encode("utf-8")

    assert "\r" not in texto
    assert not bytes_gravados.startswith(b"\xef\xbb\xbf")
    assert texto.endswith("\n")
    assert not texto.endswith("\n\n")


def test_a_unica_linha_em_branco_e_a_separadora_de_tabela() -> None:
    """Design §3.1: nenhuma linha em branco além das separadoras (R3.5)."""
    itens, relacoes = trio_valido()
    texto = serializar_canonico(itens, relacoes)
    linhas = texto.split("\n")

    for ordinal, linha in enumerate(linhas):
        if linha:
            continue
        if ordinal == len(linhas) - 1:
            continue
        seguinte = linhas[ordinal + 1]
        assert seguinte.startswith("["), f"linha em branco na posição {ordinal} não separa tabela"
    assert "\n\n\n" not in texto


def test_banco_vazio_produz_texto_vazio() -> None:
    """Texto vazio não é arquivo de definição válido, e por isso não deve ser gravado."""
    assert serializar_canonico([], []) == ""


# --------------------------------------------------------------------------- #
# Decimal na forma canônica mais curta que preserva o valor
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("0.05", "0.05"),
        ("0.050", "0.05"),
        ("0.0500000", "0.05"),
        ("1E+2", "100"),
        ("100.00", "100"),
        ("1.5E+3", "1500"),
        ("1E-7", "0.0000001"),
        ("0", "0"),
        ("0.000", "0"),
        ("-0", "0"),
        ("0.1", "0.1"),
        ("12", "12"),
    ],
)
def test_decimal_canonico_e_a_forma_mais_curta_que_preserva_o_valor(bruto: str, esperado: str) -> None:
    """Zeros à direita somem, expoente não aparece, e o valor não muda (R3.5).

    O expoente é o caso que a gramática decide: `PADRAO_DE_DECIMAL` não o admite, então
    `1E+2` escrito assim produziria arquivo que a própria leitura recusa.
    """
    canonico = decimal_canonico(Decimal(bruto))

    assert canonico == esperado
    assert Decimal(canonico) == Decimal(bruto)


@pytest.mark.parametrize("bruto", ["nan", "inf", "-inf"])
def test_decimal_nao_finito_e_recusado(bruto: str) -> None:
    """`nan` e `inf` não têm escrita que a gramática aceite; falhar alto é a alternativa."""
    with pytest.raises(ValueError, match="finito"):
        decimal_canonico(Decimal(bruto))


# --------------------------------------------------------------------------- #
# Coleções e campos opcionais
# --------------------------------------------------------------------------- #


def test_colecoes_saem_ordenadas_e_sem_repeticao_qualquer_que_seja_a_entrada() -> None:
    """Coleção é conjunto escrito como lista; a ordem de escrita não é conteúdo.

    Sem esta normalização, um item construído com a coleção fora de ordem produziria texto
    cuja releitura reordena — e a segunda serialização de R3.5 sairia diferente da primeira.
    """
    desordenado = item(
        variacoes_gabarito=("quatro", "4", "quatro"),
        unidade="reais",
        sinonimos_unidade=("real", "R$", "real"),
        termos_essenciais=(("isolar", "incognita"), ("incognita", "isolar"), ("razao",)),
        etapas_permitidas=frozenset({Etapa.PRATICA_ASSISTIDA, Etapa.LINHA_DE_BASE}),
    )

    texto = serializar_canonico([desordenado], [])

    assert 'variacoes_gabarito = ["4", "quatro"]' in texto
    assert 'sinonimos_unidade = ["R$", "real"]' in texto
    assert 'termos_essenciais = [["incognita", "isolar"], ["razao"]]' in texto
    assert 'etapas_permitidas = ["linha_de_base", "pratica_assistida"]' in texto


def test_campo_opcional_ausente_e_colecao_vazia_nao_sao_escritos() -> None:
    """TOML não tem nulo, e lista vazia é a segunda escrita de uma ausência (R3.5)."""
    minimo = item(tipo_gabarito=TipoGabarito.ALTERNATIVA, tolerancia=None, incognita=None)

    texto = serializar_canonico([minimo], [])

    for campo in ("tolerancia", "unidade", "sinonimos_unidade", "variacoes_gabarito", "termos_essenciais", "incognita"):
        assert f"\n{campo} = " not in texto


def test_transferencia_e_escrita_mesmo_quando_falsa() -> None:
    """O campo decide se o item conta na TT (R2.9); num arquivo revisado, o silêncio não serve."""
    assert "transferencia = false" in serializar_canonico([item()], [])
    assert "transferencia = true" in serializar_canonico([item(transferencia=True)], [])


def test_a_ordem_dos_blocos_nao_depende_da_ordem_dos_argumentos() -> None:
    """Itens por `id` e relações pela tripla, como o banco publicado (R26)."""
    itens, relacoes = trio_valido()

    direto = serializar_canonico(itens, relacoes)
    invertido = serializar_canonico(tuple(reversed(itens)), tuple(reversed(relacoes)))

    assert direto == invertido
    assert direto.index('id = "alg-eq-001"') < direto.index('id = "alg-eq-002"') < direto.index('id = "alg-eq-003"')


# --------------------------------------------------------------------------- #
# As duas idas e voltas de R3.4 e R3.5, em casos dirigidos
# --------------------------------------------------------------------------- #

ADVERSARIOS: Sequence[str] = (
    'aspas "duplas" no meio da frase',
    'três """ aspas seguidas, que fechariam o bloco',
    'seis """""" aspas seguidas',
    "barra invertida \\ e a dupla \\\\",
    'termina em aspas "',
    'termina em três """',
    "termina em barra invertida \\",
    "duas linhas\ne uma quebra no fim\n",
    "\nquebra de linha no começo",
    "espaços no fim   ",
    "tabulação\tno meio",
    "controles \x00\x01\x1f\x7f no meio",
    "retorno de carro \r\n do Windows",
    "acentuação e símbolos: ção, ±, −, ≤, ∑, ∈ ℝ",
    "enunciado longo " * 60,
)
"""Textos escolhidos por onde a escrita de TOML pode quebrar, não por serem realistas.

São as classes que a Propriedade 30 enfatiza — aspas, barras invertidas, texto longo — mais
as duas que só aparecem quando se olha o byte: controle e retorno de carro. Retorno de carro
é o caso instrutivo: literal no arquivo, ele seria apagado pela normalização de `\\r\\n` da
leitura, e o texto voltaria sem ele.
"""


@pytest.mark.parametrize("bruto", ADVERSARIOS)
def test_texto_adversario_sobrevive_a_ida_e_volta(bruto: str) -> None:
    """Interpretar o que foi serializado devolve o mesmo valor, caractere a caractere (R3.4)."""
    com_texto = item(enunciado=bruto, dicas=MappingProxyType({nivel: bruto for nivel in Nivel}))

    documento = tomllib.loads(serializar_canonico([com_texto], []))
    lido = documento["item"][0]

    assert lido["enunciado"] == bruto
    for nivel in Nivel:
        assert lido["dicas"][nivel.name] == bruto


@pytest.mark.parametrize("bruto", ADVERSARIOS)
def test_texto_adversario_mantem_a_serializacao_estavel(tmp_path: Path, bruto: str) -> None:
    """Serializar, interpretar e serializar de novo dá texto idêntico (R3.5)."""
    com_texto = item(enunciado=bruto, dicas=MappingProxyType({nivel: bruto for nivel in Nivel}))
    primeiro = serializar_canonico([com_texto], [])

    caminho = escrever(tmp_path, "adversario.adia.toml", primeiro)
    segundo = serializar_canonico(banco(carregar([caminho])).itens, [])

    assert segundo == primeiro


def test_o_banco_carregado_sobrevive_a_ida_e_volta_estrutural(tmp_path: Path) -> None:
    """Carregar, serializar e carregar de novo devolve o mesmo banco, por estrutura (R3.4)."""
    itens, relacoes = trio_valido()
    original = banco(carregar([escrever(tmp_path, "banco.adia.toml", serializar_canonico(itens, relacoes))]))

    reescrito = escrever(tmp_path, "reescrito.adia.toml", serializar_canonico(original.itens, original.relacoes))
    devolvido = banco(carregar([reescrito]))

    assert devolvido.itens == original.itens
    assert devolvido.relacoes == original.relacoes


def test_a_segunda_serializacao_do_banco_e_identica_a_primeira(tmp_path: Path) -> None:
    """R3.5 sobre o banco inteiro, com relações, coleções e tipos de gabarito misturados."""
    itens, relacoes = trio_valido()
    primeiro = serializar_canonico(itens, relacoes)

    carga = banco(carregar([escrever(tmp_path, "banco.adia.toml", primeiro)]))
    segundo = serializar_canonico(carga.itens, carga.relacoes)

    assert segundo == primeiro


# --------------------------------------------------------------------------- #
# Canonização por arquivo
# --------------------------------------------------------------------------- #


def test_canonizar_preserva_a_particao_de_arquivos(tmp_path: Path) -> None:
    """A validação é do conjunto; a reescrita é por arquivo (R3.3).

    Colapsar o banco num arquivo único passaria em R3.5 e destruiria a organização do
    conteúdo, que é o que R3 existe para proteger.
    """
    itens, relacoes = trio_valido()
    praticado, equivalente, transferencia = itens
    primeiro = escrever(tmp_path, "praticados.adia.toml", serializar_canonico([praticado], relacoes))
    segundo = escrever(tmp_path, "sem-ia.adia.toml", serializar_canonico([equivalente, transferencia], []))

    resultado = textos(canonizar([primeiro, segundo]))

    assert list(resultado) == [primeiro, segundo]
    assert resultado[primeiro].count("[[item]]") == 1
    assert resultado[primeiro].count("[[relacao]]") == 2
    assert resultado[segundo].count("[[item]]") == 2
    assert "[[relacao]]" not in resultado[segundo]


def test_canonizar_devolve_o_texto_ja_canonico_sem_mudanca(tmp_path: Path) -> None:
    """Arquivo já canônico sai igual ao que está em disco: é como `formatar` sabe o que mudou."""
    itens, relacoes = trio_valido()
    canonico = serializar_canonico(itens, relacoes)
    caminho = escrever(tmp_path, "banco.adia.toml", canonico)

    resultado = textos(canonizar([caminho]))

    assert resultado[caminho] == canonico


def test_canonizar_reescreve_arquivo_fora_da_forma_canonica(tmp_path: Path) -> None:
    """Chave fora de ordem, lista desordenada e cadeia de uma linha convergem para uma forma."""
    fora_de_forma = "\n".join(
        (
            "[[item]]",
            'enunciado = "Resolva a equação 2x + 3 = 11 e informe o valor de x."',
            'id = "alg-eq-001"',
            'tolerancia = "0.050"',
            'gabarito = "4"',
            'tipo_gabarito = "numerico"',
            "tamanho_max_resposta = 120",
            "dificuldade = 2",
            'habilidade_alvo = "equacao_linear"',
            'variacoes_gabarito = ["quatro", "4"]',
            'etapas_permitidas = ["teste_retencao", "linha_de_base"]',
            "",
            "[item.dicas]",
            'L3 = "Isole a incógnita."',
            'L1 = "O que a igualdade afirma?"',
            'L4 = "Em 5y + 2 = 17, subtraia 2."',
            'L2 = "É uma equação do primeiro grau."',
            "",
        )
    )
    caminho = escrever(tmp_path, "fora.adia.toml", fora_de_forma)

    canonico = textos(canonizar([caminho]))[caminho]

    assert canonico != fora_de_forma
    assert canonico.index('id = "alg-eq-001"') < canonico.index("enunciado =")
    assert 'tolerancia = "0.05"' in canonico
    assert 'variacoes_gabarito = ["4", "quatro"]' in canonico
    assert 'etapas_permitidas = ["linha_de_base", "teste_retencao"]' in canonico
    assert canonico.index('L1 = """') < canonico.index('L2 = """') < canonico.index('L3 = """')


def test_canonizar_devolve_o_erro_da_carga_e_nao_texto(tmp_path: Path) -> None:
    """Não se formata o que não carrega: a rejeição é a mesma de `carregar` (R3.2)."""
    caminho = escrever(tmp_path, "quebrado.adia.toml", "[[item]]\nid = \n")

    resultado = canonizar([caminho])

    assert isinstance(resultado, ErroDeGramatica)
    assert str(caminho) in resultado.mensagem
