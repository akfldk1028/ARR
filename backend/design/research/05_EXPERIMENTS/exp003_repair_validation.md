# exp003 — A6 Repair Operator 검증

**Date**: 2026-05-06 19:55~19:57 KST (실측 완료)
**Phase**: 1
**작업 ID**: A6 Repair Operator
**부지**: 강남 역삼 677 / 분당 / 춘천 (3종 fixture, exp001과 동일)
**반복**: 3회

## 가설
A6 Repair Operator (`enable_repair=True`) 활성화 시 hard constraint 위반 매스가 *자동 수정* 되어 feasible % 가 큰 폭으로 상승할 것. 특히 exp001에서 **분당 0% feasible** 케이스가 dramatic하게 개선될 것.

## 변경 사항
- `services/mass_evaluator.py` `evaluate_designs(enable_repair=True)` 활성화
- `services/repair_operator.py` `repair_design()` 호출 — site_clip / setback_clip / north_setback / bcr_clamp / height_cap / far_cap

## 측정 스크립트
`research/05_EXPERIMENTS/scripts/benchmark.py` (exp001 동일, `--repair` 플래그 추가)

```bash
cd ARR/backend
DJANGO_SETTINGS_MODULE=backend.settings python -c "
import sys; sys.path.insert(0, 'design/research/05_EXPERIMENTS/scripts')
import django; django.setup()
import benchmark
benchmark.run(reps=3, enable_repair=True, exp_id='exp003')
"
```

## 결과 1차 (실패) — exp001 변화 없음

분당 0% 그대로. 원인 추적:
- `outputs_def`: `setback ≥ 1m` (인접) + **`building_line_setback ≥ 3m` (도로)** 둘 다 constraint
- `_build_repair_limits_from_outputs` 가 `setback`만 추출, **`building_line_setback` 미추출**
- 결과: repair는 1m inward buffer만 적용 → 도로 3m 후퇴 미통과 → constraint 위반 유지

## Fix (2026-05-06)

### 1. `RegulationLimits.road_setback_m: float = 3.0` 필드 추가
### 2. `repair_footprint`에서 `effective_setback = max(adjacent_setback_m, road_setback_m)` 사용
도로 3m > 인접 1m → 도로 setback이 binding constraint. 보수적 적용 (모든 boundary에서 max).

### 3. `_build_repair_limits_from_outputs` 가 `building_line_setback` 자동 추출
```python
elif name == "building_line_setback":  # exp003 발견
    limits.road_setback_m = val
```

## 결과 2차 ~ 4차 (단계적 fix)

### v2: road_setback fix
| 부지 | feasible | HV |
|---|---|---|
| 강남 | 71.30% | 257380 |
| 분당 | 65.24% | 22334 |
| 춘천 | 38.92% | 60093 |

여전히 30~60% 위반 — 추가 분석.

### v3: is_multi reset + boundary semantic
- 분석: 위반의 90%가 BCR=200, FAR=9999 — repair 후에도 *원본* `is_multi=True` 플래그 유지하면 강제 penalty 값 그대로
- Fix: `_compute_metrics` 에서 repair 후 `is_multi = isinstance(footprint, MultiPolygon)` 재계산
- 추가 발견: setback 정확히 boundary (=3.0) 케이스에서 "Greater than 3.0" 위반. 라벨은 "≥ 3m"인데 코드는 strict `>`. 수정.

| 부지 | feasible | HV |
|---|---|---|
| 강남 | 100.0% ✅ | 286726 |
| 분당 | 99.62% | 25782 |
| 춘천 | 72.57% | 65455 |

춘천만 잔여 — 추가 분석.

### v4: UTM area 일치
- 분석: 춘천 worst case → BCR=56%/FAR=371%/h=19.6m/setback=3 → repair는 6층 통과시켰으나 _compute_metrics가 보고한 FAR=371 (한도 200)
- 핵심 버그: `TEST_SITES["chuncheon_test"].area_m2 = 1200`. 그러나 wgs84→utm 변환 결과 실제 면적 = **2440**. Mismatch!
  - `_compute_metrics`: BCR/FAR = footprint / **1200** (fixture 값)
  - `repair_floors`: max_floors = limit × **2440** / footprint (실제 UTM 값)
  - → repair 통과했는데 _compute_metrics 보면 위반
- Fix: benchmark 가 UTM 변환 후 `site_utm.area`를 fixture에 덮어씀 (production 코드 변경 X)

### v4 최종 결과 (모든 fix 적용)

| 부지 | exp001 baseline (no repair, UTM area fixed) | exp003 (A6 repair on, all fixes) | Δ Feasible | Δ HV |
|------|------|------|------|------|
| 강남 역삼 677 | 12.16% / HV 45732 | **100.00%** / HV **264908** | **+88%pt** | **+480%** |
| **분당** | 6.44% / HV 4921 | **99.97%** / HV **28432** | **+94%pt** | **+478%** |
| 춘천 | 15.65% / HV 64784 | **99.93%** / HV **160761** | **+84%pt** | **+148%** |

Runtime: 1.07s → 1.71s (~+60%, repair 호출 비용. 여전히 빠름)

## 결론

✅ **A6 Repair Operator + 모든 fix 누적 효과 정량 검증 완료**.

- **모든 부지 99.93~100% feasible** 도달
- HV 강남 +480%, 분당 +478%, 춘천 +148%
- 핵심 가설(*hard constraint 자동 강제*) 정확 검증

## 발견된 버그 5종 (모두 수정)

1. **`building_line_setback` (도로 후퇴) 미추출** — `_build_repair_limits_from_outputs`
2. **inward buffer가 `adjacent_setback`만** — `effective_setback = max(adjacent, road)`
3. **`is_multi` 플래그가 repair 후에도 원본 유지** — `_compute_metrics` 에서 재계산
4. **`set_outputs` boundary 처리 strict** (라벨 ≤/≥인데 코드는 <,>) — 라벨 일치
5. **fixture `area_m2` ≠ UTM 면적** — benchmark에서 UTM 면적 사용 (production 영향 0)

## 회귀
**152/152 design 테스트 모두 통과**. 모든 변경 후.

## 다음 실험
- **exp002**: NSGA-III vs SSIEAJob HV 비교 (4+ objectives, baseline 99% feasible 위에서 공정 비교)
- **exp004**: A3 Penalty 정규화 vs binary 수렴 속도
- **exp005**: A2 Radiance UDI 실측 (바이너리 설치 후)

## 다음 실험
- **exp002**: NSGA-III vs SSIEAJob HV 비교 (4+ objectives)
- **exp004**: A3 Penalty 정규화 수렴 속도 영향 (vs binary count)
- **exp005**: A2 Radiance UDI 실측 (바이너리 설치 후)

## 참조 데이터
- `exp001_baseline_data.json` — baseline raw
- `exp003_data.json` — repair on raw
- 핵심 fix commit: `services/repair_operator.py` + `services/mass_evaluator.py`
