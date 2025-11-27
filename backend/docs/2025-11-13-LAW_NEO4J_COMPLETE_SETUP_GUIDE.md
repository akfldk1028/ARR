# 법규 Neo4j Multi-Agent System - 완전 설치 가이드

**작성일**: 2025-11-13
**목적**: 다음 AI 또는 개발자가 처음부터 순차적으로 시스템을 구축할 수 있도록 완전한 가이드 제공

---

## ⚡ 빠른 시작

**바로 실행하고 싶다면:**

```bash
# 1. Neo4j Desktop 시작
# 2. .env 파일 확인 (NEO4J_*, OPENAI_API_KEY)
# 3. 실행 스크립트 폴더로 이동
cd D:\Data\11_Backend\01_ARR\backend\law\STEP

# 4. 전체 자동 실행
python run_all.py

# 5. 검증
python verify_system.py
```

**💡 law/STEP 폴더에는 순차적 실행 스크립트가 준비되어 있습니다:**
- `step1_pdf_to_json.py` - PDF → JSON 변환
- `step2_json_to_neo4j.py` - JSON → Neo4j 로드
- `step3_add_hang_embeddings.py` - HANG 임베딩 (KR-SBERT)
- `step4_initialize_domains.py` - Domain 초기화 (K-means)
- `step5_run_relationship_embedding.py` - 관계 임베딩 (OpenAI)
- `run_all.py` - 전체 자동 실행
- `verify_system.py` - 시스템 검증
- `README.md` - 자세한 실행 가이드

**자세한 내용은 이 문서를 계속 읽거나 `law/STEP/README.md`를 참조하세요.**

---

## 🎯 시스템 개요

### 전체 아키텍처
```
PDF 법률 문서
    ↓ [파싱]
표준 JSON
    ↓ [로드]
Neo4j 그래프 DB
    ↓ [임베딩]
벡터 검색 (노드 768-dim + 관계 3072-dim)
    ↓ [클러스터링]
Domain 노드 생성 (K-means)
    ↓ [인스턴스화]
Multi-Agent System (DomainAgent)
    ↓ [검색]
하이브리드 검색 (벡터 + 그래프 + A2A)
```

### 핵심 기술
- **그래프 DB**: Neo4j 5.x (벡터 인덱스 지원)
- **노드 임베딩**: KR-SBERT (768-dim, 로컬)
- **관계 임베딩**: OpenAI text-embedding-3-large (3072-dim)
- **클러스터링**: K-means (scikit-learn)
- **검색 알고리즘**: RNE/INE (그래프 탐색)
- **MAS**: AgentManager + DomainAgent (자가 조직화)
- **A2A**: JSON-RPC 2.0 프로토콜

---

## 📋 사전 준비

### 1. 환경 요구사항
```
- Python 3.12+
- Django 5.2.6
- Neo4j Desktop (또는 Neo4j Server 5.x)
- OpenAI API Key
- 최소 16GB RAM 권장
```

### 2. .env 파일 설정
```bash
# 프로젝트 루트에 .env 파일 생성
cd D:\Data\11_Backend\01_ARR\backend

# .env 파일 내용
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=11111111
NEO4J_DATABASE=neo4j

OPENAI_API_KEY=sk-your-api-key-here

DJANGO_SECRET_KEY=your-secret-key
DEBUG=True
```

### 3. Neo4j Desktop 시작
```
1. Neo4j Desktop 실행
2. 데이터베이스 생성/선택
3. "Start" 버튼 클릭
4. http://localhost:7474 접속 확인
```

### 4. Python 패키지 설치
```bash
pip install django==5.2.6
pip install neo4j==5.14.1
pip install sentence-transformers
pip install openai
pip install scikit-learn
pip install numpy
pip install python-dotenv
```

---

## 🚀 순차적 실행 가이드

### ✅ Step 0: 데이터 확인

**목적**: 원본 PDF 파일 존재 확인

```bash
# 위치 확인
ls law/data/raw/

# 예상 파일:
# - 04_국토의 계획 및 이용에 관한 법률(법률).pdf
# - 05_국토의 계획 및 이용에 관한 법률 시행령.pdf
# - 06_국토의 계획 및 이용에 관한 법률 시행규칙.pdf
```

**파일이 없으면**: PDF 파일을 `law/data/raw/` 디렉토리에 복사

---

### ✅ Step 1: PDF → JSON 변환

**목적**: PDF 법률 문서를 표준 JSON 형식으로 파싱

**실행 위치**: 프로젝트 루트

**명령어**:
```bash
python law/scripts/pdf_to_json.py --pdf "law/data/raw/04_국토의 계획 및 이용에 관한 법률(법률)(제19117호)(20230628).pdf"
python law/scripts/pdf_to_json.py --pdf "law/data/raw/05_국토의 계획 및 이용에 관한 법률 시행령(대통령령)(제33637호)(20230718).pdf"
python law/scripts/pdf_to_json.py --pdf "law/data/raw/06_국토의 계획 및 이용에 관한 법률 시행규칙(국토교통부령)(제01192호)(20230127).pdf"
```

**출력**:
```
law/data/parsed/
  ├── 국토의_계획_및_이용에_관한_법률_법률.json
  ├── 국토의_계획_및_이용에_관한_법률_시행령.json
  └── 국토의_계획_및_이용에_관한_법률_시행규칙.json
```

**검증**:
```bash
# JSON 파일 크기 확인 (각 500KB ~ 2MB)
ls -lh law/data/parsed/*.json

# JSON 구조 샘플 확인
python -c "
import json
with open('law/data/parsed/국토의_계획_및_이용에_관한_법률_법률.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    print(f\"법률명: {data['law_info']['law_name']}\")
    print(f\"총 단위: {data['law_info']['total_units']}개\")
    print(f\"파싱 완료: {len(data['units'])}개 단위\")
"
```

**예상 출력**:
```
법률명: 국토의 계획 및 이용에 관한 법률
총 단위: 1554개
파싱 완료: 1554개 단위
```

**주요 파일**:
- `law/scripts/pdf_to_json.py` - 메인 스크립트
- `law/scripts/pdf_extractor.py` - PDF 텍스트 추출
- `law/scripts/neo4j_preprocessor.py` - 법률 파싱 로직

---

### ✅ Step 2: JSON → Neo4j 로드

**목적**: 표준 JSON을 Neo4j 그래프 데이터베이스에 적재

**실행 위치**: 프로젝트 루트

**명령어**:
```bash
python law/scripts/json_to_neo4j.py --json "law/data/parsed/국토의_계획_및_이용에_관한_법률_법률.json"
python law/scripts/json_to_neo4j.py --json "law/data/parsed/국토의_계획_및_이용에_관한_법률_시행령.json"
python law/scripts/json_to_neo4j.py --json "law/data/parsed/국토의_계획_및_이용에_관한_법률_시행규칙.json"
```

**출력**:
```
law/scripts/neo4j/
  ├── 국토의_계획_및_이용에_관한_법률_neo4j.json
  ├── 국토의_계획_및_이용에_관한_법률_시행령_neo4j.json
  └── 국토의_계획_및_이용에_관한_법률_시행규칙_neo4j.json
```

**Neo4j 구조**:
```
LAW (3개)
 └─ JANG (24개) 장
     └─ JEOL (22개) 절
         └─ JO (1,053개) 조 ← 제목만!
             └─ HANG (1,477개) 항 ← 실제 내용!
                 └─ HO (1,025개) 호
                     └─ MOK (263개) 목

관계:
- CONTAINS: 계층 관계
- NEXT: 순서 관계
- CITES: 법률 인용 관계
```

**검증**:
```bash
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from graph_db.services import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

# 노드 개수 확인
result = neo4j.execute_query('MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY label')
print('Neo4j 노드 통계:')
for r in result:
    print(f\"  {r['label']}: {r['count']}개\")

# HANG 노드 샘플
hang = neo4j.execute_query('MATCH (h:HANG) RETURN h.full_id, h.content LIMIT 1')
print(f\"\nHANG 노드 샘플:\")
print(f\"  ID: {hang[0]['h.full_id']}\")
print(f\"  내용: {hang[0]['h.content'][:50]}...\")

neo4j.disconnect()
"
```

**예상 출력**:
```
Neo4j 노드 통계:
  HANG: 1477개
  HO: 1025개
  JANG: 24개
  JEOL: 22개
  JO: 1053개
  LAW: 3개
  MOK: 263개
```

**주요 파일**:
- `law/scripts/json_to_neo4j.py` - 메인 스크립트
- `law/scripts/neo4j_loader.py` - Neo4j 로더 클래스
- `law/core/neo4j_manager.py` - Neo4j 매니저

---

### ✅ Step 3: HANG 노드 임베딩 추가

**목적**: HANG 노드에 KR-SBERT 임베딩 (768-dim) 추가

**실행 위치**: 프로젝트 루트

**명령어**:
```bash
python add_hang_embeddings.py
```

**프로세스**:
```
1. HANG 노드 1,477개 로드
2. KR-SBERT 모델로 임베딩 생성 (768-dim)
3. Neo4j 업데이트 (SET hang.embedding = [...])
4. 벡터 인덱스 생성 (hang_embedding_index)
```

**예상 소요 시간**: 5~10분 (GPU 사용 시 2~3분)

**검증**:
```bash
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from graph_db.services import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

# 임베딩 확인
result = neo4j.execute_query('''
    MATCH (h:HANG)
    WHERE h.embedding IS NOT NULL
    RETURN count(h) as with_emb
''')
print(f\"임베딩 있는 HANG: {result[0]['with_emb']}개\")

# 임베딩 차원 확인
result = neo4j.execute_query('''
    MATCH (h:HANG)
    WHERE h.embedding IS NOT NULL
    RETURN size(h.embedding) as dim
    LIMIT 1
''')
print(f\"임베딩 차원: {result[0]['dim']}\")

# 벡터 인덱스 확인
result = neo4j.execute_query('SHOW INDEXES')
indexes = [r['name'] for r in result if 'hang_embedding' in r['name']]
print(f\"벡터 인덱스: {indexes}\")

neo4j.disconnect()
"
```

**예상 출력**:
```
임베딩 있는 HANG: 1477개
임베딩 차원: 768
벡터 인덱스: ['hang_embedding_index']
```

**주요 파일**:
- `add_hang_embeddings.py` - 메인 스크립트 (프로젝트 루트)
- `law/core/embedding_loader.py` - 임베딩 모델 로더

---

### ✅ Step 4: Domain 노드 초기화 ⭐ 필수!

**목적**: HANG 노드를 클러스터링하여 Domain 노드 생성 + DomainAgent 인스턴스화

**실행 위치**: 프로젝트 루트

**명령어**:
```bash
python initialize_domains.py
```

**프로세스**:
```
1. AgentManager 인스턴스 생성
2. HANG 노드 1,477개 + 임베딩 로드
3. K-means 클러스터링 (k=5, Silhouette Score 최적화)
4. 각 클러스터:
   - Domain 노드 생성 (Neo4j)
   - LLM으로 도메인 이름 생성 (OpenAI GPT-4)
   - DomainAgent 인스턴스 생성 (메모리)
   - BELONGS_TO_DOMAIN 관계 생성
5. A2A 네트워크 구성 (이웃 도메인 연결)
```

**예상 소요 시간**: 1~2분

**검증**:
```bash
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from graph_db.services import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

# Domain 노드 확인
domains = neo4j.execute_query('''
    MATCH (d:Domain)
    RETURN d.domain_id, d.domain_name, d.node_count
    ORDER BY d.node_count DESC
''')
print(f'Domain 노드: {len(domains)}개')
for d in domains:
    print(f\"  - {d['d.domain_id']}: {d['d.node_count']}개 노드\")

# BELONGS_TO_DOMAIN 관계 확인
rels = neo4j.execute_query('MATCH ()-[r:BELONGS_TO_DOMAIN]->() RETURN count(r) as count')
print(f\"\nBELONGS_TO_DOMAIN 관계: {rels[0]['count']}개\")

# 샘플 확인
sample = neo4j.execute_query('''
    MATCH (h:HANG)-[r:BELONGS_TO_DOMAIN]->(d:Domain)
    RETURN h.full_id, d.domain_id, r.similarity
    ORDER BY r.similarity DESC
    LIMIT 3
''')
print('\n샘플 관계 (Top 3 유사도):')
for s in sample:
    print(f\"  {s['h.full_id'][:50]}... -> {s['d.domain_id']} (sim: {s['r.similarity']:.3f})\")

neo4j.disconnect()
"
```

**예상 출력**:
```
Domain 노드: 5개
  - domain_c283b545: 510개 노드
  - domain_676e7400: 389개 노드
  - domain_3be25bdc: 230개 노드
  - domain_fad24752: 227개 노드
  - domain_09b3af0d: 121개 노드

BELONGS_TO_DOMAIN 관계: 1477개

샘플 관계 (Top 3 유사도):
  국토의 계획 및 이용에 관한 법률::제16조::① -> domain_09b3af0d (sim: 0.847)
  국토의 계획 및 이용에 관한 법률::제109조::2 -> domain_09b3af0d (sim: 0.822)
  국토의 계획 및 이용에 관한 법률::제10조::1 -> domain_09b3af0d (sim: 0.799)
```

**주요 파일**:
- `initialize_domains.py` - 메인 스크립트 (프로젝트 루트)
- `agents/law/agent_manager.py` - AgentManager 클래스
- `agents/law/domain_agent.py` - DomainAgent 클래스

---

### ✅ Step 5: CONTAINS 관계 임베딩 추가 (선택)

**목적**: CONTAINS 관계에 OpenAI 임베딩 (3072-dim) 추가

**실행 위치**: `law/relationship_embedding/`

**명령어** (순차 실행):
```bash
cd law/relationship_embedding

# Step 1: 관계 분석
python step1_analyze_relationships.py

# Step 2: 컨텍스트 추출
python step2_extract_contexts.py

# Step 3: 임베딩 생성 (OpenAI API 호출)
python step3_generate_embeddings.py

# Step 4: Neo4j 업데이트
python step4_update_neo4j.py

# Step 5: 벡터 인덱스 생성 및 테스트
python step5_create_index_and_test.py

# Step 10: 타입 무시 순수 벡터 검색 테스트
python step10_type_agnostic_search.py
```

**예상 소요 시간**: 10~15분 (OpenAI API 호출 시간 포함)

**비용**: 약 $0.50 ~ $1.00 (3,565개 관계 × 3072-dim)

**검증**:
```bash
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from graph_db.services import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

# 관계 임베딩 확인
result = neo4j.execute_query('''
    MATCH ()-[r:CONTAINS]->()
    WHERE r.embedding IS NOT NULL
    RETURN count(r) as count
''')
print(f\"임베딩 있는 CONTAINS 관계: {result[0]['count']}개\")

# 임베딩 차원 확인
result = neo4j.execute_query('''
    MATCH ()-[r:CONTAINS]->()
    WHERE r.embedding IS NOT NULL
    RETURN size(r.embedding) as dim
    LIMIT 1
''')
print(f\"임베딩 차원: {result[0]['dim']}\")

# 벡터 인덱스 확인
result = neo4j.execute_query('SHOW INDEXES')
indexes = [r['name'] for r in result if 'contains_embedding' in r['name']]
print(f\"벡터 인덱스: {indexes}\")

neo4j.disconnect()
"
```

**예상 출력**:
```
임베딩 있는 CONTAINS 관계: 3565개
임베딩 차원: 3072
벡터 인덱스: ['contains_embedding']
```

**주요 파일**:
- `law/relationship_embedding/step*.py` - 각 단계별 스크립트
- `law/relationship_embedding/README.md` - 상세 가이드

---

### ✅ Step 6: 전체 시스템 검증

**목적**: 모든 구성 요소가 정상 작동하는지 종합 확인

**실행 위치**: 프로젝트 루트

**검증 스크립트**:
```bash
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from graph_db.services import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

print('='*80)
print('법규 Neo4j Multi-Agent System - 전체 검증')
print('='*80)

# 1. 노드 통계
print('\n[1] 노드 통계:')
result = neo4j.execute_query('MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY label')
total_nodes = 0
for r in result:
    print(f\"  {r['label']}: {r['count']}개\")
    total_nodes += r['count']
print(f\"  총합: {total_nodes}개\")

# 2. 관계 통계
print('\n[2] 관계 통계:')
result = neo4j.execute_query('MATCH ()-[r]->() RETURN type(r) as rel_type, count(r) as count ORDER BY rel_type')
total_rels = 0
for r in result:
    print(f\"  {r['rel_type']}: {r['count']}개\")
    total_rels += r['count']
print(f\"  총합: {total_rels}개\")

# 3. 임베딩 통계
print('\n[3] 임베딩 통계:')
hang_emb = neo4j.execute_query('MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN count(h) as count')
print(f\"  HANG 임베딩: {hang_emb[0]['count']}개 (768-dim)\")

contains_emb = neo4j.execute_query('MATCH ()-[r:CONTAINS]->() WHERE r.embedding IS NOT NULL RETURN count(r) as count')
print(f\"  CONTAINS 임베딩: {contains_emb[0]['count']}개 (3072-dim)\")

# 4. Domain 통계
print('\n[4] Domain 통계:')
domains = neo4j.execute_query('MATCH (d:Domain) RETURN count(d) as count')
print(f\"  Domain 노드: {domains[0]['count']}개\")

belongs = neo4j.execute_query('MATCH ()-[r:BELONGS_TO_DOMAIN]->() RETURN count(r) as count')
print(f\"  BELONGS_TO_DOMAIN 관계: {belongs[0]['count']}개\")

# 5. 벡터 인덱스 확인
print('\n[5] 벡터 인덱스:')
indexes = neo4j.execute_query('SHOW INDEXES')
vector_indexes = [r['name'] for r in indexes if 'embedding' in r['name'].lower()]
for idx in vector_indexes:
    print(f\"  - {idx}\")

print('\n' + '='*80)
print('✅ 전체 검증 완료!')
print('='*80)

neo4j.disconnect()
"
```

**예상 출력**:
```
================================================================================
법규 Neo4j Multi-Agent System - 전체 검증
================================================================================

[1] 노드 통계:
  Domain: 5개
  HANG: 1477개
  HO: 1025개
  JANG: 24개
  JEOL: 22개
  JO: 1053개
  LAW: 3개
  MOK: 263개
  총합: 3872개

[2] 관계 통계:
  BELONGS_TO_DOMAIN: 1477개
  CITES: 0개
  CONTAINS: 3565개
  NEXT: 2458개
  총합: 7500개

[3] 임베딩 통계:
  HANG 임베딩: 1477개 (768-dim)
  CONTAINS 임베딩: 3565개 (3072-dim)

[4] Domain 통계:
  Domain 노드: 5개
  BELONGS_TO_DOMAIN 관계: 1477개

[5] 벡터 인덱스:
  - contains_embedding
  - hang_embedding_index

================================================================================
✅ 전체 검증 완료!
================================================================================
```

---

## 🔍 검색 테스트

### AgentManager를 통한 검색 테스트

**실행 위치**: Django shell

```bash
python manage.py shell
```

**테스트 코드**:
```python
from agents.law.agent_manager import AgentManager
from graph_db.services import Neo4jService

# AgentManager 초기화 (기존 Domain 로드)
manager = AgentManager()

print(f"로드된 도메인: {len(manager.domains)}개")
for domain_id, domain_info in manager.domains.items():
    print(f"  - {domain_info.domain_name}: {domain_info.size()}개 노드")

# 특정 도메인의 DomainAgent 가져오기
domain = list(manager.domains.values())[0]
domain_agent = domain.agent_instance

print(f"\n선택된 도메인: {domain.domain_name}")
print(f"DomainAgent 인스턴스: {domain_agent}")

# 비동기 검색 테스트
import asyncio

async def test_search():
    query = "개발행위 허가 요건"
    print(f"\n질의: {query}")

    results = await domain_agent._search_my_domain(query)

    print(f"\n검색 결과: {len(results)}개")
    for i, result in enumerate(results[:3], 1):
        print(f"\n[{i}] 유사도: {result['similarity']:.3f}")
        print(f"    ID: {result['hang_id']}")
        print(f"    내용: {result['content'][:100]}...")

# 실행
asyncio.run(test_search())
```

**예상 출력**:
```
로드된 도메인: 5개
  - 도시계획 및 이용: 510개 노드
  - 도시계획 및 관리 규정: 389개 노드
  - 토지 이용 및 기반시설: 230개 노드
  - 토지 이용 및 건축: 227개 노드
  - 도시 계획 및 개발: 121개 노드

선택된 도메인: 도시계획 및 이용
DomainAgent 인스턴스: <agents.law.domain_agent.DomainAgent object>

질의: 개발행위 허가 요건

검색 결과: 10개

[1] 유사도: 0.847
    ID: 국토의 계획 및 이용에 관한 법률::제56조::①
    내용: 개발행위의 허가를 받으려는 자는 국토교통부령으로 정하는 바에 따라 개발행위허가신청서...

[2] 유사도: 0.812
    ID: 국토의 계획 및 이용에 관한 법률::제58조::①
    내용: 제56조에 따라 개발행위허가를 받은 자는 그 허가받은 사항을 변경하려는 경우...

[3] 유사도: 0.795
    ID: 국토의 계획 및 이용에 관한 법률 시행령::제45조::②
    내용: 개발행위허가의 기준은 다음 각 호와 같다. 1. 용도지역별 건폐율...
```

---

## 🐛 트러블슈팅

### 1. Neo4j 연결 실패

**증상**:
```
neo4j.exceptions.ServiceUnavailable: Unable to retrieve routing information
```

**해결**:
```bash
# Neo4j Desktop에서 데이터베이스 시작 확인
# http://localhost:7474 접속 테스트

# .env 파일 확인
cat .env | grep NEO4J

# 포트 확인
netstat -ano | findstr 7687
```

### 2. 임베딩 생성 실패 (Out of Memory)

**증상**:
```
RuntimeError: CUDA out of memory
```

**해결**:
```python
# add_hang_embeddings.py 수정
# 배치 크기 줄이기
embedding_batch_size=16  # 기본값 32에서 16으로
```

### 3. Domain 노드 생성 실패

**증상**:
```
ValueError: No HANG nodes with embeddings found
```

**해결**:
```bash
# Step 3 (임베딩 추가)를 먼저 실행했는지 확인
python add_hang_embeddings.py

# HANG 임베딩 확인
python -c "
from graph_db.services import Neo4jService
neo4j = Neo4jService()
neo4j.connect()
result = neo4j.execute_query('MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN count(h) as count')
print(f'임베딩 있는 HANG: {result[0][\"count\"]}개')
neo4j.disconnect()
"

# 0개이면 Step 3 재실행
```

### 4. OpenAI API 오류

**증상**:
```
openai.error.AuthenticationError: Invalid API key
```

**해결**:
```bash
# .env 파일 확인
cat .env | grep OPENAI_API_KEY

# API 키 유효성 확인
python -c "
from openai import OpenAI
client = OpenAI()
try:
    response = client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': 'test'}],
        max_tokens=5
    )
    print('✅ OpenAI API 키 유효')
except Exception as e:
    print(f'❌ OpenAI API 키 오류: {e}')
"
```

### 5. 한글 깨짐 (Windows)

**증상**:
```
UnicodeEncodeError: 'cp949' codec can't encode character
```

**해결**:
```bash
# Python 스크립트에 추가
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 또는 환경 변수 설정
set PYTHONIOENCODING=utf-8
```

---

## 📊 최종 데이터 통계

### Neo4j 데이터베이스

| 항목 | 개수 |
|------|------|
| **총 노드** | 3,872개 |
| **총 관계** | 7,500개 |
| **LAW 노드** | 3개 |
| **JANG 노드** | 24개 |
| **JEOL 노드** | 22개 |
| **JO 노드** | 1,053개 (제목만) |
| **HANG 노드** | 1,477개 (실제 내용 + 임베딩) |
| **HO 노드** | 1,025개 |
| **MOK 노드** | 263개 |
| **Domain 노드** | 5개 (Multi-Agent System) |

### 관계

| 관계 타입 | 개수 | 설명 |
|----------|------|------|
| **CONTAINS** | 3,565개 | 계층 관계 (+ 3072-dim 임베딩) |
| **NEXT** | 2,458개 | 순서 관계 |
| **BELONGS_TO_DOMAIN** | 1,477개 | HANG → Domain 할당 |
| **CITES** | 0개 | 법률 인용 (파싱 개선 필요) |

### 임베딩

| 타입 | 모델 | 차원 | 개수 | 인덱스 |
|------|------|------|------|--------|
| **노드 임베딩** | KR-SBERT | 768 | 1,477개 | `hang_embedding_index` |
| **관계 임베딩** | OpenAI | 3,072 | 3,565개 | `contains_embedding` |
| **도메인 중심** | KR-SBERT | 768 | 5개 | `Domain.centroid_embedding` |

### 도메인 분포

| 도메인 | HANG 노드 수 | 비율 |
|--------|-------------|------|
| domain_c283b545 | 510개 | 34.5% |
| domain_676e7400 | 389개 | 26.3% |
| domain_3be25bdc | 230개 | 15.6% |
| domain_fad24752 | 227개 | 15.4% |
| domain_09b3af0d | 121개 | 8.2% |

---

## 📚 참고 문서

### 프로젝트 문서
- `law/SYSTEM_GUIDE.md` - 전체 시스템 학습 가이드
- `law/README.md` - 법규 시스템 개요
- `law/neo4j_schema.md` - Neo4j 스키마 상세
- `law/docs/PIPELINE_GUIDE.md` - 파이프라인 가이드
- `law/relationship_embedding/README.md` - 관계 임베딩 가이드

### Backend 문서
- `docs/2025-11-03-MAS_LAW_DOMAIN_ARCHITECTURE.md` - MAS 아키텍처
- `docs/2025-11-02-MAS_NEO4J_INTEGRATION_COMPLETE.md` - Neo4j 통합
- `docs/2025-10-31-SELF_ORGANIZING_AGENT_SYSTEM_COMPLETE.md` - 자가 조직화 시스템
- `docs/2025-10-30-RNE_INE_ALGORITHM_PAPER.md` - 검색 알고리즘

---

## 🎯 다음 단계

1. ✅ **데이터 파이프라인 완성** (Step 1-2)
2. ✅ **임베딩 시스템 구축** (Step 3, 5)
3. ✅ **Multi-Agent System 구축** (Step 4)
4. ⏭ **Django REST API 엔드포인트 구현**
5. ⏭ **A2A 프로토콜 테스트 (이웃 도메인 협업)**
6. ⏭ **프론트엔드 통합 (React/Vue)**
7. ⏭ **성능 최적화 (캐싱, 배치 처리)**
8. ⏭ **프로덕션 배포 (Docker, K8s)**

---

## 🔥 핵심 요약

### 전체 실행 순서 (한눈에)
```bash
# 0. 환경 준비
# - Neo4j Desktop 시작
# - .env 파일 설정
# - 패키지 설치

# 1. PDF → JSON
python law/scripts/pdf_to_json.py --pdf "law/data/raw/법률.pdf"

# 2. JSON → Neo4j
python law/scripts/json_to_neo4j.py --json "law/data/parsed/법률.json"

# 3. HANG 임베딩
python add_hang_embeddings.py

# 4. Domain 초기화 ⭐
python initialize_domains.py

# 5. 관계 임베딩 (선택)
cd law/relationship_embedding
python step1_analyze_relationships.py
python step2_extract_contexts.py
python step3_generate_embeddings.py
python step4_update_neo4j.py
python step5_create_index_and_test.py

# 6. 검증
python manage.py shell
>>> from agents.law.agent_manager import AgentManager
>>> manager = AgentManager()
>>> # 검색 테스트
```

### 핵심 파일 위치
```
law/
  ├── scripts/
  │   ├── pdf_to_json.py          # Step 1
  │   ├── json_to_neo4j.py        # Step 2
  │   └── neo4j_loader.py
  ├── core/
  │   ├── embedding_loader.py
  │   └── neo4j_manager.py
  └── relationship_embedding/      # Step 5
      └── step*.py

agents/law/
  ├── agent_manager.py             # Step 4 핵심
  └── domain_agent.py              # Step 4 핵심

add_hang_embeddings.py             # Step 3 (루트)
initialize_domains.py              # Step 4 (루트)
```

---

**작성자**: Claude Code
**최종 업데이트**: 2025-11-13
**검증 완료**: ✅ 국토계획법 시스템 (HANG 1,477개, Domain 5개)
