"""Filtro de qualidade da dica gerada (DO-51)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adia.guarda.qualidade import motivo_de_pobreza
from adia.ia.cliente_ollama import ClienteOllama, RespostaDoModelo
from adia.nucleo.itens.carregador import CargaConcluida, arquivos_de_itens, carregar
from adia.nucleo.itens.modelo import Item
from adia.orquestracao.amostra import Gravador, amostrar, gravar
from adia.orquestracao.servico import Servico
from adia.persistencia.repositorio import Repositorio
from adia.tipos import Nivel


@pytest.fixture(scope="module")
def itens() -> tuple[Item, ...]:
    carga = carregar(arquivos_de_itens(Path("data") / "itens"))
    assert isinstance(carga, CargaConcluida)
    return carga.itens


def _item(itens: tuple[Item, ...], enunciado_com: str) -> Item:
    return next(i for i in itens if enunciado_com in i.enunciado)


def test_toda_dica_pre_escrita_passa_no_filtro(itens: tuple[Item, ...]) -> None:
    """A dica de reserva não pode reprovar no critério que a convoca."""
    for item in itens:
        for nivel in (Nivel.L1, Nivel.L2, Nivel.L3):
            assert motivo_de_pobreza(item.dicas[nivel], item, nivel) is None, (item.id, nivel)


@pytest.mark.parametrize(
    ("nivel", "texto", "motivo"),
    [
        (Nivel.L3, "Isolar x.", "curta"),
        (Nivel.L1, "Tente lembrar o que a igualdade afirma sobre a incógnita.", "sem_pergunta"),
        (Nivel.L2, "A igualdade é uma balança: subtraia o termo constante dos dois lados.", "operacao_no_conceito"),
        (Nivel.L2, "Na balança, vamos dividir os dois lados pelo coeficiente da incógnita.", "operacao_no_conceito"),
        (Nivel.L2, "É uma balança, e para resolver você deve somar o mesmo aos dois lados.", "operacao_no_conceito"),
        (Nivel.L3, "Agora, resolva a equação 2x + 3 = 11 com calma e atenção.", "repete_o_enunciado"),
        (Nivel.L2, "A balança vale para 2x + 3 = 11 como para qualquer igualdade.", None),
        (Nivel.L3, "Junte os termos parecidos até chegar em algo como 2x = 8 do outro lado.", "escreve_conta"),
        (Nivel.L1, "O que a igualdade afirma sobre a incógnita, e o que precisa valer nos dois lados?", None),
        (Nivel.L2, "Soma e multiplicação se desfazem por operações inversas, sem quebrar a igualdade.", None),
        (Nivel.L3, "Subtraia o termo constante dos dois lados para manter a igualdade.", None),
        # Casos da revisão humana de 2026-11-03 (docs/relatorios/revisao-dicas-2026-11-03.csv).
        (Nivel.L1, "Você já resolvia equações onde a incógnita estava apenas em um lado, certo?", "pergunta_fechada"),
        (Nivel.L2, "A igualdade é uma balança, então precisamos adicionar 3 a ambos os lados.", "operacao_no_conceito"),
        (Nivel.L2, "Na balança, você adiciona o mesmo valor aos dois lados.", "operacao_no_conceito"),
        (Nivel.L3, "Primeiro, desfaça a soma que acompanha a incógnita. Some 3 dos dois lados.", "inverte_a_operacao"),
        (Nivel.L3, "Primeiro, desfaça a soma que acompanha a incógnita. Subtraia 3 dos dois lados.", None),
        (Nivel.L3, "Subtraia 2x dos dois lados.", None),
        # Revisão de 2026-11-04 (docs/relatorios/revisao-dicas-2026-11-04.csv).
        (Nivel.L2, "É uma balança: devemos subtrair o termo constante dos dois lados.", "operacao_no_conceito"),
        (Nivel.L3, "Comece somando 20 a ambos os lados da equação.", "numero_fora_do_enunciado"),
        # Rodada 2026-11-04b (docs/relatorios/revisao-dicas-2026-11-04b.csv).
        (Nivel.L2, "A ideia matemática da dica de referência está em desfazer as operações.", "cita_o_pedido"),
        (Nivel.L2, "Na ordem contrária, devemos desfazer a multiplicação primeiro.", "operacao_no_conceito"),
        (Nivel.L1, "Você já resolveu equações onde a incógnita está apenas em um lado?", "pergunta_fechada"),
        (Nivel.L1, "Antes de começar: você espera uma solução grande ou pequena?", None),
        (Nivel.L1, "Se você cobrisse os parênteses, que equação sobraria?", None),
        # Rodada 2026-11-04c (docs/relatorios/revisao-dicas-2026-11-04c.csv).
        (Nivel.L2, "A igualdade é uma balança. Resolver é encontrar o número que, colocado no lugar", "cortada"),
        (Nivel.L2, "Na ordem contrária: primeiro desfazemos a soma, depois a multiplicação.", "operacao_no_conceito"),
    ],
)
def test_motivos(itens: tuple[Item, ...], nivel: Nivel, texto: str, motivo: str | None) -> None:
    assert motivo_de_pobreza(texto, _item(itens, "2x + 3 = 11"), nivel) == motivo


class _Modelo(ClienteOllama):
    def gerar(self, sistema: str, pedido: str) -> RespostaDoModelo:
        texto = "O que você já sabe que ajuda neste problema?" if "metacognitivo" in sistema else "Isolar x."
        return RespostaDoModelo(texto, 5, 900, self.modelo)


class _Duble(Gravador, _Modelo):
    """Grava o texto cru do modelo dublê, como o ``Gravador`` faz com o Ollama."""


def test_amostra_guarda_o_texto_cru_e_tira_as_repetidas(tmp_path: Path) -> None:
    gravador = _Duble()
    servico = Servico(Path("data") / "itens", gravador, Repositorio(tmp_path / "adia.db"))
    linhas = amostrar(servico, gravador, por_nivel=2)
    praticados = sum(1 for i in servico.carga.itens if i.e_praticado)
    assert len(linhas) == 3 * praticados
    for linha in linhas:
        esperado = ("O que você já sabe que ajuda neste problema?", "passou")
        if linha["nivel"] != "L1":
            esperado = ("Isolar x.", "dica gerada fora do padrão do nível: curta")
        assert (linha["gerada_pelo_modelo"], linha["filtro"]) == esperado
        assert (linha["modelo"], linha["ms"]) == (gravador.modelo, "900")
    gravar(linhas, tmp_path / "amostra.csv")
    assert (tmp_path / "amostra.csv").read_text(encoding="utf-8-sig").startswith("n;item;nivel;")
