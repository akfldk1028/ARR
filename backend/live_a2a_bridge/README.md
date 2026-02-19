# live_a2a_bridge/ - A2A 실시간 브릿지 서비스

## 개요
A2A 프로토콜과 Gemini Live API 간 브릿지. 실시간 음성 TTS (Text-to-Speech) 서비스 통합.

## 핵심 기능
- A2A ↔ Live API 브릿지
- Gemini TTS 서비스
- 최적화된 브릿지 (저지연)
- Context7 Live 클라이언트

---

## 파일 구조 및 역할

### services/ - 서비스 레이어
| 파일 | 역할 | 핵심 클래스 |
|------|------|------------|
| `live_api_tts_bridge.py` | Live API TTS 브릿지 | `LiveAPITTSBridge` - A2A ↔ TTS 연결 |
| `gemini_tts_service.py` | Gemini TTS 서비스 | `GeminiTTSService` - 텍스트→음성 |
| `optimized_bridge.py` | 최적화 브릿지 | `OptimizedBridge` - 저지연 처리 |
| `context7_live_client.py` | Context7 클라이언트 | `Context7LiveClient` - 외부 서비스 연결 |

### 루트 파일
| 파일 | 역할 |
|------|------|
| `models.py` | 모델 (현재 비어있음) |
| `views.py` | API 뷰 |
| `apps.py` | 앱 설정 |

---

## 아키텍처

```
A2A Agent Response (텍스트)
        ↓
  LiveAPITTSBridge
        ↓
  GeminiTTSService
        ↓
    음성 출력 (오디오)
```

## 사용 시나리오

1. **음성 채팅**: 사용자 음성 → STT → A2A Agent → TTS → 음성 응답
2. **실시간 스트리밍**: 토큰 단위 TTS 변환

---

## 의존성
- `gemini.services`: Gemini API 클라이언트
- `agents.worker_agents`: Worker Agent 시스템

## 환경 변수
```env
GEMINI_API_KEY=your_api_key
TTS_MODEL=gemini-2.0-flash-exp
```
