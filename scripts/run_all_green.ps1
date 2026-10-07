# Полный зелёный прогон: offline suite + LLM golden (нужен ollama serve + qwen2.5:3b)

$ErrorActionPreference = "Stop"
$Root = "D:\HUH\MTS_Hacaton_AI_Agent"
Set-Location $Root

$env:PYTHONIOENCODING = "utf-8"
$env:OLLAMA_HOME = Join-Path $Root ".ollama"
$env:OLLAMA_MODELS = Join-Path $Root ".ollama\models"
$env:LLM_PROVIDER = "local"
$env:Path = "D:\HUH\ollama\install;" + $env:Path

$py = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "=== check ollama ==="
$tags = Invoke-RestMethod "http://127.0.0.1:11434/api/tags"
$names = @($tags.models | ForEach-Object { $_.name })
if (-not ($names | Where-Object { $_ -like "qwen2.5:3b*" })) {
    throw "qwen2.5:3b not loaded. Run scripts\pull_qwen_api.ps1 first. Have: $($names -join ', ')"
}
Write-Host ("models: " + ($names -join ", "))

Write-Host "`n=== offline suite ==="
& $py tests\run_offline_suite.py
if ($LASTEXITCODE -ne 0) { throw "offline suite failed" }

Write-Host "`n=== LLM golden ==="
& $py tests\smoke_hard_routing.py
if ($LASTEXITCODE -ne 0) { throw "LLM golden failed" }

Write-Host "`nALL GREEN"
