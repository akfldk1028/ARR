# TASK.md - 작업 목록 및 진행상황

> **프로젝트**: 법규 Graph Node Multi-Agent 검색 시스템
> **마지막 업데이트**: 2025-11-14

---

## 현재 상태 요약

| 항목 | 상태 |
|------|------|
| **Neo4j 데이터** | ✅ 1,477 HANG 노드, 5 도메인 |
| **임베딩** | ✅ OpenAI 3072-dim 완료 |
| **Multi-Agent 시스템** | ✅ 5개 DomainAgent 운영 중 |
| **검색 API** | ✅ Hybrid + RNE 동작 |
| **WebSocket 채팅** | ✅ Daphne ASGI |

---

## 우선순위 작업

### P0 - 긴급 (이번 주)

| ID | 작업 | 상태 | 담당 | 비고 |
|----|------|------|------|------|
| T001 | - | - | - | - |

### P1 - 중요 (이번 달)

| ID | 작업 | 상태 | 담당 | 비고 |
|----|------|------|------|------|
| T101 | 검색 성능 벤치마크 | 📋 TODO | - | evaluation/ 활용 |
| T102 | 추가 법률 데이터 적재 | 📋 TODO | - | 건축법, 주택법 등 |
| T103 | 도메인 자동 분할/병합 테스트 | 📋 TODO | - | MIN_SIZE=50, MAX_SIZE=500 |

### P2 - 개선 (백로그)

| ID | 작업 | 상태 | 담당 | 비고 |
|----|------|------|------|------|
| T201 | RNE threshold 튜닝 | 📋 TODO | - | 현재 0.75 |
| T202 | A2A 협업 로직 개선 | 📋 TODO | - | quality_score 계산 |
| T203 | 캐싱 레이어 추가 | 📋 TODO | - | Redis 검토 |
| T204 | 검색 결과 UI 개선 | 📋 TODO | - | frontend 연동 |

---

## 완료된 작업

### 2025-11

| ID | 작업 | 완료일 | 비고 |
|----|------|--------|------|
| D001 | 프로젝트 문서화 | 2025-11-14 | README 26개 작성 |
| D002 | AI_INDEX.md 작성 | 2025-11-14 | 전체 시스템 가이드 |
| D003 | README_INDEX.md 작성 | 2025-11-14 | 문서 인덱스 |

### 이전

| ID | 작업 | 완료일 | 비고 |
|----|------|--------|------|
| D100 | Neo4j 스키마 설계 | - | LAW→JO→HANG→HO |
| D101 | 데이터 파이프라인 구축 | - | law/STEP/ |
| D102 | OpenAI 임베딩 적용 | - | 3072-dim |
| D103 | Multi-Agent 시스템 구현 | - | AgentManager, DomainAgent |
| D104 | Hybrid Search 구현 | - | Exact + Semantic + Rel |
| D105 | SemanticRNE 구현 | - | graph_db/algorithms/ |
| D106 | A2A 협업 구현 | - | asyncio.gather() |
| D107 | WebSocket 채팅 | - | Django Channels |

---

## 알려진 이슈

| ID | 이슈 | 심각도 | 상태 | 비고 |
|----|------|--------|------|------|
| I001 | - | - | - | - |

---

## 기술 부채

| ID | 항목 | 우선순위 | 비고 |
|----|------|----------|------|
| TD01 | agents/deprecated/ 정리 | 낮음 | 미사용 코드 |
| TD02 | 테스트 커버리지 확대 | 중간 | 현재 낮음 |
| TD03 | 에러 핸들링 강화 | 중간 | 특히 Neo4j 연결 |
| TD04 | 로깅 개선 | 낮음 | structlog 검토 |

---

## 노트

### 시스템 운영 명령어

```bash
# 서버 시작
daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# Neo4j 연결 확인
python -c "from graph_db.services import get_neo4j_service; print(get_neo4j_service().execute_query('RETURN 1'))"

# 데이터 파이프라인 전체 실행
cd law/STEP && python run_all.py

# 검색 테스트
curl -X POST http://localhost:8000/agents/law/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "17조 검색", "limit": 5}'
```

### 주요 설정값

| 항목 | 현재값 | 위치 |
|------|--------|------|
| RNE Threshold | 0.75 | domain_agent.py |
| MIN_AGENT_SIZE | 50 | agent_manager.py |
| MAX_AGENT_SIZE | 500 | agent_manager.py |
| DOMAIN_SIMILARITY_THRESHOLD | 0.70 | agent_manager.py |
| RRF k값 | 60 | domain_agent.py |
| 벡터 차원 (OpenAI) | 3072 | 전체 |
| 벡터 차원 (KR-SBERT) | 768 | RNE sibling |

### 참고 자료

- GraphTeam/GraphAgent-Reasoner 논문
- [law/SYSTEM_GUIDE.md](./law/SYSTEM_GUIDE.md) - 법률 시스템 가이드
- [LAW_SEARCH_SYSTEM_ARCHITECTURE.md](./LAW_SEARCH_SYSTEM_ARCHITECTURE.md) - 검색 아키텍처

---

## 작업 템플릿

```markdown
### [작업 제목]

**상태**: 📋 TODO | 🔄 진행중 | ✅ 완료 | ⏸️ 보류 | ❌ 취소
**우선순위**: P0 | P1 | P2
**담당자**: -
**예상 시간**: -

#### 설명
[작업 상세 설명]

#### 체크리스트
- [ ] 항목 1
- [ ] 항목 2

#### 관련 파일
- `path/to/file.py`

#### 완료 기준
- 기준 1
- 기준 2
```

---

**상태 아이콘**:
- 📋 TODO
- 🔄 진행중
- ✅ 완료
- ⏸️ 보류
- ❌ 취소
- 🐛 버그
- 💡 아이디어
