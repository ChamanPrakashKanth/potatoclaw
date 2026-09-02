<#
.SYNOPSIS
    PotatoClaw V2 Master Posting Hub (X Posts)
.DESCRIPTION
    Launches single-story news posting to X powered by PotatoClaw V2 BMW Agent.
.EXAMPLE
    .\post_all.ps1
    .\post_all.ps1 x tech
    .\post_all.ps1 x physics
    .\post_all.ps1 x defence
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

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
