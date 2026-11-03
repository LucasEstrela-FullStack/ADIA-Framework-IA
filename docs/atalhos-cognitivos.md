# Eventos mensuráveis de atalho cognitivo

Documento normativo dos eventos a partir dos quais o mapa de calor de atalhos cognitivos do
`Painel_do_Professor` é construído. É a referência que R19.2 cita.

> **Estado deste documento: provisório.** A spec não declara a lista de eventos. Os três
> padrões abaixo foram decididos em [DO-48](decisoes.md) como ponto de partida e estão
> implementados em `backend/adia/nucleo/metricas/atalhos.py`. Padrões e limiares de tempo
> precisam da revisão da pesquisa antes de qualquer análise com dados do piloto.

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

| Padrão | Condição sobre o log | Oportunidade | Eventos consultados |
| --- | --- | --- | --- |
| `dica_alta_direta` | a primeira dica pedida no item é L3 ou L4, sem passar por L1 nem L2 | item respondido com pelo menos uma dica | `dica` (nível, ordem) e a `resposta` que fecha o item |
| `resposta_logo_apos_exemplo` | a resposta chega menos de 20 s depois da última dica L4 do item | item respondido com dica L4 | `dica` L4 e `resposta`, pelos carimbos `criado_em` |
| `resposta_relampago` | em etapa sem IA (linha de base, desafio, retenção), a resposta chega menos de 5 s depois da resposta anterior ou do início da sessão | resposta em etapa sem IA | `resposta` e `sessao.criada_em` |

O primeiro é o exemplo do glossário, adaptado: a tela não registra resposta parcial, então
"sem resposta parcial" vira "sem ter passado pelos níveis baixos". O segundo pega a cópia do
exemplo resolvido. O terceiro pega o chute, porque nenhum item do banco se resolve com
leitura e conta em menos de 5 s. Todos saem do registro por replay, sem julgamento humano e
sem modelo de linguagem. Cada padrão novo precisa de entrada correspondente em
[`decisoes.md`](decisoes.md).

## Agregação no mapa de calor

Uma linha por participante e uma coluna por par habilidade alvo e padrão. A célula mostra
`ocorrências/oportunidades`, e a cor é a proporção: transparente em 0, cor de aviso cheia
em 1. Célula sem oportunidade mostra `—`, para não confundir "não fez" com "não teve
chance". Item sem habilidade conhecida conta em `desconhecida`. O mapa fica no painel do
pesquisador (`adia painel`), fora da API, ao lado do aviso de R25.8.
