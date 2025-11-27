# 법률 검색 시스템 - 서버 관리 가이드

**작성일**: 2025-11-25
**대상**: 다음 AI 어시스턴트 및 개발자

---

## 📋 목차

1. [빠른 시작](#빠른-시작)
2. [서버 구성](#서버-구성)
3. [자동 실행 스크립트](#자동-실행-스크립트)
4. [수동 실행 방법](#수동-실행-방법)
5. [서버 종료](#서버-종료)
6. [트러블슈팅](#트러블슈팅)
7. [다음 AI를 위한 체크리스트](#다음-ai를-위한-체크리스트)

---

## 🚀 빠른 시작

### 방법 1: 자동 실행 (권장) ⭐

```bash
# PowerShell 버전 (관리자 권한 불필요)
.\start_servers.ps1

# 또는 Batch 버전 (더블클릭)
start_servers.bat
```

**완료!** 3개 서버가 별도 창에서 실행됩니다.

### 방법 2: 수동 실행

[수동 실행 방법](#수동-실행-방법) 섹션 참조

---

## 🖥️ 서버 구성

이 시스템은 **3개 서버**가 필요합니다:

| 서버 | 포트 | 실행 명령 | 필수 여부 |
|------|------|-----------|-----------|
| **Neo4j** | 7687 (Bolt), 7474 (Browser) | Neo4j Desktop 실행 | ✅ 필수 |
| **Django Backend** | 8000 | `daphne -b 0.0.0.0 -p 8000 backend.asgi:application` | ✅ 필수 |
| **React Frontend** | 5173 | `npm run dev` | ✅ 필수 |

### 서버 역할

```
┌──────────────────┐
│  React Frontend  │ ← 사용자 인터페이스 (브라우저)
│   Port: 5173     │
└──────────────────┘
         ↓ HTTP/SSE
┌──────────────────┐
│ Django Backend   │ ← API 서버, A2A 협업, SSE 스트리밍
│   Port: 8000     │
└──────────────────┘
         ↓ Bolt
┌──────────────────┐
│  Neo4j Database  │ ← 그래프 DB, 법률 데이터
│   Port: 7687     │
└──────────────────┘
```

---

## 🤖 자동 실행 스크립트

### 1. `start_servers.ps1` (PowerShell)

**위치**: `D:\Data\11_Backend\01_ARR\start_servers.ps1`

**실행 방법:**
```powershell
# PowerShell에서
.\start_servers.ps1

# 또는 탐색기에서
# 우클릭 → "Run with PowerShell"
```

**기능:**
- Neo4j 상태 확인 (자동)
- Django Backend 시작 (별도 창)
- React Frontend 시작 (별도 창)
- 컬러 출력, 진행 상황 표시
- 에러 처리 및 안내 메시지

**출력 예시:**
```
========================================
  Law Search System - Starting Servers
========================================

[1/3] Checking Neo4j...
  ✅ Neo4j is already running (Port 7687)

[2/3] Starting Django Backend (Daphne ASGI)...
  ✅ Backend server starting... (Port 8000)

[3/3] Starting React Frontend (Vite)...
  ✅ Frontend server starting... (Port 5173)

========================================
  ✅ All Servers Started!
========================================

Server URLs:
  • Backend:  http://localhost:8000
  • Frontend: http://localhost:5173
  • Neo4j:    http://localhost:7474
```

---

### 2. `start_servers.bat` (Batch)

**위치**: `D:\Data\11_Backend\01_ARR\start_servers.bat`

**실행 방법:**
```bash
# CMD에서
start_servers.bat

# 또는 탐색기에서
# 더블클릭
```

**기능:**
- PowerShell 버전과 동일
- Batch 파일이므로 더블클릭으로 바로 실행
- UTF-8 인코딩 지원 (한글 정상 출력)

---

### 3. `stop_servers.ps1` (서버 종료)

**위치**: `D:\Data\11_Backend\01_ARR\stop_servers.ps1`

**실행 방법:**
```powershell
.\stop_servers.ps1
```

**기능:**
- Port 8000 프로세스 종료 (Django)
- Port 5173 프로세스 종료 (React)
- Neo4j는 종료하지 않음 (수동 관리)

**출력 예시:**
```
========================================
  Law Search System - Stopping Servers
========================================

[1/2] Stopping Django Backend (Port 8000)...
  ✅ Stopped process PID: 12345

[2/2] Stopping React Frontend (Port 5173)...
  ✅ Stopped process PID: 67890

========================================
  ✅ Server Shutdown Complete
========================================

Note: Neo4j was NOT stopped (manual management)
```

---

## 🔧 수동 실행 방법

### 1. Neo4j 시작

**방법 1: Neo4j Desktop**
1. Neo4j Desktop 실행
2. 프로젝트 선택
3. "Start" 버튼 클릭

**확인:**
```bash
netstat -ano | findstr ":7687"
# 출력: TCP    127.0.0.1:7687 ... LISTENING
```

---

### 2. Django Backend 시작 (Daphne ASGI)

**중요**: 반드시 **Daphne ASGI**로 실행해야 합니다!

```bash
cd D:\Data\11_Backend\01_ARR\backend
.venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

**확인:**
```bash
netstat -ano | findstr "0.0.0.0:8000"
# 출력: TCP    0.0.0.0:8000 ... LISTENING
```

**❌ 잘못된 방법:**
```bash
# 이렇게 하면 SSE 스트리밍이 작동하지 않습니다!
python manage.py runserver
```

**왜 Daphne인가?**
- Django의 **ASGI** (비동기) 지원 필요
- **SSE (Server-Sent Events)** 스트리밍 구현
- **WebSocket** 지원 (A2A 통신)

---

### 3. React Frontend 시작 (Vite)

```bash
cd D:\Data\11_Backend\01_ARR\frontend
npm run dev
```

**확인:**
```bash
netstat -ano | findstr ":5173"
# 출력: TCP    [::1]:5173 ... LISTENING
```

**브라우저 접속:**
```
http://localhost:5173
```

---

## 🛑 서버 종료

### 방법 1: 자동 종료 스크립트 (권장)

```powershell
.\stop_servers.ps1
```

### 방법 2: 수동 종료

#### Option A: 창 닫기
- 각 서버 실행 창(PowerShell/CMD)을 닫기

#### Option B: 포트별 종료
```powershell
# Django Backend (Port 8000)
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# React Frontend (Port 5173)
Get-NetTCPConnection -LocalPort 5173 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

#### Option C: PID로 종료
```bash
# 1. PID 확인
netstat -ano | findstr ":8000"
# 출력: TCP  0.0.0.0:8000  ...  LISTENING  12345

# 2. PID로 종료
taskkill /PID 12345 /F
```

---

## 🔍 트러블슈팅

### 문제 1: "Neo4j가 실행되지 않았습니다"

**증상:**
```
⚠️  Neo4j is NOT running!
```

**해결:**
1. Neo4j Desktop 실행
2. 프로젝트 선택 → "Start" 클릭
3. 확인: `netstat -ano | findstr ":7687"`

---

### 문제 2: "Port 8000이 이미 사용 중입니다"

**증상:**
```
Error: [Errno 10048] Address already in use
```

**해결:**
```powershell
# 1. 사용 중인 프로세스 확인
netstat -ano | findstr ":8000"

# 2. PID 종료
Stop-Process -Id <PID> -Force

# 3. 재시작
.\start_servers.ps1
```

---

### 문제 3: "Frontend에서 Backend 연결 실패"

**증상:**
- 브라우저 콘솔: `Failed to fetch` 또는 `404 Not Found`

**확인사항:**
```bash
# Backend가 0.0.0.0:8000으로 바인딩되었는지 확인
netstat -ano | findstr "0.0.0.0:8000"
```

**해결:**
1. Backend 종료
2. Daphne ASGI로 재시작 (127.0.0.1 아님!)
   ```bash
   .venv\Scripts\python.exe -m daphne -b 0.0.0.0 -p 8000 backend.asgi:application
   ```
3. 브라우저 새로고침 (Ctrl+Shift+R)

---

### 문제 4: "PowerShell 스크립트 실행 권한 오류"

**증상:**
```
.\start_servers.ps1 : File cannot be loaded because running scripts is disabled
```

**해결:**
```powershell
# 현재 세션에만 적용 (권장)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 그 다음 스크립트 실행
.\start_servers.ps1
```

---

## ✅ 다음 AI를 위한 체크리스트

### 서버 시작 시

- [ ] Neo4j Desktop 실행 (Port 7687)
- [ ] `start_servers.ps1` 또는 `start_servers.bat` 실행
- [ ] 3개 창이 열렸는지 확인 (Backend, Frontend)
- [ ] 10-15초 대기 (서버 초기화 시간)
- [ ] http://localhost:5173 접속 확인
- [ ] Backend API 테스트: `curl http://localhost:8000/agents/law/api/health`

### 서버 종료 시

- [ ] `stop_servers.ps1` 실행
- [ ] 또는 각 창 수동 닫기
- [ ] 포트 확인: `netstat -ano | findstr ":8000 :5173"`
- [ ] Neo4j는 수동으로 종료 (선택)

### 트러블슈팅 시

- [ ] Neo4j 상태 확인: `netstat -ano | findstr ":7687"`
- [ ] Backend 바인딩 확인: `netstat -ano | findstr "0.0.0.0:8000"`
- [ ] Frontend 포트 확인: `netstat -ano | findstr ":5173"`
- [ ] 각 서버 로그 확인 (실행 창)
- [ ] 브라우저 개발자 도구 콘솔 확인 (F12)

---

## 📁 파일 구조

```
D:\Data\11_Backend\01_ARR\
│
├─ start_servers.ps1        ⭐ PowerShell 시작 스크립트
├─ start_servers.bat        ⭐ Batch 시작 스크립트
├─ stop_servers.ps1         ⭐ 종료 스크립트
├─ SERVER_MANAGEMENT_GUIDE.md ⭐ 이 문서
├─ SYSTEM_STARTUP_GUIDE.md  (기존 수동 가이드)
│
├─ backend\
│  ├─ manage.py
│  ├─ backend\asgi.py       (Daphne ASGI 진입점)
│  └─ .venv\                (가상환경)
│
└─ frontend\
   ├─ package.json
   └─ vite.config.ts        (Vite 설정)
```

---

## 🎯 핵심 요약 (다음 AI용)

### 실행 명령어

```powershell
# 시작
.\start_servers.ps1

# 종료
.\stop_servers.ps1

# 상태 확인
netstat -ano | findstr ":7687 :8000 :5173"
```

### 중요 사항

1. **Neo4j 먼저 실행** (수동)
2. **Backend는 Daphne ASGI로 실행** (`0.0.0.0:8000`)
3. **Frontend는 Vite로 실행** (Port `5173`)
4. **10-15초 대기** 후 브라우저 접속

### 문제 발생 시

1. 각 서버 로그 확인 (실행 창)
2. 포트 충돌 확인 (`netstat`)
3. Backend 바인딩 확인 (`0.0.0.0` 여부)
4. 브라우저 콘솔 확인 (F12)

---

## 📚 참고 문서

- **SYSTEM_STARTUP_GUIDE.md** - 수동 실행 상세 가이드
- **PRESENTATION_COMPACT.md** - 시스템 아키텍처 및 플로우
- **backend/docs/** - 백엔드 상세 문서

---

**마지막 업데이트**: 2025-11-25
**작성자**: Claude AI Assistant
**상태**: Production Ready ✅
