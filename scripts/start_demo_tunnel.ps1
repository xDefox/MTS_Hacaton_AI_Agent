# Публичный QR для жюри → лёгкий веб МТС на uvicorn :8000 (/app)
# Не Flet :8550: Flutter JS ~10MB, на LTE белый экран минутами.
#
# Нужно уже: uvicorn backend.main:app --port 8000
# Затем:     .\scripts\start_demo_tunnel.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Cf = "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe"
if (-not (Test-Path $Cf)) { $Cf = "$env:ProgramFiles\cloudflared\cloudflared.exe" }
if (-not (Test-Path $Cf)) { throw "cloudflared not found. winget install Cloudflare.cloudflared" }

$port = if ($env:DEMO_TUNNEL_PORT) { $env:DEMO_TUNNEL_PORT } else { "8000" }
$origin = "http://127.0.0.1:$port"
Write-Host "Starting tunnel -> $origin (light MTS web /app) ..."

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $Cf
$psi.Arguments = "tunnel --url $origin"
$psi.RedirectStandardError = $true
$psi.RedirectStandardOutput = $true
$psi.UseShellExecute = $false
$p = [System.Diagnostics.Process]::Start($psi)

$url = $null
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline -and -not $url) {
    $line = $p.StandardError.ReadLine()
    if (-not $line) { Start-Sleep -Milliseconds 200; continue }
    Write-Host $line
    if ($line -match "https://[a-z0-9-]+\.trycloudflare\.com") {
        $url = $Matches[0]
    }
}
if (-not $url) { throw "Tunnel URL not found" }

$env:DEMO_WEB_URL = $url
$envPath = Join-Path $Root ".env"
$envText = if (Test-Path $envPath) { Get-Content $envPath -Raw } else { "" }
if ($envText -match "(?m)^DEMO_WEB_URL=.*$") {
    $envText = $envText -replace "(?m)^DEMO_WEB_URL=.*$", "DEMO_WEB_URL=$url"
} else {
    $envText = $envText.TrimEnd() + "`r`n`r`nDEMO_WEB_URL=$url`r`n"
}
Set-Content -Path $envPath -Value $envText -NoNewline

Set-Location $Root
python scripts/make_demo_qr.py
python scripts/build_presentation.py
Write-Host ""
Write-Host "QR -> $url/app  (лёгкий веб, открывается сразу)"
Write-Host "Keep this window open while jury uses the QR."
$p.WaitForExit()
