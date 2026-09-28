@echo off
setlocal EnableExtensions
REM Server launcher — always use PowerShell 5+ from System32 (not the old v2 "powershell" on PATH).

cd /d "%~dp0.."
set "HMS_ROOT=%CD%"
set "LOG_DIR=%HMS_ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "PS51=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS51%" (
  echo PowerShell not found at:
  echo   %PS51%
  echo Install Windows Management Framework 5.1, then try again.
  echo %DATE% %TIME% ^| ERROR: PowerShell 5+ missing>> "%LOG_DIR%\server-launcher.log"
  pause
  exit /b 1
)

"%PS51%" -NoProfile -ExecutionPolicy Bypass -Command "if ($PSVersionTable.PSVersion.Major -ge 5) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo This PC has PowerShell older than 5.0.
  echo Install Windows Management Framework 5.1, then try again.
  echo %DATE% %TIME% ^| ERROR: PowerShell version too old>> "%LOG_DIR%\server-launcher.log"
  pause
  exit /b 1
)

"%PS51%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-HMS.ps1" -InstallRoot "%HMS_ROOT%"
if errorlevel 1 (
  echo.
  echo Start HMS failed. Check: %LOG_DIR%
  pause
  exit /b 1
)
endlocal
exit /b 0
