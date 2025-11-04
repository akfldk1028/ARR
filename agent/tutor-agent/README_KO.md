# Tutor Agent

## 🎯 무엇을 하는 프로젝트인가요?

AI 튜터 시스템입니다. 학생의 질문을 분류하고, 적절한 교육 방법(설명, 퀴즈, Feynman 기법)으로 학습을 돕습니다.

## 🤖 에이전트 구조

### 4개의 전문 에이전트:

1. **ClassificationAgent** (분류 에이전트)
   - 학생 질문 분석 및 학습 방법 결정

2. **TeacherAgent** (선생님 에이전트)
   - 개념 설명 및 가이드

3. **QuizAgent** (퀴즈 에이전트)
   - 이해도 테스트 퀴즈 생성 및 채점

4. **FeynmanAgent** (Feynman 기법 에이전트)
   - 학생이 개념을 설명하도록 유도하여 학습

## 📋 기술 스택

- **LangGraph**: 워크플로우 관리
- **LangGraph Supervisor**: 에이전트 조율
- **OpenAI**: 언어 모델
- **Firecrawl** (선택): 웹에서 학습 자료 수집

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일 확인:
```env
OPENAI_API_KEY=your_api_key_here
FIRECRAWL_API_KEY=your_key_here  # 선택사항
```

### 2. 실행
```bash
uv run python main.py
```

## 💡 학습 방법

1. **설명 모드**: 선생님이 개념을 설명
2. **퀴즈 모드**: 이해도 테스트
3. **Feynman 모드**: 학생이 개념을 설명 (가장 효과적!)

## 📚 사용 예시

- "양자역학이 뭐예요?" → TeacherAgent가 설명
- "퀴즈 내주세요" → QuizAgent가 문제 출제
- "제가 설명해볼게요" → FeynmanAgent가 피드백

## 📦 필요한 패키지

이미 설치됨! (uv sync 완료)

## 🔑 필요한 API 키

- ✅ OpenAI API Key (필수)
- ⚠️ Firecrawl API Key (선택)
