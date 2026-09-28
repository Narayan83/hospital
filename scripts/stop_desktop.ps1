# Stop HMS desktop app (python running app.main)
$ErrorActionPreference = "SilentlyContinue"

$stopped = $false
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
    if ($_.CommandLine -like "*hospital*app.main*") {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host "Stopped desktop process (PID $($_.ProcessId))."
        $stopped = $true
    }
}

if (-not $stopped) {
    Write-Host "No HMS desktop process found. Close the HMS window or kill python.exe from Task Manager."
}
