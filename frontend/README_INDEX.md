# README INDEX - Frontend 문서 목차

> **목적**: Frontend 프로젝트의 모든 README를 한눈에 파악하고 빠르게 탐색
> **총 README 수**: 11개

---

## 빠른 탐색

| 카테고리 | 핵심 파일 |
|----------|-----------|
| **프로젝트 전체** | [README_PROJECT.md](#project) - 프론트엔드 가이드 |
| **법규 검색 UI** | [src/law/README.md](#law) - Django 백엔드 연동 |
| **Google 통합** | [src/google/README.md](#google) - Maps/Live API |
| **테스트** | [test/README.md](#test) - 테스트 가이드 |

---

## 1. 프로젝트 루트

### README_PROJECT.md {#project}
- **경로**: [`README_PROJECT.md`](./README_PROJECT.md)
- **중요도**: ⭐⭐⭐ 핵심
- **내용**:
  - 프로젝트 구조
  - 실행 방법 (개발/프로덕션)
  - 백엔드 연동
  - 기술 스택

### README.md
- **경로**: [`README.md`](./README.md)
- **내용**: 원본 프로젝트 README

### README_CN.md
- **경로**: [`README_CN.md`](./README_CN.md)
- **내용**: 중국어 README

---

## 2. 핵심 모듈

### src/law/ - 법규 검색 UI {#law}
- **경로**: [`src/law/README.md`](./src/law/README.md)
- **중요도**: ⭐⭐⭐ 핵심
- **내용**:
  - Django 백엔드 연동 (SSE 스트리밍 / REST)
  - `LawChat.tsx` 메인 컴포넌트
  - `useLawSearchStream` 훅 (실시간 진행상황)
  - `useLawChat` 훅 (REST API)
  - `LawAPIContext` 전역 상태
  - UI 컴포넌트 (QueryInput, ResultDisplay, etc.)

### src/google/ - Google 통합 {#google}
- **경로**: [`src/google/README.md`](./src/google/README.md)
- **내용**:
  - Google Maps 3D
  - Gemini Live API
  - 스트리밍 콘솔

### src/components/ChatBox/ {#chatbox}
- **경로**: [`src/components/ChatBox/README.md`](./src/components/ChatBox/README.md)
- **내용**:
  - 채팅 UI 컴포넌트
  - 메시지 렌더링

---

## 3. 테스트 {#test}

### test/
- **경로**: [`test/README.md`](./test/README.md)
- **내용**:
  - Vitest 설정
  - 단위 테스트
  - E2E 테스트
  - 모킹

---

## 4. 서버 (Python)

### server/
- **경로**: [`server/README_EN.md`](./server/README_EN.md)
- **내용**: Python 로컬 서버 (영문)

- **경로**: [`server/README_CN.md`](./server/README_CN.md)
- **내용**: Python 로컬 서버 (중문)

---

## 5. 패키지

### package/@stackframe/react/
- **경로**: [`package/@stackframe/react/README.md`](./package/@stackframe/react/README.md)
- **내용**: Stackframe React 패키지

---

## 6. 내장 백엔드

### backend/
- **경로**: [`backend/README.md`](./backend/README.md)
- **내용**: 프론트엔드 내장 Python 백엔드

---

## 파일 트리 (README 위치)

```
frontend/
├── README.md                 원본 README
├── README_CN.md              중국어 README
├── README_PROJECT.md         ⭐ 프로젝트 가이드
├── README_INDEX.md           (현재 파일) 목차
│
├── src/
│   ├── law/
│   │   └── README.md         ⭐⭐⭐ 법규 검색 UI
│   ├── google/
│   │   └── README.md         Google 통합
│   └── components/
│       └── ChatBox/
│           └── README.md     채팅 컴포넌트
│
├── test/
│   └── README.md             테스트 가이드
│
├── server/
│   ├── README_EN.md          서버 (영문)
│   └── README_CN.md          서버 (중문)
│
├── backend/
│   └── README.md             내장 백엔드
│
└── package/
    └── @stackframe/
        └── react/
            └── README.md     Stackframe 패키지
```

---

## 읽기 순서 추천

### 프로젝트 처음 접할 때
1. **[README_PROJECT.md](./README_PROJECT.md)** - 전체 구조 파악
2. **[src/law/README.md](./src/law/README.md)** - 핵심 법규 검색 UI

### 특정 기능 파악할 때
| 목적 | 읽을 파일 |
|------|-----------|
| 법규 검색 UI | `src/law/README.md` |
| Google Maps/Live API | `src/google/README.md` |
| 테스트 작성 | `test/README.md` |
| 채팅 UI 커스터마이징 | `src/components/ChatBox/README.md` |

---

## 관련 문서

| 위치 | 문서 |
|------|------|
| 프로젝트 루트 | [../README.md](../README.md) - 전체 프로젝트 개요 |
| Backend | [../backend/README_INDEX.md](../backend/README_INDEX.md) - 백엔드 목차 |
| Backend | [../backend/AI_INDEX.md](../backend/AI_INDEX.md) - 시스템 완전 가이드 |

---

**마지막 업데이트**: 2025-11-14
