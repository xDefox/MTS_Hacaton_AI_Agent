# Скачать модель qwen2.5:3b ТОЛЬКО в D:\...\MTS_Hacaton_AI_Agent\.ollama\models
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OllamaHome = Join-Path $ProjectRoot ".ollama"
$OllamaModels = Join-Path $OllamaHome "models"
New-Item -ItemType Directory -Force -Path $OllamaHome, $OllamaModels | Out-Null

$env:OLLAMA_HOME = $OllamaHome
$env:OLLAMA_MODELS = $OllamaModels
$env:OLLAMA_HOST = "127.0.0.1:11434"

$Candidates = @(
    "D:\HUH\ollama\install\ollama.exe",
    (Join-Path $ProjectRoot "ollama-windows-amd64\ollama.exe"),
    (Join-Path $ProjectRoot "ollama\ollama.exe")
)
$OllamaExe = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $OllamaExe) { throw "ollama.exe не найден на D:" }

Write-Host "Модели будут в: $OllamaModels"
Write-Host "Нужно свободно ~2.5+ ГБ на D:"

# убедиться что serve жив
try {
    $null = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 2
} catch {
    Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Minimized
    Start-Sleep -Seconds 4
}

& $OllamaExe pull qwen2.5:3b
& $OllamaExe list
Write-Host "Готово. Проверка: curl http://127.0.0.1:11434/api/tags"
