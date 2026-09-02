@echo off
chcp 65001 >nul
title PotatoClaw - AI Shorts and Video Generator (Pexels + FFmpeg)
color 0D

echo ======================================================================
echo   POTATOCLAW SHORTS CREATOR (PEXELS API + FFMPEG)
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

:: 2. Launch the Shorts Generator
"%PYTHON_EXE%" "%~dp0scripts\shorts_generator.py" %*

if %errorlevel% neq 0 (
    echo.
    echo [!] Process exited with status %errorlevel%
    pause
)
