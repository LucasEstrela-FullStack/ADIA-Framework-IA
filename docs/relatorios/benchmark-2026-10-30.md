# Benchmark de modelos — 2026-10-30

Dicas L1 a L3 para os itens praticados, geradas com os mesmos papéis e opções da API (CPU, `num_gpu: 0`, até 120 tokens). L4 não entra: é sempre o exemplo pré-escrito.

| Modelo | Disco | Gerações | Falhas | Vazamentos pegos pela guarda | Mediana | p95 |
| --- | --- | --- | --- | --- | --- | --- |
| `llama3.2:1b` | 1.32 GB | 36 | 0 | 12 | 10.2 s | 16.0 s |
| `qwen2.5:1.5b` | 0.99 GB | 36 | 0 | 2 | 3.4 s | 6.0 s |
| `gemma3:1b` | 0.81 GB | 36 | 0 | 0 | 3.7 s | 5.5 s |

Vazamento pego pela guarda não chega ao estudante (vira dica pré-escrita), mas cada um é uma dica gerada perdida. O que a tabela não mede, e a amostra abaixo serve para julgar: português correto, pertinência ao problema e respeito ao nível pedido.

## Amostra: `llama3.2:1b`

- `alg-eq-101` L1: O que precisa continuar valendo nos dois lados de uma igualdade para que ela siga verdadeira depois de você mexer nela é que a variável que você está tentando resolver seja igual a zero.
- `alg-eq-101` L2: Para resolver a equação 2x + 3 = 11, podemos usar a dica de "subtrair 3 do outro lado" para simplificar a equação. Isso nos ajuda a "esvaziar" a constante do lado esquerdo, tornando a equação mais fácil de resolver.
- `alg-eq-101` L3: Dica: Primeiro, desfaça a soma que acompanha a incógnita, aplicando a operação inversa aos dois membros.
- `alg-eq-102` L1 — **guarda: equacao**: O que está afirmando na equação é que 3y é igual a 16 mais 5.
- `alg-eq-102` L2 — **guarda: equacao**: Para resolver essa equação, vamos começar com a dica: "Soma e multiplicação se desfazem por caminhos distintos". Vamos primeiro multiplicar ambos os lados da equação por 1 para remover o termo constante de 3y. Isso nos dará a equação 3y - 5 = 16, 3y = 21. Agora, vamos multiplicar ambos os lados da equação por 3 para resolver y. Isso nos dará a equação 9y = 63. Ag
- `alg-eq-102` L3: Para resolver a equação 3y - 5 = 16, o primeiro passo é anular o termo constante do lado da incógnita, aplicando a operação inversa da subtração, que é a multiplicação por -1.
- `alg-eq-103` L1: Resolvi a equação sem hesitar: **parte que gera dúvida é a parte que envolve o m**. A equação é: 4m + 6 = 18 A dica é: **verifique se a equação é verdadeira para qualquer valor de m**.
- `alg-eq-103` L2 — **guarda: numero**: Para resolver essa equação, você precisa multiplicar ambos os lados pela razão que está entre o termo multiplicado (6) e o termo constante (4), que é 3. A dica é multiplicar ambos os lados pela razão que está entre o termo multiplicado e o termo constante.
- `alg-eq-103` L3 — **guarda: aritmetica**: Para resolver a equação 4m + 6 = 18, vamos seguir os passos abaixo: 1. Isolar o termo que contém a incógnita (m): - 4m + 6 = 18 - 4m = 18 - 6 - 4m = 12 2. Aplique a operação inversa da multiplicação para isolar o termo que contém a incógnita: - 4m = 12 - m = 12 / 4

## Amostra: `qwen2.5:1.5b`

- `alg-eq-101` L1: Parece que você já sabe começar. Para resolver a equação 2x + 3 = 11, você precisa fazer o que?
- `alg-eq-101` L2: Agora, vamos resolver a equação 2x + 3 = 11. Primeiro, vamos desfazer a adição de 3, subtraindo 3 de ambos os lados.
- `alg-eq-101` L3: Primeiro, desfaça a soma que acompanha a incógnita, subtraindo 3 de ambos os lados da equação.
- `alg-eq-102` L1: Leia a equação em voz alta, em palavras, antes de escrever qualquer passo: o que ela está afirmando sobre a incógnita?
- `alg-eq-102` L2: O problema envolve uma equação linear. A chave é entender que a incógnita está subtraída de um termo constante.
- `alg-eq-102` L3: Anulando a subtração, adicionamos 5 a ambos os lados da equação.
- `alg-eq-103` L1: Que parte do problema você já entendeu?
- `alg-eq-103` L2: Agora, vamos resolver a equação 4m + 6 = 18. Primeiro, vamos desfazer o sinal de adição, que é o mesmo que subtrair. Então, vamos subtrair 6 de ambos os lados da equação.
- `alg-eq-103` L3: Isolar m.

## Amostra: `gemma3:1b`

- `alg-eq-101` L1: O que você sabe sobre a equação?
- `alg-eq-101` L2: Ok, vamos entender o que estamos buscando. A equação nos diz que precisamos encontrar o valor de 'x' que, quando multiplicado por 2, resulta em 11. Precisamos encontrar o 'x' que, quando multiplicado por 2, se aproxima de 11.
- `alg-eq-101` L3: Vamos começar com a subtração para eliminar a incógnita. Primeiro, subtraia 3 de ambos os lados da equação.
- `alg-eq-102` L1: Ok, vamos lá! Qual é o que você precisa resolver com essa equação?
- `alg-eq-102` L2: Vamos entender o que estamos procurando! A equação nos diz que uma quantidade está sendo subtraída de outra. Precisamos encontrar o valor de y para que a equação seja verdadeira.
- `alg-eq-102` L3: Vamos começar com a equação original.
- `alg-eq-103` L1: Ok, vamos lá! Primeiro, você sabe o que significa "m" nesse contexto? Depois, você já se lembra de como resolver equações simples?
- `alg-eq-103` L2: Vamos entender o que estamos tentando encontrar. A equação pede para encontrar o valor de 'm' que, quando multiplicado por 4, resulta em 18. Precisamos encontrar o que 'm' representa nesse contexto.
- `alg-eq-103` L3: Vamos começar com a subtração para encontrar o valor de m.
