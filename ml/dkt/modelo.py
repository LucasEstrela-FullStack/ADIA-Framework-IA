"""Modelo_DKT (Piech et al., 2015): LSTM que estima a chance de acerto no próximo item.

Treina em CPU (R28.1, R28.2). A entrada de cada passo é um embutimento do índice
``item·4 + acerto·2 + assistido``, equivalente à camada linear sobre o *one-hot* do
artigo. A saída tem um logit por item; a perda é a entropia cruzada só no item que o
aluno de fato respondeu a seguir.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import torch
from torch import Tensor, nn

from ml.dkt.dados import Trajetorias


class DKT(nn.Module):
    def __init__(self, itens: int, oculto: int = 64) -> None:
        super().__init__()
        self.embutir = nn.Embedding(4 * itens, oculto)
        self.lstm = nn.LSTM(oculto, oculto, batch_first=True)
        self.saida = nn.Linear(oculto, itens)

    def forward(self, entradas: Tensor) -> Tensor:
        estados, _ = self.lstm(self.embutir(entradas))
        logits: Tensor = self.saida(estados)
        return logits


def _lote(trajetorias: Trajetorias, indices: Sequence[int]) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    """Entradas até o penúltimo passo; alvo, item alvo e máscara do segundo em diante."""
    sequencias = [trajetorias.sequencias[i] for i in indices]
    largura = max(len(s) for s in sequencias)
    entradas = torch.zeros(len(sequencias), largura, dtype=torch.long)
    itens = torch.zeros_like(entradas)
    acertos = torch.zeros(len(sequencias), largura)
    mascara = torch.zeros(len(sequencias), largura, dtype=torch.bool)
    for linha, sequencia in enumerate(sequencias):
        for t, passo in enumerate(sequencia):
            entradas[linha, t] = passo.entrada()
            itens[linha, t] = passo.item
            acertos[linha, t] = float(passo.acerto)
            mascara[linha, t] = True
    return entradas[:, :-1], itens[:, 1:], acertos[:, 1:], mascara[:, 1:]


def _do_alvo(modelo: DKT, entradas: Tensor, itens: Tensor) -> Tensor:
    chances: Tensor = modelo(entradas).gather(2, itens.unsqueeze(2)).squeeze(2)
    return chances


def treinar(
    trajetorias: Trajetorias,
    indices: Sequence[int],
    epocas: int = 30,
    oculto: int = 64,
    taxa: float = 0.005,
    lote: int = 32,
    semente: int = 1,
) -> DKT:
    torch.manual_seed(semente)
    torch.use_deterministic_algorithms(True)
    modelo = DKT(len(trajetorias.itens), oculto)
    otimizador = torch.optim.Adam(modelo.parameters(), lr=taxa)
    perda = nn.BCEWithLogitsLoss()
    gerador = torch.Generator().manual_seed(semente)
    modelo.train()
    for _ in range(epocas):
        ordem = [indices[int(i)] for i in torch.randperm(len(indices), generator=gerador)]
        for inicio in range(0, len(ordem), lote):
            entradas, itens, acertos, mascara = _lote(trajetorias, ordem[inicio : inicio + lote])
            otimizador.zero_grad()
            valor = perda(_do_alvo(modelo, entradas, itens)[mascara], acertos[mascara])
            valor.backward()
            otimizador.step()
    modelo.eval()
    return modelo


def prever(modelo: DKT, trajetorias: Trajetorias, indices: Sequence[int]) -> tuple[list[bool], list[float]]:
    """Rótulo e probabilidade prevista de cada passo a partir do segundo, nos alunos dados."""
    entradas, itens, acertos, mascara = _lote(trajetorias, indices)
    with torch.no_grad():
        chances = torch.sigmoid(_do_alvo(modelo, entradas, itens))[mascara]
    return [bool(a) for a in acertos[mascara].tolist()], [float(c) for c in chances.tolist()]


def salvar(modelo: DKT, trajetorias: Trajetorias, versao: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "estado": modelo.state_dict(),
            "itens": list(trajetorias.itens),
            "oculto": modelo.lstm.hidden_size,
            "versao": versao,
        },
        destino,
    )


def carregar(origem: Path) -> tuple[DKT, list[str], str]:
    """Só tensores e tipos simples: ``weights_only`` recusa objeto arbitrário no arquivo."""
    dados = torch.load(origem, weights_only=True)
    modelo = DKT(len(dados["itens"]), int(dados["oculto"]))
    modelo.load_state_dict(dados["estado"])
    modelo.eval()
    return modelo, list(dados["itens"]), str(dados["versao"])
