# Context7 기반 Gemini Live API 오디오 최적화

## 프로젝트 개요
Django backend에서 Gemini Live API와의 실시간 음성 대화를 위한 오디오 스트리밍 최적화 작업

## 문제점
- 오디오 끊김 현상 발생 (뚝뚝 끊기는 문제)
- WebSocket 전송 빈도 과부하
- PCM 변환 비효율성
- AudioWorklet 구현 오류

## 해결 방법: Context7 Cookbook 패턴 적용

### 1. 핵심 파일 구조
```
backend/gemini/
├── templates/gemini/continuous_voice.html  # 메인 구현 파일
├── services/websocket_live_client.py       # WebSocket Live API 클라이언트
├── consumers/simple_consumer.py            # WebSocket 소비자
└── routing.py                              # WebSocket 라우팅
```

### 2. Context7 AudioWorklet 구현 (`continuous_voice.html`)

#### AudioWorklet PortProcessor 클래스
```javascript
class PortProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._queue = [];        // 오디오 출력 큐
        this._out = [];          // 오디오 입력 버퍼
        this._out_len = 0;       // 버퍼 길이
    }

    // Context7 패턴: 50ms 배치 전송
    process(inputs, outputs, parameters) {
        // 입력 오디오 인코딩
        let data = this.encodeAudio(inputs[0]);
        this._out.push(data);
        this._out_len += data.byteLength;

        // 핵심: sampleRate/20 = 50ms 배치
        if (this._out_len > (2 * sampleRate / 20)) {
            // 배치 전송
            this.port.postMessage({
                'audio_in': concat.buffer
            });
        }

        // 출력 오디오 seamless 재생
        this.dequeueIntoBuffer(outputs[0][0]);
    }
}
```

#### 핵심 최적화 포인트
1. **50ms 배치 전송**: `sampleRate / 20` 기반
2. **16kHz 샘플링**: Context7 표준 설정
3. **Little Endian PCM**: `view.setInt16(2*i, channel[i] * 32767, true)`
4. **seamless 재생**: `dequeueIntoBuffer()` 메서드

### 3. 오디오 설정 최적화

#### 입력 설정
```javascript
// getUserMedia 설정
const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
        sampleRate: 16000,      // Context7 표준
        echoCancellation: true,
        channelCount: 1
    }
});

// AudioContext 설정
audioContext = new AudioContext({sampleRate: 16000});
```

#### 출력 처리
```javascript
// Context7 패턴: 직접 worklet으로 처리
case 'audio_chunk':
    const decoded = Uint8Array.from(
        atob(data.audio), c => c.charCodeAt(0)
    ).buffer;
    workletProcessor.port.postMessage({'enqueue': decoded});
    break;
```

### 4. 한국어 지원 (`websocket_live_client.py`)

#### 시스템 명령 설정
```python
'system_instruction': {
    'parts': [{
        'text': """당신은 친근하고 도움이 되는 한국어 AI 어시스턴트입니다.
        다음 규칙을 따라주세요:
        - 항상 한국어로 대답해주세요
        - 자연스럽고 대화하듯이 말해주세요
        - 질문에 명확하고 유용한 답변을 제공해주세요
        - 친근하고 정중한 말투를 사용해주세요
        - 사용자가 영어로 질문해도 한국어로 답변해주세요"""
    }]
}
```

#### 보이스 설정
```python
'speech_config': {
    'voice_config': {
        'prebuilt_voice_config': {
            'voice_name': 'Puck'  # 한국어 지원 최적화
        }
    }
}
```

### 5. WebSocket 연결 (`simple_consumer.py`)

#### 메시지 핸들러
```python
async def handle_voice_audio_chunk(self, message_data):
    """Context7 패턴으로 오디오 청크 처리"""
    audio_base64 = message_data.get('audio')
    if audio_base64:
        audio_bytes = base64.b64decode(audio_base64)
        await self.continuous_session.process_audio(audio_bytes)
```

### 6. 서버 실행
```bash
# ASGI 서버 사용 (WebSocket 지원)
daphne -b 0.0.0.0 -p 8002 backend.asgi:application
```

## 성능 개선 결과

### Before (문제점)
- 매 2.9ms마다 개별 전송 → WebSocket 과부하
- 비효율적 PCM 변환 → CPU 부하
- AudioBufferSource 간 틈 → 오디오 끊김

### After (Context7 적용)
- ✅ 50ms 배치 전송 → 안정적 전송
- ✅ 효율적 DataView PCM → 성능 향상
- ✅ seamless 재생 → 끊김 해결
- ✅ 한국어 완벽 지원

## 기술 스택
- **Frontend**: AudioWorklet API, WebSocket
- **Backend**: Django Channels, Gemini Live API
- **Protocol**: Context7 Cookbook 패턴
- **Audio**: 16kHz PCM, Little Endian

## 참조 문서
- [Context7 Gemini Cookbook](https://github.com/google-gemini/cookbook)
- Context7 AudioWorklet 패턴
- Gemini Live API WebSocket 스트리밍

## 테스트 URL
```
http://localhost:8002/gemini/continuous-voice/
```

이 구현은 Context7 Cookbook의 AudioWorklet 패턴을 정확히 따라 실시간 음성 대화의 오디오 끊김 문제를 해결합니다.