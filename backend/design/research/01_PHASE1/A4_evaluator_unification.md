# A4 — Evaluator 인터페이스 통일

**기간**: 2일 | **학습**: ❌ | **ROI 3.0**

## 목적
`mass_evaluator.py`, `regulation_validator.py`, `floor_*` 평가가 각자 다른 입출력. 통일 인터페이스로 교체 가능 구조 만듦.

## 작업
- `ARR/backend/design/services/mass_evaluator.py` — `Evaluator` 추상 클래스 정의
- 메소드: `evaluate(polygon: Polygon) -> Dict[str, float]`
- 구현체: `BasicGeometricEvaluator`(현재), `RadianceEvaluator`(A2 후), `SurrogateEvaluator`(B1 후)

## 검증
- 추상 인터페이스 단위 테스트
- 기존 통합 테스트 (`tests.py`) 통과
