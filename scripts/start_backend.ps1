# Demo backend: YandexGPT + SpeechKit. NO --reload. NO Ollama/Whisper.

$ErrorActionPreference = "Stop"
$Root = "D:\HUH\MTS_Hacaton_AI_Agent"
Set-Location $Root

$env:PYTHONIOENCODING = "utf-8"
$env:LLM_PROVIDER = "yandex"
$env:STT_PROVIDER = "yandex"
$env:TTS_PROVIDER = "yandex"

Write-Host "Stack: EXTERNAL YandexGPT (HTTP REST) + SpeechKit STT/TTS -> data\tts\call_N.ogg"
Write-Host "Starting API..."
Write-Host "DO NOT use --reload during demo."
Write-Host "Need outbound HTTPS to llm.api.cloud.yandex.net (VPN if blocked)."
& (Join-Path $Root ".venv\Scripts\uvicorn.exe") backend.main:app --host 0.0.0.0 --port 8000
