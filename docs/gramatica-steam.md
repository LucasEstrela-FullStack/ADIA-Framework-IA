# Gramática dos arquivos de cenário STEAM e de rubrica

Documento normativo da gramática dos arquivos `data/steam/*.adia.toml`: o **cenário** do
projeto STEAM, suas **partes numéricas** de correção automática, a **justificativa** pedida ao
estudante e a **rubrica versionada** com que o professor a avalia. É a referência de R13.1 a
R13.4.

> **Estado deste documento.** O formato é decidido aqui, pela tarefa 3.14, junto com o
> conteúdo que o cumpre. O **carregador** de cenários STEAM — com a recusa que nomeia caminho,
> linha e campo, como faz o de itens — é de tarefa posterior, e não existe `adia steam
> validar`. Enquanto ele não existe, quem verifica estas seções é
> [`backend/tests/conjuntos/test_cenario_steam_inicial.py`](../backend/tests/conjuntos/test_cenario_steam_inicial.py),
> que interpreta os arquivos reais no portão. As decisões de formato tomadas aqui ainda estão
> a transcrever para [`decisoes.md`](decisoes.md).
>
> Este documento existe pela mesma razão que [`gramatica-itens.md`](gramatica-itens.md): o
> conteúdo é revisado em texto por quem não escreveu o código, e um formato que vive só na
> cabeça de quem escreveu o primeiro arquivo é um formato que o segundo arquivo viola sem que
> ninguém note.

## 1. Formato e codificação do arquivo

**TOML**, UTF-8 **sem marca de ordem de bytes**, fim de linha `LF`, uma quebra de linha no fim
do arquivo. É o formato dos arquivos de item, pelos mesmos motivos de `D12` — revisável em
texto, versionável, interpretador na biblioteca padrão — e a escolha de repeti-lo é
deliberada: conteúdo com duas gramáticas é conteúdo com dois lugares para errar, e quem revisa
uma dica e um nível de rubrica no mesmo dia não devia ter de trocar de notação no caminho. O
repositório declara `* text=auto eol=lf`, e o `LF` aqui é o que impede o primeiro `checkout`
em outra máquina de produzir diferença em todas as linhas.

Cada arquivo é autônomo e o conteúdo STEAM é a **união** dos arquivos do diretório. Estrutura
de nível raiz, e nada mais:

| Construção | Significado |
| --- | --- |
| `[[cenario]]` | um cenário do projeto STEAM (seção 2) |
| `[[cenario.partes_numericas]]` | uma parte numérica do cenário imediatamente acima (seção 3) |
| `[cenario.justificativa]` | a justificativa pedida pelo cenário imediatamente acima (seção 4) |
| `[[rubrica]]` | uma rubrica versionada (seção 5) |

Qualquer outra chave de nível raiz é erro de gramática, pela razão da seção 1 da gramática de
itens: `rubrcia` com as letras trocadas, se fosse ignorado, produziria um arquivo que carrega
**sem** a rubrica que ele existe para declarar.

Nomes de campo são ASCII sem aspas, por consequência da sintaxe de TOML. Acentuação é livre
nos **valores** de texto — título, enunciado, pergunta, descrição de critério e de nível —, que
é onde ela significa algo, e o conteúdo é escrito em pt-BR com acentuação.

**Identificadores são ASCII, sem espaço**: `id`, `habilidade_alvo`, `areas`, `parte`,
`rubrica_id`, `criterio` e `nivel`. A razão é a de `DO-23` e vale com força particular em
`habilidade_alvo`, que é comparado por **igualdade exata** na liberação de R13.1: `"equação"`
escrito em NFC e em NFD são cadeias diferentes com a mesma aparência na tela, e a liberação
falharia sem que nada no arquivo parecesse errado.

**Número é cadeia decimal, nunca ponto flutuante de TOML.** `gabarito` e `tolerancia` são
escritos como cadeia, na forma `[+-]?\d+(\.\d+)?` — dígitos, ponto como separador decimal, sem
expoente. A razão é a mesma de R4.2 e está registrada em `DO-23`: o valor binário mais próximo
de `0.05` é `0,05000000000000000277…`, e a tolerância decide o acerto de parte de fronteira.
`pontos`, na rubrica, é **inteiro** de TOML, porque inteiro de TOML é exato e a razão da cadeia
decimal não se aplica a ele.

Dois limites de notação vêm de `interpretar_decimal` do `Motor_de_Correção`, que é quem lê
esses valores em tempo de correção (§3.11, R13.2). Notação científica não é número para ele, e
um separador **único** é lido como **separador decimal** — de modo que `1.500` vale um e meio,
e não mil e quinhentos. Mil e quinhentos se escreve `1500`.

Não há comentário nos arquivos de conteúdo. É a convenção da seção 5.4 da gramática de itens:
quem precisa registrar a razão de uma escolha de conteúdo registra em
[`decisoes.md`](decisoes.md), não em comentário que a reescrita canônica descarta.

## 2. Campos de um cenário

| Campo | Tipo em TOML | Obrigatório | Regra |
| --- | --- | --- | --- |
| `id` | cadeia | sim | identificador, único entre todos os cenários do diretório |
| `titulo` | cadeia | sim | texto não vazio; é o que aparece na lista do painel |
| `habilidade_alvo` | cadeia | sim | identificador; precisa coincidir com a `habilidade_alvo` de algum item de `data/itens/` (R13.1) |
| `areas` | lista de cadeias | sim | identificadores, conjunto não vazio; as áreas que o cenário cruza |
| `enunciado` | cadeia em bloco `"""` | sim | a situação, com **todos** os dados que as partes usam |
| `partes_numericas` | `[[cenario.partes_numericas]]` | sim | de 3 a 5 partes (seção 3) |
| `justificativa` | `[cenario.justificativa]` | sim | exatamente uma (seção 4) |

**`habilidade_alvo` tem de existir no banco de itens.** R13.1 libera o projeto STEAM associado
à habilidade alvo **da sessão**, e a associação é por igualdade exata. Cenário apontando para
habilidade que nenhum item cobre nunca é liberado por sessão alguma; pior, um cenário cuja
habilidade é parecida mas não igual à praticada seria liberado e a pontuação de R13.7 deixaria
de medir transferência do que foi praticado.

**`areas` é obrigatório porque a interdisciplinaridade é definidora.** O glossário define o
projeto STEAM como tarefa **interdisciplinar** de transferência ecológica. Declarar as áreas
torna isso auditável; deixá-las implícitas na prosa do enunciado torna "é interdisciplinar"
uma impressão de quem leu.

**Três campos de item que o cenário deliberadamente não tem**, e a razão de cada ausência:

- **`dicas`**. O catálogo pré-escrito de L1 a L4 é exigência de R2.1 sobre **item**, e existe
  como contingência de falha de geração no laço de assistência. R13 não declara catálogo de
  dica para o projeto STEAM, e inventá-lo aqui acrescentaria superfície de vazamento a um
  conteúdo cujo propósito é medir transferência;
- **`teto_steam`**. O teto vigente é **decisão de regulação** (R9, R14), não conteúdo: o evento
  `steam_submetido` registra o teto que estava em vigor na submissão (§4.4). Declará-lo no
  arquivo faria o conteúdo decidir o que a regra decide;
- **`etapas_permitidas`**. O cenário **é** a etapa `projeto_steam`; o campo existe em item
  porque um item precisa dizer em quais das sete etapas pode aparecer.

## 3. Partes numéricas

```toml
[[cenario.partes_numericas]]
parte = "retirada_diaria_total"
pergunta = """
...\
"""
unidade = "litros"
sinonimos_unidade = ["L", "litro"]
gabarito = "620"
tolerancia = "0"
variacoes_gabarito = ["620", "seiscentos e vinte"]
tamanho_max_resposta = 40
```

| Campo | Tipo em TOML | Obrigatório | Regra |
| --- | --- | --- | --- |
| `parte` | cadeia | sim | identificador, único **no cenário** |
| `pergunta` | cadeia em bloco | sim | o que se pede, respondível com os dados do enunciado |
| `gabarito` | cadeia decimal | sim | forma de dados; legível por `interpretar_decimal` |
| `tolerancia` | cadeia decimal | sim | não negativa; é a tolerância que R13.2 manda aplicar |
| `variacoes_gabarito` | lista de cadeias | sim | formas aceitas, inclusive o próprio gabarito |
| `unidade` | cadeia | não | ausência significa grandeza adimensional |
| `sinonimos_unidade` | lista de cadeias | não | exige `unidade` declarada |
| `tamanho_max_resposta` | inteiro | sim | 1 ou mais, em caracteres |

**Os nomes dos campos são os do evento.** `steam_submetido` carrega `partes_numericas` na
forma `[{parte, valor, resultado, tolerancia}]` (§4.4): `parte` e `tolerancia` se escrevem
aqui com o mesmo nome que terão no registro, de modo que o identificador que o professor lê no
arquivo é o mesmo que aparece na exportação. Um termo por conceito.

**De 3 a 5 partes.** Menos de três não distingue acerto parcial de acerto total — a pontuação
de R13.7 passaria a ter poucos valores possíveis e deixaria de discriminar —, e mais de cinco
transforma o projeto de transferência em lista de exercícios, que é exatamente o que ele não
é.

**Identificador de parte é único no cenário** porque é a chave pela qual o resultado de cada
parte é registrado. Dois iguais fariam o registro de um sobrescrever o do outro, e a pontuação
contaria menos partes do que o estudante respondeu.

**Tolerância por parte, e não por cenário.** R13.2 fala das tolerâncias declaradas **em cada
parte**, e a razão é de conteúdo: uma parte de soma e produto de inteiros não tem arredondamento
a absorver e declara `"0"`, enquanto uma parte com divisão ou com valor em reais declara folga
para o centavo. Tolerância única de cenário obrigaria a maior folga a valer para a parte mais
exata.

**Numeral em palavras entre as formas aceitas.** Foi a convenção adotada no banco de itens, e
vale aqui pela mesma razão, que não é de correção, mas de **varredura de vazamento**: declarar
`seiscentos e vinte` ao lado de `620` é o que faz a varredura cobrir o numeral escrito em
palavras, que R7.2 manda detectar. Gabarito **inteiro** declara o numeral em palavras;
gabarito decimal fica de fora porque não tem grafia única em palavras — "cento e um reais e
quarenta centavos" é uma entre várias.

**As partes não encadeiam.** Cada parte é respondível a partir do enunciado, e nenhuma usa
como dado a resposta de outra. Encadear puniria duas vezes o mesmo erro e, pior, obrigaria a
pergunta de uma parte a citar o resultado de outra — que é vazamento pelo caminho mais curto.

### 3.1 Derivação das respostas do cenário `steam-eq-001`

Registrada aqui, e não no arquivo de conteúdo, porque o arquivo é apresentado ao estudante. É
o que sustenta a aritmética das partes: o teste de conjunto não a verifica, porque conferi-la
exigiria reimplementar o modelo da situação no teste, e o teste passaria a verificar a própria
cópia.

| Parte | Expressão | Tolerância e por quê |
| --- | --- | --- |
| `retirada_diaria_total` | `80 + 15 × 36` | `"0"`: soma e produto de inteiros, sem arredondamento a absorver |
| `metros_dentro_do_limite` | `(350 − 80) ÷ 15` | `"0.05"`: há divisão no caminho |
| `chuva_semanal_necessaria` | `350 × 7 ÷ 175` | `"0.05"`: há divisão no caminho |
| `economia_mensal` | `(12000 ÷ 1000) × 8,45` | `"0.05"`: valor em reais, absorve o centavo de arredondamento |

**Nenhuma dessas respostas é um número que o enunciado informe**, e nenhum numeral de uma
palavra escrito no texto (`cinco`, `uma`) é resposta de parte alguma. É a metade estrutural da
proibição da seção 6: a varredura textual pega o gabarito escrito, e esta separação é o que
fecha o que a varredura não alcança.

## 4. Justificativa

```toml
[cenario.justificativa]
pergunta = """
...\
"""
tamanho_max_resposta = 2000
rubrica_id = "rub-modelagem-ecologica"
rubrica_versao = 1
```

| Campo | Tipo em TOML | Obrigatório | Regra |
| --- | --- | --- | --- |
| `pergunta` | cadeia em bloco | sim | o que a justificativa deve argumentar |
| `tamanho_max_resposta` | inteiro | sim | 1 ou mais, em caracteres |
| `rubrica_id` | cadeia | sim | identificador de rubrica declarada em `data/steam/` |
| `rubrica_versao` | inteiro | sim | positivo; versão **exata** daquela rubrica |

Exatamente uma justificativa por cenário: R13.3 fala de "a justificativa", e é ela que o
`Gestor_de_Sessão` encaminha ao `Painel_do_Professor`.

**A referência à rubrica mora aqui, e não no cabeçalho do cenário**, porque é a justificativa
— e só ela — que vai à avaliação por rubrica. As partes numéricas são corrigidas
automaticamente por R13.2 e não recebem nota de rubrica.

**A versão é fixada pelo cenário.** `avaliacao_rubrica` tem
`UNIQUE (submissao_id, avaliador_id, rubrica_versao)` e `CHECK (rubrica_versao > 0)` (§4.3):
a versão é parte da identidade da avaliação registrada. Fixá-la no cenário custa editar o
cenário quando a rubrica muda, e é o preço certo — o par cenário/rubrica fica reproduzível, e
duas coletas com o mesmo cenário não acabam pontuadas por rubricas diferentes sem que nada no
registro diga isso.

**A pergunta diz o que argumentar, critério por critério.** Toda exigência da rubrica aparece
pedida no texto da justificativa. Rubrica que pontua o que não foi pedido é rubrica que pune o
estudante por não adivinhar.

## 5. Rubrica versionada

```toml
[[rubrica]]
rubrica_id = "rub-modelagem-ecologica"
rubrica_versao = 1
titulo = "..."
criterios_total = 4
descricao = """
...\
"""

[[rubrica.criterio]]
criterio = "adequacao_do_modelo"
descricao = """
...\
"""

[[rubrica.criterio.nivel]]
nivel = "ausente"
pontos = 0
descricao = """
...\
"""
```

| Campo | Tipo em TOML | Obrigatório | Regra |
| --- | --- | --- | --- |
| `rubrica_id` | cadeia | sim | identificador; o par com a versão é único no diretório |
| `rubrica_versao` | inteiro | sim | **positivo** |
| `titulo` | cadeia | sim | texto não vazio |
| `criterios_total` | inteiro | sim | igual ao número de `[[rubrica.criterio]]` declarados |
| `descricao` | cadeia em bloco | sim | o que a rubrica avalia, e o que ela não avalia |
| `criterio` | `[[rubrica.criterio]]` | sim | 2 ou mais |

Em cada critério: `criterio` (identificador, único na rubrica), `descricao` (texto em bloco) e
2 ou mais `[[rubrica.criterio.nivel]]`. Em cada nível: `nivel` (identificador, único no
critério), `pontos` (inteiro não negativo) e `descricao` (texto em bloco).

**Os nomes são os do registro.** A coluna `pontuacoes` de `avaliacao_rubrica` guarda JSON na
forma `[{criterio, nivel, pontos}]` (§4.3). As três chaves se escrevem aqui com esses nomes,
de modo que o que o professor pontua, o que o arquivo declara e o que o banco grava se chamam
a mesma coisa.

**`criterios_total` é declarado, apesar de ser contável.** Ele vai para a coluna de mesmo nome,
e é com ele que `CHECK (concluida = 0 OR criterios_pontuados = criterios_total)` decide se a
avaliação pode concluir — que é R13.4 em forma de restrição. Escrito **e** conferido contra a
contagem real, ele pega o critério apagado do arquivo sem o total ser corrigido, que faria a
avaliação concluir com um critério não pontuado.

**Pontos crescentes e distintos por critério.** Dois níveis valendo o mesmo não distinguem
desempenho nenhum; escala invertida num arquivo escrito à mão é erro de transcrição que nada
mais pegaria, e a pontuação registrada premiaria o pior nível.

**A rubrica não declara habilidade alvo.** Os critérios são sobre qualidade de **modelagem** —
traduzir a situação, ler o resultado de volta nela, dizer o que foi assumido, recomendar uma
providência —, e isso vale para qualquer cenário cuja justificativa peça essas coisas. A
ligação com a habilidade é do cenário, que aponta a rubrica pelo identificador e pela versão.
Declará-la na rubrica criaria uma segunda fonte para a mesma afirmação, e as duas poderiam
divergir.

**Versionar é acrescentar bloco, não editar texto.** Mudar critério, nível ou pontuação de uma
rubrica já usada numa coleta invalidaria avaliações registradas: as pontuações gravadas
apontariam para critérios que não existem mais. A rubrica nova entra como outro `[[rubrica]]`
com `rubrica_versao` maior, e o cenário passa a apontar para ela quando o professor decidir.
Correção de erro de digitação em descrição é o único reparo que não exige versão nova, porque
não muda o que se pontua.

## 6. O que nenhum texto pode conter

**Nenhum texto de `data/steam/` reproduz o gabarito de nenhuma parte numérica.** Vale para o
`enunciado` e a `pergunta` de cada parte, que vão ao **estudante**; vale para o `titulo` e toda
`descricao` da rubrica, que vão ao **professor**; e vale para os identificadores, porque uma
parte chamada `litros_620` vazaria tanto quanto uma frase.

A varredura está em `test_cenario_steam_inicial.py` e compara como a do banco de itens:
insensível a caixa e a acentuação, exigindo **token delimitado** — com gabarito `14`, as
formas `14` e `14,0` reprovam, e `1400` não. A forma de comparação é compartilhada pelos dois
conjuntos declarados, em `backend/tests/conjuntos/vazamento.py`, de propósito: duas cópias
seriam dois lugares para errar, e fortalecer uma deixaria a outra varrendo por critério mais
fraco sem que nada ficasse vermelho.

Dois cuidados de escrita que a varredura não substitui:

- **gabarito `1` e `2` são evitados.** "um", "uma", "dois" e "os dois" aparecem naturalmente em
  pt-BR, e R7.2 manda detectar o numeral escrito em palavras: um gabarito desses faria a
  varredura reprovar frases legítimas, ou — se afrouxada para aceitá-las — deixaria de cobrir
  o numeral em palavras. Na primeira metade desta tarefa uma dica foi reescrita por exatamente
  isso: "os dois lados" reproduzia o gabarito `2`;
- **descrição de nível é qualitativa.** "Identificou corretamente que o valor é tal" entrega a
  resposta a quem lê a rubrica. O que a descrição de nível descreve é a **qualidade** do
  argumento, nunca o número que o argumento alcança.

O que a varredura textual **não** alcança, e é honesto registrar: numeral de mais de uma
palavra só reprova quando o texto traz a expressão completa, e nenhuma varredura separa o
gabarito de um item do banco de um número qualquer do cenário — gabaritos de uma casa colidem
com os dígitos de qualquer situação realista. O que fecha esse lado é a separação estrutural
da seção 3.1.
