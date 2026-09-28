# Server PC: start backend (PostgreSQL must already be running) -> open desktop
# Launched by Start-HMS.bat using System32 PowerShell 5+.
param([string]$InstallRoot = "")

$ErrorActionPreference = "Stop"
$root = if ($InstallRoot) { (Resolve-Path $InstallRoot).Path } else { Split-Path $PSScriptRoot -Parent }

$env:HMS_ROOT = $root
$env:HMS_CONFIG_FILE = Join-Path $root "config\hms.env"
$env:HMS_LISTEN_ALL = "true"

# Refuse to start backend on a client PC (common mis-install).
$configPath = $env:HMS_CONFIG_FILE
if (Test-Path $configPath) {
    $role = ""
    $baseUrl = ""
    Get-Content $configPath -Encoding utf8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -match '^\s*HMS_ROLE\s*=\s*(.+)$') { $role = $Matches[1].Trim().ToLower() }
        if ($line -match '^\s*BASE_URL\s*=\s*(.+)$') { $baseUrl = $Matches[1].Trim() }
    }
    if ($role -eq "client" -or ($baseUrl -and $baseUrl -notmatch "127\.0\.0\.1|localhost")) {
        Write-Host ""
        Write-Host "This PC is configured as a CLIENT (BASE_URL=$baseUrl)." -ForegroundColor Yellow
        Write-Host "Do NOT use Start HMS (Server) here." -ForegroundColor Yellow
        Write-Host "Use: Start HMS Desktop  (or scripts\Start-HMS-Desktop-Only.bat)" -ForegroundColor Green
        Write-Host ""
        Write-Host "If this should be the server PC, edit config\hms.env:" -ForegroundColor DarkGray
        Write-Host "  HMS_ROLE=server" -ForegroundColor DarkGray
        Write-Host "  BASE_URL=http://127.0.0.1:8010" -ForegroundColor DarkGray
        throw "Client PC - use Start HMS Desktop only"
    }
}

& (Join-Path $PSScriptRoot "Check-HMS-Update.ps1") -InstallRoot $root

$backend = Join-Path $root "backend\HMS Backend.exe"
$desktop = Join-Path $root "desktop\HMS Desktop.exe"
$blog = Join-Path $root "logs\backend.log"

Write-Host ""
Write-Host "HMS Server - $root" -ForegroundColor Cyan
Write-Host "Config: $env:HMS_CONFIG_FILE" -ForegroundColor Cyan
Write-Host "(Database must be installed and running separately)" -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Path $backend)) { throw "Missing: $backend" }
if (-not (Test-Path $desktop)) {
    Write-Host "Missing desktop app: $desktop" -ForegroundColor Red
    Write-Host "Put HMS-Update.zip in updates\ and Start HMS again, or run HMS-Setup.exe once." -ForegroundColor Yellow
    throw "Missing: $desktop"
}
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null

Write-Host "Stopping any old HMS processes..."
$prev = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
taskkill /F /IM "HMS Backend.exe" /T 2>$null | Out-Null
taskkill /F /IM "HMS Desktop.exe" /T 2>$null | Out-Null
$ErrorActionPreference = $prev
Start-Sleep -Seconds 2
# Second pass - leftover children from failed migrations
$prev = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
taskkill /F /IM "HMS Backend.exe" /T 2>$null | Out-Null
$ErrorActionPreference = $prev
Start-Sleep -Seconds 1

Write-Host "Starting backend..."
Start-Process cmd -ArgumentList "/c", "cd /d `"$root`" && set HMS_ROOT=$root && set HMS_CONFIG_FILE=$($env:HMS_CONFIG_FILE) && set HMS_LISTEN_ALL=true && `"$backend`" >> `"$blog`" 2>&1" -WindowStyle Minimized

$ready = $false
for ($i = 1; $i -le 45; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:8010/health" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    if ($i % 5 -eq 0) { Write-Host "  loading... ($($i * 2)s)" -ForegroundColor DarkGray }
}

if (-not $ready) {
    Write-Host "Backend failed. Check: $blog" -ForegroundColor Red
    if (Test-Path $blog) { Get-Content $blog -Tail 25 }
    Write-Host ""
    Write-Host "If log says Alembic timed out: open Task Manager, end ALL 'HMS Backend.exe'," -ForegroundColor Yellow
    Write-Host "confirm PostgreSQL is running, check DATABASE_URL in config\hms.env, then retry." -ForegroundColor Yellow
    throw "Backend not running. Check DATABASE_URL in config\hms.env"
}

Write-Host "Backend OK" -ForegroundColor Green
if (-not (Test-Path $desktop)) {
    throw "Missing: $desktop (update may have failed - check logs\update.log)"
}
Start-Process -FilePath $desktop -WorkingDirectory $root
Write-Host "Done. Login: admin@admin.com / admin123" -ForegroundColor Green
