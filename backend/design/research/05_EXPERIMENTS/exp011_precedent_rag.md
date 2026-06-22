# exp011 — Precedent RAG 검증 (B3)

**Date**: 2026-05-06 21:27 KST (offline mode 검증)
**Phase**: 2
**작업 ID**: B3 LLM RAG (건축 사례 검색)
**모드**: offline (keyword fallback) — OpenAI API 미사용

## 원리 (Principle)

**Retrieval-Augmented Generation (RAG)**:
- 사례 corpus → 임베딩 (text-embedding-3-large 3072-dim) → 벡터 인덱스
- query (자연어) → 임베딩 → cosine similarity top-K corpus item

**왜 필요한가**:
- SSIEA가 새 매스를 *생성* 하지만, 사용자는 "비슷한 실제 사례" 도 보고 싶음
- 매스 + 사례 = 사용자 신뢰 ↑ (Flexity 광고처럼 *근거 있는 추천*)

**Offline fallback**:
- OpenAI API 없을 때 keyword 매칭 (zone + typology + words 점수)
- API 활성화 시 자동 cosine similarity 전환

## Demo Corpus

`design/services/precedent_rag.py:DEMO_CORPUS` — 10 건 한국 매스 사례 hand-curated
- 강남 / 분당 / 춘천 부지 케이스 + 도심 좁은 부지 / 광활한 부지 / 광장형 등
- Schema: id, name, zone, bcr_pct, far_pct, height_limit_m, aspect_ratio, typology, description, tags

## 검증 — offline keyword 매칭

| Query | Top-1 Result | Top-2 | Top-3 |
|---|---|---|---|
| 강남 일반상업 1300% FAR 고층 매스 | 강남 테헤란로 'tower_podium' (sim 0.50) | 고층 주거 'tower_podium' (강남구) (0.50) | 방사형 광장 'radial' (0.30) |
| 분당 아파트 정북일조 25m | 분당 신도시 2종 'courtyard' (0.40) | U자 공동주택 'ushape' (분당) (0.20) | 고층 주거 'tower_podium' (강남구) (0.10) |
| 춘천 단독 주거 | 춘천 1종 'lshape' (0.30) | 분당 신도시 'courtyard' (0.10) | 도심 좁은 부지 'cross' (0.10) |
| 광활한 부지 H자 매스 | 광활한 부지 'hshape' (0.40) | 도심 좁은 부지 'cross' (0.20) | 방사형 광장 'radial' (0.20) |

→ **모든 query 의 top-1 이 의미적으로 정확**. zone + typology + 부지 특성 매칭.

## 결론

✅ **B3 PrecedentRAG 인프라 검증 완료** (offline mode).

- 10 case corpus 키워드 매칭으로도 합리적 검색
- API 활성화 시 (OPENAI_API_KEY 설정) 자동 임베딩 + cosine
- B5 Typology Recommender 와 시너지: typology 추천 → 실제 사례 1-2개 함께 표시

## 활성화 절차 (online mode)

```bash
export OPENAI_API_KEY=sk-...

# Build embeddings (1회):
python -c "
import django; django.setup()
from design.services.precedent_rag import PrecedentRAG
rag = PrecedentRAG()
rag.build_with_openai()  # OpenAI API 호출, 10 sample × 3072-dim
rag.save()
"

# 이후 검색:
rag = PrecedentRAG()
rag.load()  # corpus + embeddings npy
results = rag.search('강남 1300% FAR', top_k=3)  # cosine similarity
```

## 한계

1. **10 case corpus** — 데모 수준. 실 운영 시 100~1000 사례 필요
2. **Hand-curated** — 도시건축통합지도 / 잡지 / 학술 자료 자동 수집 필요
3. **Image embedding 없음** — text only. 향후 CLIP 등 multimodal 추가
4. **Generation 단계 없음** — LLM (gpt-4o-mini) 으로 검색 결과 *요약/설명* 추가 가능

## Production 통합

Frontend Land 페이지:
1. 사용자가 부지 선택 → SiteFeatures 추출
2. typology_recommender.recommend(sf) → top-3 typology
3. precedent_rag.search(zone + typology) → top-3 실제 사례
4. UI: "추천 매스: subtractive (HV 552k) | 비슷한 사례: 강남 테헤란로..."

## 변경 파일
- `design/services/precedent_rag.py` (신규)
- `04_DATASETS/data/precedent_corpus.json` (gitignore, save 시 자동)
- `04_DATASETS/data/precedent_embeddings.npy` (gitignore, online mode 시)

## 회귀
**152/152 design 테스트 통과**.

## 다음
- B6 Core Planner — 코어/엘리베이터 위치 자동
- B7 Explanation Generator — LLM 으로 매스 결과 자연어 설명
- 사례 확장: 도시건축통합지도 자동 수집 + 인덱싱 (실 사용 시점)
