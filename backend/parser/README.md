# parser/ - 문서 파싱 및 벡터 검색 API

## 개요
문서 파싱, 청킹, 벡터 검색, 그래프 쿼리 API. 범용 문서 처리 엔드포인트 제공.

## 핵심 기능
- 문서 업로드 및 파싱
- 텍스트 청킹
- 벡터 검색
- 그래프 쿼리
- 스키마 추출

---

## 파일 구조 및 역할

### views/ - API 뷰
| 파일 | 역할 | 핵심 함수 |
|------|------|----------|
| `documents.py` | 문서 처리 API | 문서 업로드, 파싱 |
| `vector.py` | 벡터 검색 API | 유사도 검색 |
| `graph.py` | 그래프 쿼리 API | Cypher 쿼리 |
| `extraction.py` | 정보 추출 API | 엔티티 추출 |
| `schema.py` | 스키마 API | 스키마 추출/관리 |
| `health.py` | 헬스체크 API | 시스템 상태 |
| `metrics.py` | 메트릭 API | 통계 정보 |
| `chat.py` | 채팅 API | 대화형 검색 |
| `helpers.py` | 헬퍼 함수 | 유틸리티 |

### tests/ - 테스트
| 파일 | 역할 |
|------|------|
| `test_documents.py` | 문서 API 테스트 |
| `test_health.py` | 헬스체크 테스트 |
| `test_schema.py` | 스키마 API 테스트 |

### 루트 파일
| 파일 | 역할 |
|------|------|
| `urls.py` | URL 라우팅 |
| `models.py` | 모델 (현재 비어있음) |
| `views_backup.py` | 뷰 백업 |

---

## API 엔드포인트 (예상)

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/parser/documents/` | POST | 문서 업로드 |
| `/parser/vector/search/` | POST | 벡터 검색 |
| `/parser/graph/query/` | POST | 그래프 쿼리 |
| `/parser/schema/` | GET | 스키마 조회 |
| `/parser/health/` | GET | 헬스체크 |
| `/parser/metrics/` | GET | 메트릭 |

---

## 사용 예시
```python
# 문서 업로드
POST /parser/documents/
{
    "file": <PDF/TXT 파일>,
    "options": {"chunk_size": 500}
}

# 벡터 검색
POST /parser/vector/search/
{
    "query": "토지 보상 절차",
    "limit": 10
}
```

## 의존성
- 문서 파싱 라이브러리
- 벡터 검색 엔진
- Neo4j 그래프 DB
