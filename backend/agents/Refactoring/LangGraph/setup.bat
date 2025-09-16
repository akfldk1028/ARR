@echo off
REM A2A + LangGraph Integration Setup Script for Windows
REM 자동으로 전체 시스템을 설정하고 실행

title A2A + LangGraph Setup

echo.
echo ================================================
echo A2A + LangGraph Integration Setup (Windows)
echo ================================================
echo.

REM 1. Python 버전 확인
echo [INFO] Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.12+
    pause
    exit /b 1
)
echo [OK] Python found

REM 2. 가상환경 생성 (선택사항)
echo [INFO] Checking virtual environment...
if not exist "venv_312" (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv_312
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
)

REM 3. 가상환경 활성화
echo [INFO] Activating virtual environment...
call venv_312\Scripts\activate.bat
if errorlevel 1 (
    echo [WARNING] Failed to activate virtual environment, using system Python
)

REM 4. 필수 패키지 설치
echo [INFO] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

REM 5. A2A 샘플 클론 (없는 경우)
if not exist "a2a-samples" (
    echo [INFO] Cloning A2A samples repository...
    git clone https://github.com/a2aproject/a2a-samples.git
    if errorlevel 1 (
        echo [ERROR] Failed to clone A2A samples
        pause
        exit /b 1
    )
    echo [OK] A2A samples cloned
) else (
    echo [INFO] A2A samples directory already exists
)

REM 6. UV 설치
echo [INFO] Installing UV package manager...
pip install uv
if errorlevel 1 (
    echo [WARNING] Failed to install UV, will use pip
    set USE_UV=false
) else (
    echo [OK] UV installed
    set USE_UV=true
)

REM 7. 환경 파일 생성
if not exist "a2a-samples\samples\python\agents\langgraph\.env" (
    echo [INFO] Creating .env file...
    echo GOOGLE_API_KEY=dummy_key_for_testing > "a2a-samples\samples\python\agents\langgraph\.env"
    echo # Replace above with your actual Google Gemini API key >> "a2a-samples\samples\python\agents\langgraph\.env"
    echo [OK] .env file created
)

REM 8. 서비스 시작
echo.
echo [INFO] Starting services...
echo.

REM 새 터미널에서 Hello Agent 실행
start "Hello World Agent" cmd /k "cd /d a2a-samples\samples\python\agents\helloworld && uv run . --port 9999"

REM 새 터미널에서 Currency Agent 실행
start "Currency Agent" cmd /k "cd /d a2a-samples\samples\python\agents\langgraph && uv run app --port 10000"

REM 새 터미널에서 CORS Proxy 실행
start "CORS Proxy" cmd /k "python proxy\proxy_server.py"

REM 잠시 대기
echo [INFO] Waiting for services to start...
timeout /t 10 /nobreak >nul

REM 9. 브라우저에서 웹 인터페이스 열기
echo [INFO] Opening web interfaces...
start http://localhost:5000/
timeout /t 2 /nobreak >nul
start http://localhost:5000/docs/langgraph_visualization.html

echo.
echo ================================================
echo Setup Complete!
echo ================================================
echo.
echo Services running:
echo   - Hello World Agent: http://localhost:9999
echo   - Currency Agent:    http://localhost:10000
echo   - CORS Proxy:        http://localhost:5000
echo.
echo Web Interfaces:
echo   - Main Monitor:      http://localhost:5000/
echo   - LangGraph Visual:  http://localhost:5000/docs/langgraph_visualization.html
echo.
echo [INFO] Press any key to close this window (services will keep running)
echo [INFO] To stop services, close their individual terminal windows
echo.

pause