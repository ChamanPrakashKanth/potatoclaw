@echo off
setlocal
chcp 65001 >nul
title PotatoClaw - X News ^& Autonomous Browser Agent Hub
color 0A

echo ======================================================================
echo   POTATOCLAW V3 - X POSTING HUB ^& AUTONOMOUS BROWSER AGENT
echo   Spark-X2.5-4B (11435) ^| Qwen2.5-0.5B (11436) ^| CDP Browser
echo ======================================================================
echo.

:: 0. Enforce Zero-Cache Rule (Every start is fresh)
set PYTHONDONTWRITEBYTECODE=1

:: 1. Check Python
set "PYTHON_EXE=C:\Program Files\Python38\python.exe"
if not exist "%PYTHON_EXE%" (
    where python.exe >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=python.exe"
    ) else (
        echo [!] Python was not found on your system. Please install Python 3.
        pause
        endlocal & exit /b 1
    )
)

:: 2. Launch the Master Hub
pushd "%~dp0"
"%PYTHON_EXE%" "%~dp0scripts\post_all_hub.py" %*
set "POTATO_EXIT=%ERRORLEVEL%"
popd

echo.
echo ======================================================================
if not "%POTATO_EXIT%"=="0" (
    echo   Process failed with exit code %POTATO_EXIT%.
) else (
    echo   Process completed successfully.
)
echo   Press any key to close this window...
echo ======================================================================
pause >nul
endlocal & exit /b %POTATO_EXIT%
