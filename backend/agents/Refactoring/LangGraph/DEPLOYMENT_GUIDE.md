# A2A + LangGraph 배포 가이드

이 문서는 A2A + LangGraph 통합 시스템을 새로운 환경에 배포하는 완전한 가이드입니다.

## 📋 사전 요구사항

### 시스템 요구사항
- **Python**: 3.12+ (권장)
- **Node.js**: 18+ (LangGraph Studio용, 선택사항)
- **Git**: 최신 버전
- **브라우저**: Chrome, Firefox, Edge (최신 버전)

### API 키 (선택사항)
- **Google Gemini API**: Currency Agent 전체 기능용
- 없어도 시스템 동작 (Hello Agent 및 시각화는 API 키 불필요)

## 🚀 단계별 배포

### 1단계: 환경 준비

```bash
# 1. 프로젝트 디렉토리 생성
mkdir a2a-langgraph
cd a2a-langgraph

# 2. Python 가상환경 생성
python -m venv venv_312

# 3. 가상환경 활성화
# Windows
venv_312\\Scripts\\activate
# Linux/Mac
source venv_312/bin/activate

# 4. pip 업그레이드
pip install --upgrade pip
```

### 2단계: 의존성 설치

```bash
# requirements.txt를 이용한 설치
pip install -r requirements.txt

# 또는 개별 설치
pip install a2a
pip install langgraph langchain langchain-openai langchain-google-genai
pip install flask flask-cors httpx requests python-dotenv
pip install graphviz mermaid-py
pip install pytest pytest-asyncio
```

### 3단계: A2A 샘플 에이전트 설치

```bash
# A2A 샘플 저장소 클론
git clone https://github.com/a2aproject/a2a-samples.git

# 또는 특정 버전 다운로드
# https://github.com/a2aproject/a2a-samples/archive/refs/heads/main.zip
```

### 4단계: UV 패키지 매니저 설치 (권장)

```bash
# UV 설치 (Windows)
pip install uv

# 또는 curl로 설치 (Linux/Mac)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 5단계: 환경 변수 설정

```bash
# Currency Agent용 .env 파일 생성
cd a2a-samples/samples/python/agents/langgraph
echo "GOOGLE_API_KEY=your_actual_api_key_here" > .env

# 또는 수동으로 .env 파일 생성
# GOOGLE_API_KEY=your_google_gemini_api_key
# TOOL_LLM_URL=http://localhost:11434  # Ollama 등 로컬 LLM용
# TOOL_LLM_NAME=llama2  # 로컬 LLM 모델명
```

### 6단계: 서비스 실행

#### 방법 1: 자동 스크립트 (Windows)
```bash
# setup.py 실행
python setup.py
```

#### 방법 2: 수동 실행
```bash
# 터미널 1: Currency Agent
cd a2a-samples/samples/python/agents/langgraph
uv run app --port 10000

# 터미널 2: Hello World Agent
cd ../helloworld
uv run . --port 9999

# 터미널 3: CORS 프록시
cd path/to/LangGraph/proxy
python proxy_server.py

# 터미널 4: LangGraph Studio (선택사항)
cd a2a-samples/samples/python/agents/langgraph
langgraph dev --port 8123
```

## 🌐 웹 인터페이스 배포

### 정적 파일 서빙
```bash
# Python 내장 서버 사용
cd LangGraph/visualization
python -m http.server 8080

# 접속: http://localhost:8080/langgraph_visualization.html
```

### Nginx 설정 (프로덕션)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /path/to/LangGraph/visualization;
        index web_monitor_cors.html;
    }

    location /api {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /agents/currency {
        proxy_pass http://localhost:10000;
    }

    location /agents/hello {
        proxy_pass http://localhost:9999;
    }
}
```

## 🐳 Docker 배포

### Dockerfile 생성
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \\
    git curl graphviz \\
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# UV 설치
RUN pip install uv

# A2A 샘플 클론
RUN git clone https://github.com/a2aproject/a2a-samples.git

# 패키지 파일 복사
COPY . .

# 포트 노출
EXPOSE 5000 9999 10000 8123

# 실행 스크립트
CMD ["python", "setup.py"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  a2a-langgraph:
    build: .
    ports:
      - "5000:5000"   # CORS Proxy
      - "9999:9999"   # Hello Agent
      - "10000:10000" # Currency Agent
      - "8123:8123"   # LangGraph Studio
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
    volumes:
      - ./logs:/app/logs
```

## ☁️ 클라우드 배포

### AWS EC2
```bash
# 1. EC2 인스턴스 생성 (Ubuntu 22.04 LTS)
# 2. 보안 그룹에서 포트 5000, 9999, 10000 오픈
# 3. SSH 접속 후 배포 스크립트 실행

#!/bin/bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv git

# 나머지 배포 단계 실행
```

### Google Cloud Run
```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/a2a-langgraph', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/a2a-langgraph']
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'a2a-langgraph'
      - '--image=gcr.io/$PROJECT_ID/a2a-langgraph'
      - '--region=us-central1'
      - '--platform=managed'
```

## 🔧 트러블슈팅

### 일반적인 문제들

#### 1. 포트 충돌
```bash
# 사용 중인 포트 확인
netstat -tulpn | grep :5000
lsof -i :5000

# 프로세스 종료
kill -9 <PID>
```

#### 2. 의존성 오류
```bash
# 가상환경 재생성
rm -rf venv_312
python -m venv venv_312
source venv_312/bin/activate
pip install -r requirements.txt
```

#### 3. UV 설치 문제
```bash
# UV 대신 pip 사용
cd a2a-samples/samples/python/agents/langgraph
pip install -e .
python -m app --port 10000
```

#### 4. CORS 문제
```bash
# 브라우저 개발자 도구에서 네트워크 탭 확인
# proxy_server.py가 정상 실행 중인지 확인
curl http://localhost:5000/api/test
```

## 📊 모니터링 및 로깅

### 로그 설정
```python
# logging_config.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/a2a-langgraph.log'),
        logging.StreamHandler()
    ]
)
```

### Health Check 엔드포인트
```python
# proxy_server.py에 추가
@app.route('/health')
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}
```

## 🔒 보안 고려사항

### 1. API 키 보호
- 환경 변수 또는 보안 볼트 사용
- .env 파일을 .gitignore에 추가
- 프로덕션에서는 AWS Secrets Manager 등 사용

### 2. CORS 설정
```python
# 프로덕션용 CORS 설정
CORS(app, origins=['https://your-domain.com'])
```

### 3. HTTPS 설정
```bash
# Let's Encrypt SSL 인증서
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 📈 성능 최적화

### 1. 멀티프로세싱
```python
# gunicorn을 이용한 멀티프로세스
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 proxy_server:app
```

### 2. 캐싱
```python
# Redis 캐싱 추가
pip install redis
# Agent Card 결과를 캐싱하여 성능 향상
```

### 3. 로드 밸런싱
```bash
# Nginx upstream 설정
upstream a2a_backend {
    server 127.0.0.1:5001;
    server 127.0.0.1:5002;
    server 127.0.0.1:5003;
}
```

---

## ✅ 배포 체크리스트

- [ ] Python 3.12+ 설치
- [ ] 가상환경 생성 및 활성화
- [ ] requirements.txt로 의존성 설치
- [ ] A2A 샘플 저장소 클론
- [ ] UV 패키지 매니저 설치
- [ ] 환경 변수 설정 (.env 파일)
- [ ] Currency Agent 실행 (포트 10000)
- [ ] Hello World Agent 실행 (포트 9999)
- [ ] CORS 프록시 서버 실행 (포트 5000)
- [ ] 웹 브라우저에서 접속 테스트
- [ ] LangGraph 시각화 페이지 확인
- [ ] Agent 간 통신 테스트
- [ ] 로그 모니터링 설정
- [ ] 보안 설정 (HTTPS, API 키 보호)

**🎉 배포 완료! 이제 A2A + LangGraph 시스템이 정상 작동합니다.**