# Financial Analyst (Google ADK)

## 🎯 무엇을 하는 프로젝트인가요?

금융 분석을 자동화하는 AI 시스템입니다. 주식 데이터 분석, 뉴스 분석, 투자 조언을 제공합니다.

## 🤖 서브 에이전트 구조

1. **Data Analyst**: 주식 데이터 수집 및 분석 (yfinance)
2. **News Analyst**: 금융 뉴스 분석 (Firecrawl)
3. **Financial Analyst**: 투자 조언 생성

## 📋 기술 스택

- **Google ADK**: Agent Development Kit
- **LiteLLM**: 다양한 LLM 통합
- **yfinance**: 주식 데이터
- **Firecrawl**: 뉴스 크롤링

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일:
```env
GOOGLE_API_KEY=your_google_key_here
FIRECRAWL_API_KEY=your_firecrawl_key_here  # 선택
```

### 2. 실행
```bash
uv run python -m financial_advisor.agent
```

## 💡 기능

- 📈 주식 데이터 분석
- 📰 금융 뉴스 분석
- 💰 투자 조언 생성
- 📊 포트폴리오 분석

## 🔑 필요한 API 키

- ⚠️ Google Gemini API Key (필수)
- ⚠️ Firecrawl API Key (선택)

## 📦 필요한 패키지

이미 설치됨! (Python 3.13)
