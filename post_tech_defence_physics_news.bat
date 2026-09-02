@echo off
chcp 65001 >nul
title PotatoClaw - X (Twitter) Tech, Defence and Physics News Engine
color 0B

echo ======================================================================
echo   POTATOCLAW X-ENGINE: TECH, DEFENCE ^& PHYSICS NEWS POSTER
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

:: 2. Launch the interactive News and X Posting Engine
"%PYTHON_EXE%" "%~dp0scripts\x_news_engine.py" %*

if %errorlevel% neq 0 (
    echo.
    echo [!] Process exited with status %errorlevel%
    pause
)
