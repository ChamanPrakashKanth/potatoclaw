<#
.SYNOPSIS
    PotatoClaw Interactive AI Agent Chat (PotatoAI)
.DESCRIPTION
    Launches an interactive conversational computer agent session powered by Spark-X2.5-4B
    with Bounded Working Memory (BMW), Dynamic Tool Execution, and Small-Model Syntax Repair.
.EXAMPLE
    .\potato_chat.ps1
    .\potato_chat.ps1 --test "Hello PotatoAI"
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

$ScriptPath = Join-Path $PSScriptRoot "scripts\potato_chat.py"
& $PythonExe $ScriptPath $args
