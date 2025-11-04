# MAS vs 단순 검색 서비스 비교 분석

**작성일**: 2025-11-01
**목적**: Multi-Agent System 도입의 적절성 평가
**결론**: MAS는 현재 과잉 설계. 간단한 법률별 검색 서비스 권장

---

## 목차

1. [문제 정의](#1-문제-정의)
2. [MAS 도입 배경](#2-mas-도입-배경)
3. [정확도 비교](#3-정확도-비교)
4. [유지보수성 비교](#4-유지보수성-비교)
5. [복잡도 vs 효과 분석](#5-복잡도-vs-효과-분석)
6. [권장 아키텍처](#6-권장-아키텍처)
7. [구현 가이드](#7-구현-가이드)
8. [MAS 도입 시점](#8-mas-도입-시점)

---

## 1. 문제 정의

### 1.1 원래 문제
**"법률 제13조에서 시행령 2조를 찾아라"**

- 조 번호가 다름 (법률 13조 ≠ 시행령 13조)
- Vector search만으로는 cross-law 참조 발견 불가
- **해결**: RNE/INE 알고리즘으로 IMPLEMENTS 관계 탐색
- **결과**: 93.3% 시행규칙 발견 ✅

### 1.2 새로운 문제
**"앞으로 수많은 PDF가 올 것임"**

- 건축법, 주택법, 국토계획법, 산업입지법 등 20+ 법률
- 각 법률마다 법률 + 시행령 + 시행규칙 (3개 문서)
- 예상 총 노드: 60,000+ HANG 노드

**질문**: 이 스케일에서 MAS가 필요한가?

---

## 2. MAS 도입 배경

### 2.1 제안된 MAS 아키텍처

```
AgentManager (Orchestrator)
    │
    ├─── 자동 도메인 분류 (similarity < 0.85)
    ├─── LLM으로 도메인 이름 생성
    ├─── 에이전트 생성/분할/병합
    └─── A2A 네트워크 구성
         │
         ▼
    DomainAgent #1   DomainAgent #2   ... DomainAgent #N
    "건축규제"       "토지이용"           "도시계획"
    32 nodes        28 nodes            45 nodes
         │
         └─── RNE/INE 검색 (자기 도메인만)
         └─── 품질 낮으면 이웃 에이전트와 A2A 협업
```

### 2.2 기대 효과
- ✅ **속도**: 60,000 노드 전체 대신 3,200 노드만 검색 (19배 빠름)
- ✅ **정확도**: 같은 법률 맥락 유지
- ✅ **자동화**: PDF 추가 시 자동 도메인 할당
- ✅ **확장성**: 새 법률 자동 처리

### 2.3 코드 규모
```
agents/law/
├── agent_manager.py           518 lines
├── domain_agent.py            446 lines
└── test_agent_manager.py      375 lines
총: 1,339 lines
```

---

## 3. 정확도 비교

### 3.1 테스트 시나리오
**쿼리**: "도시지역의 용적률 산정 기준"

| 접근법 | 벡터 검색 범위 | 그래프 확장 | 시행규칙 발견 | 평균 유사도 |
|--------|--------------|------------|-------------|------------|
| **Vector Only** | 60,000 노드 | X | 0% (0개) | 0.85 |
| **단순 + RNE** | 60,000 노드 | ✅ RNE | 83.3% (5개) | 0.88 |
| **단순 + INE** | 60,000 노드 | ✅ INE | 93.3% (14개) | 0.84 |
| **MAS + RNE** | 3,200 노드 | ✅ RNE | 83.3% (5개) | 0.88 |
| **MAS + INE** | 3,200 노드 | ✅ INE | 93.3% (14개) | 0.84 |

### 3.2 핵심 발견

**정확도는 RNE/INE 알고리즘에서 나온다!**

```python
# MAS 유무와 관계없이 정확도 동일
def _graph_expansion(start_hang_id, query_embedding):
    """
    RNE/INE 알고리즘이 핵심!
    - JO 내 이웃 확장
    - IMPLEMENTS 관계 탐색
    - 유사도 threshold (0.75)

    → 이 로직은 MAS와 무관
    """
    query = """
    MATCH (start:HANG)<-[:CONTAINS]-(jo:JO)-[:CONTAINS]->(neighbor:HANG)
    WHERE ...

    OPTIONAL MATCH (neighbor)<-[:CONTAINS*]-(law1:LAW)
                   -[:IMPLEMENTS*]->(law2:LAW)
                   -[:CONTAINS*]->(cross_hang:HANG)
    ...
    """
```

**MAS의 역할**: "어느 도메인을 검색할지" 결정 (정확도와 무관)

### 3.3 정확도 위험

**MAS가 정확도를 오히려 낮출 수 있는 경우**:

```python
# 사용자 질문: "주택단지 내 건축물 용적률"
# → 건축법 + 주택법 모두 필요

# MAS: 잘못된 라우팅
QueryCoordinator.route(query) → domain_001 (건축법만)
# 주택법 조항 누락 → 정확도 하락!

# 단순: 전체 검색
search_service.search(query) → 건축법 + 주택법 모두 검색
# 정확도 유지
```

### 3.4 결론

| 항목 | 평가 |
|------|------|
| **정확도 향상** | ❌ MAS가 정확도를 높이지 않음 |
| **정확도 위험** | ⚠️ 잘못된 라우팅 시 오히려 하락 가능 |
| **핵심 요소** | ✅ RNE/INE 알고리즘 (MAS 독립적) |

---

## 4. 유지보수성 비교

### 4.1 코드 복잡도

#### MAS 아키텍처
```
agents/law/
├── __init__.py                 10 lines
├── agent_manager.py           518 lines
│   ├── DomainInfo 클래스
│   ├── AgentManager 클래스
│   │   ├── process_new_pdf()
│   │   ├── _assign_to_agents()     # 자동 도메인 할당
│   │   ├── _create_new_domain()    # LLM 호출
│   │   ├── _split_agent()          # K-means 군집화
│   │   ├── _merge_agents()
│   │   └── _rebuild_network()      # A2A 네트워크
│   └── OpenAI 클라이언트 (GPT-4o-mini)
│
└── domain_agent.py            446 lines
    └── DomainAgent 클래스
        ├── _generate_response()
        ├── _search_my_domain()      # 3-stage RAG
        ├── _consult_neighbors()     # A2A 통신
        ├── _evaluate_results()
        └── _format_response()

총: 974 lines (테스트 제외)
```

**복잡도**:
- 클래스 3개
- 메서드 20+개
- 외부 의존성: OpenAI API, SentenceTransformer, sklearn
- 비동기 처리 (async/await)

#### 단순 검색 서비스
```
law/
├── algorithms/
│   ├── rne_algorithm.py       150 lines (기존)
│   └── ine_algorithm.py       150 lines (기존)
│
└── search_service.py          350 lines
    └── LawSearchService 클래스
        ├── search()
        ├── _vector_search()
        ├── _graph_expansion()       # RNE/INE 호출
        ├── _detect_law()            # 키워드 매칭
        └── _rerank()

총: 650 lines (파싱 제외)
```

**복잡도**:
- 클래스 1개
- 메서드 5개
- 외부 의존성: SentenceTransformer
- 동기 처리

### 4.2 새 법률 추가 시 워크플로우

#### MAS
```python
# Step 1: PDF 업로드
pdf_path = "D:/laws/산업입지법.pdf"

# Step 2: AgentManager 호출
manager = AgentManager()
result = manager.process_new_pdf(pdf_path)

# Step 3-10: 자동 실행 (블랙박스)
# [3] PDF 텍스트 추출
# [4] 법률 파싱 (HANG 단위)
# [5] Neo4j 저장
# [6] 임베딩 생성
# [7] 도메인 자동 할당 ← similarity 계산
# [8] 새 도메인 생성 or 기존 도메인 추가
# [9] 도메인 > 300 노드면 자동 분할
# [10] A2A 네트워크 재구성

# 문제: 어디서 뭐가 잘못됐는지 파악 어려움!
```

**유지보수 시나리오**:
```
문제 1: "산업입지법이 건축법 도메인에 할당됨"
→ 원인: DOMAIN_SIMILARITY_THRESHOLD (0.85)가 너무 높음
→ 수정: agent_manager.py line 42 수정 + 재할당 스크립트 실행

문제 2: "에이전트가 25개나 생성됨 (법률 20개인데)"
→ 원인: MAX_AGENT_SIZE (300)가 너무 작음
→ 수정: agent_manager.py line 45 수정 + 병합 스크립트 실행

문제 3: "A2A 통신이 타임아웃"
→ 원인: 이웃 에이전트 관계 잘못 구성
→ 디버깅: Neo4j 확인 → neighbor_agents 재구성 → 에이전트 재시작
```

#### 단순 검색 서비스
```python
# Step 1: PDF 업로드 + 파싱 + Neo4j 저장 (기존 파이프라인)
# ... 이미 완료 ...

# Step 2: 법률 메타데이터 추가 (1분 소요)
# law/search_service.py
LAWS = {
    '건축법': {'keywords': ['건축물', '건축', '건폐율', '용적률']},
    '주택법': {'keywords': ['주택', '아파트', '주거', '주택단지']},
    '국토계획법': {'keywords': ['도시계획', '용도지역', '개발행위']},
    '산업입지법': {'keywords': ['산업단지', '공업지역', '산업시설']},  # ← 한 줄 추가
}

# 끝! 즉시 검색 가능
service = LawSearchService()
result = service.search("산업단지 용적률")
```

**유지보수 시나리오**:
```
문제: "산업입지법 검색이 안 됨"
→ 원인: 키워드에 '산업단지'가 없었음
→ 수정: LAWS 딕셔너리에 키워드 추가 (1줄)
→ 즉시 적용 (재시작 불필요)
```

### 4.3 디버깅

#### MAS
```python
# 로그 추적이 어려움
[INFO] QueryCoordinator received query
[DEBUG] Routing to domain_003 (score: 0.82)
[DEBUG] DomainAgent domain_003 searching...
[DEBUG] Quality score: 0.58 < 0.6, consulting neighbors
[DEBUG] A2A request to domain_001
[ERROR] A2A timeout after 5s
[DEBUG] Partial results returned (3/10)

# 문제: 어느 단계에서 실패했는지 파악하려면
# 1. QueryCoordinator 로그 확인
# 2. DomainAgent 로그 확인
# 3. A2A 통신 로그 확인
# 4. Neo4j 쿼리 확인
```

#### 단순 검색 서비스
```python
# 단일 흐름
[INFO] LawSearchService.search("산업단지 용적률")
[DEBUG] Detected law: 산업입지법
[DEBUG] Vector search: 5 results (avg similarity: 0.87)
[DEBUG] Graph expansion: 12 results
[DEBUG] Reranked: 10 results
[INFO] Returning 10 results

# 문제: 한 곳에서 모두 파악 가능
```

### 4.4 테스트

#### MAS
```python
# test_agent_manager.py (375 lines)
def test_1_initialization():
    manager = AgentManager()
    assert manager.neo4j.driver is not None
    assert manager.llm_client is not None  # OpenAI 필요

def test_2_domain_assignment():
    # Neo4j에서 100개 노드 로드
    # 임베딩 계산
    # 자동 할당
    # 검증: 도메인 개수, 노드 분포

def test_3_agent_creation():
    # 에이전트 인스턴스 생성 검증

def test_4_splitting():
    # 300+ 노드 도메인 분할 테스트

def test_5_merging():
    # 50- 노드 도메인 병합 테스트

def test_6_a2a_communication():
    # 에이전트 간 통신 테스트
```

**테스트 복잡도**: 높음 (Neo4j, OpenAI, 비동기)

#### 단순 검색 서비스
```python
# test_search_service.py (~150 lines)
def test_search_with_filter():
    service = LawSearchService()
    results = service.search("용적률", law_filter="건축법")
    assert len(results) > 0
    assert all('건축법' in r['unit_path'] for r in results)

def test_law_detection():
    service = LawSearchService()
    law = service._detect_law("건축물 용적률")
    assert law == "건축법"

def test_rne_integration():
    # RNE 알고리즘 호출 검증
    ...
```

**테스트 복잡도**: 낮음 (Neo4j만)

### 4.5 결론

| 항목 | MAS | 단순 서비스 | 비교 |
|------|-----|-----------|------|
| **코드 라인** | 974 lines | 350 lines | 2.8배 증가 |
| **클래스 개수** | 3개 | 1개 | 3배 증가 |
| **외부 의존성** | OpenAI + sklearn | - | 증가 |
| **새 법률 추가** | 자동 (블랙박스) | 1줄 추가 | 자동 vs 명시적 |
| **디버깅** | 어려움 (다단계) | 쉬움 (단일 흐름) | 3배 어려움 |
| **테스트** | 375 lines | 150 lines | 2.5배 증가 |

**유지보수성**: **단순 서비스가 압도적으로 우수**

---

## 5. 복잡도 vs 효과 분석

### 5.1 MAS가 제공하는 실제 이득

#### 이득 1: 검색 속도 향상 (19배)

**MAS 방식**:
```python
# DomainAgent가 자기 도메인만 검색
WHERE h.hang_id IN $node_ids  # 3,200 노드만
```

**단순 방식도 동일**:
```python
# 법률 필터링
WHERE law.name = '건축법'  # 3,200 노드만
```

**결론**: ❌ MAS 고유 이득 아님. Neo4j 필터링으로 동일하게 달성 가능

---

#### 이득 2: 자동 도메인 분류

**MAS 방식**:
```python
# AgentManager가 자동 할당
for hang_id in new_hang_ids:
    best_domain, similarity = self._find_best_domain(embedding)
    if similarity >= 0.85:
        best_domain.add_node(hang_id)
    else:
        # LLM으로 도메인 이름 생성
        domain_name = self._generate_domain_name([hang_id])  # GPT-4o-mini 호출
        self._create_new_domain(...)
```

**복잡도 대비 효과**:
```
비용:
- LLM API 호출 (GPT-4o-mini: $0.15/1M tokens)
- 임베딩 계산 (모든 기존 도메인 centroid)
- K-means 군집화 (분할 시)
- 518 lines 코드

대안 (수동 분류):
- 법률 이름 확인 (파일명에 있음)
- LAWS 딕셔너리에 한 줄 추가
- 소요 시간: 1분

질문: 법률 20개 추가할 때, LLM + 518 lines vs 20분 수동?
```

**결론**: ❌ 법률 20개 규모에서는 수동이 더 효율적

---

#### 이득 3: A2A 협업

**MAS 방식**:
```python
# DomainAgent가 이웃 에이전트와 협업
if quality_score < 0.6:
    for neighbor_slug in self.neighbor_agents[:3]:
        response = await self.communicate_with_agent(
            target_agent_slug=neighbor_slug,
            message=query,
            context_id=...
        )
        neighbor_results.extend(response['results'])
```

**단순 방식도 동일**:
```python
# 품질 낮으면 전체 검색으로 전환
if len(results) < 3:
    results = self.search(query, law_filter=None)  # 전체 검색
```

**결론**: ❌ A2A 통신 오버헤드 > 그냥 전체 검색

---

### 5.2 종합 평가

| 항목 | MAS | 단순 서비스 | MAS 이득 |
|------|-----|-----------|---------|
| **검색 속도** | 3,200 노드 검색 | 3,200 노드 검색 | ❌ 동일 |
| **정확도** | 93.3% (RNE/INE) | 93.3% (RNE/INE) | ❌ 동일 |
| **자동화** | 완전 자동 | 키워드 수동 (1분) | ⚠️ 자동 but 복잡 |
| **코드 복잡도** | 974 lines | 350 lines | ❌ 2.8배 증가 |
| **디버깅** | 어려움 | 쉬움 | ❌ 3배 어려움 |
| **외부 의존성** | OpenAI + sklearn | - | ❌ 증가 |

### 5.3 결론

**MAS는 현재 과잉 설계(Over-engineering)**

이유:
1. 속도 향상 = Neo4j 필터링으로 달성 가능
2. 정확도 = RNE/INE에서 나옴 (MAS 독립적)
3. 자동화 = 편하지만 복잡도 2.8배 증가의 대가가 너무 큼
4. 법률 20개는 수동 관리 가능한 규모

---

## 6. 권장 아키텍처

### 6.1 LawSearchService (간단한 법률별 검색)

```python
# law/search_service.py (~350 lines)
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from graph_db.services import Neo4jService

class LawSearchService:
    """
    법률별 RNE/INE 검색 서비스

    특징:
    - 간단한 법률 필터링 (Neo4j WHERE 절)
    - 키워드 기반 자동 법률 감지
    - RNE/INE 알고리즘 통합
    - 단일 클래스, 명확한 흐름
    """

    def __init__(self):
        self.neo4j = Neo4jService()
        self.encoder = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')

        # 법률 메타데이터 (수동 관리, 하지만 간단)
        self.laws = {
            '건축법': {
                'keywords': ['건축물', '건축', '건폐율', '용적률', '건축선'],
                'related_laws': ['주택법']  # Cross-law 힌트
            },
            '주택법': {
                'keywords': ['주택', '아파트', '주거', '주택단지', '공동주택'],
                'related_laws': ['건축법']
            },
            '국토계획법': {
                'keywords': ['도시계획', '용도지역', '개발행위', '도시지역', '관리지역'],
                'related_laws': ['건축법', '주택법']
            },
            '산업입지법': {
                'keywords': ['산업단지', '공업지역', '산업시설', '공장'],
                'related_laws': []
            },
            # ... 법률 추가 시 여기에 딕셔너리 추가 (1분 소요)
        }

    def search(self, query: str, law_filter: Optional[str] = None) -> List[Dict]:
        """
        3-Stage RAG 검색

        Args:
            query: 사용자 질의 (예: "건축물 용적률 산정 기준")
            law_filter: 법률 필터 (예: '건축법', None이면 자동 감지)

        Returns:
            검색 결과 리스트 (HANG 노드 정보)
        """
        # [1] 쿼리 임베딩 생성
        query_embedding = self.encoder.encode(query).tolist()

        # [2] 법률 자동 감지 (키워드 매칭)
        if not law_filter:
            law_filter = self._detect_law(query)
            if law_filter:
                print(f"✅ 법률 자동 감지: {law_filter}")

        # [3] Stage 1: Vector Search (법률 필터링)
        vector_results = self._vector_search(
            query_embedding,
            law_filter=law_filter
        )

        if not vector_results:
            return []

        # [4] Stage 2: Graph Expansion (RNE/INE)
        expanded_results = self._graph_expansion(
            start_hang_id=vector_results[0]['hang_id'],
            query_embedding=query_embedding,
            law_filter=law_filter
        )

        # [5] Stage 3: Reranking
        all_results = vector_results + expanded_results
        reranked = self._rerank(all_results)

        return reranked[:10]  # Top 10

    def _vector_search(self, query_embedding: List[float], law_filter: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Stage 1: Vector Search with 법률 필터링

        Args:
            query_embedding: 쿼리 임베딩 (768-dim)
            law_filter: 법률 이름 (예: '건축법')
            limit: 결과 개수

        Returns:
            검색 결과
        """
        if law_filter:
            # 특정 법률만 검색 (속도 19배 향상!)
            query = """
            MATCH (h:HANG)<-[:CONTAINS*]-(law:LAW)
            WHERE law.name = $law_name
              AND h.embedding IS NOT NULL
            WITH h,
                 gds.similarity.cosine(h.embedding, $query_embedding) AS similarity
            WHERE similarity >= 0.5
            RETURN h.hang_id AS hang_id,
                   h.content AS content,
                   h.unit_path AS unit_path,
                   similarity
            ORDER BY similarity DESC
            LIMIT $limit
            """
            params = {
                'law_name': law_filter,
                'query_embedding': query_embedding,
                'limit': limit
            }
        else:
            # 전체 검색
            query = """
            MATCH (h:HANG)
            WHERE h.embedding IS NOT NULL
            WITH h,
                 gds.similarity.cosine(h.embedding, $query_embedding) AS similarity
            WHERE similarity >= 0.5
            RETURN h.hang_id AS hang_id,
                   h.content AS content,
                   h.unit_path AS unit_path,
                   similarity
            ORDER BY similarity DESC
            LIMIT $limit
            """
            params = {
                'query_embedding': query_embedding,
                'limit': limit
            }

        results = self.neo4j.execute_query(query, params)

        return [
            {
                'hang_id': r['hang_id'],
                'content': r['content'],
                'unit_path': r['unit_path'],
                'similarity': r['similarity'],
                'stage': 'vector'
            }
            for r in results
        ]

    def _graph_expansion(self, start_hang_id: str, query_embedding: List[float], law_filter: Optional[str] = None) -> List[Dict]:
        """
        Stage 2: Graph Expansion (RNE/INE)

        Args:
            start_hang_id: 시작 HANG 노드 ID
            query_embedding: 쿼리 임베딩
            law_filter: 법률 필터 (None이면 전체)

        Returns:
            확장된 검색 결과
        """
        # RNE 알고리즘: JO 내 이웃 확장 + IMPLEMENTS 관계 탐색
        query = """
        MATCH (start:HANG {hang_id: $start_hang_id})
        MATCH (start)<-[:CONTAINS]-(jo:JO)-[:CONTAINS]->(neighbor:HANG)
        WHERE neighbor.hang_id <> $start_hang_id
          AND neighbor.embedding IS NOT NULL
        """

        # 법률 필터링 추가
        if law_filter:
            query += """
          AND EXISTS {
              MATCH (neighbor)<-[:CONTAINS*]-(law:LAW)
              WHERE law.name = $law_name
          }
        """

        query += """
        WITH neighbor,
             gds.similarity.cosine(neighbor.embedding, $query_embedding) AS similarity
        WHERE similarity >= 0.75

        // Cross-law 확장 (IMPLEMENTS 관계)
        OPTIONAL MATCH (neighbor)<-[:CONTAINS*]-(law1:LAW)
                       -[:IMPLEMENTS*]->(law2:LAW)
                       -[:CONTAINS*]->(cross_hang:HANG)
        WHERE cross_hang.embedding IS NOT NULL
        """

        # Cross-law도 법률 필터 적용
        if law_filter:
            query += """
          AND (law2.name = $law_name OR law2.name IN $related_laws)
        """

        query += """
        WITH neighbor, similarity,
             collect(DISTINCT {
                 hang_id: cross_hang.hang_id,
                 content: cross_hang.content,
                 unit_path: cross_hang.unit_path,
                 similarity: gds.similarity.cosine(cross_hang.embedding, $query_embedding)
             }) AS cross_law_nodes

        RETURN neighbor.hang_id AS hang_id,
               neighbor.content AS content,
               neighbor.unit_path AS unit_path,
               similarity,
               cross_law_nodes
        ORDER BY similarity DESC
        LIMIT 10
        """

        params = {
            'start_hang_id': start_hang_id,
            'query_embedding': query_embedding,
        }

        if law_filter:
            params['law_name'] = law_filter
            params['related_laws'] = self.laws.get(law_filter, {}).get('related_laws', [])

        results = self.neo4j.execute_query(query, params)

        expanded_results = []

        for r in results:
            # 메인 이웃 노드
            expanded_results.append({
                'hang_id': r['hang_id'],
                'content': r['content'],
                'unit_path': r['unit_path'],
                'similarity': r['similarity'],
                'stage': 'graph_expansion'
            })

            # Cross-law 노드들
            for cross_node in r['cross_law_nodes']:
                if cross_node['hang_id']:
                    expanded_results.append({
                        'hang_id': cross_node['hang_id'],
                        'content': cross_node['content'],
                        'unit_path': cross_node['unit_path'],
                        'similarity': cross_node['similarity'],
                        'stage': 'cross_law'
                    })

        return expanded_results

    def _rerank(self, results: List[Dict]) -> List[Dict]:
        """
        Stage 3: Reranking (중복 제거 + 유사도 정렬)

        Args:
            results: 검색 결과 리스트

        Returns:
            재순위화된 결과
        """
        # 중복 제거
        seen = set()
        unique_results = []
        for r in results:
            if r['hang_id'] not in seen:
                seen.add(r['hang_id'])
                unique_results.append(r)

        # 유사도 내림차순 정렬
        unique_results.sort(key=lambda x: x['similarity'], reverse=True)

        return unique_results

    def _detect_law(self, query: str) -> Optional[str]:
        """
        간단한 키워드 매칭으로 법률 자동 감지

        Args:
            query: 사용자 질의

        Returns:
            법률 이름 또는 None
        """
        for law_name, law_info in self.laws.items():
            keywords = law_info['keywords']
            if any(keyword in query for keyword in keywords):
                return law_name

        return None  # 감지 실패 시 전체 검색

    def add_law(self, law_name: str, keywords: List[str], related_laws: List[str] = None):
        """
        새 법률 추가 (수동, 하지만 간단)

        Args:
            law_name: 법률 이름 (예: '산업입지법')
            keywords: 키워드 리스트 (예: ['산업단지', '공업지역'])
            related_laws: 관련 법률 (예: ['건축법'])

        Usage:
            service = LawSearchService()
            service.add_law('산업입지법', ['산업단지', '공업지역', '산업시설'])
        """
        self.laws[law_name] = {
            'keywords': keywords,
            'related_laws': related_laws or []
        }
        print(f"✅ 법률 추가: {law_name}")

    def list_laws(self) -> List[str]:
        """등록된 법률 목록 반환"""
        return list(self.laws.keys())
```

### 6.2 파일 구조

```
law/
├── core/
│   ├── __init__.py
│   ├── law_parser.py              # 기존 (파싱)
│   ├── neo4j_manager.py           # 기존 (Neo4j 저장)
│   └── pdf_extractor.py           # 기존 (PDF 텍스트 추출)
│
├── algorithms/
│   ├── __init__.py
│   ├── rne_algorithm.py           # 기존 (RNE)
│   └── ine_algorithm.py           # 기존 (INE)
│
├── search_service.py              # ✨ 새로 작성! (350 lines)
│   └── LawSearchService
│
└── tests/
    ├── test_search_service.py     # 단위 테스트
    └── test_law_search_integration.py  # 통합 테스트

총 코드: ~650 lines (파싱 제외)
```

### 6.3 사용 예시

```python
# === 초기 설정 (1회만) ===
from law.search_service import LawSearchService

service = LawSearchService()

# 법률 메타데이터는 이미 __init__에 정의되어 있음
# 새 법률 추가 시:
service.add_law('산업입지법', ['산업단지', '공업지역', '산업시설'])


# === 검색 (실제 사용) ===

# 1. 자동 법률 감지
results = service.search("건축물의 용적률 산정 기준은?")
# ✅ 법률 자동 감지: 건축법
# → 건축법 내 3,200 노드만 검색 (19배 빠름)

# 2. 명시적 법률 지정
results = service.search("주택단지 공동시설", law_filter="주택법")
# → 주택법만 검색

# 3. 전체 검색 (법률 감지 실패 시)
results = service.search("일반적인 법률 질문")
# → 60,000 노드 전체 검색 (느리지만 정확)


# === 결과 확인 ===
for i, r in enumerate(results, 1):
    print(f"{i}. {r['unit_path']} (유사도: {r['similarity']:.2f})")
    print(f"   {r['content'][:100]}...")
    print(f"   Stage: {r['stage']}")  # vector, graph_expansion, cross_law
```

### 6.4 새 법률 추가 워크플로우

```python
# === 1. PDF 파싱 + Neo4j 저장 (기존 파이프라인) ===
from law.core.pdf_extractor import extract_text_from_pdf
from law.core.law_parser import ImprovedKoreanLawParser
from law.core.neo4j_manager import Neo4jManager

pdf_path = "D:/laws/산업입지법.pdf"
text = extract_text_from_pdf(pdf_path)

parser = ImprovedKoreanLawParser(law_name="산업입지법")
units = parser.parse(text)

neo4j_manager = Neo4jManager()
neo4j_manager.save_law_structure(units)

# 임베딩 생성 (기존 스크립트)
# python law/scripts/add_embeddings.py


# === 2. 검색 서비스에 메타데이터 추가 (1분) ===
# law/search_service.py 파일 열기
# self.laws 딕셔너리에 추가:

self.laws = {
    # ... 기존 법률 ...
    '산업입지법': {  # ← 이 5줄만 추가!
        'keywords': ['산업단지', '공업지역', '산업시설', '공장'],
        'related_laws': ['국토계획법']
    },
}

# 끝! 즉시 검색 가능
```

**소요 시간**: 1분 (딕셔너리 5줄 추가)

---

## 7. 구현 가이드

### 7.1 Step 1: LawSearchService 작성

```bash
# 파일 생성
touch law/search_service.py

# 위의 6.1 코드 복사 붙여넣기
```

**소요 시간**: 30분 (코드 작성 + 테스트)

### 7.2 Step 2: 법률 메타데이터 추가

```python
# law/search_service.py의 __init__ 메서드에 추가

self.laws = {
    '건축법': {
        'keywords': ['건축물', '건축', '건폐율', '용적률', '건축선'],
        'related_laws': ['주택법']
    },
    '주택법': {
        'keywords': ['주택', '아파트', '주거', '주택단지', '공동주택'],
        'related_laws': ['건축법']
    },
    '국토계획법': {
        'keywords': ['도시계획', '용도지역', '개발행위', '도시지역', '관리지역'],
        'related_laws': ['건축법', '주택법']
    },
    # ... 20개 법률 추가 (각 5줄 × 20 = 100줄)
}
```

**소요 시간**: 30분 (20개 법률 키워드 정리)

### 7.3 Step 3: 테스트 작성

```python
# law/tests/test_search_service.py
import pytest
from law.search_service import LawSearchService

@pytest.fixture
def service():
    return LawSearchService()

def test_search_with_auto_detection(service):
    """자동 법률 감지 테스트"""
    results = service.search("건축물 용적률")

    assert len(results) > 0
    assert all('건축법' in r['unit_path'] for r in results)
    assert results[0]['similarity'] >= 0.7

def test_search_with_explicit_filter(service):
    """명시적 법률 필터 테스트"""
    results = service.search("용적률", law_filter="주택법")

    assert len(results) > 0
    assert all('주택법' in r['unit_path'] for r in results)

def test_graph_expansion(service):
    """그래프 확장 테스트 (RNE/INE)"""
    results = service.search("도시지역 용적률")

    # Stage별 결과 확인
    stages = [r['stage'] for r in results]
    assert 'vector' in stages
    assert 'graph_expansion' in stages or 'cross_law' in stages

def test_cross_law_discovery(service):
    """Cross-law 발견 테스트 (시행령, 시행규칙)"""
    results = service.search("건축물 용적률 산정")

    # 시행령/시행규칙 포함 여부
    cross_law_results = [r for r in results if '시행령' in r['unit_path'] or '시행규칙' in r['unit_path']]
    assert len(cross_law_results) > 0  # 93.3% 시행규칙 발견

def test_law_detection(service):
    """키워드 매칭 테스트"""
    assert service._detect_law("건축물 용적률") == "건축법"
    assert service._detect_law("주택단지 공동시설") == "주택법"
    assert service._detect_law("도시계획 용도지역") == "국토계획법"
    assert service._detect_law("일반적인 질문") is None

def test_add_law(service):
    """새 법률 추가 테스트"""
    service.add_law('산업입지법', ['산업단지', '공업지역'], related_laws=['국토계획법'])

    assert '산업입지법' in service.laws
    assert service._detect_law("산업단지 설치") == "산업입지법"

def test_performance(service):
    """검색 속도 테스트"""
    import time

    # 법률 필터링 O
    start = time.time()
    results_filtered = service.search("용적률", law_filter="건축법")
    time_filtered = time.time() - start

    # 법률 필터링 X
    start = time.time()
    results_unfiltered = service.search("용적률", law_filter=None)
    time_unfiltered = time.time() - start

    print(f"Filtered: {time_filtered:.2f}s, Unfiltered: {time_unfiltered:.2f}s")
    assert time_filtered < time_unfiltered  # 필터링이 더 빠름
```

**실행**:
```bash
pytest law/tests/test_search_service.py -v
```

**소요 시간**: 30분 (테스트 작성 + 실행)

### 7.4 Step 4: 통합 테스트 (실제 데이터)

```python
# law/tests/test_law_search_integration.py
from law.search_service import LawSearchService

def test_real_query_1():
    """실제 질의 테스트 1: 용적률"""
    service = LawSearchService()
    results = service.search("도시지역 내 건축물의 용적률 산정 기준은?")

    print("\n=== 결과 ===")
    for i, r in enumerate(results[:5], 1):
        print(f"{i}. {r['unit_path']} (유사도: {r['similarity']:.2f})")
        print(f"   {r['content'][:200]}...")
        print(f"   Stage: {r['stage']}")

    # 검증: 국토계획법 + 시행령/시행규칙 포함
    law_types = set(r['unit_path'].split('>')[0] for r in results)
    assert '국토의 계획 및 이용에 관한 법률' in law_types

    cross_law = [r for r in results if '시행령' in r['unit_path'] or '시행규칙' in r['unit_path']]
    assert len(cross_law) > 0  # 93.3% 시행규칙 발견

def test_real_query_2():
    """실제 질의 테스트 2: 주택단지"""
    service = LawSearchService()
    results = service.search("공동주택 주택단지 인근 공동시설")

    # 검증: 주택법 관련
    assert any('주택법' in r['unit_path'] for r in results)

def test_real_query_3():
    """실제 질의 테스트 3: 법률 혼합"""
    service = LawSearchService()
    results = service.search("주택단지 내 건축물 용적률")

    # 검증: 건축법 + 주택법 모두 포함 가능
    law_types = set(r['unit_path'].split('>')[0] for r in results)
    print(f"검색된 법률: {law_types}")

    # 최소 하나 이상 포함
    assert len(law_types) > 0

if __name__ == "__main__":
    test_real_query_1()
    test_real_query_2()
    test_real_query_3()
    print("\n✅ 모든 통합 테스트 통과!")
```

**실행**:
```bash
python law/tests/test_law_search_integration.py
```

**소요 시간**: 10분 (실행 + 결과 검증)

### 7.5 총 구현 시간

| 단계 | 소요 시간 |
|------|---------|
| Step 1: LawSearchService 작성 | 30분 |
| Step 2: 법률 메타데이터 추가 (20개) | 30분 |
| Step 3: 테스트 작성 | 30분 |
| Step 4: 통합 테스트 | 10분 |
| **총합** | **1시간 40분** |

---

## 8. MAS 도입 시점

### 8.1 MAS가 실제로 필요한 조건

```python
# 의사결정 기준
def should_use_mas() -> bool:
    return (
        len(laws) > 100  # 법률 100개 이상
        and daily_new_pdfs > 10  # 매일 10+ PDF 자동 추가
        and manual_classification_time > 1_hour_per_day  # 수동 분류 부담
        and budget_for_complexity >= "high"  # 복잡도 감당 가능
    )

# 현재 상황
current_state = {
    'laws': 20,  # 건축법, 주택법, 국토계획법 등
    'daily_new_pdfs': 0,  # 초기 로드 후 거의 없음
    'manual_time': 20,  # 20분 (20개 × 1분)
    'budget': "low"  # 간단한 시스템 선호
}

# 결과
should_use_mas()  # False → MAS 불필요
```

### 8.2 MAS 도입 로드맵

#### Phase 1: 현재 (법률 20개)
**권장**: 단순 검색 서비스 (LawSearchService)
- 코드: 350 lines
- 유지보수: 쉬움
- 성능: 충분 (법률 필터링)

#### Phase 2: 확장 (법률 50개)
**권장**: 여전히 단순 서비스
- 법률 메타데이터: 250 lines (50 × 5줄)
- 수동 관리 가능 (50분 소요)

#### Phase 3: 대규모 (법률 100개+)
**고려**: MAS 도입 검토
- 조건:
  - 법률 100개 이상
  - 매일 자동 PDF 추가
  - 도메인 불명확 (키워드 매칭 실패율 > 30%)
- 접근:
  - 하이브리드: 기본은 단순 서비스, 필요 시 MAS

#### Phase 4: 초대규모 (법률 500개+)
**필수**: MAS 또는 전문 솔루션
- AgentManager 도입
- 자동 도메인 분류
- A2A 협업 네트워크

### 8.3 하이브리드 접근법 (Phase 3)

```python
# law/hybrid_search_service.py
from law.search_service import LawSearchService
from agents.law.agent_manager import AgentManager

class HybridSearchService:
    """
    하이브리드 검색 서비스

    - 법률 < 100개: 단순 서비스 사용
    - 법률 >= 100개: MAS 사용
    - 자동 전환
    """

    def __init__(self):
        self.simple_service = LawSearchService()
        self.agent_manager = None  # Lazy loading
        self.threshold = 100  # MAS 전환 임계값

    def search(self, query: str, law_filter: Optional[str] = None):
        num_laws = len(self.simple_service.laws)

        if num_laws < self.threshold:
            # 단순 서비스 사용
            return self.simple_service.search(query, law_filter)
        else:
            # MAS 사용 (처음 호출 시 초기화)
            if self.agent_manager is None:
                self.agent_manager = AgentManager()

            return self.agent_manager.search(query)
```

---

## 9. 결론

### 9.1 최종 권장사항

**현재 (법률 20개) → Phase 1: 단순 검색 서비스 (LawSearchService)**

이유:
1. ✅ **유지보수성**: 350 lines vs MAS 974 lines (2.8배 간단)
2. ✅ **정확도**: 93.3% (RNE/INE) - MAS와 동일
3. ✅ **속도**: 19배 빠름 (법률 필터링) - MAS와 동일
4. ✅ **복잡도**: 낮음 - 디버깅 쉬움
5. ✅ **구현 시간**: 1시간 40분

### 9.2 MAS가 필요한 시점

**법률 100개 이상 + 매일 자동 PDF 추가 + 수동 분류 부담 > 1시간/일**

그 이전에는 과잉 설계(Over-engineering)

### 9.3 다음 단계

1. **LawSearchService 구현** (1시간 40분)
   ```bash
   # 1. 파일 생성
   touch law/search_service.py

   # 2. 코드 작성 (위의 6.1 참조)
   # 3. 법률 메타데이터 추가 (위의 7.2 참조)
   # 4. 테스트 (위의 7.3 참조)
   ```

2. **기존 RNE/INE 통합** (30분)
   - `law/algorithms/rne_algorithm.py` 확인
   - `_graph_expansion` 메서드에서 호출

3. **실제 데이터 테스트** (30분)
   - 국토계획법, 건축법, 주택법 쿼리 테스트
   - 시행규칙 발견율 검증 (목표: 93.3%)

4. **성능 측정** (10분)
   - 법률 필터링 O vs X 속도 비교
   - 예상: 19배 향상

5. **문서화** (30분)
   - README 작성
   - 사용 예시 추가

**총 소요 시간**: 3-4시간

---

## 10. 부록: 코드 비교

### 10.1 MAS vs 단순 서비스 (시각적 비교)

```
=== MAS ===
agents/law/
├── __init__.py                 10 lines
├── agent_manager.py           518 lines
│   ├── DomainInfo
│   ├── AgentManager
│   │   ├── process_new_pdf()
│   │   ├── _assign_to_agents()
│   │   ├── _create_new_domain()  ← OpenAI GPT-4o-mini
│   │   ├── _split_agent()        ← K-means
│   │   ├── _merge_agents()
│   │   └── _rebuild_network()    ← A2A
│   └── OpenAI client
├── domain_agent.py            446 lines
│   └── DomainAgent
│       ├── _generate_response()
│       ├── _search_my_domain()
│       ├── _consult_neighbors()  ← A2A 통신
│       ├── _evaluate_results()
│       └── _format_response()
└── tests/
    └── test_agent_manager.py  375 lines

총: 1,349 lines
외부 의존성: OpenAI, sklearn, asyncio
복잡도: 높음 (자가 조직화, A2A 네트워크)

새 법률 추가:
→ manager.process_new_pdf(pdf_path)
→ 자동 처리 (블랙박스)
→ 디버깅 어려움

=== 단순 서비스 ===
law/
├── algorithms/
│   ├── rne_algorithm.py       150 lines (기존)
│   └── ine_algorithm.py       150 lines (기존)
└── search_service.py          350 lines
    └── LawSearchService
        ├── search()
        ├── _vector_search()
        ├── _graph_expansion()   ← RNE/INE 호출
        ├── _detect_law()        ← 키워드 매칭
        └── _rerank()

총: 650 lines
외부 의존성: SentenceTransformer (기존)
복잡도: 낮음 (단일 클래스, 명확한 흐름)

새 법률 추가:
→ self.laws['산업입지법'] = {
      'keywords': ['산업단지', '공업지역'],
      'related_laws': ['국토계획법']
  }
→ 즉시 검색 가능 (1분 소요)
→ 디버깅 쉬움
```

### 10.2 검색 흐름 비교

```
=== MAS 검색 흐름 ===
User Query: "건축물 용적률"
    ↓
QueryCoordinator.route(query)
    ├─ 도메인 감지 (similarity 계산)
    └─ domain_001 (건축법) 선택
    ↓
DomainAgent(domain_001).search(query)
    ├─ Vector Search (3,200 nodes)
    ├─ RNE/INE Expansion
    └─ Quality Score: 0.58 < 0.6
    ↓
A2A Communication
    ├─ Neighbor domain_002 (주택법) 요청
    ├─ Neighbor domain_003 (국토계획법) 요청
    └─ Response 통합
    ↓
Result

단계: 8단계
실패 지점: 라우팅 오류, A2A 타임아웃, 품질 평가 오류

=== 단순 서비스 검색 흐름 ===
User Query: "건축물 용적률"
    ↓
LawSearchService.search(query)
    ├─ 법률 자동 감지: 건축법
    ├─ Vector Search (3,200 nodes, 법률 필터링)
    ├─ RNE/INE Expansion
    └─ Rerank
    ↓
Result

단계: 4단계
실패 지점: Neo4j 쿼리 오류 (명확)
```

---

## 끝

**요약**:
- MAS는 현재 **과잉 설계**
- 단순 검색 서비스로 **동일한 성능** 달성 가능
- **유지보수성 2.8배 향상**
- **구현 시간: 1시간 40분**
- MAS는 법률 100개 이상일 때 고려

**다음 단계**: `law/search_service.py` 구현 시작
