# Law App 임베딩 가이드

## 현재 상태 정리

### Parser App vs Law App 임베딩 비교

| App | 현재 모델 | 차원 | 방식 | 비용 |
|-----|----------|------|------|------|
| **Parser** | all-MiniLM-L6-v2 | 384 | 로컬 (HuggingFace) | 무료 |
| **Law (기존)** | ko-sbert-sts | 768 | 로컬 (Sentence-Transformers) | 무료 |
| **Law (v2)** | 선택 가능 | 384-1536 | 로컬 또는 OpenAI API | 무료/유료 |

**중요**: 둘 다 GPT를 사용하지 않습니다! 모두 로컬 모델입니다.

## Law App 임베딩 모델 선택 가이드

### 1. ko-sbert-sts (기본값, 권장)
```bash
# .env 설정
LAW_EMBEDDING_MODEL=ko-sbert
```

**장점**:
- ✅ 한국어 법률 문서에 최적화
- ✅ 768 차원 (좋은 정확도)
- ✅ 완전 무료 (API 호출 없음)
- ✅ 오프라인 작동 가능

**단점**:
- ❌ 초기 모델 다운로드 (~500MB)
- ❌ 첫 실행 시 시간 소요

**추천 상황**: 대부분의 경우 (한국어 법률 문서)

### 2. OpenAI text-embedding-3-large
```bash
# .env 설정
LAW_EMBEDDING_MODEL=openai
OPENAI_API_KEY=sk-...  # 필수
```

**장점**:
- ✅ 최고 성능 (3072 차원)
- ✅ 다국어 지원 우수
- ✅ 업데이트 자동
- ✅ 가장 큰 임베딩 차원 (3072)

**단점**:
- ❌ API 호출마다 비용 발생 ($0.13 per 1M tokens)
- ❌ 1,586개 HANG 노드 임베딩 시 약 $0.50-1.00
- ❌ 인터넷 연결 필수
- ❌ 속도 느림 (네트워크 지연)
- ❌ 큰 차원 (저장 공간 많이 사용)

**추천 상황**: 최고 성능 필요 + 예산 있음

### 3. OpenAI text-embedding-3-small
```bash
# .env 설정
LAW_EMBEDDING_MODEL=openai-small
OPENAI_API_KEY=sk-...  # 필수
```

**장점**:
- ✅ 저렴한 비용 ($0.02 per 1M tokens)
- ✅ 1536 차원 (large보다 절반)
- ✅ 빠른 속도
- ✅ 작은 저장 공간

**단점**:
- ❌ large 모델보다 성능 낮음
- ❌ API 비용 발생 (약 $0.10)
- ❌ 인터넷 연결 필수

**추천 상황**: OpenAI 사용하되 비용 절약

### 4. all-MiniLM-L6-v2 (Parser App 기본값)
```bash
# .env 설정
LAW_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

**장점**:
- ✅ 완전 무료
- ✅ 빠른 속도
- ✅ 작은 모델 크기 (~100MB)

**단점**:
- ❌ 384 차원 (낮은 정확도)
- ❌ 한국어 최적화 안 됨
- ❌ 법률 문서에 부적합

**추천 상황**: 빠른 테스트용, 영어 문서

## 사용 방법

### 기존 임베딩 사용 (ko-sbert-sts)
```bash
# 이미 실행했으므로 다시 할 필요 없음
.venv\Scripts\python.exe law\scripts\add_embeddings.py
```

### 새 임베딩 시스템 사용 (v2)

#### Option 1: 기본값 (ko-sbert-sts)
```bash
# .env에서 확인
LAW_EMBEDDING_MODEL=ko-sbert

# 실행 (기존 임베딩 덮어쓰기)
.venv\Scripts\python.exe law\scripts\add_embeddings_v2.py
```

#### Option 2: OpenAI 고성능 (유료)
```bash
# .env 수정
LAW_EMBEDDING_MODEL=openai
OPENAI_API_KEY=sk-proj-...

# Neo4j 임베딩 삭제 (차원이 달라서)
MATCH (h:HANG) SET h.embedding = null

# 벡터 인덱스 삭제
DROP INDEX hang_embedding_index

# 새 임베딩 추가
.venv\Scripts\python.exe law\scripts\add_embeddings_v2.py

# 예상 비용: $0.50 ~ $1.00
```

#### Option 3: OpenAI 저렴 (유료)
```bash
# .env 수정
LAW_EMBEDDING_MODEL=openai-small

# 위와 동일한 절차
# 예상 비용: $0.08 ~ $0.15
```

## 임베딩 비교 테스트

### 성능 비교 (예상치)

| 모델 | 한국어 법률 정확도 | 속도 | 비용 (1,586개) |
|------|------------------|------|---------------|
| ko-sbert-sts | 90% | 35초 | $0 |
| openai (large) | 95% | 2-3분 | $0.50-1.00 |
| openai-small | 92% | 1-2분 | $0.08-0.15 |
| all-MiniLM-L6-v2 | 75% | 20초 | $0 |

**결론**: 한국어 법률 문서에는 **ko-sbert-sts**가 가성비 최고

## 현재 설정 확인

```bash
# Neo4j Browser에서 실행
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
RETURN size(h.embedding) as dimension, count(h) as count

# 결과 해석:
# dimension = 768 → ko-sbert-sts
# dimension = 3072 → OpenAI text-embedding-3-large (현재 설정)
# dimension = 1536 → OpenAI text-embedding-3-small
# dimension = 384 → all-MiniLM-L6-v2
```

## FAQ

### Q1: 기존 임베딩을 OpenAI로 바꿔야 할까요?
**A**: 아니요. ko-sbert-sts가 한국어 법률 문서에 충분히 좋습니다.
OpenAI는 비용이 들고, 한국어 법률 도메인에서 큰 성능 차이 없을 수 있습니다.

### Q2: Parser app과 Law app을 같은 모델로 통일해야 하나요?
**A**: 필요 없습니다. 각 app의 목적이 다릅니다:
- Parser: 일반 문서 파싱 (all-MiniLM-L6-v2)
- Law: 한국어 법률 검색 (ko-sbert-sts)

### Q3: 임베딩을 바꾸면 기존 데이터는?
**A**: Neo4j에서 기존 임베딩을 삭제하고 다시 생성해야 합니다.
벡터 인덱스도 차원이 달라지면 재생성 필요합니다.

### Q4: 비용 절약하려면?
**A**: ko-sbert-sts 또는 all-MiniLM-L6-v2 사용 (무료)

### Q5: 최고 성능이 필요하다면?
**A**: OpenAI text-embedding-3-large 사용 (유료)
단, 한국어 법률에서 ko-sbert-sts와 차이가 크지 않을 수 있음

## 추천 시나리오별 선택

| 상황 | 추천 모델 | 이유 |
|------|----------|------|
| 한국어 법률 검색 (기본) | ko-sbert-sts | 한국어 특화, 무료, 충분한 성능 |
| 영어 문서 혼합 | openai | 다국어 지원 우수 |
| 프로토타입/테스트 | all-MiniLM-L6-v2 | 빠르고 가벼움 |
| 프로덕션 (고성능) | openai-large | 최고 성능 (비용 감수) |
| 프로덕션 (가성비) | ko-sbert-sts | 무료 + 한국어 최적화 |

## 결론

**현재 상태: OpenAI text-embedding-3-large (3072 차원) 적용 완료!**

✅ **완료된 작업**:
- 1,586개 HANG 노드에 OpenAI 임베딩 추가
- 3072 차원 벡터 인덱스 생성
- 비용: 약 $0.50-1.00 (API 호출)

**성능 특징**:
- 최고 품질 임베딩 (3072 차원)
- 다국어 지원 우수
- 한국어 법률 문서에 높은 정확도 예상

**주의사항**:
- ko-sbert-sts (768 차원, 무료)와 비교하여 성능 차이가 크지 않을 수 있음
- 향후 임베딩 재생성 시 API 비용 발생
- 큰 차원 크기로 저장 공간 많이 사용 (768의 4배)

**ko-sbert-sts로 되돌리려면**:
1. .env에서 `LAW_EMBEDDING_MODEL=ko-sbert` 변경
2. `python clean_embeddings_for_openai.py` 실행
3. `python law/scripts/add_embeddings_v2.py` 실행
4. 비용: 무료
