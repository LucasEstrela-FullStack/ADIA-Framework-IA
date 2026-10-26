"""Conjunto declarado da camada 3 da fronteira determinística: a fixture `ollama_proibido`.

Fica em `conjuntos/` ao lado das outras duas camadas — `test_contratos_de_import.py`
é a camada 1 e `tipos_fronteira.py` é a camada 2 — porque as três respondem à
mesma pergunta por meios diferentes, e separá-las por diretório esconderia isso.

Um teste de fixture tem uma inversão própria: aqui o sujeito sob verificação é o
**arnês**, não o domínio. Três afirmações o sustentam, e cada uma falharia por um
motivo distinto se a camada regredisse:

1. a fixture **morde**: cada um dos quatro pontos interceptados levanta
   `ChamadaDeInferenciaProibida` ao tentar a porta de inferência, por qualquer
   endereço — `127.0.0.1`, `localhost`, `::1` e o IP da interface local;
2. a fixture **não produz falso positivo**: conexão para qualquer outra porta
   passa intacta, que é o que permite aos testes de integração da Fase 2 subirem
   a API local em `127.0.0.1:8000` com o `TestClient`;
3. o marcador **libera**: sob `@pytest.mark.ollama` nenhum dos quatro pontos
   está substituído.

A quarta afirmação é sobre o dublê de transporte, que depende de um módulo que
ainda não existe, e está em `test_transporte_do_cliente_oficial_acompanha_o_modulo`.

**Validates: Requirements 30.1, 4.5, 24.8**
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import random
import socket
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Final

import pytest
from conftest import (
    ATRIBUTO_DO_TRANSPORTE,
    MODULO_DO_CLIENTE,
    PORTA_INFERENCIA,
    ChamadaDeInferenciaProibida,
    RelogioFalso,
    cliente_oficial_existe,
)

from adia import cli

# Capturados na importação do módulo, que acontece na coleta — antes de qualquer
# fixture rodar. São a referência de identidade para decidir se a interceptação
# está instalada, sem depender de conexão nenhuma.
_CONNECT_REAL: Final = socket.socket.connect
_CONNECT_EX_REAL: Final = socket.socket.connect_ex
_CREATE_CONNECTION_REAL: Final = socket.create_connection
_CREATE_CONNECTION_ASYNC_REAL: Final = asyncio.base_events.BaseEventLoop.create_connection


def _ip_da_interface_local() -> str:
    """IP da interface local, que não é `127.0.0.1` e é por onde o filtro por endereço vazaria.

    Resolução de nome, não conexão: nada aqui atravessa a interceptação.
    """
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:  # pragma: no cover - máquina sem nome resolvível
        return "127.0.0.1"


IP_LOCAL: Final = _ip_da_interface_local()


@pytest.fixture
def ouvinte_local() -> Iterator[tuple[str, int]]:
    """Soquete escutando numa porta efêmera do laço local — qualquer uma, menos a da inferência.

    É o que torna a prova de ausência de falso positivo uma conexão de verdade,
    e não a ausência de exceção numa tentativa que falharia de todo jeito.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.bind(("127.0.0.1", 0))
        servidor.listen(1)
        anfitriao, porta = servidor.getsockname()
        assert porta != PORTA_INFERENCIA
        yield anfitriao, porta


async def _abrir_e_fechar(anfitriao: str, porta: int | str) -> None:
    """Conexão assíncrona pelo caminho de alto nível, que passa por `loop.create_connection`."""
    _, escritor = await asyncio.open_connection(anfitriao, porta)
    escritor.close()
    with contextlib.suppress(OSError):
        await escritor.wait_closed()


async def _create_connection_por_palavra_chave(anfitriao: str, porta: int) -> None:
    """Mesmo ponto do laço de eventos, com anfitrião e porta passados por palavra-chave."""
    laco = asyncio.get_running_loop()
    await laco.create_connection(asyncio.Protocol, host=anfitriao, port=porta)


# --------------------------------------------------------------------------- #
# Prova 1 — a fixture morde, nos quatro pontos e por qualquer endereço
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("familia", "endereco"),
    [
        (socket.AF_INET, ("127.0.0.1", PORTA_INFERENCIA)),
        (socket.AF_INET, ("localhost", PORTA_INFERENCIA)),
        (socket.AF_INET, (IP_LOCAL, PORTA_INFERENCIA)),
        (socket.AF_INET6, ("::1", PORTA_INFERENCIA, 0, 0)),
    ],
    ids=["laco_ipv4", "nome_localhost", "ip_da_interface", "laco_ipv6"],
)
def test_connect_para_a_inferencia_e_proibido_em_qualquer_endereco(
    familia: socket.AddressFamily, endereco: tuple[object, ...]
) -> None:
    """Ponto 1 de 4: `socket.connect`. A proibição é por porta, então nenhum endereço escapa."""
    with socket.socket(familia, socket.SOCK_STREAM) as cliente:
        with pytest.raises(ChamadaDeInferenciaProibida) as capturado:
            cliente.connect(endereco)
    assert "socket.connect" in str(capturado.value)
    assert repr(endereco) in str(capturado.value)


def test_connect_ex_para_a_inferencia_e_proibido() -> None:
    """Ponto 2 de 4: `socket.connect_ex`, que é como uma sondagem verifica porta sem falhar."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:
        with pytest.raises(ChamadaDeInferenciaProibida) as capturado:
            cliente.connect_ex(("127.0.0.1", PORTA_INFERENCIA))
    assert "sondagem" in str(capturado.value)
    assert "socket.connect_ex" in str(capturado.value)


def test_create_connection_para_a_inferencia_e_proibido() -> None:
    """Ponto 3 de 4: `socket.create_connection`, o atalho que resolve nome e conecta."""
    with pytest.raises(ChamadaDeInferenciaProibida) as capturado:
        socket.create_connection(("127.0.0.1", PORTA_INFERENCIA), timeout=1)
    assert "socket.create_connection" in str(capturado.value)


@pytest.mark.parametrize("porta", [PORTA_INFERENCIA, str(PORTA_INFERENCIA)], ids=["inteira", "em_texto"])
def test_create_connection_do_laco_de_eventos_e_proibido(porta: int | str) -> None:
    """Ponto 4 de 4, posicional: é por onde `httpx`, `anyio` e `aiohttp` terminam.

    A porta em texto é chamada válida de `asyncio.open_connection`; comparar sem
    normalizar deixaria essa passar.
    """
    with pytest.raises(ChamadaDeInferenciaProibida) as capturado:
        asyncio.run(_abrir_e_fechar("127.0.0.1", porta))
    assert "laço de eventos" in str(capturado.value)


def test_create_connection_do_laco_de_eventos_por_palavra_chave_e_proibido() -> None:
    """Mesmo ponto, forma por palavra-chave: `host=` e `port=` não escapam do filtro."""
    with pytest.raises(ChamadaDeInferenciaProibida) as capturado:
        asyncio.run(_create_connection_por_palavra_chave("127.0.0.1", PORTA_INFERENCIA))
    assert "laço de eventos" in str(capturado.value)


def test_sondagem_do_doutor_e_proibida_e_nao_e_engolida_por_except_oserror() -> None:
    """A sondagem de `adia doutor` é travessia em tempo de execução, e é pega como tal.

    O valor deste teste não é a sondagem em si, é o tipo da exceção.
    `_servico_ollama_responde` trata falha de rede com `except OSError` e
    devolve `False`; se `ChamadaDeInferenciaProibida` herdasse de `OSError`, a
    travessia detectada viraria "serviço indisponível" e a camada ficaria muda.
    """
    assert not issubclass(ChamadaDeInferenciaProibida, OSError)
    with pytest.raises(ChamadaDeInferenciaProibida):
        cli._servico_ollama_responde()


# --------------------------------------------------------------------------- #
# Prova 2 — nenhum falso positivo: outra porta passa intacta
# --------------------------------------------------------------------------- #


def test_connect_em_outra_porta_passa(ouvinte_local: tuple[str, int]) -> None:
    """Conexão síncrona para porta que não é a da inferência atravessa sem erro."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:
        cliente.connect(ouvinte_local)
        assert cliente.getpeername() == ouvinte_local


def test_connect_ex_em_outra_porta_passa(ouvinte_local: tuple[str, int]) -> None:
    """`connect_ex` segue devolvendo código de erro, e não exceção, fora da porta proibida."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:
        assert cliente.connect_ex(ouvinte_local) == 0


def test_create_connection_em_outra_porta_passa(ouvinte_local: tuple[str, int]) -> None:
    """É este caminho que o `TestClient` da Fase 2 usa contra a API local em 127.0.0.1:8000."""
    with socket.create_connection(ouvinte_local, timeout=5) as conexao:
        assert conexao.getpeername() == ouvinte_local


def test_laco_de_eventos_em_outra_porta_passa(ouvinte_local: tuple[str, int]) -> None:
    """O ponto assíncrono também deixa passar: a API local não fica inalcançável."""
    asyncio.run(_abrir_e_fechar(*ouvinte_local))


def test_endereco_que_nao_e_de_rede_passa() -> None:
    """Endereço fora da forma `(anfitrião, porta)` não é tratado como inferência.

    Soquete de domínio Unix recebe caminho em texto, e indexar `endereco[1]`
    nele daria a letra errada em vez de uma porta. O `TypeError` que aparece é o
    do `connect` real recusando a forma do endereço, e é justamente a prova de
    que o valor atravessou o filtro em vez de ser confundido com inferência.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:
        with pytest.raises(TypeError) as capturado:
            cliente.connect("nao-e-endereco-de-rede")
    assert not isinstance(capturado.value, ChamadaDeInferenciaProibida)


# --------------------------------------------------------------------------- #
# Prova 3 — a inversão de padrão: proibido por omissão, liberado por marcador
# --------------------------------------------------------------------------- #


def test_interceptacao_instalada_sem_marcador() -> None:
    """Sem marcador, os quatro pontos estão substituídos. É o padrão da suíte."""
    assert socket.socket.connect is not _CONNECT_REAL
    assert socket.socket.connect_ex is not _CONNECT_EX_REAL
    assert socket.create_connection is not _CREATE_CONNECTION_REAL
    assert asyncio.base_events.BaseEventLoop.create_connection is not _CREATE_CONNECTION_ASYNC_REAL


@pytest.mark.ollama
def test_marcador_ollama_libera_os_quatro_pontos() -> None:
    """Com `@pytest.mark.ollama`, nada está substituído e a porta é alcançável.

    Fora do portão local por construção (`-m "not ollama"`, design §6.1): é o
    escape declarado, e declarar é o que o torna aceitável.
    """
    assert socket.socket.connect is _CONNECT_REAL
    assert socket.socket.connect_ex is _CONNECT_EX_REAL
    assert socket.create_connection is _CREATE_CONNECTION_REAL
    assert asyncio.base_events.BaseEventLoop.create_connection is _CREATE_CONNECTION_ASYNC_REAL

    # Serviço desligado é `OSError`, e isso não interessa aqui. O que interessa é
    # que a fixture não está no caminho.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cliente:
        cliente.settimeout(2)
        with contextlib.suppress(OSError):
            cliente.connect(("127.0.0.1", PORTA_INFERENCIA))


# --------------------------------------------------------------------------- #
# O dublê de transporte, e a trava contra o desarme silencioso
# --------------------------------------------------------------------------- #


def test_transporte_do_cliente_oficial_acompanha_o_modulo() -> None:
    """Invariante dos dois estados da substituição condicional do transporte.

    Sem `adia.ia.cliente_ollama`, a ausência tem de ser **real** — o import
    falha de fato, e não por erro mascarado. Com o módulo, o dublê tem de
    morder. Este teste é o que impede que a condição se torne um desarme
    silencioso: no dia em que a tarefa 13.1 criar o cliente, ele passa a
    exercitar a substituição, e falha se ela não estiver ativa.
    """
    if not cliente_oficial_existe():
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(MODULO_DO_CLIENTE)
        return

    modulo = importlib.import_module(MODULO_DO_CLIENTE)
    classe, atributo = ATRIBUTO_DO_TRANSPORTE.split(".")
    transporte = getattr(getattr(modulo, classe), atributo)
    with pytest.raises(ChamadaDeInferenciaProibida) as capturado:
        transporte()
    assert "ClienteOllama" in str(capturado.value)


# --------------------------------------------------------------------------- #
# Relógio e semente injetados
# --------------------------------------------------------------------------- #


def test_relogio_injetado_e_fixo_e_com_fuso(agora: datetime, relogio: RelogioFalso) -> None:
    """O instante é o mesmo a cada leitura e traz deslocamento de fuso.

    Carimbo ingênuo que atravesse o núcleo falha aqui, e não na exportação.
    """
    assert relogio.agora() == agora
    assert relogio.agora() == relogio()
    assert relogio.agora().utcoffset() is not None


def test_relogio_avanca_so_por_comando(relogio: RelogioFalso) -> None:
    """A janela de retenção de 168 a 216 h (R12.4 a R12.6) depende de avanço explícito."""
    inicio = relogio.agora()
    assert relogio.avancar(timedelta(hours=168)) - inicio == timedelta(hours=168)
    assert relogio.agora() - inicio == timedelta(hours=168)


def test_semente_injetada_produz_sequencia_reproduzivel(semente: int, aleatorio: random.Random) -> None:
    """Mesma semente, mesma sequência — e instância própria, nunca o estado global."""
    referencia = random.Random(semente)
    assert [aleatorio.random() for _ in range(5)] == [referencia.random() for _ in range(5)]
    assert aleatorio is not random.Random(semente)
