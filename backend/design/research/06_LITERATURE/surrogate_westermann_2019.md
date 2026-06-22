# Westermann 2019 — Surrogate Model 리뷰

**저자**: Westermann, P., Evins, R.
**저널**: *Building and Environment* (또는 *Renewable & Sustainable Energy Reviews*)
**연도**: 2019

## 핵심
건물 에너지 surrogate model 리뷰. GP, MLP, GBM, Random Forest 비교.

## 학계 표준 정확도
- R² > 0.85 (실용 임계값)
- 학습 데이터 1k-5k가 일반적

## 우리 시스템과의 연결
- Phase 2 B1 surrogate 학습 검증 기준
- B1b 학습 후 R² 측정해 본 논문 기준 충족 확인

## 적용 가능 모델
- LightGBM (가장 빠름, 정확도 좋음)
- GP (작은 데이터에 강함, 1k 이하)
- MLP (확장성, 5k+ 데이터)
