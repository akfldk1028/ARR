# B5 — Typology 추천기 ✅ DONE (2026-05-06 21:25)

## 상태: COMPLETE (Phase 2 minimum viable)

**기간**: 1주 예상 → 1시간으로 완료 (3 fixture 학습 데이터 한정)
**학습**: ❌ 학습 불필요 — k-NN with k=1 (가장 비슷한 fixture 반환)
**구현**: `design/services/typology_recommender.py`
**실험**: `05_EXPERIMENTS/exp010_*.{md,json}` + `04_DATASETS/data/typology_ranking.pkl`

## 검증 결과 (exp010)

| 부지 | Winner | HV |
|---|---|---|
| 강남 (일반상업, BCR80/FAR1300/H50) | **subtractive** | 552,714 |
| 분당 (2종 주거, BCR60/FAR250/H25) | **subtractive** | 95,283 |
| 춘천 (1종 주거, BCR60/FAR200/H20) | **radial** | 270,470 |

핵심: 절차적 매스 (additive/subtractive/grid) > typological 7종.

## API

```python
from design.services.typology_recommender import (
    SiteFeatures, recommend, set_ranking, TypologyRanking,
)
import pickle
with open('04_DATASETS/data/typology_ranking.pkl', 'rb') as f:
    set_ranking(TypologyRanking(**pickle.load(f)))

sf = SiteFeatures(area_m2=2000, bcr_limit=70, far_limit=400,
                  height_limit_m=30, aspect_ratio=1.2)
top3 = recommend(sf, top_k=3)
# → [{'typology': 'subtractive', 'score': 503519, 'rank': 1, 'rationale': '...'}, ...]
```

## 제한 + 다음

- **Fixture 3개만** — 운영 시 10+ 부지 추가 필요
- **2 obj 만** — 4 obj (compactness/stepback) 시 winner 바뀔 수 있음
- 사용자 모드: typology 직접 선택 + AI 추천 hint 동시 제공
- 데이터 늘어나면 GP/MLP 로 k-NN 대체 (현재 4개 단위 테스트 통과)

## 회귀
**160/160 design 테스트 통과** (4 신규 TypologyRecommenderTest).
