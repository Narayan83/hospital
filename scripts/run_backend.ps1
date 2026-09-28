# Terminal 1 — backend API only
#   cd D:\fullstack\others\hospital
#   .\scripts\run_backend.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\lib\hms.ps1"

Initialize-HmsBackend

Write-Host "Creating database if needed..."
Ensure-HmsDatabase

$port = Get-HmsBackendPort
$base = Get-HmsBackendBaseUrl

Write-Host ""
Write-Host "Starting API at $base" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

uvicorn app.main:app --reload --host 127.0.0.1 --port $port
