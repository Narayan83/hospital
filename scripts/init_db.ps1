# Run database migrations (requires PostgreSQL installed locally)
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — edit DATABASE_URL if needed."
}

& .\.venv\Scripts\Activate.ps1
alembic upgrade head
Write-Host "Database migrations applied."
