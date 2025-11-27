# Law Search System - Server Shutdown Script (PowerShell)
# 법률 검색 시스템 - 서버 종료 스크립트
#
# Usage:
#   Right-click → "Run with PowerShell"
#   or in PowerShell: .\stop_servers.ps1
#
# Created: 2025-11-25
# Author: Claude AI Assistant

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Law Search System - Stopping Servers" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Stop Django Backend (Port 8000)
Write-Host "[1/2] Stopping Django Backend (Port 8000)..." -ForegroundColor Yellow
try {
    $backendProcesses = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    if ($backendProcesses) {
        foreach ($pid in $backendProcesses) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "  ✅ Stopped process PID: $pid" -ForegroundColor Green
        }
    } else {
        Write-Host "  ℹ️  No backend server running on port 8000" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ⚠️  Could not stop backend: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""

# Stop React Frontend (Port 5173)
Write-Host "[2/2] Stopping React Frontend (Port 5173)..." -ForegroundColor Yellow
try {
    $frontendProcesses = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    if ($frontendProcesses) {
        foreach ($pid in $frontendProcesses) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "  ✅ Stopped process PID: $pid" -ForegroundColor Green
        }
    } else {
        Write-Host "  ℹ️  No frontend server running on port 5173" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ⚠️  Could not stop frontend: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ Server Shutdown Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Note: Neo4j was NOT stopped (manual management)" -ForegroundColor Gray
Write-Host "If you want to stop Neo4j, use Neo4j Desktop" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
