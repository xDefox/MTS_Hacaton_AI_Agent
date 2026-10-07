# Демо-бэкенд: БЕЗ --reload (reload рвёт долгие запросы Whisper/LLM/TTS)

$ErrorActionPreference = "Stop"
$Root = "D:\HUH\MTS_Hacaton_AI_Agent"
Set-Location $Root

$env:PYTHONIOENCODING = "utf-8"
$env:LLM_PROVIDER = "local"
$env:OLLAMA_HOME = Join-Path $Root ".ollama"
$env:OLLAMA_MODELS = Join-Path $Root ".ollama\models"
$env:HF_HOME = Join-Path $Root ".cache\huggingface"
$env:HUGGINGFACE_HUB_CACHE = Join-Path $Root ".cache\huggingface\hub"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

Write-Host "Check Ollama..."
$tags = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -ErrorAction Stop
if (-not ($tags.models.name | Where-Object { $_ -like "qwen2.5:3b*" })) {
    Write-Host "WARN: qwen2.5:3b not in tags. Run scripts\start_ollama_d.ps1 + pull_qwen_api.ps1"
}

Write-Host "Starting API (warmup blocks until Whisper+Ollama ready)..."
Write-Host "DO NOT use --reload during demo."
& (Join-Path $Root ".venv\Scripts\uvicorn.exe") backend.main:app --host 0.0.0.0 --port 8000
