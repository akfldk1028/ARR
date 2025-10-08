# Voice Transcript Display System - 2025-10-02

## 프로젝트 개요

**A2A (Agent-to-Agent) 기반 멀티모달 음성 AI 시스템**

Django 백엔드 기반의 실시간 음성 대화 시스템으로, Google Gemini Live API와 STT(Speech-to-Text)를 결합하여 A2A 프로토콜을 통한 멀티 에이전트 협업을 구현합니다.

### 핵심 목표
1. **실시간 음성 대화**: Google Gemini Live API를 통한 자연스러운 음성 상호작용
2. **A2A 에이전트 협업**: 음성 입력 기반 의미론적 라우팅으로 전문 에이전트 위임
3. **실시간 Transcript 표시**: 사용자와 AI의 모든 음성을 텍스트로 실시간 표시
4. **한글 지원**: UTF-8 완전 지원 및 한글 음절 조합 최적화

---

## 시스템 아키텍처

### 1. 음성 시스템 (`gemini/`)

#### **핵심 파일들**

##### `gemini/consumers/simple_consumer.py`
- **역할**: WebSocket 메인 소비자, 모든 실시간 통신의 중심
- **주요 기능**:
  - WebSocket 연결 관리
  - Live API 세션 초기화
  - VAD+STT 시스템 초기화 및 콜백 관리
  - A2A 라우팅 처리
- **중요 코드 섹션**:
  - `lines 177-241`: VAD+STT 초기화 및 콜백 설정
  - `lines 243-292`: **STT transcript callback** (사용자 음성 → frontend 전송)
  - `lines 294-353`: A2A 응답 처리

##### `gemini/services/websocket_live_client.py`
- **역할**: Google Gemini Live API WebSocket 클라이언트
- **주요 기능**:
  - Live API와의 양방향 통신
  - 오디오 스트림 전송/수신
  - **Transcript 버퍼링 및 전송** (한글 음절 조합)
- **중요 코드 섹션**:
  - `line 54`: `transcript_timeout = 0.1` (100ms 버퍼링)
  - `lines 245-263`: **Input transcript 처리** (Live API → 사용자 음성)
  - `lines 265-289`: **Output transcript 처리** (Live API → AI 응답)
  - `lines 291-329`: Transcript 버퍼 flush 로직

##### `gemini/services/vad_stt_service.py`
- **역할**: VAD(음성 활동 감지) + STT(음성→텍스트) 통합 서비스
- **주요 기능**:
  - Silero VAD로 음성 구간 감지
  - Google Cloud STT로 한국어 인식
  - 실시간 오디오 청크 처리
  - Transcript 콜백 트리거

##### `gemini/consumers/handlers/a2a_handler.py`
- **역할**: A2A 에이전트 라우팅 로직
- **주요 기능**:
  - 의미론적 분석 (embedding similarity)
  - 전문 에이전트 결정 (예: flight-specialist)
  - Context-aware 라우팅

---

### 2. A2A 에이전트 시스템 (`agents/`)

#### **핵심 구조**

```
agents/
├── models.py                    # Agent 데이터베이스 모델
├── a2a_client.py               # A2A 프로토콜 클라이언트
├── views.py                    # A2A agent card endpoints
└── worker_agents/
    ├── base/
    │   └── base_worker.py      # BaseWorkerAgent 추상 클래스
    ├── implementations/
    │   ├── general_worker.py           # 일반 어시스턴트
    │   └── flight_specialist_worker.py # 항공권 예약 전문가
    ├── cards/
    │   ├── general_worker_card.json
    │   └── flight_specialist_card.json
    ├── worker_factory.py       # 에이전트 생성 팩토리
    └── worker_manager.py       # 에이전트 생명주기 관리
```

#### **A2A 프로토콜 준수**
- **Agent Card Discovery**: `/.well-known/agent-card/{slug}.json`
- **JSON-RPC 2.0**: 표준 메시지 포맷
- **양방향 통신**: 에이전트 간 상호 통신 가능

---

## 최근 달성한 목표 (2025-10-02)

### ✅ 문제 1: Live API Transcript 지연 해결
**증상**: Live API의 transcript가 500ms 지연되어 실시간성 부족

**해결**:
- `websocket_live_client.py:54` - `transcript_timeout = 0.5` → `0.1` (100ms)
- 실시간 느낌 유지하면서 한글 음절 조합 보장

### ✅ 문제 2: 한글 텍스트 음절 단위 분리 현상 해결
**증상**: Live API가 한글을 음절별로 전송 ("네 비", "행기", "예약에")

**해결**:
- Buffering 로직 유지 (완전 제거하면 음절 분리 발생)
- 100ms 타임아웃으로 빠른 조합 + 완전한 단어 표시

### ✅ 문제 3: STT Transcript Frontend 미표시 해결
**증상**: 사용자가 말한 내용(STT)이 채팅창에 안 나타남

**해결**:
- `simple_consumer.py:253-260` - STT transcript callback에 frontend 전송 코드 추가
```python
await self.send(text_data=json.dumps({
    'type': 'transcript',
    'text': transcript_text,
    'sender': 'user',
    'source': 'stt'
}))
```

---

## Transcript 플로우 (최종 완성 버전)

### 1. Live API Input Transcript (사용자 음성)
```
Live API → inputTranscription event
    ↓
websocket_live_client._handle_input_transcript()
    ↓
100ms buffering (한글 음절 조합)
    ↓
Frontend WebSocket: {type: 'transcript', sender: 'user', source: 'live_api_input'}
```

### 2. Live API Output Transcript (AI 응답)
```
Live API → outputTranscription event
    ↓
websocket_live_client._handle_output_transcript()
    ↓
100ms buffering (한글 음절 조합)
    ↓
Frontend WebSocket: {type: 'transcript', sender: 'ai', source: 'live_api_output'}
```

### 3. STT Transcript (사용자 음성 - VAD 감지)
```
User Audio → VAD (음성 감지) → STT (Google Cloud)
    ↓
stt_transcript_callback() in simple_consumer.py
    ↓
Noise filtering (<noise>, <silence> 제거)
    ↓
즉시 Frontend 전송: {type: 'transcript', sender: 'user', source: 'stt'}
    ↓
A2A 라우팅 분석 (필요시 전문 에이전트 위임)
```

---

## 기술 스택

### Backend
- **Django**: 웹 프레임워크
- **Django Channels**: WebSocket 지원
- **Daphne**: ASGI 서버 (비동기 처리)

### AI/ML
- **Google Gemini 2.0 Flash Live API**: 실시간 멀티모달 대화
- **Google Cloud Speech-to-Text**: 한국어 STT (ko-KR)
- **Silero VAD**: 음성 활동 감지 (16kHz)
- **LangGraph**: 에이전트 워크플로우 (SemanticKernel 대체)

### Database
- **Neo4j**: 그래프 데이터베이스 (에이전트 지식 관리)

### Protocols
- **A2A Protocol**: Google/Linux Foundation 표준 (Agent-to-Agent)
- **JSON-RPC 2.0**: A2A 메시지 포맷

---

## 개발 환경 설정

### 서버 실행
```bash
# Port 8004에서 Django 서버 실행
python -X utf8 -m daphne -p 8004 backend.asgi:application
```

### 환경 변수 (필수)
```bash
GOOGLE_API_KEY=<Gemini API key>
GOOGLE_APPLICATION_CREDENTIALS=<Google Cloud STT 인증 JSON>
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>
```

### 의존성
```
Django==4.2+
channels==4.0+
daphne
google-generativeai
google-cloud-speech
torch (for Silero VAD)
langchain
langgraph
neo4j
```

---

## 주요 디버깅 포인트

### Transcript 관련 로그 확인
```python
# simple_consumer.py
logger.info(f"STT Transcript received: {safe_log_text(transcript_text)}")
logger.info(f"Sent STT transcript to frontend: {safe_log_text(transcript_text)}")

# websocket_live_client.py
logger.info(f"User transcript: {safe_log_text(combined_text)}")
logger.info(f"AI transcript: {safe_log_text(combined_text)}")
```

### 일반적인 문제들

1. **Transcript 안 나옴**
   - WebSocket 연결 상태 확인
   - `transcript_timeout` 값 확인 (0.1 권장)
   - Frontend에서 'transcript' type 메시지 처리 확인

2. **한글 깨짐**
   - UTF-8 인코딩 확인 (`-X utf8` 플래그)
   - `safe_log_text()` 함수 사용 (encoding 보호)

3. **STT 작동 안 함**
   - Google Cloud credentials 확인
   - VAD 초기화 로그 확인
   - 마이크 권한 확인

---

## 다음 단계 (Next Implementation Tasks)

### 🚀 즉시 구현 필요: 텍스트 기반 A2A 통합

**현재 상황**: 음성 입력만 A2A 라우팅이 작동합니다.

**구현 목표**: 텍스트 입력(채팅)도 A2A 라우팅 + Neo4j 연동이 자동으로 작동해야 합니다.

#### 필수 구현 사항

1. **텍스트 메시지 A2A 라우팅 활성화**
   - `gemini/consumers/simple_consumer.py`의 `receive()` 메서드 수정
   - 텍스트 메시지에도 의미론적 분석 적용
   - A2A handler를 통한 자동 에이전트 위임

2. **Neo4j 대화 기록 저장**
   - 모든 텍스트 대화를 Neo4j에 저장
   - User-Agent-Message 관계 그래프 구축
   - Context 및 Session 추적

3. **참조해야 할 핵심 디렉토리**: **`D:\Data\11_Backend\01_ARR\backend\agents`**

   **핵심 파일들:**
   - `agents/worker_agents/base/base_worker.py` - 에이전트 베이스 클래스
   - `agents/worker_agents/implementations/flight_specialist_worker.py` - 항공권 전문 에이전트
   - `agents/worker_agents/implementations/general_worker.py` - 일반 어시스턴트
   - `agents/database/neo4j/service.py` - Neo4j 서비스 (대화 저장)
   - `agents/a2a_client.py` - A2A 프로토콜 클라이언트
   - `agents/worker_agents/worker_manager.py` - 에이전트 생명주기 관리

#### 구현 가이드

**Step 1: 텍스트 메시지 A2A 라우팅**
```python
# gemini/consumers/simple_consumer.py의 receive() 메서드에서

async def receive(self, text_data):
    data = json.loads(text_data)
    message_type = data.get('type')

    if message_type == 'chat_message':
        user_message = data.get('message')

        # A2A 라우팅 분석 추가
        routing_result = await self.a2a_handler._analyze_intent_with_similarity(
            user_message, 'text-input'
        )

        if routing_result.get('should_delegate', False):
            # 전문 에이전트로 위임
            target_agent = routing_result.get('target_agent')
            agent = await self.worker_manager.get_worker(target_agent)

            response = await agent.process_request(
                user_input=user_message,
                context_id=self.session_id,
                session_id=self.session_id,
                user_name=self.user_obj.username
            )

            # Neo4j에 저장 (agent.process_request 내부에서 자동)
        else:
            # Live API로 전달 (기존 로직)
            pass
```

**Step 2: Neo4j 대화 저장 확인**
```python
# agents/database/neo4j/service.py 활용

from agents.database.neo4j.service import Neo4jService

neo4j_service = Neo4jService()

# 대화 저장 (BaseWorkerAgent.process_request에서 자동 호출)
await neo4j_service.store_conversation(
    user_name=user_name,
    agent_slug=self.agent_slug,
    user_message=user_input,
    agent_response=response_text,
    context_id=context_id
)
```

**Step 3: A2A 에이전트 테스트**
```bash
# 텍스트로 항공권 예약 테스트
# Frontend에서 텍스트 입력: "서울에서 도쿄 가는 비행기 알아봐줘"
# 기대 결과:
# 1. A2A 라우팅 → flight-specialist 에이전트로 위임
# 2. Neo4j에 대화 저장
# 3. 응답 반환
```

#### Neo4j 그래프 구조
```cypher
// 저장되는 노드 및 관계
(User)-[:SENT]->(Message)-[:PROCESSED_BY]->(Agent)
(Message)-[:IN_SESSION]->(Session)
(Message)-[:IN_CONTEXT]->(Context)
(Agent)-[:RESPONDED_WITH]->(Response)
```

---

### 기타 계획된 개선사항

1. **Transcript 품질 향상**
   - 더 정교한 한글 조합 로직
   - 문장 단위 버퍼링

2. **A2A 라우팅 고도화**
   - 더 많은 전문 에이전트 추가
   - Context 유지 개선
   - Multi-turn 대화 지원

3. **성능 최적화**
   - Transcript 버퍼링 알고리즘 개선
   - 메모리 사용량 최적화
   - Neo4j 쿼리 최적화

4. **모니터링**
   - Transcript 지연 시간 메트릭
   - A2A 라우팅 정확도 추적
   - Neo4j 성능 모니터링

---

## 참조 문서

### 프로젝트 내부
- `CLAUDE.md` - A2A 시스템 전체 개요
- `AGENTS.md` - 에이전트 구조 상세 설명
- `docs/2025-09-30_hybrid_voice_architecture.md` - 음성 시스템 아키텍처

### 외부 문서
- [A2A Protocol Specification](https://a2a-protocol.org)
- [Google Gemini Live API](https://ai.google.dev/api/multimodal-live)
- [Google Cloud Speech-to-Text](https://cloud.google.com/speech-to-text)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)

---

## 핵심 파일 요약 (AI 참조용)

### 반드시 확인해야 할 파일

#### 음성 시스템 (Gemini)
1. **`gemini/consumers/simple_consumer.py`** - WebSocket 소비자, STT callback, **텍스트 A2A 라우팅 구현 필요**
2. **`gemini/services/websocket_live_client.py`** - Live API 클라이언트, transcript buffering
3. **`gemini/services/vad_stt_service.py`** - VAD+STT 통합
4. **`gemini/consumers/handlers/a2a_handler.py`** - A2A 라우팅 로직

#### A2A 에이전트 시스템 (Agents) - **텍스트 A2A 구현 시 필수 참조**
5. **`agents/worker_agents/base/base_worker.py`** - BaseWorkerAgent 클래스, process_request 메서드
6. **`agents/worker_agents/implementations/flight_specialist_worker.py`** - 항공권 전문 에이전트
7. **`agents/worker_agents/implementations/general_worker.py`** - 일반 어시스턴트
8. **`agents/database/neo4j/service.py`** - Neo4j 서비스 (대화 저장 로직)
9. **`agents/a2a_client.py`** - A2A 프로토콜 클라이언트
10. **`agents/worker_agents/worker_manager.py`** - 에이전트 생명주기 관리

### 설정 파일
- **`backend/settings.py`** - Django 설정, ASGI 설정
- **`gemini/routing.py`** - WebSocket URL 라우팅
- **`agents/worker_agents/cards/*.json`** - A2A agent card 정의

### 테스트/예제
- **`test_websocket.py`** - WebSocket 테스트
- **`test_korean_flight_routing.py`** - 한글 A2A 라우팅 테스트

---

## 성공 지표

### 현재 달성 상태 (2025-10-02)
- ✅ Live API transcript 실시간 표시 (100ms latency)
- ✅ STT transcript 실시간 표시
- ✅ 한글 음절 조합 완벽 지원
- ✅ A2A 에이전트 라우팅 작동
- ✅ 양방향 음성 대화 가능
- ✅ WebSocket 안정성 확보

### 검증 방법
1. 음성으로 "비행기 예약해줘" 말하기
2. 채팅창에 transcript 즉시 표시 확인
3. Flight specialist 에이전트로 라우팅 확인
4. AI 응답이 실시간으로 transcript와 음성으로 나오는지 확인

---

**작성일**: 2025년 10월 2일
**작성자**: Voice Transcript System Development Team
**상태**: Production Ready ✅
