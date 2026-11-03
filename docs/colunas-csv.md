# Colunas e chave de junção das exportações CSV

Documento normativo dos cabeçalhos das exportações do `Exportador_CSV`. É a referência que
R16.4 e R16.6 citam. Um CSV de pesquisa que circula sem cabeçalho documentado é um CSV que
vai ser mal interpretado em algum momento; este arquivo existe para evitar isso.

O exportador está em `backend/adia/exportacao/csv_pesquisa.py` e roda com
`uv run adia exportar`, que grava os arquivos em `exportacoes/<exportacao_id>/`, fora do git.
As métricas saem do replay da sessão, já conferido contra as decisões gravadas (DO-38):
sessão que não se reproduz com o código e o banco de itens atuais não é exportada, e o
comando a nomeia.

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

A linha de base tem `ciclo = 0`. A atribuição de condição não vira linha: a condição vai como
coluna em todas as linhas dos dois arquivos.

## Colunas de proveniência

Já fixado pelo design: as **seis últimas colunas** de cada arquivo repetem o mesmo valor em
todas as linhas, por decisão deliberada de redundância:

`exportacao_id`, `exportado_em`, `prototipo_versao`, `commit_sha`, e mais `limiares_versao`
e `banco_itens_hash` ou `esquema_versao`, conforme o arquivo.

Nos eventos a sexta é `banco_itens_hash`; nas métricas, `esquema_versao`. A decisão de
embutir a proveniência em coluna está em DO-42 de [`decisoes.md`](decisoes.md).

## Cabeçalho de `eventos_{sessao_id}.csv`

Uma linha por dica ou resposta, na ordem do registro.

| Coluna | Tipo | Significado |
| --- | --- | --- |
| `sessao_id` | texto | identificador da sessão |
| `participante_id` | texto | pseudônimo `P-NNNN` |
| `condicao` | `A`, `B`, `C` | condição sorteada |
| `ciclo` | inteiro | 0 na linha de base, 1 a 3 nos ciclos |
| `etapa` | texto | `linha_de_base`, `pratica_assistida` ou `desafio_independente` |
| `sequencia` | inteiro | ordem do evento na sessão, a partir de 1 |
| `tipo` | `dica`, `resposta` | |
| `item_id` | texto | item apresentado |
| `teto` | 1 a 4 | teto de dicas vigente no evento |
| `nivel` | 1 a 4 | nível da dica; vazio em resposta |
| `origem` | `ia`, `pre-escrita` | de onde veio a dica entregue |
| `motivo` | texto | por que a dica pré-escrita substituiu a gerada |
| `texto_dica` | texto | dica entregue ao estudante |
| `resposta` | texto | resposta como o estudante escreveu |
| `acerto` | `1`, `0` | vazio quando o item não tem correção automática |
| `confianca` | 0 a 10 | confiança declarada |
| `explicacao_presente` | `1`, `0` | se houve explicação antes da dica; o texto não sai |
| `justificativa_presente` | `1`, `0` | se houve justificativa da resposta; o texto não sai |
| `segundos_desde_anterior` | decimal | tempo desde a resposta anterior ou o início da sessão, com pausas |
| `criado_em` | ISO 8601 | instante do registro, em UTC |

## Cabeçalho de `metricas_{sessao_id}.csv`

Formato longo: uma linha por métrica de cada ciclo.

| Coluna | Tipo | Significado |
| --- | --- | --- |
| `sessao_id`, `participante_id`, `condicao`, `ciclo` | | como nos eventos |
| `etapa` | texto | etapa de onde a métrica vem: `linha_de_base`, `pratica_assistida`, `desafio_independente`, `projeto_steam` ou `teste_retencao` |
| `metrica` | texto | `acerto_assistido`, `dss`, `tai`, `tt`, `confianca_media`, `brier`, `iic`, `gap`, `vies`; no projeto STEAM, `steam_partes` (proporção de partes numéricas certas) e `steam_rubrica` (pontos da rubrica sobre o máximo, média dos avaliadores), sem decisão (DO-46) |
| `valor` | decimal | vazio quando indisponível |
| `indisponivel_motivo` | texto | por que não há valor; vazio quando há |
| `decisao` | texto | `fading`, `onloading`, `escalonar` ou `manter` |
| `teto` | 1 a 4 | teto vigente no ciclo |
| `teto_indicado` | 1 a 4 | teto que a regra indicou |
| `teto_aplicado` | 1 a 4 | teto do ciclo seguinte de fato; difere do indicado em A e C |
| `decisao_aplicada` | `1`, `0` | 1 só na condição B; em A e C a decisão é sombra |

Domínio de `indisponivel_motivo`: `nenhum item praticado corrigido`, `nenhum item do desafio
corrigido`, `sem respostas no desafio`, `sem item de transferência`, `nenhum item praticado`,
`acerto assistido zero`, `aguardando_rubrica` (projeto enviado e ainda não avaliado), e os
motivos do IIC, do gap e do viés, que repetem os de origem.

## Ida e volta

`ler_metricas` relê o arquivo de métricas e `medida_de` devolve a `Medida` de cada linha:
o valor volta como o mesmo `Decimal`, sem perda, porque a exportação não arredonda, e a
indisponibilidade volta como `Indisponivel` com o mesmo motivo, nunca como zero. O arquivo
de eventos não tem reimportação: ele é a cópia legível do registro, e a fonte continua o
banco.
