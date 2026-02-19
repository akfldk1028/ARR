# Frontend - Electron 데스크톱 앱

## 개요

법규 검색 Multi-Agent 시스템의 프론트엔드.
Electron + React + TypeScript + Tailwind CSS.

---

## 프로젝트 구조

```
frontend/
├── src/
│   ├── law/              ⭐ 법규 검색 UI (Django 백엔드 연동)
│   ├── google/           Google Maps/Live API
│   ├── components/       공통 컴포넌트
│   ├── pages/            페이지 컴포넌트
│   ├── hooks/            커스텀 훅
│   ├── store/            상태 관리 (Zustand)
│   ├── api/              HTTP 클라이언트
│   ├── i18n/             다국어 지원
│   └── routers/          라우팅
├── electron/             Electron 메인/프리로드
├── server/               Python 백엔드 (별도)
├── test/                 테스트
└── docs/                 문서
```

---

## 핵심 모듈

### src/law/ - 법규 검색 UI

Django 백엔드의 Multi-Agent 검색 시스템과 연동.

| 파일 | 역할 |
|------|------|
| `LawChat.tsx` | 메인 채팅 UI |
| `hooks/use-law-search-stream.ts` | SSE 스트리밍 |
| `hooks/use-law-chat.ts` | REST API |
| `contexts/LawAPIContext.tsx` | API 컨텍스트 |
| `components/` | UI 컴포넌트 |

**상세**: [src/law/README.md](./src/law/README.md)

### src/google/ - Google 통합

Google Maps 3D, Live API 통합.

| 파일 | 역할 |
|------|------|
| `GoogleMapsDemo.tsx` | Maps 3D 데모 |
| `contexts/LiveAPIContext.tsx` | Live API 컨텍스트 |
| `hooks/use-live-api.ts` | Live API 훅 |

---

## 실행 방법

### 개발 모드

```bash
# 의존성 설치
npm install

# 개발 서버 (Vite)
npm run dev

# Electron 앱 (개발)
npm run electron:dev
```

### 프로덕션 빌드

```bash
# 웹 빌드
npm run build

# Electron 빌드
npm run electron:build
```

---

## 백엔드 연동

| 백엔드 | URL | 용도 |
|--------|-----|------|
| Django | `http://127.0.0.1:8000` | 법규 검색 API |
| Python Server | `http://127.0.0.1:8011` | 로컬 서버 (선택) |

### Django 백엔드 실행

```bash
cd D:\Data\11_Backend\01_ARR\backend
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

---

## 라우팅

| 경로 | 컴포넌트 | 설명 |
|------|----------|------|
| `/` | Home | 메인 페이지 |
| `/law` | LawChat | 법규 검색 채팅 |
| `/setting` | Setting | 설정 |
| `/history` | History | 히스토리 |

---

## 기술 스택

| 카테고리 | 기술 |
|----------|------|
| Framework | React 18 |
| Language | TypeScript |
| Build | Vite |
| Desktop | Electron |
| Styling | Tailwind CSS |
| State | Zustand |
| Routing | React Router |
| i18n | react-i18next |
| Test | Vitest |

---

## 환경 변수

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_GOOGLE_MAPS_API_KEY=your-key
```

---

## 문서

- [src/law/README.md](./src/law/README.md) - 법규 검색 UI 상세
- [docs/get_started/](./docs/get_started/) - 시작 가이드
- [CONTRIBUTING.md](./CONTRIBUTING.md) - 기여 가이드
- [A2A_FILE_CHANGES_SUMMARY.md](./A2A_FILE_CHANGES_SUMMARY.md) - A2A 변경 요약
- [STREAMING_INTEGRATION_GUIDE.md](./STREAMING_INTEGRATION_GUIDE.md) - 스트리밍 통합

---

## 관련 프로젝트

| 디렉토리 | 역할 |
|----------|------|
| `../backend/` | Django 법규 검색 백엔드 |
| `../agent/` | AI 에이전트 예제 (학습용) |
