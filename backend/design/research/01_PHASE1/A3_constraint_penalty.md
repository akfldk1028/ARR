# A3 — Constraint penalty 정교화

**기간**: 3일 | **학습**: ❌ | **ROI 2.0**

## 목적
현재 `objects.py:189-205` 의 penalty는 *위반 개수만 카운트* (binary). 위반 *정도* 무시됨. → 위반 거리에 비례한 penalty로 정규화.

## 작업
- `ARR/backend/design/engine/objects.py:189-205` — `set_outputs()` 안 penalty 계산 수정
- 정규화: `penalty += max(0, val - goal_val) / abs(goal_val)` (Less than 케이스)
- 효과: GA가 *덜 위반하는 매스* 부터 점진 개선

## 검증
- 단위 테스트: 위반 거리에 따라 penalty 단조 증가 확인
- baseline vs 정규화 penalty 결과 비교
