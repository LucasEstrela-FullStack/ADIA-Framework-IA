"""Testes do carregador de itens: as nove classes de falha e a atomicidade da carga.

O que estes testes afirmam não é "o carregador lê TOML". É que **nenhum item malformado
entra no banco** e que a recusa diz onde consertar (R3.2). A diferença importa porque o banco
de itens é entrada de tudo o que se mede: um item sem tolerância não produz uma tela torta,
produz TAI, TT, IIC e decisão de regulação descrevendo outra coisa (§7.2).

Três afirmações, portanto:

1. cada uma das nove classes de falha de §3.1 é recusada, com arquivo e campo nomeados, e com
   linha exata quando o campo existe no texto;
2. a carga é **atômica**: um conjunto com um arquivo válido e um inválido não publica item
   nenhum — nem os itens do arquivo bom. É o que §7.2 exige, e é o contrário do que um
   carregador tolerante faria;
3. nenhuma mensagem de erro cita gabarito, variação de gabarito, termo essencial, enunciado
   ou texto de dica. Mensagem de erro vai para terminal, log e captura de tela; gabarito ali
   é vazamento por outro caminho.

Os arquivos são escritos em `tmp_path` a cada teste. O banco inicial de `data/itens/` é da
tarefa 3.14, e depender dele aqui trocaria a verificação do carregador pela verificação do
conteúdo.

**Validates: Requirements 2.1, 2.2, 2.4, 2.6, 2.8, 2.9, 2.11, 3.1, 3.2, 3.6**
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from adia.nucleo.itens.carregador import (
    CargaConcluida,
    ResultadoDeCarga,
    arquivos_de_itens,
    carregar,
)
from adia.nucleo.itens.erros import (
    VALOR_OMITIDO,
    ErroDeAssociacaoAusente,
    ErroDeCarga,
    ErroDeConflitoDeRelacao,
    ErroDeDicaAusente,
    ErroDeEtapasVazias,
    ErroDeFaixa,
    ErroDeGramatica,
    ErroDeIdentificadorDuplicado,
    ErroDePerfilIncompleto,
)
from adia.nucleo.itens.modelo import Item, TipoGabarito
from adia.tipos import Etapa, Nivel

# --------------------------------------------------------------------------- #
# Construção de arquivos de definição
# --------------------------------------------------------------------------- #

ENUNCIADO: str = '"""\nResolva a equação 2x + 3 = 11 e informe o valor de x.\n"""'
"""Enunciado em bloco, como a gramática pede para texto multilinha."""

DICAS_PADRAO: Mapping[str, str] = {
    "L1": '"O que a igualdade está afirmando sobre os dois lados?"',
    "L2": '"Isto é uma equação do primeiro grau com uma incógnita."',
    "L3": '"Isole a incógnita aplicando a mesma operação aos dois lados."',
    "L4": '"Em 5y + 2 = 17, subtraia 2 dos dois lados e divida por 5."',
}
"""Dicas de L1 a L4 que não revelam o gabarito do item usado nos testes."""


def item(
    identificador: str = "alg-eq-001",
    *,
    enunciado: str = ENUNCIADO,
    habilidade: str = '"equacao_linear"',
    dificuldade: str | None = "2",
    tamanho: str | None = "120",
    tipo_gabarito: str | None = '"numerico"',
    gabarito: str | None = '"4"',
    tolerancia: str | None = '"0.01"',
    termos: str | None = None,
    etapas: str | None = '["linha_de_base"]',
    transferencia: str | None = None,
    extras: Sequence[str] = (),
    dicas: Mapping[str, str] | None = DICAS_PADRAO,
) -> str:
    """Bloco `[[item]]` com os valores dados, já escritos como literais de TOML.

    Os parâmetros são **texto de TOML**, não valores de Python, para que um teste possa
    injetar o tipo errado (`dificuldade="\\"dois\\""`) ou suprimir um campo (`tolerancia=None`)
    sem que o construtor conserte o defeito pelo caminho.
    """
    linhas = ["[[item]]", f'id = "{identificador}"', f"enunciado = {enunciado}"]
    opcionais = (
        ("habilidade_alvo", habilidade),
        ("dificuldade", dificuldade),
        ("tamanho_max_resposta", tamanho),
        ("tipo_gabarito", tipo_gabarito),
        ("gabarito", gabarito),
        ("tolerancia", tolerancia),
        ("termos_essenciais", termos),
        ("etapas_permitidas", etapas),
        ("transferencia", transferencia),
    )
    linhas.extend(f"{campo} = {valor}" for campo, valor in opcionais if valor is not None)
    linhas.extend(extras)
    if dicas is not None:
        linhas.append("")
        linhas.append("[item.dicas]")
        linhas.extend(f"{nivel} = {texto}" for nivel, texto in dicas.items())
    return "\n".join(linhas) + "\n"


def relacao(origem: str, destino: str, tipo: str) -> str:
    """Bloco `[[relacao]]` dirigido da origem para o destino."""
    return f'[[relacao]]\nitem_origem = "{origem}"\nitem_destino = "{destino}"\ntipo = "{tipo}"\n'


def conjunto_valido() -> str:
    """Trio mínimo que satisfaz R2.2 e R2.6: praticado, equivalente e transferência."""
    return "\n".join(
        (
            item("alg-eq-001", etapas='["pratica_assistida", "linha_de_base"]'),
            item("alg-eq-002", enunciado='"Determine x em 3x - 6 = 9."', etapas='["desafio_independente"]'),
            item(
                "alg-eq-003",
                enunciado='"Uma corrida custa 3 reais por km mais 6 de bandeirada; qual a distância de 15 reais?"',
                etapas='["desafio_independente"]',
                transferencia="true",
            ),
            relacao("alg-eq-001", "alg-eq-002", "equivalente"),
            relacao("alg-eq-001", "alg-eq-003", "transferencia"),
        )
    )


def escrever(diretorio: Path, nome: str, texto: str) -> Path:
    """Escreve o arquivo em UTF-8 sem BOM e com fim de linha LF, como a gramática exige."""
    caminho = diretorio / nome
    caminho.write_bytes(texto.encode("utf-8"))
    return caminho


def linha_de(texto: str, trecho: str) -> int:
    """Número da linha, contado de 1, em que o trecho aparece pela primeira vez.

    Os testes comparam a linha relatada com esta, em vez de com um número escrito à mão:
    número à mão passa a mentir na primeira vez que alguém insere uma linha no construtor.
    """
    for numero, conteudo in enumerate(texto.splitlines(), start=1):
        if trecho in conteudo:
            return numero
    raise AssertionError(f"trecho {trecho!r} não aparece no texto")


def recusa(resultado: ResultadoDeCarga) -> ErroDeCarga:
    """O erro de uma carga que deveria ter sido recusada."""
    assert not isinstance(resultado, CargaConcluida), "a carga deveria ter sido recusada"
    return resultado


def banco(resultado: ResultadoDeCarga) -> CargaConcluida:
    """O banco de uma carga que deveria ter sido aceita."""
    assert isinstance(resultado, CargaConcluida), f"carga recusada: {resultado}"
    return resultado


# --------------------------------------------------------------------------- #
# Caminho nominal
# --------------------------------------------------------------------------- #


def test_conjunto_valido_produz_os_itens_declarados(tmp_path: Path) -> None:
    """Arquivo válido é interpretado conforme a gramática documentada (R3.1)."""
    caminho = escrever(tmp_path, "algebra.adia.toml", conjunto_valido())

    carga = banco(carregar([caminho]))

    assert [item_lido.id for item_lido in carga.itens] == ["alg-eq-001", "alg-eq-002", "alg-eq-003"]
    praticado = carga.itens[0]
    assert praticado.habilidade_alvo == "equacao_linear"
    assert praticado.dificuldade == 2
    assert praticado.tipo_gabarito is TipoGabarito.NUMERICO
    assert praticado.etapas_permitidas == frozenset({Etapa.PRATICA_ASSISTIDA, Etapa.LINHA_DE_BASE})
    assert praticado.e_praticado
    assert set(praticado.dicas) == set(Nivel)
    assert [(r.item_origem, r.item_destino, r.tipo) for r in carga.relacoes] == [
        ("alg-eq-001", "alg-eq-002", "equivalente"),
        ("alg-eq-001", "alg-eq-003", "transferencia"),
    ]


def test_tolerancia_e_decimal_exato_e_nunca_ponto_flutuante(tmp_path: Path) -> None:
    """A tolerância vem de cadeia decimal e chega como `Decimal` exato (R2.8, R11.12)."""
    caminho = escrever(tmp_path, "algebra.adia.toml", item(tolerancia='"0.05"'))

    lido = banco(carregar([caminho])).itens[0]

    assert lido.tolerancia == Decimal("0.05")
    assert isinstance(lido.tolerancia, Decimal)
    assert str(lido.tolerancia) == "0.05"


def test_ponto_flutuante_na_tolerancia_e_recusado(tmp_path: Path) -> None:
    """`tolerancia = 0.05` em ponto flutuante é erro de gramática, não conversão silenciosa.

    O valor binário mais próximo de 0,05 é 0,05000000000000000277..., e a tolerância decide o
    acerto de item de fronteira (R4.2). Aceitar o ponto flutuante seria aceitar um critério de
    acerto ligeiramente diferente do declarado no arquivo.
    """
    texto = item(tolerancia="0.05")
    caminho = escrever(tmp_path, "algebra.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeGramatica)
    assert erro.campo == "tolerancia"
    assert erro.linha == linha_de(texto, "tolerancia = 0.05")
    assert "ponto flutuante" in erro.mensagem


def test_colecoes_sao_conjuntos_ordenados(tmp_path: Path) -> None:
    """Coleções são lidas ordenadas, porque são conjuntos escritos como lista (R3.4, R3.5)."""
    texto = item(
        tipo_gabarito='"textual"',
        tolerancia=None,
        termos='[["somar", "ambos"], ["dividir"]]',
        extras=('variacoes_gabarito = ["quatro", "4"]',),
    )
    caminho = escrever(tmp_path, "algebra.adia.toml", texto)

    lido = banco(carregar([caminho])).itens[0]

    assert lido.variacoes_gabarito == ("4", "quatro")
    assert lido.termos_essenciais == (("ambos", "somar"), ("dividir",))


def test_enunciado_multilinha_nao_desloca_a_linha_relatada(tmp_path: Path) -> None:
    """Conteúdo de bloco que **parece** estrutura de TOML não confunde a apuração da linha.

    O enunciado abaixo contém uma linha começando por `[[item]]` e uma linha que parece
    atribuição de campo. Uma varredura linha a linha ingênua contaria um item a mais e
    relataria a linha errada — e linha errada em arquivo de 300 linhas é o mesmo que nenhuma
    linha.
    """
    enunciado = '"""\nConsidere a tabela:\n[[item]]\ndificuldade = 99\nQual o valor de x?\n"""'
    texto = item(enunciado=enunciado, dificuldade="7")
    caminho = escrever(tmp_path, "algebra.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeFaixa)
    assert erro.campo == "dificuldade"
    assert erro.linha == linha_de(texto, "dificuldade = 7") == 10
    assert linha_de(texto, "dificuldade = 99") == 6, "a armadilha precisa estar dentro do bloco"


def test_arquivos_de_itens_lista_o_diretorio_em_ordem_estavel(tmp_path: Path) -> None:
    """A ordem do conjunto não depende da ordem do sistema de arquivos (R26)."""
    escrever(tmp_path, "zebra.adia.toml", item("z-001"))
    escrever(tmp_path, "alfa.adia.toml", item("a-001"))
    escrever(tmp_path, "ignorado.toml", "conteúdo que não é arquivo de definição")

    caminhos = arquivos_de_itens(tmp_path)

    assert [caminho.name for caminho in caminhos] == ["alfa.adia.toml", "zebra.adia.toml"]


# --------------------------------------------------------------------------- #
# As nove classes de falha de §3.1
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Caso:
    """Uma classe de falha, o conjunto de arquivos que a produz e a rejeição esperada."""

    nome: str
    arquivos: Mapping[str, str]
    tipo: type[ErroDeCarga]
    campo: str
    arquivo_do_erro: str = "quebrado.adia.toml"


ITEM_SEM_TOLERANCIA: str = item("num-001", tolerancia=None)
ITEM_TEXTUAL_SEM_TERMOS: str = item("txt-001", tipo_gabarito='"textual"', tolerancia=None)
ITEM_ETAPAS_VAZIAS: str = item("vaz-001", etapas="[]")
ITEM_SEM_DICA_L3: str = item("dic-001", dicas={k: v for k, v in DICAS_PADRAO.items() if k != "L3"})
ITEM_DIFICULDADE_ALTA: str = item("dif-001", dificuldade="9")
ITEM_CHAVE_DESCONHECIDA: str = item("chv-001", extras=('toleranica = "0.01"',))

PRATICADO_SEM_EQUIVALENTE: str = "\n".join(
    (
        item("ass-001", etapas='["pratica_assistida"]'),
        item("ass-002", enunciado='"Determine x em 3x - 6 = 9."', transferencia="true"),
        relacao("ass-001", "ass-002", "transferencia"),
    )
)

TRANSFERENCIA_ISOMORFA: str = "\n".join(
    (
        item("cnf-001", etapas='["pratica_assistida"]'),
        item("cnf-002", enunciado='"Determine x em 3x - 6 = 9."', transferencia="true"),
        item("cnf-003", enunciado='"Quantos km cabem em 15 reais a 3 por km mais 6?"', transferencia="true"),
        relacao("cnf-001", "cnf-002", "equivalente"),
        relacao("cnf-001", "cnf-003", "transferencia"),
    )
)

CASOS: tuple[Caso, ...] = (
    Caso(
        nome="gramatica_sintaxe",
        arquivos={"quebrado.adia.toml": '[[item]]\nid = = "x"\n'},
        tipo=ErroDeGramatica,
        campo="arquivo",
    ),
    Caso(
        nome="gramatica_chave_desconhecida",
        arquivos={"quebrado.adia.toml": ITEM_CHAVE_DESCONHECIDA},
        tipo=ErroDeGramatica,
        campo="toleranica",
    ),
    Caso(
        nome="identificador_duplicado",
        arquivos={
            "quebrado.adia.toml": item("rep-001"),
            "quebrado-2.adia.toml": item("rep-001", enunciado='"Outro enunciado para o mesmo id."'),
        },
        tipo=ErroDeIdentificadorDuplicado,
        campo="id",
        arquivo_do_erro="quebrado-2.adia.toml",
    ),
    Caso(
        nome="associacao_ausente",
        arquivos={"quebrado.adia.toml": PRATICADO_SEM_EQUIVALENTE},
        tipo=ErroDeAssociacaoAusente,
        campo="relacao.equivalente",
    ),
    Caso(
        nome="conflito_de_relacao",
        arquivos={"quebrado.adia.toml": TRANSFERENCIA_ISOMORFA},
        tipo=ErroDeConflitoDeRelacao,
        campo="relacao.equivalente",
    ),
    Caso(
        nome="tolerancia_ausente",
        arquivos={"quebrado.adia.toml": ITEM_SEM_TOLERANCIA},
        tipo=ErroDePerfilIncompleto,
        campo="tolerancia",
    ),
    Caso(
        nome="termos_essenciais_ausentes",
        arquivos={"quebrado.adia.toml": ITEM_TEXTUAL_SEM_TERMOS},
        tipo=ErroDePerfilIncompleto,
        campo="termos_essenciais",
    ),
    Caso(
        nome="etapas_vazias",
        arquivos={"quebrado.adia.toml": ITEM_ETAPAS_VAZIAS},
        tipo=ErroDeEtapasVazias,
        campo="etapas_permitidas",
    ),
    Caso(
        nome="dica_ausente",
        arquivos={"quebrado.adia.toml": ITEM_SEM_DICA_L3},
        tipo=ErroDeDicaAusente,
        campo="dicas.L3",
    ),
    Caso(
        nome="dificuldade_fora_da_faixa",
        arquivos={"quebrado.adia.toml": ITEM_DIFICULDADE_ALTA},
        tipo=ErroDeFaixa,
        campo="dificuldade",
    ),
)
"""As nove classes de falha de §3.1. A gramática aparece em duas formas — sintaxe e estrutura
— porque o texto do requisito trata as duas como a mesma rejeição e os caminhos de código são
diferentes: uma vem do interpretador, a outra da verificação de vocabulário."""


@pytest.mark.parametrize("caso", CASOS, ids=[caso.nome for caso in CASOS])
def test_cada_classe_de_falha_e_recusada_com_arquivo_e_campo(tmp_path: Path, caso: Caso) -> None:
    """Toda falha de carga é recusada nomeando arquivo e campo (R3.2)."""
    caminhos = [escrever(tmp_path, nome, texto) for nome, texto in caso.arquivos.items()]

    erro = recusa(carregar(caminhos))

    assert isinstance(erro, caso.tipo)
    assert erro.campo == caso.campo
    assert erro.arquivo == tmp_path / caso.arquivo_do_erro
    assert str(erro.arquivo) in erro.mensagem
    assert f"`{caso.campo}`" in erro.mensagem


@pytest.mark.parametrize("caso", CASOS, ids=[caso.nome for caso in CASOS])
def test_a_carga_e_atomica_em_toda_classe_de_falha(tmp_path: Path, caso: Caso) -> None:
    """Nenhum item é publicado quando qualquer arquivo falha (§7.2).

    O conjunto tem um arquivo **válido** com três itens e o arquivo quebrado do caso. As duas
    ordens são verificadas, porque "carregar o que deu" se esconderia na ordem: um carregador
    que publicasse o que já tinha lido passaria na ordem em que o quebrado vem primeiro e
    falharia na outra.
    """
    valido = escrever(tmp_path, "valido.adia.toml", conjunto_valido())
    quebrados = [escrever(tmp_path, nome, texto) for nome, texto in caso.arquivos.items()]

    assert len(banco(carregar([valido])).itens) == 3, "o arquivo válido sozinho precisa carregar"

    for ordem in ([valido, *quebrados], [*quebrados, valido]):
        resultado = carregar(ordem)
        erro = recusa(resultado)
        assert isinstance(erro, caso.tipo)
        assert not hasattr(erro, "itens"), "o erro não carrega item nenhum"
        assert not isinstance(resultado, CargaConcluida)


# --------------------------------------------------------------------------- #
# Detalhe de cada rejeição
# --------------------------------------------------------------------------- #


def test_sintaxe_invalida_identifica_a_linha_do_interpretador(tmp_path: Path) -> None:
    """Erro de sintaxe traz a linha apurada pelo interpretador de TOML (R3.2)."""
    texto = '[[item]]\nid = "ok-001"\ndificuldade = = 2\n'
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeGramatica)
    assert erro.linha == 3
    assert "sintaxe TOML inválida" in erro.mensagem


def test_chave_desconhecida_identifica_a_linha_exata(tmp_path: Path) -> None:
    """Campo com nome errado é recusado em vez de ignorado.

    `toleranica` com as letras trocadas é o caso real: ignorado, produziria um item numérico
    **sem** tolerância declarada, isto é, perfil incompleto apresentado como item válido. Já
    `tolerância` com acento nem chega aqui — chave sem aspas em TOML é ASCII, e o próprio
    interpretador recusa a linha.
    """
    caminho = escrever(tmp_path, "quebrado.adia.toml", ITEM_CHAVE_DESCONHECIDA)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeGramatica)
    assert erro.campo == "toleranica"
    assert erro.linha == linha_de(ITEM_CHAVE_DESCONHECIDA, "toleranica")
    assert "chave desconhecida" in erro.mensagem


def test_campo_com_acento_e_recusado_pela_sintaxe(tmp_path: Path) -> None:
    """Nome de campo acentuado é erro de sintaxe, não campo ignorado (R3.2)."""
    texto = item("acn-001", extras=('tolerância = "0.01"',))
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeGramatica)
    assert erro.linha == linha_de(texto, "tolerância")


def test_identificador_duplicado_nomeia_os_dois_arquivos(tmp_path: Path) -> None:
    """A rejeição por `id` repetido nomeia os dois arquivos em que o `id` aparece (R3.6, §7.2)."""
    primeiro = escrever(tmp_path, "a.adia.toml", item("rep-001"))
    segundo = escrever(tmp_path, "b.adia.toml", item("rep-001", enunciado='"Outro enunciado."'))

    erro = recusa(carregar([primeiro, segundo]))

    assert isinstance(erro, ErroDeIdentificadorDuplicado)
    assert erro.identificador == "rep-001"
    assert erro.arquivo == segundo
    assert erro.arquivo_anterior == primeiro
    assert erro.linha == erro.linha_anterior == 2
    assert str(primeiro) in erro.mensagem and str(segundo) in erro.mensagem


def test_identificador_duplicado_dentro_do_mesmo_arquivo(tmp_path: Path) -> None:
    """Repetição no mesmo arquivo é a mesma falha, com as duas linhas distintas."""
    texto = item("rep-001") + "\n" + item("rep-001", enunciado='"Outro enunciado."')
    caminho = escrever(tmp_path, "unico.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeIdentificadorDuplicado)
    assert erro.arquivo == erro.arquivo_anterior == caminho
    assert erro.linha_anterior == 2
    assert erro.linha is not None and erro.linha > 2


@pytest.mark.parametrize(
    ("ausente", "arquivo"),
    (
        ("relacao.equivalente", PRATICADO_SEM_EQUIVALENTE),
        (
            "relacao.transferencia",
            "\n".join(
                (
                    item("ass-001", etapas='["pratica_assistida"]'),
                    item("ass-002", enunciado='"Determine x em 3x - 6 = 9."'),
                    relacao("ass-001", "ass-002", "equivalente"),
                )
            ),
        ),
    ),
    ids=("equivalente", "transferencia"),
)
def test_associacao_ausente_reporta_qual_das_duas_falta(tmp_path: Path, ausente: str, arquivo: str) -> None:
    """Item praticado sem equivalente **ou** sem transferência diz qual falta (R2.6)."""
    caminho = escrever(tmp_path, "quebrado.adia.toml", arquivo)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeAssociacaoAusente)
    assert erro.campo == ausente
    assert erro.identificador == "ass-001"
    assert erro.associacao == ausente.removeprefix("relacao.")
    assert erro.linha == linha_de(arquivo, 'id = "ass-001"')


def test_equivalente_que_nao_cumpre_o_isomorfismo_conta_como_ausente(tmp_path: Path) -> None:
    """Relação declarada que não qualifica é ausência, não pareamento parcial (R2.2).

    O candidato abaixo tem a mesma habilidade e enunciado distinto, mas dificuldade diferente:
    pareá-lo faria o desafio independente medir uma tarefa mais fácil que a praticada, e a
    comparação entre assistido e independente deixaria de dizer o que diz.
    """
    texto = "\n".join(
        (
            item("iso-001", etapas='["pratica_assistida"]', dificuldade="2"),
            item("iso-002", enunciado='"Determine x em 3x - 6 = 9."', dificuldade="5"),
            item("iso-003", enunciado='"Quantos km cabem em 15 reais?"', transferencia="true"),
            relacao("iso-001", "iso-002", "equivalente"),
            relacao("iso-001", "iso-003", "transferencia"),
        )
    )
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeAssociacaoAusente)
    assert erro.associacao == "equivalente"
    assert erro.candidatos_desqualificados == 1
    assert "mesma dificuldade" in erro.mensagem


def test_conflito_de_relacao_recusa_transferencia_isomorfa(tmp_path: Path) -> None:
    """Item de transferência isomorfo a praticado da mesma habilidade é recusado (R2.9)."""
    caminho = escrever(tmp_path, "quebrado.adia.toml", TRANSFERENCIA_ISOMORFA)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeConflitoDeRelacao)
    assert erro.identificador == "cnf-002"
    assert erro.item_praticado == "cnf-001"
    assert erro.habilidade_alvo == "equacao_linear"
    assert erro.linha == linha_de(TRANSFERENCIA_ISOMORFA, 'tipo = "equivalente"')


def test_conflito_de_relacao_vale_nas_duas_direcoes(tmp_path: Path) -> None:
    """Escrever a relação de trás para frente produz a mesma inflação da TT (R2.9)."""
    texto = "\n".join(
        (
            item("cnf-001", etapas='["pratica_assistida"]'),
            item("cnf-002", enunciado='"Determine x em 3x - 6 = 9."', transferencia="true"),
            item("cnf-003", enunciado='"Quantos km cabem em 15 reais?"', transferencia="true"),
            relacao("cnf-002", "cnf-001", "equivalente"),
            relacao("cnf-001", "cnf-003", "transferencia"),
        )
    )
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeConflitoDeRelacao)
    assert erro.identificador == "cnf-002"
    assert erro.item_praticado == "cnf-001"


@pytest.mark.parametrize(
    ("campo", "arquivo", "tipo"),
    (
        ("tolerancia", ITEM_SEM_TOLERANCIA, "numerico"),
        ("termos_essenciais", ITEM_TEXTUAL_SEM_TERMOS, "textual"),
    ),
    ids=("tolerancia", "termos_essenciais"),
)
def test_perfil_incompleto_aponta_o_campo_que_o_tipo_exige(
    tmp_path: Path, campo: str, arquivo: str, tipo: str
) -> None:
    """Falta o campo que o tipo de gabarito torna obrigatório (R2.8, R2.11).

    A linha é a do cabeçalho `[[item]]`, porque o campo ausente não tem linha própria: é a
    aproximação declarada no cabeçalho do carregador, não precisão fingida.
    """
    caminho = escrever(tmp_path, "quebrado.adia.toml", arquivo)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDePerfilIncompleto)
    assert erro.campo == campo
    assert erro.tipo_gabarito == tipo
    assert erro.linha == linha_de(arquivo, "[[item]]")


@pytest.mark.parametrize(
    ("forma", "etapas"), (("lista_vazia", "[]"), ("campo_ausente", None)), ids=("vazia", "ausente")
)
def test_etapas_permitidas_vazias_ou_ausentes_sao_recusadas(
    tmp_path: Path, forma: str, etapas: str | None
) -> None:
    """Conjunto de etapas vazio e campo ausente são o mesmo defeito (R2.4)."""
    texto = item("vaz-001", etapas=etapas)
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeEtapasVazias)
    assert erro.campo == "etapas_permitidas"
    assert erro.identificador == "vaz-001"
    assert erro.linha == linha_de(texto, "etapas_permitidas" if forma == "lista_vazia" else "[[item]]")


@pytest.mark.parametrize("nivel", tuple(Nivel), ids=[nivel.name for nivel in Nivel])
def test_dica_faltando_em_qualquer_nivel_e_recusada(tmp_path: Path, nivel: Nivel) -> None:
    """R2.1 exige exatamente uma dica pré-escrita por nível de L1 a L4."""
    dicas = {chave: valor for chave, valor in DICAS_PADRAO.items() if chave != nivel.name}
    texto = item("dic-001", dicas=dicas)
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeDicaAusente)
    assert erro.nivel is nivel
    assert erro.campo == f"dicas.{nivel.name}"
    assert erro.linha == linha_de(texto, "[item.dicas]")


def test_dica_declarada_vazia_conta_como_ausente(tmp_path: Path) -> None:
    """Espaço em branco não é dica: o nível fica indisponível quando a geração falha (D15)."""
    texto = item("dic-002", dicas={**DICAS_PADRAO, "L2": '"   "'})
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeDicaAusente)
    assert erro.nivel is Nivel.L2
    assert erro.linha == linha_de(texto, "L2 =")


@pytest.mark.parametrize("dificuldade", ("0", "6", "-1"))
def test_dificuldade_fora_de_um_a_cinco_e_recusada(tmp_path: Path, dificuldade: str) -> None:
    """A faixa fechada de 1 a 5 é a escala de DO-01 (R2.1)."""
    texto = item("dif-001", dificuldade=dificuldade)
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeFaixa)
    assert erro.campo == "dificuldade"
    assert erro.faixa == "de 1 a 5"
    assert erro.linha == linha_de(texto, f"dificuldade = {dificuldade}")


# --------------------------------------------------------------------------- #
# Codificação e sigilo da mensagem
# --------------------------------------------------------------------------- #


def test_marca_de_ordem_de_bytes_e_recusada(tmp_path: Path) -> None:
    """A gramática declara UTF-8 **sem** BOM, e aceitar a marca quebraria a ida e volta de R3.5."""
    caminho = tmp_path / "com-bom.adia.toml"
    caminho.write_bytes(b"\xef\xbb\xbf" + conjunto_valido().encode("utf-8"))

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeGramatica)
    assert erro.campo == "arquivo"
    assert "marca de ordem de bytes" in erro.mensagem


def test_arquivo_inexistente_e_a_unica_falha_sem_linha(tmp_path: Path) -> None:
    """Sem texto não há linha a apontar, e o erro não inventa uma."""
    erro = recusa(carregar([tmp_path / "ausente.adia.toml"]))

    assert isinstance(erro, ErroDeGramatica)
    assert erro.linha is None
    assert erro.campo == "arquivo"
    assert str(tmp_path / "ausente.adia.toml") in erro.mensagem


@pytest.mark.parametrize(
    ("campo", "texto_do_item", "segredo"),
    (
        ("gabarito", item("seg-001", gabarito="42"), "42"),
        ("variacoes_gabarito", item("seg-001", extras=("variacoes_gabarito = [7, 7]",)), "7"),
        (
            "termos_essenciais",
            item("seg-001", tipo_gabarito='"textual"', tolerancia=None, termos='[["dividir", "dividir"]]'),
            "dividir",
        ),
    ),
    ids=("gabarito", "variacoes_gabarito", "termos_essenciais"),
)
def test_mensagem_de_erro_nao_cita_conteudo_do_item(
    tmp_path: Path, campo: str, texto_do_item: str, segredo: str
) -> None:
    """Nenhuma mensagem interpola gabarito, variação de gabarito ou termo essencial (§6 da gramática).

    Mensagem de erro vai para o terminal de quem roda `adia itens validar`, para o log de
    subida da API e, no pior caso, para uma captura de tela em sala. Gabarito ali é vazamento
    por outro caminho — o mesmo que a `Guarda_de_Vazamento` fecha no texto da dica.
    """
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto_do_item)

    erro = recusa(carregar([caminho]))

    assert erro.campo == campo
    assert segredo not in erro.mensagem
    if "repetido" in erro.mensagem:
        assert VALOR_OMITIDO in erro.mensagem


def test_etapa_desconhecida_e_recusada(tmp_path: Path) -> None:
    """Etapa fora da enumeração do protocolo não entra no conjunto permitido (R2.4, R12.1)."""
    texto = item("etp-001", etapas='["revisao_livre"]')
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeGramatica)
    assert erro.campo == "etapas_permitidas"
    assert erro.linha == linha_de(texto, "etapas_permitidas")
    assert "etapa desconhecida" in erro.mensagem


def test_relacao_para_item_inexistente_e_recusada(tmp_path: Path) -> None:
    """Relação precisa ligar dois itens declarados, ou aponta para um banco que não existe."""
    texto = item("rel-001") + "\n" + relacao("rel-001", "rel-999", "equivalente")
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeGramatica)
    assert erro.campo == "item_destino"
    assert erro.linha == linha_de(texto, 'item_destino = "rel-999"')
    assert "não corresponde a nenhum item declarado" in erro.mensagem


def test_duas_relacoes_sobre_o_mesmo_par_sao_recusadas(tmp_path: Path) -> None:
    """Par com `equivalente` e `transferencia` é contradição, e a leitura não desempata."""
    texto = "\n".join(
        (
            item("par-001", etapas='["pratica_assistida"]'),
            item("par-002", enunciado='"Determine x em 3x - 6 = 9."', transferencia="true"),
            relacao("par-001", "par-002", "equivalente"),
            relacao("par-002", "par-001", "transferencia"),
        )
    )
    caminho = escrever(tmp_path, "quebrado.adia.toml", texto)

    erro = recusa(carregar([caminho]))

    assert isinstance(erro, ErroDeGramatica)
    assert erro.campo == "tipo"
    assert "no máximo uma relação" in erro.mensagem


def test_item_construido_em_codigo_tambem_recusa_perfil_incompleto() -> None:
    """A invariante do item não depende de passar pelo carregador (§7.2, falha fechada)."""
    with pytest.raises(ValueError, match="tolerância"):
        Item(
            id="num-001",
            enunciado="Resolva 2x + 3 = 11.",
            habilidade_alvo="equacao_linear",
            dificuldade=2,
            tamanho_max_resposta=120,
            tipo_gabarito=TipoGabarito.NUMERICO,
            gabarito="4",
            tolerancia=None,
            unidade=None,
            sinonimos_unidade=(),
            variacoes_gabarito=(),
            termos_essenciais=(),
            incognita="x",
            etapas_permitidas=frozenset({Etapa.LINHA_DE_BASE}),
            transferencia=False,
            dicas={nivel: f"dica de {nivel.name}" for nivel in Nivel},
        )
