<#
.SYNOPSIS
    Launches Qwen2.5-0.5B-Instruct as dedicated browser-action policy on port 11436.
.DESCRIPTION
    Hardware-Optimized Offloading:
    - GPU: NVIDIA GeForce GTX 1650 (4GB VRAM) -> full layer offload (-ngl 99, ~450MB VRAM)
    - Context: 2048 tokens
    - Inference: Single slot (-np 1), Flash Attention (-fa on)
    - API Endpoint: http://127.0.0.1:11436/v1
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " PotatoClaw + Qwen2.5-0.5B Browser Action Policy Server   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check / Start Qwen Server on Port 11436
Write-Host "[1/2] Checking Qwen 0.5B Policy Server on port 11436..." -ForegroundColor Yellow
$isReady = $false
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:11436/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
    $isReady = $true
    Write-Host "  -> Qwen Policy Server is already online and ready!" -ForegroundColor Green
} catch {
    Write-Host "  -> Starting Qwen 0.5B llama-server in WSL on port 11436..." -ForegroundColor Yellow
    wsl -u openclaw -d OpenClawGateway -e bash -c "nohup /home/openclaw/llama.cpp-spark/build/bin/llama-server -m /home/openclaw/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf -c 2048 -np 1 -fa on -ngl 99 -t 4 --host 0.0.0.0 --port 11436 --alias qwen2.5-0.5b:latest </dev/null >/home/openclaw/qwen-server.log 2>&1 & disown"
    
    Write-Host "  -> Waiting for model tensors to load..." -ForegroundColor Yellow
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:11436/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
            $isReady = $true
            Write-Host "  -> Qwen Policy Server is now online and ready!" -ForegroundColor Green
            break
        } catch {
            Write-Host -NoNewline "."
        }
    }
}

if (-not $isReady) {
    Write-Host "`n[!] Warning: Server is still initializing. Check 'wsl -u openclaw -d OpenClawGateway -e cat /home/openclaw/qwen-server.log'" -ForegroundColor Red
}

# 2. Test Inference
Write-Host "`n[2/2] Running Quick Inference Test..." -ForegroundColor Yellow
$body = @{
    model = "qwen2.5-0.5b:latest"
    messages = @(
        @{ role = "user"; content = "Confirm in one short sentence that Qwen2.5-0.5B is running as the browser policy." }
    )
    max_tokens = 64
    temperature = 0.2
} | ConvertTo-Json

try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11436/v1/chat/completions" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 30
    $content = $resp.choices[0].message.content
    if (-not $content) {
        $content = $resp.choices[0].message.reasoning_content
    }
    Write-Host "  -> Response: $content" -ForegroundColor Green
} catch {
    Write-Host "  -> Test call error: $_" -ForegroundColor Yellow
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Qwen2.5-0.5B Policy Server running on http://127.0.0.1:11436/v1" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
