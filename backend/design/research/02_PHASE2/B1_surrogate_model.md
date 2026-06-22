# B1 — Surrogate Model

**기간**: 2주 (B1a + B1b) | **학습**: ⚠️ 경량 (CPU, 분~시간) | **ROI 1.67**

## 목적
Radiance 평가 1매스 ~30s → ML 모델 inference ~1ms. GA 평가 비용 30,000배 ↓.

## 모델 후보
- **Gaussian Process (GP)** — sklearn, 100~1000 샘플에 강함
- **MLP** (3-layer, 64-32 hidden) — pytorch, 1k~10k 샘플
- **LightGBM** — gradient boosting, robust, fast

## 입출력
- 입력: 29-D gene 벡터 (Additive 매스 기준)
- 출력: UDI, sDA, BCR, FAR, daylight_score (5-D)

## 학습 데이터
- B1a 자가 생성 (Phase 1 GA + Radiance) 1k-5k

## 검증
- 5-fold CV, MSE / R²
- 학계 표준 (Westermann 2019 review): R² > 0.85 목표
- 초과 시 BO에 사용 (B2)

## 코드 위치 (예정)
- `ARR/backend/design/services/surrogate_model.py` 신규
- 학습된 weight: `ARR/backend/design/models/surrogate_v1.pkl`
