# Verificação de ambiente e versões exigidas

Documento do comando de verificação de ambiente e das versões exigidas de cada ferramenta. É
a referência que R1.7 cita como "o comando de verificação de ambiente documentado em
`docs/`".

## Comando

```powershell
uv run adia doutor
```

Ou, pelo script de apoio, que já ajusta a codificação do terminal e entra na raiz do
projeto antes de executar:

```powershell
.\scripts\doutor.ps1
```

O comando **não instala, não atualiza e não altera nenhuma ferramenta** (R1.7). Ele observa
e reporta; corrigir é ação humana, e o relatório diz qual é o passo de cada caso.

### Códigos de saída

| Código | Significado |
| --- | --- |
| `0` | Ambiente conforme: as seis ferramentas exigidas estão presentes |
| `1` | Ferramenta `ausente` ou `divergente`, ou arquivo de fixação ilegível (R1.11) |
| `2` | Erro de uso da linha de comando |
| `3` | Comando declarado cuja implementação pertence a outra fase |

O `3` é dos outros comandos da CLI, não do `doutor`: `adia migrar`, `adia itens validar`,
`adia itens formatar`, `adia guarda verificar`, `adia indexar`, `adia replay`,
`adia exportar`, `adia excluir-dados` e `adia benchmark` estão declarados desde a Fase 0,
informam a fase e a tarefa em que entram e terminam com código diferente de zero — comando
que ainda não faz nada e termina com sucesso é falsa impressão de sucesso.

## O que o comando reporta

Já fixado por R1.7. Para cada uma das seis ferramentas — **Python**, **`uv`**,
**Node.js**, **`npm`**, **`git`** e **Ollama** — o relatório traz três campos:

| Campo | Conteúdo |
| --- | --- |
| Versão exigida | A versão fixada pelo projeto |
| Versão detectada | A versão encontrada na máquina |
| Situação | `presente`, `ausente` ou `divergente` |

O relatório acrescenta uma quarta coluna, **Fixada em**, com o arquivo que fixa a
exigência. Ela existe para que a resposta a "de onde vem essa versão exigida?" esteja no
próprio relatório: as versões exigidas são **lidas dos arquivos de fixação**, nunca
embutidas no código do comando.

Quatro regras de comportamento que acompanham:

- **Tempo limite.** A ferramenta cujo comando de versão não responder em até **5 segundos**
  é classificada como `ausente`. O valor é decisão operacional e está registrado em
  [`decisoes.md`](decisoes.md) como `DO-16`.
- **Não modifica nada.** O comando não instala, não atualiza e não altera nenhuma das
  ferramentas verificadas. Ele diagnostica e informa.
- **Falha é falha.** Diante de qualquer ferramenta `ausente` ou `divergente`, o comando
  conclui com indicação de falha — código de saída diferente de zero — e lista cada
  ferramenta com a situação apurada (R1.11). Arquivo de fixação ilegível também reprova:
  ambiente que não se sabe verificar não é ambiente verificado.
- **Serviço do Ollama é observação, não situação.** A situação reportada para o Ollama é a
  do **executável**. O relatório informa, separadamente, se o serviço responde em
  `127.0.0.1:11434`, e serviço desligado **não** reprova o ambiente: por D1, linha de base,
  desafio independente, pós-teste, retenção e o portão local do design §6.1 rodam
  integralmente com o Ollama fora (R23.5).

## Versões exigidas

| Ferramenta | Versão exigida | Fixada em | Como é detectada |
| --- | --- | --- | --- |
| Python | `3.13.x` | [`.python-version`](../.python-version) e `requires-python` em [`pyproject.toml`](../pyproject.toml) | Interpretador em execução, por `platform.python_version()` |
| `uv` | não fixada | — | `uv --version` |
| Node.js | `24.x` | [`.nvmrc`](../.nvmrc) e `engines.node` em [`package.json`](../package.json) | `node --version` |
| `npm` | `>=11 <12` | `engines.npm` em [`package.json`](../package.json) | `npm --version` |
| `git` | não fixada | — | `git --version` |
| Ollama | não fixada | — | `ollama --version`, mais a sondagem de `127.0.0.1:11434` |

Três notas sobre a tabela:

- **Precisão da exigência.** `3.13.x` aceita toda a linha 3.13 e recusa 3.12 e 3.14; `24.x`
  aceita toda a linha 24 e recusa 23 e 25. É a "precisão mínima de `maior.menor`" de R1.2 e
  a "precisão mínima de versão maior" de R1.5. Arquivo de fixação com três componentes, se
  vier a existir, passa a exigir a versão exata.
- **Sem versão fixada não é sem exigência.** Para `uv`, `git` e Ollama o projeto não fixa
  versão, e o comando não inventa piso mínimo: reporta a detectada e trata **a ausência**
  como falha. Essas três nunca aparecem como `divergente`.
- **Python é lido do interpretador em execução.** É o Python que o `uv` provisionou em
  `.venv` (R1.2), não o que estiver no `PATH`. No Windows, `python --version` no `PATH`
  pode responder pelo atalho da loja de aplicativos, que não é o interpretador do projeto.

As divergências frente ao `README.md` estão em [`decisoes.md`](decisoes.md): `D6` para a
versão de Python e `D7` para a de Node.js, com motivo, data e gatilho de revalidação,
conforme R1.3 e R1.9.

### Estado desta máquina de desenvolvimento

Na máquina em que o protótipo é desenvolvido, `adia doutor` conclui com **falha**, e isso
está previsto: o Node.js instalado é **25.5.0**, e `D7` fixa a linha **24** por ela ser LTS.
O comando classifica o Node como `divergente`, lista o passo de correção e termina com
código `1`. O ambiente fica conforme depois de instalar a linha 24 — o que não impede o
trabalho no backend, que não usa Node.js.

## Passos de correção

| Situação | Passo |
| --- | --- |
| Python `ausente` ou `divergente` | `uv python install` na versão de [`.python-version`](../.python-version), seguido de `uv sync` para recriar o ambiente (`D6`) |
| `uv` `ausente` | Instalar o `uv` pela documentação oficial e reabrir o terminal, para que o `PATH` seja relido |
| Node.js `ausente` ou `divergente` | `nvm install 24` seguido de `nvm use 24` no `nvm-windows`, ou o instalador oficial da linha 24 (`D7`) |
| `npm` `ausente` ou `divergente` | O `npm` acompanha o Node.js: corrigir a linha do Node resolve |
| `git` `ausente` | Instalar o Git para Windows e reabrir o terminal |
| Ollama `ausente` | Instalar o Ollama. A Fase 4 é a primeira que depende dele; as fases anteriores rodam sem |
| Serviço do Ollama sem resposta | Nada a corrigir para rodar as etapas sem IA e o portão local. Para a Fase 4, subir o serviço |
| Arquivo de fixação ilegível | O relatório nomeia o arquivo e o que ele deveria declarar. Os arquivos de fixação são rastreados pelo git: `git checkout` sobre o arquivo restaura a versão fixada |

## Scripts de apoio

Todos em [`scripts/`](../scripts), no padrão de PowerShell 5.1 em pt-BR do design §2.3: um
comando por linha, sem o operador `&&`, com verificação explícita de `$LASTEXITCODE` depois
de cada comando nativo.

| Script | O que faz |
| --- | --- |
| `doutor.ps1` | Executa `uv run adia doutor` e propaga o código de saída |
| `dev-backend.ps1` | Sincroniza o ambiente por `uv sync` e sobe a API local em `127.0.0.1:8000` (D11). A aplicação entra na Fase 2, tarefa 9.1; até lá o script informa isso e termina com `3` |
| `dev-frontend.ps1` | Instala o frontend por `npm ci` e sobe o Vite em `127.0.0.1:5173` (D11). O projeto Vite entra na Fase 3, tarefa 11.1; até lá o script informa isso e termina com `3` |

Os scripts são UTF-8 **sem BOM**, e o PowerShell 5.1 lê arquivo sem BOM pela página de
código ANSI do sistema. Por isso o texto que eles **imprimem** é restrito a ASCII, e a
acentuação do relatório vem do processo do `adia`, que emite UTF-8; a linha
`[Console]::OutputEncoding = [Text.Encoding]::UTF8` no início de cada script é o que faz o
terminal decodificar esse UTF-8 corretamente.

## O que ainda entra neste relatório

O design prevê para o `doutor` três campos que dependem de código de fases posteriores, e
eles entram junto com o código que os produz:

| Campo | Fase | Onde o design pede |
| --- | --- | --- |
| `sqlite3.sqlite_version`, com falha abaixo de 3.31 | Fase 2 | §4.3 — a coluna gerada de `resposta` exige SQLite ≥ 3.31 |
| `esquema_versao` e a verificação dos três *triggers* de imutabilidade | Fase 2 | §4.7 e §7.7 |
| `indice_rag`, com instrução de rodar `adia indexar` | Fase 4 | §7.6 |

## Hardware de referência

O perfil de hardware em que os orçamentos não funcionais do projeto foram derivados está no
design, seção `Architecture`. Os orçamentos de desempenho só valem nesse perfil; é o que o
marcador de teste `desempenho` significa.
