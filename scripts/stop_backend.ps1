# Stop HMS backend (uvicorn on configured BACKEND_PORT)
$ErrorActionPreference = "SilentlyContinue"
. "$PSScriptRoot\lib\hms.ps1"

$port = Get-HmsBackendPort
$connections = Get-NetTCPConnection -LocalPort $port -State Listen
foreach ($conn in $connections) {
    $pid = $conn.OwningProcess
    if ($pid) {
        Stop-Process -Id $pid -Force
        Write-Host "Stopped backend process (PID $pid) on port $port."
    }
}

if (-not $connections) {
    Write-Host "No backend running on port $port."
}
