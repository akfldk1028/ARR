# Django 프로젝트 통합 가이드 (2025-10-26 업데이트)

> **한국 법률 Multi-Agent RAG 시스템**을 Django 프로젝트에 통합하는 완전한 가이드

---

## 📊 시스템 현황 (국토계획법 기준)

### 파싱 완료 데이터
- **법률**: 1,554 units (201,519자) ✓ **전체 내용 파싱 완료**
- **시행령**: 2,078 units (294,414자) ✓ **전체 내용 파싱 완료**
- **시행규칙**: 341 units (54,267자) ✓ **전체 내용 파싱 완료**

### Neo4j 그래프 데이터베이스
- **총 노드**: 3,976개
- **총 관계**: 7,023개
- **법률 문서**: 3개 (법률, 시행령, 시행규칙)
- **조문 계층**: 1,053개 조, 1,586개 항, 1,025개 호, 263개 목

**✓ 모든 PDF 법규 내용이 Neo4j에 완전히 저장되어 있습니다!**

---

## 📁 폴더 구조

```
django_migration/
├── core/                    # 핵심 비즈니스 로직 (Django로 복사 필요)
│   ├── law_parser.py        # PDF → JSON 파서
│   ├── neo4j_manager.py     # Neo4j 연결/로더
│   ├── pdf_extractor.py     # PDF 텍스트 추출
│   ├── rag_chunker.py       # 3단계 다층 청킹
│   ├── converters.py        # JSON 형식 변환
│   └── relation_extractor.py # 법률 참조 추출
│
├── scripts/                 # 유틸리티 스크립트
│   ├── add_embeddings.py    # Phase 2: Neo4j에 임베딩 추가
│   ├── pdf_to_json.py       # PDF → 표준 JSON
│   ├── json_to_neo4j.py     # JSON → Neo4j
│   ├── json_to_rag.py       # JSON → RAG 청크
│   └── neo4j_loader.py      # Neo4j 로더 (내부 사용)
│
├── data/                    # 데이터 (백업용)
│   └── parsed/              # 표준 JSON 파일 (3개, 2.7MB)
│
├── examples/                # Django 통합 예시
│   ├── django_settings.py   # settings.py에 추가할 내용
│   └── management_command.py # Management command 예시
│
├── docs/                    # 상세 문서
│   ├── chunking_strategy.md # 3단계 청킹 전략
│   ├── neo4j_scaling_guide.md # Neo4j 스케일링
│   └── PIPELINE_GUIDE.md    # 파이프라인 가이드
│
├── load_data.py             # ⭐ 간단 데이터 로더 (시작점!)
├── .env.example             # 환경 변수 템플릿
├── neo4j_schema.md          # Neo4j 스키마 상세 (실제 구조)
├── requirements.txt         # Python 의존성
└── README.md               # 이 문서
```

---

## 🚀 빠른 시작 (Quick Start)

### 1. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 수정 (NEO4J_PASSWORD 설정)
# NEO4J_PASSWORD=your_password
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. Neo4j에 데이터 로드 ⭐

```bash
python load_data.py
```

이 스크립트가 자동으로:
- `data/parsed/` 폴더의 JSON 파일 읽기
- Neo4j 인덱스 생성
- 3,976개 노드 로드
- 7,023개 관계 생성

**예상 시간**: 1-2분

### 4. 확인

Neo4j Browser에서 확인:
```
http://localhost:7474
```

쿼리:
```cypher
MATCH (n) RETURN labels(n), count(n)
```

결과:
- LAW: 3개
- JANG: 19개
- JEOL: 12개
- JO: 1,053개
- HANG: 1,586개 ⭐
- HO: 1,025개
- MOK: 263개

---

## 🎯 시스템 아키텍처: Multi-Agent RAG

### 전체 흐름도

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 데이터 준비 (완료!)                                        │
│                                                             │
│ PDF 법규 (3개)                                              │
│  └→ 파서 → JSON (3,973 units) → Neo4j (3,976 노드)         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. 3단계 다층 청킹 (RAG Chunking)                           │
│                                                             │
│ Neo4j 조문 → 3가지 레벨로 청크 생성                          │
│  ├─ 조전체 (1,053개): 전체 맥락 파악용                       │
│  ├─ 항단위 (1,586개): 균형 검색용 (최적!)                   │
│  └─ 호단위 (1,025개): 세부 정보 추출용                       │
│                                                             │
│ 각 청크 → 768차원 벡터 임베딩 (ko-sbert-sts)                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Multi-Agent RAG 시스템 (목표!)                           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Query Agent (질의 분석 에이전트)                      │  │
│  │ - 질의 의도 파악 ("개념 정의" vs "구체적 절차")       │  │
│  │ - 청킹 레벨 선택 (조전체 / 항단위 / 호단위)          │  │
│  │ - 질의 임베딩 생성                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Retrieval Agent (검색 에이전트)                       │  │
│  │                                                      │  │
│  │ 1) 벡터 검색 (Neo4j Vector Index)                   │  │
│  │    └→ 의미적으로 유사한 HANG 노드 찾기                │  │
│  │                                                      │  │
│  │ 2) 그래프 탐색 (Neo4j Graph)                         │  │
│  │    └→ 상위 JO, JANG 정보 가져오기                    │  │
│  │    └→ 법률 → 시행령 참조 자동 연결                   │  │
│  │                                                      │  │
│  │ 3) 컨텍스트 확장                                     │  │
│  │    └→ 전후 HANG, 관련 HO/MOK 함께 반환               │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Synthesis Agent (답변 생성 에이전트)                  │  │
│  │ - 검색된 여러 조문을 종합                            │  │
│  │ - LLM으로 자연어 답변 생성                           │  │
│  │ - 법률 출처 인용 추가                                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 청킹 전략 상세

### 왜 3단계 청킹인가?

법률 질의는 **입도(Granularity)가 다릅니다**:

```
질의 A: "용도지역이란?"
 └→ 개념 정의 → 조 전체 필요 → 조전체 청크 사용

질의 B: "개발행위 허가 요건은?"
 └→ 구체적 절차 → 항별 검색 → 항단위 청크 사용

질의 C: "건폐율은 정확히 몇 %?"
 └→ 세부 숫자 → 호 단위 필요 → 호단위 청크 사용
```

### 3단계 청킹 비교표

| 레벨 | 평균 크기 | 청크 수 | 용도 | Multi-Agent 역할 |
|------|----------|---------|------|------------------|
| **조전체** | 286자 | 1,053개 | 전체 맥락 파악 | Query Agent가 "개념/정의" 질의 시 선택 |
| **항단위** | 191자 | 1,586개 | **균형 검색** (최적!) | 대부분의 질의에서 사용 (기본값) |
| **호단위** | 187자 | 1,025개 | 세부 정보 추출 | "구체적으로/정확히" 질의 시 선택 |

### Query Agent의 청킹 레벨 선택 로직

```python
# Query Agent 예시
def select_chunking_level(query: str) -> str:
    """질의 분석 후 적절한 청킹 레벨 선택"""

    # 개념/정의 질의 → 조전체
    if any(keyword in query for keyword in ["란", "이란", "정의", "의미"]):
        return "조전체"

    # 구체적 숫자/기준 질의 → 호단위
    elif any(keyword in query for keyword in ["몇", "얼마", "정확히", "구체적으로"]):
        return "호단위"

    # 일반 질의 → 항단위 (기본값)
    else:
        return "항단위"  # 최적 균형!
```

---

## 🤖 Multi-Agent 구현 예시

### Agent 1: Query Agent

```python
# law_rag/agents/query_agent.py

from sentence_transformers import SentenceTransformer

class QueryAgent:
    """질의 분석 및 임베딩 생성"""

    def __init__(self):
        self.model = SentenceTransformer('jhgan/ko-sbert-sts')

    def analyze_query(self, query: str) -> dict:
        """질의 분석"""
        return {
            'query': query,
            'embedding': self.model.encode(query).tolist(),
            'chunk_level': self._select_chunk_level(query),
            'intent': self._detect_intent(query)
        }

    def _select_chunk_level(self, query: str) -> str:
        """청킹 레벨 선택"""
        if any(kw in query for kw in ["란", "이란", "정의"]):
            return "조전체"
        elif any(kw in query for kw in ["몇", "구체적으로"]):
            return "호단위"
        return "항단위"  # 기본값

    def _detect_intent(self, query: str) -> str:
        """질의 의도 파악"""
        if "?" in query:
            return "question"
        elif "찾아줘" in query or "알려줘" in query:
            return "search"
        return "general"
```

### Agent 2: Retrieval Agent

```python
# law_rag/agents/retrieval_agent.py

from ..core.neo4j_manager import Neo4jLawLoader

class RetrievalAgent:
    """하이브리드 검색 (벡터 + 그래프)"""

    def __init__(self, neo4j_config: dict):
        self.loader = Neo4jLawLoader(**neo4j_config)

    def search(self, query_data: dict, top_k: int = 5) -> list:
        """하이브리드 검색 실행"""

        embedding = query_data['embedding']
        chunk_level = query_data['chunk_level']

        with self.loader.driver.session() as session:
            # 1단계: 벡터 검색
            results = session.run("""
                CALL db.index.vector.queryNodes('vector', $top_k, $embedding)
                YIELD node, score
                WHERE node.chunk_level = $chunk_level
                RETURN node, score
                ORDER BY score DESC
            """, top_k=top_k, embedding=embedding, chunk_level=chunk_level)

            chunks = []
            for record in results:
                node = record['node']

                # 2단계: 그래프 탐색으로 컨텍스트 확장
                context = self._expand_context(session, node)

                chunks.append({
                    'content': node['content'],
                    'score': record['score'],
                    'metadata': {
                        'jo_title': context['jo_title'],
                        'law_name': context['law_name'],
                        'full_id': node['full_id']
                    },
                    'context': context
                })

            return chunks

    def _expand_context(self, session, chunk_node) -> dict:
        """그래프 탐색으로 상위/관련 정보 가져오기"""

        # HANG 노드에서 상위 JO, JANG 찾기
        result = session.run("""
            MATCH (hang:HANG {full_id: $full_id})
            MATCH (jo:JO)-[:CONTAINS]->(hang)
            OPTIONAL MATCH (jang:JANG)-[:CONTAINS*]->(jo)
            RETURN jo.title as jo_title,
                   jo.unit_number as jo_number,
                   jang.title as jang_title,
                   hang.law_name as law_name
        """, full_id=chunk_node['full_id'])

        return dict(result.single())
```

### Agent 3: Synthesis Agent

```python
# law_rag/agents/synthesis_agent.py

from openai import OpenAI  # 또는 LangChain

class SynthesisAgent:
    """검색 결과 종합 및 답변 생성"""

    def __init__(self, llm_config: dict):
        self.client = OpenAI(api_key=llm_config['api_key'])

    def generate_answer(self, query: str, chunks: list) -> dict:
        """최종 답변 생성"""

        # 검색된 조문들을 컨텍스트로 구성
        context = self._build_context(chunks)

        # LLM 프롬프트
        prompt = f"""
당신은 한국 법률 전문가입니다. 다음 법률 조문을 참고하여 질문에 답변하세요.

질문: {query}

관련 법률 조문:
{context}

답변 시 주의사항:
1. 반드시 제공된 법률 조문만 참고하세요
2. 조문 출처를 명시하세요 (예: "국토계획법 제20조 제1항에 따르면")
3. 법률 용어를 정확히 사용하세요
"""

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            'answer': response.choices[0].message.content,
            'sources': [c['metadata'] for c in chunks],
            'chunks_used': len(chunks)
        }

    def _build_context(self, chunks: list) -> str:
        """검색된 청크를 컨텍스트 문자열로 변환"""
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            meta = chunk['metadata']
            context_parts.append(
                f"{i}. {meta['law_name']} {meta['jo_title']}\n"
                f"   {chunk['content']}\n"
            )
        return "\n".join(context_parts)
```

---

## 🚀 빠른 시작 (3단계, 15분)

### 1단계: Django App 생성 및 core 복사 (5분)

```bash
# Django app 생성
cd your_django_project/
python manage.py startapp law_rag

# core 모듈 복사
cp -r django_migration/core law_rag/

# agents 폴더 생성 (Multi-Agent용)
mkdir law_rag/agents
touch law_rag/agents/__init__.py
```

### 2단계: Django Settings 설정 (5분)

`your_django_project/settings.py`에 추가:

```python
# INSTALLED_APPS에 추가
INSTALLED_APPS = [
    ...
    'law_rag',
]

# Neo4j 설정
NEO4J_CONFIG = {
    'uri': 'bolt://localhost:7687',
    'user': 'neo4j',
    'password': '11111111',  # ⚠️ 실제 비밀번호로 변경!
    'database': 'neo4j'
}

# 임베딩 모델
EMBEDDING_MODEL = 'jhgan/ko-sbert-sts'
EMBEDDING_DIM = 768

# LLM 설정 (Multi-Agent용)
LLM_CONFIG = {
    'api_key': 'your-openai-api-key',  # 또는 다른 LLM
    'model': 'gpt-4'
}
```

### 3단계: 의존성 설치 (5분)

```bash
pip install -r django_migration/requirements.txt
```

---

## 🗄️ Neo4j 스키마 (실제 구조)

### 계층 구조

```
LAW (법률/시행령/시행규칙)
 │
 ├── JANG (장) - 선택적, 24개
 │   └── JEOL (절) - 선택적, 22개
 │       └── JO (조) - 1,053개 ⚠️ 제목만 저장!
 │
 └── JO (조) - 94개 (장/절 없이 직접 연결)
     └── HANG (항) - 1,586개 ✓ 실제 조문 내용!
         └── HO (호) - 1,025개
             └── MOK (목) - 263개
```

### ⚠️ 중요: 내용 저장 위치

```
❌ JO 노드 content:
   "제20조(도시ㆍ군기본계획 수립을 위한 기초조사 및 공청회)"  ← 32자 (제목만!)

✓ HANG 노드 content:
   "도시ㆍ군기본계획을 수립하거나 변경하는 경우에는 제 치시장ㆍ특별자치도지사ㆍ시장 또는 군수로, 광역도시계획은 도시ㆍ군기본계획으로 본다..."  ← 수백 자 (실제 내용!)
```

**검색 대상:** JO 제목 검색이 아니라 **HANG/HO/MOK 내용 검색**이 핵심!

> 📖 상세 스키마는 `neo4j_schema.md` 참고

---

## 💻 사용 예시: Multi-Agent 통합

### Django View에서 Multi-Agent 사용

```python
# law_rag/views.py

from django.http import JsonResponse
from django.conf import settings
from .agents.query_agent import QueryAgent
from .agents.retrieval_agent import RetrievalAgent
from .agents.synthesis_agent import SynthesisAgent

# 에이전트 초기화 (싱글톤 패턴 권장)
query_agent = QueryAgent()
retrieval_agent = RetrievalAgent(settings.NEO4J_CONFIG)
synthesis_agent = SynthesisAgent(settings.LLM_CONFIG)

def multi_agent_search(request):
    """Multi-Agent RAG 검색 엔드포인트"""
    query = request.GET.get('q')

    # Agent 1: 질의 분석
    query_data = query_agent.analyze_query(query)
    print(f"선택된 청킹 레벨: {query_data['chunk_level']}")

    # Agent 2: 하이브리드 검색 (벡터 + 그래프)
    chunks = retrieval_agent.search(query_data, top_k=5)

    # Agent 3: 답변 생성
    result = synthesis_agent.generate_answer(query, chunks)

    return JsonResponse({
        'query': query,
        'answer': result['answer'],
        'sources': result['sources'],
        'chunk_level_used': query_data['chunk_level']
    })
```

---

## 📦 requirements.txt

```txt
# Neo4j
neo4j==5.14.1

# 임베딩 (필수!)
sentence-transformers>=2.2.0
torch>=2.0.0

# PDF 파싱
pdfplumber==0.10.3

# LLM (Multi-Agent용)
openai>=1.0.0
# 또는
# langchain>=0.1.0
# llama-index>=0.9.0

# 유틸리티
python-dotenv==1.0.0
numpy>=1.24.0
```

---

## ⚠️ 주의사항

### 1. Neo4j 연결 확인

```bash
# Neo4j 서버 실행 확인
neo4j status
neo4j start
```

### 2. 임베딩 모델 다운로드

- 첫 실행 시 모델 다운로드 (~500MB, 5~10분)
- GPU 사용 권장 (CPU는 느림)

### 3. 메모리 요구사항

- 임베딩 모델: ~2GB RAM
- Neo4j: 최소 4GB RAM
- LLM 호출: API 키 필요

---

## 📚 핵심 문서

| 문서 | 내용 |
|------|------|
| `neo4j_schema.md` | **실제 Neo4j 스키마 상세** (JANG, JEOL, MOK 포함) |
| `README.md` | 이 문서 (통합 가이드, Multi-Agent 아키텍처) |
| `examples/django_settings.py` | Django settings 전체 예시 |
| `examples/management_command.py` | Management command 구현 |

---

## 🎯 다음 단계: Multi-Agent 시스템 구현

### Phase 1: 기본 RAG (완료!)
- ✓ PDF 파싱
- ✓ Neo4j 그래프 저장
- ✓ 3단계 청킹 전략

### Phase 2: Vector Search (다음!)

**⭐ 임베딩 추가 스크립트 제공!**

Neo4j HANG 노드에 임베딩을 추가하는 스크립트가 준비되어 있습니다:

```bash
# 1. 환경 변수 설정 (.env 파일 생성)
cp .env.example .env
# NEO4J_PASSWORD를 실제 비밀번호로 수정

# 2. 필요한 패키지 설치
pip install -r requirements.txt

# 3. 임베딩 추가 실행
cd django_migration
python scripts/add_embeddings.py
```

스크립트가 자동으로:
- [ ] HANG 노드 1,586개의 content를 임베딩 (768차원)
- [ ] 각 HANG 노드에 embedding 속성 추가
- [ ] Neo4j Vector Index 생성 (`hang_embedding_index`)
- [ ] 검증 및 완료 확인

**예상 소요 시간**: 5-10분 (GPU 사용 시 2-3분)

완료 후 다음 작업:
- [ ] 벡터 검색 쿼리 구현
- [ ] 하이브리드 검색 (벡터 + 그래프) 테스트

### Phase 3: Multi-Agent RAG
- [ ] Query Agent 구현 (질의 분석, 청킹 레벨 선택)
- [ ] Retrieval Agent 구현 (하이브리드 검색)
- [ ] Synthesis Agent 구현 (LLM 답변 생성)

### Phase 4: 프로덕션
- [ ] Django REST API
- [ ] React/Vue Frontend
- [ ] Docker 컨테이너화
- [ ] 성능 최적화

---

## ✅ 체크리스트

Django 통합 전:
- [ ] Neo4j 서버 실행 중
- [ ] 임베딩 모델 다운로드 완료
- [ ] API 키 준비 (LLM 사용 시)

Django 통합 후:
- [ ] `law_rag` app 생성
- [ ] `core/` 모듈 복사
- [ ] `settings.py` 설정
- [ ] `requirements.txt` 설치
- [ ] Multi-Agent 클래스 구현
- [ ] API 엔드포인트 테스트

---

## 📚 참고 문서

프로젝트의 상세 기술 문서는 `docs/` 폴더에 있습니다:

| 문서 | 설명 | 필수 여부 |
|------|------|----------|
| [chunking_strategy.md](docs/chunking_strategy.md) | 3단계 청킹 전략 상세 설명 | ✅ 필수 |
| [neo4j_scaling_guide.md](docs/neo4j_scaling_guide.md) | Neo4j 스케일링 가이드 | ⚠️ 권장 |
| [PIPELINE_GUIDE.md](docs/PIPELINE_GUIDE.md) | PDF→JSON→Neo4j/RAG 파이프라인 | ✅ 필수 |
| [neo4j_schema.md](neo4j_schema.md) | Neo4j 스키마 (최신) | ✅ 필수 |

**읽기 순서 권장:**
1. `README.md` (현재 문서) - 전체 개요
2. `neo4j_schema.md` - 데이터 구조
3. `docs/chunking_strategy.md` - 청킹 전략
4. `docs/PIPELINE_GUIDE.md` - 파이프라인 이해
5. `docs/neo4j_scaling_guide.md` - 스케일링 (선택)

---

**작성일**: 2025-10-26
**최종 업데이트**: 2025-10-27
**프로젝트**: 한국 법률 Multi-Agent RAG 시스템
**검증**: ✓ 실제 국토계획법 시스템 (3,976 노드) 기반
**PDF 파싱**: ✓ 전체 내용 (550K 자) 완료
