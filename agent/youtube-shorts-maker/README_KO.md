# YouTube Shorts Maker (Google ADK)

## 🎯 무엇을 하는 프로젝트인가요?

YouTube Shorts 동영상을 자동으로 생성하는 AI 시스템입니다. 스크립트 작성부터 이미지/음성 생성까지 자동화합니다.

## 🤖 서브 에이전트 구조

1. **Content Planner**: 콘텐츠 아이디어 및 스크립트
2. **Asset Generator**:
   - Image Generator: AI 이미지 생성
   - Voice Generator: AI 음성 생성
3. **Video Assembler**: 최종 동영상 조립

## 📋 기술 스택

- **Google ADK**: 에이전트 프레임워크
- **OpenAI DALL-E**: 이미지 생성
- **OpenAI TTS**: 음성 생성
- **Video Assembly**: 동영상 편집

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일:
```env
GOOGLE_API_KEY=your_google_key_here
OPENAI_API_KEY=your_openai_key_here
```

### 2. 실행
```bash
uv run python -m youtube_shorts_maker.agent
```

## 💡 워크플로우

1. 주제 입력
2. 스크립트 자동 생성
3. 이미지 생성 (DALL-E)
4. 음성 생성 (TTS)
5. 동영상 조립
6. YouTube Shorts 준비 완료!

## 🔑 필요한 API 키

- ⚠️ Google Gemini API Key (필수)
- ✅ OpenAI API Key (이미지/음성 생성용)

## 📦 필요한 패키지

이미 설치됨! (Python 3.13)
