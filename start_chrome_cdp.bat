@echo off
chcp 65001 >nul
title PotatoClaw - Chrome CDP Remote Debugging Launcher (Port 9222)
color 0B

echo ======================================================================
echo   POTATOCLAW CHROME CDP LAUNCHER (REMOTE DEBUGGING PORT 9222)
echo ======================================================================
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0scripts\launch-chrome-debug.ps1"
