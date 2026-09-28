# Client PC: check for updates, then open desktop only.
# Prefer Start-HMS-Desktop-Only.bat (works on PowerShell 2.0 clients).
param([string]$InstallRoot = "")

$ErrorActionPreference = "Stop"
$root = if ($InstallRoot) { (Resolve-Path $InstallRoot).Path } else { Split-Path $PSScriptRoot -Parent }
$desktop = Join-Path $root "desktop\HMS Desktop.exe"
$config = Join-Path $root "config\hms.env"
$logDir = Join-Path $root "logs"
$launcherLog = Join-Path $logDir "desktop-launcher.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-LauncherLog([string]$Message) {
    $stamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    "$stamp | $Message" | Out-File -FilePath $launcherLog -Append -Encoding utf8
    Write-Host $Message
}

Write-LauncherLog "=== Start HMS Desktop Only ==="
Write-LauncherLog "InstallRoot=$root"
Write-LauncherLog "Config=$config"
Write-LauncherLog "DesktopExe=$desktop"

if (-not (Test-Path $config)) {
    Write-LauncherLog "ERROR: Missing config\hms.env"
    throw "Missing: $config - run installer again or copy config\hms.env from the server package."
}

# Same env vars the server launcher sets, so the EXE always finds config + logs.
$env:HMS_ROOT = $root
$env:HMS_CONFIG_FILE = $config

# Read BASE_URL for a clear pre-flight message.
$baseUrl = "http://127.0.0.1:8010"
Get-Content $config -ErrorAction SilentlyContinue | ForEach-Object {
    $line = $_.Trim()
    if ($line -match '^\s*BASE_URL\s*=\s*(.+)$') {
        $baseUrl = $Matches[1].Trim()
    }
}
Write-LauncherLog "BASE_URL=$baseUrl"

# Stop any wrongly started local backend on a client PC (from Server-role mis-install).
$prev = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
taskkill /F /IM "HMS Backend.exe" /T 2>$null | Out-Null
$ErrorActionPreference = $prev

if ($baseUrl -match '127\.0\.0\.1|localhost') {
    Write-Host ""
    Write-Host "WARNING: BASE_URL points to this PC ($baseUrl)." -ForegroundColor Yellow
    Write-Host "On a client PC edit: $config" -ForegroundColor Yellow
    Write-Host "  HMS_ROLE=client" -ForegroundColor Yellow
    Write-Host "  BASE_URL=http://SERVER_IP:8010" -ForegroundColor Yellow
    Write-Host "  UPDATE_PATH=\\SERVER-PC-NAME\HMSUpdates" -ForegroundColor Yellow
    Write-Host ""
    Write-LauncherLog "WARNING: BASE_URL is localhost - client will fail unless backend runs on this PC"
}

# Update first so a missing desktop\ can be restored from HMS-Update.zip.
try {
    & (Join-Path $PSScriptRoot "Check-HMS-Update.ps1") -InstallRoot $root
} catch {
    Write-LauncherLog "Update check failed (continuing): $($_.Exception.Message)"
}

if (-not (Test-Path $desktop)) {
    Write-LauncherLog "ERROR: Missing desktop EXE after update check"
    Write-Host "Missing: $desktop" -ForegroundColor Red
    Write-Host "Put HMS-Update.zip on the server share (UPDATE_PATH) and retry, or run HMS-Setup.exe (Client) once." -ForegroundColor Yellow
    throw "Missing: $desktop"
}

Write-LauncherLog "Starting desktop EXE..."
# Child inherits $env:HMS_ROOT / HMS_CONFIG_FILE from this process.
Start-Process -FilePath $desktop -WorkingDirectory $root
Write-LauncherLog "Desktop process started. App log: $(Join-Path $logDir 'desktop.log')"
Write-Host "If login fails, open: $logDir\desktop.log" -ForegroundColor DarkGray
