"""Cliente do Serviço_de_Inferência_Local: disponibilidade, geração e *embeddings*.

**Esqueleto da Fase 0.** O que está aqui são as duas peças de que a verificação de
isolamento precisa antes de existir cliente nenhum (design §6.4):

- ``RespostaDoModelo``, o tipo que o teste de tipo negativo de
  ``backend/tests/conjuntos/tipos_fronteira.py`` tenta empurrar para dentro do núcleo puro.
  É o lado de fora da fronteira da **camada 2**;
- ``ClienteOllama._transporte``, a costura única que a fixture ``ollama_proibido`` substitui
  pelo dublê. É o ponto de ancoragem da **camada 3**.

O resto é da **tarefa 13.1**: ``disponivel`` (tempo limite de conexão de 1 s e cache de
5 s), ``gerar`` com tempo limite de 20 s e saída de até 120 tokens, ``embutir``,
``descritor_do_modelo``, a restrição do transporte a ``127.0.0.1`` e ``localhost``, o
aquecimento na subida da API e os tipos de retorno ``GeracaoCompleta`` e ``FalhaDeGeracao``
de §3.12.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RespostaDoModelo:
    """Saída bruta do serviço de inferência, do lado probabilístico da fronteira.

    Campos na tarefa 13.1 (§3.12): texto gerado, contagem de tokens, latência e o
    descritor do modelo que a proveniência exige (R26.2).

    Que esta classe **não** seja aceita por ``adia.nucleo.regulacao.regra.decidir`` é o que
    a camada 2 afirma. Dar a ela qualquer compatibilidade com ``EntradaDeRegulacao`` — por
    herança, por protocolo estrutural ou por alias — reprova o ``mypy``, e é essa a
    intenção: a travessia não deve ser escrevível.
    """


class ClienteOllama:
    """Única porta de saída para o serviço de inferência local (§3.12).

    Métodos públicos na tarefa 13.1. O que existe desde a Fase 0 é a costura de transporte,
    porque é dela que a camada 3 depende: a fixture ``ollama_proibido`` troca
    ``ClienteOllama._transporte`` pelo dublê a cada teste sem o marcador ``ollama``. Sem o
    atributo, a troca falharia e a proibição ficaria pela metade — de pé apenas a
    interceptação de soquete, que é a rede larga, não a costura do cliente oficial.
    """

    BASE = "http://127.0.0.1:11434"
    """Endereço do serviço local. A porta 11434 é a que a camada 3 proíbe por destino."""

    def _transporte(self, *argumentos: object, **nomeados: object) -> object:
        """Emite o pedido HTTP ao serviço local e devolve a resposta decodificada.

        A assinatura fica aberta de propósito enquanto o corpo não existe: fixá-la agora
        seria decidir o formato do pedido, que é projeto da tarefa 13.1. O que a Fase 0
        precisa é do **nome** — é por ele que a fixture encontra a costura.
        """
        raise NotImplementedError("O transporte HTTP é implementado na tarefa 13.1 (design §3.12).")
