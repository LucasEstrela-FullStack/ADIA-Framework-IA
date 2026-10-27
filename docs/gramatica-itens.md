# Gramática dos arquivos de definição de item

Documento normativo da gramática dos arquivos `data/itens/*.adia.toml`. É a referência que
R3.1 e R3.2 citam: o carregador interpreta conforme esta gramática, e rejeita o arquivo que
a viole indicando caminho, linha e campo.

> **Estado deste documento.** As seis seções são normativas e correspondem ao que
> `backend/adia/nucleo/itens/` implementa: `modelo.py`, `erros.py` e a leitura de
> `carregador.py` na tarefa 3.2; `serializar_canonico` e `canonizar`, no mesmo
> `carregador.py`, na tarefa 3.3.
>
> O formato TOML e a existência de um serializador canônico são decisão de design (`D12`),
> ainda a transcrever para [`decisoes.md`](decisoes.md).

## 1. Formato e codificação do arquivo

TOML, **UTF-8 sem marca de ordem de bytes**, fim de linha `LF`. A marca de ordem de bytes é
recusada em vez de descartada: a escrita canônica não a produz, e aceitá-la na leitura faria
o arquivo mudar de bytes entre uma leitura e uma reescrita sem que o conteúdo mudasse — a
ida e volta de R3.5 deixaria de valer por um detalhe invisível na tela.

A leitura **tolera** `CRLF`, normalizando para `LF` antes de interpretar, porque a quebra de
linha do editor não é conteúdo do item; a escrita canônica emite sempre `LF` (DO-18).

Cada arquivo é autônomo e o banco de itens é a **união** dos arquivos do diretório. A carga é
**atômica**: nenhum item é publicado se algum arquivo falhar, e não existe modo "carregar o
que deu" (design §7.2). A razão não é rigor de estilo — o banco de itens é entrada de tudo o
que se mede, e um banco parcial produz TAI, TT, IIC e decisão de regulação descrevendo um
conjunto de itens diferente do que o protocolo descreve.

Estrutura de nível raiz, e nada mais:

| Construção | Significado |
| --- | --- |
| `[[item]]` | um item do banco (seção 2) |
| `[item.dicas]` | catálogo de dicas pré-escritas do item imediatamente acima (seção 3) |
| `[[relacao]]` | uma associação entre dois itens (seção 4) |

Qualquer outra chave de nível raiz é erro de gramática. Arquivo sem nenhum `[[item]]` e
nenhuma `[[relacao]]` também: arquivo vazio em `data/itens/` é indício de arquivo truncado,
não de conjunto vazio deliberado.

Nomes de campo são escritos **sem aspas** e, por consequência da própria sintaxe de TOML, só
admitem ASCII: `tolerância` com acento é recusado pelo interpretador, na linha em que
aparece. Acentuação é livre nos **valores** de texto — enunciado, dicas, unidade, sinônimos e
termos essenciais —, que é onde ela significa algo.

A gramática aceita as chaves em qualquer ordem, a cadeia de uma linha ou em bloco e a coleção
em qualquer ordem. A **forma canônica** — a escrita única que `adia itens formatar` produz e
de que R3.5 depende — está na seção 5.

## 2. Campos de um item

| Campo | Tipo em TOML | Obrigatório | Regra |
| --- | --- | --- | --- |
| `id` | cadeia | sim | de 1 a 64 caracteres ASCII entre letras, dígitos, `.`, `-` e `_`, começando por letra ou dígito; único em **todo** o conjunto de arquivos (R3.6) |
| `enunciado` | cadeia, em bloco `"""` quando multilinha | sim | texto não vazio |
| `habilidade_alvo` | cadeia | sim | mesma forma de `id` |
| `dificuldade` | inteiro | sim | de 1 a 5, escala ordinal (R2.1, `DO-01`) |
| `tamanho_max_resposta` | inteiro | sim | 1 ou mais, em caracteres |
| `tipo_gabarito` | cadeia | sim | `numerico`, `alternativa` ou `textual` |
| `gabarito` | cadeia | sim | texto não vazio |
| `tolerancia` | cadeia decimal | só em `numerico` | `[+-]?\d+(\.\d+)?`, valor **não negativo** (R2.8); proibida fora de `numerico` |
| `unidade` | cadeia | não | texto não vazio; ausência significa grandeza adimensional |
| `sinonimos_unidade` | lista de cadeias | não | conjunto; exige `unidade` declarada |
| `variacoes_gabarito` | lista de cadeias | não | conjunto de variações aceitas (R2.1) |
| `termos_essenciais` | lista de listas de cadeias | só em `textual` | conjunto de conjuntos, nenhum deles vazio (R2.11) |
| `incognita` | cadeia | não | mesma forma de `id`; nome da variável, para o detector algébrico da guarda |
| `etapas_permitidas` | lista de cadeias | sim | conjunto **não vazio** (R2.4) entre `linha_de_base`, `pratica_assistida`, `desafio_independente`, `gatilho_fading`, `projeto_steam`, `posteste` e `teste_retencao` |
| `transferencia` | booleano | não, padrão `false` | marca o item como item de transferência (seção 4) |
| `dicas` | subtabela `[item.dicas]` | sim | exatamente L1 a L4 (seção 3) |

Quatro regras valem para todos os campos, e cada uma fecha uma porta concreta.

**Chave desconhecida é erro, não campo ignorado.** `toleranica` com as letras trocadas, se
ignorado, produziria um item numérico **sem tolerância declarada** — perfil incompleto
apresentado como item válido. O carregador recusa a chave que a gramática não declara,
nomeando-a.

**Coleção é conjunto escrito como lista.** `sinonimos_unidade`, `variacoes_gabarito`,
`termos_essenciais` e `etapas_permitidas` não admitem repetição e são lidos em **ordem
crescente**, independentemente da ordem em que foram escritos. Ordem e tamanho estáveis são
o que sustenta a ida e volta de R3.4 e R3.5: repetição silenciosamente descartada mudaria o
tamanho entre uma leitura e a seguinte.

**`id` e `habilidade_alvo` são ASCII por decisão, não por limitação.** `habilidade_alvo` é
comparado por igualdade exata no pareamento isomórfico de R2.2, e `"equação"` escrito em NFC
e em NFD são cadeias **diferentes** com a mesma aparência na tela: o pareamento falharia sem
que nada no arquivo parecesse errado. Fechar o alfabeto elimina a classe inteira de defeito.

**Tolerância é cadeia decimal, nunca ponto flutuante de TOML.** O valor binário mais próximo
de `0.05` é `0,05000000000000000277…`, e a tolerância decide o acerto de item de fronteira
(R4.2) — que é exatamente o que separa acerto de erro na TAI. Escrever `tolerancia = 0.05`
sem aspas é erro de gramática, com mensagem que explica a razão.

## 3. Catálogo de dicas pré-escritas

```toml
[item.dicas]
L1 = """pergunta metacognitiva"""
L2 = """pista conceitual"""
L3 = """orientação procedural"""
L4 = """exemplo resolvido análogo"""
```

Exatamente quatro níveis, `L1` a `L4`, cada um com **uma** dica de texto não vazio (R2.1).
Nível ausente, nível declarado vazio e nível fora de L1 a L4 são todos recusados.

Dica declarada apenas com espaço em branco conta como **ausente**, e a razão é operacional: o
catálogo pré-escrito é a contingência de toda falha de geração (`D15`, R17.7) — quando a
guarda reprova o texto gerado, é a dica do mesmo nível que é entregue. Nível em branco é
assistência indisponível exatamente no momento em que a geração falhou.

Nenhuma dica pode revelar o gabarito. Essa verificação **não** é da gramática: é o conjunto
declarado da `Guarda_de_Vazamento`, que inclui as dicas de L1 a L4 de cada item e reprova o
*build* quando uma pré-escrita vaza (R7.11, design §6.5).

## 4. Declaração de isomorfismo estrutural

```toml
[[relacao]]
item_origem = "alg-eq-001"
item_destino = "alg-eq-002"
tipo = "equivalente"
```

`tipo` é `equivalente` — isomorfismo estrutural — ou `transferencia`. Ambos os
identificadores precisam corresponder a itens declarados no conjunto, e nenhum item se
relaciona consigo mesmo.

A direção é **informativa, não normativa**. Isomorfismo é simétrico por natureza e, em
`transferencia`, quem é o item de transferência está declarado no próprio item, pelo campo
`transferencia`. As verificações examinam o par nas duas direções; exigir uma ordem de
escrita criaria uma regra arbitrária cuja violação produziria a mensagem errada — "falta
equivalente" para um par que está declarado, só de trás para frente.

**No máximo uma relação por par de itens**, em qualquer direção. `equivalente` e
`transferencia` sobre a mesma dupla são afirmações contraditórias, e qual delas valeria
passaria a depender da ordem de leitura.

O que cada associação precisa cumprir:

| Associação | Qualifica quando o outro item… | Requisito |
| --- | --- | --- |
| `equivalente` | tem a **mesma** habilidade alvo, a **mesma** dificuldade, e identificador e enunciado **distintos** | R2.2 |
| `transferencia` | tem a mesma habilidade alvo e declara `transferencia = true` | R2.2 |

Todo item cujas `etapas_permitidas` incluem `pratica_assistida` precisa das **duas**
associações, e a recusa diz qual falta (R2.6). Relação declarada que não cumpre o critério
conta como **ausência**, nunca como pareamento parcial: um equivalente de dificuldade
diferente faria o desafio independente medir uma tarefa mais fácil que a praticada, e a
comparação entre assistido e independente deixaria de dizer o que diz.

Um item com `transferencia = true` **não** pode ser marcado como isomorfo a um item praticado
da mesma habilidade (R2.9). É a recusa mais silenciosa do catálogo: isomorfia transforma
transferência em repetição e infla a TT sem que nada pareça errado na tela.

## 5. Forma canônica e ida e volta

A gramática das seções 1 a 4 aceita **muitas** escritas do mesmo item: chaves em qualquer
ordem, cadeia de uma linha ou em bloco, coleção em qualquer ordem, `0.05` e `0.050`. A forma
canônica escolhe **uma** delas, e é essa escolha que torna verdadeira a exigência mais dura
de R3.5 — serializar, interpretar e serializar de novo produz **texto idêntico**.

Não é preferência de estilo. O banco de itens é revisado em texto e versionado, e duas
escritas do mesmo conteúdo produzem diferença de `git` sem mudança de conteúdo, o que torna
impossível separar a revisão do conteúdo do ruído de formatação. `adia itens formatar` grava
a forma canônica; `adia itens validar` aceita qualquer escrita que a gramática admita.

### 5.1 Disposição do arquivo

| Aspecto | Forma canônica |
| --- | --- |
| Codificação e fim de linha | UTF-8 **sem** BOM, `LF`, uma única quebra de linha no fim do arquivo |
| Ordem dos blocos | todos os `[[item]]` por `id` crescente, depois todos os `[[relacao]]` pela tripla `(origem, destino, tipo)` |
| Linha em branco | exatamente **uma** antes de cada cabeçalho de tabela, nenhuma no começo do arquivo e nenhuma em qualquer outro lugar |
| Comentário | **não** é preservado na reescrita (ver 5.4) |

### 5.2 Ordem das chaves de um item

Fixada pelo esquema, na ordem da tabela da seção 2, e **não** alfabética nem a ordem em que
o autor escreveu:

```
id, enunciado, habilidade_alvo, dificuldade, tamanho_max_resposta, tipo_gabarito,
gabarito, tolerancia, unidade, sinonimos_unidade, variacoes_gabarito,
termos_essenciais, incognita, etapas_permitidas, transferencia
```

seguida da subtabela `[item.dicas]` com `L1`, `L2`, `L3` e `L4` nessa ordem. Em `[[relacao]]`:
`item_origem`, `item_destino`, `tipo`.

As duas alternativas foram descartadas por motivos diferentes. A ordem alfabética separaria
`gabarito` de `tolerancia` e `unidade` de `sinonimos_unidade`, que são os pares que um revisor
lê juntos. A ordem de escrita faria o texto do arquivo depender de como o objeto foi
construído em memória, que é exatamente o que R3.5 proíbe.

### 5.3 Escrita de cada valor

| Construção | Forma canônica | Por quê |
| --- | --- | --- |
| `enunciado` e cada dica | bloco `"""`, **sempre**, inclusive com uma linha só | "bloco quando multilinha" seriam duas formas para o mesmo conteúdo |
| Demais cadeias | cadeia básica de uma linha, `"..."`, com escape padrão de TOML | — |
| `tolerancia` | cadeia decimal na forma mais curta que preserva o valor, em notação simples: `"0.050"` sai `"0.05"`, `1E+2` sai `"100"`, zero sai `"0"` | a gramática não admite expoente (seção 2), e arredondar mudaria o acerto de item de fronteira (R4.2) |
| Coleção | lista **em linha**, ordem crescente, sem repetição | é conjunto escrito como lista; a ordem de escrita não é conteúdo |
| `termos_essenciais` | lista de listas, canônica nos dois níveis | idem, em dois níveis |
| Campo opcional ausente | **omitido** — TOML não tem nulo | — |
| Coleção vazia | **omitida**, porque a leitura trata ausência e lista vazia como a mesma coisa | `sinonimos_unidade = []` seria a segunda forma de uma ausência |
| `transferencia` | escrito **sempre**, inclusive `false` | decide se o item conta na TT (R2.9); num arquivo que vai a revisão humana, o silêncio não é a melhor escrita do valor padrão |

O bloco tem duas sutilezas de TOML, e as duas existem para que o texto volte exatamente como
entrou. A quebra de linha imediatamente após o delimitador de abertura é descartada pela
especificação, e emiti-la sempre é o que deixa o conteúdo começar na linha de baixo sem ganhar
um `\n` que ninguém escreveu. E a **barra invertida no fim da última linha de conteúdo**
descarta a quebra seguinte: sem ela, todo valor voltaria com um `\n` a mais no fim — o defeito
mais fácil de não notar numa ida e volta, porque a tela mostra o mesmo texto. Ela também separa
o conteúdo do delimitador de fechamento, de modo que um enunciado terminado em aspas não
forme `"""`.

```toml
[[item]]
id = "alg-eq-001"
enunciado = """
Resolva a equação 2x + 3 = 11 e informe o valor de x.\
"""
habilidade_alvo = "equacao_linear"
dificuldade = 2
tamanho_max_resposta = 120
tipo_gabarito = "numerico"
gabarito = "4"
tolerancia = "0.05"
variacoes_gabarito = ["4", "quatro"]
incognita = "x"
etapas_permitidas = ["linha_de_base", "pratica_assistida"]
transferencia = false

[item.dicas]
L1 = """
O que a igualdade afirma sobre os dois lados?\
"""
```

Dentro do bloco, a quebra de linha e a tabulação ficam **literais** — é o que faz valer a pena
escrever enunciado em bloco num arquivo editado à mão. São escapados: a barra invertida,
sempre; a **terceira** aspa de uma sequência, porque três aspas seguidas fechariam o bloco no
meio do texto; e os demais caracteres de controle, por nome curto quando têm um e por `\uXXXX`
quando não têm. Escapar só a terceira aspa, e não toda aspa, mantém legível o caso comum, que
é texto em pt-BR com uma citação.

### 5.4 O que a ida e volta preserva, e o que não preserva

R3.4 e R3.5 são afirmações sobre **conteúdo de item**, em dois sentidos:

- **R3.4, ida e volta de objeto:** interpretar, serializar e interpretar de novo devolve o
  mesmo conjunto de itens, comparado por **estrutura** e não por texto. É a Propriedade 29;
- **R3.5, estabilidade do texto:** serializar, interpretar e serializar de novo devolve texto
  **idêntico**, byte a byte. É a Propriedade 30.

Três coisas, portanto, **não** sobrevivem a `adia itens formatar`, e nenhuma delas é conteúdo
de item: comentários, a ordem em que as chaves e as coleções foram escritas, e a partição de
um item entre arquivos — um item permanece no arquivo em que foi declarado, mas a disposição
interna do arquivo é reescrita por inteiro. Quem precisa registrar a razão de uma escolha de
conteúdo registra em [`decisoes.md`](decisoes.md), não em comentário de arquivo de item.

A reescrita **preserva a partição de arquivos**: a validação é do conjunto, porque as
associações de R2.2 e R2.6 e o conflito de R2.9 cruzam arquivos, mas a gravação é arquivo por
arquivo. Colapsar o banco num arquivo único passaria em R3.5 e destruiria a organização do
conteúdo, que é o que R3 existe para proteger.

## 6. Erros de gramática

Toda mensagem traz **caminho do arquivo, linha e campo** (R3.2), no formato
`arquivo:linha: campo \`nome\`: motivo`.

| Gatilho | Erro | Campo relatado | Requisito |
| --- | --- | --- | --- |
| Sintaxe de TOML inválida, codificação inválida, marca de ordem de bytes, arquivo ilegível | `ErroDeGramatica` | `arquivo` | R3.2 |
| Chave desconhecida, tipo inesperado, campo obrigatório ausente, valor fora do vocabulário, repetição em coleção, relação apontando para item inexistente, par com mais de uma relação | `ErroDeGramatica` | o campo em questão | R3.2 |
| `id` repetido entre itens | `ErroDeIdentificadorDuplicado` | `id` | R3.6 |
| Item praticado sem equivalente **ou** sem transferência válida | `ErroDeAssociacaoAusente` | `relacao.equivalente` ou `relacao.transferencia` | R2.6 |
| Item de transferência isomorfo a item praticado da mesma habilidade | `ErroDeConflitoDeRelacao` | `relacao.equivalente` | R2.9 |
| `numerico` sem `tolerancia` | `ErroDePerfilIncompleto` | `tolerancia` | R2.8, R7.6 |
| `textual` sem `termos_essenciais` | `ErroDePerfilIncompleto` | `termos_essenciais` | R2.11, R7.6 |
| `etapas_permitidas` vazio ou ausente | `ErroDeEtapasVazias` | `etapas_permitidas` | R2.4 |
| Dica faltando ou vazia em qualquer nível de L1 a L4 | `ErroDeDicaAusente` | `dicas.L1` … `dicas.L4` | R2.1 |
| `dificuldade` fora de 1 a 5, `tamanho_max_resposta` não positivo, `tolerancia` negativa | `ErroDeFaixa` | o campo em questão | R2.1, R2.8 |

**Precisão da linha.** Quando o campo existe no texto, a linha é a dele, inclusive dentro de
enunciados e dicas escritos em bloco. Quando o campo está **ausente**, não existe linha a
apontar e o erro aponta a construção que deveria contê-lo — o cabeçalho `[item.dicas]` para
um nível de dica que falta, o cabeçalho `[[item]]` para um campo de item que falta. É
aproximação declarada, não precisão fingida. Uma única falha fica sem linha: arquivo
inexistente ou ilegível, onde não há texto para localizar.

**Ordem das verificações.** Fixa, para que o mesmo conjunto de arquivos produza sempre a
**mesma** primeira rejeição: por arquivo, na ordem recebida — leitura, sintaxe, estrutura da
raiz, cada item na ordem de declaração com os campos em ordem fixa, identificador duplicado,
depois cada relação; e, com todos os arquivos lidos, integridade das relações, associações de
R2.2 e R2.6 e conflito de R2.9. Reprodutibilidade de diagnóstico vale tanto quanto
reprodutibilidade de métrica.

**Nenhuma mensagem de erro cita conteúdo.** `gabarito`, `variacoes_gabarito`,
`termos_essenciais`, `enunciado` e texto de dica nunca são interpolados: no lugar do valor
entra `<omitido: campo de conteúdo>`. A razão é concreta — a mensagem vai para o terminal de
quem roda `adia itens validar`, para o log de subida da API e, no pior caso, para uma captura
de tela em sala. Gabarito ali é vazamento por outro caminho, o mesmo que a
`Guarda_de_Vazamento` fecha no texto da dica. A regra é mecânica, e não disciplinar: há um
único caminho no código para pôr um valor lido em mensagem, e ele omite o valor nesses cinco
campos.
