# MAS (Multi-Agent System) 사용 가이드

**작성일**: 2025-11-02
**목적**: 법률 MAS 사용 방법 (완전 자동화)

---

## 핵심 질문: "수동으로 때려넣어야 하나?"

### 답변: **아니요! 완전 자동화됩니다.** ✅

---

## 1. 기존 데이터 → 완전 자동 (서버 시작 시)

### 작동 방식:

```python
# 서버 시작 시 LawCoordinatorWorker 초기화
# agents/worker_agents/implementations/law_coordinator_worker.py:62

def __init__(self, agent_slug, agent_config):
    self.agent_manager = AgentManager()
    self._initialize_domains()  # ← 자동 실행!

def _initialize_domains(self):
    # [1] Neo4j에서 기존 HANG 노드 자동 로드
    query = "MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN h LIMIT 3000"

    # [2] 임베딩 캐시에 로드
    embeddings = {hang_id: np.array(embedding) for ...}

    # [3] 자동 도메인 할당
    assignments = self.agent_manager._assign_to_agents(hang_ids, embeddings)

    # [4] 도메인 자동 생성
    # - 유사도 >= 0.85: 기존 도메인에 추가
    # - 유사도 < 0.85: 새 도메인 생성 (LLM으로 이름 자동 생성)
    # - 크기 > 300: 자동 분할
    # - 크기 < 50: 자동 병합
```

### 결과:

```
✅ 서버 시작만 하면 자동으로:
1. 기존 HANG 노드 로드
2. 도메인 자동 분류
3. DomainAgent 인스턴스 생성
4. A2A 네트워크 구성

아무것도 안 해도 됩니다!
```

### 확인 방법:

```bash
# 서버 시작
daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# 로그 확인
[INFO] AgentManager initialized
[INFO] Initializing domains from existing HANG nodes...
[INFO] Found 2987 existing HANG nodes
[INFO] ✅ Initialized 5 domains from 2987 HANG nodes
[INFO]    - 도시계획: 1245 nodes
[INFO]    - 건축규제: 987 nodes
[INFO]    - 토지이용: 755 nodes
```

---

## 2. 새 PDF 추가 → 완전 자동 (API 호출)

### 방법 1: Web UI 업로드 (가장 쉬움)

**엔드포인트**: `POST /agents/law/upload-pdf/`

```bash
# curl로 테스트
curl -X POST http://localhost:8000/agents/law/upload-pdf/ \
  -F "file=@D:/laws/건축법.pdf"

# 응답 (자동 처리 완료!)
{
  "success": true,
  "law_name": "건축법",
  "hang_count": 245,
  "domains_touched": 3,
  "new_domains": ["건축규제", "안전기준"],
  "total_domains": 7,
  "duration_seconds": 12.5
}
```

**처리 과정 (완전 자동)**:
1. ✅ PDF 텍스트 추출
2. ✅ 법률 파싱 (HANG 단위)
3. ✅ Neo4j 저장
4. ✅ 임베딩 생성
5. ✅ 도메인 자동 할당
   - 기존 도메인과 유사도 계산
   - 유사도 >= 0.85 → 기존 도메인 추가
   - 유사도 < 0.85 → 새 도메인 생성 (LLM 자동 이름 생성)
6. ✅ DomainAgent 자동 생성/업데이트
7. ✅ A2A 네트워크 재구성

**아무것도 수동으로 할 필요 없음!**

### 방법 2: Python 스크립트

```python
# scripts/upload_law_pdf.py
from agents.law.agent_manager import AgentManager

manager = AgentManager()
result = manager.process_new_pdf("D:/laws/건축법.pdf")

print(f"✅ 처리 완료!")
print(f"   법률: {result['law_name']}")
print(f"   조항: {result['hang_count']}개")
print(f"   도메인: {result['domains_touched']}개 영향")
```

### 방법 3: Django Admin (향후 구현 가능)

```python
# admin.py에 추가
class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField()

@admin.register(LawDocument)
class LawDocumentAdmin(admin.ModelAdmin):
    # 파일 업로드 시 자동으로 process_new_pdf() 호출
    ...
```

---

## 3. 도메인 확인

### 현재 도메인 목록 조회:

```bash
# API 호출
curl http://localhost:8000/agents/law/domains/

# 응답
{
  "domains": [
    {
      "domain_id": "domain_001",
      "domain_name": "도시계획",
      "node_count": 1245,
      "neighbor_count": 2,
      "created_at": "2025-11-02T10:30:00",
      "last_updated": "2025-11-02T10:35:00"
    },
    {
      "domain_id": "domain_002",
      "domain_name": "건축규제",
      "node_count": 987,
      "neighbor_count": 3
    }
  ],
  "total_domains": 5,
  "total_nodes": 2987
}
```

---

## 4. 법률 검색 사용

### A2A 시스템 통합:

```bash
# LawCoordinatorWorker를 통한 검색
POST /agents/law-coordinator/chat/

Body:
{
  "query": "도시지역 용적률 기준은?",
  "session_id": "test-session"
}

# 응답 (자동으로 적절한 도메인 라우팅)
{
  "response": "'도시지역 용적률 기준은?'에 대한 도시계획 관련 법률 정보입니다.

  [핵심 조항]
  1. 국토의 계획 및 이용에 관한 법률 > 제2장 > 제12조 > 제1항 (유사도: 0.89)
     도시지역 내 건축물의 용적률은 해당 지역의 특성을 고려하여...

  2. 국토의 계획 및 이용에 관한 법률 시행령 > 제3조 (유사도: 0.85)
     법 제12조에 따른 용적률 산정 기준은 다음과 같다...

  [검색 통계]
  총 10개 조항 발견
  - 벡터 검색: 5개
  - 그래프 확장: 3개
  - Cross-law: 2개"
}
```

---

## 5. 전체 워크플로우

### 초기 설정 (1회만):

```bash
# 1. 서버 시작
daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# ✅ 자동으로:
# - AgentManager 초기화
# - 기존 HANG 노드 로드
# - 도메인 자동 생성
# - DomainAgent 인스턴스 생성
```

### 법률 추가 (언제든지):

```bash
# 방법 1: API 업로드 (권장)
curl -X POST http://localhost:8000/agents/law/upload-pdf/ \
  -F "file=@D:/laws/건축법.pdf"

# 방법 2: Python 스크립트
python scripts/upload_law_pdf.py D:/laws/건축법.pdf

# ✅ 자동으로:
# - PDF 파싱
# - Neo4j 저장
# - 임베딩 생성
# - 도메인 할당 (기존/신규 자동 판단)
# - DomainAgent 업데이트
```

### 법률 검색 (사용자):

```bash
# A2A 시스템 통합
POST /agents/law-coordinator/chat/
Body: {"query": "용적률 기준"}

# ✅ 자동으로:
# - 쿼리 임베딩 생성
# - 적절한 도메인 자동 선택
# - DomainAgent 검색 실행
# - RNE/INE 알고리즘 적용
# - Cross-law 참조
# - 결과 포맷팅
```

---

## 6. 자동화 수준 비교

| 작업 | 수동 필요? | 자동화 수준 |
|------|----------|----------|
| **서버 시작 시 도메인 생성** | ❌ 없음 | ✅ **100% 자동** |
| **새 PDF 업로드** | ⚠️ API 호출 | ✅ **95% 자동** (파일만 올리면 끝) |
| **도메인 분류** | ❌ 없음 | ✅ **100% 자동** (유사도 기반) |
| **도메인 이름 생성** | ❌ 없음 | ✅ **100% 자동** (LLM 사용) |
| **도메인 분할/병합** | ❌ 없음 | ✅ **100% 자동** (크기 기반) |
| **DomainAgent 생성** | ❌ 없음 | ✅ **100% 자동** |
| **A2A 네트워크 구성** | ❌ 없음 | ✅ **100% 자동** |
| **법률 검색** | ⚠️ 질의만 | ✅ **100% 자동** (라우팅, 검색, 협업) |

**결론**: PDF 파일만 업로드하면 **모든 것이 자동**입니다!

---

## 7. 예시: 20개 법률 추가

### 시나리오: 건축법, 주택법, 산업입지법 등 20개 추가

```bash
# 1. PDF 일괄 업로드 스크립트
cat > upload_all_laws.sh << 'EOF'
#!/bin/bash
for pdf in D:/laws/*.pdf; do
  echo "Uploading: $pdf"
  curl -X POST http://localhost:8000/agents/law/upload-pdf/ \
    -F "file=@$pdf"
  echo ""
done
EOF

chmod +x upload_all_laws.sh
./upload_all_laws.sh

# ✅ 자동으로:
# - 20개 PDF 파싱
# - 15개 도메인 자동 생성 (유사도 기반)
# - 15개 DomainAgent 인스턴스 생성
# - A2A 네트워크 45개 연결 구성
```

### 결과:

```
✅ 처리 완료!

도메인 목록:
1. 도시계획 (1,245 nodes)
2. 건축규제 (987 nodes)
3. 토지이용 (755 nodes)
4. 주거환경 (834 nodes)
5. 산업시설 (621 nodes)
6. 개발행위 (512 nodes)
7. 용적률관리 (456 nodes)
... (총 15개 도메인)

총 조항: 8,734개
A2A 네트워크: 45개 연결

검색 준비 완료!
```

**수동 작업**: PDF 파일 업로드만 (20번 클릭)
**자동 작업**: 나머지 모든 것 (파싱, 분류, 에이전트 생성, 네트워크 구성)

---

## 8. 유지보수

### 도메인 재구성 (필요 시):

```python
# 도메인이 너무 커졌을 때 (자동 분할)
# - 300개 초과 → K-means로 2개 도메인 분할
# - 자동 실행됨!

# 도메인이 너무 작을 때 (자동 병합)
# - 50개 미만 → 가장 유사한 도메인과 병합
# - 자동 실행됨!

# 수동 개입 불필요!
```

### 모니터링:

```bash
# 도메인 현황 확인
curl http://localhost:8000/agents/law/domains/

# 로그 확인
tail -f agents/logs/agent_communication_*.json
```

---

## 9. FAQ

**Q: PDF 업로드할 때마다 스크립트 실행해야 하나요?**
A: 아니요! API 호출만 하면 됩니다. `POST /agents/law/upload-pdf/`

**Q: 도메인 이름을 수동으로 정해야 하나요?**
A: 아니요! GPT-4o-mini가 자동으로 생성합니다.

**Q: 도메인이 많아지면 수동으로 관리해야 하나요?**
A: 아니요! 자동으로 분할/병합됩니다.

**Q: 법률 검색 시 어느 도메인을 선택할지 지정해야 하나요?**
A: 아니요! LawCoordinatorWorker가 자동으로 라우팅합니다.

**Q: A2A 네트워크를 수동으로 구성해야 하나요?**
A: 아니요! cross_law 관계 기반으로 자동 구성됩니다.

---

## 10. 다음 단계

### 완전 자동화 확인:

```bash
# 1. 서버 시작
daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# 2. PDF 업로드 테스트
curl -X POST http://localhost:8000/agents/law/upload-pdf/ \
  -F "file=@law/data/raw/04_국토의\ 계획\ 및\ 이용에\ 관한\ 법률\(법률\).pdf"

# 3. 도메인 확인
curl http://localhost:8000/agents/law/domains/

# 4. 법률 검색 테스트
curl -X POST http://localhost:8000/agents/law-coordinator/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "도시지역 용적률", "session_id": "test"}'
```

**모든 것이 자동입니다!** 🎉
