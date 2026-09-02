@echo off
chcp 65001 >nul
title PotatoClaw - Master Automation Hub (X Posts + YouTube Shorts)
color 0A

echo ======================================================================
echo   POTATOCLAW V2 MASTER POSTING HUB (X POSTS + YOUTUBE SHORTS)
echo ======================================================================
echo.

:: 1. Check Python
set "PYTHON_EXE=C:\Program Files\Python38\python.exe"
if not exist "%PYTHON_EXE%" (
    where python.exe >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=python.exe"
    ) else (
        echo [!] Python was not found on your system. Please install Python 3.
        pause
        exit /b 1
    )
)

:: 2. Launch the Master Hub
"%PYTHON_EXE%" "%~dp0scripts\post_all_hub.py" %*

if %errorlevel% neq 0 (
    echo.
    echo [!] Process exited with status %errorlevel%
    pause
)
