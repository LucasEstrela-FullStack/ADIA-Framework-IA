# Gramática dos arquivos de definição de item

Documento normativo da gramática dos arquivos `data/itens/*.adia.toml`. É a referência que
R3.1 e R3.2 citam: o carregador interpreta conforme esta gramática, e rejeita o arquivo que
a viole indicando caminho, linha e campo.

> **Estado deste documento: esqueleto.** As seções abaixo estão previstas e vazias. O
> conteúdo é produzido pela tarefa que implementa o modelo de item, o carregador TOML e o
> serializador canônico, em `backend/adia/nucleo/itens/`. Esta tarefa (1.1) apenas fixa a
> estrutura e o destino, para que nenhuma parte da gramática seja decidida em código sem
> deixar registro aqui.
>
> O formato TOML e a existência de um serializador canônico são decisão de design (`D12`),
> ainda a transcrever para [`decisoes.md`](decisoes.md).

## 1. Formato e codificação do arquivo

Previsto: TOML, UTF-8 sem marca de ordem de bytes, fim de linha `LF`. A forma canônica
exata — ordem de chaves, estilo de cadeia e tratamento de linhas em branco — é o que
sustenta a ida e volta de R3.5 e entra aqui.

*A preencher.*

## 2. Campos de um item

Previsto: a tabela campo a campo, com nome, tipo, obrigatoriedade e regra de validação, para
identificador, enunciado, gabarito, variações aceitas de gabarito, habilidade alvo,
dificuldade, tamanho máximo de resposta, tipo de gabarito, tolerância numérica e conjuntos
de termos essenciais.

Já fixado: **dificuldade é inteiro de 1 a 5**, escala ordinal — ver `DO-01` em
[`decisoes.md`](decisoes.md).

*A preencher.*

## 3. Catálogo de dicas pré-escritas

Previsto: a estrutura das quatro dicas obrigatórias por item, uma para cada nível de L1 a
L4, e as regras de validação que R2.1 impõe sobre esse conjunto.

*A preencher.*

## 4. Declaração de isomorfismo estrutural

Previsto: como um item declara seu par isomórfico e quais campos precisam coincidir para que
o par seja aceito.

*A preencher.*

## 5. Forma canônica e ida e volta

Previsto: a especificação da serialização canônica que torna verdadeira a exigência mais
dura de R3.5 — serializar, interpretar e serializar de novo produz **texto idêntico** — e a
sua relação com a equivalência de objetos de R3.4.

*A preencher.*

## 6. Erros de gramática

Previsto: o catálogo de violações, cada uma com a mensagem correspondente. R3.2 exige
caminho do arquivo, linha e campo inválido em toda mensagem. Nenhuma mensagem de erro pode
interpolar gabarito, variação de gabarito ou termo essencial.

*A preencher.*
