# 법률 시스템 순차적 실행 가이드

법률 데이터를 Neo4j 그래프 데이터베이스로 구축하는 파이프라인.

## 데이터 소스 (2가지)

```
A) PDF Pipeline (legacy):  PDF → JSON → Neo4j → 임베딩 → Domain → 관계 임베딩
                          step1   step2   step3     step4      step5

B) API Pipeline (추천):   law_downloader.py → JSON → Neo4j → 임베딩 → Domain → 관계 임베딩
                                              step2   step3     step4      step5

C) 별표 구조화 확장:      official PDF/TXT → law/data/structured/*.json → APPENDIX rule nodes → Domain
```

**API Pipeline 추천**: law.go.kr Open API는 structured XML(조/항/호/목 태그)로 파서 버그 없음.
```bash
cd ARR/backend/law/scripts
python law_downloader.py --oc YOUR_EMAIL    # 10개 법률 → data/api/*.json
```

## Status (2026-02-23)

| Step | Script | Status | 소요 시간 | 비용 |
|------|--------|--------|----------|------|
| Step1 | `step1_pdf_to_json.py` | DONE | ~1분 | - |
| Step1-alt | `../scripts/law_downloader.py` | NEW | ~2분 | - |
| Step2 | `step2_json_to_neo4j.py` | DONE | ~2분 | - |
| Step3 | `step3_add_hang_embeddings.py` | DONE | ~20초 | ~$0.03 |
| Step4 | `step4_initialize_domains.py` | DONE | ~5분 | - |
| Step5 | `step5_run_relationship_embedding.py` | TODO | ~30분 | $2-3 |
| ALL | `run_all.py` | - | ~50분 | $3-5 |

## 사전 준비

- Neo4j 실행 중 (`bolt://localhost:7687`, pw=`11111111`)
- 환경변수: `NEO4J_PASSWORD`, `OPENAI_API_KEY`
- (API용) `LAW_API_OC` — open.law.go.kr 가입 후 로그인 ID

## Step별 상세

### Step 1: PDF → JSON (legacy)

```bash
python step1_pdf_to_json.py
```

출력: `law/data/parsed/*.json` (3개: 법률, 시행령, 시행규칙)

### Step 1-alt: API → JSON (추천)

```bash
python ../scripts/law_downloader.py --oc EMAIL --list   # 검색 테스트
python ../scripts/law_downloader.py --oc EMAIL           # 10개 법률 다운로드
```

출력: `law/data/api/*.json` (10개, step2 호환)

### Step 2: JSON → Neo4j

```bash
python step2_json_to_neo4j.py
```

현재 노드 수 (국토계획법 only, PDF pipeline):
- LAW: 3, JANG: 24, JEOL: 14
- JO: 920 (검색 인덱스)
- HANG: 1,966 (검색 대상, 임베딩 대상)
- HO: 1,118, MOK: 232

### Step 3: HANG 임베딩 (OpenAI)

```bash
python step3_add_hang_embeddings.py
```

- **모델**: OpenAI text-embedding-3-large (3,072-dim)
- **인덱스**: `hang_embedding_index` (cosine, ONLINE)
- **대상**: 1,966 HANG 노드

Standalone (Django 불필요):
```bash
LAW_NEO4J_PASSWORD=11111111 python ../scripts/run_step3_standalone.py
```

### Step 4: Domain 분류

```bash
python step4_initialize_domains.py
```

2개 Domain: 용도지역 (1838 nodes), 도시계획 및 이용 (128 nodes).

### Step 5: 관계 임베딩 (미완료)

```bash
python step5_run_relationship_embedding.py
```

### Appendix Extension: 주차장법/편의증진법 별표 구조화

기존 `LAW → JO → HANG → HO → MOK` 계층은 그대로 두고, 계산이 필요한 별표 표 행만 structured artifact로 관리한다. loader 코드에 법규 행을 직접 넣지 않는다.

```bash
python ../scripts/add_parking_law_semantics.py --uri bolt://localhost:7687
python ../scripts/add_parking_appendix_rules.py --uri bolt://localhost:7687 --data ../data/structured/parking_appendix_rules.json
python ../scripts/verify_parking_law_graph.py --uri bolt://localhost:7687
python ../scripts/check_parking_counts.py --uri bolt://localhost:7687
```

소스:
- `law/data/structured/parking_appendix_rules.json`
- `docs/legal-sources/parking_law_enforcement_decree_appendix1.pdf`
- `docs/legal-sources/accessibility_rule_appendix1.pdf`

Graph 확장:
- `APPENDIX.full_id`로 기존 조문 `HAS_APPENDIX`와 연결
- `ParkingRequirementRule.rule_id`, `AccessibleParkingFacilityRule.rule_id`는 unique key
- 모든 rule node는 기존 Domain 방식과 동일하게 `BELONGS_TO_DOMAIN`으로 묶음
- `check_parking_counts.py`는 여러 PNU 관할코드와 용도/면적 경계값을 넣어
  별표 비고 6 반올림, 1대 미만 0대, 단독주택 산식, 외부 위임, 장애인
  2~4% 범위 상태를 검산함

## 검증

```cypher
MATCH (n) RETURN labels(n)[0] as type, count(n) ORDER BY count(n) DESC
MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN count(h)
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain) RETURN d.domain_name, count(h) ORDER BY count(h) DESC
SHOW INDEXES
```

## Neo4j

```
bolt://localhost:7687, pw=11111111 (Neo4j Desktop) — 법규 데이터 전용
```
