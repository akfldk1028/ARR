# MAS 자가 조직화 시스템 분석 및 문제점

**작성일**: 2025-11-02
**상태**: ✅ **RESOLVED (2025-11-03)** - 해결 완료
**해결 문서**: [2025-11-03-MAS_SELF_ORGANIZING_FIX_COMPLETE.md](./2025-11-03-MAS_SELF_ORGANIZING_FIX_COMPLETE.md)

---

## 🎯 핵심 질문

> **"지금 MAS가 정말 자가 조직화(Self-Organizing)인가, 아니면 5개로 픽스(고정)된 건가?"**

**답변 (2025-11-03)**: 5개로 고정되어 있었음 → **완전히 수정 완료!**
- 임베딩 로딩 버그 수정
- 자동 재구성 트리거 추가
- 5개 → 13개 도메인 자동 생성 성공

---

## 📊 현재 상태 분석

### 1. 도메인 생성 방식

#### 초기 생성 (K-means 클러스터링)
```python
# agent_manager.py line 216-219
if not self.domains and len(hang_ids) > 100:
    logger.info(f"First-time clustering: using K-means on {len(hang_ids)} nodes")
    return self._kmeans_initial_clustering(hang_ids, embeddings)
```

**결과**:
- ✅ Silhouette score로 최적 k 선택 (5~15 범위)
- ✅ 초기 2,987개 HANG 노드 → 5개 도메인 생성 (최적)
- ✅ 각 도메인에 centroid 계산

**문제**:
- ⚠️ **One-time clustering**: 처음 한 번만 실행
- ⚠️ 이후 새 법률이 추가되어야만 동적 생성 작동
- ⚠️ 현재는 **5개로 고정**된 상태

---

### 2. 동적 할당 메커니즘

#### 새 HANG 노드 추가 시
```python
# agent_manager.py line 224-253
for hang_id in hang_ids:
    # 기존 도메인과 유사도 계산
    best_domain, similarity = self._find_best_domain(embedding)

    if similarity >= self.DOMAIN_SIMILARITY_THRESHOLD:  # 0.70
        # 기존 도메인에 추가
        best_domain.add_node(hang_id)

        # ✅ 크기 체크 및 분할
        if best_domain.size() > self.MAX_AGENT_SIZE:  # 500
            self._split_agent(best_domain)
    else:
        # ✅ 새 도메인 생성
        new_domain = self._create_new_domain([hang_id], [embedding])
```

**동작 조건**:
1. **기존 도메인에 추가**: similarity >= 0.70
2. **새 도메인 생성**: similarity < 0.70
3. **도메인 분할**: size > 500

**현재 상황**:
- ❌ 새 법률이 추가되지 않음 → 동적 할당 미작동
- ❌ 도메인 크기가 500 이하 → 분할 미작동
- ✅ 코드는 존재하지만 **실제로 실행되지 않음**

---

### 3. 분할/병합 메커니즘

#### 분할 (Split)
```python
# agent_manager.py line 519-560
def _split_agent(self, domain: DomainInfo):
    """도메인 크기 > 500이면 K-means로 2개로 분할"""
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    # 2개의 새 도메인 생성
    domain_0 = self._create_new_domain(cluster_0, embeddings_0)
    domain_1 = self._create_new_domain(cluster_1, embeddings_1)

    # 원래 도메인 삭제
    del self.domains[domain.domain_id]
```

**현재 도메인 크기** (2025-11-02 기준):
```
시설설치 위치 및 기준: 728 nodes  ⚠️ 500 초과!
토지 및 건축 제한: 236 nodes
도시 정비 및 재건축: 1,291 nodes  ⚠️ 500 초과!
도시계획 및 토지이용: 686 nodes   ⚠️ 500 초과!
일반 행정 절차: 46 nodes
```

**❗ 문제 발견**:
- 3개 도메인이 **500 초과**함
- 그런데 **분할이 안 일어남**
- 이유: `_assign_to_agents()`가 호출되지 않음

#### 병합 (Merge)
```python
# agent_manager.py line 562-598
def _merge_agents(self, domain_a: DomainInfo, domain_b: DomainInfo):
    """작은 도메인들 병합 (size < 50)"""
    for node_id in domain_b.node_ids:
        domain_a.add_node(node_id)

    # domain_b 삭제
    del self.domains[domain_b.domain_id]
```

**현재 상황**:
- "일반 행정 절차": 46 nodes (50 미만)
- 하지만 **병합이 안 일어남**
- 이유: `_merge_agents()` 호출 로직이 없음

---

## 🚨 핵심 문제점

### 문제 1: 초기 클러스터링만 실행
```
Initial State:
  2,987 HANG nodes
      ↓ K-means (one-time)
  5 domains (optimal)

Current State (여전히 5개):
  시설설치: 728 nodes  ← 500 초과!
  토지제한: 236 nodes
  도시정비: 1,291 nodes  ← 500 초과!
  도시계획: 686 nodes    ← 500 초과!
  행정절차: 46 nodes    ← 50 미만 (병합 대상)

Expected (자가 조직화라면):
  시설설치 → 2개로 분할
  도시정비 → 3개로 분할
  도시계획 → 2개로 분할
  행정절차 → 다른 도메인에 병합

  → 총 8-10개 도메인으로 자동 재구성되어야 함
```

### 문제 2: 재구성 트리거 없음
```python
# 현재 코드
def _assign_to_agents():
    # 처음만 K-means
    if not self.domains and len(hang_ids) > 100:
        return self._kmeans_initial_clustering()

    # 이후: 순차 할당 (새 노드가 들어올 때만)
    for hang_id in hang_ids:
        ...

# ❌ 문제: 초기 5개 생성 후, 재구성 트리거가 없음!
```

**트리거가 필요한 시점**:
1. 도메인 크기 > 500 → 자동 분할
2. 도메인 크기 < 50 → 자동 병합
3. 주기적 재클러스터링 (예: 매달)

**현재**:
- ❌ 자동 분할 트리거 없음
- ❌ 자동 병합 트리거 없음
- ❌ 주기적 재클러스터링 없음

### 문제 3: `process_new_pdf()` 미사용
```python
# agent_manager.py line 135
def process_new_pdf(self, pdf_path: str) -> Dict:
    """
    새 PDF 자동 처리:
    1. PDF 파싱
    2. 임베딩 생성
    3. 도메인 자동 할당 (_assign_to_agents 호출!)
    4. Neo4j 저장
    """
```

**현재 상황**:
- ✅ 메서드는 존재
- ❌ 실제로 호출되지 않음
- ❌ 새 법률 추가 워크플로우 없음

---

## 🔍 순차적 분석

### Step 1: 초기 상태 (2025-10-30)
```
2,987 HANG nodes (raw)
    ↓ K-means clustering (Silhouette score)
5 domains (optimal k=5)
    ↓ Neo4j 저장
Domain 노드 생성 완료
```
✅ **성공**: 초기 클러스터링 완료

### Step 2: 현재 상태 (2025-11-02)
```
5 domains (여전히)
  - 시설설치: 728 nodes  ← 500 초과
  - 토지제한: 236 nodes
  - 도시정비: 1,291 nodes  ← 500 초과
  - 도시계획: 686 nodes    ← 500 초과
  - 행정절차: 46 nodes    ← 50 미만
```
❌ **문제**: 재구성이 안 일어남

### Step 3: 기대 상태 (자가 조직화라면)
```
8-10 domains (자동 분할/병합)
  - 시설설치_A: 364 nodes  ← 분할
  - 시설설치_B: 364 nodes
  - 토지제한: 236 nodes (통합, 행정절차 병합)
  - 도시정비_A: 430 nodes  ← 분할
  - 도시정비_B: 430 nodes
  - 도시정비_C: 431 nodes
  - 도시계획_A: 343 nodes  ← 분할
  - 도시계획_B: 343 nodes
```

---

## 💡 해결 방안

### 방안 1: 즉시 재클러스터링 실행 (수동)
```python
# 스크립트 작성 필요
agent_manager = AgentManager()
agent_manager._rebalance_domains()  # 새 메서드 필요

# 알고리즘:
for domain in domains:
    if domain.size() > MAX_AGENT_SIZE:
        agent_manager._split_agent(domain)
    elif domain.size() < MIN_AGENT_SIZE:
        merge_target = find_closest_domain(domain)
        agent_manager._merge_agents(domain, merge_target)
```

**효과**:
- 3개 도메인 분할 (728, 1291, 686)
- 1개 도메인 병합 (46)
- 총 8-10개 도메인으로 재구성

### 방안 2: 주기적 재구성 (자동화)
```python
# Celery Beat 또는 Django-Q 사용
from django_q.tasks import schedule

schedule('agents.law.agent_manager.rebalance_all_domains',
         schedule_type='D',  # Daily
         name='Daily Domain Rebalancing')
```

**효과**:
- 매일 자동 재클러스터링
- 도메인 크기 최적화
- 진정한 "자가 조직화"

### 방안 3: 새 법률 추가 워크플로우 구축
```python
# law/views.py
@api_view(['POST'])
def upload_law_pdf(request):
    """새 법률 PDF 업로드 API"""
    pdf_file = request.FILES['pdf']

    # AgentManager 사용
    agent_manager = AgentManager()
    result = agent_manager.process_new_pdf(pdf_file.path)

    return Response({
        'status': 'success',
        'domains_created': result['domains_created'],
        'domains_split': result['domains_split']
    })
```

**효과**:
- 새 법률 추가 시 자동 처리
- 도메인 자동 할당/분할
- MAS 본래 목적 달성

---

## 📊 비교표: 현재 vs 이상적 MAS

| 항목 | 현재 구현 | 이상적 MAS | 차이 |
|------|----------|----------|------|
| **초기 클러스터링** | ✅ K-means (최적 k) | ✅ K-means | 동일 |
| **도메인 수** | **5개 고정** | **동적 (5~15개)** | ❌ 고정 |
| **자동 분할** | ❌ 미작동 | ✅ size > 500 | ❌ 트리거 없음 |
| **자동 병합** | ❌ 미작동 | ✅ size < 50 | ❌ 트리거 없음 |
| **새 법률 추가** | ❌ 워크플로우 없음 | ✅ process_new_pdf() | ❌ API 없음 |
| **주기적 재구성** | ❌ 없음 | ✅ 매일/매주 | ❌ 스케줄러 없음 |
| **Neo4j 동기화** | ✅ 있음 | ✅ 있음 | 동일 |

---

## 🎯 결론

### 현재 상태
```
Self-Organizing MAS (설계) ✅
    ↓
Initial Clustering (구현) ✅
    ↓
Dynamic Reconfiguration (구현) ✅ (코드 존재)
    ↓
Trigger Mechanism (구현) ❌ (없음!)
    ↓
Result: 5개 도메인으로 고정 ❌
```

### 핵심 문제
1. **코드는 완벽함**: `_split_agent()`, `_merge_agents()` 모두 구현됨
2. **트리거가 없음**: 재구성을 실행할 메커니즘 없음
3. **워크플로우 부재**: 새 법률 추가 → 재클러스터링 흐름 없음

### 사용자 우려 검증
> **"지금은 그냥 5개로 픽스해서 주는 거면 좀 이상한데"**

✅ **맞습니다**:
- 현재는 **5개로 고정**
- **자가 조직화** 코드는 있지만 **실행 안 됨**
- **즉시 해결 필요**

---

## 🚀 즉시 조치 사항

### 1. 수동 재클러스터링 스크립트 작성
```bash
python manage.py rebalance_law_domains
```

### 2. 주기적 재구성 스케줄러 설정
```python
# settings.py
Q_CLUSTER = {
    'name': 'domain_rebalancing',
    'schedule': [
        {
            'func': 'agents.law.agent_manager.rebalance_all_domains',
            'schedule_type': 'D',  # Daily
        }
    ]
}
```

### 3. 새 법률 업로드 API 구축
```python
# law/urls.py
path('api/upload-law/', upload_law_pdf),
```

---

**작성일**: 2025-11-02
**상태**: ⚠️ **CRITICAL - 즉시 수정 필요**
**우선순위**: **HIGH**
