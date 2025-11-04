# Deep Research Clone (AutoGen)

## 🎯 무엇을 하는 프로젝트인가요?

심층 리서치를 자동화하는 AI 시스템입니다. 복잡한 주제를 다각도로 조사하고 종합 보고서를 작성합니다.

## 🤖 에이전트 구조

**AutoGen Framework** 사용:
- **Research Coordinator**: 리서치 조율
- **Web Researcher**: 웹 검색 및 정보 수집
- **Data Analyst**: 데이터 분석
- **Report Writer**: 보고서 작성

## 📋 기술 스택

- **AutoGen**: Microsoft의 멀티 에이전트 프레임워크
- **Firecrawl**: 웹 크롤링
- **OpenAI**: 언어 모델

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일:
```env
OPENAI_API_KEY=your_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_key_here
```

### 2. Jupyter Notebook 실행
```bash
uv run jupyter notebook
```

또는 Python 스크립트 실행

## 💡 기능

- 🔍 웹 리서치 자동화
- 📊 데이터 분석 및 시각화
- 📝 종합 보고서 생성
- 🤖 에이전트 간 협업

## 🔑 필요한 API 키

- ✅ OpenAI API Key (필수)
- ✅ Firecrawl API Key (필수)

## 📦 필요한 패키지

이미 설치됨! (Python 3.13)
