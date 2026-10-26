# scripts/verificar.ps1
# Portao local de verificacao -- design secao 6.1.
#
# Nao ha CI em nuvem neste projeto: este script E o portao, e e o mesmo comando que um
# gancho de pre-commit invocaria. A ordem dos oito passos e a de 6.1 e vai do mais barato
# para o mais caro, para que a falha mais comum apareca em segundos em vez de minutos.
#
# Padrao obrigatorio de 2.3 (PowerShell 5.1 em locale pt-BR): um comando por linha,
# verificacao explicita de $LASTEXITCODE, sem "&&" e sem pipe de bloco foreach.
#
# SEM ACENTOS NESTE ARQUIVO, DE PROPOSITO. O PowerShell 5.1 le um .ps1 sem BOM usando a
# pagina de codigo ANSI do sistema, nao UTF-8: cada caractere acentuado chegaria ao console
# como dois caracteres latinos. Verificado nesta maquina. Como os arquivos do repositorio
# sao UTF-8 sem BOM, o texto proprio do script fica em ASCII -- este arquivo nao tem um
# unico byte acima de 127. O [Console]::OutputEncoding abaixo resolve o outro lado do
# problema, que e o que de fato importa: a saida dos processos filhos -- nomes dos
# contratos de import, mensagens da CLI, relatorio do pytest -- e UTF-8, e chega acentuada
# e legivel.
#
# O portao roda com o Ollama DESLIGADO, e essa e a configuracao que mais se aproxima do que
# o prototipo precisa garantir. Ficam fora dele, por exigirem o servico de inferencia de pe:
# "uv run pytest -m ollama" (contrato do cliente), "adia indexar" (embeddings do bge-m3),
# "adia benchmark" (R20) e os testes marcados "desempenho".

[Console]::OutputEncoding = [Text.Encoding]::UTF8

# Permite invocar o portao de qualquer diretorio: todos os caminhos abaixo sao relativos a
# raiz do repositorio ("backend/.importlinter", "--prefix frontend").
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $raiz

# Mesma convencao de backend/adia/cli.py: 3 significa "declarado no design, ainda nao
# implementado". Os passos 4 e 5 ja devolvem esse codigo por conta propria, com a fase e a
# tarefa na mensagem, e por isso sao chamados direto. Os passos 7 e 8 ganham o equivalente
# mais abaixo, porque o npm nao tem como saber que frontend/package.json entra na tarefa
# 11.1 -- sem a checagem, o portao morreria num ENOENT em vez de dizer o que falta.
$CODIGO_NAO_IMPLEMENTADO = 3

# Triagem de dependencias que exigem rede -- DO-17 em docs/decisoes.md (R24.8, R24.9).
#
# O fastapi 0.162 le estas duas variaveis em fastapi/telemetry/_runtime.py. Com
# OTEL_SDK_DISABLED=true a configuracao automatica retorna sem registrar exportador, e
# FASTAPI_OTEL_AUTO_CONFIGURE=false e o padrao declarado em vez de presumido. Sao a segunda
# linha de defesa: a primeira e a ausencia do opentelemetry-sdk e do exportador OTLP no
# uv.lock, que faz qualquer exportacao levantar erro em vez de sair pela rede.
#
# backend/tests/conjuntos/test_triagem_de_rede.py le estas duas linhas: remover uma delas
# reprova o passo 6.
$env:OTEL_SDK_DISABLED = "true"
$env:FASTAPI_OTEL_AUTO_CONFIGURE = "false"

$inicio = Get-Date

Write-Host ""
Write-Host "[1/8] ruff -- estilo, e a proibicao de relogio em adia.nucleo e adia.guarda"
uv run ruff check backend ml
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[2/8] mypy --strict -- camada 2: fronteira de tipo, sem Any no lado puro"
uv run mypy --strict backend/adia
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[3/8] lint-imports -- camada 1: contratos de camada e de proibicao"
uv run lint-imports --config backend/.importlinter
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[4/8] adia itens validar -- gramatica e elegibilidade do banco de itens"
uv run adia itens validar
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[5/8] adia guarda verificar -- conjunto declarado da guarda como portao"
uv run adia guarda verificar
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[6/8] pytest -- unidade, propriedades, conjuntos e integracao, com o Ollama fora"
uv run pytest -m "not ollama and not desempenho"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[7/8] vitest -- decisao de renderizacao das telas"
if (-not (Test-Path -LiteralPath "frontend/package.json")) {
    Write-Host "  'npm --prefix frontend run test:run' ainda nao esta disponivel."
    Write-Host "  frontend/package.json entra na Fase 5, tarefa 11.1 (andaime do Vite)."
    Write-Host "  Os passos 7 e 8 dependem dele. Nenhuma acao foi executada."
    exit $CODIGO_NAO_IMPLEMENTADO
}
npm --prefix frontend run test:run
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[8/8] playwright -- cinco fluxos de ponta a ponta, sobre dicas pre-escritas"
npm --prefix frontend run e2e
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$duracao = (Get-Date) - $inicio
Write-Host ""
Write-Host ("Portao completo: 8 de 8 passos verdes em {0:n1} min (orcamento de 10 min em 2.5)." -f $duracao.TotalMinutes)
exit 0
