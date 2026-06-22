# exp008 — Surrogate Training (Phase 2 진입 첫 학습)

**Date**: 2026-05-06 21:12 KST (실측 완료)
**Phase**: 2
**작업 ID**: B1b Surrogate Training
**Dataset**: `ds01_self_generated_ga.json` (3000 samples, 99.97% feasible)
**Train/Test split**: 2400 / 600 (80/20, random_state=42)

## 가설

3000 sample 자가 생성 데이터로 surrogate 학습 시 mean R² ≥ 0.7 도달 가능. 빠른 응답 (1초 미만 추론) 가능.

## 모델 비교 — 3종

| 모델 | 학습시간 | floor_area R² | daylight R² | bcr R² | far R² | **mean R²** |
|------|------|------|------|------|------|------|
| RandomForest (200 trees) | 0.51s | 0.9365 | 0.7587 | 0.6451 | 0.9368 | 0.8193 |
| **MLP (64,32) ⭐** | **0.49s** | 0.9213 | **0.7828** | **0.6615** | 0.9200 | **0.8214** |
| GP (subsample 1000) | 1.50s | 0.8436 | 0.5163 | 0.5013 | 0.8163 | 0.6694 |

→ **MLP best** (mean R² 0.82). RandomForest 거의 동일. GP 가장 약함 (subsample 영향).

## 핵심 발견

### Floor area / FAR R² ≥ 0.92 — 거의 deterministic
- footprint × num_floors → floor_area, /site_area → FAR
- gene_vector 만으로 거의 정확히 계산 가능
- surrogate가 이 두 metric은 *시뮬레이터를 거의 대체*

### Daylight / BCR R² 0.66~0.78 — 중간
- daylight_score = formula(open_ratio, perimeter, stepback) — 복잡
- bcr = footprint_area / site_area — repair 후 footprint 모양 의존
- 추가 데이터 (5k+) + feature engineering 으로 개선 여지

## Production 가용성

mean R² 0.82는 *GA를 guide* 하기엔 충분 (B2 BO acquisition function 에서 ranking이 정확하면 OK). *시뮬레이터 완전 대체*는 부족 (R² 0.95+ 필요).

## 추론 속도

학습 < 1초, 추론 < 1ms (MLP forward pass 작음). SSIEA 1매스 ~1ms 와 동등 또는 빠름.
→ Phase 1 baseline 대비 **속도 이득 없음** (geometric 평가가 이미 빠름).
→ Surrogate 진가는 **Radiance 활성화 후** (실 평가 30s/매스 → surrogate 1ms = 3만배).

## 결론

✅ **B1b Surrogate 학습 성공**.
- MLP mean R² 0.82, floor_area/FAR R² 0.92
- **현재 박스 적층 baseline에는 surrogate 가치 적음** (geometric 평가가 이미 빠름)
- Radiance 활성화 (Phase 1 exp005 BLOCKED) 후 진가 발휘 → **B2 BO 효과 검증 시점은 Radiance 이후**

## 다음

- **B2 Bayesian Optimization** — surrogate 위에 BO acquisition (EI/UCB)
  - 현재 surrogate 정확도로 BO가 SSIEA 1500 평가 = BO 50 평가 도달 검증
  - 단, geometric evaluator 빠르므로 BO의 *실용적* 이점은 Radiance 도입 후
- **B3 LLM RAG** — 건축 사례 인덱싱 (검색만, 학습 X)
- exp005 follow-up: Radiance 바이너리 설치 후 → ds01 v2 (UDI 포함) 재학습

## 모델 저장
- `04_DATASETS/data/surrogate_best.pkl` (MLP + scalers, gitignore)

## 변경 파일
- `05_EXPERIMENTS/scripts/surrogate_training.py` (신규)
- `05_EXPERIMENTS/exp008_data.json` (raw, 모델 R²/MAE)

## 회귀
**152/152 design 테스트 통과**.
