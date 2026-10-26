# Critérios de aderência ao nível de ajuda solicitado

Documento normativo dos critérios usados pelo `Benchmark_de_Modelos` para julgar se a dica
que um modelo candidato produziu corresponde ao nível de ajuda solicitado. É a referência
que R20.4 cita.

> **Estado deste documento: esqueleto.** Os critérios **ainda não estão decididos** na spec:
> R20.4 exige que sejam declarados em `docs/`, sem fixá-los. A tarefa 1.1 cria o arquivo e a
> estrutura; o conteúdo vem da tarefa que implementa o benchmark, em `ml/benchmark/`.

## O que esta medida é e o que não é

A taxa de aderência mede uma coisa estreita: se o texto produzido fica **no nível de
diretividade pedido**, de L1 a L4. Ela não mede qualidade pedagógica. Se a dica L2 de fato
ajuda mais que a L1, se a formulação é correta quanto ao conteúdo, se a progressão de L1 a
L4 faz sentido para um estudante — nada disso é computável, exige julgamento humano, e tem
destino em `relatorios/`, não aqui.

A aderência é também independente da guarda: um texto pode aderir ao nível **e** vazar o
gabarito. As duas medidas do benchmark são separadas de propósito, e a taxa de vazamento é
julgada pela própria `Guarda_de_Vazamento`, não por estes critérios.

## Critérios por nível

Previsto: para cada nível de L1 a L4, o conjunto de critérios verificáveis que caracterizam
aderência, com a forma de julgamento de cada um e o que conta como violação.

*A preencher pela tarefa do `Benchmark_de_Modelos`.*

## Cálculo da taxa

Previsto: o conjunto de pedidos usado, como cada julgamento entra na taxa, e o tratamento de
caso indeterminado.

*A preencher pela tarefa do `Benchmark_de_Modelos`.*

## Procedimento de julgamento

Previsto: quem ou o que julga cada critério, e — se houver julgamento humano — como a
concordância entre avaliadores é apurada e registrada.

*A preencher pela tarefa do `Benchmark_de_Modelos`. Qualquer critério acrescentado aqui é
decisão operacional e precisa de entrada correspondente em [`decisoes.md`](decisoes.md).*
