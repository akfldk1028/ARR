# A2A + LangGraph Integration Package

이 패키지는 **A2A Protocol**과 **LangGraph**를 통합하여 멀티 에이전트 시스템을 구축하고 시각화하는 완전한 솔루션입니다.

## 🎯 주요 기능

### ✅ 구현된 기능들
- **A2A Protocol**: Agent-to-Agent 통신
- **LangGraph 시각화**: 웹 기반 워크플로우 다이어그램
- **웹 모니터링**: 실시간 에이전트 상태 모니터링
- **CORS 프록시**: 브라우저 CORS 문제 해결
- **Worker 통신**: 에이전트간 직접 통신
- **LangGraph Studio**: 전문적 디버깅 환경

## 📁 패키지 구조

```
LangGraph/
├── README.md                    # 이 파일
├── requirements.txt             # Python 의존성
├── DEPLOYMENT_GUIDE.md          # 배포 가이드
├── LANGGRAPH_VISUALIZATION.md   # 상세 시각화 가이드
├── setup.py                     # 설치 스크립트
├──
├── visualization/               # 웹 UI 파일들
│   ├── langgraph_visualization.html  # LangGraph 시각화 페이지
│   └── web_monitor_cors.html         # 메인 모니터 페이지
│
├── proxy/                       # CORS 프록시 서버
│   └── proxy_server.py          # Flask 기반 프록시
│
├── scripts/                     # 유틸리티 스크립트들
│   ├── visualize_graph.py       # 그래프 추출/시각화
│   └── test_worker_to_worker.py # Worker 통신 테스트
│
├── config/                      # 설정 파일들
│   └── langgraph.json          # LangGraph Studio 설정
│
└── agents/                      # 샘플 에이전트들 (별도 제공)
    ├── currency/               # Currency Agent
    └── helloworld/             # Hello World Agent
```

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# Python 3.12 가상환경 생성
python -m venv venv_312
source venv_312/bin/activate  # Linux/Mac
venv_312\\Scripts\\activate    # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 에이전트 실행
```bash
# A2A 샘플 저장소 클론
git clone https://github.com/a2aproject/a2a-samples.git

# Currency Agent 실행 (포트 10000)
cd a2a-samples/samples/python/agents/langgraph
uv run app --port 10000

# Hello World Agent 실행 (포트 9999)
cd ../helloworld
uv run . --port 9999
```

### 3. 웹 인터페이스 시작
```bash
# CORS 프록시 서버 실행 (포트 5000)
python proxy/proxy_server.py
```

### 4. 브라우저에서 접속
- **메인 모니터**: `http://localhost:5000/`
- **LangGraph 시각화**: `http://localhost:5000/docs/langgraph_visualization.html`

## 🔧 API 키 설정

### Google Gemini API 키 (Currency Agent용)
```bash
# .env 파일 생성 (a2a-samples/samples/python/agents/langgraph/.env)
GOOGLE_API_KEY=your_actual_google_gemini_api_key_here
```

## 📊 시각화 기능

### 1. **웹 기반 시각화**
- Mermaid.js 기반 인터랙티브 다이어그램
- 노드/엣지 상세 정보
- 실시간 업데이트
- 줌/새로고침 컨트롤

### 2. **LangGraph Studio**
```bash
# LangGraph Studio 실행
cd agents/currency
langgraph dev --port 8123
```
- 전문적 디버깅 인터페이스
- 실행 추적
- Human-in-the-loop 워크플로우

### 3. **그래프 추출**
```bash
# 그래프 구조 추출 및 시각화
python scripts/visualize_graph.py
```

## 🌐 네트워크 구성

### 포트 할당
- **5000**: CORS 프록시 서버
- **9999**: Hello World Agent
- **10000**: Currency Agent
- **8123**: LangGraph Studio (선택사항)

### 에이전트 디스커버리
- **Agent Card**: `/.well-known/agent-card.json`
- **A2A Protocol**: JSON-RPC 2.0 over HTTP(S)
- **Worker-to-Worker**: 직접 HTTP 통신

## 🧪 테스트

### 1. Worker 통신 테스트
```bash
python scripts/test_worker_to_worker.py
```

### 2. 웹 인터페이스 테스트
- 브라우저에서 `http://localhost:5000/` 접속
- "Hello World Agent" 선택하여 메시지 전송
- "🔄 View LangGraph Workflow" 버튼 클릭

### 3. API 직접 테스트
```bash
# Hello Agent 테스트
curl -X POST http://localhost:9999 \\
  -H "Content-Type: application/json" \\
  -d '{"jsonrpc": "2.0", "method": "message/send", "params": {"message": {"kind": "message", "messageId": "test", "parts": [{"kind": "text", "text": "Hello"}], "role": "user"}}, "id": "test"}'
```

## 🔍 트러블슈팅

### 일반적인 문제들

1. **"failed to fetch" 오류**
   - CORS 프록시 서버가 실행 중인지 확인
   - `http://localhost:5000` 접속 확인

2. **Currency Agent "Internal error"**
   - Google API 키가 설정되었는지 확인
   - Hello Agent는 API 키 없이도 작동

3. **포트 충돌**
   - 각 서비스가 다른 포트를 사용하는지 확인
   - 필요시 포트 번호 수정

4. **의존성 오류**
   - `requirements.txt`의 모든 패키지 설치 확인
   - Python 3.12 사용 권장

## 📈 확장 가능성

### 새로운 에이전트 추가
1. A2A Protocol 준수하는 에이전트 개발
2. `proxy_server.py`에 새 에이전트 정보 추가
3. 웹 인터페이스에서 선택 옵션 추가

### 다른 LLM 모델 통합
- OpenAI GPT
- Anthropic Claude
- Local LLM (Ollama 등)

### 추가 시각화 도구
- D3.js 기반 커스텀 시각화
- Real-time 메트릭 대시보드
- 성능 모니터링 도구

## 🤝 기여

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다.

## 🙏 감사의 말

- **A2A Project**: Agent-to-Agent Protocol
- **LangChain**: LangGraph 프레임워크
- **Mermaid.js**: 다이어그램 시각화
- **Flask**: 웹 서버 프레임워크

---

**📧 문의사항이나 버그 리포트는 이슈로 등록해주세요!**