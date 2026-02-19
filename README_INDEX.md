# README INDEX - 전체 프로젝트 목차

> **프로젝트**: 법규 Graph Node Multi-Agent 검색 시스템
> **목적**: 전체 프로젝트의 모든 문서를 책처럼 목차로 정리
> **마지막 업데이트**: 2025-11-14

---

## 프로젝트 구조

```
D:\Data\11_Backend\01_ARR\
├── README.md             프로젝트 개요
├── README_INDEX.md       (현재 파일) 전체 목차
│
├── backend/              ⭐ Django 법규 검색 백엔드
│   ├── README_INDEX.md   백엔드 목차 (26개 README)
│   ├── AI_INDEX.md       시스템 완전 가이드
│   └── TASK.md           작업 목록
│
├── frontend/             ⭐ Electron 데스크톱 앱
│   ├── README_INDEX.md   프론트엔드 목차 (11개 README)
│   └── README_PROJECT.md 프로젝트 가이드
│
└── agent/                AI 에이전트 예제 (학습용)
```

---

## 1장. 프로젝트 개요

| 문서 | 설명 |
|------|------|
| [README.md](./README.md) | 프로젝트 전체 개요, 아키텍처, 빠른 시작 |

---

## 2장. Backend - Django 법규 검색

### 목차
- **[backend/README_INDEX.md](./backend/README_INDEX.md)** - 백엔드 전체 목차 (26개 README)

### 핵심 문서

| 문서 | 중요도 | 설명 |
|------|--------|------|
| [backend/AI_INDEX.md](./backend/AI_INDEX.md) | ⭐⭐⭐ | 시스템 완전 가이드 (AI 인덱싱용) |
| [backend/TASK.md](./backend/TASK.md) | ⭐⭐ | 작업 목록 및 진행상황 |

### 핵심 앱 문서

| 문서 | 중요도 | 설명 |
|------|--------|------|
| [backend/agents/law/README.md](./backend/agents/law/README.md) | ⭐⭐⭐ | Multi-Agent 시스템 (AgentManager, DomainAgent) |
| [backend/graph_db/README.md](./backend/graph_db/README.md) | ⭐⭐⭐ | Neo4j 스키마 및 SemanticRNE 알고리즘 |
| [backend/law/README.md](./backend/law/README.md) | ⭐⭐⭐ | 법률 검색 API 및 데이터 파이프라인 |

### 지원 앱 문서

| 문서 | 설명 |
|------|------|
| [backend/chat/README.md](./backend/chat/README.md) | WebSocket 채팅 |
| [backend/gemini/README.md](./backend/gemini/README.md) | Gemini Live API |
| [backend/core/README.md](./backend/core/README.md) | 공통 모델, 유틸리티 |
| [backend/conversations/README.md](./backend/conversations/README.md) | 대화 히스토리 |
| [backend/config/README.md](./backend/config/README.md) | Django 설정 |

---

## 3장. Frontend - Electron 앱

### 목차
- **[frontend/README_INDEX.md](./frontend/README_INDEX.md)** - 프론트엔드 전체 목차 (11개 README)

### 핵심 문서

| 문서 | 중요도 | 설명 |
|------|--------|------|
| [frontend/README_PROJECT.md](./frontend/README_PROJECT.md) | ⭐⭐⭐ | 프론트엔드 프로젝트 가이드 |
| [frontend/src/law/README.md](./frontend/src/law/README.md) | ⭐⭐⭐ | 법규 검색 UI (Django 백엔드 연동) |

### 기타 문서

| 문서 | 설명 |
|------|------|
| [frontend/src/google/README.md](./frontend/src/google/README.md) | Google Maps/Live API |
| [frontend/test/README.md](./frontend/test/README.md) | 테스트 가이드 |
| [frontend/server/README_EN.md](./frontend/server/README_EN.md) | Python 로컬 서버 |

---

## 4장. 통합 문서

### A2A (Agent-to-Agent) 통합

| 문서 | 위치 | 설명 |
|------|------|------|
| [A2A_FILE_CHANGES_SUMMARY.md](./frontend/A2A_FILE_CHANGES_SUMMARY.md) | frontend | A2A 변경 요약 |
| [A2A_UI_COMPARISON.md](./frontend/A2A_UI_COMPARISON.md) | frontend | A2A UI 비교 |
| [PARALLEL_A2A_FRONTEND_IMPLEMENTATION.md](./frontend/PARALLEL_A2A_FRONTEND_IMPLEMENTATION.md) | frontend | 병렬 A2A 구현 |

### 스트리밍 통합

| 문서 | 위치 | 설명 |
|------|------|------|
| [STREAMING_INTEGRATION_GUIDE.md](./frontend/STREAMING_INTEGRATION_GUIDE.md) | frontend | 스트리밍 통합 가이드 |
| [STREAMING_SUMMARY.md](./frontend/STREAMING_SUMMARY.md) | frontend | 스트리밍 요약 |
| [SSE_INTEGRATION_COMPLETE.md](./frontend/SSE_INTEGRATION_COMPLETE.md) | frontend | SSE 통합 완료 |

---

## 읽기 순서 추천

### 프로젝트 처음 접할 때

```
1. README.md (루트)
   ↓ 전체 구조 파악
2. backend/AI_INDEX.md
   ↓ 핵심 로직 이해
3. backend/agents/law/README.md
   ↓ Multi-Agent 상세
4. frontend/src/law/README.md
   ↓ UI 연동 방식
```

### 특정 기능 파악할 때

| 목적 | 읽을 순서 |
|------|-----------|
| **검색 로직** | `backend/AI_INDEX.md` → `backend/agents/law/README.md` |
| **Neo4j 스키마** | `backend/graph_db/README.md` |
| **데이터 파이프라인** | `backend/law/README.md` → `backend/law/STEP/` |
| **프론트엔드 UI** | `frontend/README_PROJECT.md` → `frontend/src/law/README.md` |
| **SSE 스트리밍** | `frontend/src/law/README.md` (useLawSearchStream) |

---

## 문서 통계

| 위치 | README 개수 |
|------|-------------|
| Backend | 26개 |
| Frontend | 11개 |
| **총합** | **37개** |

---

## 빠른 링크

### 필수 문서 (먼저 읽기)

1. [README.md](./README.md) - 프로젝트 개요
2. [backend/AI_INDEX.md](./backend/AI_INDEX.md) - 시스템 완전 가이드
3. [backend/agents/law/README.md](./backend/agents/law/README.md) - Multi-Agent 핵심
4. [frontend/src/law/README.md](./frontend/src/law/README.md) - UI 연동

### 목차 파일

| 위치 | 목차 파일 |
|------|-----------|
| 루트 | [README_INDEX.md](./README_INDEX.md) (현재 파일) |
| Backend | [backend/README_INDEX.md](./backend/README_INDEX.md) |
| Frontend | [frontend/README_INDEX.md](./frontend/README_INDEX.md) |

---

**이 문서가 전체 프로젝트의 "책 목차" 역할을 합니다.**
