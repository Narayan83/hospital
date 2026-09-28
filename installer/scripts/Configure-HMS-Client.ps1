# First-time client setup: set server IP in config\hms.env
param(
    [string]$InstallRoot = "",
    [string]$ServerHost = ""
)

$ErrorActionPreference = "Stop"
$root = if ($InstallRoot) { (Resolve-Path $InstallRoot).Path } else { Split-Path $PSScriptRoot -Parent }
$config = Join-Path $root "config\hms.env"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir "client-setup.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-SetupLog([string]$Message) {
    $stamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    "$stamp | $Message" | Out-File -FilePath $logFile -Append -Encoding utf8
}

Write-SetupLog "=== Configure HMS Client ==="
Write-SetupLog "InstallRoot=$root"

if (-not (Test-Path $config)) {
    Write-SetupLog "ERROR: missing $config"
    throw "Missing config file: $config"
}

if (-not $ServerHost) {
    Add-Type -AssemblyName Microsoft.VisualBasic
    $ServerHost = [Microsoft.VisualBasic.Interaction]::InputBox(
        "Enter the HMS server PC IP address or name.`nExample: 192.168.1.10`n`nThis is written to config\hms.env as BASE_URL.",
        "HMS Client Setup",
        "192.168.1.10"
    )
}

$ServerHost = ($ServerHost -as [string]).Trim()
if (-not $ServerHost) {
    Write-SetupLog "User cancelled server host prompt - leaving config unchanged"
    exit 0
}

# Strip accidental scheme/port from typed values.
$ServerHost = $ServerHost -replace '^https?://', ''
$ServerHost = $ServerHost -replace '/.*$', ''
$ServerHost = $ServerHost -replace ':\d+$', ''

$baseUrl = "http://${ServerHost}:8010"
$updatePath = "\\${ServerHost}\HMSUpdates"

$lines = Get-Content $config
$out = foreach ($line in $lines) {
    if ($line -match '^\s*BASE_URL\s*=') {
        "BASE_URL=$baseUrl"
    } elseif ($line -match '^\s*UPDATE_PATH\s*=') {
        "UPDATE_PATH=$updatePath"
    } elseif ($line -match '^\s*HMS_ROLE\s*=') {
        "HMS_ROLE=client"
    } else {
        $line
    }
}
# Ensure HMS_ROLE=client exists even on older configs
if (-not ($out | Where-Object { $_ -match '^\s*HMS_ROLE\s*=' })) {
    $out = @("HMS_ROLE=client") + $out
}
$out | Set-Content -Path $config -Encoding utf8

Write-SetupLog "HMS_ROLE=client"
Write-SetupLog "BASE_URL=$baseUrl"
Write-SetupLog "UPDATE_PATH=$updatePath"
Write-SetupLog "Wrote $config"

Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.MessageBox]::Show(
    "Client configured.`n`nHMS_ROLE=client`nBASE_URL=$baseUrl`nUPDATE_PATH=$updatePath`n`nUse Start HMS Desktop only.`nMake sure the server PC is running Start HMS, and share D:\HMS\updates as HMSUpdates.",
    "HMS Client Setup",
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null
