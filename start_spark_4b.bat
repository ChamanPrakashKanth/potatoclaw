@echo off
setlocal
title PotatoClaw - MiniCPM5-2B Model Server

echo MiniCPM5-2B - local shared model server
echo API: http://127.0.0.1:11435/v1
echo Context: 2048 tokens / Slots: 1 / GPU layers: 18
echo.

where.exe wsl.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: Windows Subsystem for Linux is not installed.
    if /I not "%~1"=="--check" pause
    exit /b 1
)

if /I "%~1"=="--check" goto check
echo Starting the shared MiniCPM server through the canonical launcher...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-minicpm-potato.ps1"
set "potatoExit=%ERRORLEVEL%"
echo.
if not "%potatoExit%"=="0" echo Server exited with code %potatoExit%. See the error above.
pause
exit /b %potatoExit%

:check
powershell.exe -NoProfile -Command "try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:11435/health' -TimeoutSec 3 -ErrorAction Stop; if ($health.status -eq 'ok') { exit 0 }; exit 2 } catch { exit 1 }"
set "potatoHealth=%ERRORLEVEL%"
if "%potatoHealth%"=="0" echo MiniCPM server is online.
if not "%potatoHealth%"=="0" echo MiniCPM server is offline or not ready.
exit /b %potatoHealth%
