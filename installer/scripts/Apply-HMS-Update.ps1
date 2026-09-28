# Runs DB migrations + menu seeds (server PC only).
# Never run on a client PC. Never hang the installer (installer no longer calls this).
param(
    [string]$InstallRoot = "",
    [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = "Continue"
$root = if ($InstallRoot) { (Resolve-Path $InstallRoot).Path } else { Split-Path $PSScriptRoot -Parent }
$backend = Join-Path $root "backend\HMS Backend.exe"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir "update.log"
$config = Join-Path $root "config\hms.env"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-UpdateLog([string]$Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$stamp] $Message" | Out-File $logFile -Append -Encoding utf8
}

function Read-EnvValues([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    foreach ($line in Get-Content $Path -Encoding utf8) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { continue }
        $key, $value = $line -split "=", 2
        $values[$key.Trim()] = $value.Trim()
    }
    return $values
}

function Get-DbEndpoint([string]$DbUrl) {
    if (-not $DbUrl) { return $null }
    if ($DbUrl -match '@([^:/]+):(\d+)/') {
        return @{ Host = $Matches[1]; Port = [int]$Matches[2] }
    }
    if ($DbUrl -match '@([^:/]+)/') {
        return @{ Host = $Matches[1]; Port = 5432 }
    }
    return $null
}

function Test-TcpOpen([string]$HostName, [int]$Port, [int]$TimeoutMs = 2000) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $ok) {
            $client.Close()
            return $false
        }
        $client.EndConnect($iar)
        $client.Close()
        return $true
    }
    catch {
        return $false
    }
}

Write-UpdateLog "Apply-HMS-Update starting (root=$root)"

if (-not (Test-Path $config)) {
    Write-UpdateLog "No config\hms.env - skip"
    exit 0
}

$envValues = Read-EnvValues $config
$role = ($envValues["HMS_ROLE"] -as [string]).Trim().ToLower()
$baseUrl = ($envValues["BASE_URL"] -as [string])

# Client PCs must never start the backend / migrations.
if ($role -eq "client") {
    Write-UpdateLog "HMS_ROLE=client - skip DB setup (desktop-only PC)"
    exit 0
}
if ($baseUrl -and ($baseUrl -notmatch "127\.0\.0\.1|localhost")) {
    Write-UpdateLog "BASE_URL points to remote server ($baseUrl) - skip DB setup (this is a client PC)"
    exit 0
}

if (-not (Test-Path $backend)) {
    Write-UpdateLog "Missing HMS Backend.exe - skip"
    exit 0
}

$ep = Get-DbEndpoint $envValues["DATABASE_URL"]
if ($ep) {
    Write-UpdateLog ("Checking database at {0}:{1}" -f $ep.Host, $ep.Port)
    if (-not (Test-TcpOpen $ep.Host $ep.Port 2000)) {
        Write-UpdateLog "Database not reachable in 2s - skip (will migrate on next Start HMS)"
        exit 0
    }
}

$env:HMS_ROOT = $root
$env:HMS_CONFIG_FILE = $config

try {
    Write-UpdateLog ("Starting HMS Backend.exe --setup-only (timeout {0}s)" -f $TimeoutSeconds)
    $proc = Start-Process -FilePath $backend -ArgumentList "--setup-only" `
        -WorkingDirectory $root -PassThru -WindowStyle Hidden

    if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
        Write-UpdateLog ("TIMEOUT after {0}s - killing setup process" -f $TimeoutSeconds)
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Get-Process -Name "HMS Backend" -ErrorAction SilentlyContinue |
                Stop-Process -Force -ErrorAction SilentlyContinue
        } catch {}
        Write-UpdateLog "Setup skipped - migrations will run on next Start HMS"
        exit 0
    }

    Write-UpdateLog ("--setup-only exit code: {0}" -f $proc.ExitCode)
}
catch {
    Write-UpdateLog ("Error: {0}" -f $_)
}

exit 0
