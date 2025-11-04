# MAS + 법률 검색 시스템 통합 계획

## 🎯 목표

**엄청난 양의 PDF 문서** + **MAS (Multi-Agent System)** + **RNE/INE 법률 검색**을 결합하여 지능형 법률 자문 시스템 구축

---

## 📊 현재 상황 분석

### 현재 시스템 구성

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Chat Interface)                                  │
│  - 텍스트 채팅 (chat/)                                        │
│  - 음성 채팅 (gemini/)                                        │
└─────────────────────┬───────────────────────────────────────┘
                      │ WebSocket
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  MAS (Multi-Agent System)                                   │
│  - GeneralWorker: 일반 조정자                                │
│  - FlightSpecialist: 항공권 전문가                            │
│  - A2A Protocol: 에이전트 간 통신                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Law Search System (별도)                                    │
│  - RNE/INE 알고리즘                                          │
│  - Neo4j (2,987 HANG 노드)                                   │
│  - 3개 PDF (법률, 시행령, 시행규칙)                            │
└─────────────────────────────────────────────────────────────┘
```

**문제점**:
- ❌ MAS와 법률 검색이 분리됨
- ❌ 3개 PDF만 처리 (확장성 없음)
- ❌ 에이전트가 법률 검색 기능 사용 불가
- ❌ 대량 PDF 처리 파이프라인 없음

---

## 💡 통합 아이디어

### 1. LawSpecialist Agent 추가

**역할**: 법률 전문가 에이전트
- 법률 검색 (RNE/INE)
- 법률 해석 & 자문
- 관련 조항 추천
- 판례 연결 (향후)

**기존 MAS와 통합**:
```
사용자: "도시계획 관련 법규 알려줘"
  ↓
GeneralWorker (조정자)
  ↓ A2A 프로토콜
LawSpecialist (법률 전문가)
  ↓ RNE/INE
Neo4j (법률 DB)
  ↓ 결과 반환
GeneralWorker → 사용자
```

---

### 2. 대량 PDF 처리 파이프라인

**현재**: 3개 PDF 수동 처리
**목표**: 수천 개 PDF 자동 처리

**파이프라인 설계**:
```
PDF 폴더 (수천 개)
  ↓ [Step 1] PDF → JSON
  ├─→ pdf_extractor.py (기존)
  ├─→ law_parser_improved.py (기존)
  └─→ 병렬 처리 (multiprocessing)
  ↓
JSON 파일들 (구조화)
  ↓ [Step 2] JSON → Neo4j
  ├─→ json_to_neo4j.py (기존)
  ├─→ 배치 처리 (bulk import)
  └─→ 중복 제거
  ↓
Neo4j (수만 개 노드)
  ↓ [Step 3] 임베딩 생성
  ├─→ add_embeddings.py (기존)
  ├─→ GPU 가속 (선택)
  └─→ 캐싱
  ↓
검색 가능한 법률 DB
```

---

## 🔍 순차적 통합 계획

### Phase 1: LawSpecialist Agent 개발 (1주)

**목표**: MAS에 법률 전문가 추가

#### 1.1 파일 생성

```
agents/worker_agents/
├── implementations/
│   └── law_specialist_worker.py  ← 새로 생성
└── cards/
    └── law_specialist_agent.json  ← 새로 생성
```

#### 1.2 LawSpecialistWorker 구현

```python
# agents/worker_agents/implementations/law_specialist_worker.py

from ..base.base_worker import BaseWorkerAgent
from graph_db.services.neo4j_service import Neo4jService
from graph_db.algorithms.repository.law_repository import LawRepository
from graph_db.algorithms.core.semantic_rne import SemanticRNE
from graph_db.algorithms.core.semantic_ine import SemanticINE
from sentence_transformers import SentenceTransformer

class LawSpecialistWorker(BaseWorkerAgent):
    """
    법률 전문가 에이전트

    역할:
    - 법률 검색 (RNE/INE)
    - 법률 해석 & 자문
    - 관련 조항 추천
    """

    def __init__(self, agent_card):
        super().__init__(agent_card)

        # Neo4j 연결
        self.neo4j = Neo4jService()
        self.neo4j.connect()

        # 임베딩 모델
        self.model = SentenceTransformer('jhgan/ko-sbert-sts')

        # Repository
        self.law_repo = LawRepository(self.neo4j)

        # 알고리즘
        self.rne = SemanticRNE(None, self.law_repo, self.model)
        self.ine = SemanticINE(None, self.law_repo, self.model)

    def get_system_prompt(self) -> str:
        return """당신은 법률 전문가 에이전트입니다.

역할:
1. 법률 검색: 사용자 질문에 관련된 법률/시행령/시행규칙 조항 찾기
2. 법률 해석: 찾은 조항을 이해하기 쉽게 설명
3. 맥락 제공: 상위/하위 조항, 관련 법규 제시

검색 전략:
- 정확도 우선: RNE 알고리즘 (threshold=0.75)
- 재현율 우선: INE 알고리즘 (k=15)
- 자동 선택: 질문 유형에 따라

응답 형식:
1. 관련 조항 요약
2. 상세 설명
3. 참고 조항 (선택)
"""

    async def process_message(self, message: str, context_id: str, session_id: str) -> str:
        """법률 검색 + 해석"""

        # [1] 쿼리 분류
        query_type = self._classify_query(message)

        # [2] 검색 실행
        if query_type == "precise":
            # 정확한 조항 찾기
            results, _ = self.rne.execute_query(
                query_text=message,
                similarity_threshold=0.75,
                max_results=10
            )
        else:
            # 관련 조항 전부 찾기
            results = self.ine.execute_query(
                query_text=message,
                k=15
            )

        # [3] LLM으로 해석 생성
        context = self._format_search_results(results)
        response = await self._generate_interpretation(message, context)

        return response

    def _classify_query(self, message: str) -> str:
        """쿼리 유형 분류"""
        if "정확히" in message or "구체적으로" in message:
            return "precise"  # RNE
        else:
            return "comprehensive"  # INE

    def _format_search_results(self, results) -> str:
        """검색 결과 포맷팅"""
        formatted = "### 관련 법규\n\n"

        # 법규별 그룹화
        law_groups = {}
        for r in results:
            law_name = r['law_name']
            if '시행규칙' in law_name:
                law_type = '시행규칙'
            elif '시행령' in law_name:
                law_type = '시행령'
            else:
                law_type = '법률'

            if law_type not in law_groups:
                law_groups[law_type] = []
            law_groups[law_type].append(r)

        # 출력
        for law_type in ['법률', '시행령', '시행규칙']:
            if law_type in law_groups:
                formatted += f"\n**{law_type}**:\n"
                for article in law_groups[law_type][:3]:  # 상위 3개
                    formatted += f"- {article['full_id']}\n"
                    formatted += f"  {article['content'][:100]}...\n"

        return formatted

    async def _generate_interpretation(self, query: str, context: str) -> str:
        """LLM으로 해석 생성"""
        # LangGraph 또는 직접 OpenAI API 호출
        # 기존 BaseWorkerAgent의 LLM 호출 메커니즘 활용

        prompt = f"""사용자 질문: {query}

{context}

위 법규를 바탕으로 사용자 질문에 답변하세요."""

        # LLM 호출 (기존 메커니즘 사용)
        response = await self._call_llm(prompt)
        return response
```

#### 1.3 Agent Card 작성

```json
// agents/worker_agents/cards/law_specialist_agent.json
{
  "name": "LawSpecialist",
  "slug": "law-specialist",
  "version": "1.0.0",
  "description": "법률 검색 및 해석 전문가",
  "capabilities": [
    {
      "name": "법률 검색",
      "description": "RNE/INE 알고리즘으로 관련 법규 검색"
    },
    {
      "name": "법률 해석",
      "description": "법률 조항을 이해하기 쉽게 설명"
    },
    {
      "name": "관련 조항 추천",
      "description": "상위/하위 법규 자동 추천"
    }
  ],
  "keywords": ["법률", "법규", "조항", "시행령", "시행규칙"],
  "author": "System",
  "license": "MIT"
}
```

#### 1.4 Worker Factory 등록

```python
# agents/worker_agents/worker_factory.py

from .implementations.law_specialist_worker import LawSpecialistWorker

class WorkerAgentFactory:
    WORKER_CLASSES = {
        'general-worker': GeneralWorker,
        'flight-specialist': FlightSpecialistWorker,
        'law-specialist': LawSpecialistWorker,  # ← 추가
    }
```

#### 1.5 테스트

```python
# test_law_specialist.py

from agents.worker_agents.worker_factory import WorkerAgentFactory

# Agent 생성
factory = WorkerAgentFactory()
law_specialist = factory.create_worker('law-specialist')

# 테스트 쿼리
query = "도시계획 수립 절차가 뭐야?"
response = await law_specialist.process_message(query, "ctx1", "session1")

print(response)
```

**예상 출력**:
```
도시계획 수립 절차는 다음과 같습니다:

### 관련 법규

**법률**:
- 국토의 계획 및 이용에 관한 법률::제13조::2
  도시계획은 국토교통부장관이 수립한다...

**시행령**:
- 국토의 계획 및 이용에 관한 법률 시행령::제6조의2::1
  법 제13조에 따른 도시계획 수립 시 다음 절차를 따른다...

**시행규칙**:
- 국토의 계획 및 이용에 관한 법률 시행규칙::제3조::①
  영 제25조제3항제1호다목에서 정하는 경미한 사항...

### 상세 설명
도시계획은 먼저 법률에서 큰 틀을 정하고, 시행령에서 구체적인 절차를,
시행규칙에서 세부 사항을 규정합니다...
```

---

### Phase 2: 대량 PDF 처리 파이프라인 (2주)

**목표**: 수천 개 PDF 자동 처리

#### 2.1 폴더 구조

```
law/
├── data/
│   ├── raw/                    # 원본 PDF (수천 개)
│   │   ├── batch_001/
│   │   │   ├── law_001.pdf
│   │   │   ├── law_002.pdf
│   │   │   └── ...
│   │   ├── batch_002/
│   │   └── ...
│   │
│   ├── parsed/                 # 파싱된 JSON
│   │   ├── law_001.json
│   │   ├── law_002.json
│   │   └── ...
│   │
│   └── embeddings/             # 임베딩 캐시
│       ├── law_001_embeddings.pkl
│       └── ...
│
└── scripts/
    ├── batch_processor.py      # ← 새로 생성 (배치 처리)
    ├── pdf_to_json_batch.py    # ← 새로 생성 (병렬 PDF→JSON)
    └── json_to_neo4j_batch.py  # ← 새로 생성 (배치 Neo4j 삽입)
```

#### 2.2 배치 처리 스크립트

```python
# law/scripts/batch_processor.py
"""
대량 PDF 일괄 처리

단계:
1. PDF → JSON (병렬 처리)
2. JSON → Neo4j (배치 삽입)
3. 임베딩 생성 (GPU 가속)
"""

import os
import multiprocessing
from pathlib import Path
from tqdm import tqdm

class LawBatchProcessor:
    def __init__(self, raw_dir, parsed_dir, batch_size=100):
        self.raw_dir = Path(raw_dir)
        self.parsed_dir = Path(parsed_dir)
        self.batch_size = batch_size

    def process_all(self):
        """전체 파이프라인 실행"""

        # [1] PDF → JSON (병렬)
        pdf_files = list(self.raw_dir.rglob("*.pdf"))
        print(f"발견한 PDF: {len(pdf_files)}개")

        with multiprocessing.Pool() as pool:
            results = list(tqdm(
                pool.imap(self._process_single_pdf, pdf_files),
                total=len(pdf_files),
                desc="PDF 파싱"
            ))

        # [2] JSON → Neo4j (배치)
        json_files = list(self.parsed_dir.glob("*.json"))
        self._batch_import_to_neo4j(json_files)

        # [3] 임베딩 생성
        self._generate_embeddings()

    def _process_single_pdf(self, pdf_path):
        """단일 PDF 처리"""
        from law.core.pdf_extractor import PDFExtractor
        from law.core.law_parser_improved import LawParser

        # PDF → 텍스트
        extractor = PDFExtractor()
        text = extractor.extract(pdf_path)

        # 텍스트 → JSON
        parser = LawParser()
        data = parser.parse(text)

        # JSON 저장
        output_path = self.parsed_dir / f"{pdf_path.stem}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return output_path

    def _batch_import_to_neo4j(self, json_files):
        """배치 Neo4j 삽입"""
        from graph_db.services.neo4j_service import Neo4jService

        neo4j = Neo4jService()
        neo4j.connect()

        # 배치 처리 (100개씩)
        for i in tqdm(range(0, len(json_files), self.batch_size), desc="Neo4j 삽입"):
            batch = json_files[i:i+self.batch_size]

            # Cypher UNWIND로 배치 삽입
            with neo4j.driver.session() as session:
                session.run("""
                    UNWIND $batch as item
                    MERGE (law:LAW {name: item.law_name})
                    // ... (나머지 노드 생성)
                """, batch=[self._load_json(f) for f in batch])

    def _generate_embeddings(self):
        """임베딩 생성 (GPU 가속)"""
        from sentence_transformers import SentenceTransformer

        # GPU 사용 가능 시 자동 활용
        model = SentenceTransformer('jhgan/ko-sbert-sts')

        # 배치 처리
        # ... (기존 add_embeddings.py 로직 활용)

# 실행
if __name__ == "__main__":
    processor = LawBatchProcessor(
        raw_dir="law/data/raw",
        parsed_dir="law/data/parsed"
    )
    processor.process_all()
```

**실행**:
```bash
# 전체 PDF 처리 (병렬)
python law/scripts/batch_processor.py

# 진행 상황
# PDF 파싱: 100%|██████████| 5000/5000 [1:23:45<00:00, 59.82it/s]
# Neo4j 삽입: 100%|██████████| 50/50 [00:15:32<00:00, 18.64s/it]
# 임베딩 생성: 100%|██████████| 5000/5000 [02:34:12<00:00, 1.85s/it]
```

#### 2.3 성능 최적화

**병렬 처리**:
```python
# CPU 코어 활용
cpu_count = multiprocessing.cpu_count()
with multiprocessing.Pool(processes=cpu_count - 1) as pool:
    pool.map(process_pdf, pdf_files)
```

**GPU 가속** (선택):
```python
# CUDA 사용 가능 시 자동 활용
model = SentenceTransformer('jhgan/ko-sbert-sts', device='cuda')

# 배치 임베딩 (더 빠름)
embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)
```

**캐싱**:
```python
# 이미 처리된 파일 스킵
def is_already_processed(pdf_path, parsed_dir):
    json_path = parsed_dir / f"{pdf_path.stem}.json"
    return json_path.exists()

pdf_files = [f for f in all_pdfs if not is_already_processed(f, parsed_dir)]
```

---

### Phase 3: A2A 통합 & 라우팅 (1주)

**목표**: GeneralWorker가 법률 질문을 LawSpecialist에게 자동 라우팅

#### 3.1 라우팅 규칙

```python
# agents/worker_agents/implementations/general_worker.py

class GeneralWorker(BaseWorkerAgent):
    async def process_message(self, message, context_id, session_id):
        # 법률 관련 키워드 감지
        law_keywords = ['법률', '법규', '조항', '시행령', '시행규칙',
                       '규정', '법', '조례', '시행', '개정']

        if any(keyword in message for keyword in law_keywords):
            # LawSpecialist에게 위임
            return await self._delegate_to_specialist(
                'law-specialist',
                message,
                context_id
            )

        # 기존 로직...
```

#### 3.2 A2A 메시지 흐름

```
[사용자]
"도시계획 법규 알려줘"
  ↓ WebSocket
[GeneralWorker]
  ↓ 키워드 감지: "법규"
  ↓ A2A JSON-RPC
  {
    "jsonrpc": "2.0",
    "method": "process_message",
    "params": {
      "message": "도시계획 법규 알려줘",
      "context_id": "ctx123"
    }
  }
  ↓
[LawSpecialist]
  ↓ RNE 검색
  ↓ Neo4j
  ↓ LLM 해석
  {
    "result": "도시계획 법규는..."
  }
  ↓ A2A 응답
[GeneralWorker]
  ↓ 포맷팅
[사용자]
```

---

### Phase 4: Context7 & Web 검색 통합 (1주)

**목표**: 외부 지식과 내부 법률 DB 결합

#### 4.1 하이브리드 검색

```python
# agents/worker_agents/implementations/law_specialist_worker.py

class LawSpecialistWorker(BaseWorkerAgent):
    async def process_message(self, message, context_id, session_id):
        # [1] 내부 법률 DB 검색 (RNE/INE)
        internal_results = self.rne.execute_query(message, threshold=0.75)

        # [2] Context7 검색 (외부 법률 데이터베이스)
        external_results = await self._search_context7(message)

        # [3] Web 검색 (최신 판례, 해석)
        web_results = await self._search_web(message)

        # [4] 결합 & 랭킹
        combined = self._merge_results(
            internal_results,
            external_results,
            web_results
        )

        # [5] LLM 해석
        response = await self._generate_interpretation(message, combined)
        return response

    async def _search_context7(self, query):
        """Context7 API 호출"""
        # 기존 Context7 MCP 서버 활용
        # mcp__context7__get-library-docs 호출
        pass

    async def _search_web(self, query):
        """Web 검색"""
        # WebSearch 도구 활용
        pass

    def _merge_results(self, internal, external, web):
        """결과 병합 & 중복 제거"""
        # 유사도 기반 중복 제거
        # 소스별 가중치 적용
        pass
```

#### 4.2 소스별 가중치

```python
WEIGHTS = {
    'internal_law': 1.0,      # 내부 법률 DB (가장 신뢰)
    'context7': 0.8,          # Context7 (전문 DB)
    'web_search': 0.5,        # Web 검색 (참고용)
}

def _merge_results(self, internal, external, web):
    merged = []

    for result in internal:
        result['score'] *= WEIGHTS['internal_law']
        result['source'] = 'internal'
        merged.append(result)

    for result in external:
        result['score'] *= WEIGHTS['context7']
        result['source'] = 'context7'
        merged.append(result)

    for result in web:
        result['score'] *= WEIGHTS['web_search']
        result['source'] = 'web'
        merged.append(result)

    # 유사도 기반 중복 제거
    merged = self._deduplicate(merged)

    # 점수순 정렬
    merged.sort(key=lambda x: x['score'], reverse=True)

    return merged[:15]  # Top-15
```

---

### Phase 5: 확장 & 최적화 (진행중)

**목표**: 대규모 운영 준비

#### 5.1 벡터 DB 마이그레이션 (선택)

**문제**: Neo4j 벡터 인덱스는 대규모 데이터에서 느릴 수 있음

**해결**: Qdrant/Pinecone 등 전문 벡터 DB 활용

```python
from qdrant_client import QdrantClient

class LawRepository:
    def __init__(self, neo4j, qdrant):
        self.neo4j = neo4j      # 그래프 구조
        self.qdrant = qdrant    # 벡터 검색

    def vector_search(self, query_emb, top_k):
        # Qdrant로 빠른 벡터 검색
        results = self.qdrant.search(
            collection_name="law_embeddings",
            query_vector=query_emb,
            limit=top_k
        )

        # Neo4j에서 그래프 정보 가져오기
        for result in results:
            hang_id = result.id
            neighbors = self._get_neighbors_from_neo4j(hang_id)
            result.neighbors = neighbors

        return results
```

#### 5.2 캐싱 전략

```python
import redis
import pickle

class CachedLawRepository:
    def __init__(self, law_repo):
        self.law_repo = law_repo
        self.redis = redis.Redis()
        self.ttl = 3600  # 1시간

    def vector_search(self, query_emb, top_k):
        # 캐시 키
        cache_key = f"search:{hash(query_emb.tobytes())}:{top_k}"

        # 캐시 확인
        cached = self.redis.get(cache_key)
        if cached:
            return pickle.loads(cached)

        # 검색 실행
        results = self.law_repo.vector_search(query_emb, top_k)

        # 캐시 저장
        self.redis.setex(cache_key, self.ttl, pickle.dumps(results))

        return results
```

#### 5.3 모니터링

```python
# 검색 로그
import logging

logger = logging.getLogger('law_search')

def vector_search(self, query_emb, top_k):
    import time
    start = time.time()

    results = self._do_search(query_emb, top_k)

    elapsed = time.time() - start
    logger.info(f"검색 완료: {len(results)}개, {elapsed:.2f}초")

    # 메트릭 수집
    metrics.record('search_latency', elapsed)
    metrics.record('search_results', len(results))

    return results
```

---

## 📈 예상 효과

### 1. 검색 성능

| 항목 | 현재 (3 PDF) | Phase 2 (5,000 PDF) | 개선율 |
|------|--------------|---------------------|--------|
| 법규 커버리지 | 3개 | 5,000+개 | **+166,567%** |
| HANG 노드 | 2,987개 | ~500,000개 | **+16,633%** |
| 검색 정확도 | 88% | 92% (예상) | +4.5% |

### 2. 사용자 경험

**Before (현재)**:
```
사용자: "도시계획 법규 알려줘"
시스템: (응답 없음 - MAS와 분리됨)
```

**After (Phase 3 완료)**:
```
사용자: "도시계획 법규 알려줘"
GeneralWorker: (법률 키워드 감지)
  ↓ A2A
LawSpecialist: (RNE 검색)
  → 법률 3개, 시행령 2개, 시행규칙 5개 발견
  → LLM 해석 생성
시스템: "도시계획 법규는 다음과 같습니다..."
```

### 3. 확장 가능성

```
현재 시스템:
  └─ 법률 검색 (독립)

Phase 5 완료:
  ├─ 법률 검색 (RNE/INE)
  ├─ 판례 검색 (추가 가능)
  ├─ 행정 규칙 검색 (추가 가능)
  └─ 외국 법률 검색 (Context7)
```

---

## 🚀 시작 방법

### Quick Start (Phase 1만 먼저)

```bash
# 1. LawSpecialist 파일 생성
mkdir -p agents/worker_agents/implementations
touch agents/worker_agents/implementations/law_specialist_worker.py

mkdir -p agents/worker_agents/cards
touch agents/worker_agents/cards/law_specialist_agent.json

# 2. 구현 (위 코드 복사)
# ... (law_specialist_worker.py, law_specialist_agent.json 작성)

# 3. Worker Factory 등록
# agents/worker_agents/worker_factory.py 수정

# 4. 테스트
python test_law_specialist.py

# 5. MAS 통합 테스트
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
# 브라우저: http://localhost:8000/chat/
# 메시지: "도시계획 법규 알려줘"
```

---

## 🎯 타임라인

| Phase | 기간 | 핵심 작업 | 우선순위 |
|-------|------|----------|---------|
| Phase 1 | 1주 | LawSpecialist Agent | ⭐⭐⭐⭐⭐ |
| Phase 2 | 2주 | 대량 PDF 처리 | ⭐⭐⭐⭐ |
| Phase 3 | 1주 | A2A 라우팅 | ⭐⭐⭐⭐⭐ |
| Phase 4 | 1주 | Context7/Web 통합 | ⭐⭐⭐ |
| Phase 5 | 진행중 | 확장 & 최적화 | ⭐⭐ |

**총 소요 시간**: 5주

**최소 MVP (Phase 1+3)**: 2주

---

## 🤔 의사 결정 포인트

### 1. 벡터 DB 선택

**선택지**:
- A. Neo4j 벡터 인덱스 (현재)
- B. Qdrant (전문 벡터 DB)
- C. Pinecone (클라우드)

**추천**: Phase 2에서 데이터 규모 확인 후 결정

### 2. 임베딩 모델

**선택지**:
- A. ko-sbert-sts (현재, 768-dim)
- B. ko-sroberta-multitask (1024-dim)
- C. multilingual-e5 (1024-dim)

**추천**: 현재 모델 유지, Phase 5에서 성능 비교

### 3. LLM 선택

**선택지**:
- A. OpenAI GPT-4 (기존)
- B. Claude 3.5 Sonnet
- C. Gemini 2.0

**추천**: Phase 4에서 법률 해석 품질 비교

---

## 📚 참고 자료

- [2025-10-31-RNE_INE_INTEGRATION_GUIDE.md](./2025-10-31-RNE_INE_INTEGRATION_GUIDE.md)
- [2025-10-31-CROSS_LAW_VERIFICATION_COMPLETE.md](./2025-10-31-CROSS_LAW_VERIFICATION_COMPLETE.md)
- [CLAUDE.md](../CLAUDE.md) - MAS 아키텍처

---

**작성일**: 2025-10-31
**작성자**: Claude Code
**다음 작업**: Phase 1 - LawSpecialist Agent 개발
