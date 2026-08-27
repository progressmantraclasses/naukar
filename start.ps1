#!/usr/bin/env pwsh
# Naukar Full Stack Startup Script
# Run this from C:\Users\HP\Desktop\Naukar\

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "NAUKAR - Autonomous AI Workforce Platform" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path "backend\.env")) {
    Write-Host "backend\\.env not found. Copying from .env.example..." -ForegroundColor Yellow
    if (Test-Path "backend\.env.example") {
        Copy-Item "backend\.env.example" "backend\.env"
        Write-Host "Please edit backend\\.env and add required keys, then run again." -ForegroundColor Yellow
    }
    else {
        Write-Host "backend\\.env.example not found. Create backend\\.env manually." -ForegroundColor Red
    }
    exit 1
}

Write-Host "1) Starting Docker services (PostgreSQL + Redis)..." -ForegroundColor Green
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker failed. Make sure Docker Desktop is running." -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Gray
Start-Sleep -Seconds 4

Write-Host ""
Write-Host "2) Starting Backend (FastAPI)..." -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    Set-Location "C:\Users\HP\Desktop\Naukar\backend"
    if (Test-Path ".venv\Scripts\python.exe") {
        .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    }
    else {
        python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    }
}
Write-Host "Backend starting on http://localhost:8000" -ForegroundColor Gray
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "3) Starting Frontend (Vite Web)..." -ForegroundColor Green
Set-Location "C:\Users\HP\Desktop\Naukar"
$frontendWorkspace = "@naukar/frontend"
$corepackCmd = Join-Path $env:ProgramFiles "nodejs\corepack.cmd"
& $corepackCmd yarn workspace $frontendWorkspace dev:vite

Stop-Job $backendJob
Remove-Job $backendJob
