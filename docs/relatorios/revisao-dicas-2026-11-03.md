# Revisão humana das dicas geradas — 2026-11-03

Planilha: `revisao-dicas-2026-11-03.csv` (separador `;`, abre no Excel).

58 dicas geradas pelo caminho real da API (papel do nível, trecho do RAG, guarda e filtro
DO-51), duas gerações por nível L1 a L3 em cada um dos 12 itens praticados, sem as
repetidas (a temperatura é 0,3 e 14 dos 36 pares saíram iguais). A coluna `filtro` diz se a
dica chegaria ao estudante (`passou`) ou se viraria a pré-escrita, e por quê.

## Como marcar

Preencha `serve (s/n)` em todas as linhas, inclusive nas que o filtro descartou: um
descarte de dica boa também é erro a corrigir. Em `comentario`, diga o problema em poucas
palavras quando marcar `n`.

Uma dica serve quando:

- está em português correto e um estudante do ensino médio a entende sem ajuda;
- fala do problema da linha, não de outro;
- respeita o nível: L1 é pergunta que faz pensar, sem dizer o que fazer; L2 nomeia a ideia
  matemática, sem mandar fazer operação; L3 diz só o primeiro passo, sem fazer a conta;
- não entrega a resposta nem o resultado de um passo.

Compare com `dica_de_referencia`, que é a pré-escrita revisada do mesmo nível.

## Depois da marcação

As marcações `n` com motivo comum viram ajuste no papel (`backend/adia/ia/subagentes/papeis.py`)
ou no filtro (`backend/adia/guarda/qualidade.py`), e uma nova amostra mede o efeito:
`uv run adia amostra-de-dicas` grava `revisao-dicas-<data>.csv` nesta pasta, já sem as repetidas.
