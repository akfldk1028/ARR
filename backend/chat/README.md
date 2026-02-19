# chat/ - 텍스트 채팅 시스템

## 개요
A2A 프로토콜 통합 텍스트 채팅 시스템. WebSocket 기반 실시간 채팅, Neo4j 대화 저장, Worker Agent 자동 라우팅.

## 핵심 기능
- WebSocket 기반 실시간 텍스트 채팅
- A2A 프로토콜 자동 라우팅
- Neo4j 대화 기록 저장
- Host Agent를 통한 전문가 위임

---

## 파일 구조 및 역할

### 루트 파일
| 파일 | 역할 | 핵심 클래스/함수 |
|------|------|-----------------|
| `consumers.py` | 채팅 WebSocket Consumer | `ChatConsumer` - A2A 통합, Neo4j 저장 |
| `models.py` | 채팅 모델 (현재 비어있음) | gemini.models 사용 |
| `views.py` | 페이지 렌더링 | 채팅 UI 뷰 |
| `urls.py` | URL 라우팅 | `/chat/` 하위 경로 |
| `routing.py` | WebSocket 라우팅 | `websocket_urlpatterns` |

### templates/chat/ - UI 템플릿
| 파일 | 역할 |
|------|------|
| `index.html` | 메인 채팅 UI |
| `law_chat.html` | 법률 채팅 전용 UI |

### docs/ - 문서
| 파일 | 역할 |
|------|------|
| `A2A_CHAT_ARCHITECTURE.md` | A2A 채팅 아키텍처 |
| `ENTERPRISE_ARCHITECTURE.md` | 엔터프라이즈 아키텍처 |
| `A2A_COOKBOOK_COMPARISON.md` | A2A 쿡북 비교 |
| `CODE_REVIEW_AND_IMPROVEMENTS.md` | 코드 리뷰 |

---

## ChatConsumer 기능

### 메시지 타입
| 타입 | 설명 |
|------|------|
| `chat_message` | 일반 채팅 메시지 |
| `switch_agent` | 에이전트 전환 |
| `list_agents` | 에이전트 목록 조회 |
| `session_info` | 세션 정보 조회 |
| `history` | 대화 기록 조회 |

### 통합 기능
- `WorkerAgentManager`: Worker Agent 관리
- `ConversationTracker`: Neo4j 대화 추적
- `A2AHandler`: A2A 프로토콜 처리

---

## 의존성
- `channels`: Django Channels
- `agents.worker_agents`: Worker Agent 시스템
- `graph_db.services`: Neo4j 서비스
- `graph_db.tracking`: 대화/작업/출처 추적

## WebSocket 엔드포인트
| 경로 | Consumer | 설명 |
|------|----------|------|
| `/ws/chat/` | `ChatConsumer` | 텍스트 채팅 |

## 페이지 URL
| 경로 | 설명 |
|------|------|
| `/chat/` | 메인 채팅 |
| `/chat/law/` | 법률 채팅 |

## 사용 예시
```javascript
// 클라이언트 WebSocket 연결
const ws = new WebSocket('ws://localhost:8000/ws/chat/');
ws.send(JSON.stringify({
    type: 'chat_message',
    content: '국토계획법 17조 알려줘'
}));
```
