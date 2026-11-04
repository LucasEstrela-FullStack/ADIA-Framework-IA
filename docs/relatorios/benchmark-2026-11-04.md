# Benchmark de modelos — 2026-11-04

Dicas L1 a L3 para os itens praticados, geradas com os mesmos papéis e opções da API (CPU, `num_gpu: 0`, até 120 tokens). L4 não entra: é sempre o exemplo pré-escrito.

| Modelo | Disco | Gerações | Falhas | Vazamentos pegos pela guarda | Mediana | p95 |
| --- | --- | --- | --- | --- | --- | --- |
| `qwen2.5:1.5b` | 0.99 GB | 36 | 0 | 3 | 3.3 s | 5.5 s |
| `qwen2.5:3b` | 1.93 GB | 36 | 0 | 0 | 9.6 s | 15.2 s |

Vazamento pego pela guarda não chega ao estudante (vira dica pré-escrita), mas cada um é uma dica gerada perdida. O que a tabela não mede, e a amostra abaixo serve para julgar: português correto, pertinência ao problema e respeito ao nível pedido.

## Amostra: `qwen2.5:1.5b`

- `alg-eq-101` L1: O que você precisa continuar valendo nos dois lados de uma igualdade para que ela siga verdadeira depois de você mexer nela?
- `alg-eq-101` L2: Esta é uma equação do primeiro grau com uma incógnita. A igualdade funciona como uma balança em equilíbrio: os dois membros valem o mesmo, e é esse equilíbrio que a resolução preserva.
- `alg-eq-101` L3: Primeiro, subtraia 3 dos dois lados para desfazer a soma que acompanha x.
- `alg-eq-102` L1: Leia a equação em voz alta, em palavras, antes de escrever qualquer passo: o que ela está afirmando sobre a incógnita?
- `alg-eq-102` L2: A ideia é entender que termos constantes e termos variáveis são diferentes e precisamos adicionar para resolver.
- `alg-eq-102` L3: Anulando o termo constante do lado da incógnita com a operação inversa da subtração, aplicada aos dois membros, subtraia 5 de ambos os lados.
- `alg-eq-103` L1: Qual parte da equação você resolveu facilmente? E qual parte ainda causa dúvida?
- `alg-eq-103` L2: Identificar a incógnita m, que está multiplicada por 4, e somado a 6, resultando em 18.
- `alg-eq-103` L3: Subtraia 6 dos dois lados.

## Amostra: `qwen2.5:3b`

- `alg-eq-101` L1: O que precisa continuar valendo nos dois lados de uma igualdade para que ela siga verdadeira depois de você adicionar ou subtrair algo de ambos os lados?
- `alg-eq-101` L2: Esta é uma equação do primeiro grau com uma incógnita. A igualdade funciona como uma balança em equilíbrio: os dois membros valem o mesmo, e é esse equilíbrio que a resolução preserva.
- `alg-eq-101` L3: Subtraia 3 de ambos os membros para cancelar a soma com a incógnita.
- `alg-eq-102` L1: Qual é a mensagem que a equação 3y - 5 = 16 está transmitindo sobre a incógnita y?
- `alg-eq-102` L2: A dica é que na equação, você está lidando com uma subtração envolvendo uma incógnita, e não pode simplesmente adicionar o mesmo valor a ambos os lados para resolver, precisando usar a soma de maneiras distintas.
- `alg-eq-102` L3: Anule o termo constante do lado da incógnita com a operação inversa da subtração, que é a adição, aplicada aos dois membros.
- `alg-eq-103` L1: Qual parte desta equação você resolveria sem hesitar, e qual parte gera dúvida? Comece nomeando as duas.
- `alg-eq-103` L2: Reconhecer a ordem de ter uma incógnita multiplicada por um coeficiente e depois somado a um termo constante é crucial para desfazê-la, permitindo isolá-la e encontrar seu valor.
- `alg-eq-103` L3: Subtraia 6 de ambos os lados para isolar o termo com m.
