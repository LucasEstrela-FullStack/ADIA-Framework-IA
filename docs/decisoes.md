# Registro de decisões — ADIA-CognitiveLoop

Registro rastreável das decisões do protótipo. Existe porque vários requisitos nomeiam
este arquivo como destino obrigatório: um valor operacional que não está aqui é um valor
que ninguém pode auditar depois.

## Como ler este registro

Duas famílias de identificador, com significados distintos:

- **`D6` a `D14`** — decisões de design, com contexto, escolha, justificativa e
  alternativas rejeitadas desenvolvidos na seção `Overview` do documento de design.
  Aqui entram em forma resumida, com o ponteiro para o original.
- **`DO-NN`** — decisões **operacionais**: valores que o `README.md` não fixa e que o
  design precisou escolher para que o software fosse implementável. São as marcadas no
  design como *decisão operacional a registrar em `docs/decisoes.md`*.

Cada entrada traz: identificador, data, decisão adotada, justificativa, a origem que a
exige (requisito ou seção do design) e, quando houver, o gatilho de revalidação.

Convenção numérica: **vírgula** como separador decimal no texto em prosa; **ponto** em
código, em arquivos de configuração e nas exportações CSV.

> **Nota de escopo.** `DO-01` a `DO-14` são a entrega da tarefa 1.1 da Fase 0: as decisões
> operacionais já fixadas no design cujo valor não depende de nenhum código ainda escrito.
> `D6`, `D7` e `DO-15` vieram da tarefa 1.2, com a fixação de versões de linguagem,
> gerenciadores e dependências. `DO-16` veio da tarefa 1.3, com o esqueleto da CLI e o
> comando `adia doutor`. `DO-17` veio da tarefa 1.4, com a triagem de dependências que
> exigem rede. `DO-18` a `DO-20` vieram das correções de fim da Fase 0.
>
> `D12` e `DO-21` a `DO-36` são da **Fase 1**, do núcleo determinístico de itens: as
> tarefas 3.2 a 3.7 produziram a gramática e a forma canônica dos arquivos de item, a
> configuração dos testes de propriedade, os geradores compartilhados e o
> `Banco_de_Itens`. Diferente das anteriores, boa parte destas **não** estava prevista no
> design como decisão a registrar: elas apareceram ao implementar, e três delas
> ([DO-25](#do-25--canonizar-preserva-a-partição-de-arquivos),
> [DO-30](#do-30--errodeitemdesconhecido-como-terceiro-tipo-de-retorno) e
> [DO-31](#do-31--semente-injetada-no-construtor-nunca-gerador-com-estado)) registram
> divergência em relação ao contrato de §3.1 que o design precisa absorver.
>
> As demais estão na seção [Pendências](#pendências), cada
> uma com a tarefa que a produz. Nenhum valor foi inventado aqui: todos vêm do design ou
> dos requisitos, com a origem citada, e o que foi medido nesta máquina traz o comando que
> produziu a medida.

---

## D6 — Versão de Python: 3.13

- **Data:** 2026-10-25
- **Decisão:** `requires-python = ">=3.13,<3.14"` em `pyproject.toml` e `3.13` em
  `.python-version` — a mesma versão nos dois arquivos, com precisão `maior.menor`. O
  ambiente é provisionado por `uv` em `.venv` dentro do diretório do projeto, e a
  instalação de Python do sistema permanece inalterada. É **uma** versão menor abaixo do
  3.14 indicado no `README.md`, dentro do limite de [DO-15](#do-15--limite-de-retrocesso-de-versão-de-python-duas-versões-menores).
- **Justificativa:** o design §1.5 fixou 3.13 porque a cobertura de rodas binárias `cp314`
  do `torch` para Windows em CPU — dependência obrigatória do `Modelo_DKT` (R28.1, R28.2) —
  não estava verificada, e `pip` sem roda binária cai para compilação a partir do código
  fonte, que falha em Windows sem as ferramentas de compilação da Microsoft. A verificação
  desta tarefa mostra que **esse impedimento já não existe** (ver abaixo). O que sustenta
  3.13 hoje é outra razão, mais fraca mas verdadeira: 3.13.14 é o interpretador auditado na
  máquina de desenvolvimento, e usar o interpretador auditado elimina uma variável de
  reprodutibilidade entre o que foi medido no design §2.5 e o que roda na coleta.
- **Dependências bloqueadoras (R1.4):** **nenhuma**, na verificação de 2026-10-25. Nenhum
  retrocesso foi necessário: 3.13 foi adotado por escolha de reprodutibilidade, não por
  incompatibilidade.
- **Verificação executada:** `uv lock` e `uv sync` com a lista obrigatória completa sob
  3.13 resolveram 55 pacotes e instalaram 46, sem erro; `uv run python --version` reporta
  3.13.14. Para medir o 3.14, as 15 dependências diretas foram resolvidas com
  `uv pip compile --python-version 3.14 --python-platform windows --only-binary :all:`,
  que recusa compilação a partir do código fonte e portanto só passa se houver roda
  binária `cp314`: resolveu 54 pacotes, `torch==2.14.1` entre eles. O método foi
  controlado contra `numpy==1.26.4`, que a mesma verificação reprova com
  *no usable wheels* — ou seja, a verificação detecta ausência de roda quando ela ocorre.
- **Origem:** R1.2, R1.3, R1.4, R1.10; design §1.5 (D6) e o portão de verificação da Fase 0.
- **Revalidação:** o gatilho previsto no design — "quando todas as dependências
  obrigatórias publicarem rodas `cp314`, reavaliar a subida" — **já disparou**. Subir para
  3.14 passou a ser decisão do autor, não remoção de impedimento, e custa reauditar o
  interpretador e remedir os orçamentos do design §2.5. Enquanto essa decisão não for
  tomada, 3.13 permanece fixado. Qualquer dependência obrigatória nova, sobretudo as da
  Fase 6, exige repetir a verificação acima antes de mexer na versão.

## D7 — Versão de Node.js: 24

- **Data:** 2026-10-25
- **Decisão:** `24` em `.nvmrc` e `"node": ">=24 <25"` em `engines` do `package.json` da
  raiz — a mesma linha nos dois arquivos, com precisão de versão maior, como o `README.md`
  especifica. O campo `engines` declara também `"npm": ">=11 <12"`, que é a linha de `npm`
  distribuída com o Node 24, para que `adia doutor` tenha uma versão exigida de `npm`
  contra a qual comparar (R1.7) — o `README.md` não fixa essa, e sem um valor declarado o
  relatório do comando não teria o que reportar na coluna de versão exigida.
- **Justificativa:** linhas de versão ímpares do Node.js não são promovidas a LTS, e a 24 é
  linha LTS. Fixar a 25.5.0 que está instalada atrelaria um instrumento de pesquisa de
  ciclo plurianual a uma linha sem suporte de longo prazo. Como a versão fixada coincide
  com a do `README.md`, R1.9 não gera registro de divergência de versão adotada.
- **Divergência frente à máquina de desenvolvimento:** a máquina auditada tem Node
  **v25.5.0** e `npm` **11.8.0**. O `npm` satisfaz o intervalo declarado; o Node **não**.
  A consequência é intencional: `adia doutor` classificará o Node como `divergente` e
  concluirá com indicação de falha (R1.11) até que a linha 24 seja instalada. O verificador
  não instala nem modifica ferramenta alguma (R1.7).
- **Passo de correção:** instalar a linha 24 com `nvm-windows` — `nvm install 24` e
  `nvm use 24`, que passam a honrar o `.nvmrc` — ou pelo instalador oficial do Node.js 24.
  Nenhuma ação é tomada automaticamente por este repositório.
- **Condição conhecida do arquivo de bloqueio:** `npm install --package-lock-only` na raiz
  avisa `EBADENGINE` por causa do Node 25.5.0, mas **não** falha, porque o `npm` só reporta
  `engines` como aviso quando `engine-strict` não está ligado. O `package-lock.json` gerado
  tem apenas o pacote raiz, já que o `package.json` da raiz não declara dependência alguma:
  o projeto Vite entra na tarefa 11.1, que preenche o bloqueio e acrescenta a entrada de
  workspace. Ver a pendência correspondente.
- **Origem:** R1.5, R1.9, R1.11; design §1.5 (D7).
- **Revalidação:** quando a linha 24 sair da manutenção LTS, reavaliar para a próxima linha
  par. Mudar a linha fixada exige entrada nova aqui e atualização do `README.md` no mesmo
  movimento, porque é o `README.md` que serve de referência para R1.5 e R1.9.

## D12 — Itens em TOML com serializador canônico

- **Data:** 2026-10-22
- **Decisão:** os itens vivem em `data/itens/*.adia.toml`, lidos por `tomllib`, e o projeto
  mantém um **serializador canônico próprio** em vez de usar um escritor de TOML pronto.
  `adia itens formatar` grava a forma canônica; `adia itens validar` aceita qualquer escrita
  que a gramática admita. A gramática normativa está em
  [`gramatica-itens.md`](gramatica-itens.md).
- **Justificativa:** R3.5 exige que serializar, interpretar e serializar de novo produza
  texto **idêntico**, byte a byte. Nenhum escritor genérico garante isso, porque a escolha
  de estilo de cadeia, a ordem das chaves e a quebra de linha variam com a entrada. O
  `tomli-w` 1.2.0 ficou, por isso, restrito ao **literal de cada cadeia** — que é onde
  errar é fácil e silencioso; listas, ordem de chaves, blocos e linhas em branco são
  escritos pelo módulo, porque o `tomli-w` sempre explode lista em várias linhas com vírgula
  final, o que contradiz os exemplos em linha da gramática.
- **Origem:** R3.4, R3.5; design §1.5 (D12) e §3.1.
- **Revalidação:** se uma versão futura do `tomli-w` passar a oferecer controle de estilo de
  lista e de ordem de chaves, vale remedir quanto do módulo ainda precisa existir.

---

## DO-01 — Escala de dificuldade de item: inteiro de 1 a 5

- **Data:** 2026-10-25
- **Decisão:** `Item.dificuldade` é um inteiro no intervalo fechado de 1 a 5, com **1 = mais
  fácil** e **5 = mais difícil**. A escala é ordinal, não intervalar: a diferença entre 1 e 2
  não é comparável à diferença entre 4 e 5, e os valores não entram em nenhuma média. O
  carregador de itens reprova o arquivo cujo valor esteja fora do intervalo, nomeando
  arquivo, linha e campo.
- **Justificativa:** R2.1 exige o nível de dificuldade como inteiro de 1 a 5 e manda
  registrar a escala. Cinco graus dão granularidade suficiente para o pareamento isomórfico
  entre item assistido e item independente sem exigir calibração psicométrica, que este
  protótipo não faz e não pretende fazer. Declarar a escala como ordinal é o que impede que
  a dificuldade apareça como média em painel ou em exportação.
- **Origem:** R2.1; design §3.1 (`class Item`).
- **Revalidação:** se a seleção isomórfica passar a exigir pareamento mais fino que cinco
  graus, ou se algum consumidor precisar tratar dificuldade como quantidade, reavaliar antes
  de ampliar a escala.

## DO-02 — Orçamento de 2 segundos da `Guarda_de_Vazamento`

- **Data:** 2026-10-25
- **Decisão:** a verificação de um texto gerado conclui em até **2 s**, medidos com
  `time.monotonic()` dentro de `adia.guarda`. O estouro do orçamento é tratado como
  **impossibilidade de avaliar**, na mesma classe de erro interno e de perfil de item
  incompleto: o texto gerado é descartado, a dica pré-escrita do mesmo nível é entregue, o
  motivo da impossibilidade é registrado, e a entrega conta como **exatamente uma** dica do
  nível solicitado, sem nova tentativa de geração para o mesmo pedido.
- **Justificativa:** R7.1 fixa os 2 s. O que esta entrada acrescenta é a **postura diante do
  estouro**: falha fechada. Uma guarda que, ao exceder o tempo, deixasse o texto passar
  seria pior que nenhuma guarda, porque daria garantia que não cumpre. O orçamento também
  é a razão de ser dos limites de DO-10 — sem eles o tempo da verificação depende do texto
  de entrada, e um orçamento que depende da entrada não é orçamento.
- **Origem:** R7.1; design §2.1, §3.11 e a propriedade P23.
- **Revalidação:** medir no perfil de hardware do design §2.5. Se o percentil 95 da
  verificação passar de aproximadamente 1 s, a correção é apertar os limites de DO-10, não
  aumentar o orçamento.

## DO-03 — Limiar de 95% de acerto em dica legítima

- **Data:** 2026-10-25
- **Decisão:** sobre o conjunto declarado de verificação da guarda, exige-se
  `taxa_acerto_legitima = VN / (VN + FP) >= 0,95` — no máximo 5% de falso positivo em dica
  legítima — e **100%** de detecção dos casos de vazamento. Os dois portões são verificados
  por `adia guarda verificar`, que roda antes do `pytest` no portão local.
- **Justificativa:** a assimetria entre os dois portões é deliberada. Um vazamento não
  detectado contamina de forma irreversível o dado experimental daquele participante: o
  acerto deixa de distinguir domínio de cópia, que é exatamente a tese sob teste. Um falso
  positivo custa uma dica pré-escrita no lugar de uma gerada, perda de qualidade de
  assistência sem perda de validade. Daí recall de 100% e precisão apenas alta.
- **Origem:** R7.11; design §3.11 e §6.5.
- **Revalidação:** o limiar em si é do requisito e não se move sem mudar o requisito.
  Qualquer alteração na **composição** do conjunto de verificação exige entrada nova neste
  registro, com o caso, o motivo e quem decidiu (design §6.5). A ordem de reparo diante de
  portão vermelho é conteúdo, depois detector, e só então o conjunto.

## DO-04 — Limiar de confiança 0,60 do `Classificador_Roteador`

- **Data:** 2026-10-25
- **Decisão:** a confiança do roteador é `confianca = max P(papel)`. Com
  `confianca < 0,60`, o `Orquestrador_de_Dicas` entrega a **dica pré-escrita do nível
  autorizado** e registra `roteador_indeciso`.
- **Justificativa:** R21.4 exige confiança mínima declarada e prescreve a dica pré-escrita
  como saída da indecisão — não o papel padrão. Ou seja: indecisão do roteador é tratada
  como indisponibilidade de conteúdo gerado, do mesmo modo que ausência do Ollama ou
  veredito de vazamento, e não como "escolhe o papel padrão e segue". O valor 0,60 é ponto
  de partida para três classes: fica acima do acaso (0,33) com margem confortável e abaixo
  do ponto em que um classificador compacto passaria a recusar a maioria dos pedidos
  legítimos.
- **Origem:** design §3.8; R21.4 (que exige o limiar declarado, sem fixar o valor).
- **Revalidação:** medir a taxa de indecisão contra `data/roteador/pedidos_rotulados.jsonl`
  quando o conjunto rotulado estiver completo. Taxa de indecisão alta com acurácia alta
  indica limiar conservador demais; o ajuste entra como entrada nova aqui.

## DO-05 — Limiares do aviso do IIC

- **Data:** 2026-10-25
- **Decisão:** com `iic >= 0,8` **e** `tai_independente < 0,4` no mesmo ciclo, o campo
  `aviso` do IIC recebe o texto de que desempenho baixo com e sem ajuda também produz IIC
  alto. As duas condições são conjuntivas: nenhuma delas sozinha dispara o aviso.
- **Justificativa:** o IIC é uma razão, e razão entre dois valores baixos pode ser alta. Um
  participante que acerta pouco com ajuda e quase nada sem ajuda produz IIC alto por
  aritmética, não por independência. Sem o aviso, o painel apresentaria esse caso como bom
  resultado — leitura que inverte o sentido da métrica. O corte de 0,8 marca o IIC que um
  leitor interpretaria como "quase independente"; o de 0,4 marca o desempenho independente
  que não sustenta essa leitura. R11.8 já obriga a apresentar o IIC acompanhado da TAI; o
  aviso é a defesa para quem lê rápido.
- **Origem:** R11.9 (que exige o registro dos dois limiares); design §3.5.
- **Revalidação:** reavaliar com dados do piloto, quando houver distribuição empírica de
  TAI e IIC. Antes disso não há base para mover os cortes.

## DO-06 — Arredondamento meio para cima na apresentação em tela

- **Data:** 2026-10-25
- **Decisão:** métrica apresentada em tela é arredondada a **duas casas decimais** com
  arredondamento **meio para cima** (`ROUND_HALF_UP`). A conversão vive em um único lugar,
  `adia.nucleo.metricas.formatacao:para_tela`, e **nunca** alimenta comparação com limiar
  nem exportação. Armazenamento e exportação permanecem sem arredondamento, com no mínimo
  seis casas decimais.
- **Justificativa:** R11.13 exige a apresentação em duas casas; R11.12 proíbe arredondamento
  no armazenamento, na exportação e na comparação com limiar. Os dois convivem apenas se a
  apresentação for um beco sem saída no fluxo de dados. Meio para cima em vez do meio para
  o par da biblioteca padrão porque é o arredondamento que um leitor brasileiro espera ao
  conferir o número à mão, e a tela existe para ser conferida. Concentrar a conversão em uma
  função é o que torna a separação verificável por propriedade em vez de apenas pretendida.
- **Origem:** R11.13, com R11.12 como restrição; design §3.5 e a propriedade P19.
- **Revalidação:** nenhum gatilho previsto. Mudança aqui implica revisar P19.

## DO-07 — Atribuição balanceada de condição experimental

- **Data:** 2026-10-25
- **Decisão:** a condição de uma sessão é sorteada **uniformemente entre as condições de
  menor contagem corrente na coorte**, com semente registrada. Isso mantém a diferença
  entre as contagens por condição na mesma coorte sempre menor ou igual a 1, por
  construção, sem blocos de tamanho fixo. O evento `condicao_atribuida` registra a condição
  atribuída, a semente e o carimbo de tempo.
- **Justificativa:** R14.1 exige sorteio aleatório **e** diferença de contagens menor ou
  igual a 1 — duas exigências que um sorteio uniforme simples não satisfaz ao mesmo tempo.
  Restringir o sorteio ao conjunto de menor contagem preserva a aleatoriedade onde ela
  importa (qual participante vai para qual condição) e torna o balanceamento uma invariante
  em vez de uma expectativa. A alternativa de randomização por blocos de tamanho fixo
  deixaria o balanceamento quebrado entre fronteiras de bloco, que é precisamente o momento
  em que uma coleta pequena para.
- **Origem:** R14.1; design §3.3.
- **Revalidação:** nenhum gatilho previsto para o protótipo. Estratificação por
  característica do participante, se vier a ser desejada, é decisão nova.

## DO-08 — Janela de retenção de 168 a 216 horas

- **Data:** 2026-10-25
- **Decisão:** `liberar_retencao` compara `agora` com `posteste_concluido_em`:
  - **abaixo de 168 h** — não libera, e informa quanto falta;
  - **de 168 a 216 h** — libera, dentro do protocolo;
  - **acima de 216 h** — libera, aceita as respostas, marca a sessão como
    `fora_de_protocolo` e registra `desvio_horas` no evento `retencao_fora_de_janela`, com
    `janela_horas = [168, 216]`.
- **Justificativa:** R12.5 fixa a janela. 168 h são 7 dias e 216 h são 9 dias, o que dá à
  coleta uma folga de dois dias para acomodar a vida real do participante sem perder a
  comparabilidade do intervalo. As duas bordas têm posturas opostas de propósito: antes da
  janela a porta é **fechada**, porque medir retenção antes do intervalo não mede retenção e
  um dado assim contamina a análise; depois da janela a porta é **aberta com marca**, porque
  recusar eliminaria a única medida de retenção daquele participante, e uma medida fora de
  protocolo identificada vale mais que medida nenhuma. Quem analisa decide se inclui.
- **Origem:** R12.5, R12.4 e R12.6; design §3.3 e os eventos `retencao_liberada` e
  `retencao_fora_de_janela`.
- **Revalidação:** nenhum gatilho previsto. A janela faz parte do protocolo experimental
  documentado em [`protocolo.md`](protocolo.md) e mudá-la invalida a comparação entre
  coortes coletadas com janelas diferentes.

## DO-09 — Cache de 5 segundos da verificação de disponibilidade do Ollama

- **Data:** 2026-10-25
- **Decisão:** a disponibilidade do `Serviço_de_Inferência_Local` é verificada antes de cada
  pedido de geração, com **tempo limite de conexão de 1 s** e **resultado em cache por 5 s**.
- **Justificativa:** R23.1 exige a verificação antes de **cada** pedido. Sem cache, uma
  rajada de pedidos pagaria a checagem repetidas vezes em uma janela em que a resposta não
  pode ter mudado de forma relevante. Cinco segundos é curto o bastante para que a queda do
  serviço seja percebida dentro do mesmo pedido de dica seguinte, e longo o bastante para
  que a rajada custe uma única checagem. O tempo limite de 1 s existe para que a própria
  checagem não vire a fonte de latência que ela deveria evitar.
- **Origem:** R23.1; design §3.9.
- **Revalidação:** se o tempo até perceber a indisponibilidade aparecer como problema em uso
  real, encurtar o cache antes de removê-lo.

## DO-10 — Limites do avaliador aritmético da guarda

- **Data:** 2026-10-25
- **Decisão:** o avaliador de expressões da guarda usa **gramática restrita, sem `eval`**:
  tokens `Decimal` e os operadores `+ - * / ^ ( )`, analisador descendente recursivo,
  aritmética em `Fraction` quando há divisão e conversão para `Decimal` no fim. Limites de
  custo:
  - no máximo **32** expressões candidatas por texto;
  - no máximo **64** tokens por expressão;
  - profundidade de parênteses no máximo **8**;
  - divisão por zero **descartada**, não propagada como erro;
  - expoente limitado a **6**.
- **Justificativa:** R7.9 obriga a detectar expressão aritmética cujo resultado iguale o
  gabarito dentro da tolerância declarada, ainda que o gabarito não apareça escrito. Isso
  exige avaliar texto vindo de um modelo de linguagem, e `eval` sobre esse texto seria
  execução de código arbitrário no processo da API. A gramática restrita elimina a classe
  inteira. Os cinco limites são o que torna o orçamento de DO-02 **demonstrável** em vez de
  esperado: sem eles, o custo da verificação cresce com a criatividade do texto de entrada,
  e o pior caso é definido por quem escreve o texto. `Fraction` na divisão evita que erro de
  arredondamento intermediário faça um vazamento passar por diferença de centésimo.
- **Origem:** design §3.11 (D4 e D5b); R7.9 e R7.1.
- **Revalidação:** se o conjunto de verificação acusar vazamento aritmético não detectado
  por **truncamento** em algum dos cinco limites, o limite correspondente sobe e DO-02 é
  remedido. Subir limite sem remedir o orçamento não é permitido.

## DO-11 — Segmentação do corpus e embeddings do RAG

- **Data:** 2026-10-25
- **Decisão:** o material da disciplina é segmentado em trechos de **400 a 600 caracteres
  com sobreposição de 80**. Cada trecho recebe embedding `bge-m3` de **1024 dimensões**
  obtido por `POST /api/embed` do Ollama, normalizado em L2 e gravado como BLOB `float32`
  *little-endian* na tabela `rag_trecho`. A versão do índice registra o modelo de
  embeddings, sua versão e o hash do corpus.
- **Justificativa:** a faixa de 400 a 600 caracteres mantém o trecho perto de um parágrafo
  de material didático — grande o bastante para carregar um conceito completo, pequeno o
  bastante para que o trecho recuperado não arraste o gabarito junto, que é o risco que P25
  verifica. A sobreposição de 80 impede que uma definição partida exatamente na fronteira
  fique irrecuperável. A normalização em L2 transforma similaridade de cosseno em produto
  interno, o que é o que permite a passagem exaustiva em NumPy de D13 sem índice aproximado.
  Registrar modelo, versão e hash do corpus é o que atende R26.4: um índice sem proveniência
  é um índice que não se sabe reproduzir.
- **Origem:** design §3.10; R26.4, com D13 como decisão de design associada.
- **Revalidação:** acima de 50 000 trechos, reavaliar a busca exaustiva (gatilho de D13).
  Troca do modelo de embeddings invalida o índice e exige reindexação completa.

## DO-12 — Cobertura mínima de 95% com portão em `adia.nucleo` e `adia.guarda`

- **Data:** 2026-10-25
- **Decisão:** cobertura mínima de **95%**, com **portão** apenas para os pacotes
  `adia.nucleo` e `adia.guarda`. A cobertura do restante é medida e reportada, **sem**
  portão. Orçamentos de tempo: **90 s** para a suíte sem marcadores e **10 min** para o
  portão completo, na máquina do design §2.5.
- **Justificativa:** o portão restrito a dois pacotes não é concessão, é a consequência de
  onde o teste tem valor. `adia.nucleo` e `adia.guarda` são puros e determinísticos: a
  cobertura ali mede código que decide regulação, métrica, correção e vazamento. Exigir
  cobertura da camada de IA mediria o **dublê** instalado pela fixture `ollama_proibido`,
  não o código de produção — número alto que não informa nada e que criaria incentivo a
  escrever teste para satisfazer o número. Os orçamentos de tempo existem porque portão
  lento é portão que alguém contorna.
- **Origem:** design §6.1; R30.
- **Revalidação:** se a suíte sem marcadores passar de 90 s ou o portão completo de 10 min
  na máquina de referência, a correção é dividir a suíte por marcador, não afrouxar o
  limite de cobertura.

## DO-13 — Árvore rastreada com `.gitkeep` apenas nas folhas vazias

- **Data:** 2026-10-25
- **Decisão:** a árvore de diretórios do design §2.3 é criada por inteiro, com um arquivo
  `.gitkeep` vazio apenas nos **diretórios folha ainda sem conteúdo**. Diretórios
  intermediários ficam rastreados pelo caminho das folhas, sem `.gitkeep` próprio. Exceção
  única: **`data/identidade/` não recebe `.gitkeep`** e permanece fora do controle de
  versão.
- **Justificativa:** R1.1 exige que `docs/`, `backend/`, `frontend/`, `ml/` e `data/` estejam
  rastreados mesmo sem código, e o git não rastreia diretório vazio — daí os marcadores. Só
  nas folhas porque um `.gitkeep` em diretório intermediário seria redundante e precisaria
  ser removido depois, gerando ruído de histórico sem ganho. A exceção de
  `data/identidade/` segue o design §2.3, que a declara ignorada pelo git: é onde vive o
  mapa pseudônimo↔identidade, o único artefato do projeto cuja presença acidental no
  histórico seria irreversível. Para esse diretório, não existir no git é a propriedade
  desejada, e um marcador rastreado abriria a porta para o conteúdo entrar junto.
- **Origem:** R1.1 e R1.8; design §2.3.
- **Revalidação:** ao fim da Fase 0, remover o `.gitkeep` de todo diretório que já tenha
  ganhado conteúdo. O `.gitignore` de `data/identidade/` está em
  [DO-19](#do-19--caminho-único-do-vínculo-entre-pseudônimo-e-identidade).

## DO-14 — Prazo de retenção de dados de estudante: 180 dias

- **Data:** 2026-10-25
- **Decisão:** `participante_pseudonimo.retencao_ate` é gravado na criação do participante,
  com prazo padrão de **180 dias após a conclusão do teste de retenção da sessão**. Expirado
  o prazo, a exclusão dos dados daquele participante é executada por comando dedicado da
  CLI, e a execução da exclusão é ela própria registrada.
- **Justificativa:** R25.7 exige prazo declarado em `docs/` e operação de exclusão com
  registro, mas não fixa o prazo — é valor novo, nem do `README.md` nem dos requisitos.
  Cento e oitenta dias cobrem com folga o intervalo entre a última coleta e a análise e
  redação de resultados, que é o único uso legítimo do dado, e não se estendem ao ponto de
  transformar o repositório em arquivo permanente de dados de menores. A contagem começa na
  conclusão do teste de retenção, e não na criação do participante, porque é o fim da coleta
  daquele participante que inicia a vida útil analítica do dado. O prazo autoritativo e sua
  leitura para o participante estão em [`protocolo.md`](protocolo.md).
- **Origem:** R25.7; design §4 (`participante_pseudonimo`).
- **Revalidação:** o prazo é piso ético do protótipo, não teto legal. A aprovação ética
  institucional da Fase 7 (ver `protocolo.md`) pode impor prazo **menor**, e nesse caso
  prevalece o menor. Prazo maior exige justificativa nova nesta entrada.

## DO-15 — Limite de retrocesso de versão de Python: duas versões menores

- **Data:** 2026-10-25
- **Decisão:** diante de dependência obrigatória sem distribuição compatível com a versão
  de Python fixada, o retrocesso é de **uma versão menor por vez**, até o limite de **duas
  versões menores abaixo da indicada no `README.md`**. Com 3.14 como referência, o conjunto
  admissível é **{3.14, 3.13, 3.12}**; 3.11 ou inferior está fora. Cada passo registra,
  neste arquivo, a dependência que bloqueou e a versão em que bloqueou. Se nenhuma das três
  servir, `pyproject.toml` e `.python-version` **ficam inalterados** e o relatório lista as
  dependências bloqueadoras e as versões avaliadas (R1.10) — não há retrocesso além de 3.12
  sem decisão nova aqui.
- **Justificativa:** R1.4 exige o limite registrado como decisão operacional, sem fixar o
  valor. Duas versões menores cobrem cerca de dois anos de lançamentos do CPython, que
  segue cadência anual, e mantêm o interpretador dentro da janela de correção de segurança
  do upstream. Afrouxar o limite trocaria um problema de compatibilidade de dependência,
  que é temporário e se resolve com o tempo, por um problema de interpretador sem correção
  de segurança, que só piora. A regra de **uma por vez** existe para que o registro sirva
  de evidência: descer direto para o fundo da janela esconderia qual versão realmente
  bastava e qual dependência custou a queda.
- **Origem:** R1.4 e R1.10; design §1.5 (D6, portão de verificação da Fase 0).
- **Revalidação:** o limite está amarrado ao 3.14 do `README.md`. Se a versão de referência
  do `README.md` mudar, a janela admissível se refaz a partir dela, e a mudança entra como
  entrada nova neste registro.

## DO-16 — Tempo limite de 5 s do comando de versão em `adia doutor`

- **Data:** 2026-10-25
- **Decisão:** em `adia doutor`, o comando de versão de cada ferramenta tem **5 segundos**
  para responder. Esgotado o prazo, o processo é encerrado e a ferramenta é classificada
  como **`ausente`**, com o motivo registrado no relatório. O valor vale por ferramenta,
  não para o comando inteiro: o pior caso do `doutor` são seis esperas de 5 s.
  Três decisões acompanham, pela mesma origem:
  - **A sondagem do serviço do Ollama não usa este prazo.** Ela usa o tempo limite de
    conexão de 1 s de [DO-09](#do-09--cache-de-5-segundos-da-verificação-de-disponibilidade-do-ollama),
    e seu resultado é **observação, não situação**: a situação reportada é a do executável.
    Serviço desligado não reprova o ambiente — por D1, as etapas sem IA e o portão local do
    design §6.1 rodam integralmente com o Ollama fora (R23.5).
  - **Python é verificado no interpretador em execução**, por `platform.python_version()`,
    sem subprocesso e portanto sem este prazo. O Python que interessa é o que o `uv`
    provisionou em `.venv` e está rodando a CLI (R1.2); `python --version` no `PATH`
    responderia por outra instalação e, no Windows, pode responder pelo atalho da loja de
    aplicativos.
  - **Código de saída:** `0` ambiente conforme; `1` ferramenta ausente ou divergente, ou
    arquivo de fixação ilegível; `2` erro de uso da linha de comando; `3` comando declarado
    cuja implementação pertence a outra fase. O `3` existe porque comando que ainda não faz
    nada e termina com sucesso é falsa impressão de sucesso.
- **Justificativa:** R1.7 exige o prazo registrado como decisão operacional, sem fixar o
  valor. Cinco segundos é folgado para um `--version`, que é leitura de constante embutida
  no executável: as seis ferramentas desta máquina respondem em menos de 1 s. A folga
  cobre o caso que motiva o prazo — executável em disco de rede, verificação de assinatura
  no primeiro uso, ou binário que espera por serviço antes de imprimir a versão, como o
  `ollama` faz quando o serviço está fora. Prazo mais curto classificaria como `ausente`
  ferramenta instalada e funcional, que é o pior erro possível num diagnóstico: o
  desenvolvedor iria instalar o que já tem. Prazo mais longo transformaria o diagnóstico
  em espera. Classificar como `ausente` em vez de criar uma quarta situação é imposição de
  R1.7, que fecha o conjunto em `presente`, `ausente` e `divergente`; e é a leitura
  honesta, porque ferramenta que não responde não serve, esteja o arquivo em disco ou não.
- **Origem:** R1.7 e R1.11; design §3.18 e §2.4.
- **Revalidação:** se alguma ferramenta desta lista passar a ser classificada como
  `ausente` por tempo limite em máquina onde ela está instalada e funcional, medir o tempo
  real de resposta do `--version` e subir o prazo com a medida anotada aqui. Subir o prazo
  sem a medida não é permitido: seria trocar diagnóstico por espera sem saber o que se
  compra com ela.

## DO-17 — Triagem de dependências que exigem rede

- **Data:** 2026-10-25
- **Decisão:** a triagem é **código que roda**, não uma lista neste documento:
  `backend/tests/conjuntos/test_triagem_de_rede.py` carrega o veredito de cada distribuição
  do fecho de `uv.lock` e falha o passo 6 do portão local diante de dependência sem veredito,
  de dependência excluída que reapareça no bloqueio, de uso de API restrita em `backend/` ou
  `ml/`, e de exclusão que não esteja registrada aqui. R24.9 elege este arquivo como destino
  da exclusão; o portão trata a divergência entre a tabela e este texto como falha, para que
  as duas metades não possam andar separadas.
- **As três classes que a triagem separa.** Confundi-las torna a verificação inútil:
  1. **Rede na preparação** é aceita: baixar distribuição do PyPI, baixar o binário do
     navegador uma única vez. Acontece antes da coleta, com a máquina deliberadamente
     conectada. R24.8 fala da requisição que o protótipo **em execução** emite.
  2. **Rede em execução para laço local** é aceita e é o projeto: `httpx` falando com o
     Ollama em `127.0.0.1:11434`, `uvicorn` escutando em `127.0.0.1:8000` (D11).
  3. **Rede em execução para destino externo** é o que se rejeita: telemetria, verificação
     de atualização, download de peso ou de conjunto de dados sob demanda, recurso remoto.
- **Destinos aceitos:** `127.0.0.1`, `localhost` e `::1`, e nada mais. `0.0.0.0` e `::`
  ficam fora de propósito: são endereços de escuta em todas as interfaces, não de laço
  local, e é esse engano que D11 manda a aplicação recusar na partida.

### Método

Sobre o **fecho completo** de `uv.lock` — 54 distribuições, não as 15 diretas, porque o
risco mora no que entra de carona: `opentelemetry-api` chegou com o `fastapi` e `fsspec`
chega com o `torch`, nenhum dos dois pedido por nome. Três passadas sobre o código
instalado em `.venv`, e depois leitura do código fonte de cada achado antes do veredito:

1. **Importação de módulo de rede** — `socket`, `ssl`, `urllib`, `http.client`, `requests`,
   `aiohttp`, `smtplib`, `ftplib`, `xmlrpc`, fora das suítes das próprias bibliotecas.
2. **Literal de URL com hospedeiro externo**, descartando `127.0.0.1`, `localhost` e os
   domínios reservados de exemplo.
3. **Leitura de variável de ambiente** de telemetria, de modo offline ou de diretório de
   download.

Dois controles sustentam o método. O primeiro é que ele **achou coisas**: a telemetria OTLP
do `fastapi` 0.162, o `--pastebin` do `pytest` e o `GitHubArtifactDatabase` do `hypothesis`
não estavam na lista de suspeitos com que a triagem começou. O segundo é a medida
comportamental que acompanha a estática: um subprocesso importa toda a superfície de
execução com `connect`, `connect_ex`, `create_connection` e `getaddrinfo` interceptados,
liberando apenas destino de laço local. Nenhuma importação tentou sair — nem `sklearn`, nem
`fastapi`, nem o `adia`.

Nenhum veredito vem de reputação de pacote. O que não foi lido não recebeu veredito.

### Resultado: nenhuma dependência declarada foi removida

**A triagem não removeu nada do que já estava declarado.** Vale dizer com clareza, porque
triagem que não encontra nada é resultado legítimo e triagem inventada não é: as 15
dependências diretas de `pyproject.toml` permanecem as mesmas depois da triagem. O que a
triagem produziu foram **nove restrições de uso** e **treze exclusões**, listadas abaixo.

Das 54 distribuições do fecho, 40 não tocam a rede em tempo de execução. Das 14 restantes,
cinco falam rede e só com o laço local:

| Distribuição | Por que fala rede |
| --- | --- |
| `httpx` | cliente do `Serviço_de_Inferência_Local` (§3.12), com transporte injetável que recusa destino fora do laço local |
| `httpcore` | transporte do `httpx`: é quem abre o socket |
| `anyio` | primitivas de socket assíncrono usadas pelo `httpcore` e pelo `starlette` |
| `uvicorn` | servidor da `API_ADIA`, bind fixo em `127.0.0.1:8000` (D11) |
| `import-linter` | `importlinter/ui/server.py` sobe um visualizador de grafo com bind em `localhost`; o portão usa `lint-imports --config`, que não toca essa interface |

### Aceitas com restrição de uso

Um veredito restrito não é concessão: é a constatação de que a distribuição tem **uma
sub-API** que alcança destino externo e que o resto dela não alcança. Rejeitar
`scikit-learn` inteiro custaria o `Classificador_Roteador` e não compraria nada que a
proibição de `sklearn.datasets` não compre. Cada linha abaixo nomeia o que fica proibido, e
o portão varre `backend/` e `ml/` em busca desses trechos — é a varredura que transforma a
restrição em barreira. O `import-linter` não alcança esses casos: ele reduz pacote externo
ao nome de topo, que é a mesma limitação já anotada em `backend/.importlinter`.

| Distribuição | Caminho externo encontrado | Fica proibido |
| --- | --- | --- |
| `fastapi` | 0.162 traz configuração automática de OpenTelemetry que exportaria rastros, métricas e registros por OTLP. Três portas a separam de nós, todas fechadas: `auto_configure` é falso sem `FASTAPI_OTEL_AUTO_CONFIGURE=true`, não há ponto de exportação configurado, e o exportador exige o extra `fastapi[opentelemetry]`, que a declaração não pede. O caminho de serviço em si não abre conexão | `FASTAPI_OTEL_AUTO_CONFIGURE`, `auto_configure`, `OTEL_EXPORTER_OTLP` |
| `scikit-learn` | `sklearn.datasets` baixa de `openml.org`, `ndownloader.figshare.com` e `archive.ics.uci.edu` por `urlopen` e `urlretrieve`. O uso do projeto é `TfidfVectorizer` mais `LogisticRegression` (§3.8) | `sklearn.datasets` e os `fetch_*` |
| `numpy` | `numpy.lib.DataSource` aceita caminho `http://` e o abre com `urlopen` | `numpy.lib.DataSource`, `np.DataSource` |
| `scipy` | `scipy.datasets` baixa conjuntos de exemplo. O caminho está estruturalmente morto: exige `pooch`, que a triagem mantém fora | `scipy.datasets` |
| `hypothesis` | `GitHubArtifactDatabase` busca o banco de exemplos em `api.github.com` com `GITHUB_TOKEN`. O padrão é `DirectoryBasedExampleDatabase`, em `.hypothesis/` no disco local | `GitHubArtifactDatabase` |
| `pytest` | `--pastebin` publica o relatório da sessão em `https://bpa.st`. Num protótipo que processa produção textual de estudantes, isso é vazamento de dado, não só saída de rede | `--pastebin`, inclusive em `addopts` |
| `torch` | `torch.hub` baixa pesos pré-treinados sob demanda. O `Modelo_DKT` é uma LSTM treinada do zero em CPU (R28.1, R28.2) | `torch.hub`, `load_state_dict_from_url`, `pretrained=True` |
| `opentelemetry-api` | entra de carona com o `fastapi`. É só a interface: sem SDK e sem exportador, os provedores são implementações nulas e nada sai do processo | `opentelemetry.sdk`, `opentelemetry.exporter` |
| `fsspec` | entra com o `torch`. Os sistemas de arquivo remotos exigem `aiohttp` ou `requests`, que a triagem mantém fora; sobra o acesso a arquivo local | `fsspec.implementations.http` |

### Exclusões (R24.9)

Num projeto bloqueado por `uv.lock`, **rejeitar é não constar do fecho**. O portão falha no
commit que trouxer qualquer um destes nomes, com o nome e a razão na mensagem. Nenhuma
entrada é hipótese: cada uma é o pacote que ativaria um caminho de rede externo que a
varredura encontrou no código instalado, ou a alternativa de projeto que o design descartou
e que teria trazido esse caminho.

| Dependência excluída | Razão da exclusão |
| --- | --- |
| `opentelemetry-sdk` | completa o `opentelemetry-api` com provedores reais; é a metade que falta para o `fastapi` exportar telemetria |
| `opentelemetry-exporter-otlp-proto-http` | exportador OTLP sobre HTTP que o `fastapi[opentelemetry]` instala. É o pacote que emitiria a requisição ao coletor |
| `opentelemetry-exporter-otlp` | metapacote dos exportadores OTLP, pela mesma razão |
| `opentelemetry-instrumentation` | instrumentação automática de bibliotecas; arrasta SDK e exportador por dependência |
| `pooch` | baixa e põe em cache os conjuntos de `scipy.datasets`. Mantê-la fora deixa `scipy.datasets` em `ImportError`, que é a forma mais forte de proibição |
| `requests` | segundo cliente HTTP, sem o transporte restrito ao laço local que o `httpx` do projeto recebe (§3.12); também habilitaria o sistema de arquivo remoto do `fsspec`. Já é módulo proibido em `nucleo-puro` e `guarda-pura` |
| `aiohttp` | cliente HTTP assíncrono; habilitaria `fsspec.implementations.http`, pela mesma razão |
| `huggingface-hub` | consulta o hub por padrão para resolver e baixar modelo. Os embeddings vêm do `bge-m3` servido pelo Ollama no laço local (D13, DO-11) |
| `transformers` | arrasta `huggingface-hub` e baixa configuração e pesos sob demanda |
| `sentence-transformers` | arrasta `huggingface-hub` e baixaria o modelo de embeddings, duplicando fora do laço local o que DO-11 obtém por `POST /api/embed` do Ollama |
| `torchvision` | baixa pesos pré-treinados por `torch.hub`; o `Modelo_DKT` não usa visão nem peso de terceiro |
| `torchaudio` | mesma razão do `torchvision` |
| `ollama` | o cliente oficial em Python. **Não** é excluído por alcançar destino externo — ele fala com o laço local — e sim porque embutiria o cliente em vez de deixá-lo injetável. Os contratos `nucleo-puro` e `guarda-pura` o proíbem ao lado do `httpx` para que a fixture `ollama_proibido` tenha um único transporte a substituir (§3.12, §6.4) |

Nenhuma das treze está no bloqueio, e nenhuma foi retirada de lá: o bloqueio nasceu na
tarefa 1.2 já com as 15 dependências diretas de hoje. A exclusão aqui é o que impede que
entrem por conveniência numa fase posterior, sobretudo na Fase 6, e o que obriga quem as
quiser a reabrir esta decisão em vez de só acrescentar uma linha a `pyproject.toml`.

### Variáveis de ambiente que desligam telemetria e download automático

A lista é curta porque só entra nela variável que uma biblioteca do fecho **de fato** lê.
`DO_NOT_TRACK`, `HF_HUB_OFFLINE` e `TRANSFORMERS_OFFLINE` ficam fora: a varredura não
encontrou leitor para a primeira, e as outras duas pertencem a bibliotecas que a tabela de
exclusões mantém ausentes. Declará-las seria encenar uma defesa.

| Variável | Valor | Quem lê | Efeito |
| --- | --- | --- | --- |
| `OTEL_SDK_DISABLED` | `true` | `fastapi/telemetry/_runtime.py`, em `_configure_from_environment` | a configuração automática retorna sem registrar exportador algum |
| `FASTAPI_OTEL_AUTO_CONFIGURE` | `false` | construtor de `FastAPI` | mantém `auto_configure` desligado por declaração, não por ausência |

As duas são declaradas em `scripts/verificar.ps1` e `scripts/dev-backend.ps1`, os dois
processos que carregam o `fastapi`, e o portão lê esses arquivos: remover uma das linhas
reprova o passo 6. São a **segunda** linha de defesa. A primeira é a ausência do SDK e do
exportador no bloqueio, que faz a exportação levantar `FastAPIError` em vez de sair pela
rede — garantia estrutural, que não depende de ninguém lembrar de exportar variável.

### Rede na preparação, aceita e delimitada

| Insumo | Quando | Por que é aceitável |
| --- | --- | --- |
| Distribuições do PyPI | `uv sync`, a partir de `uv.lock` | versões e hashes fixados (R1.6); a coleta não resolve dependência |
| Pacotes do npm | `npm ci`, a partir de `package-lock.json` | mesma razão |
| Modelos do Ollama | `ollama pull llama3.2:1b` e `bge-m3`, uma vez | depois disso a inferência é local; o serviço escuta em `127.0.0.1:11434` |
| **Binários do navegador dos testes de ponta a ponta** | `npx playwright install chromium`, **uma única vez** | §6.2 fixa Chromium apenas, sem interface. O download é da preparação, não da coleta: depois dele a suíte roda inteiramente offline, contra `vite preview` e a API local. Um único motor respeita o orçamento de disco de §2.5 |

O download dos binários do navegador é o único item desta tabela que o design manda passar
pela triagem por nome (§6.2). Ele é **aceito**, não excluído, e a razão é a classe 1 acima:
nenhuma requisição é emitida durante a sessão de um participante. A contrapartida é que o
caminho de cache dos binários e a recusa de download na instalação do frontend ficam a cargo
da tarefa 11.1, que é quando `frontend/package.json` passa a existir — a triagem registra a
pendência em vez de configurar agora um arquivo que ainda não há.

- **Origem:** R24.8 e R24.9; design §2.5 (linha `Rede` do orçamento) e §6.2 (ponta a ponta).
- **Revalidação:** a cada mudança de `uv.lock`, por construção — o portão falha enquanto a
  distribuição nova não tiver veredito. Três gatilhos pedem releitura **do método**, e não só
  da tabela: subir a versão maior do `fastapi`, porque a telemetria automática é recente e
  seus padrões podem mudar; entrar qualquer dependência da Fase 6; e a tarefa 11.1, que
  acrescenta o lado Node ao fecho e com ele um segundo bloqueio a triar.

## DO-18 — Fim de linha LF fixado por `.gitattributes`

- **Data:** 2026-10-25
- **Decisão:** `.gitattributes` com `* text=auto eol=lf` fixa LF também na cópia de
  trabalho, e não apenas no repositório. Formatos binários recebem `binary` para escapar
  de qualquer conversão.
- **Justificativa:** `core.autocrlf` está como `true` nesta máquina, o que converteria
  todo arquivo de texto para CRLF ao extrair. Três coisas do projeto dependem de LF: o
  serializador canônico de itens (D12) exige ida e volta idêntica byte a byte com fim de
  linha LF, que é exatamente o que a Propriedade 30 verifica; os scripts `.ps1` são ASCII
  puro e sem BOM por convenção; e os arquivos `.excalidraw` são JSON de uma única linha.
  Sem a fixação, a Propriedade 30 reprovaria por um motivo sem relação nenhuma com o
  serializador, e o tempo de diagnóstico seria gasto no lugar errado.
- **Origem:** D12; design §5 (Propriedade 30) e §6.3.
- **Revalidação:** nenhum gatilho previsto.

## DO-19 — Caminho único do vínculo entre pseudônimo e identidade

- **Data:** 2026-10-25
- **Decisão:** o vínculo entre pseudônimo e identidade vive em **`data/identidade/`**.
  Tanto `data/identidade/` quanto `data/privado/` entram no `.gitignore` como diretórios
  inteiros, sem exceção de `.gitkeep`: o diretório não é rastreado, e não existir no git é
  a propriedade desejada.
- **Justificativa:** o design nomeia dois caminhos diferentes para o mesmo artefato — a
  seção de arquitetura diz `data/identidade/` e a de modelos de dados diz
  `data/privado/vinculo-identidade.csv`. Dois caminhos para o mesmo dado significam que a
  proteção cobriria um e deixaria o outro aberto. Adotado `data/identidade/`, que é o que
  a árvore de diretórios da tarefa 1.1 criou; `data/privado/` fica igualmente ignorado
  para que a ambiguidade do design não se converta em vazamento. Antes desta decisão
  nenhum padrão do `.gitignore` cobria o caminho, de modo que o primeiro arquivo colocado
  ali seria rastreado — e é o único artefato do projeto cujo vazamento é irreversível.
- **Origem:** R25.4, R25.5; design §2.3 e §4.6, que divergem entre si.
- **Revalidação:** a tarefa 8.11, que implementa a separação de identidade, deve confirmar
  o caminho adotado e corrigir a referência divergente no design.

## DO-20 — O portão invoca `mypy` e `import-linter` como módulo

- **Data:** 2026-10-25
- **Decisão:** `scripts/verificar.ps1` chama `uv run python -m mypy` e invoca o
  `import-linter` por `importlinter.cli.lint_imports`, em vez dos atalhos `mypy.exe` e
  `lint-imports.exe` de `.venv/Scripts`.
- **Justificativa:** nesta máquina os dois atalhos são bloqueados por política de Controle
  de Aplicativos do Windows (`os error 4551`), enquanto `ruff.exe`, `pytest.exe` e
  `adia.exe` passam. Invocados como módulo, ambos funcionam e produzem o mesmo resultado:
  `mypy --strict` sem erro em 30 arquivos e 5 contratos mantidos. A forma por módulo é
  também mais portátil, porque não depende de atalho gerado na instalação.
- **Origem:** design §6.1 e §6.4; restrição do ambiente auditado.
- **Revalidação:** se a política deixar de bloquear os atalhos, a forma direta volta a ser
  válida, mas não há ganho em trocar.

---

## DO-21 — Configuração dos testes de propriedade

- **Data:** 2026-10-22
- **Decisão:** perfil `propriedades` com `max_examples=100`, registrado **e carregado** em
  `backend/tests/conftest.py`. O único `@settings` que aparece num arquivo de propriedade é o
  **desvio** daquela propriedade. Os dois desvios que §5.0 prevê — 500 exemplos em P22, P25,
  P26 e P28; `deadline=None` em P16, P17, P31 e P35 — ficam como `@settings` no teste, porque
  a biblioteca mantém um perfil carregado por processo e perfil por propriedade exigiria
  trocá-lo no meio da execução. O `deadline=None` fica **estendido** às propriedades de ida e
  volta que gravam arquivo temporário, hoje P29 e P30.
- **Justificativa:** os 100 exemplos são regra da especificação, não escolha de arquivo;
  repeti-los em 37 decoradores apagaria a diferença entre o piso de §5.0 e uma decisão tomada
  localmente, e criaria 37 lugares para divergir. A extensão do prazo é medida, não suposta:
  8 a 47 ms por exemplo nesta máquina contra os 200 ms do padrão — folga que protege contra o
  **pico**, não contra a média, e um exemplo lento basta para pintar o portão de vermelho com
  uma mensagem sobre cronômetro. `DeadlineExceeded` que não se reproduz volta como teste
  instável, e o modo de falha é pior que o sintoma. Prazo frouxo foi rejeitado por ser a mesma
  medida com outro número; medir orçamento é de §2.5, com o marcador `desempenho`.
- **Onde o perfil não pode morar:** `backend/tests/propriedades/conftest.py`. O portão roda
  `mypy --strict` sobre `backend/tests`, nenhum diretório de teste tem `__init__.py`, e dois
  arquivos chamados `conftest.py` colapsam no mesmo nome de módulo — `Duplicate module named
  "conftest"`, com a checagem **abortada**, não apenas um erro a mais. As duas saídas que o
  próprio mypy sugere são piores que o sintoma: `__init__.py` nos diretórios de teste
  transformaria `propriedades/` em pacote e quebraria o `from estrategias import ...` dos
  arquivos de propriedade, que depende de o pytest inserir o diretório em `sys.path`; e
  `--explicit-package-bases` quebraria o mesmo import pelo outro lado, renomeando o módulo
  para `tests.propriedades.estrategias`.
- **Guarda:** `backend/tests/propriedades/test_perfil_de_propriedades.py`. O modo de falha do
  perfil é **silencioso** — apagado, renomeado ou com o número rebaixado, as propriedades
  seguem verdes rodando menos exemplos, nenhum portão fica vermelho e a perda não aparece em
  lugar nenhum. O teste também fixa a composição de que a convenção depende: um `settings`
  criado depois do carregamento herda do perfil tudo o que não declara.
- **Origem:** design §5.0 e §6.2. Resolve a pendência "Configuração de testes de propriedade".
- **Revalidação:** a cada subida de versão maior do `hypothesis`, porque a herança entre
  perfil carregado e `settings` por teste é comportamento da biblioteca, não contrato público.

---

## DO-22 — O pytest coleta os arquivos de propriedade `p01` a `p37`

- **Data:** 2026-10-22
- **Decisão:** `python_files = ["test_*.py", "p[0-9][0-9]_*.py"]` em `pyproject.toml`.
- **Justificativa:** o design §6.2 nomeia as 37 propriedades uma por arquivo, de
  `p01_decisao_unica.py` a `p37_tolerancia_decide.py`. O padrão de coleta do pytest é
  `test_*.py` e `*_test.py`, de modo que **nenhum** desses arquivos seria coletado: a
  propriedade existiria no repositório, verde por nunca ter rodado. O número no nome do
  arquivo é o que liga a propriedade à seção que a enuncia, e renomear 37 arquivos para
  `test_p29_...` custaria essa ligação. `python_functions` fica no padrão `test*`, logo a
  **função** de teste continua precisando do prefixo `test_`.
- **Origem:** design §6.2; tarefas 3.5 e 3.6.
- **Revalidação:** nenhum gatilho previsto.

---

## DO-23 — Gramática dos arquivos de definição de item

- **Data:** 2026-10-22
- **Decisão:** onze escolhas de gramática, todas normativas em
  [`gramatica-itens.md`](gramatica-itens.md) e implementadas em
  `backend/adia/nucleo/itens/carregador.py`. Cada uma fecha uma porta concreta:

| Escolha | Porta que ela fecha |
| --- | --- |
| Tolerância é **cadeia decimal**, nunca ponto flutuante de TOML | o valor binário mais próximo de `0.05` é `0,05000000000000000277…`, e a tolerância decide o acerto de item de fronteira (R4.2) — que é o que separa acerto de erro na TAI |
| `id`, `habilidade_alvo` e `incognita` são **ASCII** | `habilidade_alvo` é comparado por igualdade exata no pareamento de R2.2, e `"equação"` em NFC e em NFD são cadeias **diferentes** com a mesma aparência na tela: o pareamento falharia sem que nada parecesse errado |
| Chave desconhecida é **erro**, não campo ignorado | `toleranica` com as letras trocadas, se ignorado, produziria item numérico **sem tolerância declarada** apresentado como válido |
| Coleção é **conjunto** escrito como lista: ordenada, sem repetição | repetição silenciosamente descartada mudaria o tamanho entre uma leitura e a seguinte, e a ida e volta de R3.4 deixaria de valer |
| Marca de ordem de bytes é **recusada**, não descartada | aceitá-la faria o arquivo mudar de bytes entre uma leitura e uma reescrita sem que o conteúdo mudasse |
| `CRLF` é **tolerado na leitura**, e a escrita emite sempre `LF` | a quebra de linha do editor não é conteúdo do item (ver DO-18) |
| No máximo **uma** relação por par de itens, em qualquer direção | `equivalente` e `transferencia` sobre a mesma dupla são afirmações contraditórias, e qual valeria passaria a depender da ordem de leitura |
| A **direção** da relação é informativa, não normativa | isomorfismo é simétrico; exigir uma ordem de escrita produziria a mensagem errada — "falta equivalente" para um par declarado de trás para frente |
| Relação declarada que não qualifica conta como **ausência**, nunca como pareamento parcial | um equivalente de dificuldade diferente faria o desafio independente medir uma tarefa mais fácil que a praticada |
| **Comentário não sobrevive** a `adia itens formatar` | quem precisa registrar a razão de uma escolha de conteúdo registra neste arquivo, não em comentário de arquivo de item |
| Nenhuma mensagem de erro **cita conteúdo** de campo sigiloso | a mensagem vai para o terminal, para o log de subida da API e, no pior caso, para uma captura de tela em sala; gabarito ali é vazamento por outro caminho |

- **Origem:** R2.1, R2.2, R2.6, R2.8, R2.9, R2.11, R3.1 a R3.6, R4.2, R7.6; design §3.1 e §7.2.
- **Revalidação:** qualquer campo novo no esquema do item reabre a linha de coleções e a de
  chave desconhecida.

---

## DO-24 — Forma canônica do arquivo de item

- **Data:** 2026-10-22
- **Decisão:** a gramática aceita muitas escritas do mesmo item; a forma canônica escolhe
  **uma**, e é essa escolha que torna verdadeira a exigência de R3.5. As decisões de escrita,
  todas em `serializar_canonico`:

| Construção | Forma canônica | Por quê |
| --- | --- | --- |
| Ordem das chaves | fixada pelo **esquema** (`ORDEM_CANONICA_DE_ITEM`) | a alfabética separaria `gabarito` de `tolerancia` e `unidade` de `sinonimos_unidade`, que são os pares que um revisor lê juntos; a ordem de inserção faria o texto depender de como o objeto foi construído em memória, que é o que R3.5 proíbe |
| `enunciado` e cada dica | bloco de três aspas **sempre**, inclusive com uma linha só | "bloco quando multilinha" seriam duas formas para o mesmo conteúdo |
| Fim do bloco | **barra invertida** na última linha de conteúdo | a barra descarta a quebra seguinte; sem ela, todo valor voltaria com um `\n` a mais no fim — o defeito mais fácil de não notar, porque a tela mostra o mesmo texto. Ela também separa o conteúdo do delimitador, de modo que texto terminado em aspas não forme o fechamento |
| Aspas no texto | escapada só a **terceira** de uma sequência | três aspas seguidas fechariam o bloco no meio do texto; escapar toda aspa tornaria ilegível o caso comum, que é texto em pt-BR com uma citação |
| Coleção | lista **em linha**, ordem crescente, sem repetição | é conjunto escrito como lista, e a ordem de escrita não é conteúdo |
| Campo opcional ausente e coleção vazia | **omitidos** | TOML não tem nulo, e `sinonimos_unidade = []` seria a segunda escrita de uma ausência |
| `transferencia` | escrito **sempre**, inclusive `false` | decide se o item conta na TT (R2.9); num arquivo que vai a revisão humana, o silêncio não é a melhor escrita do valor padrão |
| `Decimal` | forma mais curta que preserva o valor, em notação simples | a gramática não admite expoente, e arredondar mudaria o acerto de item de fronteira (R4.2) |
| `Decimal` não finito | **recusado alto**, com `ValueError` | `nan` e `inf` não têm escrita que a gramática aceite; serializá-los produziria arquivo que a própria leitura rejeita |
| Banco vazio | texto vazio, que **não** é arquivo de definição válido | documentado para que ninguém o grave; `canonizar` nunca produz esse caso |

- **Origem:** R3.5; design §3.1 e §1.5 (D12).
- **Revalidação:** campo novo no esquema precisa entrar em `ORDEM_CANONICA_DE_ITEM`, ou
  simplesmente **não seria escrito** e a ida e volta perderia o campo em silêncio. Há teste
  que reprova essa omissão.

---

## DO-25 — `canonizar` preserva a partição de arquivos

- **Data:** 2026-10-22
- **Decisão:** além de `serializar_canonico(itens, relacoes) -> str`, que é o que o design
  declara, existe `canonizar(caminhos) -> Mapping[Path, str] | ErroDeCarga`: ela valida o
  banco **inteiro** e devolve o texto canônico **de cada arquivo**. É ela que
  `adia itens formatar` grava.
- **Justificativa:** `serializar_canonico` recebe o banco inteiro e produz um texto só. Usada
  direto pelo comando, ela colapsaria N arquivos em um — passaria em R3.5 e destruiria a
  organização do conteúdo, que é o que R3 existe para proteger. A validação precisa ser do
  conjunto, porque as associações de R2.2 e R2.6 e o conflito de R2.9 cruzam arquivos e um
  arquivo isolado não é verificável; a gravação, ao contrário, é arquivo por arquivo.
- **Divergência registrada:** o design §3.1 declara apenas `serializar_canonico`.
- **Origem:** R3.3, R3.5; design §3.1 e §7.2.
- **Revalidação:** nenhum gatilho previsto.

---

## DO-26 — Códigos de saída e escopo de `adia itens validar` e `adia itens formatar`

- **Data:** 2026-10-22
- **Decisão:** quatro escolhas nos dois comandos:
  - **banco vazio passa, com aviso explícito na tela**; **diretório inexistente reprova**;
  - `--diretorio` nos dois subcomandos;
  - `formatar` grava só o que de fato muda, e **nada** quando a carga falha;
  - `CODIGO_BANCO_INVALIDO = 1`, nome próprio com o mesmo valor de
    `CODIGO_AMBIENTE_INVALIDO`.
- **Justificativa:** `validar` é o passo 4 do portão local e roda **antes** do `pytest`. Até a
  tarefa 3.14, banco vazio é a situação declarada do repositório, e reprovar por ela travaria
  o portão inteiro por uma ausência já conhecida; o aviso é o que impede a leitura "o banco
  está bem". Caminho errado silenciado, ao contrário, produziria um "banco válido" que ninguém
  verificou. `--diretorio` é o que permite verificar um conjunto sem tocar em `data/itens/`, e
  é o que torna os testes da CLI possíveis sem efeito no repositório. Não reescrever arquivo
  idêntico não é economia de E/S: `formatar` é rodado em laço durante a escrita do banco, e
  reescrever sujaria a data de modificação de arquivo que não mudou. O código 1 é o único
  "verifiquei e reprovei", e cada comando o nomeia pelo que reprovou — separar os nomes mantém
  a leitura do código honesta sem multiplicar códigos que o PowerShell trataria igual.
- **Origem:** R3.1 a R3.5; design §3.18, §6.1 e §7.2.
- **Revalidação:** a tarefa 3.14 torna o aviso de banco vazio um sintoma, e não mais a
  situação normal.

---

## DO-27 — Geradores do Hypothesis: validade por construção

- **Data:** 2026-10-22
- **Decisão:** `backend/tests/propriedades/estrategias.py` é o módulo único de geradores
  nomeados, com seis escolhas:
  - **dois** geradores de item. `itens` cobre o domínio inteiro, inclusive
    `pratica_assistida` em `etapas_permitidas`; `itens_carregaveis` é o mesmo com essa etapa
    fora, e é o único que as propriedades de ida e volta podem usar;
  - **nenhum** gerador filtra com `assume` ou `.filter`: tudo o que a carga impõe é honrado
    por construção;
  - coleção gerada já sai na **forma canônica**, nos dois níveis de `termos_essenciais`;
  - `PerfilDeGabarito` mantém juntos os cinco campos que `tipo_gabarito` acopla;
  - mapeadores de `.map()` são **funções nomeadas**, nunca `lambda`;
  - peso de indisponibilidade de `Medida` em **0,15**, sorteado como inteiro em centésimos.
- **Justificativa:** item praticado exige equivalente isomorfo e item de transferência
  **declarados como relação** (R2.2, R2.6), e isso é invariante do **banco**, não do item:
  serializado sozinho ele é recusado com `ErroDeAssociacaoAusente`, e a propriedade reprovaria
  por item malformado em vez de por defeito de serialização — com o contraexemplo apontando
  para o lugar errado. Filtrar seria a outra saída, e é pior em dois sentidos: desperdiça
  exemplos e deixa o encolhimento perseguir a borda do filtro em vez do defeito. A leitura
  devolve `tuple(sorted(...))`, de modo que coleção gerada fora de ordem produziria item que
  vai e volta **diferente de si mesmo**; quem precisa de ordem arbitrária — a ênfase de §5.5
  em P30 — embaralha na própria propriedade, onde a intenção fica visível. Sortear os cinco
  campos do perfil de forma independente produziria, na maioria dos exemplos, item que a carga
  rejeita. E o nome do mapeador aparece no contraexemplo encolhido: `catalogo_de_dicas({...})`
  se lê onde `<lambda>({...})` não diz nada.
- **Nota sobre o encolhimento:** o lado para o qual `Medida` encolhe é o **indisponível**, por
  ser o valor estruturalmente mais simples da união. Vale saber ao ler um contraexemplo de
  métrica: o primeiro a conferir é se a indisponibilidade é parte do defeito ou só o fundo do
  poço do encolhimento.
- **Origem:** R29.1 a R29.3; design §6.3. Resolve a metade de `indisponibilidade = 0,15` da
  pendência "Pesos padrão dos geradores"; o banco de 12 a 60 itens segue com a tarefa 3.14.
- **Revalidação:** campo novo em `Item` exige revisar `PerfilDeGabarito` e o gerador de item.

---

## DO-28 — Convenção dos arquivos de propriedade

- **Data:** 2026-10-22
- **Decisão:** `p29_item_ida_e_volta.py` fixou a forma dos 37 arquivos, e `p30` a exerceu.
  Seis pontos:
  - **um arquivo, uma propriedade, um teste** (§5.0). Afirmação de apoio entra como teste
    separado, **sem** `@given`, nunca como segundo `@given` no mesmo arquivo;
  - **etiqueta na primeira linha do corpo**, antes da docstring, no formato de §5.0;
  - **fronteira de nome entre `estrategias.py` e o arquivo da propriedade:** gerador de
    domínio compartilhado **sobe** para o módulo; encanamento de E/S fica privado e
    **repetido** em cada arquivo;
  - `maximo` **sem padrão** em `bancos`: o teto de banco gerado é decisão de orçamento de
    quem chama, justificada no arquivo de cada propriedade;
  - **`tempfile`, nunca a fixture `tmp_path`**, e gravação em **bytes**;
  - igualdade byte a byte é contra o **arquivo lido de volta do disco**, e a ausência de
    qualquer `CR` é a forma de verificar fim de linha `LF`.
- **Justificativa:** a fronteira de nome já se moveu uma vez e no lugar certo — `bancos` e
  `identificador_de` subiram quando P30 passou a precisar deles, porque unicidade e ordenação
  por `id` são exigência do **banco** (R3.6) e não substância de nenhuma das duas
  propriedades; repetida em cada arquivo, é o tipo de restrição que divergiria sem ninguém
  notar, e o preço é uma propriedade reprovando por banco inválido em vez de pelo defeito que
  procura. O encanamento de E/S fica fora porque `estrategias.py` é módulo de **geradores**, e
  acolher E/S nele apagaria o que o nome promete. Fixture de escopo de função sob `@given` é
  reprovada pela própria biblioteca, e com razão: seria criada uma vez e compartilhada por
  todos os exemplos. `write_text` no Windows traduziria `LF` em `CRLF`, e o arquivo deixaria de
  ser o que o serializador produziu. Reencodificar a cadeia em memória tornaria as afirmações
  de BOM e de `CRLF` afirmações sobre a biblioteca padrão, não sobre o arquivo.
- **Guarda da ênfase:** quando §5.5 declara uma ênfase de geração, ela é afirmada com `find`
  num teste de apoio. O modo de falha é silencioso: embaralhamento que deixasse de embaralhar
  não quebra nada — a propriedade segue verde, afirmando a estabilidade sobre entrada que já
  estava canônica, e o que se perde é a chance de encontrar o defeito.
- **Achado que justifica as duas propriedades serem separadas:** com a subtabela de dicas
  emitida na ordem de inserção — o que um escritor de TOML genérico faz — **P29 passa** e só
  P30 reprova. P29 compara estrutura, e `Mapping` não compara ordem: as duas cargas devolvem o
  catálogo em ordem de `Nivel` de todo modo. É defeito que só o texto vê.
- **Origem:** design §5.0, §5.5 e §6.3.
- **Revalidação:** nenhum gatilho previsto.

---

## DO-29 — Duas raízes de erro no banco de itens, sem herança entre elas

- **Data:** 2026-10-22
- **Decisão:** `backend/adia/nucleo/itens/erros.py` guarda duas famílias com raízes
  **separadas**: `ErroDeCarga`, falha de **conteúdo** descoberta ao ler `data/itens/`, que
  aborta a carga e com ela a subida da API; e `ErroDeSelecao`, falha de **tempo de execução**
  descoberta ao atender um pedido sobre banco que já carregou, que recusa o **pedido** e vira
  resposta `409`. Nenhuma deriva da outra. Acompanha a decisão: `ValueError` fica reservado ao
  pedido que **não descreve nada** — conjunto de praticados vazio, identificador repetido na
  mesma solicitação, etapa com IA pedida a `elegiveis_sem_ia`.
- **Justificativa:** a hierarquia única produziria um defeito concreto nas duas direções. Um
  `except ErroDeCarga` ou um `isinstance` no caminho de subida passaria a capturar a recusa de
  um pedido e abortaria o serviço por um item pedido na etapa errada; na direção oposta, um
  arquivo malformado apareceria ao estudante como `409` em vez de impedir a execução.
  `ErroDeCarga` exige `arquivo`, `linha` e `campo` porque a falha dele **está** num arquivo;
  herdar forçaria inventar um caminho, que é a precisão fingida que o módulo recusa. E
  `ValueError` como valor de erro faria a interface anunciar "conjunto indisponível" para um
  banco que tem todos os itens — defeito de quem chama apresentado como indisponibilidade de
  conteúdo.
- **Nota de verificação:** o `mypy --strict` com `warn_unused_ignores` **prova** que a
  interseção dos dois tipos é vazia — um `isinstance(erro, ErroDeCarga)` sobre erro de seleção
  é código morto, e o verificador recusa. O teste afirma a mesma invariante pela hierarquia,
  legível sem rodar o mypy.
- **Origem:** design §3.1 e §7.2. Relaciona-se à pendência "Recusa da API em servir diante de
  erro de carga do banco de itens".
- **Revalidação:** a tarefa 9.1, que monta o catálogo de erros da API, consome esta taxonomia.

---

## DO-30 — `ErroDeItemDesconhecido` como terceiro tipo de retorno

- **Data:** 2026-10-22
- **Decisão:** `BancoDeItens.obter` devolve
  `Item | ErroDeEtapaNaoPermitida | ErroDeItemDesconhecido`, e `conjunto_do_desafio` recebe o
  mesmo terceiro tipo. Código de interface `ITEM_DESCONHECIDO`.
- **Justificativa:** o contrato de §3.1 escreve `Item | ErroDeEtapaNaoPermitida`, que não cobre
  o identificador que não existe — caso que não desaparece por não estar previsto. Tratá-lo
  como etapa não permitida mandaria quem depura olhar as `etapas_permitidas` de um item que
  não existe, e a API responderia `ITEM_FORA_DA_ETAPA` para identificador obsoleto. Levantar
  contraria o padrão do módulo e tem alvo real: o design §4.2 registra que
  `apresentacao_item.item_id` **não** é chave estrangeira, então um evento antigo pode citar
  item que saiu do banco — referência que precisa ser tratável, não fatal.
- **Divergência registrada:** §3.1 e a tabela de §7.2 precisam da terceira linha.
- **Origem:** R2.5; design §3.1, §4.2 e §7.2.
- **Revalidação:** nenhum gatilho previsto.

---

## DO-31 — Semente injetada no construtor, nunca gerador com estado

- **Data:** 2026-10-22
- **Decisão:** `BancoDeItens(carga, semente)`. A semente entra na **construção**, e o módulo
  não guarda nenhum gerador: cada chave de ordenação sai de uma instância própria de
  `random.Random`, semeada com a cadeia `semente ⟂ contexto ⟂ id do candidato`, usando o
  separador de unidade do ASCII como delimitador.
- **Justificativa:** a semente é parâmetro da **execução**, não do pedido — uma semente por
  chamada permitiria que dois pedidos da mesma execução usassem sementes diferentes, e a
  semente registrada na proveniência deixaria de descrever a seleção que de fato aconteceu.
  Duas propriedades vêm da chave por candidato, e nenhuma viria de um gerador guardado no
  banco: a **independência da ordem das chamadas**, porque um gerador avançaria a cada pedido
  e a escolha do ciclo 3 passaria a depender de quantas vezes o ciclo 1 chamou o banco —
  contagem que não está registrada em lugar nenhum, e sem a qual o replay de R26.7 não
  reproduz a seleção; e a **estabilidade sob crescimento do banco**, porque a chave é por
  candidato e não um embaralhamento da lista inteira, de modo que acrescentar um item não
  reordena a preferência entre os que já existiam — o que mantém legível uma preferência
  antiga depois de a tarefa 3.14 acrescentar conteúdo.
- **Nota sobre o contrato `nucleo-puro`:** ele proíbe `secrets`, `uuid` e `time` em
  `adia.nucleo`. `random` com semente **explícita** é o oposto do que a proibição persegue, que
  é a aleatoriedade implícita. O semeamento é por cadeia de texto, e não por tupla, porque o
  Python 3.11 removeu o semeamento a partir de objeto arbitrário; para `str` a semente passa
  por `sha512` do texto em UTF-8, determinística entre execuções, plataformas e valores de
  `PYTHONHASHSEED`.
- **Divergência registrada:** §3.1 diz que "a seleção usa a semente registrada" mas a
  assinatura que ele declara não tem onde recebê-la. O design precisa declarar o construtor.
- **Origem:** R26.3, R26.7; design §3.1, §4.3 e §6.4.
- **Revalidação:** nenhum gatilho previsto.

---

## DO-32 — Emparelhamento máximo, não escolha gulosa, na atribuição de equivalentes

- **Data:** 2026-10-22
- **Decisão:** `conjunto_do_desafio` atribui equivalentes a itens praticados por
  **emparelhamento máximo bipartido com caminhos de aumento** — reacomoda o dono de um
  candidato antes de desistir. Determinístico: praticados na ordem do pedido, candidatos na
  ordem da semente.
- **Justificativa:** a escolha gulosa falha num caso que tem solução. Com os equivalentes de
  `p1` sendo `{a, b}` e os de `p2` sendo `{a}`, o guloso dá `a` a `p1`, deixa `p2` sem nada e
  recusa o pedido — embora a atribuição `p1→b, p2→a` exista. Isso não violaria a letra da
  Propriedade 33, que proíbe conjunto parcial e não exige sucesso, mas violaria o que ela
  protege: abortaria um ciclo que o banco tinha itens para atender, e o aborto apareceria como
  lacuna de conteúdo inexistente — alguém iria mexer em `data/itens/` para corrigir um
  problema que não está lá. Com o emparelhamento máximo, a recusa só acontece quando nenhuma
  atribuição completa existe, e aí é fato sobre o banco, não artefato da ordem de visita.
- **Origem:** R2.3, R2.10; design §3.1 e §5.6 (Propriedade 33).
- **Revalidação:** nenhum gatilho previsto.

---

## DO-33 — Composição do conjunto do desafio independente

- **Data:** 2026-10-22
- **Decisão:** três escolhas sobre o que entra no conjunto:
  - **exatamente um** item de transferência, não "um ou mais"
    (`TRANSFERENCIAS_NO_CONJUNTO = 1`), de modo que o tamanho é sempre
    `itens praticados + 1`;
  - o universo de candidatos de transferência é a **habilidade alvo**, não a relação
    declarada;
  - item **praticado no ciclo** é inelegível como equivalente de outro praticado do mesmo
    ciclo.
- **Justificativa:** R2.3 pede "ao menos um item de transferência" **e** "nenhum outro item", e
  entregar exatamente um é a leitura que mantém as duas metades verdadeiras ao mesmo tempo.
  Também mantém a TT comparável: com quantidade variável, uma TT de 0,5 significaria coisas
  diferentes em dois ciclos do mesmo participante. O universo pela habilidade segue a letra de
  §3.1 — a relação declarada continua exigida na **carga**, item por item (R2.6), mas fixá-la
  na montagem faria a disponibilidade do desafio depender de qual praticado o autor do arquivo
  escolheu como origem da relação, que a gramática declara informativa (DO-23). E apresentar um
  item praticado minutos antes com assistência como desafio **sem** assistência mediria memória
  recente, não desempenho autônomo — que é exatamente o que o par isomorfo existe para evitar.
  Essa última exclusão não está enunciada em nenhum requisito; está implícita no propósito do
  par e fica registrada aqui por isso.
- **Divergência registrada:** `ErroDeConjuntoIncompleto.item_praticado` é `str | None`. R2.10
  pede que o erro identifique "o item praticado e a associação indisponível", mas na lacuna de
  **transferência** não há praticado responsável: a exigência é da solicitação e da habilidade
  alvo. Eleger um dos praticados seria apontar culpado arbitrário; o erro carrega `praticados`
  (todos) e `habilidade`, que identifica mais, não menos. A redação de R2.10 merece revisão
  nessa metade.
- **Origem:** R2.3, R2.6, R2.10, R8.3, R11.2; design §3.1 e §7.2.
- **Revalidação:** se o protocolo passar a querer mais de um item de transferência, a
  constante é o único lugar a mudar.

---

## DO-34 — Taxonomia das lacunas do conjunto, com precedência declarada

- **Data:** 2026-10-22
- **Decisão:** `LacunaDoConjunto` distingue cinco causas, avaliadas nesta ordem:
  `JA_APRESENTADO`, `PRATICADO_NO_CICLO`, `FORA_DA_ETAPA`, `DISPUTADO`,
  `SEM_CANDIDATO_QUALIFICADO`.
- **Justificativa:** as causas pedem **consertos diferentes**, e quem opera o protocolo precisa
  saber qual antes de mexer em `data/itens/`. "Sem candidato qualificado" tem conserto no
  arquivo do item; "já apresentado" não tem conserto nenhum no arquivo — o participante já viu
  todos, e a saída é ampliar o banco. A precedência tem duas razões: "já apresentado" vem
  primeiro porque é a única que descreve a **execução em curso** em vez do conteúdo do banco,
  e é a consequência esperada de R2.7 num banco pequeno; e "disputado" vem antes de "sem
  candidato qualificado" porque na disputa **havia** candidato qualificado, e dizer o contrário
  seria falso.
- **Origem:** R2.7, R2.10; design §3.1 e §7.2.
- **Revalidação:** nenhum gatilho previsto.

---

## DO-35 — Critério de qualificação de R2.2 com uma só implementação

- **Data:** 2026-10-22
- **Decisão:** `equivalente_qualifica`, `transferencia_qualifica` e
  `e_de_transferencia_da_habilidade` moram em `backend/adia/nucleo/itens/modelo.py`, públicas,
  e são importadas tanto pelo carregador quanto pelo banco.
- **Justificativa:** o carregador recusa o item praticado sem equivalente (R2.6) e o banco
  monta o desafio com os que qualificam (R2.3) — é o **mesmo** critério aplicado em dois
  momentos. Duas cópias divergiriam na primeira correção feita em um lado só, e a divergência
  seria silenciosa nas duas direções: banco aceito na carga recusando a montagem, ou o
  contrário.
- **Origem:** R2.2, R2.3, R2.6; design §3.1.
- **Revalidação:** nenhum gatilho previsto.

---

## DO-36 — O sigilo da mensagem de erro é afirmado sobre `detalhe()`

- **Data:** 2026-10-22
- **Decisão:** o teste que verifica que nenhuma mensagem cita conteúdo de campo sigiloso
  afirma sobre `erro.detalhe()`, e não sobre `erro.mensagem`.
- **Justificativa:** `mensagem` compõe `local`, o nome do campo e `detalhe()`, e `local` traz o caminho
  do arquivo. Sob `tmp_path` esse caminho inclui o número da sessão do pytest, de modo que um
  segredo de um dígito casa com ele por coincidência: o teste reprovava **sobre o caminho** em
  vez de sobre o conteúdo, em cerca de uma execução em cinco para o segredo `"7"`. Reproduzido
  de forma determinística com `--basetemp` contendo os dígitos. A superfície de vazamento é
  `detalhe()`; caminho e linha são estruturais e exigidos por R3.2, e não podem conter conteúdo
  de campo.
- **Origem:** R3.2; design §7.2 e §6 de [`gramatica-itens.md`](gramatica-itens.md).
- **Revalidação:** nenhum gatilho previsto.

---

## Pendências

Decisões operacionais que o design já identifica mas cujo valor pertence a código ainda não
escrito, ou que a tarefa 1.1 não produz. Cada uma entra neste registro pela tarefa indicada.
A lista existe para que nenhuma se perca entre fases.

### Fases posteriores

| Pendência | Origem |
| --- | --- |
| `package-lock.json` da raiz sem entradas de dependência enquanto não houver projeto de frontend. A tarefa 11.1 monta o Vite, preenche o bloqueio e acrescenta a entrada de workspace na raiz; só então R1.6 vale também para o lado Node. Ver D7 | R1.6; design §2.3 |
| Caminho de cache dos binários do navegador e recusa de download na instalação do frontend, para que o download único de [DO-17](#do-17--triagem-de-dependências-que-exigem-rede) não se repita. Entra na tarefa 11.1, quando `frontend/package.json` passa a existir | R24.8; design §6.2 |
| Triagem de rede do fecho do `package-lock.json`, pelo método de DO-17. A tarefa 11.1 traz o lado Node, e com ele um segundo bloqueio a triar | R24.8, R24.9; design §6.2 |
| `D8` — base de cálculo de `dicas usadas` no DSS e o máximo de uma dica por nível por item por ciclo | R6.3; design §1.5 |
| `D9` — base de cálculo da `confiança_média` do viés | design §1.5 |
| `D10` — um único valor de viés por ciclo, produzido por `MetricasDoCiclo.vies` | design §1.5 |
| `D11` — API local sem autenticação, com a lista de seis pré-condições de qualquer exposição futura | design §1.5 |
| `D13` — busca vetorial exaustiva, com gatilho de revisão acima de 50 000 trechos | design §1.5 |
| `D14` — parâmetros de inferência do `llama3.2:1b` derivados do hardware auditado | design §1.5 |
| Arredondamento a quatro casas com meio para cima **antes** da comparação com limiar, e igualdade no limiar valendo só para `>=` e `<=` | R9.12; design §3.2 |
| L4 como teto de suporte inicial do primeiro ciclo nas Condições B e C | R9.10 |
| Tratamento de métrica indisponível por denominador zero: decidir manter, teto inalterado, evidência incompleta registrada | R9.13 |
| Regra de desempate do separador decimal e a falha fechada no caso ambíguo | R7.11; design §3.11 |
| `responsavel_id` e `avaliador_id` no formato `PROF-NN`, mantidos fora do banco operacional | R25.3; design §4 |
| Proveniência embutida nas seis últimas colunas de cada CSV, com a alternativa rejeitada anotada | R16.8; design §4 |
| Pesos padrão dos geradores, a metade que resta: banco de itens entre 12 e 60 (tarefa 3.14) e composição `3 / 10 / 20` do corpus sintético (Fase 4). O peso `indisponibilidade = 0,15` está em [DO-27](#do-27--geradores-do-hypothesis-validade-por-construção) | design §6.3 |
| Seleção de modelo no benchmark e remoção dos candidatos não selecionados, com o tamanho em disco registrado antes da remoção | R20.2, R24.6; design §2.5 |
| Alterações na composição do conjunto de verificação da guarda, com caso, motivo e responsável | R7.11; design §6.5 |
| Destino do registro da falha de escrita do próprio log de eventos, fora do banco | design §7 |
| Recusa da API em servir diante de erro de carga do banco de itens, nomeando arquivo, linha e campo | design §7 |
| Motivo de indisponibilidade `aguardando_rubrica` do projeto STEAM | design §7 |
| Janela de inatividade que dispara `sessao_interrompida`, com 45 minutos como ponto de partida | design §7 |
| Limite global de corpo de requisição, com 64 KB como ponto de partida | design §7 |
| Catálogo único de mensagens de erro no frontend, varrido contra o `Banco_de_Itens` | R7; design §7 |
