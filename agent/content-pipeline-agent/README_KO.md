# Content Pipeline Agent (CrewAI)

## 🎯 무엇을 하는 프로젝트인가요?

콘텐츠 제작 파이프라인을 자동화하는 AI 시스템입니다. SEO와 바이럴리티를 고려한 블로그 글, 소셜 미디어 콘텐츠를 생성합니다.

## 🤖 CrewAI 에이전트 팀

### SEO Crew (SEO 최적화 팀):
- SEO 전략가
- 키워드 리서처
- 콘텐츠 작성자

### Virality Crew (바이럴리티 팀):
- 트렌드 분석가
- 소셜 미디어 전문가
- 카피라이터

## 📋 기술 스택

- **CrewAI**: 멀티 에이전트 오케스트레이션
- **ChromaDB**: 벡터 데이터베이스 (메모리)
- **Firecrawl**: 웹 스크래핑
- **Python 3.11**: ChromaDB 호환성

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일 확인:
```env
OPENAI_API_KEY=your_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_key_here
```

### 2. 실행
```bash
uv run python main.py
```

## 💡 작동 방식

1. **주제 입력**: 콘텐츠 주제 제공
2. **리서치**: 웹에서 관련 정보 수집
3. **SEO 분석**: 키워드 및 SEO 전략 수립
4. **콘텐츠 생성**: 블로그 글, 소셜 미디어 포스트 작성
5. **최적화**: 바이럴리티 및 SEO 최적화

## 📦 필요한 패키지

이미 설치됨! (Python 3.11 사용)

## 🔑 필요한 API 키

- ✅ OpenAI API Key (필수)
- ✅ Firecrawl API Key (필수)

## ⚠️ 중요 사항

이 프로젝트는 **Python 3.11**을 사용합니다 (ChromaDB 호환성).
다른 프로젝트는 Python 3.13을 사용합니다.
