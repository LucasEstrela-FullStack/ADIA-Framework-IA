# Conjunto de verificação da `Guarda_de_Vazamento`

Documento normativo da composição do conjunto declarado de verificação e dos portões que ele
sustenta. É a referência que R7.11 cita. O conjunto vive em
`data/guarda/conjunto_verificacao.jsonl` e é avaliado por `adia guarda verificar`.

> **Estado deste documento: esqueleto.** A composição mínima e os dois portões abaixo já
> estão fixados por R7.11 e valem como especificação. O inventário caso a caso é produzido
> pela tarefa que monta o conjunto e implementa a guarda, em `backend/adia/guarda/`.

## Portões

Já fixado. Os dois limiares são verificados sobre este conjunto:

| Portão | Exigência |
| --- | --- |
| Detecção de vazamento | **100%** dos casos de vazamento classificados corretamente |
| Acerto em dica legítima | `VN / (VN + FP) >= 0,95` — no máximo 5% de falso positivo |

A assimetria é deliberada e está justificada em `DO-03` de [`decisoes.md`](decisoes.md): um
vazamento não detectado contamina de forma irreversível o dado experimental; um falso
positivo custa uma dica pré-escrita.

`adia guarda verificar` roda **antes** do `pytest` no portão local, porque é o portão mais
barato de reparar e o mais caro de ignorar.

## Composição mínima

Já fixado por R7.11. O conjunto contém, no mínimo:

1. **Ao menos um caso por forma de detecção** dos critérios 2, 9 e 10 de R7 — ou seja, por
   forma de vazamento que a guarda é obrigada a reconhecer.
2. **Ao menos um caso de equação linear** cuja resolução revele o valor da incógnita em
   etapas intermediárias. É o caso difícil: o gabarito não aparece escrito, mas o caminho
   mostrado o entrega.
3. **As dicas de L1 a L4 do `Catálogo_de_Dicas_Pré_Escritas` de cada item.** São os casos
   legítimos de referência, e a razão pela qual o portão bloqueia a Fase 3 mesmo sem
   geração nenhuma: na Fase 3 o catálogo pré-escrito é o conteúdo primário, e um catálogo
   que vaza é um protótipo que vaza, com ou sem modelo.

## Inventário dos casos

Previsto: tabela com uma linha por caso, contendo identificador, item de referência,
classificação esperada entre vazamento e legítimo, a forma de vazamento exercitada, e a
procedência do caso.

*A preencher pela tarefa que monta o conjunto.*

## Ordem de reparo quando o portão falha

Já fixado pelo design: **conteúdo, depois detector, e só então o conjunto.** Ajustar o
conjunto é a última opção, não a primeira, porque o conjunto é a medida — afrouxá-lo para
passar o portão destrói a única garantia que ele oferece.

**Qualquer alteração no próprio conjunto entra como decisão operacional em
[`decisoes.md`](decisoes.md), com o caso, o motivo e quem decidiu.**

## Formato do arquivo

Previsto: o esquema de cada linha de `data/guarda/conjunto_verificacao.jsonl`.

*A preencher pela tarefa que monta o conjunto.*
