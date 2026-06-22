# Phase 2 — Light Learning

**기간**: 1-2개월 | **학습**: ⚠️ 경량 (자가 생성 데이터, CPU)

## 목적
Phase 1 Radiance가 GA를 비실용화 → Surrogate model로 100배 가속 + LLM RAG로 사례 기반 가이드.

## 작업 순서
1. B1a Dataset 자가 생성 (2주) — Phase 1 GA 1k-5k 매스 + Radiance 결과
2. B1b Surrogate 학습 (1주) — sklearn / lightgbm
3. B2 BO 통합 (1주)
4. B3 LLM RAG (2주)
5. B4 Heterogeneous Island (3주)
6. B5 Typology 추천 (1주)
7. **B6 Core Planner** 신규 (2-3주) — ⭐ 코어 자동 배치 (Flexity 광고)
8. **B7 Explanation Generator** 신규 (1-2주) — LLM이 매스 결정 한국어 설명

## 완료 조건
- BO 50평가 = GA 1500평가 hypervolume 동등
- RAG 부지 입력 → 유사 사례 3건 반환
- Heterogeneous island 다양성 +20%

## Phase 3 트리거
- Surrogate MSE plateau → 박스 적층 표현 한계 도달
- RAG 사례 매칭이 박스 적층으로는 부족 → SDF/Diffusion 필요
- 외부 데이터셋 1k+ 확보 가능성 검증 완료
