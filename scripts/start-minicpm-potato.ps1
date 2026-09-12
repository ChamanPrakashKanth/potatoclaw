<#
.SYNOPSIS
    Launches the shared MiniCPM5-2B PotatoClaw model server.
.DESCRIPTION
    Uses one local llama-server for chat, news drafting, and browser actions.
    A single 2B instance keeps the GTX 1650/6-8GB target within the
    single-slot, 2048-token PotatoClaw resource budget.

    Override the operator-managed WSL model path with POTATO_MINICPM_GGUF.
    Override GPU offload with POTATO_MINICPM_NGL when the hardware permits it.
    No model is downloaded by this launcher.
#>

$ErrorActionPreference = "Stop"

$WorkspaceDir = (Get-Item -Path $PSScriptRoot).Parent.FullName
$ConfigPath = Join-Path $WorkspaceDir "config\openclaw.json"
$GlobalConfigDir = "C:\Users\user\.openclaw"
$GlobalConfigFile = Join-Path $GlobalConfigDir "openclaw.json"
$ModelPath = if ($env:POTATO_MINICPM_GGUF) { $env:POTATO_MINICPM_GGUF } else { "/home/openclaw/MiniCPM5-2B-Q4_K_M.gguf" }
$ServerBin = if ($env:POTATO_LLAMA_SERVER) { $env:POTATO_LLAMA_SERVER } else { "/home/openclaw/llama.cpp-spark/build/bin/llama-server" }
$Alias = if ($env:POTATO_MINICPM_MODEL) { $env:POTATO_MINICPM_MODEL } else { "minicpm5-2b:latest" }
$Port = 11435
$Ngl = if ($env:POTATO_MINICPM_NGL) { $env:POTATO_MINICPM_NGL } else { "18" }
$Health = "http://127.0.0.1:$Port/health"
$Chat = "http://127.0.0.1:$Port/v1/chat/completions"
$Models = "http://127.0.0.1:$Port/v1/models"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " PotatoClaw + MiniCPM5-2B (Shared Low-VRAM Server)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Model:   $ModelPath"
Write-Host "Alias:   $Alias"
Write-Host "Context: 2048 | Slots: 1 | GPU layers: $Ngl"
Write-Host "Port:    $Port (chat + browser policy)"

Write-Host "[0/3] Verifying MiniCPM model and llama-server paths in WSL..." -ForegroundColor Yellow
$quotedModel = $ModelPath.Replace("'", "'\''")
$quotedServer = $ServerBin.Replace("'", "'\''")
wsl.exe -u openclaw -d OpenClawGateway -e bash -lc "test -s '$quotedModel' && test -x '$quotedServer'"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  -> MiniCPM model or llama-server path is missing/unusable." -ForegroundColor Red
    Write-Host "     Model: $ModelPath"
    Write-Host "     Server: $ServerBin"
    Write-Host "     Put the MiniCPM5-2B GGUF at that WSL path or set POTATO_MINICPM_GGUF."
    exit 1
}
Write-Host "  -> MiniCPM model and llama-server paths verified." -ForegroundColor Green

Write-Host "[1/3] Ensuring PotatoClaw configuration..." -ForegroundColor Yellow
if (-not (Test-Path $GlobalConfigDir)) {
    New-Item -ItemType Directory -Path $GlobalConfigDir -Force | Out-Null
}
Copy-Item -Path $ConfigPath -Destination $GlobalConfigFile -Force
Write-Host "  -> PotatoClaw configured at $GlobalConfigFile" -ForegroundColor Green

Write-Host "[2/3] Checking shared MiniCPM server on port $Port..." -ForegroundColor Yellow
$isReady = $false
$isOnline = $false
try {
    Invoke-RestMethod -Uri $Health -Method Get -TimeoutSec 2 -ErrorAction Stop | Out-Null
    $isOnline = $true
    $modelResponse = Invoke-RestMethod -Uri $Models -Method Get -TimeoutSec 2 -ErrorAction Stop
    $servedId = $modelResponse.data[0].id
    if ($servedId -and $servedId -ne $Alias) {
        Write-Host "  -> Port $Port is occupied by '$servedId', not '$Alias'." -ForegroundColor Red
        Write-Host "     Stop the old llama-server, then run this launcher again." -ForegroundColor Red
        exit 2
    }
    $isReady = $true
    Write-Host "  -> MiniCPM server is already online and ready." -ForegroundColor Green
} catch {
    if ($isOnline) {
        Write-Host "  -> Server is online but its model identity could not be verified." -ForegroundColor Red
        Write-Host "     Stop the old server before starting MiniCPM." -ForegroundColor Red
        exit 2
    }
    Write-Host "  -> Starting shared MiniCPM llama-server in WSL..." -ForegroundColor Yellow
    $serverCommand = "'$quotedServer' -m '$quotedModel' -c 2048 -np 1 -fa on -ngl $Ngl -t 6 --host 127.0.0.1 --port $Port --alias '$Alias' > /home/openclaw/minicpm-potato.log 2>&1"
    $wslArguments = "-u openclaw -d OpenClawGateway -e bash -lc `"$serverCommand`""
    Start-Process -FilePath "wsl.exe" -ArgumentList $wslArguments -WindowStyle Hidden | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] MiniCPM server start command failed." -ForegroundColor Red
        exit 1
    }

    Write-Host "  -> Waiting for model tensors to load..." -ForegroundColor Yellow
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        try {
            Invoke-RestMethod -Uri $Health -Method Get -TimeoutSec 2 -ErrorAction Stop | Out-Null
            $modelResponse = Invoke-RestMethod -Uri $Models -Method Get -TimeoutSec 2 -ErrorAction Stop
            $servedId = $modelResponse.data[0].id
            if ($servedId -and $servedId -ne $Alias) {
                Write-Host "`n[!] Port $Port became ready with unexpected model '$servedId'." -ForegroundColor Red
                exit 2
            }
            $isReady = $true
            Write-Host "  -> MiniCPM server is now online and ready!" -ForegroundColor Green
            break
        } catch {
            Write-Host -NoNewline "."
        }
    }
    Write-Host ""
}

if (-not $isReady) {
    Write-Host "[!] MiniCPM server is still initializing or failed to start." -ForegroundColor Red
    Write-Host "    Check: wsl -u openclaw -d OpenClawGateway -e cat /home/openclaw/minicpm-potato.log"
    exit 1
}

Write-Host "[3/3] Running MiniCPM inference test..." -ForegroundColor Yellow
$body = @{
    model = $Alias
    messages = @(
        @{ role = "user"; content = "Return only one short sentence confirming that MiniCPM is running in PotatoClaw." }
    )
    max_tokens = 64
    temperature = 0.2
} | ConvertTo-Json -Depth 5

try {
    $resp = Invoke-RestMethod -Uri $Chat -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60
    $content = $resp.choices[0].message.content
    if (-not $content) {
        $content = $resp.choices[0].message.reasoning_content
    }
    if (-not $content) {
        throw "The server returned an empty response."
    }
    Write-Host "  -> Response: $content" -ForegroundColor Green
} catch {
    Write-Host "[!] MiniCPM server is healthy but inference failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " PotatoClaw is connected to MiniCPM5-2B!" -ForegroundColor Cyan
Write-Host " Chat and browser actions share this one local model server." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
