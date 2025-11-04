# Email Refiner Agent (Google ADK)

## 🎯 무엇을 하는 프로젝트인가요?

이메일 작성을 도와주는 AI 시스템입니다. 이메일을 분석하고 더 나은 버전으로 개선합니다.

## 🤖 에이전트 기능

- 이메일 톤 조정 (공식적/비공식적)
- 문법 및 맞춤법 교정
- 명확성 및 간결성 개선
- 다국어 번역 지원

## 📋 기술 스택

- **Google ADK**: Agent Development Kit
- **Google Gemini**: 언어 모델
- **LiteLLM**: LLM 통합

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일:
```env
GOOGLE_API_KEY=your_google_key_here
```

### 2. 로컬 실행
```bash
uv run python -m travel_advisor_agent.agent
```

### 3. 배포 (선택사항)
```bash
uv run python deploy.py
```

## 💡 기능

- ✉️ 이메일 개선 제안
- 🎨 톤 조정
- ✅ 문법 교정
- 🌍 다국어 지원

## 🔑 필요한 API 키

- ⚠️ Google Gemini API Key (필수)

## 📦 필요한 패키지

이미 설치됨! (Python 3.13)
