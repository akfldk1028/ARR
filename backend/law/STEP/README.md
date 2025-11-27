# 법률 시스템 순차적 실행 가이드

이 폴더는 법률 Neo4j 시스템을 처음부터 구축하기 위한 순차적 실행 스크립트를 포함합니다.

---

## 전체 프로세스

```
PDF 파일 → JSON 변환 → Neo4j 로드 → HANG 임베딩 → Domain 초기화 → 관계 임베딩 → 완료
```

---

## 순차 실행 단계

### Step 0: 사전 준비

**필수 요구사항:**
- Neo4j Desktop 실행 중 (http://localhost:7474)
- Python 가상환경 활성화 (`.venv`)
- 환경변수 설정 (`.env` 파일)
  - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
  - `OPENAI_API_KEY`

**데이터 확인:**
```bash
# PDF 파일 확인
ls law/data/raw/*.pdf

# 필요 시 parsed 폴더 생성
mkdir -p law/data/parsed
```

---

### Step 1: PDF → JSON 변환

**스크립트:** `step1_pdf_to_json.py`

**기능:**
- PDF 법률 문서 파싱
- 계층 구조 추출: LAW → JANG → JEOL → JO → HANG → HO
- 표준 JSON 포맷 생성

**실행:**
```bash
cd law/STEP
python step1_pdf_to_json.py
```

**출력:** `law/data/parsed/*.json` (3개 파일: 법률, 시행령, 시행규칙)

**검증:**
```bash
ls -lh law/data/parsed/*.json
```

---

### Step 2: JSON → Neo4j 로드

**스크립트:** `step2_json_to_neo4j.py`

**기능:**
- JSON 데이터를 Neo4j 그래프로 변환
- 3가지 관계 생성:
  - `CONTAINS`: 계층 관계 (부모 → 자식)
  - `NEXT`: 순차 관계 (형제간)
  - `CITES`: 참조 관계 (법률간)

**실행:**
```bash
python step2_json_to_neo4j.py
```

**검증 (Neo4j Browser):**
```cypher
// 전체 노드 수
MATCH (n) RETURN count(n) as total_nodes

// 노드 타입별 분포
MATCH (n)
RETURN labels(n)[0] as node_type, count(n) as count
ORDER BY count DESC

// HANG 노드 수 (주요 컨텐츠)
MATCH (h:HANG) RETURN count(h) as hang_count
```

**예상 결과:**
- LAW: 3개
- JANG: ~24개
- JO: ~200개
- HANG: ~1,477개
- HO: ~수백개

---

### Step 3: HANG 노드 임베딩 추가

**스크립트:** `step3_add_hang_embeddings.py`

**기능:**
- KR-SBERT 모델 사용 (jhgan/ko-sbert-sts)
- 768차원 임베딩 생성
- 벡터 인덱스 생성 (`hang_embedding_index`)

**실행:**
```bash
python step3_add_hang_embeddings.py
```

**처리 시간:** ~5-10분 (1,477개 노드)

**검증:**
```cypher
// 임베딩이 있는 HANG 노드 수
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
RETURN count(h) as embedded_count

// 벡터 인덱스 확인
SHOW INDEXES
```

**예상 결과:**
- 임베딩 노드: 1,477개 (100%)
- 인덱스: `hang_embedding_index` (VECTOR)

---

### Step 4: Domain 노드 초기화 ⭐ 필수!

**스크립트:** `step4_initialize_domains.py`

**기능:**
- K-means 클러스터링 (HANG 임베딩 기반)
- 최적 k 값 자동 선택 (Silhouette Score)
- LLM으로 도메인 이름 생성
- DomainAgent 인스턴스 생성
- Neo4j에 Domain 노드 + BELONGS_TO_DOMAIN 관계 생성

**실행:**
```bash
python step4_initialize_domains.py
```

**검증:**
```cypher
// Domain 노드 수
MATCH (d:Domain) RETURN count(d) as domain_count

// 도메인별 HANG 노드 수
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
RETURN d.domain_name, count(h) as node_count
ORDER BY node_count DESC

// BELONGS_TO_DOMAIN 관계 수
MATCH ()-[r:BELONGS_TO_DOMAIN]->()
RETURN count(r) as relation_count
```

**예상 결과:**
- Domain 노드: 5개
- BELONGS_TO_DOMAIN 관계: 1,477개 (모든 HANG 노드 할당)
- 도메인별 분포: 121~510개 노드

---

### Step 5: CONTAINS 관계 임베딩 추가

**스크립트:** `step5_add_relationship_embeddings/`

**기능:**
- CONTAINS 관계에 의미 기반 임베딩 추가
- OpenAI text-embedding-3-large (3,072차원)
- 관계 벡터 인덱스 생성 (`contains_embedding`)

**실행:**
```bash
cd step5_add_relationship_embeddings

# 전체 프로세스 실행
python step1_analyze_relationships.py
python step2_extract_contexts.py
python step3_generate_embeddings.py
python step4_update_neo4j.py
python step5_create_index_and_test.py

cd ..
```

**또는 간편 실행:**
```bash
python step5_run_relationship_embedding.py
```

**검증:**
```cypher
// 임베딩이 있는 CONTAINS 관계 수
MATCH ()-[r:CONTAINS]->()
WHERE r.embedding IS NOT NULL
RETURN count(r) as embedded_relations

// 관계 벡터 인덱스 확인
SHOW INDEXES
```

**예상 결과:**
- 임베딩 관계: 3,565개
- 인덱스: `contains_embedding` (VECTOR, HNSW)

---

## 전체 자동 실행

**모든 단계를 한 번에 실행:**
```bash
python run_all.py
```

⚠️ **주의:**
- 전체 실행 시간: 약 30-60분
- 충분한 메모리 필요 (8GB 이상 권장)
- OpenAI API 비용 발생 (관계 임베딩)

---

## 최종 검증

**전체 시스템 상태 확인:**
```bash
python verify_system.py
```

**Neo4j 쿼리:**
```cypher
// 전체 통계
MATCH (n)
WITH labels(n)[0] as node_type, count(n) as count
RETURN node_type, count
ORDER BY count DESC

// 관계 통계
MATCH ()-[r]->()
WITH type(r) as rel_type, count(r) as count
RETURN rel_type, count
ORDER BY count DESC

// 임베딩 상태
MATCH (h:HANG)
WITH count(h) as total,
     sum(CASE WHEN h.embedding IS NOT NULL THEN 1 ELSE 0 END) as embedded
RETURN total, embedded,
       embedded * 100.0 / total as embedding_percentage

// Domain 분포
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
WITH d.domain_name as domain, count(h) as size
RETURN domain, size,
       size * 100.0 / 1477 as percentage
ORDER BY size DESC
```

**예상 최종 통계:**
- 전체 노드: 3,872개
- 전체 관계: 7,500개
- HANG 임베딩: 1,477개 (100%)
- CONTAINS 관계 임베딩: 3,565개 (100%)
- Domain 노드: 5개
- BELONGS_TO_DOMAIN 관계: 1,477개 (100%)

---

## 스크립트 설명

| 파일 | 기능 | 소요 시간 |
|------|------|----------|
| `step1_pdf_to_json.py` | PDF 파싱 → JSON | ~1분 |
| `step2_json_to_neo4j.py` | JSON → Neo4j 로드 | ~2분 |
| `step3_add_hang_embeddings.py` | HANG 임베딩 생성 | ~10분 |
| `step4_initialize_domains.py` | Domain 클러스터링 | ~5분 |
| `step5_run_relationship_embedding.py` | 관계 임베딩 (전체) | ~30분 |
| `run_all.py` | 전체 자동 실행 | ~50분 |
| `verify_system.py` | 시스템 검증 | ~1분 |

---

## 문제 해결

### 1. Neo4j 연결 실패
```bash
# Neo4j 상태 확인
# Neo4j Desktop에서 데이터베이스 시작 버튼 클릭

# 환경 변수 확인
echo $NEO4J_URI
echo $NEO4J_USER
```

### 2. 메모리 부족 (OOM)
```python
# step3_add_hang_embeddings.py에서 배치 크기 조정
batch_size = 32  # → 16으로 줄이기
```

### 3. OpenAI API 오류
```bash
# API 키 확인
echo $OPENAI_API_KEY

# Rate limit 오류 시 대기 시간 증가
# step5/step3_generate_embeddings.py 수정
```

### 4. Domain 노드 생성 실패
```bash
# Step 3 완료 후 실행했는지 확인
# HANG 노드에 임베딩이 있어야 클러스터링 가능

# 재실행
python step4_initialize_domains.py
```

---

## 참고 문서

- **전체 시스템 가이드**: `law/SYSTEM_GUIDE.md`
- **완전 설정 가이드**: `docs/2025-11-13-LAW_NEO4J_COMPLETE_SETUP_GUIDE.md`
- **관계 임베딩**: `law/relationship_embedding/README.md`
- **Neo4j 스키마**: `law/docs/neo4j_schema.md`

---

## 다음 단계

시스템 구축 완료 후:

1. **검색 테스트**
```python
from agents.law.agent_manager import AgentManager
manager = AgentManager()

# 질의 예시
result = manager.search("도시계획시설의 설치 기준은?")
```

2. **DomainAgent 개별 테스트**
```python
from agents.law.domain_agent import DomainAgent
agent = manager.get_domain_agent("domain_id")
result = await agent.search("특정 도메인 질의")
```

3. **A2A 협업 테스트**
```python
# 품질 점수 < 0.6 시 자동으로 다른 도메인 에이전트 협업
result = manager.search_with_collaboration("복합적인 법률 질의")
```

---

**마지막 업데이트:** 2025-11-13
**작성자:** Claude AI (순차적 실행 가이드)
