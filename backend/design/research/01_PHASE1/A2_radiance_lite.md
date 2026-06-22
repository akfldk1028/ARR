# A2 — Radiance lite 통합

**기간**: 1주
**학습**: ❌
**효과**: ★★★★★ / 비용: ★★ / ROI 2.5

## 목적

현재 "일조 평가"는 *정북일조 사선과 매스가 부딪히는 부피 계산*(기하 검증). 진짜 채광 품질이 아님.

→ Radiance(rtrace)로 **UDI**(Useful Daylight Illuminance, 연중 채광 시간 비율)와 **sDA**(spatial Daylight Autonomy, 자연광 충족 면적)를 계산.

## 작업

### 의존성 (requirements.txt 추가)
- pyradiance 또는 honeybee-radiance
- Radiance 바이너리 별도 설치 (Windows: 별도 인스톨러)

### 코드 변경 위치
- `ARR/backend/design/services/mass_evaluator.py` — `radiance_evaluate(mass_polygon)` 함수 신규
- 기존 `simulate_solar()` 와 인터페이스 호환

### 평가 흐름
```python
def radiance_evaluate(mass_polygon, weather_file='Seoul.epw'):
    # 1. Polygon → OBJ 변환
    obj = polygon_to_obj(mass_polygon)
    # 2. Radiance scene 생성
    scene = create_scene(obj, weather_file)
    # 3. UDI/sDA 계산 (~30s)
    udi = compute_udi(scene, threshold_lux=(100, 2000))
    sda = compute_sda(scene, threshold=300, hours=0.5)
    return {'udi': udi, 'sda': sda}
```

## 위험

- Windows 환경에서 Radiance 설치 까다로움 → Docker/WSL2 우회
- 1매스 평가 ~30s → GA 50 gen × 30 indiv = 12.5h. *Phase 2 surrogate 트리거*

## 검증

- 단일 매스 회귀 테스트 (`tests.py`): UDI 0~1, sDA 0~1 범위 확인
- Seoul 표준 .epw 파일 사용
- `05_EXPERIMENTS/exp003_radiance_validation.md` 결과 기록

## 참고

- Radiance: https://www.radiance-online.org
- honeybee-radiance: https://www.ladybug.tools/honeybee-radiance/
- Reinhart, C. F. (2014). UDI methodology

## 진행 상황 (2026-05-06)

- ✅ **인터페이스 + fallback 구현 완료**: `services/radiance_evaluator.py` (신규)
  - `RADIANCE_AVAILABLE` flag (현재 False, pyradiance 미설치 시 자동 fallback)
  - `RadianceConfig` dataclass (Seoul.epw, grid_size=1m, UDI 100~2000 lux, sDA 300 lux)
  - `RadianceEvaluator(Evaluator)` — A4 Evaluator 추상 인터페이스 준수
  - `_fallback_udi_sda()` — pyradiance 미설치 시 기존 daylight_score 로직으로 UDI/sDA proxy 계산
  - `_radiance_compute_udi_sda()` — 실제 광선 추적 (`NotImplementedError` placeholder, follow-up PR)
  - `register_evaluator("radiance", RadianceEvaluator)` — 자동 등록
- ✅ **단위 테스트 4개 추가** (`tests.py:RadianceEvaluatorTest`)
  - `test_evaluator_registered` — registry 등록 확인
  - `test_fallback_when_not_installed` — RADIANCE_AVAILABLE=False 시 using_fallback=True
  - `test_fallback_udi_sda_range` — UDI/sDA 0~1 범위 검증
  - `test_fallback_empty_footprint` — 빈 footprint 시 0,0 반환

## 활성화 절차 (follow-up)

1. Radiance 바이너리 설치 (Windows: 별도 인스톨러 또는 WSL2 + Linux 빌드)
2. `pip install pyradiance` 또는 `pip install honeybee-radiance`
3. `RADIANCE_AVAILABLE = True` 로 변경
4. `_radiance_compute_udi_sda()` 실제 구현 채움 (footprint→OBJ→scene→rtrace)
5. Seoul.epw 다운로드 → `design/data/weather/Seoul.epw`
6. 단일 매스 평가 시간 측정 → Phase 2 surrogate 트리거 결정
