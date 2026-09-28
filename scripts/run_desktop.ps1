# Terminal 2 — desktop UI only (start backend first with run_backend.ps1)
#   cd D:\fullstack\others\hospital
#   .\scripts\run_desktop.ps1

param(
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\lib\hms.ps1"

Initialize-HmsDesktop

if (-not $NoWait) {
    if (-not (Test-HmsBackendHealthy)) {
        Write-Host "Backend not detected yet." -ForegroundColor Yellow
        $ready = Wait-HmsBackend -TimeoutSeconds 30 -Message "Waiting for backend"
        if (-not $ready) {
            Write-Host "Backend still not ready. Desktop will open but login may fail." -ForegroundColor Yellow
            Write-Host "Start backend first: .\scripts\run_backend.ps1" -ForegroundColor Gray
        }
    } else {
        Write-Host "Backend is running." -ForegroundColor Green
    }
}

Set-HmsDesktopEnv

Write-Host ""
Write-Host "Starting desktop..." -ForegroundColor Green
Write-Host "API: $(Get-HmsBackendBaseUrl)" -ForegroundColor DarkGray
Write-Host "Login: admin@admin.com / admin123" -ForegroundColor DarkGray
Write-Host ""

python -m app.main
