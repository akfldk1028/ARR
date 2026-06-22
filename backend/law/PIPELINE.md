# Law Ingestion Pipeline

Complete guide: data sources → JSON → Neo4j → embeddings → domains → search API.

## Architecture

```
Data Sources                 Pipeline                    Runtime
============                 ========                    =======

law.go.kr API ─┐
  (18 laws)    ├→ JSON ─→ json_to_neo4j.py ─→ Neo4j ←─ law-domain-agents (:8011)
PDF (legacy)  ─┘           (step2)             │              │
                                               │         /api/search
                                    run_step3  │         /api/domains
                                   (embeddings)│         /api/health
                                               │
                                    initialize_domains.py
                                   (5 domains, BELONGS_TO_DOMAIN rels)
```

## Data Sources

### A) law.go.kr Open API (recommended, 18 laws)

```bash
cd ARR/backend/law/scripts
C:/Python313/python law_downloader.py --oc hanvit4303 --list    # search test
C:/Python313/python law_downloader.py --oc hanvit4303 --force   # download all
```

**Output**: `ARR/backend/law/data/api/*.json` (18 files)

**Target laws** (LAWS_TO_DOWNLOAD in law_downloader.py — 6개 법률 × 3 types):

| # | Law | Type | Units |
|---|-----|------|-------|
| 1 | 국토의 계획 및 이용에 관한 법률 | 법률 | 1143 |
| 2 | 국토의 계획 및 이용에 관한 법률 | 시행령 | 1441 |
| 3 | 국토의 계획 및 이용에 관한 법률 | 시행규칙 | 160 |
| 4 | 건축법 | 법률 | 1066 |
| 5 | 건축법 | 시행령 | 1417 |
| 6 | 건축법 | 시행규칙 | 418 |
| 7 | 농지법 | 법률 | 519 |
| 8 | 농지법 | 시행령 | ~ |
| 9 | 농지법 | 시행규칙 | ~ |
| 10 | 산지관리법 | 법률 | 608 |
| 11 | 산지관리법 | 시행령 | ~ |
| 12 | 산지관리법 | 시행규칙 | ~ |
| 13 | 자연공원법 | 법률 | 475 |
| 14 | 자연공원법 | 시행령 | ~ |
| 15 | 자연공원법 | 시행규칙 | ~ |
| 16 | 수도법 | 법률 | 731 |
| 17 | 수도법 | 시행령 | ~ |
| 18 | 수도법 | 시행규칙 | ~ |

**API key**: `LAW_API_OC=hanvit4303` (OC = login ID from open.law.go.kr)

**Naming convention**: `base_name(law_type)` in Neo4j. The downloader strips 시행령/시행규칙 suffix from the API's matched name so `json_to_neo4j.py` correctly builds `건축법(시행령)::...` (not `건축법 시행령(시행령)::...`).

### B) PDF Pipeline (legacy, 국토계획법 only)

```bash
cd ARR/backend/law/STEP
python run_all.py   # step1(PDF→JSON) → step2 → step3 → step4 → step5
```

**Output**: `ARR/backend/law/data/parsed/*.json` (3 files: 법률/시행령/시행규칙)

**Note**: PDF pipeline has more units than API (234 empty 조 + body-text 항 extraction), but API data is structured and cleaner. Do NOT mix both for the same law.

## JSON Format (Standard)

```json
{
  "law_info": {
    "law_name": "건축법",         // base name (NO suffix)
    "law_type": "시행령",         // 법률 | 시행령 | 시행규칙
    "law_mst": "267115",
    "source": "law.go.kr Open API",
    "total_units": 1417
  },
  "units": [
    {
      "unit_type": "장",          // 편/장/절/관/조/항/호/목
      "unit_number": "1",
      "title": "총칙",
      "content": "...",
      "unit_path": "제1장",
      "full_id": "건축법::제1장",  // base_name::path (NO law_type here)
      "parent_id": "건축법",
      "order": 1,
      "revision_dates": [],
      "metadata": {}
    }
  ]
}
```

## Neo4j full_id Format

`json_to_neo4j.py` adds `(law_type)` to create unique full_ids:

```
JSON:   건축법::제1장::제3조::1
Neo4j:  건축법(시행령)::제1장::제3조::1
        ^^^^^^^^^^^^^^^^ law_with_type = f"{law_name}({law_type})"
```

## Step-by-Step Execution

### Prerequisites

- Neo4j running on `bolt://localhost:7687` (pw: `11111111`)
- Python 3.13+ with `neo4j`, `openai`, `numpy` packages
- `OPENAI_API_KEY` in `AG/agent/law-domain-agents/.env`

### Step 1: Download laws (if needed)

```bash
cd ARR/backend/law/scripts
C:/Python313/python law_downloader.py --oc hanvit4303 --force
```

### Step 2: Load JSON → Neo4j

```bash
cd ARR/backend/law/scripts

# Load individual file:
C:/Python313/python json_to_neo4j.py --json "../data/api/건축법_법률.json" --password 11111111

# Load all files in a directory:
C:/Python313/python json_to_neo4j.py --dir "../data/api" --all --password 11111111
```

**Verify**:
```cypher
MATCH (n) RETURN labels(n)[0] as type, count(n) ORDER BY count(n) DESC
MATCH (l:LAW) RETURN l.full_id ORDER BY l.full_id
```

### Step 3: Generate HANG embeddings

```bash
cd ARR/backend/law/scripts
LAW_NEO4J_PASSWORD=11111111 C:/Python313/python run_step3_standalone.py
```

Auto-finds HANG nodes without embeddings. Cost: ~$0.03/1000 nodes.

**Verify**:
```cypher
MATCH (h:HANG) WHERE h.embedding IS NULL RETURN count(h)
-- Should be 0
```

### Step 4: Initialize domains

```bash
cd AG/agent/law-domain-setup
C:/Python313/python initialize_domains.py
```

Deletes old domains, classifies all HANG nodes into 5 domains.

**Verify**:
```cypher
MATCH (d:Domain) RETURN d.domain_id, d.domain_name, d.node_count ORDER BY d.node_count DESC
```

### Step 5: Generate CONTAINS relationship embeddings

```bash
cd ARR/backend
LAW_NEO4J_PASSWORD=11111111 C:/Python313/python law/scripts/run_step5_incremental.py
```

Only processes relationships where `embedding IS NULL`. Cost: ~$0.85/6000 rels.

**Verify**:
```cypher
MATCH ()-[r:CONTAINS]->() WHERE r.embedding IS NULL RETURN count(r)
-- Should be 0
SHOW INDEXES WHERE name = 'contains_embedding'
-- Should be ONLINE
```

### Step 6: Restart search server

```bash
cd AG/agent/law-domain-agents
.venv/Scripts/python server.py
# or: C:/Python313/python server.py
```

**Verify**:
```bash
curl http://localhost:8011/api/health
# → domains_loaded: 5
curl http://localhost:8011/api/domains
# → 5 domains with counts
```

## Neo4j Schema (after full pipeline)

### Node Types

| Label | Count | Key Properties |
|-------|-------|----------------|
| LAW | 18 | full_id, name, title, law_type |
| JANG | 96 | full_id, number, title, content |
| JEOL | 50 | full_id, number, title |
| JO | 2431 | full_id, number, title, content |
| HANG | 6171 | full_id, content, embedding (3072-dim) |
| HO | 6026 | full_id, content |
| MOK | 1284 | full_id, content |
| Domain | 5 | domain_id, domain_name, description, node_count |

### Relationships

| Type | Pattern | Description |
|------|---------|-------------|
| CONTAINS | (LAW)→(JANG)→(JO)→(HANG)→(HO)→(MOK) | Hierarchical containment |
| NEXT | (JO)→(JO), (HANG)→(HANG) | Sequential ordering |
| BELONGS_TO_DOMAIN | (HANG)→(Domain) | Domain classification |
| CITES | (JO)→(target) | Cross-law citation |

### Vector Indexes

| Index | Label/Rel | Property | Dimensions |
|-------|-----------|----------|------------|
| hang_embedding_index | HANG | embedding | 3072 |
| ho_embedding_index | HO | embedding | 3072 |
| mok_embedding_index | MOK | embedding | 3072 |
| jo_embedding_index | JO | embedding | 3072 |
| contains_embedding | CONTAINS (rel) | embedding | 3072 |

### Fulltext Indexes

| Index | Label | Property | Analyzer |
|-------|-------|----------|----------|
| hang_content_fulltext | HANG | content | CJK bi-gram |
| jo_content_fulltext | JO | content | standard |

## Domain Classification Rules

| Domain | domain_id | Rule |
|--------|-----------|------|
| 건축기준 | building_standards | full_id starts with "건축법" |
| 토지이용규제 | land_use_regulation | full_id starts with 농지법/산지관리법/자연공원법/수도법 |
| 용도지역 및 건축규제 | zoning_regulation | 국토계획법 + "::제4장::" in full_id |
| 도시계획 | urban_planning | 국토계획법 + "::제3장::" or "::제6장::" |
| 국토계획 총론 | national_land_planning | 국토계획법 catch-all |

Rule priority: building_standards → land_use_regulation → zoning → urban_planning → national_land_planning

## Code File Map

### Pipeline Scripts (`ARR/backend/law/scripts/`)

| File | What | Calls |
|------|------|-------|
| `law_downloader.py` | law.go.kr API → JSON | law.go.kr REST API |
| `json_to_neo4j.py` | JSON → Neo4j nodes/rels | `neo4j_loader.py` |
| `neo4j_loader.py` | Neo4j batch writer | neo4j driver |
| `run_step3_standalone.py` | HANG embeddings | OpenAI API + Neo4j |
| `run_step5_incremental.py` | CONTAINS rel embeddings (incremental) | OpenAI API + Neo4j |
| `pdf_to_json.py` | PDF → JSON (legacy step1) | `pdf_extractor.py`, `neo4j_preprocessor.py` |

### Domain Setup (`AG/agent/law-domain-setup/`)

| File | What |
|------|------|
| `initialize_domains.py` | Create 5 Domain nodes, classify HANG→Domain |
| `recreate_vector_index.py` | Drop + recreate vector indexes |

### Search Engine (`AG/agent/law-domain-agents/`)

| File | What |
|------|------|
| `server.py` | FastAPI server (:8011), REST + A2A endpoints |
| `law_search_engine.py` | Hybrid search (exact + vector + RNE + RRF) |
| `domain_manager.py` | Load domains from Neo4j, slug mapping |
| `law_utils.py` | Result enrichment (law_name, law_type, article) |

## Troubleshooting

### "Connection refused" on :8011
law-domain-agents not running. Start with `python server.py`.

### "domains_loaded: 0"
Run `initialize_domains.py` to create Domain nodes. Then restart server.

### HANG nodes without embeddings
```bash
cd ARR/backend/law/scripts
LAW_NEO4J_PASSWORD=11111111 C:/Python313/python run_step3_standalone.py
```

### CONTAINS rels without embeddings
```bash
cd ARR/backend
LAW_NEO4J_PASSWORD=11111111 C:/Python313/python law/scripts/run_step5_incremental.py
```

### Duplicate/redundant full_ids
If you see `건축법 시행령(시행령)::...`, re-download with fixed `law_downloader.py` and reload. The base_name stripping logic ensures `건축법(시행령)::...`.

### Vector search returns unrelated results
Check `hang_embedding_index` status:
```cypher
SHOW INDEXES WHERE name = 'hang_embedding_index'
```
If not ONLINE, recreate: `python recreate_vector_index.py`

### Adding a new law
1. Add to `LAWS_TO_DOWNLOAD` in `law_downloader.py`
2. Run downloader with `--force`
3. Run `json_to_neo4j.py --json <new_file> --password 11111111`
4. Run `run_step3_standalone.py` (auto-finds new nodes)
5. Add classification rule in `initialize_domains.py`
6. Run `initialize_domains.py`
7. Restart search server
