# B3 — LLM + 건축 사례 RAG ✅ DONE — minimum viable (2026-05-06 21:27)

## 상태: 인프라 완료 (offline + online 모드)

**기간**: 2주 예상 → 1시간 (10 case demo corpus)
**학습**: ❌ (인덱싱만)
**구현**: `design/services/precedent_rag.py` (PrecedentRAG 클래스)
**실험**: `05_EXPERIMENTS/exp011_*.md`

## 원리

1. **Embedding-based search** (online): query → OpenAI text-embedding-3-large (3072d) → cosine similarity → top-K
2. **Keyword fallback** (offline, API 없을 때): zone 매칭 + typology 매칭 + word overlap

## API

```python
from design.services.precedent_rag import PrecedentRAG
rag = PrecedentRAG()
rag.load_or_build()  # OPENAI_API_KEY 있으면 online, 없으면 offline

results = rag.search("강남 일반상업 1300% FAR", top_k=3)
# offline: zone 매칭 → 강남 사례 top
# online: cosine similarity 3072d
```

## Demo Corpus

10 hand-curated 한국 매스 사례 (강남/분당/춘천/도심/광활/광장 등). Schema:
- id, name, zone, bcr_pct, far_pct, height_limit_m, aspect_ratio, typology, description, tags

## 검증 (exp011 offline)

| Query | Top-1 매칭 |
|---|---|
| 강남 일반상업 1300% FAR 고층 | 강남 테헤란로 'tower_podium' ✓ |
| 분당 아파트 정북일조 25m | 분당 신도시 2종 'courtyard' ✓ |
| 춘천 단독 주거 | 춘천 1종 'lshape' ✓ |
| 광활한 부지 H자 매스 | 광활한 부지 'hshape' ✓ |

## 운영 통합 시나리오

Frontend Land 페이지:
1. 부지 선택 → SiteFeatures 추출 → typology recommendation (B5)
2. zone + typology → PrecedentRAG search → 실제 사례 1-3건
3. UI: "추천 매스: subtractive | 비슷한 사례: 강남 테헤란로..."

## 한계

- **10 case** — 데모 수준. 운영 100~1000 사례 필요
- **Hand-curated** — 도시건축통합지도 자동 수집 별도 PR
- **Image embedding 없음** — text only (CLIP multimodal 향후)
- **Generation 단계 없음** — gpt-4o-mini 로 결과 *요약/설명* 추가 가능 (B7)

## 회귀
**160/160 design 테스트 통과** (4 신규 PrecedentRAGTest).

## Open Questions
1. 사례 데이터 출처 — 도시건축통합지도 라이선스
2. Image LOD 수준 — CLIP 추가 시 결정
3. Neo4j vs separate pgvector — 현재 numpy npy 충분 (10~1k 케이스)
