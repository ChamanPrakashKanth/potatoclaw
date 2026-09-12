<#
.SYNOPSIS
    Compatibility entry point for the former Spark launcher.
.DESCRIPTION
    PotatoClaw now uses one shared MiniCPM5-2B server. Keep using this old
    filename if it is referenced by an existing shortcut; it delegates to the
    canonical MiniCPM launcher and never starts Spark.
#>

$canonical = Join-Path $PSScriptRoot "start-minicpm-potato.ps1"
& $canonical @args
exit $LASTEXITCODE
