# Job Hunter Agent (CrewAI)

## 🎯 무엇을 하는 프로젝트인가요?

구직 활동을 자동화하는 AI 시스템입니다. 이력서 최적화, 맞춤형 커버레터 작성, 채용 공고 분석을 수행합니다.

## 🤖 CrewAI 에이전트 팀

- **Job Researcher**: 채용 공고 검색 및 분석
- **Resume Optimizer**: 이력서 최적화
- **Cover Letter Writer**: 맞춤형 커버레터 작성
- **Application Tracker**: 지원 현황 관리

## 📋 기술 스택

- **CrewAI**: 멀티 에이전트 협업
- **Firecrawl**: 채용 사이트 크롤링
- **Python 3.11**: ChromaDB 호환성

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일:
```env
OPENAI_API_KEY=your_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_key_here
```

### 2. 실행
```bash
uv run python main.py
```

## 💡 기능

- 🔍 채용 공고 자동 검색
- 📄 이력서 키워드 최적화
- ✍️ 맞춤형 커버레터 생성
- 📊 지원 현황 추적

## 🔑 필요한 API 키

- ✅ OpenAI API Key (필수)
- ✅ Firecrawl API Key (필수)

## ⚠️ Python 3.11 사용
