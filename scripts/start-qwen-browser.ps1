<#
.SYNOPSIS
    Compatibility entry point for the former Qwen browser sidecar.
.DESCRIPTION
    Browser actions now use the shared MiniCPM5-2B server on port 11435.
    This wrapper delegates to the canonical launcher and never starts a second
    model process on port 11436.
#>

$canonical = Join-Path $PSScriptRoot "start-minicpm-potato.ps1"
& $canonical @args
exit $LASTEXITCODE
