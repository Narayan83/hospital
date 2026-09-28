@echo off
REM Double-click or run from cmd: scripts\dev.cmd
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1"
pause
