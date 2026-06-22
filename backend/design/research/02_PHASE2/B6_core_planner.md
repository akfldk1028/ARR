# B6 — Core Planner ✅ DONE — heuristic v1 (2026-05-06 21:36)

## 상태: COMPLETE (휴리스틱 v1, 학습 없음)

**기간**: 2-3주 예상 → 1시간 (10 typology × strategy 매핑)
**학습**: ❌ — geometric heuristic (학습은 향후 ds04 라벨 후)
**구현**: `design/services/core_planner.py`
**실험**: `05_EXPERIMENTS/exp013_*.md`

## 원리

10 typology 별 코어 배치 전략:
| Typology | Strategy | 위치 |
|---|---|---|
| additive / subtractive / grid | centroid | 무게중심 |
| tower_podium | tower_centroid | upper part 무게중심 |
| lshape / cross | wing_intersection | 두 wing 교차점 (= centroid) |
| ushape / courtyard | inset_one_wing | 마당 회피, footprint 안쪽 |
| radial | centroid | 정중앙 |
| hshape | bridge_center | 가운데 bridge |

코어 사이즈: default 4×4m (16m²). footprint 안 들어가면 축소 (3→2→1.5m).

## API

```python
from design.services.core_planner import plan_core
plan = plan_core(footprint_utm, typology="subtractive", core_size_m=4.0)
# → CorePlan(typology, core_polygon_utm, inside_footprint, distance_to_boundary, ...)
```

## 회귀
**171/171 design 테스트 통과** (4 신규 CorePlannerTest).

---

## (Original Plan)

## 목적
플렉시티 광고처럼 매스 안에 *코어(계단실 + 엘리베이터)* 자동 배치. 매스 결정 후 코어 위치/크기 결정.

## 휴리스틱 + 학습

### 휴리스틱 (1주)
- 코어 면적 = 전체 면적의 5-10% (건축법 기준)
- 위치 후보: 매스 *중심* 또는 *측벽* (피난 동선 30m 이내 도달)
- 자연광 회피 (창 면적 손실 최소화)
- 구조 수직 통일 (모든 층에 같은 위치)

### 학습 (선택, 1-2주)
- ds04 (Phase 2) 사례에서 *코어 위치* 라벨링
- 작은 MLP: 입력 = 매스 형태 + 부지, 출력 = 코어 좌표/크기

## 작업
- `ARR/backend/design/services/core_planner.py` (신규)
- `floor_packer.py` 와 통합 — 코어를 *고정 영역*으로 평면 packing 시작

## 검증
- 한국 부지 100건 수동 검토 (도메인 전문가)
- 피난 거리 30m 이내 만족률 > 95%

## 학계 참고
- House-GAN++ (Nauata 2021) — floorplan 자동 생성 + room adjacency
- Graph2Plan (Wang 2021) — graph 기반 평면 생성
