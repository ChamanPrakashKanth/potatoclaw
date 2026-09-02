<#
.SYNOPSIS
    PotatoClaw X (Twitter) News Engine - Tech, Defence & Physics
.DESCRIPTION
    Searches live Tech, Defence, and Physics news, drafts formatted posts, and opens X for manual review & 1-click posting.
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

$ScriptPath = Join-Path $PSScriptRoot "scripts\x_news_engine.py"

if ($Category) {
    & $PythonExe $ScriptPath $Category
} else {
    & $PythonExe $ScriptPath
}
