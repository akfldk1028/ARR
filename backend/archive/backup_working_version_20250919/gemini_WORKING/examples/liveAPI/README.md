# 🚀 Gemini Live API 멀티모달 서버

Django 프로젝트로 이전하기 전 정리된 Gemini Live API 구현체들입니다.

## 📁 파일 구조

```
examples/liveAPI/
├── README.md                           # 이 파일
├── live_api_web_server.py              # WebSocket 서버 (추천)
├── gemini_live_multimodal_server.py    # 하이브리드 서버
└── gemini_live_webrtc_port8888.py      # WebRTC 서버
```

## ⚡ 빠른 실행

### 1️⃣ WebSocket 서버 (가장 빠름)
```bash
cd examples/liveAPI
python live_api_web_server.py --port 8888
```
→ **추천**: 텍스트+이미지 멀티모달 테스트

### 2️⃣ WebRTC 서버 (실시간 비디오)
```bash
cd examples/liveAPI
python gemini_live_webrtc_port8888.py --port 8888
```
→ 실시간 비디오 스트리밍 필요시

## 🎯 서버별 특징

| 서버 | 속도 | 용도 | 기능 |
|------|------|------|------|
| **live_api_web_server.py** | 🟢 가장 빠름 | 텍스트+이미지 | WebSocket 직접 연결 |
| **gemini_live_webrtc_port8888.py** | 🟡 보통 | 실시간 비디오 | WebRTC + Pipecat |
| **gemini_live_multimodal_server.py** | 🟡 보통 | 하이브리드 | WebSocket + 이미지 API |

## 📋 환경 설정

### .env 파일 설정
```bash
GOOGLE_API_KEY=your_api_key_here
```

### 필수 패키지 설치

**Option 1: 최소 필수 패키지 (추천)**
```bash
pip install -r requirements-minimal.txt
```

**Option 2: 전체 환경 복사**
```bash
pip install -r requirements.txt
```

**Option 3: 수동 설치**
```bash
pip install google-generativeai websockets fastapi uvicorn pipecat-ai-small-webrtc-prebuilt pillow python-dotenv
```

## 🌐 접속 URL

### WebSocket 서버
- **메인**: http://localhost:8888
- **WebSocket**: ws://localhost:8888/ws

### WebRTC 서버
- **메인**: http://localhost:8888 (텍스트+이미지)
- **WebRTC**: http://localhost:8888/webrtc (실시간 비디오)

## 🔧 Django 이전 시 참고사항

### 1. URL 패턴
```python
# Django urls.py 예시
urlpatterns = [
    path('ws/', consumers.GeminiLiveConsumer.as_asgi()),
    path('api/multimodal/', views.multimodal_test, name='multimodal_test'),
]
```

### 2. WebSocket Consumer
```python
# Django channels consumer 예시
from channels.generic.websocket import AsyncWebsocketConsumer
```

### 3. 정적 파일
- HTML/CSS/JS를 Django templates로 이전
- 이미지 업로드를 Django forms로 처리

### 4. 설정 분리
- API 키를 Django settings로 이전
- CORS 설정 추가

## 📚 관련 문서

- [전체 가이드](../docs/gemini-live-multimodal-guide.md)
- [이전 테스트 기록](../docs/live-api-websocket-test-guide.md)

---

**🎉 Django 프로젝트에서 이 구현체들을 참고하여 멋진 멀티모달 서비스를 만들어보세요!**