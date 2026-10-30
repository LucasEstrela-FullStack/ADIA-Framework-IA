"""Testes de `adia itens validar` e `adia itens formatar`.

Os dois comandos são a porta pela qual a gramática de R3 chega a quem escreve o conteúdo, e
cada um tem uma obrigação distinta que estes testes fixam.

`validar` é o passo 4 do portão local (design §6.1), e roda **antes** do `pytest`: um arquivo
de item quebrado reprova o *build* antes de alcançar qualquer máquina de coleta. Para isso o
código de saída precisa ser confiável nos dois sentidos — diferente de zero quando o banco é
inválido, e zero quando é válido, inclusive no caso do banco ainda vazio, que é a situação
declarada do repositório até a tarefa 3.14.

`formatar` **escreve** em `data/itens/`, e é o único comando desta fase que altera arquivo do
repositório. Daí as três afirmações: não grava nada quando a carga falha, não toca arquivo que
já está canônico, e grava em UTF-8 sem BOM com `LF` — porque `write_text` no Windows produziria
`CRLF` e o arquivo passaria a divergir da gramática e do `.gitattributes` a cada formatação.

**Validates: Requirements 3.1, 3.2, 3.3, 3.5**
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adia import caminhos, cli
from adia.nucleo.itens.carregador import SUFIXO_DE_ARQUIVO

# --------------------------------------------------------------------------- #
# Conteúdo de apoio
# --------------------------------------------------------------------------- #

ITEM_VALIDO: str = "\n".join(
    (
        "[[item]]",
        'id = "alg-eq-001"',
        'enunciado = "Resolva a equação 2x + 3 = 11 e informe o valor de x."',
        'habilidade_alvo = "equacao_linear"',
        "dificuldade = 2",
        "tamanho_max_resposta = 120",
        'tipo_gabarito = "numerico"',
        'gabarito = "4"',
        'tolerancia = "0.050"',
        'variacoes_gabarito = ["quatro", "4"]',
        'etapas_permitidas = ["desafio_independente", "linha_de_base"]',
        "",
        "[item.dicas]",
        'L1 = "O que a igualdade afirma sobre os dois lados?"',
        'L2 = "É uma equação do primeiro grau."',
        'L3 = "Isole a incógnita."',
        'L4 = "Em 5y + 2 = 17, subtraia 2 dos dois lados."',
        "",
    )
)
"""Item válido escrito **fora** da forma canônica: chave fora de ordem não há, mas a
tolerância tem zero à direita, a lista está desordenada e as cadeias são de uma linha."""

ITEM_SEM_TOLERANCIA: str = ITEM_VALIDO.replace('tolerancia = "0.050"\n', "")
"""Item numérico sem tolerância: perfil incompleto, recusado por R2.8."""


def escrever(diretorio: Path, nome: str, texto: str) -> Path:
    """Grava em UTF-8 sem BOM, sem tradução de fim de linha."""
    caminho = diretorio / nome
    caminho.write_bytes(texto.encode("utf-8"))
    return caminho


# --------------------------------------------------------------------------- #
# Localização do banco
# --------------------------------------------------------------------------- #


def test_sem_diretorio_o_banco_e_data_itens_sob_a_raiz() -> None:
    """O padrão é o diretório que D12 declara, achado pelas marcas da raiz do projeto."""
    alvo = cli.localizar_itens()

    assert alvo.diretorio is not None
    assert alvo.diretorio.parts[-2:] == caminhos.DIRETORIO_DE_ITENS.parts


def test_diretorio_inexistente_reprova(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Caminho errado silenciado produziria um "banco válido" que ninguém verificou."""
    codigo = cli.itens_validar(str(tmp_path / "nao-existe"))

    assert codigo == cli.CODIGO_BANCO_INVALIDO
    assert "não é um diretório" in capsys.readouterr().out


def test_banco_vazio_passa_com_aviso(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Diretório sem arquivo de definição é caso declarado, não falha.

    Reprovar aqui travaria o portão local inteiro por uma ausência já conhecida: o banco
    inicial entra na tarefa 3.14. O aviso é o que impede a leitura "o banco está bem".
    """
    codigo = cli.itens_validar(str(tmp_path))
    saida = capsys.readouterr().out

    assert codigo == cli.CODIGO_OK
    assert "vazio" in saida
    assert SUFIXO_DE_ARQUIVO in saida
    assert "3.14" in saida
    assert cli.itens_formatar(str(tmp_path)) == cli.CODIGO_OK


# --------------------------------------------------------------------------- #
# `adia itens validar`
# --------------------------------------------------------------------------- #


def test_banco_valido_e_aprovado_com_a_contagem(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    escrever(tmp_path, f"algebra{SUFIXO_DE_ARQUIVO}", ITEM_VALIDO)

    codigo = cli.itens_validar(str(tmp_path))
    saida = capsys.readouterr().out

    assert codigo == cli.CODIGO_OK
    assert "válido" in saida
    assert "1 item(ns)" in saida


def test_banco_invalido_reprova_dizendo_arquivo_linha_e_campo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R3.2 na saída do comando, que é onde quem escreve o conteúdo a lê."""
    caminho = escrever(tmp_path, f"algebra{SUFIXO_DE_ARQUIVO}", ITEM_SEM_TOLERANCIA)

    codigo = cli.itens_validar(str(tmp_path))
    saida = capsys.readouterr().out

    assert codigo == cli.CODIGO_BANCO_INVALIDO
    assert str(caminho) in saida
    assert "tolerancia" in saida
    assert "ErroDePerfilIncompleto" in saida
    assert "atômica" in saida


def test_validar_nao_altera_arquivo_nenhum(tmp_path: Path) -> None:
    """`validar` observa e reporta; reescrever é de `formatar`."""
    caminho = escrever(tmp_path, f"algebra{SUFIXO_DE_ARQUIVO}", ITEM_VALIDO)
    antes = caminho.read_bytes()

    assert cli.itens_validar(str(tmp_path)) == cli.CODIGO_OK
    assert caminho.read_bytes() == antes


# --------------------------------------------------------------------------- #
# `adia itens formatar`
# --------------------------------------------------------------------------- #


def test_formatar_reescreve_na_forma_canonica(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    caminho = escrever(tmp_path, f"algebra{SUFIXO_DE_ARQUIVO}", ITEM_VALIDO)

    codigo = cli.itens_formatar(str(tmp_path))
    saida = capsys.readouterr().out
    gravado = caminho.read_text(encoding="utf-8", newline="")

    assert codigo == cli.CODIGO_OK
    assert "reescrito" in saida
    assert 'enunciado = """' in gravado
    assert 'tolerancia = "0.05"' in gravado
    assert 'variacoes_gabarito = ["4", "quatro"]' in gravado


def test_formatar_grava_em_utf8_sem_bom_com_lf(tmp_path: Path) -> None:
    """`write_text` no Windows produziria `CRLF`; a gramática e o `.gitattributes` exigem `LF`."""
    caminho = escrever(tmp_path, f"algebra{SUFIXO_DE_ARQUIVO}", ITEM_VALIDO)

    assert cli.itens_formatar(str(tmp_path)) == cli.CODIGO_OK

    bytes_gravados = caminho.read_bytes()
    assert not bytes_gravados.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in bytes_gravados
    assert "equação".encode() in bytes_gravados


def test_formatar_e_idempotente_e_nao_toca_arquivo_canonico(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Segunda passada não muda byte nenhum, e o relatório diz que não mudou."""
    caminho = escrever(tmp_path, f"algebra{SUFIXO_DE_ARQUIVO}", ITEM_VALIDO)
    assert cli.itens_formatar(str(tmp_path)) == cli.CODIGO_OK
    canonico = caminho.read_bytes()
    capsys.readouterr()

    codigo = cli.itens_formatar(str(tmp_path))
    saida = capsys.readouterr().out

    assert codigo == cli.CODIGO_OK
    assert caminho.read_bytes() == canonico
    assert "já canônico" in saida
    assert "0 de 1 arquivo(s) reescrito(s)" in saida


def test_formatar_nao_grava_nada_quando_a_carga_falha(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Não se formata o que não carrega, e nem o arquivo bom do conjunto é tocado (§7.2)."""
    bom = escrever(tmp_path, f"bom{SUFIXO_DE_ARQUIVO}", ITEM_VALIDO)
    quebrado = escrever(
        tmp_path, f"quebrado{SUFIXO_DE_ARQUIVO}", ITEM_SEM_TOLERANCIA.replace("alg-eq-001", "alg-eq-009")
    )
    antes = (bom.read_bytes(), quebrado.read_bytes())

    codigo = cli.itens_formatar(str(tmp_path))

    assert codigo == cli.CODIGO_BANCO_INVALIDO
    assert (bom.read_bytes(), quebrado.read_bytes()) == antes
    assert "recusado" in capsys.readouterr().out


def test_formatar_preserva_a_particao_de_arquivos(tmp_path: Path) -> None:
    """Dois arquivos entram, dois arquivos saem: a reescrita não colapsa o banco (R3.3)."""
    primeiro = escrever(tmp_path, f"um{SUFIXO_DE_ARQUIVO}", ITEM_VALIDO)
    segundo = escrever(
        tmp_path, f"dois{SUFIXO_DE_ARQUIVO}", ITEM_VALIDO.replace("alg-eq-001", "alg-eq-002")
    )

    assert cli.itens_formatar(str(tmp_path)) == cli.CODIGO_OK

    assert primeiro.read_text(encoding="utf-8").count("[[item]]") == 1
    assert segundo.read_text(encoding="utf-8").count("[[item]]") == 1
    assert 'id = "alg-eq-001"' in primeiro.read_text(encoding="utf-8")
    assert 'id = "alg-eq-002"' in segundo.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Despacho da linha de comando
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("subcomando", ["validar", "formatar"])
def test_a_linha_de_comando_despacha_os_dois_subcomandos(tmp_path: Path, subcomando: str) -> None:
    """`--diretorio` é o que permite verificar um conjunto sem tocar em `data/itens/`."""
    escrever(tmp_path, f"algebra{SUFIXO_DE_ARQUIVO}", ITEM_VALIDO)

    codigo = cli.principal(["itens", subcomando, "--diretorio", str(tmp_path)])

    assert codigo == cli.CODIGO_OK


@pytest.mark.parametrize("subcomando", ["validar", "formatar"])
def test_os_dois_subcomandos_deixaram_de_ser_pendentes(tmp_path: Path, subcomando: str) -> None:
    """Implementado deixa de informar fase e tarefa, e passa a fazer o trabalho."""
    assert f"itens {subcomando}" not in cli.PENDENTES

    codigo = cli.principal(["itens", subcomando, "--diretorio", str(tmp_path / "nao-existe")])

    assert codigo != cli.CODIGO_NAO_IMPLEMENTADO
