# Colunas e chave de junção das exportações CSV

Documento normativo dos cabeçalhos das exportações do `Exportador_CSV`. É a referência que
R16.4 e R16.6 citam. Um CSV de pesquisa que circula sem cabeçalho documentado é um CSV que
vai ser mal interpretado em algum momento; este arquivo existe para evitar isso.

> **Estado deste documento: esqueleto.** O formato geral e a chave de junção abaixo já estão
> fixados pelo design e valem como especificação. As tabelas coluna a coluna são produzidas
> pela tarefa que implementa o `Exportador_CSV`, em `backend/adia/exportacao/`.

## Formato dos arquivos

Já fixado pelo design:

| Aspecto | Regra |
| --- | --- |
| Arquivos por sessão | Dois: `eventos_{sessao_id}.csv` e `metricas_{sessao_id}.csv` |
| Codificação | UTF-8 |
| Fim de linha | `\n` |
| Separador decimal | `.` (ponto) |
| Carimbos de tempo | ISO 8601 com deslocamento de fuso |
| Precisão de métrica | No mínimo seis casas decimais, sem arredondamento, completadas com zeros quando o valor tem menos |
| Métrica indisponível | Coluna de valor vazia e motivo preenchido, **nunca** `0` |
| Identificação | Só pseudônimos |

## Chave de junção

Já fixado pelo design: **`(sessao_id, ciclo, etapa)`**. É a tripla que permite unir o
arquivo de eventos ao de métricas da mesma sessão.

*As regras de junção para linhas que não pertencem a um ciclo ou a uma etapa — onboarding,
atribuição de condição — ficam para a tarefa do exportador.*

## Colunas de proveniência

Já fixado pelo design: as **seis últimas colunas** de cada arquivo repetem o mesmo valor em
todas as linhas, por decisão deliberada de redundância:

`exportacao_id`, `exportado_em`, `prototipo_versao`, `commit_sha`, e mais `limiares_versao`
e `banco_itens_hash` ou `esquema_versao`, conforme o arquivo.

A decisão de embutir proveniência em coluna, em vez de linha de comentário ou arquivo
lateral, está marcada no design para registro em [`decisoes.md`](decisoes.md) e consta como
pendência lá.

## Cabeçalho de `eventos_{sessao_id}.csv`

Previsto: tabela coluna a coluna, com nome, tipo, significado e domínio de valores.

*A preencher pela tarefa do `Exportador_CSV`.*

## Cabeçalho de `metricas_{sessao_id}.csv`

Previsto: tabela coluna a coluna, incluindo o domínio de `indisponivel_motivo`.

*A preencher pela tarefa do `Exportador_CSV`.*

## Ida e volta

Previsto: a especificação da função de reimportação que sustenta a propriedade de ida e
volta de R16.5, e o que exatamente se preserva nela.

*A preencher pela tarefa do `Exportador_CSV`.*
