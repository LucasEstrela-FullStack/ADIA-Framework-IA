"""Projeto STEAM: carga do conteúdo, correção das partes, etapa da sessão, rubrica e API (R13)."""

from __future__ import annotations

import shutil
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adia.api.app import criar_app
from adia.caminhos import CHAVE_DO_PROFESSOR
from adia.exportacao.csv_pesquisa import ler_metricas
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.nucleo.sessao.gestor import OperacaoRecusada
from adia.nucleo.steam.cenarios import ErroDeSteam, arquivos_de_steam, carregar
from adia.orquestracao.exportar import exportar
from adia.orquestracao.painel import gerar_painel
from adia.orquestracao.servico import Servico, SessaoInconsistente, SubmissaoInexistente
from adia.persistencia.repositorio import BANCO_DE_DADOS, Repositorio
from adia.tipos import Etapa, Indisponivel

_RAIZ = Path(__file__).resolve().parents[3]
_ITENS = _RAIZ / "data" / "itens"
_STEAM = _RAIZ / "data" / "steam"
_LOCAL = "http://127.0.0.1:8000"
_CERTAS = {
    "retirada_diaria_total": "620 L",
    "metros_dentro_do_limite": "18",
    "chuva_semanal_necessaria": "14,02 mm",
    "economia_mensal": "R$ 101,40",
}
_NIVEIS = {
    "adequacao_do_modelo": "exemplar",
    "interpretacao_no_contexto": "adequado",
    "hipoteses_declaradas": "inicial",
    "recomendacao_sustentada": "ausente",
}


class _ClienteFora(ClienteOllama):
    def disponivel(self) -> bool:
        return False

    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        raise FalhaDeGeracao("dublê")


def _servico(caminho: Path, steam: Path | None = _STEAM) -> Servico:
    return Servico(_ITENS, _ClienteFora(), Repositorio(caminho), diretorio_steam=steam)


def _ate_o_projeto(servico: Servico) -> str:
    sessao_id, sessao = servico.iniciar(servico.repositorio.criar_participantes("turma", 1)[0])
    while sessao.etapa != Etapa.PROJETO_STEAM:
        item = sessao.item_atual
        assert item is not None, f"a sessão parou em {sessao.etapa} sem chegar ao projeto"
        servico.responder(sessao_id, item.gabarito, 10)
    return sessao_id


# --------------------------------------------------------------------------- conteúdo


def test_conteudo_real_carrega_e_corrige_as_partes() -> None:
    conteudo = carregar(arquivos_de_steam(_STEAM))
    cenario = conteudo.para_habilidade("equacao_linear")
    assert cenario is not None
    assert conteudo.para_habilidade("outra") is None
    assert cenario.rubrica.pontos_maximos == 12
    partes = {p.parte: p for p in cenario.partes}
    assert all(partes[nome].corrigir(valor) for nome, valor in _CERTAS.items())
    economia = partes["economia_mensal"]
    assert economia.corrigir("101.4") and economia.corrigir("101,45") and economia.corrigir("101.35 reais")
    assert not economia.corrigir("101,46")
    assert not economia.corrigir("cento e um")
    assert not partes["retirada_diaria_total"].corrigir("621")
    assert partes["retirada_diaria_total"].corrigir("seiscentos e vinte")


def test_diretorio_ausente_e_conteudo_vazio(tmp_path: Path) -> None:
    assert arquivos_de_steam(tmp_path / "nao-existe") == ()
    assert carregar(()).cenarios == ()


_RUBRICA = """
[[rubrica]]
rubrica_id = "rub"
rubrica_versao = 1
titulo = "Rubrica"
criterios_total = 2
descricao = "d"

[[rubrica.criterio]]
criterio = "c1"
descricao = "d"

[[rubrica.criterio.nivel]]
nivel = "baixo"
pontos = 0
descricao = "d"

[[rubrica.criterio.nivel]]
nivel = "alto"
pontos = 1
descricao = "d"

[[rubrica.criterio]]
criterio = "c2"
descricao = "d"

[[rubrica.criterio.nivel]]
nivel = "baixo"
pontos = 0
descricao = "d"

[[rubrica.criterio.nivel]]
nivel = "alto"
pontos = 2
descricao = "d"
"""

_PARTE = """
[[cenario.partes_numericas]]
parte = "p{n}"
pergunta = "q"
unidade = "litros"
sinonimos_unidade = ["L"]
gabarito = "1{n}"
tolerancia = "0"
variacoes_gabarito = ["1{n}"]
tamanho_max_resposta = 10
"""

_CENARIO = (
    """
[[cenario]]
id = "cen"
titulo = "t"
habilidade_alvo = "equacao_linear"
areas = ["ciencias"]
enunciado = "e"
"""
    + "".join(_PARTE.format(n=n) for n in range(3))
    + """
[cenario.justificativa]
pergunta = "q"
tamanho_max_resposta = 100
rubrica_id = "rub"
rubrica_versao = 1
"""
)


def _carregar_texto(tmp_path: Path, texto: str) -> None:
    arquivo = tmp_path / "x.adia.toml"
    arquivo.write_text(texto, encoding="utf-8")
    carregar(arquivos_de_steam(tmp_path))


def test_conteudo_minimo_valido_carrega(tmp_path: Path) -> None:
    (tmp_path / "a.adia.toml").write_text(_RUBRICA, encoding="utf-8")
    (tmp_path / "b.adia.toml").write_text(_CENARIO, encoding="utf-8")
    conteudo = carregar(arquivos_de_steam(tmp_path))
    assert [c.id for c in conteudo.cenarios] == ["cen"]
    assert conteudo.cenarios[0].rubrica.pontos_maximos == 3


@pytest.mark.parametrize(
    ("antigo", "novo", "mensagem"),
    [
        ('id = "cen"', 'id = "cen', "TOML inválido"),
        ('id = "cen"', 'id = "cen"\n[[extra]]', "raiz desconhecida"),
        ('titulo = "t"\n', "", "'titulo': obrigatório"),
        ('titulo = "t"\n', 'titulo = "t"\ncor = "azul"\n', "'cor': campo desconhecido"),
        ('id = "cen"', 'id = "com espaço"', "identificador"),
        ('titulo = "t"', 'titulo = "  "', "texto não vazio"),
        ('areas = ["ciencias"]', "areas = []", "conjunto não vazio"),
        ('areas = ["ciencias"]', 'areas = ["ciências naturais"]', "identificador"),
        ('areas = ["ciencias"]', "areas = [1]", "lista de textos"),
        ('gabarito = "10"', 'gabarito = "10,5"', "cadeia decimal"),
        ('tolerancia = "0"\nvariacoes_gabarito = ["10"]', 'tolerancia = "-1"\nvariacoes_gabarito = ["10"]', "negativa"),
        ('parte = "p1"', 'parte = "p0"', "parte 'p0' repetido"),
        ("tamanho_max_resposta = 100", "tamanho_max_resposta = true", "inteiro"),
        ('rubrica_versao = 1\n"""', 'rubrica_versao = 2\n"""', "não está declarada"),
    ],
)
def test_cenario_fora_da_gramatica_e_recusado(tmp_path: Path, antigo: str, novo: str, mensagem: str) -> None:
    texto = _RUBRICA + _CENARIO + '"""'
    assert antigo in texto, antigo
    with pytest.raises(ErroDeSteam, match=mensagem):
        _carregar_texto(tmp_path, texto.replace(antigo, novo, 1).removesuffix('"""'))


def test_partes_fora_da_faixa_e_sinonimo_sem_unidade(tmp_path: Path) -> None:
    duas = _CENARIO.replace(_PARTE.format(n=2), "")
    with pytest.raises(ErroDeSteam, match="de 3 a 5 tabelas"):
        _carregar_texto(tmp_path, _RUBRICA + duas)
    sem_unidade = _CENARIO.replace('unidade = "litros"\n', "", 1)
    with pytest.raises(ErroDeSteam, match="sinonimos_unidade exige unidade"):
        _carregar_texto(tmp_path, _RUBRICA + sem_unidade)
    with pytest.raises(ErroDeSteam, match="esperava uma tabela"):
        _carregar_texto(tmp_path, "cenario = [1]\n" + _RUBRICA)


@pytest.mark.parametrize(
    ("antigo", "novo", "mensagem"),
    [
        ("criterios_total = 2", "criterios_total = 3", "criterios_total = 3"),
        ("pontos = 2", "pontos = 0", "precisam crescer"),
        ('nivel = "alto"\npontos = 1', 'nivel = "baixo"\npontos = 1', "nível 'baixo' repetido"),
        ('criterio = "c2"', 'criterio = "c1"', "critério 'c1' repetido"),
    ],
)
def test_rubrica_fora_da_gramatica_e_recusada(tmp_path: Path, antigo: str, novo: str, mensagem: str) -> None:
    assert antigo in _RUBRICA
    with pytest.raises(ErroDeSteam, match=mensagem):
        _carregar_texto(tmp_path, _RUBRICA.replace(antigo, novo, 1))


def test_duplicatas_entre_arquivos_sao_recusadas(tmp_path: Path) -> None:
    (tmp_path / "a.adia.toml").write_text(_RUBRICA + _RUBRICA, encoding="utf-8")
    with pytest.raises(ErroDeSteam, match="declarada duas vezes"):
        carregar(arquivos_de_steam(tmp_path))
    (tmp_path / "a.adia.toml").write_text(_RUBRICA + _CENARIO + _CENARIO, encoding="utf-8")
    with pytest.raises(ErroDeSteam, match="cenário 'cen' repetido"):
        carregar(arquivos_de_steam(tmp_path))


def test_servico_recusa_cenario_sem_item_da_habilidade(tmp_path: Path) -> None:
    conteudo = tmp_path / "steam"
    conteudo.mkdir()
    (conteudo / "a.adia.toml").write_text(_RUBRICA + _CENARIO.replace("equacao_linear", "fotossintese"), "utf-8")
    with pytest.raises(RuntimeError, match="nenhum item cobre"):
        _servico(tmp_path / "adia.db", conteudo)
    (conteudo / "a.adia.toml").write_text("[[rubrica]]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Conteúdo STEAM inválido"):
        _servico(tmp_path / "adia.db", conteudo)


# --------------------------------------------------------------------------- sessão


def test_sem_conteudo_steam_a_sessao_encerra_no_posteste(tmp_path: Path) -> None:
    servico = _servico(tmp_path / "adia.db", steam=None)
    sessao_id, sessao = servico.iniciar(servico.repositorio.criar_participantes("turma", 1)[0])
    while not sessao.encerrada:
        item = sessao.item_atual
        assert item is not None
        servico.responder(sessao_id, item.gabarito, 10)
    assert sessao.cenario is None and sessao.steam is None
    with pytest.raises(OperacaoRecusada, match="não está aberto"):
        servico.submeter_steam(sessao_id, _CERTAS, "texto")


def test_projeto_abre_depois_do_posteste_e_encerra_na_submissao(tmp_path: Path) -> None:
    servico = _servico(tmp_path / "adia.db")
    sessao_id = _ate_o_projeto(servico)
    sessao = servico.obter(sessao_id)
    assert sessao.ciclo == 3 and len(sessao.ciclos) == 3
    assert sessao.cenario is not None and sessao.cenario.habilidade_alvo == "equacao_linear"
    assert not sessao.com_ia and sessao.item_atual is None and not sessao.encerrada
    assert servico.janela_da_retencao(sessao_id) is None, "a janela da retenção só conta depois do projeto"
    with pytest.raises(OperacaoRecusada, match="já terminou"):
        servico.responder(sessao_id, "1", 5)
    with pytest.raises(OperacaoRecusada, match="todas as partes"):
        sessao.submeter_steam([True])

    erradas = {**_CERTAS, "economia_mensal": "99"}
    for respostas, justificativa, mensagem in [
        ({**_CERTAS, "metros_dentro_do_limite": " "}, "texto", "todas as partes"),
        ({**_CERTAS, "metros_dentro_do_limite": "1" * 41}, "texto", "passou de 40"),
        (_CERTAS, "  ", "Escreva a justificativa"),
        (_CERTAS, "x" * 2001, "passou de 2000"),
    ]:
        with pytest.raises(OperacaoRecusada, match=mensagem):
            servico.submeter_steam(sessao_id, respostas, justificativa)
    assert servico.medidas_steam(sessao_id, sessao) is None

    servico.submeter_steam(sessao_id, erradas, "A turma deve regar metade dos canteiros por dia.")
    fechada = servico.obter(sessao_id)  # nome novo: o mypy guardou o estreitamento de antes da submissão
    assert fechada.encerrada and fechada.steam == (True, True, True, False)
    assert servico.janela_da_retencao(sessao_id) is not None
    medidas = servico.medidas_steam(sessao_id, sessao)
    assert medidas == (Decimal("0.75"), Indisponivel("aguardando_rubrica"))
    with pytest.raises(OperacaoRecusada, match="não está aberto"):
        servico.submeter_steam(sessao_id, _CERTAS, "de novo")

    reaberta = _servico(tmp_path / "adia.db").obter(sessao_id)
    assert reaberta.encerrada and reaberta.steam == sessao.steam and reaberta.ciclos == sessao.ciclos
    with pytest.raises(SessaoInconsistente, match="projeto STEAM"):
        _servico(tmp_path / "adia.db", steam=None).obter(sessao_id)


def test_rubrica_avaliada_por_professor_entra_na_exportacao(tmp_path: Path) -> None:
    servico = _servico(tmp_path / "adia.db")
    sessao_id = _ate_o_projeto(servico)
    servico.submeter_steam(sessao_id, _CERTAS, "Justificativa do estudante.")
    [submissao] = servico.repositorio.submissoes_steam()
    assert submissao.avaliadores == () and submissao.justificativa == "Justificativa do estudante."

    with pytest.raises(SubmissaoInexistente):
        servico.avaliar(999, "PROF-01", _NIVEIS)
    with pytest.raises(OperacaoRecusada, match="todos os critérios"):
        servico.avaliar(submissao.id, "PROF-01", {**_NIVEIS, "hipoteses_declaradas": "otimo"})
    with pytest.raises(OperacaoRecusada, match="todos os critérios"):
        servico.avaliar(submissao.id, "PROF-01", {"adequacao_do_modelo": "exemplar"})

    avaliacao = servico.avaliar(submissao.id, "PROF-01", _NIVEIS)
    assert sum(p for _, _, p in avaliacao.pontuacoes) == 6 and avaliacao.pontos_maximos == 12
    with pytest.raises(OperacaoRecusada, match="já avaliou"):
        servico.avaliar(submissao.id, "PROF-01", _NIVEIS)
    servico.avaliar(submissao.id, "PROF-02", dict.fromkeys(_NIVEIS, "exemplar"))
    assert servico.repositorio.submissoes_steam()[0].avaliadores == ("PROF-01", "PROF-02")

    sessao = servico.obter(sessao_id)
    assert servico.medidas_steam(sessao_id, sessao) == (Decimal(1), Decimal("0.75"))
    assert "partes numéricas 1,00, rubrica 0,75" in gerar_painel(servico)

    pasta = exportar(servico, tmp_path / "saida").diretorio
    linhas = ler_metricas((pasta / f"metricas_{sessao_id}.csv").read_text(encoding="utf-8"))
    steam = {linha["metrica"]: linha for linha in linhas if linha["etapa"] == "projeto_steam"}
    assert steam["steam_partes"]["valor"] == "1.000000"
    assert steam["steam_rubrica"]["valor"].startswith("0.75")
    assert steam["steam_partes"]["ciclo"] == "3"


def test_exclusao_apaga_submissao_e_avaliacoes(tmp_path: Path) -> None:
    caminho = tmp_path / "adia.db"
    servico = _servico(caminho)
    sessao_id = _ate_o_projeto(servico)
    servico.submeter_steam(sessao_id, _CERTAS, "texto")
    submissao = servico.repositorio.submissoes_steam()[0]
    servico.avaliar(submissao.id, "PROF-01", _NIVEIS)
    with sqlite3.connect(caminho) as conexao, pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conexao.execute("DELETE FROM avaliacao_rubrica")
    participante = servico.repositorio.ler_sessao(sessao_id)
    assert participante is not None
    servico.repositorio.excluir_participante(participante[0].participante_id, "pedido")
    with sqlite3.connect(caminho) as conexao:
        assert conexao.execute("SELECT count(*) FROM submissao_steam").fetchone()[0] == 0
        assert conexao.execute("SELECT count(*) FROM avaliacao_rubrica").fetchone()[0] == 0


# --------------------------------------------------------------------------- API


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    shutil.copytree(_ITENS, tmp_path / "data" / "itens")
    shutil.copytree(_STEAM, tmp_path / "data" / "steam")
    return tmp_path


@pytest.fixture
def app(raiz: Path) -> FastAPI:
    return criar_app(raiz, _ClienteFora())


def test_api_do_estudante_e_do_professor(app: FastAPI, raiz: Path) -> None:
    cliente = TestClient(app, base_url=_LOCAL)
    servico: Servico = app.state.servico
    sessao_id = _ate_o_projeto(servico)

    estado = cliente.get(f"/api/sessoes/{sessao_id}").json()
    assert estado["etapa"] == "projeto_steam" and estado["item"] is None
    projeto = estado["steam"]
    assert [p["parte"] for p in projeto["partes"]] == list(_CERTAS)
    assert "gabarito" not in str(projeto) and "rubrica" not in str(projeto)

    recusa = cliente.post(f"/api/sessoes/{sessao_id}/steam", json={"partes": {}, "justificativa": "x"})
    assert recusa.status_code == 409
    final = cliente.post(f"/api/sessoes/{sessao_id}/steam", json={"partes": _CERTAS, "justificativa": "Meu argumento."})
    assert final.status_code == 200
    assert final.json()["steam"] is None and final.json()["retencao"] is not None

    rota = "/api/professor/submissoes"
    assert cliente.get(rota).status_code == 503
    chave = raiz / CHAVE_DO_PROFESSOR
    chave.parent.mkdir(parents=True)
    chave.write_text("segredo\n", encoding="utf-8")
    assert cliente.get(rota).status_code == 401
    assert cliente.get(rota, headers={"X-Chave-Professor": "errada"}).status_code == 401

    cabecalho = {"X-Chave-Professor": "segredo"}
    [resumo] = cliente.get(rota, headers=cabecalho).json()
    assert set(resumo) == {"id", "cenario", "criado_em", "avaliadores"}, "cega para participante e condição"
    detalhe = cliente.get(f"{rota}/{resumo['id']}", headers=cabecalho).json()
    assert detalhe["justificativa"] == "Meu argumento."
    assert [c["criterio"] for c in detalhe["rubrica"]["criterios"]] == list(_NIVEIS)
    assert cliente.get(f"{rota}/999", headers=cabecalho).status_code == 404

    avaliacao = {"avaliador": "PROF-07", "niveis": _NIVEIS}
    assert cliente.post(f"{rota}/{resumo['id']}/avaliacoes", json=avaliacao).status_code == 401
    invalida = {**avaliacao, "avaliador": "Ana"}
    assert cliente.post(f"{rota}/{resumo['id']}/avaliacoes", json=invalida, headers=cabecalho).status_code == 422
    nota = cliente.post(f"{rota}/{resumo['id']}/avaliacoes", json=avaliacao, headers=cabecalho)
    assert nota.json() == {"pontos": 6, "pontos_maximos": 12}
    assert cliente.post(f"{rota}/{resumo['id']}/avaliacoes", json=avaliacao, headers=cabecalho).status_code == 409
    assert cliente.get(rota, headers=cabecalho).json()[0]["avaliadores"] == ["PROF-07"]
    assert Repositorio(raiz / BANCO_DE_DADOS).notas_da_rubrica(sessao_id) == [(6, 12)]
