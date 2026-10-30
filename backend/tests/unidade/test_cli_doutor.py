"""Testes de unidade do `adia doutor` e do esqueleto da CLI (R1.7, R1.11).

Exemplos nomeados sobre a parte determinística do comando: leitura das versões
exigidas dos arquivos de fixação, comparação de versões, classificação em
`presente`, `ausente` e `divergente`, e o código de saída que R1.11 exige.

A detecção em si — `shutil.which` mais o comando de versão de cada ferramenta,
mais a sondagem do serviço de inferência — fica fora daqui por dois motivos. O
primeiro é que ela observa a máquina, e um teste que afirmasse qual versão de
Node.js está instalada falharia por motivo certo na máquina errada. O segundo é
que a sondagem do laço local é exatamente o que a fixture `ollama_proibido`
(tarefa 1.7) intercepta; teste que a dispare passaria a reprovar quando a
fixture entrar, e com razão. O que estes testes fixam é a **regra**, alimentada
por detecções construídas à mão.

R1 não tem propriedade associada na matriz de rastreabilidade do design: §6.1
verifica ambiente e estrutura por exemplos e conjuntos declarados, e as 37
propriedades são conjunto fechado e numerado. Por isso este arquivo fica em
`unidade/` e não em `propriedades/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adia import caminhos, cli

# --------------------------------------------------------------------------- #
# Leitura de versão
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("saida", "esperado"),
    [
        ("Python 3.13.14", "3.13.14"),
        ("uv 0.11.1 (a6042f67f 2026-03-24 x86_64-pc-windows-msvc)", "0.11.1"),
        ("v25.5.0\n", "25.5.0"),
        ("11.8.0\n", "11.8.0"),
        ("git version 2.55.0.windows.3", "2.55.0"),
        ("ollama version is 0.40.8", "0.40.8"),
        ("", None),
        ("comando não reconhecido", None),
    ],
)
def test_extrair_versao_le_a_saida_real_de_cada_ferramenta(saida: str, esperado: str | None) -> None:
    assert cli.extrair_versao(saida) == esperado


def test_numerar_descarta_componentes_alem_do_terceiro() -> None:
    assert cli.numerar("3.13.14") == (3, 13, 14)
    assert cli.numerar("3.13") == (3, 13, 0)
    assert cli.numerar("24") == (24, 0, 0)
    assert cli.numerar("sem número") is None


def test_faixa_por_prefixo_respeita_a_precisao_declarada() -> None:
    """`3.13` aceita toda a linha 3.13; `24` aceita toda a linha 24 (R1.2, R1.5)."""
    python = cli.faixa_por_prefixo("3.13")
    assert python is not None
    assert python.contem((3, 13, 0))
    assert python.contem((3, 13, 14))
    assert not python.contem((3, 14, 0))
    assert not python.contem((3, 12, 11))

    node = cli.faixa_por_prefixo("24")
    assert node is not None
    assert node.contem((24, 0, 0))
    assert node.contem((24, 22, 1))
    assert not node.contem((25, 5, 0))
    assert not node.contem((23, 11, 1))


def test_faixa_por_prefixo_com_versao_completa_aceita_so_ela() -> None:
    faixa = cli.faixa_por_prefixo("3.13.2")
    assert faixa is not None
    assert faixa.contem((3, 13, 2))
    assert not faixa.contem((3, 13, 3))
    assert not faixa.contem((3, 13, 1))


@pytest.mark.parametrize("conteudo", ["lts/iron", "", "3.13.2.1", "3.x"])
def test_faixa_por_prefixo_recusa_o_que_nao_e_versao(conteudo: str) -> None:
    assert cli.faixa_por_prefixo(conteudo) is None


def test_faixa_de_intervalo_le_o_campo_engines() -> None:
    faixa = cli.faixa_de_intervalo(">=11 <12")
    assert faixa is not None
    assert faixa.contem((11, 0, 0))
    assert faixa.contem((11, 8, 0))
    assert not faixa.contem((12, 0, 0))
    assert not faixa.contem((10, 9, 3))


@pytest.mark.parametrize("intervalo", ["^11.8.0", "~11", "*", "<12", "11 || 12"])
def test_faixa_de_intervalo_recusa_operador_que_nao_reconhece(intervalo: str) -> None:
    """Melhor dizer que não soube ler a exigência do que adivinhar uma."""
    assert cli.faixa_de_intervalo(intervalo) is None


# --------------------------------------------------------------------------- #
# Classificação da situação
# --------------------------------------------------------------------------- #


def _exigencia(declarada: str) -> cli.Exigencia:
    return cli.Exigencia(
        texto=declarada,
        fonte="teste",
        faixa=cli.faixa_por_prefixo(declarada),
    )


def test_versao_dentro_da_faixa_e_presente() -> None:
    assert cli.classificar(cli.Deteccao("3.13.14"), _exigencia("3.13")) == "presente"


def test_versao_fora_da_faixa_e_divergente() -> None:
    """O caso real desta máquina: Node 25.5.0 contra a linha 24 fixada (D7)."""
    assert cli.classificar(cli.Deteccao("25.5.0"), _exigencia("24")) == "divergente"


def test_ferramenta_sem_resposta_e_ausente() -> None:
    deteccao = cli.Deteccao(None, "executável `node` não encontrado no PATH")
    assert cli.classificar(deteccao, _exigencia("24")) == "ausente"


def test_tempo_limite_esgotado_e_ausente() -> None:
    """R1.7: ferramenta cujo comando de versão não responde em 5 s é `ausente`."""
    deteccao = cli.Deteccao(None, "o comando de versão não respondeu em 5 s")
    assert cli.classificar(deteccao, _exigencia("24")) == "ausente"
    assert cli.TEMPO_LIMITE_VERSAO_S == 5.0


def test_ferramenta_sem_versao_fixada_nunca_diverge() -> None:
    """`uv`, `git` e Ollama não têm versão exigida: ou respondem, ou estão ausentes."""
    sem_exigencia = cli.Exigencia(texto=cli.SEM_VERSAO_FIXADA, fonte="-", faixa=None)
    assert cli.classificar(cli.Deteccao("0.11.1"), sem_exigencia) == "presente"
    assert cli.classificar(cli.Deteccao(None, "ausente"), sem_exigencia) == "ausente"


# --------------------------------------------------------------------------- #
# Leitura dos arquivos de fixação
# --------------------------------------------------------------------------- #


def _montar_raiz(
    diretorio: Path,
    *,
    python: str | None = "3.13\n",
    node: str | None = "24\n",
    npm: str | None = ">=11 <12",
) -> Path:
    """Monta uma raiz de projeto de mentira com os arquivos de fixação pedidos."""
    (diretorio / "pyproject.toml").write_text('[project]\nname = "adia"\n', encoding="utf-8")
    if python is not None:
        (diretorio / ".python-version").write_text(python, encoding="utf-8")
    if node is not None:
        (diretorio / ".nvmrc").write_text(node, encoding="utf-8")
    conteudo: dict[str, object] = {"name": "adia-framework"}
    if npm is not None:
        conteudo["engines"] = {"node": ">=24 <25", "npm": npm}
    (diretorio / "package.json").write_text(json.dumps(conteudo), encoding="utf-8")
    return diretorio


def test_exigencias_vem_dos_arquivos_de_fixacao(tmp_path: Path) -> None:
    """Nenhuma versão exigida é embutida em código: todas vêm de arquivo."""
    raiz = _montar_raiz(tmp_path, python="3.12\n", node="22\n", npm=">=10 <11")
    exigencias = cli.montar_exigencias(raiz)
    assert exigencias["Python"].texto == "3.12.x"
    assert exigencias["Python"].fonte == caminhos.ARQUIVO_PYTHON
    assert exigencias["Node.js"].texto == "22.x"
    assert exigencias["Node.js"].fonte == cli.ARQUIVO_NODE
    assert exigencias["npm"].texto == ">=10 <11"
    assert exigencias["uv"].texto == cli.SEM_VERSAO_FIXADA
    assert exigencias["git"].texto == cli.SEM_VERSAO_FIXADA
    assert exigencias["Ollama"].texto == cli.SEM_VERSAO_FIXADA


def test_relatorio_cobre_as_seis_ferramentas_de_r1_7(tmp_path: Path) -> None:
    exigencias = cli.montar_exigencias(_montar_raiz(tmp_path))
    assert list(exigencias) == ["Python", "uv", "Node.js", "npm", "git", "Ollama"]


def test_fixacao_lida_nao_deixa_problema_pendente(tmp_path: Path) -> None:
    exigencias = cli.montar_exigencias(_montar_raiz(tmp_path))
    assert [e.problema for e in exigencias.values() if e.problema is not None] == []


def test_arquivo_de_fixacao_ausente_vira_problema_declarado(tmp_path: Path) -> None:
    exigencias = cli.montar_exigencias(_montar_raiz(tmp_path, node=None))
    problema = exigencias["Node.js"].problema
    assert problema is not None
    assert "`.nvmrc` ausente" in problema
    assert exigencias["Node.js"].texto == cli.EXIGENCIA_INDETERMINADA


def test_fixacao_ilegivel_e_reportada_em_vez_de_adivinhada(tmp_path: Path) -> None:
    exigencias = cli.montar_exigencias(_montar_raiz(tmp_path, node="lts/iron\n"))
    problema = exigencias["Node.js"].problema
    assert problema is not None
    assert "não declara versão reconhecível" in problema


def test_package_json_sem_engines_vira_problema_declarado(tmp_path: Path) -> None:
    exigencias = cli.montar_exigencias(_montar_raiz(tmp_path, npm=None))
    problema = exigencias["npm"].problema
    assert problema is not None
    assert "não declara `engines`" in problema


def test_engines_sem_npm_vira_problema_declarado(tmp_path: Path) -> None:
    raiz = _montar_raiz(tmp_path)
    conteudo = json.dumps({"name": "adia-framework", "engines": {"node": ">=24 <25"}})
    (raiz / "package.json").write_text(conteudo, encoding="utf-8")
    problema = cli.montar_exigencias(raiz)["npm"].problema
    assert problema is not None
    assert "`engines.npm` ausente" in problema


def test_package_json_invalido_vira_problema_declarado(tmp_path: Path) -> None:
    raiz = _montar_raiz(tmp_path)
    (raiz / "package.json").write_text("{não é json}", encoding="utf-8")
    problema = cli.montar_exigencias(raiz)["npm"].problema
    assert problema is not None
    assert "inválido" in problema


def test_sem_raiz_nenhuma_exigencia_e_conhecida() -> None:
    exigencias = cli.montar_exigencias(None)
    fixadas = [nome for nome, e in exigencias.items() if e.problema is not None]
    assert fixadas == ["Python", "Node.js", "npm"]


def test_encontrar_raiz_sobe_a_arvore(tmp_path: Path) -> None:
    raiz = _montar_raiz(tmp_path)
    fundo = raiz / "backend" / "adia" / "nucleo"
    fundo.mkdir(parents=True)
    assert caminhos.encontrar_raiz(fundo) == raiz.resolve()


# --------------------------------------------------------------------------- #
# Código de saída e relatório (R1.11)
# --------------------------------------------------------------------------- #


def _verificacao(ferramenta: str, situacao: cli.Situacao) -> cli.Verificacao:
    detectada = {"presente": "24.22.1", "divergente": "25.5.0", "ausente": None}[situacao]
    return cli.Verificacao(
        ferramenta=ferramenta,
        exigencia=_exigencia("24"),
        deteccao=cli.Deteccao(detectada, None if detectada else "não encontrado no PATH"),
        situacao=situacao,
        correcao="instalar a linha exigida",
    )


def _relatorio(*situacoes: cli.Situacao, problemas: tuple[str, ...] = ()) -> cli.Relatorio:
    return cli.Relatorio(
        raiz=Path("C:/projeto"),
        verificacoes=tuple(_verificacao(f"ferramenta-{indice}", situacao) for indice, situacao in enumerate(situacoes)),
        problemas=problemas,
    )


def test_ambiente_todo_presente_termina_com_zero() -> None:
    assert cli.codigo_de_saida(_relatorio("presente", "presente")) == cli.CODIGO_OK


@pytest.mark.parametrize("situacao", ["ausente", "divergente"])
def test_ausente_ou_divergente_termina_com_falha(situacao: cli.Situacao) -> None:
    """R1.11: o comando conclui com indicação de falha nos dois casos."""
    relatorio = _relatorio("presente", situacao)
    assert cli.codigo_de_saida(relatorio) == cli.CODIGO_AMBIENTE_INVALIDO
    assert cli.codigo_de_saida(relatorio) != cli.CODIGO_OK


def test_fixacao_ilegivel_tambem_reprova() -> None:
    """Ambiente que não se sabe verificar não é ambiente verificado."""
    relatorio = _relatorio("presente", problemas=("Node.js: `.nvmrc` ausente ou ilegível",))
    assert cli.codigo_de_saida(relatorio) == cli.CODIGO_AMBIENTE_INVALIDO


def test_relatorio_lista_cada_ferramenta_com_a_situacao_apurada() -> None:
    """R1.11 exige a lista, não só o código de saída."""
    relatorio = cli.Relatorio(
        raiz=Path("C:/projeto"),
        verificacoes=(
            _verificacao("Python", "presente"),
            _verificacao("Node.js", "divergente"),
            _verificacao("git", "ausente"),
        ),
        problemas=(),
    )
    texto = "\n".join(cli.formatar_relatorio(relatorio))
    assert "Versão exigida" in texto
    assert "Versão detectada" in texto
    assert "Situação" in texto
    for esperado in ("Python", "presente", "Node.js", "divergente", "25.5.0", "git", "ausente"):
        assert esperado in texto
    assert "Correção:" in texto
    assert "Nada foi instalado nem alterado" in texto


def test_relatorio_conforme_nao_lista_correcao() -> None:
    texto = "\n".join(cli.formatar_relatorio(_relatorio("presente")))
    assert "Ambiente conforme" in texto
    assert "Correção:" not in texto


# --------------------------------------------------------------------------- #
# Esqueleto da CLI
# --------------------------------------------------------------------------- #


def test_os_nove_comandos_do_design_estao_declarados() -> None:
    """Design §3.18 declara nove comandos, e `participantes` é o décimo; a ajuda os lista todos."""
    assert set(cli.COMANDOS) == {
        "doutor",
        "migrar",
        "itens",
        "guarda",
        "indexar",
        "replay",
        "exportar",
        "excluir-dados",
        "benchmark",
        "participantes",
    }
    ajuda = cli.construir_analisador().format_help()
    for comando in cli.COMANDOS:
        assert comando in ajuda


def test_todo_comando_nao_implementado_tem_fase_e_tarefa_declaradas() -> None:
    """Implementados: `doutor`, `itens`, `excluir-dados` e `participantes`; os seis restantes seguem pendentes."""
    assert set(cli.PENDENTES) == {
        "migrar",
        "guarda verificar",
        "indexar",
        "replay",
        "exportar",
        "benchmark",
    }
    for pendente in cli.PENDENTES.values():
        assert pendente.fase.startswith("Fase ")
        assert pendente.tarefa
        assert pendente.resumo


@pytest.mark.parametrize(
    "invocacao",
    [
        ["migrar"],
        ["guarda", "verificar"],
        ["indexar"],
        ["replay"],
        ["exportar"],
        ["benchmark"],
    ],
)
def test_comando_pendente_informa_a_fase_e_falha(invocacao: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    """Comando ainda não implementado não dá falsa impressão de sucesso."""
    codigo = cli.principal(invocacao)
    saida = capsys.readouterr().out
    assert codigo == cli.CODIGO_NAO_IMPLEMENTADO
    assert codigo != cli.CODIGO_OK
    assert "ainda não está implementado" in saida
    assert "Fase" in saida
    assert "tarefa" in saida
    assert "Nenhuma ação foi executada" in saida


@pytest.mark.parametrize("grupo", ["itens", "guarda"])
def test_grupo_sem_subcomando_e_erro_de_uso(grupo: str) -> None:
    """`adia itens` sem `validar` nem `formatar` é erro de uso, não sucesso."""
    with pytest.raises(SystemExit) as capturado:
        cli.principal([grupo])
    assert capturado.value.code != cli.CODIGO_OK


def test_sem_comando_e_erro_de_uso() -> None:
    with pytest.raises(SystemExit) as capturado:
        cli.principal([])
    assert capturado.value.code != cli.CODIGO_OK
