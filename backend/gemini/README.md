# gemini/ - Gemini AI 통합 및 WebSocket 서비스

## 개요
Google Gemini API 통합, WebSocket 기반 실시간 채팅, 음성 대화(Live API) 지원. 메인 채팅 세션 관리.

## 핵심 기능
- Gemini Live API 통합 (실시간 멀티모달)
- WebSocket 채팅 Consumer
- 음성 인식 (VAD + STT)
- 텍스트/이미지/오디오 처리
- A2A 핸들러 통합

---

## 파일 구조 및 역할

### 루트 파일
| 파일 | 역할 | 핵심 클래스/함수 |
|------|------|-----------------|
| `models.py` | 채팅 모델 | `ChatSession`, `ChatMessage` |
| `views.py` | 페이지 렌더링 | 채팅 UI 뷰 |
| `urls.py` | URL 라우팅 | `/gemini/` 하위 경로 |
| `routing.py` | WebSocket 라우팅 | `websocket_urlpatterns` |

### consumers/ - WebSocket Consumer
| 파일 | 역할 | 핵심 클래스 |
|------|------|------------|
| `simple_consumer.py` | 메인 채팅 Consumer | `SimpleConsumer` |
| `gemini_consumer.py` | Gemini 전용 Consumer | `GeminiConsumer` |
| `base.py` | Consumer 베이스 | `BaseConsumer` |
| `handlers/a2a_handler.py` | A2A 프로토콜 핸들러 | `A2AHandler` - 에이전트 라우팅 |
| `handlers/live_api_handler.py` | Live API 핸들러 | 실시간 스트리밍 |
| `handlers/message_handler.py` | 메시지 핸들러 | 텍스트/이미지 처리 |
| `handlers/agent_handler.py` | 에이전트 핸들러 | Worker Agent 위임 |

### services/ - 서비스 레이어
| 파일 | 역할 | 핵심 클래스 |
|------|------|------------|
| `gemini_client.py` | Gemini API 클라이언트 | `GeminiClient` |
| `live_api_client.py` | Live API 클라이언트 | `LiveAPIClient` |
| `websocket_live_client.py` | WebSocket Live 클라이언트 | 실시간 연결 |
| `service_manager.py` | 서비스 매니저 | 싱글톤 관리 |
| `speech_to_text_client.py` | STT 클라이언트 | 음성→텍스트 |
| `vad_stt_service.py` | VAD + STT 서비스 | 음성 활동 감지 |
| `vad/silero_vad.py` | Silero VAD | 고성능 VAD |
| `vad/webrtc_vad.py` | WebRTC VAD | 브라우저 호환 VAD |

### config/ - 설정
| 파일 | 역할 |
|------|------|
| `settings.py` | Gemini 설정 | 모델명, API 키, 타임아웃 |

### templates/gemini/ - UI 템플릿
| 파일 | 역할 |
|------|------|
| `index.html` | 메인 채팅 UI |
| `live_voice.html` | 음성 대화 UI |
| `continuous_voice.html` | 연속 음성 UI |
| `voice_conversation.html` | 음성 대화 전체 UI |

### utils/ - 유틸리티
| 파일 | 역할 |
|------|------|
| `logging_config.py` | 로깅 설정 |

---

## 의존성
- `channels`: Django Channels (WebSocket)
- `google.generativeai`: Gemini API
- `silero-vad`: 음성 활동 감지

## WebSocket 엔드포인트
| 경로 | Consumer | 설명 |
|------|----------|------|
| `/ws/gemini/` | `SimpleConsumer` | 텍스트 채팅 |
| `/ws/gemini/live/` | `GeminiConsumer` | 음성 대화 |

## 페이지 URL
| 경로 | 설명 |
|------|------|
| `/gemini/` | 메인 채팅 |
| `/gemini/live-voice/` | 음성 대화 |

## 사용 예시
```python
from gemini.services.gemini_client import GeminiClient

client = GeminiClient()
response = await client.generate_content("안녕하세요")
```
