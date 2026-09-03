@echo off
chcp 65001 >nul
title PotatoClaw - PotatoAI Agent Interactive Chat (Spark-X2.5-4B + BMW)
color 0E

echo ======================================================================
echo   POTATOCLAW AI AGENT CHAT (SPARK-X2.5-4B + BMW ARCHITECTURE)
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

:: 2. Launch Interactive Potato AI Agent Chat
"%PYTHON_EXE%" "%~dp0scripts\potato_chat.py" %*

echo.
echo ======================================================================
echo   Session ended. Press any key to close this window...
echo ======================================================================
pause >nul
