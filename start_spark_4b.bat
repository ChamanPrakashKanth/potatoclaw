@echo off
setlocal
title PotatoClaw - Spark 4B Model Server

echo Spark-X2.5-4B - local model server
echo API: http://127.0.0.1:11435/v1
echo Context: 2048 tokens / Slots: 1 / GPU layers: 26
echo.

where.exe wsl.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: Windows Subsystem for Linux is not installed.
    if /I not "%~1"=="--check" pause
    exit /b 1
)

powershell.exe -NoProfile -Command "try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:11435/health' -TimeoutSec 3 -ErrorAction Stop; if ($health.status -eq 'ok') { exit 0 }; exit 2 } catch { if ($null -ne $_.Exception.Response) { exit 2 }; exit 1 }"
set "potatoHealth=%ERRORLEVEL%"
if "%potatoHealth%"=="0" (
    echo Server is already online. No second model will be started.
    if /I not "%~1"=="--check" pause
    exit /b 0
)
if "%potatoHealth%"=="2" (
    echo A server is responding but is not ready, possibly still loading.
    echo No duplicate server will be started. Try again shortly.
    if /I not "%~1"=="--check" pause
    exit /b 2
)
if /I "%~1"=="--check" (
    echo Server is offline or unreachable.
    exit /b 1
)

echo Starting the installed model in OpenClawGateway WSL...
echo Keep this window open while using the model. Press Ctrl+C to stop it.
echo Startup may take a minute or longer. Wait for the listening message.
echo No configuration files will be changed.
echo.
wsl.exe -d OpenClawGateway -u openclaw --exec /home/openclaw/llama.cpp-spark/build/bin/llama-server -m /home/openclaw/Spark-X2.5-4B-Q4_K_M.gguf -c 2048 -np 1 -fa on -ngl 26 -t 6 --host 127.0.0.1 --port 11435 --alias spark-x2.5-4b:latest
set "potatoExit=%ERRORLEVEL%"
echo.
if not "%potatoExit%"=="0" echo Server exited with code %potatoExit%. See the error above.
pause
exit /b %potatoExit%
