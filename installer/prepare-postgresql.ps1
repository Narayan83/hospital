#Requires -Version 5.1
<#
  Stage PostgreSQL portable binaries (bin + lib + share only — no pgAdmin/docs).
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$StageDir
)

$ErrorActionPreference = "Stop"
$StageDir = (Resolve-Path $StageDir).Path
$pgTarget = Join-Path $StageDir "postgresql"
$cacheDir = Join-Path $PSScriptRoot "cache"
$zipPath = Join-Path $cacheDir "postgresql-16.4-1-windows-x64-binaries.zip"
$cachePg = Join-Path $cacheDir "pg-extract\pgsql"
$pgUrl = "https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip"

if (Test-Path (Join-Path $pgTarget "bin\postgres.exe")) {
    Write-Host "PostgreSQL already staged." -ForegroundColor Gray
    return
}

if (-not (Test-Path (Join-Path $cachePg "bin\postgres.exe"))) {
    New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
    if (-not (Test-Path $zipPath)) {
        Write-Host "Downloading PostgreSQL 16 portable..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $pgUrl -OutFile $zipPath -UseBasicParsing
    }
    Write-Host "Extracting PostgreSQL (one-time cache)..." -ForegroundColor Cyan
    $tempExtract = Join-Path $cacheDir "pg-extract"
    if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $tempExtract
}

Write-Host "Copying PostgreSQL from cache..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $pgTarget | Out-Null
Copy-Item (Join-Path $cachePg "*") $pgTarget -Recurse -Force

# HMS only needs the database server — drop huge optional folders (~200+ MB, faster builds)
foreach ($drop in @("pgAdmin 4", "doc", "include", "symbols")) {
    $path = Join-Path $pgTarget $drop
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force
        Write-Host "  removed postgresql\$drop" -ForegroundColor DarkGray
    }
}

Write-Host "PostgreSQL staged at $pgTarget" -ForegroundColor Green
