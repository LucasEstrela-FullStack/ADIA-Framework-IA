# Servidor de desenvolvimento do backend do protótipo ADIA-CognitiveLoop.
#
# Sincroniza o ambiente a partir de uv.lock e sobe a API local em
# 127.0.0.1:8000, o único endereço que D11 admite: a API não tem autenticação,
# e qualquer bind fora do laço local exporia produção textual de estudantes
# (R15.2, R24.3, R24.4). A própria aplicação recusa iniciar em endereço que não
# seja de laço local; o endereço explícito aqui é para que a linha de comando
# diga o mesmo que o código.
#
# A verificação de ambiente fica em scripts/doutor.ps1 e não é pré-condição
# daqui: o backend não usa Node.js, e divergência na linha do Node não deve
# impedir o desenvolvimento do lado Python.
#
# Padrão de PowerShell 5.1 em pt-BR (design §2.3): um comando por linha, sem o
# operador `&&`, com verificação explícita de $LASTEXITCODE depois de cada
# comando nativo.
#
# Codificação: este arquivo é UTF-8 sem BOM, e o PowerShell 5.1 lê arquivo sem
# BOM pela página de código ANSI do sistema. Por isso o texto que o script
# **imprime** é restrito a ASCII: acentuação em comentário é inofensiva, mas
# acentuação em `Write-Output` chegaria trocada ao terminal.
#
# Códigos de saída: 0 encerramento normal do servidor; 3 aplicação ainda não
# implementada nesta fase; demais, o código do comando que falhou.

[Console]::OutputEncoding = [Text.Encoding]::UTF8

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot) -ErrorAction Stop

# Triagem de dependencias que exigem rede -- DO-17 em docs/decisoes.md (R24.8, R24.9).
#
# Este e o processo que carrega o fastapi, e o fastapi 0.162 le estas duas variaveis em
# fastapi/telemetry/_runtime.py. Com OTEL_SDK_DISABLED=true a configuracao automatica de
# telemetria retorna sem registrar exportador algum; FASTAPI_OTEL_AUTO_CONFIGURE=false
# declara o padrao em vez de depender de ausencia. A defesa primaria nao esta aqui: e a
# ausencia do opentelemetry-sdk e do exportador OTLP no uv.lock, verificada por
# backend/tests/conjuntos/test_triagem_de_rede.py, que tambem le estas duas linhas.
$env:OTEL_SDK_DISABLED = "true"
$env:FASTAPI_OTEL_AUTO_CONFIGURE = "false"

$aplicacao = "backend\adia\api\app.py"
if (-not (Test-Path -LiteralPath $aplicacao)) {
    Write-Output "A API local entra na Fase 2, tarefa 9.1."
    Write-Output "Arquivo esperado: $aplicacao"
    Write-Output "Nada foi iniciado."
    exit 3
}

uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run uvicorn adia.api.app:app --host 127.0.0.1 --port 8000 --reload
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

exit 0
