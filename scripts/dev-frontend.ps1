# Servidor de desenvolvimento do frontend do protótipo ADIA-CognitiveLoop.
#
# Instala as dependências a partir de package-lock.json e sobe o Vite em
# 127.0.0.1:5173, a origem que a API local aceita em CORS (D11).
#
# `npm ci` em vez de `npm install`: a instalação tem de resolver exatamente as
# versões do arquivo de bloqueio (R1.6), e `npm install` pode reescrevê-lo.
#
# A linha de Node.js exigida é verificada por scripts/doutor.ps1. Aqui ela não é
# pré-condição, mas vale a lembrança: o `npm ci` recusa a instalação se o
# `engines` do package.json não for satisfeito e `engine-strict` estiver ligado.
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
# Códigos de saída: 0 encerramento normal do servidor; 3 projeto de frontend
# ainda não montado; demais, o código do comando que falhou.

[Console]::OutputEncoding = [Text.Encoding]::UTF8

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot) -ErrorAction Stop

$projeto = "frontend\package.json"
if (-not (Test-Path -LiteralPath $projeto)) {
    Write-Output "O projeto Vite entra na Fase 3, tarefa 11.1."
    Write-Output "Arquivo esperado: $projeto"
    Write-Output "Nada foi iniciado."
    exit 3
}

npm --prefix frontend ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

exit 0
