# Eventos mensuráveis de atalho cognitivo

Documento normativo dos eventos a partir dos quais o mapa de calor de atalhos cognitivos do
`Painel_do_Professor` é construído. É a referência que R19.2 cita.

> **Estado deste documento: esqueleto.** A lista de eventos **ainda não existe** em nenhum
> lugar da spec: nem os requisitos nem o design a declaram. É conteúdo a decidir, não
> conteúdo a transcrever, e por isso a tarefa 1.1 deliberadamente não a preenche. O arquivo
> é criado agora porque R19.2 o nomeia como destino, e um painel construído a partir de
> eventos não declarados seria um painel que ninguém pode auditar.

## Definição

Do glossário dos requisitos: **atalho cognitivo** é o padrão de interação, definido por
eventos mensuráveis, que indica tentativa de obter a solução sem esforço de resolução. O
exemplo dado é o pedido de dica de nível alto sem nenhuma resposta parcial registrada.

Dois limites que a definição impõe e que a lista de eventos precisa respeitar:

- **Mensurável, não inferido.** Cada entrada da lista é um padrão identificável a partir do
  log de eventos, por replay, sem julgamento humano e sem modelo de linguagem.
- **Indicador, não diagnóstico.** O mapa de calor descreve comportamento em tarefas do
  estudo. Não é medida de esforço, de caráter nem de capacidade, e a interface declara esse
  limite onde o apresenta (R25.8).

## Eventos declarados

Previsto: uma tabela com uma linha por evento mensurável, contendo identificador do padrão,
a condição exata sobre o log que o caracteriza, os eventos de origem que a condição consulta,
e a célula do mapa de calor que ele alimenta — por participante e por habilidade alvo.

*A preencher pela tarefa que implementa o mapa de calor de atalhos cognitivos do
`Painel_do_Professor`. Cada evento acrescentado aqui é decisão operacional e precisa de
entrada correspondente em [`decisoes.md`](decisoes.md).*

## Agregação no mapa de calor

Previsto: como as ocorrências são contadas e normalizadas por participante e por habilidade
alvo, e o que a escala de cor representa.

*A preencher pela mesma tarefa.*
