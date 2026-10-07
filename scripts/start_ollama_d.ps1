# Локальный контур только на D: (каталог проекта). C: почти не трогаем.

$ErrorActionPreference = "Stop"
$Root = "D:\HUH\MTS_Hacaton_AI_Agent"
$OllamaExe = "D:\HUH\ollama\install\ollama.exe"

$env:OLLAMA_MODELS = Join-Path $Root ".ollama\models"
$env:OLLAMA_HOME = Join-Path $Root ".ollama"
$env:HF_HOME = Join-Path $Root ".cache\huggingface"
$env:HUGGINGFACE_HUB_CACHE = Join-Path $Root ".cache\huggingface\hub"
$env:TRANSFORMERS_CACHE = Join-Path $Root ".cache\huggingface\transformers"
$env:TEMP = Join-Path $Root ".cache\tmp"
$env:TMP = $env:TEMP

New-Item -ItemType Directory -Force -Path $env:OLLAMA_MODELS, $env:HF_HOME, $env:HUGGINGFACE_HUB_CACHE, $env:TEMP | Out-Null

Write-Host "OLLAMA_MODELS=$env:OLLAMA_MODELS"
Write-Host "HF_HOME=$env:HF_HOME"
Write-Host "Using: $OllamaExe"

Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Важно: serve должен унаследовать env → стартуем через cmd set
$cmd = @(
    "set `"OLLAMA_MODELS=$($env:OLLAMA_MODELS)`"",
    "set `"OLLAMA_HOME=$($env:OLLAMA_HOME)`"",
    "set `"TEMP=$($env:TEMP)`"",
    "set `"TMP=$($env:TMP)`"",
    "`"$OllamaExe`" serve"
) -join " && "

Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -WindowStyle Hidden
Start-Sleep -Seconds 4

& $OllamaExe --version
try {
    $tags = Invoke-RestMethod "http://127.0.0.1:11434/api/tags"
    $names = @($tags.models | ForEach-Object { $_.name })
    Write-Host ("models: " + ($(if ($names.Count) { $names -join ", " } else { "(empty)" })))
} catch {
    Write-Host "API not ready yet: $_"
}

Write-Host ""
Write-Host "Next:  powershell -File .\scripts\pull_qwen.ps1"
