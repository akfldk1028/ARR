# 법률 채팅 테스트 가이드

**작성일**: 2025-11-02
**목적**: 법률 검색 채팅 UI 테스트 방법

---

## ✅ 구현 완료 내역

### 1. 파일 생성
- ✅ `chat/templates/chat/law_chat.html` - 법률 전용 채팅 UI
- ✅ `chat/views.py` - `law_chat()` 뷰 추가
- ✅ `chat/urls.py` - `law/` 경로 추가

### 2. 기존 시스템 연동
- ✅ LawCoordinatorWorker 자동 등록 (worker_factory.py)
- ✅ law_coordinator_card.json 설정 완료
- ✅ WebSocket `/ws/chat/` 재사용

---

## 🚀 테스트 방법

### 1단계: 서버 시작

```bash
# 가상환경 활성화
.\.venv\Scripts\activate

# Neo4j 시작 확인 (Neo4j Desktop)
# - Neo4j Desktop에서 데이터베이스 "Start" 클릭
# - 또는 http://localhost:7474 접속해서 확인

# Daphne ASGI 서버 시작 (WebSocket 필수)
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

**중요**: `python manage.py runserver`는 WebSocket을 지원하지 않습니다!
반드시 `daphne` 명령어를 사용하세요.

---

### 2단계: 브라우저 접속

```
http://localhost:8000/chat/law/
```

**예상 화면**:
- 🎨 파란색 테마의 법률 검색 UI
- 📋 왼쪽 사이드바: 예시 질문 6개
- 💬 중앙: 채팅 영역
- 📊 통계: 검색 통계 표시

---

### 3단계: 연결 확인

**브라우저 콘솔 확인** (F12 → Console 탭):

```
✅ WebSocket connected
📨 Received: {type: "connection", ...}
🔄 Switching to law-coordinator...
✅ 법률 검색 시스템 준비 완료
```

**UI 확인**:
- ✅ "연결 완료! 법률 검색을 시작하세요." 메시지
- ✅ 우측 상단 "Law Coordinator ⚖️" 표시
- ✅ 녹색 연결 상태 표시등 깜빡임

---

### 4단계: 예시 질문 테스트

**사이드바 예시 질문 클릭**:

1. 🏙️ "도시지역 용적률 기준은?"
2. 🏢 "건축물 높이 제한 규정 알려줘"
3. 🌱 "토지 형질 변경 허가 절차는?"
4. 🏗️ "개발행위허가 대상은 무엇인가요?"
5. 📖 "국토계획법 제12조 내용이 뭐야?"
6. ⚖️ "법률과 시행령의 차이점은?"

**예상 동작**:
- 클릭 시 자동으로 입력창에 질문 입력
- 자동으로 전송
- 법률 검색 결과 반환

---

### 5단계: 수동 질의 테스트

**입력창에 직접 입력**:

```
용적률 기준 알려줘
```

**예상 응답** (예시):

```
'용적률 기준'에 대한 도시계획 관련 법률 정보입니다.

[핵심 조항]
1. 국토의 계획 및 이용에 관한 법률 > 제2장 > 제12조 > 제1항 (유사도: 0.89)
   도시지역 내 건축물의 용적률은 해당 지역의 특성을 고려하여...

2. 국토의 계획 및 이용에 관한 법률 시행령 > 제3조 (유사도: 0.85)
   법 제12조에 따른 용적률 산정 기준은 다음과 같다...

[검색 통계]
총 10개 조항 발견
- 벡터 검색: 5개
- 그래프 확장: 3개
- Cross-law: 2개
```

---

## 🔍 디버깅 체크리스트

### WebSocket 연결 실패 시

**증상**: "연결 오류 발생" 메시지

**원인**:
1. ❌ Daphne 서버가 실행 중이지 않음
2. ❌ `python manage.py runserver` 사용 (WebSocket 미지원)

**해결**:
```bash
# 기존 프로세스 종료
Ctrl + C

# Daphne로 재시작
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

---

### Agent 전환 실패 시

**증상**: "Agent 'law-coordinator' not found" 에러

**원인**: LawCoordinatorWorker가 등록되지 않음

**확인**:
```bash
# Django shell에서 확인
python manage.py shell

>>> from agents.worker_agents.worker_factory import WorkerAgentFactory
>>> WorkerAgentFactory.get_available_worker_types()
# 'law-coordinator'가 목록에 있어야 함
```

**해결** (등록되지 않은 경우):
```python
# agents/worker_agents/implementations/__init__.py 확인
from .law_coordinator_worker import LawCoordinatorWorker

__all__ = [
    'HostAgent',
    'FlightSpecialistWorkerAgent',
    'HotelSpecialistWorkerAgent',
    'LawCoordinatorWorker'  # ← 이 줄이 있어야 함
]
```

---

### Neo4j 연결 실패 시

**증상**: "Neo4j connection error"

**원인**: Neo4j 데이터베이스가 실행 중이지 않음

**해결**:
1. Neo4j Desktop 실행
2. 데이터베이스 "Start" 버튼 클릭
3. 브라우저에서 http://localhost:7474 접속 확인
4. 서버 재시작

---

### 검색 결과 없음

**증상**: "조항을 찾을 수 없습니다"

**원인**: Neo4j에 법률 데이터가 없음

**확인**:
```bash
# Neo4j Browser (http://localhost:7474)에서 실행
MATCH (h:HANG) RETURN count(h)
# 결과: 2,987개 이상이어야 함
```

**해결** (데이터가 없는 경우):
```bash
# 법률 데이터 로드 (이미 완료된 경우 생략)
.venv/Scripts/python.exe law/scripts/add_embeddings.py
```

---

## 📊 통계 확인

### 사이드바 통계 패널

**검색 후 업데이트되는 항목**:
- ✅ **검색된 조항**: 반환된 HANG 노드 개수
- ✅ **도메인 수**: 검색에 사용된 도메인 개수
- ✅ **평균 유사도**: 검색 결과의 평균 코사인 유사도
- ✅ **Cross-law 참조**: 법률→시행령→시행규칙 참조 개수

**시스템 정보** (고정):
- 알고리즘: RNE/INE
- 검색 방식: 3-Stage RAG
- 벡터 DB: Neo4j

---

## 🧪 테스트 시나리오

### 시나리오 1: 기본 검색

**질문**: "용적률 기준"

**예상 동작**:
1. ✅ Vector Search → Top 5 조항
2. ✅ Graph Expansion (RNE) → 주변 조항 추가
3. ✅ Reranking → Top 10 반환
4. ✅ 통계 업데이트

**확인 사항**:
- 응답 시간 < 3초
- 최소 5개 이상 조항 반환
- 유사도 > 0.70

---

### 시나리오 2: Cross-law 검색

**질문**: "법률 제12조에 대한 시행령은?"

**예상 동작**:
1. ✅ 법률 제12조 찾기
2. ✅ IMPLEMENTS 관계 따라 시행령 탐색
3. ✅ 시행규칙까지 확장
4. ✅ Cross-law 참조 개수 표시

**확인 사항**:
- Cross-law 참조 > 0
- 법률, 시행령, 시행규칙 모두 포함

---

### 시나리오 3: 복합 검색

**질문**: "건축 허가 관련 모든 법규"

**예상 동작**:
1. ✅ 다중 도메인 검색 (건축규제, 도시계획 등)
2. ✅ RNE/INE 알고리즘으로 연관 조항 확장
3. ✅ 10개 이상 조항 반환

**확인 사항**:
- 도메인 수 > 1
- 검색된 조항 > 10
- 응답 시간 < 5초

---

## 🎯 성공 기준

### UI 동작
- ✅ WebSocket 연결 성공
- ✅ Agent 자동 전환 (law-coordinator)
- ✅ 예시 질문 클릭 동작
- ✅ 메시지 송수신 정상

### 검색 품질
- ✅ 응답 시간 < 5초
- ✅ 유사도 > 0.70 조항 반환
- ✅ Cross-law 참조 동작
- ✅ 통계 업데이트

### 시스템 안정성
- ✅ Neo4j 연결 유지
- ✅ WebSocket 안정적 연결
- ✅ 에러 핸들링 정상

---

## 📝 테스트 로그 확인

### Django 서버 로그

```bash
# 서버 실행 시 확인할 로그

[INFO] Starting server at tcp:port=8000:interface=0.0.0.0
[INFO] Auto-discovering worker agent classes...
[INFO]   [OK] Registered: LawCoordinatorWorker
[INFO] Loading worker registry from JSON agent cards...
[INFO]   law-coordinator -> LawCoordinatorWorker
[INFO] AgentManager initialized
[INFO] Initializing domains from existing HANG nodes...
[INFO] Found 2987 existing HANG nodes
[INFO] ✅ Initialized 5 domains from 2987 HANG nodes
```

### 브라우저 콘솔 로그

```javascript
✅ WebSocket connected
📨 Received: {type: "connection", success: true, ...}
🔄 Switching to law-coordinator...
📨 Received: {type: "agent_switched", new_agent: "law-coordinator"}
✅ 법률 검색 시스템 준비 완료
```

---

## 🎉 완료!

모든 단계가 성공하면 법률 검색 챗봇이 정상 작동합니다!

**다음 단계** (선택 사항):
1. 더 많은 법률 PDF 업로드
2. 도메인 자동 생성 확인
3. 성능 벤치마크 테스트
4. 사용자 피드백 수집

---

## 📞 문제 발생 시

**로그 확인**:
```bash
# Django 로그
tail -f agents/logs/django_*.log

# Agent 통신 로그
tail -f agents/logs/agent_communication_*.json
```

**Neo4j 상태 확인**:
```cypher
// Neo4j Browser (http://localhost:7474)
MATCH (h:HANG) RETURN count(h)
MATCH (h:HANG)-[r:IMPLEMENTS]->(s:HANG) RETURN count(r)
```

**문제 보고**:
- 서버 로그 첨부
- 브라우저 콘솔 캡처
- 재현 단계 기록
