# One command: setup + backend (new window) + desktop (this window)
# Run from project root:
#   .\scripts\dev.ps1
# From desktop folder:
#   .\run.ps1
#   ..\scripts\dev.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\lib\hms.ps1"

Write-Host ""
Write-Host "=== HMS Development ===" -ForegroundColor Cyan
Write-Host "Project: $(Get-HmsRoot)" -ForegroundColor DarkGray
Write-Host ""

try {
    Write-Host "[1/4] Backend setup..." -ForegroundColor Yellow
    Initialize-HmsBackend
    Ensure-HmsDatabase

    Write-Host "[2/4] Desktop setup..." -ForegroundColor Yellow
    Initialize-HmsDesktop

    if (Test-HmsBackendHealthy) {
        Write-Host "[3/4] Backend already running." -ForegroundColor Green
    } else {
        Write-Host "[3/4] Starting backend in new window..." -ForegroundColor Yellow
        Start-HmsBackendWindow

        if (-not (Wait-HmsBackend -TimeoutSeconds 90)) {
            Write-Host ""
            Write-Host "Backend did not respond in time." -ForegroundColor Red
            Write-Host "Check the backend PowerShell window for errors." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "If it shows 'Application startup complete', start desktop only:" -ForegroundColor Yellow
            Write-Host "  .\scripts\run_desktop.ps1" -ForegroundColor Gray
            exit 1
        }
    }

    Write-Host "[4/4] Starting desktop..." -ForegroundColor Green
    Write-Host "API: $(Get-HmsBackendBaseUrl)" -ForegroundColor DarkGray
    Write-Host "Login: admin@admin.com / admin123" -ForegroundColor DarkGray
    Write-Host ""

    Set-HmsDesktopEnv
    Set-Location (Get-HmsDesktopDir)
    python -m app.main
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}
