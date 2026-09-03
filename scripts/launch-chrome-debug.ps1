<#
.SYNOPSIS
    Launches Google Chrome with Remote Debugging (CDP) & OpenClaw Extension Support.
.DESCRIPTION
    Enables PotatoClaw (OpenClaw) to control Chrome tabs, navigate pages, click, type, and extract content.
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " PotatoClaw Chrome Controller (Codex-Style Browser Power)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Chrome Executable Paths
$ChromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$ChromeExe = $null
foreach ($path in $ChromePaths) {
    if (Test-Path $path) {
        $ChromeExe = $path
        break
    }
}

if (-not $ChromeExe) {
    Write-Host "[!] Could not locate chrome.exe automatically." -ForegroundColor Red
    Write-Host "Please start Chrome with: chrome.exe --remote-debugging-port=9222" -ForegroundColor Yellow
    exit 1
}

# 2. Chrome Extension Path
$WorkspaceDir = (Get-Item -Path $PSScriptRoot).Parent.FullName
$ExtensionDir = Join-Path $WorkspaceDir "extensions\browser\chrome-extension"

Write-Host "`n[1/2] Chrome Extension Available at:" -ForegroundColor Yellow
Write-Host "  $ExtensionDir" -ForegroundColor Green
Write-Host "  -> To install in Chrome: Go to chrome://extensions -> Enable 'Developer mode' -> 'Load unpacked' -> Select this folder." -ForegroundColor Gray

# 3. Check / Launch Chrome with CDP Remote Debugging
Write-Host "`n[2/2] Checking Chrome Remote Debugging on Port 9222..." -ForegroundColor Yellow
$PortOpen = $false
try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:9222/json/version" -Method Get -TimeoutSec 2 -ErrorAction Stop
    $PortOpen = $true
    Write-Host "  -> Chrome CDP is already active on http://127.0.0.1:9222 (Browser: $($r.Browser))" -ForegroundColor Green
} catch {
    Write-Host "  -> Launching Chrome with CDP port 9222 and dev profile..." -ForegroundColor Yellow
    $ProfileDir = "C:\chrome-dev-profile"
    if (-not (Test-Path $ProfileDir)) {
        New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
    }
    
    Start-Process -FilePath $ChromeExe -ArgumentList "--remote-debugging-port=9222", "--remote-allow-origins=*", "--user-data-dir=`"$ProfileDir`"", "--no-first-run", "--no-default-browser-check"
    
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:9222/json/version" -Method Get -TimeoutSec 3 -ErrorAction Stop
        Write-Host "  -> Chrome launched and CDP active! (Browser: $($r.Browser))" -ForegroundColor Green
    } catch {
        Write-Host "  -> Chrome started. Waiting for connection on port 9222..." -ForegroundColor Yellow
    }
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " PotatoClaw is armed with Codex-like Chrome control!" -ForegroundColor Cyan
Write-Host " You can now ask PotatoClaw to browse, click, and search web pages!" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
