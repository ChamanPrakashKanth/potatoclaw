<#
.SYNOPSIS
    PotatoClaw Shorts & Video Generator (Pexels API + FFmpeg)
.DESCRIPTION
    Curates breaking Tech, Defence, and Physics stories, fetches matching 9:16 stock footage from Pexels,
    renders vertical HD Shorts with dynamic text overlays, and prepares 1-click posting for X, YouTube Shorts & TikTok.
#>

param(
    [Parameter(Position=0)]
    [string]$Category
)

$PythonExe = "C:\Program Files\Python38\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        $PythonExe = $PythonCmd.Source
    } else {
        Write-Host "[!] Python 3 was not found. Please install Python." -ForegroundColor Red
        exit 1
    }
}

$ScriptPath = Join-Path $PSScriptRoot "scripts\shorts_generator.py"

if ($Category) {
    & $PythonExe $ScriptPath $Category
} else {
    & $PythonExe $ScriptPath
}
