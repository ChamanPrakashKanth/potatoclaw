<#
.SYNOPSIS
    PotatoClaw - Chrome CDP Remote Debugging Launcher (Port 9222)
.DESCRIPTION
    Launches Chrome with --remote-debugging-port=9222 for agent control.
#>

$ScriptPath = Join-Path $PSScriptRoot "scripts\launch-chrome-debug.ps1"
& $ScriptPath $args
