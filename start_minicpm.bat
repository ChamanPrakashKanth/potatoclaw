@echo off
setlocal
chcp 65001 >nul
title PotatoClaw - MiniCPM5-2B Local Model Launcher
color 0B

echo ======================================================================
echo   POTATOCLAW MINICPM5-2B LOCAL MODEL LAUNCHER
echo ======================================================================
echo   Shared chat and X/browser endpoint: http://127.0.0.1:11435/v1
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-minicpm-potato.ps1" %*
set "POTATO_EXIT=%ERRORLEVEL%"

echo.
if not "%POTATO_EXIT%"=="0" echo MiniCPM launcher exited with code %POTATO_EXIT%.
if not "%POTATO_EXIT%"=="0" pause
endlocal & exit /b %POTATO_EXIT%
