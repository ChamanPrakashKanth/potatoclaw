<#
.SYNOPSIS
    PotatoClaw V3 Master Posting Hub & Autonomous Browser Agent
.DESCRIPTION
    Launches concise factual news posting to X, non-Premium thread creation,
    and autonomous browser interactions powered by Spark-X2.5-4B reasoning,
    Qwen2.5-0.5B browser policy, and deterministic verification.
.EXAMPLE
    .\post_all.ps1
    .\post_all.ps1 x tech
    .\post_all.ps1 x tech --browser
    .\post_all.ps1 thread "Long article text to split into X thread..."
    .\post_all.ps1 browser "Open https://x.com and check home page"
    .\post_all.ps1 test
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONDONTWRITEBYTECODE = "1"

$PythonExe = "C:\Program Files\Python38\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        $PythonExe = "python.exe"
    } else {
        Write-Host "[!] Python 3 was not found on your system." -ForegroundColor Red
        exit 1
    }
}

$ScriptPath = Join-Path $PSScriptRoot "scripts\post_all_hub.py"
& $PythonExe $ScriptPath $args
