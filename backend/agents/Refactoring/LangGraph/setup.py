#!/usr/bin/env python3
"""
A2A + LangGraph Integration Setup Script
자동으로 전체 시스템을 설정하고 실행하는 스크립트
"""

import os
import sys
import subprocess
import time
import threading
from pathlib import Path
import requests
import json

class Colors:
    """터미널 색상 정의"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_status(message, status="INFO"):
    """상태 메시지 출력"""
    colors = {
        "INFO": Colors.OKBLUE,
        "SUCCESS": Colors.OKGREEN,
        "WARNING": Colors.WARNING,
        "ERROR": Colors.FAIL,
        "HEADER": Colors.HEADER
    }
    color = colors.get(status, Colors.OKBLUE)
    print(f"{color}[{status}] {message}{Colors.ENDC}")

def check_python_version():
    """Python 버전 확인"""
    print_status("Checking Python version...", "INFO")
    if sys.version_info < (3, 11):
        print_status(f"Python 3.11+ required, but {sys.version} found", "ERROR")
        return False
    print_status(f"Python {sys.version.split()[0]} - OK", "SUCCESS")
    return True

def check_dependencies():
    """필수 패키지 설치 확인"""
    print_status("Checking dependencies...", "INFO")
    required_packages = [
        'flask', 'flask-cors', 'requests', 'httpx',
        'a2a', 'langgraph', 'langchain'
    ]

    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} (missing)")
            missing_packages.append(package)

    if missing_packages:
        print_status(f"Missing packages: {', '.join(missing_packages)}", "WARNING")
        print_status("Installing missing packages...", "INFO")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing_packages,
                         check=True, capture_output=True)
            print_status("Dependencies installed successfully", "SUCCESS")
        except subprocess.CalledProcessError as e:
            print_status(f"Failed to install dependencies: {e}", "ERROR")
            return False
    else:
        print_status("All dependencies satisfied", "SUCCESS")

    return True

def clone_a2a_samples():
    """A2A 샘플 저장소 클론"""
    samples_dir = "a2a-samples"
    if os.path.exists(samples_dir):
        print_status("A2A samples directory already exists", "INFO")
        return True

    print_status("Cloning A2A samples repository...", "INFO")
    try:
        subprocess.run([
            'git', 'clone',
            'https://github.com/a2aproject/a2a-samples.git'
        ], check=True, capture_output=True)
        print_status("A2A samples cloned successfully", "SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print_status(f"Failed to clone A2A samples: {e}", "ERROR")
        return False

def install_uv():
    """UV 패키지 매니저 설치"""
    print_status("Installing UV package manager...", "INFO")
    try:
        # UV가 이미 설치되어 있는지 확인
        subprocess.run(['uv', '--version'], check=True, capture_output=True)
        print_status("UV already installed", "INFO")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'uv'],
                         check=True, capture_output=True)
            print_status("UV installed successfully", "SUCCESS")
            return True
        except subprocess.CalledProcessError as e:
            print_status(f"Failed to install UV: {e}", "WARNING")
            print_status("Continuing without UV (will use pip)", "INFO")
            return False

def run_agent(name, directory, port, command):
    """백그라운드에서 에이전트 실행"""
    print_status(f"Starting {name} on port {port}...", "INFO")
    try:
        os.chdir(directory)
        if 'uv run' in command:
            # UV 명령어 실행
            cmd_parts = command.split()
            process = subprocess.Popen(cmd_parts,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        else:
            # 일반 Python 명령어 실행
            process = subprocess.Popen(command, shell=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)

        # 잠시 기다려서 시작 확인
        time.sleep(3)
        if process.poll() is None:
            print_status(f"{name} started successfully (PID: {process.pid})", "SUCCESS")
            return process
        else:
            stdout, stderr = process.communicate()
            print_status(f"Failed to start {name}: {stderr.decode()}", "ERROR")
            return None
    except Exception as e:
        print_status(f"Error starting {name}: {e}", "ERROR")
        return None

def start_proxy_server():
    """CORS 프록시 서버 시작"""
    print_status("Starting CORS proxy server...", "INFO")
    try:
        proxy_script = Path("proxy/proxy_server.py")
        if not proxy_script.exists():
            print_status("proxy_server.py not found", "ERROR")
            return None

        process = subprocess.Popen([sys.executable, str(proxy_script)],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        time.sleep(2)
        if process.poll() is None:
            print_status("CORS proxy server started (Port 5000)", "SUCCESS")
            return process
        else:
            print_status("Failed to start proxy server", "ERROR")
            return None
    except Exception as e:
        print_status(f"Error starting proxy server: {e}", "ERROR")
        return None

def test_agents():
    """에이전트 상태 테스트"""
    print_status("Testing agents...", "INFO")

    agents = {
        "Hello Agent": "http://localhost:9999/.well-known/agent-card.json",
        "Currency Agent": "http://localhost:10000/.well-known/agent-card.json",
        "CORS Proxy": "http://localhost:5000/api/test"
    }

    results = {}
    for name, url in agents.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print_status(f"{name} - OK", "SUCCESS")
                results[name] = True
            else:
                print_status(f"{name} - HTTP {response.status_code}", "WARNING")
                results[name] = False
        except requests.RequestException as e:
            print_status(f"{name} - Connection failed", "ERROR")
            results[name] = False

    return results

def create_env_file():
    """환경 변수 파일 생성"""
    env_path = "a2a-samples/samples/python/agents/langgraph/.env"
    if os.path.exists(env_path):
        print_status(".env file already exists", "INFO")
        return

    print_status("Creating .env file...", "INFO")
    env_content = """# A2A + LangGraph Environment Variables
GOOGLE_API_KEY=dummy_key_for_testing
# 실제 사용시 위 라인을 실제 Google Gemini API 키로 교체하세요

# 대안: 로컬 LLM 사용
# TOOL_LLM_URL=http://localhost:11434
# TOOL_LLM_NAME=llama2
"""

    try:
        os.makedirs(os.path.dirname(env_path), exist_ok=True)
        with open(env_path, 'w') as f:
            f.write(env_content)
        print_status(".env file created", "SUCCESS")
    except Exception as e:
        print_status(f"Failed to create .env file: {e}", "WARNING")

def main():
    """메인 설정 함수"""
    print_status("A2A + LangGraph Integration Setup", "HEADER")
    print_status("=" * 50, "HEADER")

    # 1. Python 버전 확인
    if not check_python_version():
        return False

    # 2. 의존성 확인 및 설치
    if not check_dependencies():
        return False

    # 3. A2A 샘플 클론
    if not clone_a2a_samples():
        return False

    # 4. UV 설치
    uv_available = install_uv()

    # 5. 환경 파일 생성
    create_env_file()

    # 6. 에이전트들 시작
    print_status("Starting agents...", "HEADER")

    processes = []
    original_dir = os.getcwd()

    # Hello World Agent 시작
    hello_dir = "a2a-samples/samples/python/agents/helloworld"
    if uv_available:
        hello_cmd = "uv run . --port 9999"
    else:
        hello_cmd = "python -m app --port 9999"

    hello_process = run_agent("Hello World Agent", hello_dir, 9999, hello_cmd)
    if hello_process:
        processes.append(("Hello World Agent", hello_process))

    os.chdir(original_dir)

    # Currency Agent 시작
    currency_dir = "a2a-samples/samples/python/agents/langgraph"
    if uv_available:
        currency_cmd = "uv run app --port 10000"
    else:
        currency_cmd = "python -m app --port 10000"

    currency_process = run_agent("Currency Agent", currency_dir, 10000, currency_cmd)
    if currency_process:
        processes.append(("Currency Agent", currency_process))

    os.chdir(original_dir)

    # 7. CORS 프록시 시작
    proxy_process = start_proxy_server()
    if proxy_process:
        processes.append(("CORS Proxy", proxy_process))

    # 8. 서비스 시작 대기
    print_status("Waiting for services to start...", "INFO")
    time.sleep(5)

    # 9. 에이전트 테스트
    test_results = test_agents()

    # 10. 결과 출력
    print_status("Setup completed!", "HEADER")
    print_status("=" * 50, "HEADER")

    success_count = sum(test_results.values())
    total_count = len(test_results)

    if success_count == total_count:
        print_status("All services are running successfully!", "SUCCESS")
    else:
        print_status(f"{success_count}/{total_count} services running", "WARNING")

    print_status("\\nAccess URLs:", "INFO")
    print("  • Main Monitor: http://localhost:5000/")
    print("  • LangGraph Visualization: http://localhost:5000/docs/langgraph_visualization.html")
    print("  • Hello Agent: http://localhost:9999/.well-known/agent-card.json")
    print("  • Currency Agent: http://localhost:10000/.well-known/agent-card.json")

    print_status("\\nPress Ctrl+C to stop all services", "INFO")

    # 11. 사용자 입력 대기
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print_status("\\nStopping services...", "INFO")
        for name, process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print_status(f"{name} stopped", "INFO")
            except subprocess.TimeoutExpired:
                process.kill()
                print_status(f"{name} force killed", "WARNING")
            except Exception as e:
                print_status(f"Error stopping {name}: {e}", "ERROR")

        print_status("All services stopped", "SUCCESS")

    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_status("\\nSetup interrupted by user", "INFO")
        sys.exit(1)
    except Exception as e:
        print_status(f"Setup failed: {e}", "ERROR")
        sys.exit(1)