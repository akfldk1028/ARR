# Workflow Testing (LangGraph)

## 🎯 무엇을 하는 프로젝트인가요?

LangGraph 워크플로우를 테스트하는 방법을 학습하는 프로젝트입니다. 단위 테스트, 통합 테스트, E2E 테스트를 실습합니다.

## 📚 학습 내용

- **Unit Testing**: 개별 노드 테스트
- **Integration Testing**: 여러 노드 통합 테스트
- **E2E Testing**: 전체 워크플로우 테스트
- **Mocking**: LLM 응답 모킹
- **Assertions**: 상태 및 결과 검증

## 📋 기술 스택

- **LangGraph**: 워크플로우 프레임워크
- **pytest**: 테스트 프레임워크
- **OpenAI**: 언어 모델

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일:
```env
OPENAI_API_KEY=your_api_key_here
```

### 2. 테스트 실행
```bash
uv run pytest tests.py -v
```

### 3. 개발
```bash
uv run python main.py
```

## 💡 배울 수 있는 것

- AI 에이전트 테스트 방법
- pytest 사용법
- LLM 모킹 기법
- 테스트 주도 개발 (TDD)

## 🔑 필요한 API 키

- ✅ OpenAI API Key (필수)

## 📦 필요한 패키지

이미 설치됨! (Python 3.13)
