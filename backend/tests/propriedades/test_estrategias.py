"""Meta-testes de `estrategias.py`: o gerador produz o que promete, e nada fora disso.

Gerador não testado é pior que código não testado, porque ele decide o que as outras 37
propriedades chegam a ver. Dois modos de falha justificam este arquivo, e nenhum dos dois
aparece numa propriedade vermelha — os dois aparecem como propriedade **verde**:

1. **Buraco silencioso no vocabulário.** Um gerador de `Etapa` que nunca sorteasse `posteste`
   deixaria a Propriedade 21 passar sem nunca ter olhado o pós-teste. O teste de cobertura
   abaixo pede à biblioteca um exemplo de **cada** membro de cada enumeração; a ausência
   aparece como `NoSuchExample`, com o nome do membro que não é alcançável.
2. **Item que a carga recusaria.** `serializar_canonico` não revalida o banco. Um gerador que
   produzisse item inválido faria as Propriedades 29 e 30 reprovarem por item malformado em
   vez de por defeito de serialização, e o contraexemplo apontaria para o lugar errado. Aqui o
   item gerado atravessa `serializar_canonico` + `carregar` de verdade, com arquivo em disco.

O terceiro teste é sobre legibilidade, e é tão operacional quanto os outros dois: o motivo de
existirem geradores nomeados em vez de `st.builds` solto é que o contraexemplo **encolhido**
precisa ser compreensível. `test_o_contraexemplo_encolhido_*` fixa o item mínimo em
asserção, de modo que uma mudança de gerador que degrade o encolhimento falhe aqui em vez de
aparecer, meses depois, como contraexemplo que ninguém consegue ler.

**Validates: Requirements 3.4, 3.5, 29.1, 29.2, 29.3**
"""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from estrategias import (
    CARACTERES_DE_IDENTIFICADOR,
    FRAGMENTOS_ADVERSARIOS,
    FRONTEIRAS,
    MOTIVOS_DE_INDISPONIBILIDADE,
    QUATRO_CASAS,
    PerfilDeGabarito,
    condicoes,
    conjuntos_de_termos_essenciais,
    dicas_pre_escritas,
    dificuldades,
    enunciados,
    etapas,
    etapas_permitidas,
    identificadores,
    indisponiveis,
    itens,
    itens_carregaveis,
    medidas,
    niveis,
    perfis_de_gabarito,
    proporcoes,
    tamanhos_max_resposta,
    textos_adversarios,
    tipos_de_gabarito,
    tolerancias,
    variacoes_de_gabarito,
)
from hypothesis import Phase, find, given, settings
from hypothesis import strategies as st

from adia.nucleo.itens.carregador import (
    PADRAO_DE_IDENTIFICADOR,
    SUFIXO_DE_ARQUIVO,
    CargaConcluida,
    ResultadoDeCarga,
    carregar,
    serializar_canonico,
)
from adia.nucleo.itens.erros import ErroDeAssociacaoAusente
from adia.nucleo.itens.modelo import DIFICULDADE_MAXIMA, DIFICULDADE_MINIMA, Item, TipoGabarito
from adia.tipos import Condicao, Etapa, Indisponivel, Medida, Nivel, e_disponivel

# Meta-testes, não as propriedades de §5: o orçamento é o mínimo que dá cobertura, porque
# estes testes rodam no portão local junto com os outros. `deadline=None` só onde há disco —
# o prazo por exemplo da biblioteca mediria latência de E/S do Windows, não corretude.
EXEMPLOS = 50


def _carregar_sozinho(item: Item) -> ResultadoDeCarga:
    """Serializa o item num arquivo próprio e o carrega, sem nenhum item par.

    Bytes, e não texto: `write_text` em Windows traduziria `LF` em `CRLF` e o arquivo deixaria
    de ser o que `serializar_canonico` produziu (R3.3). `tempfile` em vez da fixture `tmp_path`
    porque fixture de escopo de função sob `@given` é reprovada pela própria biblioteca — o
    diretório é descartado por exemplo, que é o que se quer de todo modo.
    """
    with tempfile.TemporaryDirectory() as raiz:
        caminho = Path(raiz) / f"gerado{SUFIXO_DE_ARQUIVO}"
        caminho.write_bytes(serializar_canonico([item], []).encode("utf-8"))
        return carregar([caminho])


# --------------------------------------------------------------------------- #
# Cada gerador produz o tipo que declara
# --------------------------------------------------------------------------- #


@given(niveis(), etapas(), condicoes(), tipos_de_gabarito())
def test_os_geradores_de_enumeracao_produzem_o_tipo_declarado(
    nivel: Nivel, etapa: Etapa, condicao: Condicao, tipo: TipoGabarito
) -> None:
    """Enumeração gerada é membro da enumeração, não o texto nem o inteiro subjacente."""
    assert isinstance(nivel, Nivel)
    assert isinstance(etapa, Etapa)
    assert isinstance(condicao, Condicao)
    assert isinstance(tipo, TipoGabarito)


@given(medidas())
def test_a_medida_gerada_e_decimal_exato_ou_indisponivel_com_motivo(medida: Medida) -> None:
    """`Medida` é união de dois tipos distintos, e nunca zero no lugar de ausência (R11.7).

    `e_disponivel` em vez de `if medida:` de propósito: `Indisponivel.__bool__` levanta, e é
    essa recusa que impede `medida or Decimal(0)` de transformar ausência em zero.
    """
    if e_disponivel(medida):
        assert isinstance(medida, Decimal)
        assert Decimal("0") <= medida <= Decimal("1")
    else:
        assert isinstance(medida, Indisponivel)
        assert medida.motivo in MOTIVOS_DE_INDISPONIBILIDADE


@given(proporcoes())
def test_a_proporcao_gerada_tem_as_quatro_casas_da_comparacao_com_limiar(valor: Decimal) -> None:
    """Quatro casas, as de R9.12, para que o valor já esteja na forma em que `decidir` compara.

    `quantize` em vez de inspeção do expoente: o que importa não é quantos dígitos foram
    escritos, e sim que arredondar a quatro casas **não muda o valor** — que é a condição para
    a comparação com limiar de `decidir` não depender de arredondamento.
    """
    assert Decimal("0") <= valor <= Decimal("1")
    assert valor == valor.quantize(QUATRO_CASAS)


@given(dificuldades(), tamanhos_max_resposta(), tolerancias())
def test_os_escalares_de_item_ficam_nas_faixas_da_gramatica(
    dificuldade: int, tamanho: int, tolerancia: Decimal
) -> None:
    """Dificuldade de 1 a 5 (R2.1), tamanho de 1 em diante, tolerância não negativa (R2.8)."""
    assert DIFICULDADE_MINIMA <= dificuldade <= DIFICULDADE_MAXIMA
    assert tamanho >= 1
    assert tolerancia >= 0
    assert tolerancia.is_finite()


@given(identificadores())
def test_o_identificador_gerado_tem_a_forma_que_a_carga_exige(identificador: str) -> None:
    """ASCII, de 1 a 64 caracteres, começando por letra ou dígito (R3.6)."""
    assert PADRAO_DE_IDENTIFICADOR.match(identificador) is not None
    assert set(identificador) <= set(CARACTERES_DE_IDENTIFICADOR)


@given(dicas_pre_escritas())
def test_o_catalogo_gerado_tem_exatamente_os_quatro_niveis_nao_vazios(
    dicas: Mapping[Nivel, str],
) -> None:
    """Exatamente uma dica não vazia por nível de L1 a L4 (R2.1)."""
    assert set(dicas) == set(Nivel)
    assert all(dicas[nivel].strip() for nivel in Nivel)


@given(variacoes_de_gabarito(), conjuntos_de_termos_essenciais())
def test_as_colecoes_geradas_saem_na_forma_canonica(
    variacoes: tuple[str, ...], essenciais: tuple[tuple[str, ...], ...]
) -> None:
    """Coleção é conjunto escrito como lista: ordenada, sem repetição, nenhum nível vazio.

    Canônica na origem porque a leitura devolve `tuple(sorted(...))`. Gerar fora de ordem
    produziria item que vai e volta diferente de si mesmo, e R3.4 falharia sem defeito.
    """
    assert list(variacoes) == sorted(set(variacoes))
    assert list(essenciais) == sorted(set(essenciais))
    assert essenciais != ()
    for conjunto in essenciais:
        assert conjunto != ()
        assert list(conjunto) == sorted(set(conjunto))


# --------------------------------------------------------------------------- #
# Cobertura do vocabulário: o buraco silencioso
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("nivel", list(Nivel))
def test_o_gerador_de_nivel_alcanca_cada_nivel(nivel: Nivel) -> None:
    """Um nível inalcançável deixaria a saturação de R9.6 e R9.7 sem exemplo."""
    assert find(niveis(), lambda sorteado: sorteado is nivel) is nivel


@pytest.mark.parametrize("etapa", list(Etapa))
def test_o_gerador_de_etapa_alcanca_cada_etapa(etapa: Etapa) -> None:
    """`posteste` é o membro em risco: esquecê-lo deixaria a Propriedade 21 cega."""
    assert find(etapas(), lambda sorteada: sorteada is etapa) is etapa


@pytest.mark.parametrize("etapa", list(Etapa))
def test_o_conjunto_de_etapas_permitidas_alcanca_cada_etapa(etapa: Etapa) -> None:
    """Cada etapa aparece em algum conjunto gerado, e nenhum conjunto é vazio (R2.4)."""
    conjunto = find(etapas_permitidas(), lambda sorteado: etapa in sorteado)
    assert etapa in conjunto


@pytest.mark.parametrize("condicao", list(Condicao))
def test_o_gerador_de_condicao_alcanca_cada_condicao(condicao: Condicao) -> None:
    """As três condições experimentais de R14.1 a R14.4, nenhuma a menos."""
    assert find(condicoes(), lambda sorteada: sorteada is condicao) is condicao


@pytest.mark.parametrize("tipo", list(TipoGabarito))
def test_o_gerador_de_item_alcanca_cada_tipo_de_gabarito(tipo: TipoGabarito) -> None:
    """Os três tipos saem do gerador livre, não só do gerador parametrizado por tipo.

    Só a fase de geração: aqui a pergunta é de **existência**, e minimizar um item de dezesseis
    campos para responder "existe" custa segundos no portão sem acrescentar informação. A
    legibilidade do encolhimento é afirmada em `test_o_contraexemplo_encolhido_do_item_e_legivel`,
    que é onde ela importa.
    """
    sorteado = find(
        itens(),
        lambda item: item.tipo_gabarito is tipo,
        settings=settings(max_examples=500, phases=(Phase.generate,), deadline=None),
    )

    assert sorteado.tipo_gabarito is tipo


@pytest.mark.parametrize("fronteira", list(FRONTEIRAS))
def test_as_proporcoes_alcancam_cada_fronteira_declarada(fronteira: Decimal) -> None:
    """Igualdade exata no limiar é o caso em que `≥` trocado por `>` muda a decisão.

    Amostragem uniforme em quatro casas sorteia `0,2500` uma vez em dez mil; sem o reforço, o
    caso de R9.12 seria inalcançável na prática.
    """
    assert find(proporcoes(), lambda valor: valor == fronteira) == fronteira


@pytest.mark.parametrize("fragmento", list(FRAGMENTOS_ADVERSARIOS))
def test_o_texto_adversario_alcanca_cada_uma_das_quinze_classes(fragmento: str) -> None:
    """As quinze classes que quebram a escrita de TOML são a entrada que P29 e P30 precisam."""
    assert fragmento in find(textos_adversarios(), lambda texto: fragmento in texto)


def test_a_medida_alcanca_os_dois_lados_da_uniao() -> None:
    """Os dois lados, porque um gerador que só produzisse número deixaria P13 sem exemplo."""
    assert isinstance(find(medidas(), e_disponivel), Decimal)
    assert isinstance(find(medidas(), lambda medida: not e_disponivel(medida)), Indisponivel)


@given(medidas(indisponibilidade=0.0))
def test_a_proporcao_zero_de_indisponibilidade_produz_so_numero(medida: Medida) -> None:
    """O peso é parâmetro de verdade: em zero, a indisponibilidade desaparece."""
    assert e_disponivel(medida)


@given(medidas(indisponibilidade=1.0))
def test_a_proporcao_total_de_indisponibilidade_produz_so_ausencia(medida: Medida) -> None:
    """E em um, só ausência — o que dá a P13 o caso em que toda entrada está indisponível."""
    assert not e_disponivel(medida)


# --------------------------------------------------------------------------- #
# O item gerado é um item que a carga aceita
# --------------------------------------------------------------------------- #


@given(itens())
def test_o_item_gerado_honra_o_acoplamento_entre_tipo_e_perfil(item: Item) -> None:
    """Tolerância só e sempre em numérico; termos essenciais só e sempre em textual.

    São as duas exigências que `_ler_tolerancia` e `_ler_termos_essenciais` impõem (R2.8,
    R2.11), e a gramática normativa acrescenta que a tolerância é **proibida** fora de
    numérico. Sinônimo de unidade sem `unidade` declarada é a terceira recusa.
    """
    assert (item.tolerancia is not None) == (item.tipo_gabarito is TipoGabarito.NUMERICO)
    assert (item.termos_essenciais != ()) == (item.tipo_gabarito is TipoGabarito.TEXTUAL)
    if item.sinonimos_unidade:
        assert item.unidade is not None
    assert item.etapas_permitidas != frozenset()
    assert item.enunciado.strip()
    assert item.gabarito.strip()


@given(itens_carregaveis())
@settings(max_examples=EXEMPLOS, deadline=None)
def test_o_item_carregavel_sobrevive_a_serializacao_e_a_carga(item: Item) -> None:
    """O item gerado, escrito sozinho em arquivo, é aceito por `carregar` e volta igual.

    É a pré-condição das Propriedades 29 e 30, afirmada aqui para que elas falhem por defeito
    de serialização e nunca por item malformado. A comparação é estrutural: `Item` é
    `dataclass` congelada e a igualdade compara campo a campo, inclusive a tolerância em
    `Decimal` e o catálogo de dicas.
    """
    resultado = _carregar_sozinho(item)

    assert isinstance(resultado, CargaConcluida), resultado
    assert resultado.itens == (item,)


@given(itens(conjunto_de_etapas=st.just(frozenset({Etapa.PRATICA_ASSISTIDA}))))
@settings(max_examples=EXEMPLOS, deadline=None)
def test_o_item_praticado_sozinho_e_recusado_por_associacao_ausente(item: Item) -> None:
    """Por que existem dois geradores de item, afirmado em vez de apenas documentado.

    Item praticado exige equivalente isomorfo e item de transferência da mesma habilidade
    (R2.2, R2.6). Isso é invariante do **banco**: o `Item` em memória é válido, e é a carga que
    recusa. `itens` pode produzi-lo — é o gerador certo para quem monta banco —, e é
    exatamente por isso que as Propriedades 29 e 30 usam `itens_carregaveis`.
    """
    resultado = _carregar_sozinho(item)

    assert isinstance(resultado, ErroDeAssociacaoAusente), resultado


@given(perfis_de_gabarito(tipo=TipoGabarito.TEXTUAL, com_unidade=False))
def test_o_perfil_parametrizado_respeita_o_tipo_e_a_unidade_pedidos(perfil: PerfilDeGabarito) -> None:
    """Os parâmetros do perfil servem às propriedades que precisam de um tipo fixo."""
    assert perfil.tipo_gabarito is TipoGabarito.TEXTUAL
    assert perfil.tolerancia is None
    assert perfil.unidade is None
    assert perfil.sinonimos_unidade == ()
    assert perfil.termos_essenciais != ()


@given(etapas_permitidas(excluir=(Etapa.PRATICA_ASSISTIDA,)))
def test_a_exclusao_de_etapa_e_respeitada(conjunto: frozenset[Etapa]) -> None:
    """A restrição de `itens_carregaveis` é uma só, e é esta."""
    assert Etapa.PRATICA_ASSISTIDA not in conjunto
    assert conjunto != frozenset()


@given(indisponiveis())
def test_a_indisponibilidade_gerada_tem_motivo(ausencia: Indisponivel) -> None:
    """`Indisponivel` recusa motivo vazio, porque §7.8 exige o motivo na tela (R11.7)."""
    assert ausencia.motivo.strip()


# --------------------------------------------------------------------------- #
# Legibilidade do contraexemplo encolhido
# --------------------------------------------------------------------------- #


def test_o_contraexemplo_encolhido_do_item_e_legivel() -> None:
    """O item mínimo é compreensível à primeira leitura, e isso é requisito, não estilo.

    É o motivo declarado de o módulo expor geradores nomeados em vez de `st.builds` solto
    (§6.3). Os valores abaixo são o que a biblioteca devolve hoje ao minimizar
    `itens_carregaveis`; um gerador que degrade o encolhimento — identificador longo,
    enunciado com fragmento adversário, coleções preenchidas sem necessidade — falha aqui, em
    vez de aparecer meses depois como contraexemplo que ninguém consegue ler.
    """
    minimo = find(itens_carregaveis(), lambda _: True)

    assert len(minimo.id) == 1
    assert len(minimo.habilidade_alvo) == 1
    assert minimo.dificuldade == DIFICULDADE_MINIMA
    assert minimo.tamanho_max_resposta == 1
    assert minimo.tipo_gabarito is TipoGabarito.NUMERICO
    assert minimo.tolerancia == Decimal("0")
    assert minimo.unidade is None
    assert minimo.sinonimos_unidade == ()
    assert minimo.variacoes_gabarito == ()
    assert minimo.termos_essenciais == ()
    assert minimo.incognita is None
    assert len(minimo.etapas_permitidas) == 1
    assert "\n" not in minimo.enunciado
    assert len(set(minimo.dicas.values())) == 1


def test_o_contraexemplo_encolhido_mantem_o_enunciado_em_pt_br() -> None:
    """O enunciado mínimo é o caso semente de `2x + 3 = 11`, com acentuação e sem adversário.

    Encolher para o lado limpo é a ordem certa de diagnóstico: falha com texto adversário é
    sobre escape; falha com texto limpo é sobre outra coisa, e distinguir as duas é o primeiro
    passo.
    """
    minimo = find(enunciados(), lambda _: True)

    assert "equação" in minimo
    assert not any(fragmento in minimo for fragmento in FRAGMENTOS_ADVERSARIOS)
