# Скачать qwen2.5:3b ТОЛЬКО в D:\HUH\MTS_Hacaton_AI_Agent\.ollama\models

$ErrorActionPreference = "Stop"
$Root = "D:\HUH\MTS_Hacaton_AI_Agent"
$OllamaExe = "D:\HUH\ollama\install\ollama.exe"

$env:OLLAMA_MODELS = Join-Path $Root ".ollama\models"
$env:OLLAMA_HOME = Join-Path $Root ".ollama"
$env:TEMP = Join-Path $Root ".cache\tmp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:OLLAMA_MODELS, $env:TEMP | Out-Null

# serve уже должен быть запущен с тем же OLLAMA_MODELS
Write-Host "Pulling qwen2.5:3b into $env:OLLAMA_MODELS"
& $OllamaExe pull qwen2.5:3b
if ($LASTEXITCODE -ne 0) { throw "ollama pull failed: $LASTEXITCODE" }

& $OllamaExe list
Get-ChildItem $env:OLLAMA_MODELS -Recurse -ErrorAction SilentlyContinue |
    Measure-Object -Property Length -Sum |
    ForEach-Object { "models on D: ~{0:N1} MB" -f ($_.Sum / 1MB) }
