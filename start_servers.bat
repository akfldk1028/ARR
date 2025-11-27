@echo off
REM Law Search System - Server Startup Script (Batch)
REM 법률 검색 시스템 - 서버 자동 실행 스크립트
REM
REM Usage: Double-click this file
REM
REM Created: 2025-11-25
REM Author: Claude AI Assistant

chcp 65001 > nul
title Law Search System - Server Startup

echo.
echo ========================================
echo   Law Search System - Starting Servers
echo ========================================
echo.

REM Check Neo4j status
echo [1/3] Checking Neo4j...
netstat -ano | findstr ":7687" > nul 2>&1
if %errorlevel% == 0 (
    echo   ✅ Neo4j is running ^(Port 7687^)
) else (
    echo   ⚠️  Neo4j is NOT running!
    echo   → Please start Neo4j Desktop manually
    echo   → Press any key to continue anyway...
    pause > nul
)

echo.

REM Start Django Backend (Daphne ASGI)
echo [2/3] Starting Django Backend ^(Daphne ASGI^)...
start "Backend Server - Django Daphne (Port 8000)" cmd /k "cd /d %~dp0backend && echo Django Backend Server && echo Port: 0.0.0.0:8000 && echo. && .venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application"
echo   ✅ Backend server starting... ^(Port 8000^)
timeout /t 3 /nobreak > nul

echo.

REM Start React Frontend (Vite)
echo [3/3] Starting React Frontend ^(Vite^)...
start "Frontend Server - React Vite (Port 5173)" cmd /k "cd /d %~dp0frontend && echo React Frontend Server && echo Port: 5173 && echo. && npm run dev"
echo   ✅ Frontend server starting... ^(Port 5173^)
timeout /t 2 /nobreak > nul

echo.
echo ========================================
echo   ✅ All Servers Started!
echo ========================================
echo.
echo Server URLs:
echo   • Backend:  http://localhost:8000
echo   • Frontend: http://localhost:5173
echo   • Neo4j:    http://localhost:7474
echo.
echo Next Steps:
echo   1. Wait 10-15 seconds for servers to fully start
echo   2. Open http://localhost:5173 in your browser
echo   3. Check server windows for any errors
echo.
echo To stop servers:
echo   • Close each CMD window
echo   • Or run: stop_servers.bat
echo.
echo Press any key to exit this window...
pause > nul
