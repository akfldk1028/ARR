# src/ - LLM 그래프 빌더 유틸리티

## 개요
LLM 기반 지식 그래프 생성 유틸리티. 문서 소스, 청킹, 엔티티 추출, 관계 생성, RAG 평가 도구.

## 핵심 기능
- 다양한 문서 소스 지원 (S3, GCS, YouTube, Wikipedia)
- LLM 기반 엔티티/관계 추출
- 청킹 및 커뮤니티 감지
- RAGAS 기반 평가

---

## 파일 구조 및 역할

### 루트 파일
| 파일 | 역할 | 핵심 함수/클래스 |
|------|------|-----------------|
| `main.py` | 메인 진입점 | 파이프라인 실행 |
| `llm.py` | LLM 클라이언트 | `LLMClient` |
| `create_chunks.py` | 청킹 로직 | `create_chunks()` |
| `make_relationships.py` | 관계 생성 | `extract_relationships()` |
| `neighbours.py` | 이웃 탐색 | `get_neighbours()` |
| `communities.py` | 커뮤니티 감지 | `detect_communities()` |
| `post_processing.py` | 후처리 | 정규화, 정리 |
| `graph_query.py` | 그래프 쿼리 | Cypher 쿼리 |
| `graphDB_dataAccess.py` | DB 접근 | `GraphDBDataAccess` |
| `QA_integration.py` | QA 통합 | 질의응답 |
| `ragas_eval.py` | RAGAS 평가 | `evaluate_rag()` |
| `diffbot_transformer.py` | Diffbot 변환 | 외부 NER |
| `chunkid_entities.py` | 청크-엔티티 매핑 | |
| `api_response.py` | API 응답 포맷 | 표준 응답 |
| `logger.py` | 로깅 설정 | 구조화 로깅 |

### document_sources/ - 문서 소스
| 파일 | 역할 |
|------|------|
| `local_file.py` | 로컬 파일 소스 |
| `s3_bucket.py` | AWS S3 소스 |
| `gcs_bucket.py` | Google Cloud Storage 소스 |
| `web_pages.py` | 웹페이지 소스 |
| `youtube.py` | YouTube 소스 |
| `wikipedia.py` | Wikipedia 소스 |

### entities/ - 엔티티 모델
| 파일 | 역할 |
|------|------|
| `source_node.py` | 소스 노드 정의 |
| `user_credential.py` | 사용자 인증 정보 |

### shared/ - 공유 유틸리티
| 파일 | 역할 |
|------|------|
| `common_fn.py` | 공통 함수 |
| `constants.py` | 상수 정의 |
| `llm_graph_builder_exception.py` | 커스텀 예외 |
| `schema_extraction.py` | 스키마 추출 |

---

## 파이프라인 흐름

```
Document Source (S3/GCS/Web/YouTube)
        ↓
    Text Extraction
        ↓
    Chunking (create_chunks.py)
        ↓
    Entity Extraction (LLM)
        ↓
    Relationship Extraction (make_relationships.py)
        ↓
    Graph Storage (Neo4j)
        ↓
    Community Detection (communities.py)
        ↓
    QA Integration (QA_integration.py)
        ↓
    Evaluation (ragas_eval.py)
```

## 사용 예시
```python
from src.main import build_graph
from src.document_sources.local_file import LocalFileSource

source = LocalFileSource("document.pdf")
graph = build_graph(source)
```

## 의존성
- `openai`: LLM API
- `langchain`: 문서 로더
- `neo4j`: 그래프 저장
- `ragas`: RAG 평가
