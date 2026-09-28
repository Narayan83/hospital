@echo off
setlocal EnableExtensions
REM Client launcher — pure batch (works even when PowerShell is only v2.0).
REM HMS Desktop requires Windows 10 or later (Python 3.12 / PySide6).

cd /d "%~dp0.."
set "HMS_ROOT=%CD%"
set "HMS_CONFIG_FILE=%HMS_ROOT%\config\hms.env"
set "DESKTOP_EXE=%HMS_ROOT%\desktop\HMS Desktop.exe"
set "LOG_DIR=%HMS_ROOT%\logs"
set "LAUNCH_LOG=%LOG_DIR%\desktop-launcher.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
(
  echo Logs are written in this folder.
  echo Files: desktop-launcher.log , desktop.log
  echo Install folder: %HMS_ROOT%
) > "%LOG_DIR%\READ_ME_LOGS_ARE_HERE.txt"

call :log "=== Start HMS Desktop Only ==="
call :log "InstallRoot=%HMS_ROOT%"
call :log "Config=%HMS_CONFIG_FILE%"
call :log "DesktopExe=%DESKTOP_EXE%"
ver >> "%LAUNCH_LOG%" 2>&1

REM Win10/11 expose CurrentMajorVersionNumber=10. Win7/8 do not (or are < 10).
REM Do NOT check api-ms-win-core-path-*.dll as a file — API sets are virtual on Win10+.
set "WIN_MAJOR="
for /f "tokens=3" %%V in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v CurrentMajorVersionNumber 2^>nul') do set "WIN_MAJOR=%%V"
if not defined WIN_MAJOR set "WIN_MAJOR=0"
if %WIN_MAJOR% LSS 10 (
  call :log "ERROR: Unsupported Windows (CurrentMajorVersionNumber=%WIN_MAJOR%)"
  call :log "HMS Desktop requires Windows 10 or Windows 11."
  call :msg "HMS Desktop needs Windows 10 or Windows 11.#n#Windows 7 / 8 are not supported.#n##n#Log: %LAUNCH_LOG%"
  pause
  exit /b 1
)
call :log "Windows major version=%WIN_MAJOR% (OK)"

if not exist "%HMS_CONFIG_FILE%" (
  call :log "ERROR: Missing config\hms.env"
  call :msg "Missing config\hms.env#n##n#Set BASE_URL=http://SERVER_IP:8010"
  pause
  exit /b 1
)

REM Update first so a missing desktop\ folder can be restored from HMS-Update.zip.
set "PS51=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%PS51%" (
  "%PS51%" -NoProfile -ExecutionPolicy Bypass -Command "if ($PSVersionTable.PSVersion.Major -ge 5) { exit 0 } else { exit 1 }" >nul 2>&1
  if not errorlevel 1 (
    call :log "Running update check..."
    "%PS51%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Check-HMS-Update.ps1" -InstallRoot "%HMS_ROOT%" >> "%LAUNCH_LOG%" 2>&1
  ) else (
    call :log "Skip update check: PowerShell older than 5.0"
  )
) else (
  call :log "Skip update check: PowerShell not found"
)

if not exist "%DESKTOP_EXE%" (
  call :log "ERROR: Missing desktop EXE after update check"
  call :msg "Missing: %DESKTOP_EXE%#n##n#Copy HMS-Update.zip to the server updates share and retry,#n#or run HMS-Setup.exe and choose Client once."
  pause
  exit /b 1
)

call :log "Starting desktop EXE..."
echo Logs folder: %LOG_DIR%
echo If login fails, open: %LOG_DIR%\desktop.log

start "HMS Desktop" /D "%HMS_ROOT%" /WAIT "%DESKTOP_EXE%"
set "EXITCODE=%ERRORLEVEL%"
call :log "Desktop exit code=%EXITCODE%"

if not "%EXITCODE%"=="0" (
  call :log "ERROR: Desktop failed to start or exited with code %EXITCODE%"
  call :msg "HMS Desktop did not start (code %EXITCODE%).#n##n#Check log:#n#%LAUNCH_LOG%#n##n#On Windows 10, install Microsoft VC++ Redistributable x64 if a DLL error appears."
  pause
  exit /b %EXITCODE%
)

call :log "Desktop process finished normally."
endlocal
exit /b 0

:log
echo %DATE% %TIME% ^| %~1>> "%LAUNCH_LOG%"
echo %~1
goto :eof

:msg
REM Read message from env so paths with backslashes are not broken by JS string escapes.
set "HMS_MSG=%~1"
mshta "javascript:var sh=new ActiveXObject('WScript.Shell');var t=sh.Environment('Process')('HMS_MSG');sh.Popup(String(t).split('#n#').join('\r\n'),0,'HMS Desktop',16);close();" >nul 2>&1
set "HMS_MSG="
goto :eof
