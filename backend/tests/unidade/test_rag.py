"""RAG das dicas: segmentação, índice versionado, busca, filtro de vazamento e proveniência (DO-11, DO-47)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from adia import caminhos, cli
from adia.guarda.veredito import revela_resposta
from adia.ia.cliente_ollama import ClienteOllama, FalhaDeGeracao, RespostaDoModelo
from adia.ia.rag.indice import MAXIMO, MINIMO, SOBREPOSICAO, abrir, arquivos_do_corpus, construir, segmentar
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.orquestracao.servico import Servico
from adia.persistencia.repositorio import Repositorio
from adia.tipos import Etapa, Nivel

_RAIZ = Path(__file__).resolve().parents[3]
_ITENS = _RAIZ / "data" / "itens"
_CORPUS = _RAIZ / "data" / "corpus"
_EIXOS = ("balança", "parênteses", "conferir", "segredo")


class _ClienteDuble(ClienteOllama):
    """Embeddings por contagem de palavras-chave: o trecho mais próximo é previsível."""

    def __init__(self, falhar_embeddings: bool = False) -> None:
        super().__init__()
        self.falhar_embeddings = falhar_embeddings
        self.pedidos: list[str] = []

    def digest(self, modelo: str) -> str | None:
        return "sha256:abcdef0123456789"

    def embutir(self, textos: list[str], modelo: str = "bge-m3") -> list[list[float]]:
        if self.falhar_embeddings:
            raise FalhaDeGeracao("dublê sem embeddings")
        return [[float(t.lower().count(eixo)) + 0.01 for eixo in _EIXOS] for t in textos]

    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        self.pedidos.append(pedido)
        return RespostaDoModelo("Pense no que desfaz a soma.", 5, 1, "dublê")


def _corpus(pasta: Path, textos: dict[str, str]) -> tuple[Path, ...]:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, texto in textos.items():
        (pasta / nome).write_text(texto, encoding="utf-8")
    return arquivos_do_corpus(pasta)


# --------------------------------------------------------------------------- segmentação


def test_segmentos_respeitam_faixa_e_sobreposicao() -> None:
    texto = " ".join(f"Frase número {i} sobre equações e balanças em equilíbrio." for i in range(80))
    trechos = segmentar(texto)
    assert all(MINIMO <= len(t) <= MAXIMO for t in trechos[:-1])
    assert 0 < len(trechos[-1]) <= MAXIMO
    for anterior, seguinte in zip(trechos, trechos[1:], strict=False):
        cauda = anterior[-SOBREPOSICAO:]
        assert seguinte.split()[0] in cauda, "o trecho seguinte começa dentro dos 80 caracteres finais"
    assert trechos[-1].endswith("equilíbrio.")
    assert segmentar("   ") == []
    assert segmentar("Curto demais.") == ["Curto demais."]


def test_corpus_real_segmenta_e_nao_revela_resposta_de_item_nenhum() -> None:
    carga = carregar(arquivos_de_itens(_ITENS))
    assert isinstance(carga, CargaConcluida)
    trechos = [t for arquivo in arquivos_do_corpus(_CORPUS) for t in segmentar(arquivo.read_text(encoding="utf-8"))]
    assert len(trechos) >= 10
    vazamentos = [(i.id, t[:40]) for t in trechos for i in carga.itens if revela_resposta(t, i)]
    assert vazamentos == []


# --------------------------------------------------------------------------- índice


def test_indice_versionado_busca_e_recusa_corpus_alterado(tmp_path: Path) -> None:
    arquivos = _corpus(
        tmp_path / "corpus",
        {"a.md": "A balança fica em equilíbrio. " * 20, "b.md": "Os parênteses multiplicam tudo. " * 20},
    )
    destino = tmp_path / "indice" / "indice.db"
    indice = construir(arquivos, destino, _ClienteDuble())
    assert indice.versao.startswith("bge-m3@abcdef012345:")
    assert {t.arquivo for t in indice.trechos} == {"a.md", "b.md"}
    assert indice.consultar([0, 1, 0, 0], 1)[0].arquivo == "b.md"

    reaberto = abrir(destino, arquivos)
    assert reaberto is not None and reaberto.versao == indice.versao
    assert reaberto.trechos == indice.trechos
    assert (reaberto.vetores == indice.vetores).all()

    assert abrir(tmp_path / "nao-existe.db", arquivos) is None
    (tmp_path / "corpus" / "a.md").write_text("Texto novo.", encoding="utf-8")
    assert abrir(destino, arquivos_do_corpus(tmp_path / "corpus")) is None, "índice de outro corpus não vale"
    with pytest.raises(ValueError, match="corpus vazio"):
        construir((), destino, _ClienteDuble())


def test_embutir_confere_a_forma_da_resposta(monkeypatch: pytest.MonkeyPatch) -> None:
    respostas: list[dict[str, object]] = [
        {"embeddings": [[0.1, 0.2], [1, 0]]},
        {"embeddings": [[0.1]]},
        {"models": [{"name": "bge-m3:latest", "digest": "sha256:ff"}]},
    ]
    monkeypatch.setattr(ClienteOllama, "_transporte", lambda *_a: respostas.pop(0))
    cliente = ClienteOllama()
    assert cliente.embutir(["a", "b"]) == [[0.1, 0.2], [1.0, 0.0]]
    with pytest.raises(FalhaDeGeracao, match="api/embed"):
        cliente.embutir(["a", "b"])
    assert cliente.digest("bge-m3") == "sha256:ff"


# --------------------------------------------------------------------------- dicas


def _servico_com_rag(tmp_path: Path, cliente: _ClienteDuble, textos: dict[str, str]) -> tuple[Servico, str]:
    arquivos = _corpus(tmp_path / "corpus", textos)
    indice = construir(arquivos, tmp_path / "indice.db", _ClienteDuble())
    servico = Servico(_ITENS, cliente, Repositorio(tmp_path / "adia.db"), rag=indice)
    sessao_id, sessao = servico.iniciar(servico.repositorio.criar_participantes("turma", 1)[0])
    while sessao.etapa == Etapa.LINHA_DE_BASE:
        item = sessao.item_atual
        assert item is not None
        servico.responder(sessao_id, item.gabarito, 5)
    return servico, sessao_id


def test_dica_de_l2_leva_o_trecho_e_registra_a_proveniencia(tmp_path: Path) -> None:
    cliente = _ClienteDuble()
    servico, sessao_id = _servico_com_rag(tmp_path, cliente, {"a.md": "Desfaça a soma com a balança. " * 15})
    l1 = servico.dica(sessao_id, Nivel.L1)
    assert l1.trecho is None and "Trecho do material" not in cliente.pedidos[-1]
    l2 = servico.dica(sessao_id, Nivel.L2)
    assert l2.origem == "ia" and l2.trecho is not None and l2.trecho.endswith("#1")
    assert "Trecho do material da disciplina" in cliente.pedidos[-1] and "balança" in cliente.pedidos[-1]
    with sqlite3.connect(tmp_path / "adia.db") as conexao:
        gravados = [r[0] for r in conexao.execute("SELECT trecho_rag FROM evento WHERE tipo = 'dica' ORDER BY id")]
    assert gravados == [None, l2.trecho]


def test_trecho_que_revela_a_resposta_e_pulado(tmp_path: Path) -> None:
    cliente = _ClienteDuble()
    servico, sessao_id = _servico_com_rag(tmp_path, cliente, {"a.md": "texto neutro. " * 40})
    item = servico.obter(sessao_id).item_atual
    assert item is not None
    vaza = f"O segredo: a resposta é {item.gabarito}. " * 14
    servico, sessao_id = _servico_com_rag(
        tmp_path / "outro", cliente, {"a.md": vaza, "b.md": "A balança em equilíbrio. " * 20}
    )
    servico.dica(sessao_id, Nivel.L2)
    assert "O segredo" not in cliente.pedidos[-1] and "balança" in cliente.pedidos[-1]


def test_sem_embeddings_a_dica_segue_sem_trecho(tmp_path: Path) -> None:
    cliente = _ClienteDuble(falhar_embeddings=True)
    servico, sessao_id = _servico_com_rag(tmp_path, cliente, {"a.md": "A balança em equilíbrio. " * 20})
    dica = servico.dica(sessao_id, Nivel.L3)
    assert dica.origem == "ia" and dica.trecho is None
    assert "Trecho do material" not in cliente.pedidos[-1]


# --------------------------------------------------------------------------- CLI


def test_adia_indexar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    for marca in caminhos.MARCAS_DA_RAIZ:
        (tmp_path / marca).write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert cli.principal(["indexar"]) == cli.CODIGO_BANCO_INVALIDO
    assert "nada a indexar" in capsys.readouterr().out

    _corpus(tmp_path / caminhos.DIRETORIO_CORPUS, {"a.md": "A balança em equilíbrio. " * 20})
    monkeypatch.setattr(ClienteOllama, "embutir", _ClienteDuble.embutir)
    monkeypatch.setattr(ClienteOllama, "digest", _ClienteDuble.digest)
    monkeypatch.setattr(ClienteOllama, "falhar_embeddings", False, raising=False)
    assert cli.principal(["indexar"]) == cli.CODIGO_OK
    assert "trecho(s) de 1 arquivo(s)" in capsys.readouterr().out
    assert (tmp_path / caminhos.INDICE_RAG).is_file()

    monkeypatch.setattr(ClienteOllama, "falhar_embeddings", True, raising=False)
    assert cli.principal(["indexar"]) == cli.CODIGO_AMBIENTE_INVALIDO
    assert "ollama pull bge-m3" in capsys.readouterr().out


class _ClientePobre(_ClienteDuble):
    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        self.pedidos.append(pedido)
        return RespostaDoModelo("Isolar x.", 5, 1, "dublê")


def test_dica_gerada_fora_do_padrao_vira_a_pre_escrita(tmp_path: Path) -> None:
    servico, sessao_id = _servico_com_rag(tmp_path, _ClientePobre(), {"a.md": "A balança em equilíbrio. " * 20})
    item = servico.obter(sessao_id).item_atual
    assert item is not None
    dica = servico.dica(sessao_id, Nivel.L3)
    assert (dica.origem, dica.texto, dica.trecho) == ("pre-escrita", item.dicas[Nivel.L3], None)
    assert dica.motivo == "dica gerada fora do padrão do nível: curta"
