<#
.SYNOPSIS
    Starts Qwen2.5-0.5B-Instruct as PotatoClaw's browser-policy sidecar.
.DESCRIPTION
    - Separate from the main Spark server on port 11435.
    - Qwen browser policy listens on port 11436.
    - Context remains capped at 2048 to preserve PotatoClaw's low-resource invariant.
    - The browser host, not the model, executes actions through `openclaw browser`.
#>

$ErrorActionPreference = "Stop"

$ModelPath = if ($env:POTATO_QWEN_GGUF) {
    $env:POTATO_QWEN_GGUF
} else {
    "/home/openclaw/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf"
}

$ServerBin = if ($env:POTATO_LLAMA_SERVER) {
    $env:POTATO_LLAMA_SERVER
} else {
    "/home/openclaw/llama.cpp-spark/build/bin/llama-server"
}

$Alias = "qwen2.5-0.5b-browser"
$Port = 11436
$Health = "http://127.0.0.1:$Port/health"
$Chat = "http://127.0.0.1:$Port/v1/chat/completions"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " PotatoClaw + Qwen2.5-0.5B Browser Policy" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Model:   $ModelPath"
Write-Host "Context: 2048"
Write-Host "Port:    $Port"

$isReady = $false
try {
    Invoke-RestMethod -Uri $Health -Method Get -TimeoutSec 2 -ErrorAction Stop | Out-Null
    $isReady = $true
    Write-Host "  -> Qwen browser server is already online." -ForegroundColor Green
} catch {
    Write-Host "  -> Starting Qwen browser server in WSL..." -ForegroundColor Yellow

    $quotedModel = $ModelPath.Replace("'", "'\''")
    $quotedServer = $ServerBin.Replace("'", "'\''")
    $cmd = "nohup '$quotedServer' -m '$quotedModel' -c 2048 -np 1 -fa on -ngl 99 -t 6 --host 0.0.0.0 --port $Port --alias $Alias > /home/openclaw/qwen-browser.log 2>&1 &"
    wsl -u openclaw -d OpenClawGateway -e bash -lc $cmd

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-RestMethod -Uri $Health -Method Get -TimeoutSec 2 -ErrorAction Stop | Out-Null
            $isReady = $true
            break
        } catch {
            Write-Host -NoNewline "."
        }
    }
    Write-Host ""
}

if (-not $isReady) {
    Write-Host "[!] Qwen browser server did not become ready." -ForegroundColor Red
    Write-Host "    Confirm the GGUF exists: $ModelPath"
    Write-Host "    Check: wsl -u openclaw -d OpenClawGateway -e cat /home/openclaw/qwen-browser.log"
    exit 1
}

$body = @{
    model = $Alias
    messages = @(
        @{
            role = "user"
            content = 'Return only {"action":"done","note":"ready"}'
        }
    )
    max_tokens = 48
    temperature = 0.0
} | ConvertTo-Json -Depth 5

try {
    $resp = Invoke-RestMethod -Uri $Chat -Method Post -Body $body -ContentType "application/json" -TimeoutSec 30
    $content = $resp.choices[0].message.content
    if (-not $content) {
        $content = $resp.choices[0].message.reasoning_content
    }
    Write-Host "  -> Policy test: $content" -ForegroundColor Green
} catch {
    Write-Host "[!] Server is healthy but inference test failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Qwen browser policy is ready." -ForegroundColor Cyan
Write-Host " Example:" -ForegroundColor Cyan
Write-Host ' python scripts\potato_browser_agent.py "Open X and prepare a 3-post thread"'
Write-Host ""
Write-Host " Add --allow-submit only when you want final Post/Send/Publish actions executed."
Write-Host "==========================================================" -ForegroundColor Cyan
