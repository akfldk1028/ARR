# Customer Support Agent

## 🎯 무엇을 하는 프로젝트인가요?

고객 지원을 자동화하는 멀티 에이전트 시스템입니다. 다양한 부서(기술, 주문, 계정, 결제)로 고객 문의를 자동으로 라우팅합니다.

## 🤖 에이전트 구조

### 5개의 전문 에이전트:

1. **TriageAgent** (분류 에이전트)
   - 고객 문의 분석 및 적절한 부서로 라우팅

2. **TechnicalAgent** (기술 지원)
   - 기술적 문제 해결

3. **OrderAgent** (주문 관리)
   - 주문 추적, 변경, 취소

4. **AccountAgent** (계정 관리)
   - 계정 관련 문의 처리

5. **BillingAgent** (결제/청구)
   - 결제 및 환불 처리

## 📋 기술 스택

- **OpenAI Agents**: 에이전트 오케스트레이션
- **Streamlit**: 웹 UI
- **Voice Support**: 음성 입력/출력
- **Workflow System**: 자동 라우팅

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일 확인:
```env
OPENAI_API_KEY=your_api_key_here
```

### 2. Streamlit 앱 실행
```bash
uv run streamlit run main.py
```

### 3. 웹 인터페이스 사용
- 텍스트 또는 음성으로 문의 입력
- 자동으로 적절한 부서 에이전트로 라우팅
- 실시간 답변 확인

## 💡 사용 예시

- "주문이 안 왔어요" → OrderAgent
- "비밀번호를 잊어버렸어요" → AccountAgent
- "환불받고 싶어요" → BillingAgent
- "앱이 작동하지 않아요" → TechnicalAgent

## 📦 필요한 패키지

이미 설치됨! (uv sync 완료)

## 🔑 필요한 API 키

- ✅ OpenAI API Key (필수)

## ⚡ 주요 기능

- 🤖 자동 문의 분류
- 🎙️ 음성 지원
- 🔄 워크플로우 관리
- 📊 고객 데이터 추적
