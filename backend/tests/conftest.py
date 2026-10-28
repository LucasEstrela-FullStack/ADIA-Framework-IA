"""Compartilhado da suíte do backend: proibição de inferência, relógio, semente e perfil de propriedades.

Três coisas vivem aqui, conforme a árvore de §2.3 do design, e as três existem
pela mesma razão: o determinismo do protótipo precisa ser **verificável**, não
pretendido.

A primeira é a fixture `ollama_proibido`, camada 3 das três que verificam a
fronteira determinística de D1 (design §6.4). As outras duas camadas — o
contrato de import em `backend/.importlinter` e o teste de tipo negativo em
`backend/tests/conjuntos/tipos_fronteira.py` — são **estáticas**: elas leem
código. Esta é a única que observa **execução**, e por isso é a única que pega
função injetada no núcleo, `importlib.import_module` por nome, dependência
resolvida pelo FastAPI e `import` dentro do corpo de uma função. Nenhuma das
três pega a travessia que não toca a rede (saída de modelo persistida numa
execução anterior e lida depois); essa fica para a Propriedade 8.

A inversão de padrão é o ponto da fixture, não um detalhe de implementação: ela
é `autouse`, logo a proibição é o **padrão** da suíte inteira, e a permissão
exige `@pytest.mark.ollama` escrito no teste. O contrário — proibir só onde
alguém lembrou de pedir — deixaria a garantia depender de disciplina. É a
postura de D3: em dúvida, falhar fechado. Sem isso, a Propriedade 21 ("nenhuma
chamada de inferência nas etapas sem IA") não é verificável (R30.1, R4.5), e o
limite de tráfego ao laço local de R24.8 fica sem contraparte executável.

As outras duas são o relógio e a semente injetados. `adia.nucleo` e
`adia.guarda` são puros (design §3.0): não leem relógio nem geram
aleatoriedade implicitamente, recebem `agora: datetime` e `semente: int` como
argumento — veja `GestorDeSessao.criar` em §3.3. As fixtures abaixo são a fonte
desses valores nos testes, e são deliberadamente sem dependência de domínio:
`datetime`, `int` e `random.Random`, nada de `adia.tipos`, que é da tarefa 3.1.

## Por que a substituição do transporte é condicional

A fixture troca `ClienteOllama._transporte` por um dublê, mas o módulo
`adia.ia.cliente_ollama` só nasce na tarefa 13.1, na Fase 4. Em vez de criar
aqui um esboço do módulo — código de produção cuja forma pertence a outra
tarefa, e cujo nome a tarefa 1.6 também referencia —, a troca é condicionada à
**existência** do módulo. A fragilidade óbvia dessa escolha seria uma falha de
importação silenciosa desarmando a camada sem ninguém notar. Três travas
fecham esse buraco:

1. a presença é apurada com `importlib.util.find_spec`, **nunca** com
   `try/except ImportError` em volta do import: módulo que existe e falha ao
   importar propaga o erro, em vez de ser tratado como ausente;
2. a troca usa `raising=True`, então renomear o transporte na tarefa 13.1
   quebra a suíte inteira de uma vez, em vez de passar calada;
3. `test_fronteira_de_execucao.py` afirma a invariante dos dois estados — sem o
   módulo, o import tem de falhar de fato; com o módulo, o dublê tem de morder.

Até a Fase 4, portanto, quem sustenta a camada é inteiramente a interceptação
de soquete, que é o que fecha o buraco que o dublê de transporte deixa aberto:
trocar o transporte só pega quem passa pelo cliente oficial, enquanto um
`urllib.request.urlopen` escrito às pressas num caminho de erro, um `requests`
trazido por dependência, um `httpx.AsyncClient` novo ou um soquete cru
passariam incólumes. Todos eles terminam em um dos quatro pontos abaixo. Por
isso o filtro é pela **porta de destino**, e não por biblioteca nem por
endereço: filtrar por endereço deixaria passar `localhost`, `::1` e o IP da
interface local.

## Por que o perfil do Hypothesis mora aqui

A quarta coisa deste arquivo entra por imposição de ferramenta, e não por
afinidade com as três primeiras: o piso de **100 exemplos** que §5.0 exige de
cada uma das 37 propriedades. Ele é declarado uma vez, como perfil, em vez de
repetido em 37 decoradores, por uma razão de leitura: o número é regra da
especificação, não escolha de arquivo, e repeti-lo em cada propriedade apagaria
a diferença entre "o piso de §5.0" e "uma decisão tomada aqui". Com o perfil, o
único `@settings` que aparece num arquivo de propriedade é o **desvio** daquela
propriedade — que é exatamente a informação que o leitor precisa ver.

O lugar natural seria `backend/tests/propriedades/conftest.py`, ao lado dos
arquivos que o usam. Não é possível, e vale registrar o porquê para que
ninguém tente de novo: o portão roda `mypy --strict` sobre `backend/tests`, não
há `__init__.py` em nenhum diretório de teste, e dois arquivos chamados
`conftest.py` colapsam no mesmo nome de módulo — `Duplicate module named
"conftest"`, com a checagem **abortada**, não apenas um erro a mais. As duas
saídas que o próprio mypy sugere são piores que o sintoma: `__init__.py` nos
diretórios de teste transformaria `propriedades/` em pacote e quebraria o
`from estrategias import ...` dos arquivos de propriedade, que depende de o
pytest inserir o diretório em `sys.path`; e `--explicit-package-bases` quebraria
o mesmo import pelo outro lado, renomeando o módulo para
`tests.propriedades.estrategias`.

Perfil **carregado** no escopo do processo, o que alcança toda a suíte. Isso é
inócuo fora de `propriedades/`: só os arquivos daquele diretório usam a
biblioteca. E os meta-testes de `test_estrategias.py`, que rodam com 50
exemplos de propósito, continuam valendo — eles declaram o próprio
`max_examples`, e valor explícito no teste prevalece sobre o perfil.

A composição é o que sustenta a convenção, e ela é verificada em
`propriedades/test_perfil_de_propriedades.py`: um `settings(...)` criado depois
do carregamento herda do perfil tudo o que não declara, de modo que
`@settings(deadline=None)` numa propriedade que toca disco mantém os 100
exemplos. Os dois desvios que §5.0 prevê — 500 exemplos em P22, P25, P26 e P28;
`deadline=None` em P16, P17, P31 e P35 — ficam, portanto, como `@settings` no
teste, e não como perfis: a biblioteca mantém **um** perfil carregado por
processo, e perfil por propriedade exigiria trocá-lo no meio da execução.
"""

from __future__ import annotations

import asyncio
import importlib.util
import random
import socket
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any, Final, NoReturn

import pytest
from hypothesis import settings

# --------------------------------------------------------------------------- #
# Perfil dos testes de propriedade (design §5.0, §6.2)
# --------------------------------------------------------------------------- #

EXEMPLOS_MINIMOS: Final = 100
"""Piso de exemplos por propriedade, de §5.0. Declarado, e não herdado do padrão da
biblioteca, porque é exigência da especificação: padrão que muda numa atualização de
versão rebaixaria as 37 propriedades sem que nada no repositório mudasse."""

PERFIL_DE_PROPRIEDADES: Final = "propriedades"
"""Nome do perfil. Único no processo: desvio por propriedade é `@settings` no teste."""

settings.register_profile(PERFIL_DE_PROPRIEDADES, settings(max_examples=EXEMPLOS_MINIMOS))
settings.load_profile(PERFIL_DE_PROPRIEDADES)


# --------------------------------------------------------------------------- #
# Camada 3 — proibição de chamada ao serviço de inferência local
# --------------------------------------------------------------------------- #

PORTA_INFERENCIA: Final = 11434
"""Porta do serviço de inferência local, de `ClienteOllama.BASE` (design §3.12)."""

MODULO_DO_CLIENTE: Final = "adia.ia.cliente_ollama"
"""Módulo do cliente oficial. Criado na tarefa 13.1; ausente até a Fase 4."""

ATRIBUTO_DO_TRANSPORTE: Final = "ClienteOllama._transporte"
"""Costura injetável que a fixture substitui pelo dublê (design §3.12, §6.4)."""

_COMO_LIBERAR: Final = (
    "A proibição é o padrão da suíte: as etapas sem IA concluem sem emitir nenhuma chamada "
    "de inferência (R30.1, R4.5) e o tráfego fica restrito ao laço local (R24.8). "
    "Se a chamada for intencional, marque o teste com @pytest.mark.ollama."
)


class ChamadaDeInferenciaProibida(RuntimeError):
    """Emitida quando um teste sem IA tenta alcançar o serviço de inferência.

    Herda de `RuntimeError`, e **não** de `OSError`, de propósito: código que
    trata falha de rede com `except OSError` — a sondagem de `adia doutor` é o
    exemplo vivo no repositório — não pode engolir esta exceção e transformar a
    travessia detectada em "serviço indisponível".
    """


def _proibir(caminho: str, destino: str) -> NoReturn:
    """Levanta a proibição dizendo por onde a chamada escapou e para onde ia.

    O par caminho/destino não é enfeite: mensagem de falha que não diz por qual
    das cinco costuras a chamada passou obriga quem diagnostica a reconstruir o
    rastro à mão.
    """
    raise ChamadaDeInferenciaProibida(
        f"chamada de inferência bloqueada. Caminho: {caminho}. Destino: {destino}. {_COMO_LIBERAR}"
    )


def _porta_de(valor: object) -> int | None:
    """Porta de destino como inteiro, ou `None` quando o valor não descreve porta.

    `asyncio.open_connection("127.0.0.1", "11434")` é chamada válida, com a
    porta em texto; comparar sem normalizar deixaria essa passar.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, bytes):
        valor = valor.decode("ascii", "ignore")
    if isinstance(valor, str) and valor.isdigit():
        return int(valor)
    return None


def _e_porta_de_inferencia(endereco: object) -> bool:
    """Verdadeiro para endereço de soquete cuja porta é a da inferência.

    Cobre a 2-tupla de IPv4 e a 4-tupla de IPv6 — em ambas a porta é o segundo
    elemento — e ignora o que não for endereço de rede, como o caminho de um
    soquete de domínio Unix.
    """
    if not isinstance(endereco, tuple) or len(endereco) < 2:
        return False
    return _porta_de(endereco[1]) == PORTA_INFERENCIA


def _transporte_proibido(*_a: object, **_k: object) -> NoReturn:
    """Dublê do transporte HTTP do `ClienteOllama`."""
    _proibir("transporte HTTP do ClienteOllama", f"{MODULO_DO_CLIENTE}.{ATRIBUTO_DO_TRANSPORTE}")


def cliente_oficial_existe() -> bool:
    """Se `adia.ia.cliente_ollama` já é importável.

    `find_spec` apura presença sem executar o módulo e sem mascarar erro de
    importação: módulo que existe e explode ao importar propaga a exceção aqui,
    em vez de ser silenciosamente tratado como ausente.
    """
    return importlib.util.find_spec(MODULO_DO_CLIENTE) is not None


def _substituir_transporte_do_cliente(monkeypatch: pytest.MonkeyPatch) -> bool:
    """Troca o transporte do cliente oficial pelo dublê. Devolve se a troca ocorreu."""
    if not cliente_oficial_existe():
        return False
    monkeypatch.setattr(f"{MODULO_DO_CLIENTE}.{ATRIBUTO_DO_TRANSPORTE}", _transporte_proibido, raising=True)
    return True


def _interceptar_soquetes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fecha os quatro pontos por onde qualquer cliente HTTP termina na rede.

    Lacuna conhecida e deliberadamente fora do escopo dos quatro pontos que o
    design nomeia: `loop.sock_connect` chamado diretamente. No Windows o laço
    *proactor* o atende por `ConnectEx`, sem passar por `socket.connect`. O
    caminho de alto nível (`loop.create_connection`, que é o que `anyio`,
    `httpx` e `aiohttp` usam) está coberto abaixo.
    """
    connect_original = socket.socket.connect
    connect_ex_original = socket.socket.connect_ex
    create_connection_original = socket.create_connection
    create_connection_async_original = asyncio.base_events.BaseEventLoop.create_connection

    def _connect(self: socket.socket, endereco: Any) -> None:
        if _e_porta_de_inferencia(endereco):
            _proibir("soquete síncrono (socket.connect)", repr(endereco))
        connect_original(self, endereco)

    def _connect_ex(self: socket.socket, endereco: Any) -> int:
        if _e_porta_de_inferencia(endereco):
            _proibir("sondagem de soquete (socket.connect_ex)", repr(endereco))
        return connect_ex_original(self, endereco)

    def _create_connection(endereco: Any, *a: Any, **k: Any) -> socket.socket:
        if _e_porta_de_inferencia(endereco):
            _proibir("socket.create_connection", repr(endereco))
        return create_connection_original(endereco, *a, **k)

    async def _create_connection_async(self: Any, *a: Any, **k: Any) -> Any:
        porta = k["port"] if "port" in k else (a[2] if len(a) > 2 else None)
        if _porta_de(porta) == PORTA_INFERENCIA or _e_porta_de_inferencia(a[1:3]):
            anfitriao = k["host"] if "host" in k else (a[1] if len(a) > 1 else None)
            _proibir("create_connection do laço de eventos (asyncio)", f"anfitrião {anfitriao!r}, porta {porta!r}")
        return await create_connection_async_original(self, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", _connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _connect_ex)
    monkeypatch.setattr(socket, "create_connection", _create_connection)
    monkeypatch.setattr(asyncio.base_events.BaseEventLoop, "create_connection", _create_connection_async)


@pytest.fixture(autouse=True)
def ollama_proibido(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Proíbe qualquer chamada ao serviço de inferência local, salvo marcador explícito.

    `autouse` por decisão de arquitetura: a garantia alcança a suíte inteira —
    inclusive o `Motor_de_Correção`, o que cobre R4.5 — sem que nenhum teste
    precise pedi-la. O único escape é `@pytest.mark.ollama`, declarado no
    próprio teste, e o portão local o exclui com `-m "not ollama"` (design §6.1).

    Conexões para qualquer outra porta seguem intactas: os testes de integração
    da Fase 2 sobem a API local em `127.0.0.1:8000` com o `TestClient`, e o
    filtro é pela porta de inferência, não pelo endereço.
    """
    if request.node.get_closest_marker("ollama") is not None:
        yield  # único escape, e ele é declarado no teste
        return

    _substituir_transporte_do_cliente(monkeypatch)
    _interceptar_soquetes(monkeypatch)
    yield


# --------------------------------------------------------------------------- #
# Relógio e semente injetados (design §3.0, §3.3)
# --------------------------------------------------------------------------- #

FUSO_DA_COLETA: Final = timezone(timedelta(hours=-3))
"""Deslocamento de fuso da coleta. Fixo e não-nulo de propósito: carimbo ingênuo
que atravesse o núcleo falha aqui, e não na exportação ISO 8601 (§3.14)."""

INSTANTE_FIXO: Final = datetime(2026, 3, 2, 9, 30, tzinfo=FUSO_DA_COLETA)
"""Instante de referência da suíte. Qualquer valor serve; o que importa é ser o mesmo."""

SEMENTE_FIXA: Final = 20260302
"""Semente de referência. R26.3 exige a semente registrada na proveniência; aqui
ela é fixa para que a mesma execução produza a mesma sequência."""


class RelogioFalso:
    """Relógio injetável e avançável por comando, para cenários de mais de um instante.

    Existe porque parte do protocolo é sobre passagem de tempo — a janela de
    retenção de 168 a 216 h de R12.4 a R12.6 é o caso central — e a alternativa
    seria esperar de verdade ou ler o relógio do sistema, que é exatamente o
    que o núcleo puro não faz.
    """

    def __init__(self, inicio: datetime = INSTANTE_FIXO) -> None:
        self._agora = inicio

    def agora(self) -> datetime:
        """Instante vigente, sem efeito colateral."""
        return self._agora

    def avancar(self, quanto: timedelta) -> datetime:
        """Move o relógio adiante e devolve o novo instante vigente."""
        self._agora += quanto
        return self._agora

    def __call__(self) -> datetime:
        """Permite injetar a própria instância onde se espera um chamável sem argumento."""
        return self._agora


@pytest.fixture
def agora() -> datetime:
    """Instante fixo com fuso, para injetar em `agora: datetime`."""
    return INSTANTE_FIXO


@pytest.fixture
def relogio() -> RelogioFalso:
    """Relógio avançável, novo a cada teste para que nenhum avanço vaze para o seguinte."""
    return RelogioFalso()


@pytest.fixture
def semente() -> int:
    """Semente fixa, para injetar em `semente: int`."""
    return SEMENTE_FIXA


@pytest.fixture
def aleatorio(semente: int) -> random.Random:
    """Gerador semeado e isolado. Instância própria, nunca o estado global de `random`."""
    return random.Random(semente)
