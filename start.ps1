#!/usr/bin/env pwsh
# Naukar — Full Stack Startup Script
# Run this from c:\Users\HP\Desktop\Naukar\

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║            NAUKAR — Autonomous AI Workforce Platform         ║" -ForegroundColor Cyan  
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check .env exists
if (-not (Test-Path "backend\.env")) {
    Write-Host "⚠️  backend\.env not found. Copying from .env.example..." -ForegroundColor Yellow
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Host "✏️  Please edit backend\.env and add your GROQ_API_KEY, NEO4J credentials" -ForegroundColor Yellow
    Write-Host "   Then run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "1️⃣  Starting Docker services (PostgreSQL + Redis)..." -ForegroundColor Green
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker failed. Make sure Docker Desktop is running." -ForegroundColor Red
    exit 1
}

Write-Host "   Waiting for PostgreSQL to be ready..." -ForegroundColor Gray
Start-Sleep -Seconds 4

Write-Host ""
Write-Host "2️⃣  Starting Backend (FastAPI)..." -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    Set-Location "c:\Users\HP\Desktop\Naukar\backend"
    if (Test-Path ".venv\Scripts\python.exe") {
        .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    } else {
        python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    }
}
Write-Host "   Backend starting on http://localhost:8000" -ForegroundColor Gray
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "3️⃣  Starting Frontend (Vite + Electron)..." -ForegroundColor Green
Set-Location "frontend"
npm run dev

# Cleanup on exit
Stop-Job $backendJob
Remove-Job $backendJob
