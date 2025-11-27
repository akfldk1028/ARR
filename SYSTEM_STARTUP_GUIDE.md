# 법률 검색 시스템 - 실행 가이드

**최종 업데이트**: 2025-11-24
**상태**: Production Ready ✅

---

## 📋 시스템 구성

이 시스템은 3개 서버로 구성됩니다:

1. **Neo4j 그래프 데이터베이스** - `bolt://127.0.0.1:7687`
2. **Django 백엔드 (Daphne ASGI)** - `http://0.0.0.0:8000`
3. **React 프론트엔드 (Vite)** - `http://localhost:5173`

---

## 🚀 서버 실행 순서

### 1. Neo4j 데이터베이스 시작

Neo4j Desktop 또는 서비스로 실행:
```bash
# Neo4j Desktop에서 Start 버튼 클릭
# 또는 서비스로 실행
```

**확인**:
```bash
netstat -ano | findstr ":7687"
```
→ `LISTENING` 상태여야 함

---

### 2. Django 백엔드 시작 (Daphne ASGI)

**중요**: 일반 Django 서버가 아닌 **Daphne ASGI 서버**로 실행해야 합니다!

#### 방법 1: CMD 직접 실행
```bash
cd D:\Data\11_Backend\01_ARR\backend
.venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

#### 방법 2: PowerShell로 백그라운드 실행
```powershell
powershell -Command "Start-Process cmd -ArgumentList '/k','cd /d D:\Data\11_Backend\01_ARR\backend && .venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application'"
```

**확인**:
```bash
netstat -ano | findstr ":8000"
```
→ `0.0.0.0:8000` LISTENING 상태여야 함 (127.0.0.1이 아님!)

**왜 Daphne인가?**
- Django의 ASGI (비동기) 지원 필요
- SSE (Server-Sent Events) 스트리밍 구현
- WebSocket 지원 (A2A 통신)

---

### 3. React 프론트엔드 시작 (Vite)

```bash
cd D:\Data\11_Backend\01_ARR\frontend
npm run dev
```

**확인**:
```bash
netstat -ano | findstr ":5173"
```
→ `[::1]:5173` LISTENING 상태

**접속**: `http://localhost:5173`

---

## 🔍 전체 시스템 상태 확인

### 빠른 확인 스크립트

```bash
# Neo4j (7687)
netstat -ano | findstr ":7687"

# Django Backend (8000) - 0.0.0.0로 바인딩되어야 함!
netstat -ano | findstr ":8000"

# React Frontend (5173)
netstat -ano | findstr ":5173"
```

### 정상 상태 예시

```
Neo4j:
  TCP    127.0.0.1:7687         0.0.0.0:0              LISTENING       35224

Django:
  TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING       520

React:
  TCP    [::1]:5173             [::]:0                 LISTENING       41096
```

---

## ⚠️ 자주 발생하는 문제

### 문제 1: 프론트엔드에서 "백엔드 서버에 연결할 수 없습니다" 또는 404 에러

**원인**:
- Django가 `127.0.0.1:8000`으로 실행 중 (Daphne가 아닌 일반 runserver)
- Daphne가 Django 앱을 제대로 로드하지 못함

**해결**:
1. 모든 Django/Daphne 프로세스 종료:
   ```bash
   # 8000 포트의 모든 PID 확인
   netstat -ano | findstr ":8000"

   # 각 프로세스 종료 (PID 520, 34180 등 모두)
   powershell -Command "Stop-Process -Id [PID] -Force"
   powershell -Command "Stop-Process -Id [PID2] -Force"
   ```

2. Daphne ASGI 서버로 재시작 (venv 활성화 포함):
   ```bash
   powershell -Command "Start-Process cmd -ArgumentList '/k','cd /d D:\Data\11_Backend\01_ARR\backend && .venv\Scripts\activate && python -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application'"
   ```

3. `0.0.0.0:8000` 바인딩 확인:
   ```bash
   netstat -ano | findstr "0.0.0.0:8000"
   ```
   → **반드시 `0.0.0.0:8000` LISTENING이어야 함!**

4. 프론트엔드 브라우저 새로고침 (Ctrl+Shift+R)

---

### 문제 2: Neo4j 연결 실패

**확인**:
```bash
cd D:\Data\11_Backend\01_ARR\backend
.venv\Scripts\python.exe test_system_ready.py
```

**해결**:
- Neo4j Desktop에서 데이터베이스 시작
- `.env` 파일에서 Neo4j 비밀번호 확인
  ```
  NEO4J_URI=bolt://localhost:7687
  NEO4J_USER=neo4j
  NEO4J_PASSWORD=your_password
  ```

---

### 문제 3: 프론트엔드 포트 충돌

**증상**: `Port 5173 is already in use`

**해결**:
```bash
# 5173 포트 사용 프로세스 확인
netstat -ano | findstr ":5173"

# 프로세스 종료
powershell -Command "Stop-Process -Id [PID] -Force"

# 프론트엔드 재시작
cd D:\Data\11_Backend\01_ARR\frontend
npm run dev
```

---

## 📊 시스템 검증

모든 서버가 실행된 후:

```bash
cd D:\Data\11_Backend\01_ARR\backend
.venv\Scripts\python.exe test_system_ready.py
```

**정상 출력**:
```
✅ Neo4j 연결 성공
✅ HANG 노드: 1,591개 (3,072-dim embeddings)
✅ CONTAINS 관계: 3,978개 (3,072-dim embeddings)
✅ Domains: 5개
✅ Vector Index: ONLINE

시스템 상태: Production Ready ✅
```

---

## 🧪 테스트 실행

### 36조 검색 테스트
```bash
cd D:\Data\11_Backend\01_ARR\backend
.venv\Scripts\python.exe test_36jo_comprehensive.py
```

**예상 결과**: 8개 조항 (법률 4개, 시행령 2개, 시행규칙 1개)

### 용도지역 A2A 협업 테스트
프론트엔드에서 "용도지역" 검색
- Primary Domain: "토지 이용 및 기반시설" (6개)
- A2A 협업: 2개 도메인 (4개 추가)
- 최종: 10개 조항 (+67% 증가)

---

## 📁 주요 파일 위치

### 백엔드
- **설정**: `backend/backend/settings.py`
- **ASGI**: `backend/backend/asgi.py`
- **환경변수**: `backend/.env`
- **Domain Agent**: `backend/agents/law/domain_agent.py`
- **Agent Manager**: `backend/agents/law/agent_manager.py`
- **RNE 알고리즘**: `backend/graph_db/algorithms/core/semantic_rne.py`

### 프론트엔드
- **설정**: `frontend/package.json`
- **Law Search Hook**: `frontend/src/law/hooks/use-law-search-stream.ts`
- **SSE 통합**: `frontend/src/law/components/SearchProgress.tsx`

### 데이터
- **Neo4j 데이터**: Neo4j Desktop에서 관리
- **JSON 파일**: `backend/law/data/parsed/*.json`

---

## 🔄 시스템 재시작 순서

1. **모든 서버 종료**:
   ```bash
   # 각 프로세스 PID 확인 후 종료
   netstat -ano | findstr ":8000"
   netstat -ano | findstr ":5173"
   powershell -Command "Stop-Process -Id [PID] -Force"
   ```

2. **Neo4j 확인** (계속 실행 중)

3. **백엔드 재시작** (Daphne):
   ```bash
   cd D:\Data\11_Backend\01_ARR\backend
   .venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application
   ```

4. **프론트엔드 재시작**:
   ```bash
   cd D:\Data\11_Backend\01_ARR\frontend
   npm run dev
   ```

5. **브라우저 접속**: `http://localhost:5173`

---

## 💡 핵심 포인트

### ⭐ 반드시 기억할 것

1. **백엔드는 Daphne ASGI로 실행**
   - `daphne -b 0.0.0.0 -p 8000 backend.asgi:application`
   - `0.0.0.0`으로 바인딩 (127.0.0.1 아님!)

2. **프론트엔드 포트는 5173** (7777 아님!)
   - `npm run dev` → `http://localhost:5173`

3. **실행 순서**: Neo4j → Django (Daphne) → React (Vite)

4. **시스템 검증**:
   ```bash
   .venv\Scripts\python.exe test_system_ready.py
   ```

---

## 📞 트러블슈팅 체크리스트

- [ ] Neo4j 실행 중? (`netstat -ano | findstr ":7687"`)
- [ ] Django Daphne로 실행 중? (`netstat -ano | findstr "0.0.0.0:8000"`)
- [ ] React 실행 중? (`netstat -ano | findstr ":5173"`)
- [ ] 프론트엔드에서 백엔드 접속 가능? (`http://localhost:5173`)
- [ ] test_system_ready.py 통과?

---

## 🎯 다음 AI를 위한 요약

```
시스템 실행 = 3개 서버 필요

1. Neo4j (7687) - 그래프 DB
2. Django Daphne (0.0.0.0:8000) - ASGI 백엔드 ⚠️ 중요!
3. React Vite (5173) - 프론트엔드

Daphne 실행 명령어:
  cd D:\Data\11_Backend\01_ARR\backend
  .venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application

검증:
  .venv\Scripts\python.exe test_system_ready.py

모든 서버 실행 후 → http://localhost:5173 접속
```

---

**현재 상태 (2025-11-24)**:
- ✅ Neo4j: 실행 중
- ✅ Django Daphne: 실행 중 (`0.0.0.0:8000`)
- ✅ React Vite: 실행 중 (`5173`)
- ✅ Production Ready

시스템 정상 작동 중! 🚀
