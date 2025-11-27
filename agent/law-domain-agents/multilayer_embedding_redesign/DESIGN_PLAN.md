# Multi-Layer Embedding Redesign - Design Plan

**Date:** 2025-11-18
**Based on:** ArXiv 2411.07739 (Multi-Layered Embedding), ArXiv 2510.19365 (MLEB)
**Goal:** Implement JO-level embeddings to solve structural article search problem

---

## Overview

### Problem Statement

**Current:** Only HANG nodes are embedded → 30% of articles invisible
**Solution:** Add JO-level embeddings + multi-level search
**Impact:** 15% failure rate → <2% failure rate, 40s → 2s latency

### Success Criteria

1. Query "용도지역이란 무엇인가요?" returns Chapter 4, Article 36 (not 부칙)
2. All JO nodes (with or without HANG children) are searchable
3. No regression in existing HANG-based search quality
4. Latency improvement: 40s → <5s for definition queries
5. Cost reduction: 7 LLM calls → 0-1 LLM calls per query

---

## Phase 1: JO-Level Embedding Generation

**Duration:** 2-3 days
**Priority:** P0 (Critical)
**Dependencies:** None

### Phase 1.1: Data Analysis

**Objective:** Understand JO node structure in Neo4j

**Tasks:**

1. **Count JO nodes**
   ```cypher
   MATCH (jo:JO)
   RETURN count(jo) as total_jo_nodes
   ```
   - Expected: ~500 nodes

2. **Identify JO nodes without HANG children**
   ```cypher
   MATCH (jo:JO)
   WHERE NOT EXISTS((jo)-[:CONTAINS]->(:HANG))
   RETURN jo.full_id, jo.title, jo.number
   ORDER BY jo.full_id
   ```
   - Expected: ~150 nodes (30%)
   - Critical case: 제36조 (용도지역의 지정)

3. **Analyze JO node properties**
   ```cypher
   MATCH (jo:JO)
   RETURN DISTINCT keys(jo) as properties
   ```
   - Expected properties: full_id, title, number, content

4. **Verify the "용도지역" case**
   ```cypher
   MATCH (jo:JO)
   WHERE jo.title CONTAINS "용도지역"
   RETURN jo.full_id, jo.title, jo.number,
          EXISTS((jo)-[:CONTAINS]->(:HANG)) as has_hang,
          [(jo)-[:CONTAINS]->(child) | child.title] as children
   ```

**Deliverable:** Analysis report with node counts and structure

### Phase 1.2: JO Embedding Content Strategy

**Objective:** Define what text to embed for each JO node

**Three Options:**

#### Option A: Title Only
```python
def create_jo_embedding_text_option_a(jo_node):
    """Simple but may lack context"""
    return jo_node.title
```

**Pros:**
- Simple, fast
- Works for well-named articles

**Cons:**
- Generic titles may not match queries
- Example: "도시관리계획의 입안" → hard to match "계획 수립 절차"

#### Option B: Title + First HANG Content
```python
def create_jo_embedding_text_option_b(jo_node):
    """Moderate complexity"""
    title = jo_node.title

    # Get first HANG child
    first_hang = jo_node.children(HANG)[0] if jo_node.children(HANG) else None

    if first_hang:
        return f"{title}\n\n{first_hang.content[:500]}"
    else:
        # No HANG: use JO content or title only
        return jo_node.content or title
```

**Pros:**
- Adds concrete context
- Fast (no summarization needed)

**Cons:**
- First HANG may not be representative
- Still incomplete picture

#### Option C: Title + Summary of All HANGs (RECOMMENDED)
```python
def create_jo_embedding_text_option_c(jo_node):
    """
    Paper-recommended approach
    Provides complete context
    """
    title = jo_node.title

    # Get all HANG children
    hang_children = jo_node.children(HANG)

    if hang_children:
        # Concatenate all HANG contents
        all_hang_text = "\n".join([h.content for h in hang_children])

        # Truncate if too long (max 1000 chars for embedding)
        if len(all_hang_text) > 1000:
            summary = all_hang_text[:1000] + "..."
        else:
            summary = all_hang_text

        return f"{title}\n\n{summary}"

    else:
        # No HANG children: use JO content or sub-articles
        if jo_node.content:
            return f"{title}\n\n{jo_node.content}"
        else:
            # Has sub-articles (e.g., 제36조의1, 제36조의2)
            # Use title only + structural note
            return f"{title} (구조 조항)"
```

**Pros:**
- Complete semantic representation
- Matches paper recommendations
- Handles all cases (HANG, no HANG, sub-articles)

**Cons:**
- Slightly more complex
- May need truncation

**Decision: Use Option C**

### Phase 1.3: JO Embedding Generation Script

**File:** `backend/law/scripts/add_jo_embeddings.py`

**Implementation:**

```python
"""
JO 노드에 KR-SBERT 임베딩 추가

목적:
- 모든 JO (조) 노드에 768-dim 임베딩 생성
- HANG이 없는 구조 조항도 검색 가능하도록
- 용도지역 쿼리 문제 해결
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import logging
from langchain_neo4j import Neo4jGraph
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_jo_embedding_text(jo_row):
    """
    JO 노드의 임베딩용 텍스트 생성 (Option C)

    Args:
        jo_row: Neo4j query result row
            - title: JO 제목
            - content: JO 본문 (있으면)
            - hang_contents: HANG 자식 노드 내용 리스트

    Returns:
        임베딩할 텍스트
    """
    title = jo_row.get('title', '')
    content = jo_row.get('content', '')
    hang_contents = jo_row.get('hang_contents', [])

    # Case 1: Has HANG children
    if hang_contents:
        # Concatenate all HANG contents
        all_hang = "\n".join([h for h in hang_contents if h])

        # Truncate if too long
        if len(all_hang) > 1000:
            summary = all_hang[:1000] + "..."
        else:
            summary = all_hang

        return f"{title}\n\n{summary}"

    # Case 2: No HANG, but has content
    elif content:
        return f"{title}\n\n{content}"

    # Case 3: No HANG, no content (structural article)
    else:
        return f"{title} (구조 조항)"


def main():
    print("=" * 80)
    print("JO 노드 임베딩 생성")
    print("=" * 80)

    # Neo4j 연결
    uri = os.getenv('NEO4J_URI', 'neo4j://127.0.0.1:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', '11111111')
    database = os.getenv('NEO4J_DATABASE', 'neo4j')

    logger.info(f"Connecting to Neo4j: {uri}")
    graph = Neo4jGraph(url=uri, username=user, password=password, database=database)

    # JO 노드 가져오기
    logger.info("Fetching JO nodes...")
    query = """
    MATCH (jo:JO)
    OPTIONAL MATCH (jo)-[:CONTAINS]->(h:HANG)
    WITH jo,
         collect(h.content) as hang_contents
    RETURN elementId(jo) AS elementId,
           jo.full_id AS full_id,
           jo.title AS title,
           jo.content AS content,
           hang_contents,
           size(hang_contents) as hang_count
    ORDER BY jo.full_id
    """
    result = graph.query(query)
    logger.info(f"Found {len(result)} JO nodes")

    # 통계
    total_jo = len(result)
    jo_with_hang = sum(1 for r in result if r['hang_count'] > 0)
    jo_without_hang = total_jo - jo_with_hang

    print(f"\n통계:")
    print(f"  총 JO 노드: {total_jo}")
    print(f"  HANG 있는 JO: {jo_with_hang} ({100*jo_with_hang//total_jo}%)")
    print(f"  HANG 없는 JO: {jo_without_hang} ({100*jo_without_hang//total_jo}%)")
    print()

    # KR-SBERT 모델 로드
    logger.info("Loading KR-SBERT model...")
    model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
    logger.info("Model loaded (768-dim)")

    # 배치 처리
    batch_size = 50
    total_batches = (len(result) - 1) // batch_size + 1
    success_count = 0

    for i in range(0, len(result), batch_size):
        batch = result[i:i+batch_size]
        batch_num = i // batch_size + 1

        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} nodes)...")

        # 임베딩 텍스트 생성
        texts = [create_jo_embedding_text(row) for row in batch]

        # 임베딩 생성
        embeddings = model.encode(texts, show_progress_bar=False)

        # Neo4j 업데이트
        update_query = """
        UNWIND $rows AS row
        MATCH (jo) WHERE elementId(jo) = row.elementId
        SET jo.embedding = row.embedding,
            jo.embedding_text = row.text
        """

        rows = [
            {
                'elementId': batch[j]['elementId'],
                'embedding': embeddings[j].tolist(),
                'text': texts[j]
            }
            for j in range(len(batch))
        ]

        graph.query(update_query, params={'rows': rows})
        success_count += len(batch)

        logger.info(f"  Saved {len(batch)} embeddings")

    print()
    print("=" * 80)
    print("완료!")
    print("=" * 80)
    print(f"  성공: {success_count}/{total_jo}")
    print(f"  모델: KR-SBERT (768-dim)")
    print()
    print("다음 단계:")
    print("  1. JO 벡터 인덱스 생성 (Phase 1.4)")
    print("  2. 검색 알고리즘 업데이트 (Phase 2)")
    print("=" * 80)


if __name__ == "__main__":
    main()
```

**Execution:**
```bash
cd D:\Data\11_Backend\01_ARR\backend
.venv\Scripts\python.exe law\scripts\add_jo_embeddings.py
```

### Phase 1.4: Create Vector Index for JO

**Objective:** Enable vector search on JO embeddings

**Implementation:**

```cypher
// Create JO embedding vector index
CREATE VECTOR INDEX jo_embedding_index IF NOT EXISTS
FOR (jo:JO)
ON jo.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}};

// Verify index creation
SHOW INDEXES
YIELD name, type, labelsOrTypes, properties, state
WHERE name = 'jo_embedding_index';

// Test query
CALL db.index.vector.queryNodes(
  'jo_embedding_index',
  10,
  [0.1, 0.2, ..., 0.768]  // dummy vector
) YIELD node, score
RETURN node.title, score
LIMIT 5;
```

**Script:** `backend/law/scripts/create_jo_vector_index.py`

```python
"""JO 벡터 인덱스 생성"""
import os, sys
sys.path.insert(0, 'D:/Data/11_Backend/01_ARR/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from graph_db.services.neo4j_service import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

print("Creating JO embedding vector index...")

query = """
CREATE VECTOR INDEX jo_embedding_index IF NOT EXISTS
FOR (jo:JO)
ON jo.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}}
"""

neo4j.execute_query(query, {})

print("Index created successfully!")

# Verify
verify_query = """
SHOW INDEXES
YIELD name, type, state
WHERE name = 'jo_embedding_index'
RETURN name, type, state
"""

result = neo4j.execute_query(verify_query, {})
print(f"Verification: {result}")

neo4j.disconnect()
```

**Phase 1 Deliverables:**
- ✅ JO nodes analyzed
- ✅ ~500 JO embeddings generated (768-dim KR-SBERT)
- ✅ Vector index created (`jo_embedding_index`)
- ✅ Validation query successful

---

## Phase 2: Multi-Level Search Algorithm

**Duration:** 3-4 days
**Priority:** P0 (Critical)
**Dependencies:** Phase 1 complete

### Phase 2.1: Implement Hierarchical Search

**Objective:** Search both JO and HANG levels, merge intelligently

**File:** `backend/agents/law/domain_agent.py`

**New Method: `_multi_level_search()`**

```python
async def _multi_level_search(
    self,
    query: str,
    kr_sbert_embedding: List[float],
    limit: int = 10
) -> List[Dict]:
    """
    Multi-level search: JO + HANG

    Args:
        query: User query
        kr_sbert_embedding: Query embedding (768-dim)
        limit: Max results

    Returns:
        Merged results from JO and HANG searches
    """
    logger.info(f"[Multi-Level] Starting JO + HANG search...")

    # [1] JO-level search (structural)
    jo_results = await self._search_jo_level(kr_sbert_embedding, limit=20)
    logger.info(f"[Multi-Level] JO search: {len(jo_results)} results")

    # [2] HANG-level search (detailed)
    hang_results = await self._search_hang_level(kr_sbert_embedding, limit=20)
    logger.info(f"[Multi-Level] HANG search: {len(hang_results)} results")

    # [3] Hierarchical boosting
    boosted_results = self._apply_hierarchical_boosting(jo_results, hang_results)

    # [4] Path-aware scoring
    scored_results = self._apply_path_scoring(boosted_results)

    # [5] Merge and sort
    final_results = sorted(scored_results, key=lambda x: x['final_score'], reverse=True)

    logger.info(f"[Multi-Level] Final: {len(final_results[:limit])} results")

    return final_results[:limit]
```

**New Method: `_search_jo_level()`**

```python
async def _search_jo_level(
    self,
    query_embedding: List[float],
    limit: int = 20
) -> List[Dict]:
    """
    JO-level vector search

    Args:
        query_embedding: KR-SBERT embedding (768-dim)
        limit: Max results

    Returns:
        JO search results
    """
    query = """
    CALL db.index.vector.queryNodes('jo_embedding_index', $limit, $embedding)
    YIELD node, score
    WHERE EXISTS((node)-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: $domain_id}))
      AND score >= 0.5
      AND NOT node.full_id CONTAINS '부칙'
    RETURN node.full_id AS jo_id,
           node.title AS jo_title,
           node.embedding_text AS embedding_text,
           score AS similarity,
           [(node)-[:CONTAINS]->(h:HANG) | h.full_id] AS child_hang_ids
    ORDER BY score DESC
    LIMIT $limit
    """

    results = self.neo4j_service.execute_query(query, {
        'embedding': query_embedding,
        'domain_id': self.domain_id,
        'limit': limit
    })

    return [
        {
            'type': 'JO',
            'jo_id': r['jo_id'],
            'jo_title': r['jo_title'],
            'content': r['embedding_text'],
            'similarity': r['similarity'],
            'child_hang_ids': r['child_hang_ids'],
            'stage': 'jo_vector'
        }
        for r in results
    ]
```

**New Method: `_search_hang_level()`**

```python
async def _search_hang_level(
    self,
    query_embedding: List[float],
    limit: int = 20
) -> List[Dict]:
    """
    HANG-level vector search (existing logic, slightly modified)

    Args:
        query_embedding: KR-SBERT embedding (768-dim)
        limit: Max results

    Returns:
        HANG search results with parent JO info
    """
    query = """
    CALL db.index.vector.queryNodes('hang_embedding_index', $limit, $embedding)
    YIELD node, score
    WHERE EXISTS((node)-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: $domain_id}))
      AND score >= 0.5
    MATCH (node)<-[:CONTAINS*]-(jo:JO)
    RETURN node.full_id AS hang_id,
           node.content AS content,
           score AS similarity,
           jo.full_id AS parent_jo_id,
           jo.title AS parent_jo_title
    ORDER BY score DESC
    LIMIT $limit
    """

    results = self.neo4j_service.execute_query(query, {
        'embedding': query_embedding,
        'domain_id': self.domain_id,
        'limit': limit
    })

    return [
        {
            'type': 'HANG',
            'hang_id': r['hang_id'],
            'content': r['content'],
            'similarity': r['similarity'],
            'parent_jo_id': r['parent_jo_id'],
            'parent_jo_title': r['parent_jo_title'],
            'stage': 'hang_vector'
        }
        for r in results
    ]
```

### Phase 2.2: Hierarchical Boosting

**Objective:** Boost scores when JO and HANG match together

**Method: `_apply_hierarchical_boosting()`**

```python
def _apply_hierarchical_boosting(
    self,
    jo_results: List[Dict],
    hang_results: List[Dict]
) -> List[Dict]:
    """
    Apply hierarchical boosting:
    - If JO matches, boost its child HANGs
    - If HANG matches, boost its parent JO

    Args:
        jo_results: JO search results
        hang_results: HANG search results

    Returns:
        All results with boosted scores
    """
    all_results = []

    # Process JO results
    for jo_r in jo_results:
        jo_r['boosted_score'] = jo_r['similarity']

        # Find child HANGs in hang_results
        child_hang_ids = set(jo_r['child_hang_ids'])
        matching_children = [
            h for h in hang_results
            if h['hang_id'] in child_hang_ids
        ]

        if matching_children:
            # Boost JO score (has matching children)
            jo_r['boosted_score'] *= 1.2
            jo_r['boost_reason'] = f"Has {len(matching_children)} matching child HANGs"

        all_results.append(jo_r)

    # Process HANG results
    for hang_r in hang_results:
        hang_r['boosted_score'] = hang_r['similarity']

        # Check if parent JO is in jo_results
        matching_parent = next(
            (jo for jo in jo_results if jo['jo_id'] == hang_r['parent_jo_id']),
            None
        )

        if matching_parent:
            # Boost HANG score (parent JO also matches)
            hang_r['boosted_score'] *= 1.3
            hang_r['boost_reason'] = f"Parent JO '{matching_parent['jo_title']}' also matches"

        all_results.append(hang_r)

    return all_results
```

### Phase 2.3: Path-Aware Scoring

**Objective:** Penalize 부칙, prioritize main chapters

**Method: `_apply_path_scoring()`**

```python
def _apply_path_scoring(self, results: List[Dict]) -> List[Dict]:
    """
    Apply path-aware scoring:
    - Penalize 부칙 (appendix)
    - Boost main chapters (제1장~제10장)
    - Neutral for others

    Args:
        results: Results with boosted_score

    Returns:
        Results with final_score
    """
    for result in results:
        # Get full_id
        if result['type'] == 'JO':
            full_id = result['jo_id']
        else:  # HANG
            full_id = result['hang_id']

        # Path scoring
        if '부칙' in full_id or '附則' in full_id:
            path_multiplier = 0.5  # Strong penalty
        elif any(f'제{i}장' in full_id for i in range(1, 11)):
            path_multiplier = 1.2  # Boost main chapters
        else:
            path_multiplier = 1.0  # Neutral

        # Final score
        result['final_score'] = result['boosted_score'] * path_multiplier
        result['path_multiplier'] = path_multiplier

    return results
```

### Phase 2.4: Integration with Existing Search

**Modify: `_search_my_domain()`**

```python
async def _search_my_domain(self, query: str, limit: int = 10) -> List[Dict]:
    """
    UPDATED: Multi-level search pipeline

    Old: Exact + Semantic (HANG-only) + RRF
    New: Exact + Multi-level (JO+HANG) + Hierarchical boosting + Path scoring
    """
    logger.info(f"[DomainAgent {self.domain_name}] Search query: {query[:50]}...")

    # [1] Generate embeddings
    kr_sbert_embedding = await self._generate_kr_sbert_embedding(query)
    openai_embedding = await self._generate_openai_embedding(query)

    # [2] Exact match (unchanged)
    exact_results = await self._exact_match_search(query, limit=limit)

    # [3] Multi-level search (NEW!)
    multi_level_results = await self._multi_level_search(
        query,
        kr_sbert_embedding,
        limit=limit * 2
    )

    # [4] Relationship search (unchanged)
    relationship_results = await self._search_relationships(openai_embedding, limit=limit)

    # [5] Merge all results
    all_results = self._merge_all_search_results(
        exact_results,
        multi_level_results,
        relationship_results
    )

    # [6] RNE expansion (optional, unchanged)
    if len(all_results) < 5:
        rne_results = await self._rne_graph_expansion(query, all_results, kr_sbert_embedding)
        all_results = self._merge_hybrid_and_rne(all_results, rne_results)

    return all_results[:limit]
```

**Phase 2 Deliverables:**
- ✅ Multi-level search implemented
- ✅ Hierarchical boosting working
- ✅ Path-aware scoring integrated
- ✅ Backward compatible with existing search

---

## Phase 3: Integration & Testing

**Duration:** 2-3 days
**Priority:** P0 (Critical)
**Dependencies:** Phase 1 & 2 complete

### Phase 3.1: Validation Tests

**Test 1: 용도지역 Query**

```python
# File: backend/test_multilevel_search.py

import os, sys
sys.path.insert(0, 'D:/Data/11_Backend/01_ARR/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from agents.law.agent_manager import get_agent_manager

agent_manager = get_agent_manager()

# Test query
query = "용도지역이란 무엇인가요?"

print("="*80)
print(f"Query: {query}")
print("="*80)

# Get primary domain
primary_domain_agent = agent_manager.get_primary_domain(query)

# Search
results = primary_domain_agent.search(query, limit=10)

print(f"\nResults: {len(results)}")
for i, r in enumerate(results[:5], 1):
    print(f"\n{i}. Type: {r['type']}")
    if r['type'] == 'JO':
        print(f"   JO ID: {r['jo_id']}")
        print(f"   Title: {r['jo_title']}")
    else:
        print(f"   HANG ID: {r['hang_id']}")
        print(f"   Parent JO: {r['parent_jo_title']}")
    print(f"   Similarity: {r['similarity']:.3f}")
    print(f"   Boosted: {r['boosted_score']:.3f}")
    print(f"   Final: {r['final_score']:.3f}")
    print(f"   Stage: {r['stage']}")

# Validation
assert '제36조' in results[0]['jo_id'] or results[0]['parent_jo_id'], \
    "FAILED: 제36조 not in top result!"

assert '부칙' not in results[0]['jo_id'] and '부칙' not in results[0].get('hang_id', ''), \
    "FAILED: 부칙 in top result!"

print("\n" + "="*80)
print("✅ VALIDATION PASSED!")
print("="*80)
```

**Expected Output:**
```
Query: 용도지역이란 무엇인가요?
================================================================================

Results: 10

1. Type: JO
   JO ID: 국토의_계획_및_이용에_관한_법률_법률_제4장_제36조
   Title: 용도지역의 지정
   Similarity: 0.921
   Boosted: 1.105  (has 3 matching child HANGs)
   Final: 1.326  (path_multiplier=1.2 for main chapter)
   Stage: jo_vector

2. Type: HANG
   HANG ID: 국토의_계획_및_이용에_관한_법률_법률_제4장_제36조의1_제1항
   Parent JO: 주거지역
   Similarity: 0.856
   Boosted: 1.113  (parent JO matches)
   Final: 1.335
   Stage: hang_vector

... (more results)

================================================================================
✅ VALIDATION PASSED!
================================================================================
```

**Test 2: Regression Test (Existing Queries)**

```python
# Ensure existing queries still work

test_queries = [
    "17조 검색",  # Exact match
    "도시관리계획 수립 절차",  # Semantic
    "용도지역 변경 조건",  # Multi-word
]

for query in test_queries:
    results = primary_domain_agent.search(query, limit=5)
    assert len(results) > 0, f"FAILED: No results for '{query}'"
    print(f"✅ '{query}': {len(results)} results")
```

### Phase 3.2: Performance Testing

**Latency Test:**

```python
import time

queries = [
    "용도지역이란 무엇인가요?",
    "도시계획 수립 절차는?",
    "17조 내용",
]

for query in queries:
    start = time.time()
    results = agent.search(query, limit=10)
    elapsed = time.time() - start

    print(f"Query: {query}")
    print(f"  Latency: {elapsed:.2f}s")
    print(f"  Results: {len(results)}")
    print()

# Target: <5s per query (vs. 40s before)
```

**A2A Reduction Test:**

```python
# Count A2A calls before and after

# Before (HANG-only): ~7 LLM calls per "용도지역" query
# After (Multi-level): 0 LLM calls (direct match)

# Measure
api_call_count = agent.get_api_call_count()  # Track in agent

print(f"LLM API calls: {api_call_count}")
assert api_call_count == 0, "Should not need A2A for direct match queries!"
```

### Phase 3.3: Update Documentation

**Files to Update:**

1. `backend/LAW_SEARCH_SYSTEM_ARCHITECTURE.md`
   - Add multi-level search section
   - Update vector indexes section
   - Add JO embedding description

2. `backend/law/SYSTEM_GUIDE.md`
   - Add JO embedding generation guide
   - Update search pipeline diagram

3. `backend/START_HERE.md`
   - Update "Current Features" section

### Phase 3.4: Production Deployment

**Checklist:**

- [ ] Phase 1 complete: JO embeddings generated
- [ ] Phase 2 complete: Multi-level search implemented
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Code review complete
- [ ] Backup Neo4j database
- [ ] Deploy to staging
- [ ] Smoke test on staging
- [ ] Deploy to production
- [ ] Monitor for 24 hours

**Rollback Plan:**

If issues arise:
1. Revert `domain_agent.py` changes
2. System falls back to HANG-only search (no data loss)
3. JO embeddings remain in DB (safe, not used)

---

## Phase 4: Advanced Features (Optional)

**Duration:** 5-7 days
**Priority:** P1 (Nice to have)
**Dependencies:** Phase 3 complete + production stable

### Phase 4.1: LLM-Based JO Summarization

**Current:** Concatenate all HANG contents (truncate at 1000 chars)
**Upgrade:** Use GPT-4o-mini to generate semantic summary

```python
def create_jo_summary_llm(jo_node):
    """
    Use LLM to create concise summary of JO article

    Args:
        jo_node: JO node with HANG children

    Returns:
        Semantic summary (200-300 chars)
    """
    from openai import OpenAI

    title = jo_node.title
    hang_contents = [h.content for h in jo_node.children(HANG)]

    if not hang_contents:
        return title

    prompt = f"""다음 법률 조항의 핵심 내용을 200자 이내로 요약하세요.

조항 제목: {title}

세부 항 내용:
{chr(10).join(hang_contents)}

요약 (200자 이내):"""

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.3
    )

    summary = response.choices[0].message.content.strip()

    return f"{title}\n\n{summary}"
```

**Pros:**
- More semantic summary
- Better embedding quality

**Cons:**
- API cost (~$0.001 per JO × 500 JOs = $0.50 one-time)
- Slower generation (2s per JO × 500 = 17 minutes one-time)

**Decision:** Implement if Phase 3 results show embedding quality issues

### Phase 4.2: HO (호) Level Embeddings

**Objective:** Embed enumeration items

**Use Case:**
- Queries like "허용 용도 목록"
- Detailed sub-item search

**Implementation:** Similar to JO embedding script

**Priority:** P2 (only if user feedback requests it)

### Phase 4.3: Cross-Level Relationship Embeddings

**Objective:** Embed JO↔HANG relationships (not just CONTAINS)

**Example:**
```
JO: "용도지역의 지정"
  → CONTAINS →
HANG: "주거지역은 다음과 같이 구분한다"

Relationship embedding:
"용도지역 중 주거지역 구분 기준"
```

**Benefit:** Better contextual search

**Priority:** P2

---

## Timeline Summary

### Week 1: Phase 1 (JO Embeddings)
- Day 1-2: Data analysis, script development
- Day 3: Generate embeddings, create index
- Day 4: Validation

### Week 2: Phase 2 (Multi-Level Search)
- Day 5-7: Implement multi-level search
- Day 8: Hierarchical boosting
- Day 9: Path scoring
- Day 10: Integration

### Week 3: Phase 3 (Testing & Deployment)
- Day 11-12: Validation tests
- Day 13: Performance tests
- Day 14: Documentation
- Day 15: Staging deployment
- Day 16: Production deployment
- Day 17-18: Monitoring

### (Optional) Week 4+: Phase 4 (Advanced)
- As needed based on results

**Total:** 3 weeks for core implementation (Phase 1-3)

---

## Success Metrics

### Quantitative

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Coverage | 70% of articles | 100% | Count searchable JO nodes |
| Latency (definition query) | 40s | <5s | Avg response time |
| Accuracy (용도지역) | Wrong (부칙) | Correct (제36조) | Manual validation |
| LLM API calls | 7/query | 0-1/query | Count API calls |
| Failure rate | 15% | <2% | User feedback |

### Qualitative

- [ ] Users can find structural articles (e.g., 용도지역 정의)
- [ ] No regression in existing HANG-based search
- [ ] 부칙 results properly deprioritized
- [ ] Search results include parent context (JO title)

---

## Risk Mitigation

### Risk 1: JO Embeddings Quality Issues

**Risk:** JO title-only embeddings may not match user queries well

**Mitigation:**
- Use Option C (title + HANG summary) for richer context
- Monitor similarity scores in Phase 3
- If needed, implement Phase 4.1 (LLM summarization)

### Risk 2: Performance Degradation

**Risk:** Searching 2 indexes (JO + HANG) may be slower

**Mitigation:**
- Parallel search execution (async)
- Limit JO search to top 20 results (vs. unlimited)
- Use Neo4j index warming

**Monitoring:**
```python
# Track latency
start = time.time()
jo_results = await self._search_jo_level(...)
jo_time = time.time() - start

hang_results = await self._search_hang_level(...)
hang_time = time.time() - start - jo_time

logger.info(f"JO search: {jo_time:.2f}s, HANG search: {hang_time:.2f}s")
```

### Risk 3: Index Size Growth

**Risk:** Adding ~500 JO embeddings increases DB size

**Impact:**
- JO embeddings: 500 nodes × 768 floats × 4 bytes = 1.5 MB
- Negligible (HANG embeddings = 1,477 × 768 × 4 = 4.5 MB)

**Mitigation:** Not needed (acceptable size)

---

## Conclusion

This design plan provides a clear, phased approach to implementing multi-level embeddings based on latest research. The implementation is:

- **Evidence-based:** Follows ArXiv 2411.07739 and 2510.19365 recommendations
- **Incremental:** 3 phases with clear deliverables
- **Low-risk:** Backward compatible, easy rollback
- **High-impact:** Solves critical "용도지역" problem, improves coverage from 70% to 100%

**Next Step:** Proceed to IMPLEMENTATION_STEPS.md for detailed code and commands.

---

**Document Version:** 1.0
**Last Updated:** 2025-11-18
**Author:** Law Search System Team
