# Law Search System - Server Startup Script (PowerShell)
# 법률 검색 시스템 - 서버 자동 실행 스크립트
#
# Usage:
#   Right-click → "Run with PowerShell"
#   or in PowerShell: .\start_servers.ps1
#
# Created: 2025-11-25
# Author: Claude AI Assistant

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Law Search System - Starting Servers" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check Neo4j status
Write-Host "[1/3] Checking Neo4j..." -ForegroundColor Yellow
$neo4jRunning = $false
try {
    $neo4jProcess = Get-Process -Name "java" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*neo4j*" }
    if ($neo4jProcess) {
        $neo4jRunning = $true
        Write-Host "  ✅ Neo4j is already running (Port 7687)" -ForegroundColor Green
    }
} catch {
    # Silently continue
}

if (-not $neo4jRunning) {
    Write-Host "  ⚠️  Neo4j is NOT running!" -ForegroundColor Red
    Write-Host "  → Please start Neo4j Desktop manually" -ForegroundColor Yellow
    Write-Host "  → Press any key to continue anyway..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

Write-Host ""

# Start Django Backend (Daphne ASGI)
Write-Host "[2/3] Starting Django Backend (Daphne ASGI)..." -ForegroundColor Yellow
$backendPath = Join-Path $ScriptDir "backend"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$backendPath'; Write-Host 'Django Backend Server' -ForegroundColor Cyan; Write-Host 'Port: 0.0.0.0:8000' -ForegroundColor Green; Write-Host ''; .venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application"
)

Write-Host "  ✅ Backend server starting... (Port 8000)" -ForegroundColor Green
Start-Sleep -Seconds 3

Write-Host ""

# Start React Frontend (Vite)
Write-Host "[3/3] Starting React Frontend (Vite)..." -ForegroundColor Yellow
$frontendPath = Join-Path $ScriptDir "frontend"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$frontendPath'; Write-Host 'React Frontend Server' -ForegroundColor Cyan; Write-Host 'Port: 5173' -ForegroundColor Green; Write-Host ''; npm run dev"
)

Write-Host "  ✅ Frontend server starting... (Port 5173)" -ForegroundColor Green
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ All Servers Started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server URLs:" -ForegroundColor Yellow
Write-Host "  • Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  • Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  • Neo4j:    http://localhost:7474" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Wait 10-15 seconds for servers to fully start" -ForegroundColor White
Write-Host "  2. Open http://localhost:5173 in your browser" -ForegroundColor White
Write-Host "  3. Check server windows for any errors" -ForegroundColor White
Write-Host ""
Write-Host "To stop servers:" -ForegroundColor Yellow
Write-Host "  • Close each PowerShell window" -ForegroundColor White
Write-Host "  • Or run: .\stop_servers.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit this window..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
