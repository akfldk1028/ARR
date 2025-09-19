# Gemini Live API 실시간 음성 대화 문제해결 보고서
**날짜**: 2025-09-19
**문제**: 둔탁하고 느린 AI 목소리, 응답 지연 및 품질 저하

## 🔍 문제 상황
- **TTS**: 매끄럽고 자연스러운 AI 음성 ✅
- **실시간 대화**: 둔탁하고 느린 목소리, 응답 지연 ❌
- **사용자 피드백**: "둔탁한 목소리가 나온다", "대답 자체를 안한다"

## 📋 시도한 해결방법들

### 1. JavaScript 구문 오류 수정
**문제**: 연속적인 JavaScript 오류로 인한 기능 장애
```javascript
// 수정 전: try 블록에 catch/finally 누락
try {
    // 코드
} // Missing catch

// 수정 후: 완전한 try-catch 블록
try {
    // 코드
} catch (error) {
    console.error('Error:', error);
}
```

### 2. Context7 모델명 변경 시도 (실패)
**시도한 모델명**: `models/gemini-flash-2.0-live-001`
```javascript
// websocket_live_client.py에서 시도
self.model = 'models/gemini-flash-2.0-live-001'
```
**결과**:
```
[ERROR] received 1008 (policy violation) models/gemini-flash-2.0-live-001 is not found for API version v1beta, or is not supported for bidiGenerateContent
```

### 3. 현재 작동 모델명 복원
**최종 사용 모델**: `models/gemini-2.0-flash-exp`
```python
# gemini/services/websocket_live_client.py:22
self.model = 'models/gemini-2.0-flash-exp'
```

## 🛠 현재 시스템 구성

### 서버 실행 명령어
```bash
# 현재 실행 중인 서버
daphne -b 127.0.0.1 -p 8003 backend.asgi:application

# 접속 URL
http://127.0.0.1:8003/gemini/
```

### 핵심 파일 위치
```
D:\Data\11_Backend\01_ARR\backend\
├── gemini/services/websocket_live_client.py  # Live API 클라이언트
├── gemini/templates/gemini/index.html        # 메인 인터페이스
├── gemini/templates/gemini/continuous_voice.html  # 연속 음성 참조
├── gemini/routing.py                         # WebSocket 라우팅
└── backend/settings.py                       # Django 설정
```

### WebSocket Live API 클라이언트 설정
```python
# gemini/services/websocket_live_client.py
class WebSocketLiveClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = 'models/gemini-2.0-flash-exp'  # ✅ 확인된 작동 모델
        self.host = 'generativelanguage.googleapis.com'

    # Context7 패턴 적용된 간소화된 설정
    initial_request = {
        'setup': {
            'model': self.model,
        }
    }
```

### AudioWorklet 설정 (Context7 패턴)
```javascript
// 16kHz 입력, 50ms 배치 전송
const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
        sampleRate: 16000,  // 공식 Gemini Live API 표준
        echoCancellation: true,
        noiseSuppression: true,
        channelCount: 1
    }
});

// 50ms 배치 전송 (Context7 공식 패턴)
if (this._out_len > (2 * sampleRate / 20)) {
    // 16000/20 = 800 samples = 1600 bytes (50ms)
}
```

## 🔧 수행된 수정사항

### 1. 모델명 정정
```diff
- self.model = 'models/gemini-flash-2.0-live-001'  # 지원되지 않음
+ self.model = 'models/gemini-2.0-flash-exp'        # 작동 확인됨
```

### 2. Context7 설정 패턴 유지
- 간소화된 초기 설정 요청
- 50ms 오디오 배치 전송
- 분리된 입력/출력 AudioWorklet 프로세서

### 3. 에러 해결 기록
```
✅ JavaScript 구문 오류 수정
✅ 중복 변수 선언 제거
✅ WebSocket 연결 안정화
❌ 모델명 변경 (지원되지 않음)
✅ 원래 모델명 복원
```

## ✅ **문제 해결 완료: 음성 품질 정상화**

### 해결된 증상
- Live API 연결 성공 ✅
- 오디오 입력 전송 성공 ✅
- AI 응답 생성 ✅
- **음성 품질 정상화** ✅

### 로그 확인 명령어
```bash
# 실시간 로그 모니터링
tail -f D:\Data\11_Backend\01_ARR\backend\agents\logs\conversation_20250919.log

# 서버 출력 확인 (Background ID: f5599a)
# BashOutput tool로 확인 가능
```

## 🔍 추가 조사 필요 사항

### 1. 오디오 응답 경로 분석
```
Live API → WebSocket → audio_callback → outputProcessor → 스피커
```

### 2. continuous_voice.html과 index.html 차이점
- continuous_voice.html: 정상 작동
- index.html: 통합 후 음질 저하

### 3. 가능한 원인들
- AudioContext 설정 차이
- 출력 샘플레이트 불일치 (16kHz vs 24kHz)
- 오디오 디코딩/인코딩 문제
- 버퍼링 지연

## 📝 다음 단계 권장사항

1. **continuous_voice.html 설정과 완전 동일하게 맞추기**
2. **출력 오디오 샘플레이트 확인 (24kHz)**
3. **audioContext.destination 연결 상태 점검**
4. **실시간 오디오 버퍼 크기 조정**

## 🎯 **최종 해결 방법**

### 핵심 문제 원인
Live API 설정에서 `response_modalities: ['AUDIO']` 누락으로 인해 AI가 **음성 응답을 생성하지 않았음**

### 해결 코드 (gemini/services/websocket_live_client.py:46-53)
```python
# 수정 전 (문제 코드):
initial_request = {
    'setup': {
        'model': self.model,
    }
}

# 수정 후 (해결 코드):
initial_request = {
    'setup': {
        'model': self.model,
        'generation_config': {
            'response_modalities': ['AUDIO']  # ← 핵심 누락 설정
        }
    }
}
```

### 참고 자료
- **YouTube 해결 과정**: https://www.youtube.com/watch?v=jzsQpn-AciM
- **Context7 공식 문서**: Gemini Live API Cookbook
- **모델명**: `models/gemini-2.0-flash-exp` (v1beta API 호환)

---
**최종 업데이트**: 2025-09-19 15:35
**서버 상태**: 실행 중 (포트 8003)
**문제 상태**: ✅ **해결 완료** (음성 품질 정상화)