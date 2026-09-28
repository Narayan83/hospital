# Shared helpers for HMS PowerShell scripts (dot-source from scripts/*.ps1)

function Get-HmsRoot {
    # scripts/lib -> scripts -> project root
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Get-HmsBackendDir {
    return Join-Path (Get-HmsRoot) "backend"
}

function Get-HmsDesktopDir {
    return Join-Path (Get-HmsRoot) "desktop"
}

function Get-HmsBackendPort {
    $backend = Get-HmsBackendDir
    $envFile = Join-Path $backend ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*BACKEND_PORT\s*=\s*(\d+)\s*$') {
                return [int]$Matches[1]
            }
        }
    }
    if ($env:BACKEND_PORT) {
        return [int]$env:BACKEND_PORT
    }
    return 8010
}

function Get-HmsBackendBaseUrl {
    $backend = Get-HmsBackendDir
    $envFile = Join-Path $backend ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*BASE_URL\s*=\s*(\S+)\s*$') {
                return $Matches[1].TrimEnd('/').Replace("://localhost:", "://127.0.0.1:")
            }
        }
    }
    return "http://127.0.0.1:$(Get-HmsBackendPort)"
}

function Get-HmsHealthUrl {
    return "$(Get-HmsBackendBaseUrl)/health"
}

function Set-HmsDesktopEnv {
    $port = Get-HmsBackendPort
    $base = Get-HmsBackendBaseUrl
    $env:BACKEND_PORT = "$port"
    $env:BASE_URL = $base
    $env:BACKEND_HOST = "127.0.0.1"
}

function Test-HmsBackendHealthy {
    $url = Get-HmsHealthUrl
    try {
        $code = & curl.exe -s -o NUL -w "%{http_code}" --connect-timeout 2 --max-time 4 $url 2>$null
        return "$code" -eq "200"
    } catch {
        return $false
    }
}

function Wait-HmsBackend {
    param(
        [int]$TimeoutSeconds = 90,
        [string]$Message = "Waiting for backend"
    )

    if (Test-HmsBackendHealthy) {
        return $true
    }

    Write-Host "$Message (up to ${TimeoutSeconds}s)..." -ForegroundColor Yellow

    for ($i = 1; $i -le $TimeoutSeconds; $i++) {
        if (Test-HmsBackendHealthy) {
            Write-Host "Backend is ready." -ForegroundColor Green
            return $true
        }
        if ($i % 10 -eq 0) {
            Write-Host "  still waiting... ($i/$TimeoutSeconds s)" -ForegroundColor DarkGray
        }
        Start-Sleep -Seconds 1
    }

    return $false
}

function Initialize-HmsBackend {
    param([switch]$SkipPip)

    $backend = Get-HmsBackendDir
    Set-Location $backend

    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }

    & .\.venv\Scripts\Activate.ps1

    if (-not $SkipPip) {
        pip install -r requirements.txt -q
    }

    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "Created backend\.env from .env.example" -ForegroundColor Yellow
    }
}

function Initialize-HmsDesktop {
    param([switch]$SkipPip)

    $desktop = Get-HmsDesktopDir
    Set-Location $desktop

    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }

    & .\.venv\Scripts\Activate.ps1

    if (-not $SkipPip) {
        pip install -r requirements.txt -q
    }
}

function Start-HmsBackendWindow {
    $backend = Get-HmsBackendDir
    $port = Get-HmsBackendPort
    $base = Get-HmsBackendBaseUrl
    $backendCmd = @"
Set-Location '$backend'
& .\.venv\Scripts\Activate.ps1
Write-Host 'HMS Backend: $base' -ForegroundColor Green
Write-Host 'Health: $base/health' -ForegroundColor Gray
uvicorn app.main:app --reload --host 127.0.0.1 --port $port
"@

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
}

function Ensure-HmsDatabase {
    $backend = Get-HmsBackendDir
    Set-Location $backend
    & .\.venv\Scripts\Activate.ps1
    python ..\scripts\create_hms_db.py
    if ($LASTEXITCODE -ne 0) { throw "Database setup failed." }
    alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Migrations failed." }
}
