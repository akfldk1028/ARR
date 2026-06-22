# exp010 — Typology Benchmark (B5 Recommender 학습 데이터)

**Date**: 2026-05-06 21:25 KST (실측 완료, 57.6초)
**Phase**: 2
**작업 ID**: B5 Typology Recommender
**부지**: 3 fixture × 10 typology × 2 reps = 60 SSIEA runs
**Engine**: SSIEAJob + A6 repair on + A3 normalized

## 가설

10 매스 typology 가 *부지 특성에 따라 다른 성능* 보일 것.
- 고밀도 (강남 1300% FAR) → tower_podium / additive 유리?
- 중밀도 (분당 250%) → courtyard / ushape 유리?
- 저밀도 (춘천 200%) → lshape / radial 유리?

## 실험 매트릭스

| typology | 강남 HV | 분당 HV | 춘천 HV |
|---|---|---|---|
| additive | 272,689 | 28,809 | 161,559 |
| **subtractive** ⭐ | **552,714** | **95,283** | 170,726 |
| grid | 503,519 | 59,020 | 154,002 |
| lshape | 90,961 | 16,332 | 106,700 |
| ushape | 111,715 | 18,536 | 110,111 |
| cross | 99,737 | 16,869 | 104,513 |
| courtyard | 220,306 | 23,182 | 156,324 |
| tower_podium | 184,404 | 18,995 | 142,119 |
| hshape | 152,088 | 19,723 | 115,914 |
| **radial** ⭐ | 535,808 | 88,149 | **270,470** |

## Winners

| 부지 | Winner | 2nd | 3rd |
|------|------|------|------|
| 강남 역삼 677 (일반상업, BCR80/FAR1300/H50) | **subtractive** (552k) | radial (535k) | grid (503k) |
| 분당 (2종 주거, BCR60/FAR250/H25) | **subtractive** (95k) | radial (88k) | grid (59k) |
| 춘천 (1종 주거, BCR60/FAR200/H20) | **radial** (270k) | subtractive (170k) | additive (161k) |

## 핵심 발견

### 1. 절차적 매스 > 정형 typology (예상과 반대)
- *절차적* (additive/subtractive/grid, 22-29 genes) 가 모든 부지에서 상위 3
- *typological* (lshape~hshape, 10-16 genes) 은 일관 약함
- 이유: 절차적은 표현 공간 더 넓음 → GA가 더 자유롭게 탐색

### 2. Subtractive 압도적 — 정형 + 효율
- 기본 박스에서 voids 빼기 → 단순 + 공간 활용 + 채광
- BCR/FAR 한도 빠르게 채우면서 daylight 도 확보

### 3. Radial — 단일 부지 특화
- 춘천 *압도적 1위* (270k, 2위 170k 대비 +59%)
- 광활한 부지에 6분할 sector → 모든 방향 채광
- 강남에서도 2위, 분당에서도 2위 (consistent runner-up)

### 4. tower_podium / courtyard 의외로 약함
- 직관: 강남 고밀도엔 tower_podium 좋을 것
- 실제: tower_podium 184k < radial 535k (강남)
- 가능 원인: 9 genes 표현력 부족 + step-back/footprint 자유도 적음

## B5 Recommender 학습 데이터 활용

위 매트릭스 → `TypologyRanking` 에 저장 → `recommend(site_features)` API.

```python
from design.services.typology_recommender import (
    SiteFeatures, recommend, TypologyRanking, set_ranking,
)
import pickle
with open('04_DATASETS/data/typology_ranking.pkl', 'rb') as f:
    data = pickle.load(f)
set_ranking(TypologyRanking(**data))

# 새 부지 → top-3
sf = SiteFeatures(area_m2=2000, bcr_limit=70, far_limit=400,
                  height_limit_m=30, aspect_ratio=1.2)
top3 = recommend(sf, top_k=3)
# → [{typology: 'subtractive', score: ..., rationale: '가장 비슷한 fixture: 강남'}]
```

방법: k-NN with k=1 (가장 비슷한 fixture 의 ranking 반환). 데이터 늘어나면 GP/MLP 로 대체.

## 한계

1. **Fixture 3개만으로 학습** — 실 부지 다양성 부족
2. **2 obj (floor_area + daylight) 만 사용** — 4 obj (compactness, stepback) 추가 시 winner 바뀔 수 있음
3. **typological 7개의 SSIEA tuning 부족** — 표현력 차이라기보단 GA 파라미터 문제일 수도

## Production 가용성

✅ B5 minimum viable: `recommend()` API 호출 가능
- Frontend Land 페이지에서 부지 선택 시 → top-3 typology 추천 표시
- 사용자가 *해당 typology 만* SSIEA 실행 → 시간 절감

## 회귀
**152/152 design 테스트 통과**.

## 변경 파일
- `design/services/typology_recommender.py` (신규)
- `design/research/05_EXPERIMENTS/scripts/typology_benchmark.py` (신규)
- `04_DATASETS/data/typology_ranking.pkl` (신규, gitignore)
- `05_EXPERIMENTS/exp010_data.json` (raw 매트릭스 + winners)

## 다음
- exp011: PrecedentRAG 검증 (B3)
- exp012: B5 Recommender 실제 부지 (PNU 입력) 시연
- 데이터 확장: 부지 fixture 10개 이상 추가 → 학습 기반 recommendation
