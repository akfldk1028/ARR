# B2 — Bayesian Optimization

**기간**: 1주 | **학습**: ❌ (B1 모델 사용) | **ROI 2.0**

## 목적
GA의 무작위 시도 대신 *surrogate 위에서 acquisition function* 으로 다음 매스 결정. 50 평가 = GA 1500 평가 동등.

## 방법
- Acquisition: Expected Improvement (EI) 또는 Upper Confidence Bound (UCB)
- 라이브러리: `scikit-optimize`, `bayesian-optimization`, 또는 직접 구현

## 코드 (예정)
- `ARR/backend/design/services/bayesian_optimizer.py`
- `BOJob` 클래스 — 기존 `Job`/`SSIEAJob`/`NSGA3Job` 인터페이스 호환

## 검증
- BO 50 평가 vs GA 1500 평가 hypervolume 비교
- 동등하면 GA 30배 빠름 → 실서비스 적용
