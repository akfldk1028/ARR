# Neo4j 스케일링 가이드

> **작성일**: 2025-10-26
> **목적**: 법률 데이터베이스가 대규모로 확장될 때를 대비한 Neo4j 스케일업 전략

---

## 목차

1. [현황 분석](#1-현황-분석)
2. [Neo4j 스케일링 조사 결과](#2-neo4j-스케일링-조사-결과)
3. [한국 법령 규모](#3-한국-법령-규모)
4. [스케일업 방법](#4-스케일업-방법)
5. [단계별 스케일업 전략](#5-단계별-스케일업-전략)
6. [모니터링 및 최적화](#6-모니터링-및-최적화)
7. [FAQ](#7-faq)

---

## 1. 현황 분석

### 1.1 현재 시스템 상태

```
- 노드 수: 3,976개
- 법률 수: 3개 (법률 1개, 시행령 1개, 시행규칙 1개)
- 데이터베이스 크기: ~100MB
- RAM 사용: 기본 설정
- Edition: Neo4j Community Edition
```

### 1.2 예상 확장 규모

한국 법령 전체 규모 (2025년 9월 기준):
- **법률**: 1,683개
- **대통령령 (시행령)**: 1,954개
- **부령 (시행규칙)**: 1,408개
- **전체**: 약 5,045개

법률 1개당 평균 노드: ~1,325개 (현재 3,976 ÷ 3)

---

## 2. Neo4j 스케일링 조사 결과

### 2.1 노드 수 제한 - 하나의 인스턴스에 담을 수 있는가?

✅ **결론: 가능합니다!**

**기술적 제한:**
- **Neo4j 3.0 이전**: 34억 (2^35) 노드 제한
- **Neo4j 3.0 이후 (현재)**: **제한 없음** (quadrillion = 10^15 노드까지 가능)
- **실제 사례**: 수십억~수백억 노드를 하나의 인스턴스에서 운영 중

**우리 현황:**
```
현재: 약 4,000개 노드
법률 100개 추가 시: 약 133,000개 노드
법률 1,000개 추가 시: 약 1,325,000개 노드
전체 한국 법령 (5,045개): 약 6,684,625개 노드

→ 하나의 인스턴스로 충분함!
```

### 2.2 쿼리만 적게 하면 데이터 많아도 상관없나?

⚠️ **반은 맞고 반은 틀림**

**맞는 부분:**
- Neo4j 공식: _"Query time is primarily about how much of the graph needs to be touched; **the size of the graph matters very little**"_
- 인덱스가 있으면 10억 개 노드 중 1개 찾는 것도 빠름
- 노드 개수보다 **순회하는 관계 개수**가 성능에 더 큰 영향

**틀린 부분:**
- RAM이 부족하면 느려짐 (디스크 I/O 발생)
- 많은 관계를 순회하는 쿼리는 느려짐
- 인덱스 없이 전체 스캔하면 느림

**핵심:** 데이터 크기보다 **쿼리 패턴**과 **RAM**이 중요!

### 2.3 Community Edition vs Enterprise Edition

현재 Community Edition 사용 중이라면:

| 항목 | Community Edition | Enterprise Edition |
|------|------------------|-------------------|
| **노드 수 제한** | 34억 (충분함) | 무제한 |
| **CPU 코어** | 4코어 제한 (GDS) | 무제한 |
| **클러스터링** | ❌ 불가 | ✅ 가능 |
| **속도** | 기본 | 50-100% 더 빠름 |
| **백업** | 수동 | 자동 |
| **가격** | 무료 | 유료 |

**우리 프로젝트**: Community Edition으로 충분! (클러스터 필요 없음)

### 2.4 RAM 요구사항

#### Neo4j 공식 가이드 예시

**75M 노드 시스템** (5대 클러스터, 인스턴스당 15M 노드):
```
RAM: 100GB per instance
  - OS: 5GB
  - Page Cache (data + indexes): 60GB
  - Heap: 30GB

CPU: 40 cores per instance (200 queries/sec 처리)
```

#### 우리 프로젝트 예상

**법률 1,000개** (약 132만 노드):
```
RAM: 10-20GB 정도면 충분
  - OS: 2GB
  - Page Cache: 5-10GB
  - Heap: 5GB

CPU: 4-8 cores
```

**전체 한국 법령** (약 668만 노드):
```
RAM: 32-64GB 권장
  - OS: 2GB
  - Page Cache: 20-40GB
  - Heap: 10-20GB

CPU: 8-16 cores
```

### 2.5 언제 스케일아웃(sharding) 필요한가?

#### 필요한 경우:
- ✅ 노드가 **수억~수십억 개 이상**
- ✅ 쿼리가 **초당 수천 개 이상**
- ✅ 지역별로 데이터 분산 필요
- ✅ 고가용성(HA) 필요 (24/7 서비스)

#### 불필요한 경우 (우리):
- ❌ 노드 수백만~수천만 개 (단일 인스턴스로 충분)
- ❌ 쿼리 초당 수십~수백 개
- ❌ 단일 서버로 운영
- ❌ 개발/연구 목적

### 2.6 현재 우리 시스템 분석

#### 법률 추가 시나리오

| 법률 수 | 예상 노드 수 | RAM 필요량 | CPU 코어 | 단일 인스턴스 | 비고 |
|---------|-------------|-----------|---------|-------------|------|
| **10개** | 13,250 | 4GB | 2 cores | ✅ 가능 | 개발 환경 |
| **100개** | 132,500 | 8GB | 4 cores | ✅ 가능 | 테스트 환경 |
| **1,000개** | 1,325,000 | 16GB | 8 cores | ✅ 가능 | 중규모 운영 |
| **5,045개** (전체) | 6,684,625 | 32-64GB | 8-16 cores | ✅ 가능 | 대규모 운영 |
| **10,000개** | 13,250,000 | 64GB | 16 cores | ✅ 가능 | 확장 시나리오 |
| **100,000개** | 132,500,000 | 256GB | 32+ cores | ⚠️ 고려 필요 | 극한 시나리오 |

**결론:**
- ✅ **한국 법령 전체 (약 5,045개)를 넣어도 하나의 인스턴스로 충분!**
- ✅ 쿼리 성능은 데이터 크기보다 **인덱스**와 **쿼리 패턴**이 중요
- ✅ RAM만 충분하면 문제없음 (32-64GB 권장)

---

## 3. 한국 법령 규모

### 3.1 법제처 통계 (2025년 9월 2일 기준)

#### 중앙법령

| 구분 | 개수 |
|------|------|
| 헌법 | 1개 |
| 법률 | 1,683개 |
| 대통령령 (시행령) | 1,954개 |
| 총리령 | 29개 |
| 부령 (시행규칙) | 1,408개 |
| **소계** | **5,075개** |

#### 자치법규
- 조례: 108,279개
- 규칙: 46,258개
- **소계**: 154,537개

#### 전체 현행 법령
- **총 160,038건**

### 3.2 우리 프로젝트 대상

우리가 구축하는 시스템은 **중앙법령**을 대상으로 합니다:

```
대상 법령: 약 5,045개 (법률 + 시행령 + 시행규칙)
예상 노드: 약 670만 개
예상 관계: 약 1,000만 개
예상 DB 크기: 10-20GB
```

**참고**: 자치법규까지 포함하면 160,000개 이상이지만, 자치법규는 별도 시스템으로 관리하는 것이 일반적입니다.

---

## 4. 스케일업 방법

### 4.1 메모리 설정

#### 4.1.1 메모리 구성 요소

Neo4j는 3가지 주요 메모리 영역을 사용합니다:

```
┌─────────────────────────────────────┐
│         총 서버 RAM (예: 64GB)         │
├─────────────────────────────────────┤
│  OS & System (2-5GB)                 │  ← 운영체제
├─────────────────────────────────────┤
│  Page Cache (40GB)                   │  ← 그래프 데이터 캐싱
├─────────────────────────────────────┤
│  JVM Heap (20GB)                     │  ← 쿼리 실행, 객체
├─────────────────────────────────────┤
│  Other (여유 공간)                    │
└─────────────────────────────────────┘
```

**1. Page Cache**
- **용도**: 디스크에 있는 Neo4j 데이터(노드, 관계, 속성)를 메모리에 캐싱
- **중요도**: ⭐⭐⭐⭐⭐ (가장 중요!)
- **공식**: `데이터베이스 크기 × 1.2` (20% 성장 여유)
- **설정 파라미터**: `server.memory.pagecache.size`

**2. JVM Heap**
- **용도**: 쿼리 실행, 트랜잭션 처리, Java 객체
- **중요도**: ⭐⭐⭐⭐
- **공식**: 일반적으로 Page Cache의 30-50%
- **설정 파라미터**:
  - `server.memory.heap.initial_size`
  - `server.memory.heap.max_size`

**3. OS 메모리**
- **용도**: 운영체제, 파일 시스템
- **권장**: 1-5GB

#### 4.1.2 메모리 설정 방법

**Step 1: 현재 데이터베이스 크기 확인**

```bash
# Neo4j 데이터 디렉토리 크기 확인
du -sh /path/to/neo4j/data/databases/neo4j
```

또는 Neo4j Browser에서:
```cypher
CALL dbms.queryJmx("org.neo4j:instance=kernel#0,name=Store file sizes")
YIELD attributes
RETURN attributes.TotalStoreSize.value as storeSizeBytes
```

**Step 2: 메모리 추천 받기**

```bash
bin/neo4j-admin server memory-recommendation --memory=64g
```

출력 예시:
```
# Recommended initial memory settings:
server.memory.heap.initial_size=20g
server.memory.heap.max_size=20g
server.memory.pagecache.size=40g
```

**Step 3: neo4j.conf 수정**

파일 위치: `/path/to/neo4j/conf/neo4j.conf`

```properties
# Page Cache 설정 (데이터베이스 크기의 1.2배 권장)
server.memory.pagecache.size=40g

# Heap 설정 (initial과 max를 동일하게 설정 권장)
server.memory.heap.initial_size=20g
server.memory.heap.max_size=20g

# 트랜잭션 메모리 제한 (선택사항)
dbms.memory.transaction.total.max=10g
```

**Step 4: Neo4j 재시작**

```bash
neo4j restart
```

#### 4.1.3 메모리 설정 가이드라인

| 데이터베이스 크기 | 총 RAM | Page Cache | Heap | OS |
|----------------|--------|-----------|------|-----|
| 1GB | 8GB | 5GB | 2GB | 1GB |
| 10GB | 32GB | 20GB | 10GB | 2GB |
| 50GB | 128GB | 80GB | 40GB | 8GB |
| 100GB | 256GB | 160GB | 80GB | 16GB |

**우리 프로젝트 권장 설정:**

```properties
# 법률 1,000개 (약 5GB 데이터)
server.memory.pagecache.size=8g
server.memory.heap.initial_size=4g
server.memory.heap.max_size=4g
# 총 RAM: 16GB

# 전체 한국 법령 (약 20GB 데이터)
server.memory.pagecache.size=30g
server.memory.heap.initial_size=15g
server.memory.heap.max_size=15g
# 총 RAM: 64GB
```

### 4.2 인덱스 최적화

#### 4.2.1 인덱스 종류

Neo4j는 4가지 인덱스 타입을 제공합니다:

**1. Range Index (기본)**
- **용도**: 일반적인 속성 검색, 범위 쿼리
- **지원**: 모든 데이터 타입
- **생성**:
```cypher
CREATE INDEX law_name_idx FOR (n:LAW) ON (n.name)
```

**2. Text Index**
- **용도**: 접미사, 부분 문자열 검색
- **생성**:
```cypher
CREATE TEXT INDEX jo_content_text_idx FOR (n:JO) ON (n.content)
```

**3. Full-text Index**
- **용도**: 전문 검색 (한국어 형태소 분석 가능)
- **생성**:
```cypher
CREATE FULLTEXT INDEX law_fulltext_idx
FOR (n:LAW|JO|HANG)
ON EACH [n.title, n.content]
```

**4. Vector Index** (Neo4j 5.11+)
- **용도**: 임베딩 벡터 유사도 검색
- **생성**:
```cypher
CREATE VECTOR INDEX chunk_embedding_idx
FOR (n:Chunk) ON (n.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
}}
```

#### 4.2.2 우리 프로젝트 권장 인덱스

현재 `core/neo4j_manager.py`에 이미 구현되어 있습니다:

```python
single_indexes = [
    # LAW 노드
    "CREATE INDEX law_name_idx IF NOT EXISTS FOR (n:LAW) ON (n.name)",
    "CREATE INDEX law_agent_id_idx IF NOT EXISTS FOR (n:LAW) ON (n.agent_id)",
    "CREATE INDEX law_base_name_idx IF NOT EXISTS FOR (n:LAW) ON (n.base_law_name)",

    # JO 노드 (조항)
    "CREATE INDEX jo_full_id_idx IF NOT EXISTS FOR (n:JO) ON (n.full_id)",
    "CREATE INDEX jo_agent_id_idx IF NOT EXISTS FOR (n:JO) ON (n.agent_id)",
    "CREATE INDEX jo_base_name_idx IF NOT EXISTS FOR (n:JO) ON (n.base_law_name)",

    # 기타 단위 노드
    "CREATE INDEX hang_agent_id_idx IF NOT EXISTS FOR (n:HANG) ON (n.agent_id)",
    "CREATE INDEX ho_agent_id_idx IF NOT EXISTS FOR (n:HO) ON (n.agent_id)",
    "CREATE INDEX mok_agent_id_idx IF NOT EXISTS FOR (n:MOK) ON (n.agent_id)",
]
```

**추가 권장 인덱스** (Phase 3에서 구현):

```cypher
-- 전문 검색을 위한 Full-text 인덱스
CREATE FULLTEXT INDEX law_content_fulltext_idx
FOR (n:LAW|JO|HANG|HO)
ON EACH [n.title, n.content]

-- 위임 관계 검색을 위한 인덱스
CREATE INDEX jo_delegation_idx IF NOT EXISTS
FOR (n:JO) ON (n.has_delegation)

-- 벡터 인덱스 (Phase 3)
CREATE VECTOR INDEX chunk_embedding_idx
FOR (n:Chunk) ON (n.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
}}
```

#### 4.2.3 인덱스 성능 트레이드오프

**쓰기 성능 영향:**

| 인덱스 개수 | 쓰기 성능 저하 |
|----------|-------------|
| 1-3개 | 5-10% |
| 4-10개 | 10-20% |
| 10개 이상 | 20-40% |

**저장 공간 증가:**

| 인덱스 타입 | 공간 증가 |
|----------|---------|
| Range Index | 노드 크기의 5-15% |
| Composite Index | 노드 크기의 10-20% |
| Full-text Index | 인덱싱된 텍스트의 30-100% |

**우리 프로젝트**: 쓰기보다 **읽기(검색)가 압도적으로 많으므로** 인덱스 많이 사용해도 OK!

#### 4.2.4 인덱스 모니터링

```cypher
-- 모든 인덱스 확인
SHOW INDEXES

-- 인덱스 사용 통계
CALL db.stats.retrieve('INDEXES')

-- 쿼리가 인덱스를 사용하는지 확인
EXPLAIN MATCH (n:LAW {name: '국토계획법'}) RETURN n

-- 실제 실행 계획 확인 (실행 시간 포함)
PROFILE MATCH (n:LAW {name: '국토계획법'}) RETURN n
```

### 4.3 쿼리 최적화

#### 4.3.1 쿼리 최적화 원칙

**1. 조기 필터링 (Early Filtering)**

❌ 나쁜 예:
```cypher
MATCH (law:LAW)-[:CONTAINS]->(jo:JO)
WHERE jo.title CONTAINS '목적'
RETURN jo
```

✅ 좋은 예:
```cypher
MATCH (law:LAW {base_law_name: '국토계획법'})-[:CONTAINS]->(jo:JO)
WHERE jo.title CONTAINS '목적'
RETURN jo
```

**2. 인덱스 활용**

❌ 나쁜 예:
```cypher
MATCH (jo:JO)
WHERE jo.full_id = '국토계획법::제1조'
RETURN jo
```

✅ 좋은 예 (인덱스 있을 때):
```cypher
MATCH (jo:JO {full_id: '국토계획법::제1조'})
RETURN jo
```

**3. 관계 방향 명시**

❌ 나쁜 예:
```cypher
MATCH (law:LAW)--(jo:JO)  // 양방향 검색
RETURN jo
```

✅ 좋은 예:
```cypher
MATCH (law:LAW)-[:CONTAINS]->(jo:JO)  // 단방향 검색
RETURN jo
```

**4. LIMIT 사용**

```cypher
-- 대량 데이터 확인 시 반드시 LIMIT 사용
MATCH (n:JO)
RETURN n
LIMIT 100
```

**5. WITH를 이용한 파이프라이닝**

```cypher
MATCH (law:LAW {base_law_name: '국토계획법'})
WITH law
MATCH (law)-[:CONTAINS]->(jo:JO)
WHERE jo.has_delegation = true
RETURN jo
```

#### 4.3.2 쿼리 성능 분석

**EXPLAIN vs PROFILE**

```cypher
-- 실행 계획만 확인 (실제 실행 안 함)
EXPLAIN
MATCH (jo:JO {agent_id: 'agent_국토계획법'})
WHERE jo.has_delegation = true
RETURN jo

-- 실제 실행하고 성능 측정
PROFILE
MATCH (jo:JO {agent_id: 'agent_국토계획법'})
WHERE jo.has_delegation = true
RETURN jo
```

**주목할 지표:**
- `db hits`: 낮을수록 좋음
- `Rows`: 각 단계에서 처리된 행 수
- `EstimatedRows` vs `Rows`: 차이가 크면 통계 업데이트 필요
- `Index Seek` vs `Node By Label Scan`: Index Seek가 나와야 함

#### 4.3.3 자주 사용하는 쿼리 패턴

**1. Agent별 법률 검색**
```cypher
MATCH (law:LAW {agent_id: $agent_id})
RETURN law.name, law.law_category
ORDER BY
  CASE law.law_category
    WHEN '법률' THEN 1
    WHEN '시행령' THEN 2
    WHEN '시행규칙' THEN 3
  END
```

**2. 위임 조항 검색**
```cypher
MATCH (jo:JO)
WHERE jo.agent_id = $agent_id
  AND jo.has_delegation = true
  AND jo.delegation_type = '시행령'
RETURN jo.full_id, jo.title, jo.delegation_pattern
LIMIT 20
```

**3. 계층 구조 순회**
```cypher
MATCH path = (law:LAW {name: $law_name})-[:CONTAINS*]->(jo:JO {unit_number: $jo_number})
RETURN path
```

**4. 법률 간 관계 확인**
```cypher
MATCH (law:LAW {law_category: '법률', base_law_name: $base_law_name})-[r:ENFORCED_BY]->(decree:LAW)
RETURN law.name, decree.name, r.scope
```

### 4.4 디스크 최적화

#### 4.4.1 SSD 사용 권장

- **HDD**: 순차 읽기 100-200 MB/s, 랜덤 읽기 1-2 MB/s
- **SSD**: 순차 읽기 500-3500 MB/s, 랜덤 읽기 300-3000 MB/s

Neo4j는 랜덤 읽기가 많으므로 **SSD 사용 시 10-100배 빠름**

#### 4.4.2 파일 시스템

**Linux**: ext4 또는 XFS 권장
**Windows**: NTFS
**macOS**: APFS

#### 4.4.3 데이터베이스 위치 분리 (선택사항)

```
/data1 (SSD) - 그래프 데이터
/data2 (HDD) - 트랜잭션 로그, 백업
```

---

## 5. 단계별 스케일업 전략

### Stage 1: 개발 환경 (법률 10-100개)

```yaml
목표:
  - 법률: 10-100개
  - 노드: ~132,500개
  - 목적: 개발 및 테스트

하드웨어:
  - RAM: 8GB
  - CPU: 4 cores
  - 디스크: 100GB (HDD도 가능)

Neo4j 설정:
  server.memory.pagecache.size: 4g
  server.memory.heap.initial_size: 2g
  server.memory.heap.max_size: 2g

조치사항:
  ✅ 기본 인덱스 생성 (이미 완료)
  ✅ 쿼리 로깅 활성화
  ⬜ 백업 스크립트 작성
```

### Stage 2: 테스트 환경 (법률 100-1,000개)

```yaml
목표:
  - 법률: 100-1,000개
  - 노드: ~1,325,000개
  - 목적: 성능 테스트, 통합 테스트

하드웨어:
  - RAM: 16GB
  - CPU: 8 cores
  - 디스크: 200GB SSD

Neo4j 설정:
  server.memory.pagecache.size: 10g
  server.memory.heap.initial_size: 4g
  server.memory.heap.max_size: 4g

조치사항:
  ✅ 전체 인덱스 최적화
  ✅ Full-text 인덱스 추가
  ⬜ 쿼리 성능 모니터링 시작
  ⬜ 자동 백업 설정
```

### Stage 3: 운영 환경 (전체 법령 5,000개)

```yaml
목표:
  - 법률: 5,045개 (전체 한국 중앙법령)
  - 노드: ~6,684,625개
  - 목적: 실 서비스 운영

하드웨어:
  - RAM: 64GB (128GB 권장)
  - CPU: 16 cores
  - 디스크: 500GB SSD (1TB 권장)

Neo4j 설정:
  server.memory.pagecache.size: 40g
  server.memory.heap.initial_size: 20g
  server.memory.heap.max_size: 20g

  # 추가 최적화
  dbms.memory.transaction.total.max: 10g
  db.tx_state.memory_allocation: ON_HEAP

조치사항:
  ✅ Vector 인덱스 추가 (Phase 3)
  ⬜ 24/7 모니터링 시스템 구축
  ⬜ 일일 자동 백업
  ⬜ 쿼리 성능 대시보드
  ⬜ 장애 대응 매뉴얼 작성
```

### Stage 4: 확장 시나리오 (법령 10,000개 이상)

```yaml
목표:
  - 법률: 10,000개+ (자치법규 포함 시)
  - 노드: 13,250,000개+
  - 목적: 극한 확장 대비

하드웨어:
  - RAM: 128-256GB
  - CPU: 32+ cores
  - 디스크: 1-2TB NVMe SSD

Neo4j 설정:
  server.memory.pagecache.size: 100g
  server.memory.heap.initial_size: 40g
  server.memory.heap.max_size: 40g

조치사항:
  ⬜ Neo4j Enterprise Edition 고려
  ⬜ 클러스터링 (Causal Clustering) 검토
  ⬜ Fabric/Composite Database로 샤딩
  ⬜ 읽기 전용 레플리카 추가
```

### 단계별 마이그레이션 체크리스트

#### Phase 1 → Phase 2 마이그레이션

```bash
# 1. 현재 데이터베이스 백업
neo4j-admin database dump neo4j --to-path=/backup/stage1

# 2. 메모리 설정 업데이트 (neo4j.conf)
server.memory.pagecache.size=10g
server.memory.heap.max_size=4g

# 3. 인덱스 추가
CREATE FULLTEXT INDEX law_content_fulltext_idx ...

# 4. 재시작 및 검증
neo4j restart
```

#### Phase 2 → Phase 3 마이그레이션

```bash
# 1. 백업
neo4j-admin database dump neo4j --to-path=/backup/stage2

# 2. 하드웨어 업그레이드 (RAM 64GB, SSD)

# 3. 메모리 설정 업데이트
server.memory.pagecache.size=40g
server.memory.heap.max_size=20g

# 4. 벡터 인덱스 추가 (Phase 3)
CREATE VECTOR INDEX chunk_embedding_idx ...

# 5. 모니터링 도구 설치
# - Prometheus + Grafana
# - Neo4j Ops Manager (Enterprise)

# 6. 재시작 및 성능 테스트
neo4j restart
```

---

## 6. 모니터링 및 최적화

### 6.1 내장 모니터링 도구

#### 6.1.1 Neo4j Browser

**메모리 사용량 확인:**
```cypher
CALL dbms.queryJmx("org.neo4j:instance=kernel#0,name=Memory Pool")
YIELD attributes
RETURN attributes
```

**데이터베이스 크기 확인:**
```cypher
CALL dbms.queryJmx("org.neo4j:instance=kernel#0,name=Store file sizes")
YIELD attributes
RETURN attributes.TotalStoreSize.value as storeSizeBytes
```

**인덱스 상태 확인:**
```cypher
SHOW INDEXES
```

**느린 쿼리 확인:**
```cypher
CALL dbms.listQueries()
YIELD queryId, query, elapsedTimeMillis, status
WHERE elapsedTimeMillis > 1000
RETURN queryId, query, elapsedTimeMillis
ORDER BY elapsedTimeMillis DESC
```

#### 6.1.2 쿼리 로그

**neo4j.conf 설정:**
```properties
# 쿼리 로깅 활성화
db.logs.query.enabled=true

# 1초 이상 걸리는 쿼리만 로깅
db.logs.query.threshold=1s

# 로그 파일 위치
db.logs.query.path=logs/query.log
```

**로그 분석:**
```bash
# 가장 느린 쿼리 찾기
grep "elapsed" logs/query.log | sort -k5 -n -r | head -10

# 특정 라벨 관련 쿼리 찾기
grep "LAW" logs/query.log
```

### 6.2 외부 모니터링 도구

#### 6.2.1 Prometheus + Grafana

**Neo4j Prometheus Exporter 설치:**
```bash
# neo4j.conf에 추가
metrics.enabled=true
metrics.prometheus.enabled=true
metrics.prometheus.endpoint=localhost:2004
```

**Prometheus 설정 (prometheus.yml):**
```yaml
scrape_configs:
  - job_name: 'neo4j'
    static_configs:
      - targets: ['localhost:2004']
```

**주요 메트릭:**
- `neo4j_page_cache_hit_ratio`: Page Cache 적중률 (95% 이상 목표)
- `neo4j_database_store_size_bytes`: DB 크기
- `neo4j_pool_total_used`: 메모리 풀 사용량
- `neo4j_transaction_active_read`: 활성 읽기 트랜잭션 수

#### 6.2.2 Python 스크립트를 이용한 모니터링

```python
# scripts/monitor_neo4j.py
from neo4j import GraphDatabase
import time

def monitor():
    driver = GraphDatabase.driver("bolt://localhost:7687",
                                   auth=("neo4j", "password"))

    with driver.session() as session:
        # 메모리 사용량
        result = session.run("""
            CALL dbms.queryJmx("java.lang:type=Memory")
            YIELD attributes
            RETURN attributes.HeapMemoryUsage.value.used as heapUsed,
                   attributes.HeapMemoryUsage.value.max as heapMax
        """)
        record = result.single()
        heap_usage = record['heapUsed'] / record['heapMax'] * 100
        print(f"Heap Usage: {heap_usage:.2f}%")

        # 활성 쿼리
        result = session.run("CALL dbms.listQueries()")
        active_queries = len(list(result))
        print(f"Active Queries: {active_queries}")

        # 노드/관계 수
        result = session.run("""
            MATCH (n) RETURN count(n) as nodeCount
        """)
        node_count = result.single()['nodeCount']
        print(f"Total Nodes: {node_count:,}")

    driver.close()

if __name__ == "__main__":
    while True:
        monitor()
        time.sleep(60)  # 1분마다 모니터링
```

### 6.3 성능 문제 진단 및 해결

#### 문제 1: 쿼리가 느림

**증상:**
```cypher
MATCH (jo:JO)
WHERE jo.content CONTAINS '허가'
RETURN jo
-- 실행 시간: 10초+
```

**진단:**
```cypher
PROFILE MATCH (jo:JO)
WHERE jo.content CONTAINS '허가'
RETURN jo
-- db hits: 10,000,000+ → 전체 스캔!
```

**해결:**
```cypher
-- Full-text 인덱스 생성
CREATE FULLTEXT INDEX jo_content_fulltext_idx
FOR (n:JO) ON EACH [n.content]

-- 인덱스 사용
CALL db.index.fulltext.queryNodes('jo_content_fulltext_idx', '허가')
YIELD node, score
RETURN node
-- 실행 시간: 0.1초
```

#### 문제 2: Page Cache 적중률 낮음 (<80%)

**증상:**
- Page Cache Hit Ratio < 80%
- 쿼리 성능 저하

**진단:**
```cypher
CALL dbms.queryJmx("org.neo4j:instance=kernel#0,name=Page cache")
YIELD attributes
RETURN attributes.HitRatio.value as hitRatio
-- hitRatio: 0.65 (65%)
```

**해결:**
```properties
# neo4j.conf에서 Page Cache 증가
server.memory.pagecache.size=20g  # 기존 10g → 20g로 증가
```

#### 문제 3: Heap 메모리 부족

**증상:**
- `java.lang.OutOfMemoryError: Java heap space`
- GC 시간 증가

**진단:**
```cypher
CALL dbms.queryJmx("java.lang:type=Memory")
YIELD attributes
RETURN attributes.HeapMemoryUsage.value.used as heapUsed,
       attributes.HeapMemoryUsage.value.max as heapMax
-- heapUsed ≈ heapMax (90%+)
```

**해결:**
```properties
# neo4j.conf에서 Heap 증가
server.memory.heap.initial_size=10g  # 기존 4g → 10g
server.memory.heap.max_size=10g

# 또는 트랜잭션 메모리 제한
dbms.memory.transaction.total.max=5g
```

### 6.4 백업 전략

#### 6.4.1 수동 백업 (Community Edition)

```bash
# 1. Neo4j 중지
neo4j stop

# 2. 데이터 디렉토리 복사
cp -r /path/to/neo4j/data /backup/neo4j-data-2025-10-26

# 3. Neo4j 재시작
neo4j start
```

#### 6.4.2 온라인 백업 (neo4j-admin dump)

```bash
# Neo4j 실행 중에도 가능
neo4j-admin database dump neo4j --to-path=/backup/neo4j-dump-2025-10-26.dump

# 복원
neo4j-admin database load neo4j --from-path=/backup/neo4j-dump-2025-10-26.dump
```

#### 6.4.3 자동 백업 스크립트

```bash
#!/bin/bash
# scripts/backup_neo4j.sh

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/backup/neo4j"
RETENTION_DAYS=7

# 백업 수행
neo4j-admin database dump neo4j --to-path="${BACKUP_DIR}/neo4j-${DATE}.dump"

# 오래된 백업 삭제
find $BACKUP_DIR -name "neo4j-*.dump" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: neo4j-${DATE}.dump"
```

**Cron 등록 (매일 새벽 2시):**
```bash
crontab -e

# 추가
0 2 * * * /path/to/scripts/backup_neo4j.sh >> /var/log/neo4j-backup.log 2>&1
```

---

## 7. FAQ

### Q1: Community Edition으로 몇 개의 법률까지 처리 가능한가요?

**A:** 34억 노드까지 가능하므로, **수백만 개의 법률**도 처리 가능합니다. 우리 프로젝트(법률 1개당 ~1,325개 노드)로 계산하면:
- 34억 노드 ÷ 1,325 = **약 257만 개의 법률**까지 가능

한국 전체 법령(5,045개)은 **0.2%**만 사용하는 수준입니다.

### Q2: RAM이 부족하면 어떻게 되나요?

**A:** 성능이 크게 저하됩니다:
1. Page Cache에 데이터가 안 올라감
2. 디스크 I/O 발생 (HDD: 100-1000배 느림)
3. 쿼리 응답 시간 증가

**해결책:**
- RAM 증설 (가장 효과적)
- 쿼리 최적화로 데이터 접근 최소화
- SSD 사용으로 디스크 I/O 속도 개선

### Q3: 언제 Enterprise Edition이 필요한가요?

**A:** 다음 경우에만 고려하세요:
- ✅ 24/7 무중단 서비스 (클러스터링 필요)
- ✅ 자동 백업 및 HA 필요
- ✅ CPU 코어 4개 이상 사용 (GDS 알고리즘)
- ✅ 50-100% 더 빠른 쿼리 성능 필요

**우리 프로젝트**: Community Edition으로 충분!

### Q4: 벡터 검색(RAG)을 위해 별도 벡터 DB가 필요한가요?

**A:** 아니요! Neo4j 5.11+는 네이티브 벡터 인덱스를 지원합니다.

**장점:**
- ✅ 그래프 + 벡터 검색을 하나의 쿼리로
- ✅ 별도 DB 관리 불필요
- ✅ Agent가 agent_id로 필터링 후 벡터 검색 가능

**예시 쿼리:**
```cypher
MATCH (chunk:Chunk)
WHERE chunk.agent_id = 'agent_국토계획법'
CALL db.index.vector.queryNodes('chunk_embedding_idx', 10, $embedding)
YIELD node, score
RETURN node, score
```

### Q5: 자치법규(15만 개)까지 넣으면 어떻게 되나요?

**A:** 가능은 하지만 권장하지 않습니다.

**예상 규모:**
- 노드: 약 2억 개 (15만 × 1,325)
- RAM: 256-512GB 필요
- 쿼리 성능: 인덱스 있으면 문제없음

**권장 구조:**
```
Neo4j Instance 1: 중앙법령 (법률, 시행령, 시행규칙)
Neo4j Instance 2: 자치법규 (조례, 규칙)
```

또는 Neo4j Fabric으로 샤딩.

### Q6: 현재 시스템에서 바로 RAM만 늘리면 되나요?

**A:** 네, 하지만 neo4j.conf 설정도 함께 업데이트해야 합니다:

```bash
# 1. 서버 RAM 증설 (8GB → 64GB)

# 2. neo4j.conf 수정
server.memory.pagecache.size=40g  # RAM의 60%
server.memory.heap.max_size=20g   # RAM의 30%

# 3. Neo4j 재시작
neo4j restart

# 4. 확인
neo4j-admin server memory-recommendation --memory=64g
```

### Q7: 쿼리 성능 테스트는 어떻게 하나요?

**A:** 다음 단계를 따르세요:

```cypher
-- 1. 워밍업 (캐시 로드)
MATCH (n:JO) RETURN count(n)

-- 2. PROFILE로 쿼리 실행
PROFILE
MATCH (jo:JO {agent_id: 'agent_국토계획법'})
WHERE jo.has_delegation = true
RETURN jo
LIMIT 100

-- 3. 결과 확인
-- - db hits < 100,000 (좋음)
-- - Index Seek 사용 (좋음)
-- - Execution time < 100ms (좋음)

-- 4. 반복 실행하여 평균 시간 측정
```

### Q8: 디스크 공간은 얼마나 필요한가요?

**A:** 데이터베이스 크기의 **3-5배** 권장:

| 법률 수 | DB 크기 | 디스크 공간 (3배) |
|--------|--------|----------------|
| 10개 | 100MB | 300MB |
| 100개 | 1GB | 3GB |
| 1,000개 | 10GB | 30GB |
| 5,045개 (전체) | 50GB | 150GB |

**왜 3배?**
- 원본 데이터: 1배
- 인덱스: 0.5-1배
- 트랜잭션 로그: 0.3배
- 백업: 1배

---

## 결론

### ✅ 핵심 요약

1. **한국 전체 법령(5,045개)을 하나의 Neo4j 인스턴스에서 처리 가능**
   - 예상 노드: 668만 개
   - 필요 RAM: 64GB
   - Community Edition으로 충분

2. **스케일업은 RAM 증설이 가장 효과적**
   - Page Cache를 데이터베이스 크기의 1.2배로 설정
   - Heap은 Page Cache의 30-50%로 설정
   - SSD 사용 시 성능 10-100배 향상

3. **쿼리 성능은 데이터 크기보다 인덱스와 쿼리 패턴이 중요**
   - 전략적 인덱스 생성 (모든 필드에 인덱스 X)
   - EXPLAIN/PROFILE로 쿼리 최적화
   - 조기 필터링 및 관계 방향 명시

4. **모니터링과 백업은 필수**
   - Page Cache 적중률 95% 이상 유지
   - 느린 쿼리 로깅 및 최적화
   - 일일 자동 백업 설정

### 📊 단계별 하드웨어 요구사항

| Stage | 법률 수 | 노드 수 | RAM | CPU | 디스크 |
|-------|--------|--------|-----|-----|-------|
| **개발** | 10-100 | ~132K | 8GB | 4 cores | 100GB |
| **테스트** | 100-1K | ~1.3M | 16GB | 8 cores | 200GB SSD |
| **운영** | 5,045 | ~6.7M | 64GB | 16 cores | 500GB SSD |
| **확장** | 10K+ | ~13M+ | 128GB+ | 32+ cores | 1TB+ NVMe |

### 🚀 다음 단계

1. ✅ **Phase 2 완료**: Multi-agent metadata, 위임 관계 추출
2. ⬜ **Phase 3**: 벡터 임베딩 및 Neo4j Vector Index 구축
3. ⬜ **Phase 4**: 대규모 법령 데이터 로딩 및 성능 테스트
4. ⬜ **Phase 5**: Agent 구현 및 RAG 통합

### 📚 참고 자료

- [Neo4j Operations Manual - Memory Configuration](https://neo4j.com/docs/operations-manual/current/performance/memory-configuration/)
- [Neo4j Performance Tuning Guide](https://neo4j.com/developer/guide-performance-tuning/)
- [Neo4j Index Configuration](https://neo4j.com/docs/operations-manual/current/performance/index-configuration/)
- [Neo4j Fabric Sharding](https://neo4j.com/developer/neo4j-fabric-sharding/)
- [국가법령정보센터 통계](https://www.law.go.kr/lawStatistics.do)

---

**마지막 업데이트**: 2025-10-26
**작성자**: Claude Code
**프로젝트**: 한국 법률 Multi-Agent RAG 시스템
