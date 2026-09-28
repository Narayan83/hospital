@echo off
REM Double-click this file in Explorer to start HMS (backend + desktop)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\dev.ps1"
if errorlevel 1 pause
