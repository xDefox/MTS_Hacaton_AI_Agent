# Ollama только на D: проекта.
# Portable CLI часто пишет: "could not locate ollama app"
# Поэтому: serve вручную + pull через API (curl), без `ollama pull`.

$ErrorActionPreference = "Stop"
$Root = "D:\HUH\MTS_Hacaton_AI_Agent"
$Exe = if (Test-Path "D:\HUH\ollama\install\ollama.exe") {
    "D:\HUH\ollama\install\ollama.exe"
} else {
    Join-Path $Root "ollama-windows-amd64\ollama.exe"
}

# НЕ использовать имя переменной $home — в PowerShell это reserved!
$OllamaHome = Join-Path $Root ".ollama"
$OllamaModels = Join-Path $Root ".ollama\models"
$TmpDir = Join-Path $Root ".cache\tmp"
New-Item -ItemType Directory -Force -Path $OllamaModels, $TmpDir | Out-Null

Write-Host "OLLAMA_HOME=$OllamaHome"
Write-Host "OLLAMA_MODELS=$OllamaModels"

Get-Process ollama, curl -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$cmd = "set `"OLLAMA_HOME=$OllamaHome`" && set `"OLLAMA_MODELS=$OllamaModels`" && set `"TEMP=$TmpDir`" && set `"TMP=$TmpDir`" && `"$Exe`" serve"
Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" -ArgumentList "/c", $cmd -WindowStyle Minimized

$ok = $false
for ($i = 0; $i -lt 15; $i++) {
    try { Invoke-RestMethod "http://127.0.0.1:11434/api/tags" | Out-Null; $ok = $true; break }
    catch { Start-Sleep -Seconds 1 }
}
if (-not $ok) { throw "Ollama API not up on :11434" }
Write-Host "serve OK (do NOT run another ollama serve)"

$body = Join-Path $TmpDir "pull_body.json"
$log = Join-Path $TmpDir "pull.jsonl"
Set-Content -Path $body -Value '{"name":"qwen2.5:3b"}' -Encoding ascii
Remove-Item $log -ErrorAction SilentlyContinue

$curl = "$env:SystemRoot\System32\curl.exe"
Write-Host "Pulling qwen2.5:3b via API (watch $log)..."
& $curl -N -X POST "http://127.0.0.1:11434/api/pull" `
    -H "Content-Type: application/json" `
    --data-binary "@$body" `
    --max-time 7200 `
    -o $log
if ($LASTEXITCODE -ne 0) { throw "curl pull failed: $LASTEXITCODE" }

Write-Host "--- last log lines ---"
Get-Content $log -Tail 8
Write-Host "--- models ---"
(Invoke-RestMethod "http://127.0.0.1:11434/api/tags").models | ForEach-Object { $_.name }
$sum = (Get-ChildItem $OllamaModels -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
Write-Host ("Stored on D: {0:N1} MB" -f ($sum / 1MB))
