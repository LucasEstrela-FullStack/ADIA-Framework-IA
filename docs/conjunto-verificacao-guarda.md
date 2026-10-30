# Conjunto de verificação da `Guarda_de_Vazamento`

Documento normativo da composição do conjunto declarado de verificação e dos portões que ele
sustenta. É a referência que R7.11 cita. O conjunto vive em
`data/guarda/conjunto_verificacao.jsonl` e é avaliado por `adia guarda verificar`.

O conjunto e o detector estão em `backend/adia/guarda/` (`veredito.py`, `aritmetica.py` e
`conjunto.py`). Na versão de 2026-10-30, `adia guarda verificar` detecta 24 de 24 vazamentos
e aceita 159 de 159 dicas legítimas (39 casos declarados mais as 144 dicas do catálogo).

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

Os casos declarados estão abaixo. O catálogo pré-escrito entra inteiro como legítimo, gerado
na hora a partir do banco de itens (`catalogo:<item>:<nível>`), para que um item novo nunca
fique fora da verificação.

Formas de vazamento reconhecidas:

| Forma | O que pega | Exemplo |
| --- | --- | --- |
| `literal` | gabarito ou variação declarada escrita no texto | "o valor é quatro" |
| `numero` | número dentro da tolerância, nas duas leituras de milhar | "x = 4", "1.500" |
| `aritmetica` | expressão sem incógnita cujo resultado é o gabarito (DO-10) | "8 dividido por 2" |
| `equacao` | equação linear na incógnita cuja solução é o gabarito | "2x = 8" |

Limites conhecidos, aceitos por enquanto:

- repetir a equação do próprio enunciado não conta como vazamento, porque não entrega nada;
- escrever a equação de um problema em texto (como "7 + 2k = 31") conta como vazamento,
  porque a solução é o gabarito. É falso positivo aceito: custa uma dica pré-escrita;
- procedimento em palavras sem conta escrita ("faça 11 - 3 e depois divida por 2") não é
  detectado, porque "divida por 2" não forma expressão. O caso fica fora do conjunto até
  haver detector para ele.

| Caso | Item | Esperado | Forma | Procedência |
| --- | --- | --- | --- | --- |
| G-001 | `alg-eq-101` | vazamento | numero | redigido |
| G-002 | `alg-eq-101` | vazamento | literal | redigido |
| G-003 | `alg-eq-101` | vazamento | aritmetica | redigido |
| G-004 | `alg-eq-101` | vazamento | equacao | redigido |
| G-005 | `alg-eq-101` | vazamento | aritmetica | redigido |
| G-006 | `alg-eq-101` | legitimo | — | llama3.2:1b, 2026-10-30 |
| G-007 | `alg-eq-101` | legitimo | — | llama3.2:1b, 2026-10-30 |
| G-008 | `alg-eq-101` | legitimo | — | redigido |
| G-009 | `alg-eq-101` | legitimo | — | redigido |
| G-010 | `alg-eq-102` | vazamento | equacao | redigido |
| G-011 | `alg-eq-102` | vazamento | aritmetica | redigido |
| G-012 | `alg-eq-102` | vazamento | literal | redigido |
| G-013 | `alg-eq-102` | vazamento | numero | redigido |
| G-014 | `alg-eq-102` | legitimo | — | redigido |
| G-015 | `alg-eq-102` | legitimo | — | redigido |
| G-016 | `alg-eq-103` | vazamento | equacao | redigido |
| G-017 | `alg-eq-103` | vazamento | aritmetica | redigido |
| G-018 | `alg-eq-103` | vazamento | numero | redigido |
| G-019 | `alg-eq-103` | legitimo | — | redigido |
| G-020 | `alg-eq-104` | vazamento | equacao | redigido |
| G-021 | `alg-eq-104` | vazamento | aritmetica | redigido |
| G-022 | `alg-eq-104` | vazamento | literal | redigido |
| G-023 | `alg-eq-104` | legitimo | — | redigido |
| G-024 | `alg-eq-104` | legitimo | — | redigido |
| G-025 | `alg-eq-301` | vazamento | equacao | redigido |
| G-026 | `alg-eq-301` | vazamento | aritmetica | redigido |
| G-027 | `alg-eq-301` | vazamento | literal | redigido |
| G-028 | `alg-eq-301` | legitimo | — | redigido |
| G-029 | `alg-eq-301` | legitimo | — | redigido |
| G-030 | `alg-eq-302` | vazamento | aritmetica | redigido |
| G-031 | `alg-eq-302` | vazamento | equacao | redigido |
| G-032 | `alg-eq-302` | legitimo | — | redigido |
| G-033 | `alg-eq-303` | vazamento | literal | redigido |
| G-034 | `alg-eq-303` | vazamento | equacao | redigido |
| G-035 | `alg-eq-303` | legitimo | — | redigido |
| G-036 | `alg-eq-304` | vazamento | equacao | redigido |
| G-037 | `alg-eq-304` | vazamento | aritmetica | redigido |
| G-038 | `alg-eq-304` | legitimo | — | redigido |
| G-039 | `alg-eq-304` | legitimo | — | redigido |

## Ordem de reparo quando o portão falha

Já fixado pelo design: **conteúdo, depois detector, e só então o conjunto.** Ajustar o
conjunto é a última opção, não a primeira, porque o conjunto é a medida — afrouxá-lo para
passar o portão destrói a única garantia que ele oferece.

**Qualquer alteração no próprio conjunto entra como decisão operacional em
[`decisoes.md`](decisoes.md), com o caso, o motivo e quem decidiu.**

## Formato do arquivo

Uma linha JSON por caso, em UTF-8:

```json
{"id": "G-001", "item_id": "alg-eq-101", "texto": "Então x = 4.", "esperado": "vazamento", "forma": "numero", "procedencia": "redigido"}
```

- `esperado`: `vazamento` ou `legitimo`;
- `forma`: a forma de vazamento exercitada, ou `null` em caso legítimo. Conta para a
  composição mínima só quando o detector encontra exatamente essa forma;
- `procedencia`: `redigido` (escrito para o conjunto) ou o modelo e a data, quando o texto
  veio de uma geração real.

Linha que não segue o formato reprova o comando, em vez de ser ignorada.
