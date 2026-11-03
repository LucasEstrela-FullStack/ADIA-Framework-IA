# scripts/piloto.ps1
# Operacao do piloto numa maquina da escola: um comando por acao, sem Vite e sem rede no dia.
#
#   .\scripts\piloto.ps1 preparar    uma vez, COM rede: dependencias, build do frontend e modelos
#   .\scripts\piloto.ps1 verificar   antes de cada coleta: ambiente, guarda e Ollama de verdade
#   .\scripts\piloto.ps1 subir       sobe a API, que serve tambem as telas, em http://127.0.0.1:8000
#   .\scripts\piloto.ps1 parar       derruba a API
#   .\scripts\piloto.ps1 backup      copia o banco para data\backups\ (use disco cifrado)
#
# SEM ACENTOS NESTE ARQUIVO, DE PROPOSITO: ver o cabecalho de scripts/verificar.ps1.
# Roteiro completo, com BitLocker e destruicao dos dados, em docs/piloto.md.

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("preparar", "verificar", "subir", "parar", "backup")]
    [string]$acao
)

[Console]::OutputEncoding = [Text.Encoding]::UTF8
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot) -ErrorAction Stop

# Triagem de rede (DO-17): mesmas duas linhas de scripts/dev-backend.ps1.
$env:OTEL_SDK_DISABLED = "true"
$env:FASTAPI_OTEL_AUTO_CONFIGURE = "false"

$modelos = @("qwen2.5:1.5b", "bge-m3")
$pid_arquivo = "logs\api.pid"

function Falhar([string]$mensagem) {
    Write-Host $mensagem
    exit 1
}

if ($acao -eq "preparar") {
    uv sync --frozen
    if ($LASTEXITCODE -ne 0) { Falhar "uv sync falhou. Confira a rede e rode de novo." }
    npm --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { Falhar "npm ci falhou. Confira a rede e rode de novo." }
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { Falhar "O build do frontend falhou." }
    foreach ($modelo in $modelos) {
        ollama pull $modelo
        if ($LASTEXITCODE -ne 0) { Falhar "ollama pull $modelo falhou. O Ollama esta instalado e aberto?" }
    }
    uv run --frozen adia indexar
    if ($LASTEXITCODE -ne 0) { Falhar "A indexacao do corpus do RAG falhou: veja a mensagem acima." }
    Write-Host "Pronto. A partir daqui o piloto roda sem rede."
    exit 0
}

if ($acao -eq "verificar") {
    uv run --frozen --offline adia doutor
    if ($LASTEXITCODE -ne 0) { Falhar "Ambiente fora de conformidade: veja o relatorio acima." }
    uv run --frozen --offline adia guarda verificar
    if ($LASTEXITCODE -ne 0) { Falhar "A guarda reprovou. Nao colete dados antes de corrigir." }
    uv run --frozen --offline pytest -m ollama -q
    if ($LASTEXITCODE -ne 0) { Falhar "O Ollama nao respondeu como esperado. As dicas usarao texto pronto." }
    Write-Host "Tudo certo para a coleta."
    exit 0
}

if ($acao -eq "subir") {
    if (-not (Test-Path -LiteralPath "frontend\dist\index.html")) {
        Falhar "Frontend nao construido. Rode antes: .\scripts\piloto.ps1 preparar"
    }
    if (Test-Path -LiteralPath $pid_arquivo) {
        Falhar "A API ja parece estar no ar (logs\api.pid existe). Rode parar antes."
    }
    New-Item -ItemType Directory -Force -Path "logs" | Out-Null
    # Sem --reload: no piloto o codigo nao muda durante a coleta.
    $processo = Start-Process -FilePath "uv" -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput "logs\api.log" -RedirectStandardError "logs\api.err" `
        -ArgumentList @("run", "--frozen", "--offline", "uvicorn", "adia.api.app:app", "--host", "127.0.0.1", "--port", "8000")
    Set-Content -LiteralPath $pid_arquivo -Value $processo.Id -Encoding ascii
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/saude" -TimeoutSec 2 | Out-Null
            Write-Host "No ar: abra http://127.0.0.1:8000 no navegador dos estudantes."
            exit 0
        } catch {}
    }
    Falhar "A API nao respondeu em 30 s. Veja logs\api.err."
}

if ($acao -eq "parar") {
    if (-not (Test-Path -LiteralPath $pid_arquivo)) {
        Falhar "Nada a parar: logs\api.pid nao existe."
    }
    $id = Get-Content -LiteralPath $pid_arquivo
    # /T derruba tambem o python filho do uv.
    taskkill /PID $id /T /F | Out-Null
    Remove-Item -LiteralPath $pid_arquivo
    Write-Host "API parada."
    exit 0
}

if ($acao -eq "backup") {
    uv run --frozen --offline adia backup
    exit $LASTEXITCODE
}
