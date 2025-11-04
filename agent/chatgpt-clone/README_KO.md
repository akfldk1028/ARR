# ChatGPT Clone

## 🎯 무엇을 하는 프로젝트인가요?

ChatGPT와 유사한 대화형 AI 인터페이스입니다. 웹 검색, 파일 검색, 이미지 생성, 코드 실행 등 다양한 기능을 가진 AI 어시스턴트입니다.

## 🤖 에이전트 설명

- **이름**: ChatGPT Clone
- **기능**:
  - 💬 대화
  - 🔍 웹 검색
  - 📁 파일 검색
  - 🎨 이미지 생성
  - 💻 코드 실행 (Code Interpreter)
  - 🔧 MCP 도구 연동
- **프레임워크**: OpenAI Agents (Swarm)
- **UI**: Streamlit
- **LLM 모델**: OpenAI GPT 모델

## 📋 기술 스택

- **OpenAI Agents**: 에이전트 오케스트레이션
- **Streamlit**: 웹 UI
- **MCP (Model Context Protocol)**: 외부 도구 연동
- **Vector Store**: 파일 검색

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일에 OpenAI API 키를 입력하세요:
```env
OPENAI_API_KEY=your_api_key_here
```

### 2. Streamlit 앱 실행
```bash
uv run streamlit run main.py
```

### 3. 브라우저에서 접속
자동으로 브라우저가 열립니다 (보통 http://localhost:8501)

## 💡 사용 예시

- "오늘 날씨 알려줘" → 웹 검색
- "이미지 그려줘: 고양이" → 이미지 생성
- "Python 코드로 계산해줘" → 코드 실행
- 파일 업로드 후 질문 → 파일 검색

## 📦 필요한 패키지

이미 설치됨! (uv sync 완료)

## 🔑 필요한 API 키

- ✅ OpenAI API Key (필수)

## ⚡ 주요 기능

1. **Web Search Tool**: 실시간 웹 검색
2. **File Search Tool**: 업로드한 파일 검색
3. **Image Generation**: DALL-E 이미지 생성
4. **Code Interpreter**: Python 코드 실행
5. **MCP Tools**: Yahoo Finance, Time 등 외부 도구
