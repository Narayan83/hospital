#Requires -Version 5.1
<#
  Create pre-initialized PostgreSQL data for customer installs (skips slow initdb on site).
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$StageDir
)

$ErrorActionPreference = "Stop"
$StageDir = (Resolve-Path $StageDir).Path
$pgBin = Join-Path $StageDir "postgresql\bin"
$pgData = Join-Path $StageDir "data\pgdata"
$pwFile = Join-Path $StageDir "config\postgres.pw"

if (-not (Test-Path (Join-Path $pgBin "initdb.exe"))) {
    Write-Host "Skip pgdata prep - PostgreSQL binaries not in stage yet." -ForegroundColor Yellow
    exit 0
}

if (Test-Path (Join-Path $pgData "PG_VERSION")) {
    Write-Host "Pre-initialized pgdata already exists." -ForegroundColor Gray
    exit 0
}

function Write-TextFileNoBom {
    param([string]$Path, [string[]]$Lines)
    $dir = Split-Path $Path -Parent
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($Path, $Lines, $utf8)
}

Write-Host "Pre-initializing PostgreSQL data (for customer install)..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path (Split-Path $pgData -Parent), (Split-Path $pwFile -Parent) | Out-Null

if (Test-Path $pgData) { Remove-Item $pgData -Recurse -Force }
New-Item -ItemType Directory -Force -Path $pgData | Out-Null

Write-TextFileNoBom -Path $pwFile -Lines @("postpass")

$initdb = Join-Path $pgBin "initdb.exe"
& $initdb -D $pgData -U postgres -A scram-sha-256 --pwfile=$pwFile --encoding=UTF8 --locale=C
if ($LASTEXITCODE -ne 0) { throw "initdb failed during build." }

$conf = Join-Path $pgData "postgresql.conf"
$confLines = Get-Content $conf | ForEach-Object {
    if ($_ -match '^\s*#?\s*listen_addresses\s*=') { "listen_addresses = '*'" }
    elseif ($_ -match '^\s*#?\s*port\s*=') { "port = 5432" }
    else { $_ }
}
Write-TextFileNoBom -Path $conf -Lines $confLines

$hba = Join-Path $pgData "pg_hba.conf"
$hbaLines = Get-Content $hba
$hbaLines += @("", "host all all 127.0.0.1/32 scram-sha-256", "host all all 0.0.0.0/0 scram-sha-256")
Write-TextFileNoBom -Path $hba -Lines $hbaLines

Write-Host "Pre-initialized pgdata ready at $pgData" -ForegroundColor Green
