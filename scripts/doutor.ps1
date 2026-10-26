# Verificação de ambiente do protótipo ADIA-CognitiveLoop (R1.7, R1.11).
#
# Reporta, para Python, uv, Node.js, npm, git e Ollama, a versão exigida, a
# versão detectada e a situação entre presente, ausente e divergente. Não
# instala, não atualiza e não altera nenhuma ferramenta.
#
# Padrão de PowerShell 5.1 em pt-BR (design §2.3): um comando por linha, sem o
# operador `&&`, com verificação explícita de $LASTEXITCODE depois de cada
# comando nativo. $LASTEXITCODE só é confiável após comando nativo, por isso os
# cmdlets usam -ErrorAction Stop em vez de teste de código de saída.
#
# Codificação: este arquivo é UTF-8 sem BOM, e o PowerShell 5.1 lê arquivo sem
# BOM pela página de código ANSI do sistema. Por isso este script não imprime
# texto próprio: a acentuação do relatório vem do processo do `adia`, que emite
# UTF-8, e a linha de `OutputEncoding` acima é o que faz o terminal decodificar
# esse UTF-8 corretamente.
#
# Códigos de saída: 0 ambiente conforme; 1 ferramenta ausente ou divergente.

[Console]::OutputEncoding = [Text.Encoding]::UTF8

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot) -ErrorAction Stop

uv run adia doutor
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

exit 0
