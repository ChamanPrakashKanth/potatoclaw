<#
.SYNOPSIS
    Launches Spark-X2.5-4B with Bounded Working Memory (BWM) and connects to PotatoClaw.
.DESCRIPTION
    Hardware-Optimized Offloading:
    - GPU: NVIDIA GeForce GTX 1650 (4GB VRAM) -> 26 layers offloaded (~2.0 GB VRAM)
    - RAM: 6GB System RAM -> Offloaded via high-performance ext4 SSD memory mapping
    - CPU: AMD Ryzen 5 5600H -> 6 computation worker threads
    - Context: 2048 tokens ultra-low context for Potato Mode
    - API Endpoint: http://127.0.0.1:11435/v1
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " PotatoClaw + Spark-X2.5-4B (BWM Low-Resource Offload)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$WorkspaceDir = (Get-Item -Path $PSScriptRoot).Parent.FullName
$ConfigPath = Join-Path $WorkspaceDir "config\openclaw.json"
$GlobalConfigDir = "C:\Users\user\.openclaw"
$GlobalConfigFile = Join-Path $GlobalConfigDir "openclaw.json"
$SparkModel = if ($env:POTATO_SPARK_GGUF) { $env:POTATO_SPARK_GGUF } else { "/home/openclaw/Spark-X2.5-4B-Q4_K_M.gguf" }
$SparkServer = if ($env:POTATO_LLAMA_SERVER) { $env:POTATO_LLAMA_SERVER } else { "/home/openclaw/llama.cpp-spark/build/bin/llama-server" }

# Verify the exact local-only artifacts before touching configuration or starting
# a process, so a missing WSL mount/model cannot be mistaken for a model failure.
Write-Host "[0/3] Verifying Spark model and llama-server paths in WSL..." -ForegroundColor Yellow
$quotedSparkModel = $SparkModel.Replace("'", "'\''")
$quotedSparkServer = $SparkServer.Replace("'", "'\''")
wsl.exe -u openclaw -d OpenClawGateway -e bash -lc "test -s '$quotedSparkModel' && test -x '$quotedSparkServer'"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  -> Spark model or llama-server path is missing/unusable." -ForegroundColor Red
    Write-Host "     Model: $SparkModel"
    Write-Host "     Server: $SparkServer"
    exit 1
}
Write-Host "  -> Spark model and llama-server paths verified." -ForegroundColor Green

# 1. Ensure PotatoClaw Configuration
Write-Host "[1/3] Ensuring PotatoClaw configuration..." -ForegroundColor Yellow
if (-not (Test-Path $GlobalConfigDir)) {
    New-Item -ItemType Directory -Path $GlobalConfigDir -Force | Out-Null
}
Copy-Item -Path $ConfigPath -Destination $GlobalConfigFile -Force
Write-Host "  -> PotatoClaw configured at $GlobalConfigFile" -ForegroundColor Green

# 2. Check / Start Spark BWM Engine on Port 11435
Write-Host "[2/3] Checking Spark 2.5 BWM Server on port 11435..." -ForegroundColor Yellow
$isReady = $false
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:11435/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
    $isReady = $true
    Write-Host "  -> Spark Server is already online and ready!" -ForegroundColor Green
} catch {
    Write-Host "  -> Starting custom Spark BWM llama-server in WSL..." -ForegroundColor Yellow
    wsl.exe -u openclaw -d OpenClawGateway -e bash -c "nohup '$SparkServer' -m '$SparkModel' -c 2048 -np 1 -fa on -ngl 26 -t 6 --host 0.0.0.0 --port 11435 --alias spark-x2.5-4b:latest > /home/openclaw/llama-server.log 2>&1 &"
    
    Write-Host "  -> Waiting for model tensors to load..." -ForegroundColor Yellow
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:11435/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
            $isReady = $true
            Write-Host "  -> Spark Server is now online and ready!" -ForegroundColor Green
            break
        } catch {
            Write-Host -NoNewline "."
        }
    }
}

if (-not $isReady) {
    Write-Host "`n[!] Warning: Server is still initializing. Check 'wsl -u openclaw -d OpenClawGateway -e cat /home/openclaw/llama-server.log'" -ForegroundColor Red
}

# 3. Test Inference
Write-Host "`n[3/3] Running Quick Inference Test..." -ForegroundColor Yellow
$body = @{
    model = "spark-x2.5-4b:latest"
    messages = @(
        @{ role = "user"; content = "Confirm in one short sentence that Spark 2.5 is running in Potato Mode." }
    )
    max_tokens = 64
    temperature = 0.2
} | ConvertTo-Json

try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11435/v1/chat/completions" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 30
    $content = $resp.choices[0].message.content
    if (-not $content) {
        $content = $resp.choices[0].message.reasoning_content
    }
    Write-Host "  -> Response: $content" -ForegroundColor Green
} catch {
    Write-Host "  -> Test call error: $_" -ForegroundColor Yellow
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " PotatoClaw is connected to Spark-X2.5-4B!" -ForegroundColor Cyan
Write-Host " Run PotatoClaw turns with: node openclaw.mjs agent --potato" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
