
---
title: "RNE-First Road × Regulation Routing — Consolidated Spec"
version: "v1.0-draft"
date: "2025-10-30"
language: "ko"
tags:
  - routing
  - RNE
  - INE
  - IER
  - road-network
  - regulation
  - SNDB
  - neo4j
  - gds
  - cli
summary: >
  본 문서는 '법규(규정) × 도로' 통합 라우팅의 목적, PPT 핵심 개념(로드 네트워크 질의),
  RNE/INE/IER 알고리즘, Neo4j GDS 기반 구현, CLI 레시피를 한 파일에 모아
  나중에 CLI/Agent가 코드를 탐색·실행할 수 있게 만든 일체형 스펙입니다.
---

# 0) 목적 (Purpose)

- **무엇을**: 규정(법규)과 도로 그래프를 연결하여, 컨텍스트(차종/시간/허가 등)에 따라
  **엣지 차단/가중치**를 반영한 **네트워크 거리** 기반의 탐색을 수행한다.
- **왜**: 규정 준수 경로 탐색, 반경(e) 내 도달 가능 영역 탐색, POI 검색, 정책 시뮬레이션.
- **어떻게**: RNE(반경 e 도달 집합) 중심 파이프라인으로 후보를 **국소화**하고,
  필요 시 INE/IER를 보조적으로 사용한다.

> 핵심 목표: **RNE-first** 설계로 **속도**와 **정확도**를 함께 달성.

---

# 1) PPT 요약 (Lecture13: Road Network Querying)

- 도로는 그래프(노드=교차점/세그먼트 단위)로 모델링한다.
- 유클리드 거리와 네트워크 거리의 괴리: 직선상 가까워도 실제 도달비용은 클 수 있다.
- **IER**: 유클리드 후보를 점증적으로 늘리며 네트워크 거리로 검증하고, 상한 `d_max`로 가지치기.
- **INE**: 네트워크를 우선순위 큐로 확장(다익스트라식); 최초로 만난 대상이 1-NN.
- **RNE**: 비용 반경 `e` 내 도달 가능한 세그먼트/노드 집합 `Q_S(e;θ)`를 먼저 산출하고, 그 위에서 객체 탐색/후처리.

> 본 스펙은 위 개념을 **규정(법규) 비용/차단**과 결합해 실전화.

---

# 2) 용어/약어 (Glossary; YAML Registry)

```yaml
terms:
  - id: SNDB
    name: "Statutory Normative DataBase"
    kind: "data-source"
    description: "법령/규정 원문과 구조화 파싱을 담는 권위 소스(가정)."
    status: "proposed"
  - id: RNE
    name: "Range Network Expansion"
    kind: "algorithm"
    description: "비용 반경 e 내 도달 가능한 세그먼트/노드 집합 우선."
  - id: INE
    name: "Incremental Network Expansion"
    kind: "algorithm"
    description: "다익스트라식 증분 확장(1-NN/범위)."
  - id: IER
    name: "Incremental Euclidean Restriction"
    kind: "algorithm"
    description: "유클리드 후보→네트워크 검증; d_max 가지치기."
```

---

# 3) 데이터 스키마 계약 (Neo4j)

```text
(:RoadNode {point, name?})
RoadNode -[:SEGMENT {length, baseTime, dir, axleWeight?}]-> RoadNode

(:Zone {geom, name?})
(:Regulation {type, start?, end?, limit?, timePenalty?, dir?, articleId?, severity?})
(:Permit {type, validFrom?, validTo?, holder?})
(:SNDB {id, citation_uri, version, effective_from?, effective_to?})

(SEGMENT)-[:IN_ZONE]->(Zone)
(Zone)-[:ENFORCES]->(Regulation)
(Regulation)-[:CITES]->(SNDB)
(Permit)-[:OVERRIDES]->(Regulation)
(Regulation)-[:OVERRIDES]->(Regulation)
```

**인덱스 권장**:
```cypher
CREATE INDEX IF NOT EXISTS FOR (n:RoadNode) ON (n.point);
CREATE INDEX IF NOT EXISTS FOR (p:POI) ON (p.point);
CREATE INDEX IF NOT EXISTS FOR (z:Zone) ON (z.geom);
CREATE INDEX IF NOT EXISTS FOR (r:Regulation) ON (r.type);
CREATE INDEX IF NOT EXISTS FOR (s:SNDB) ON (s.id);
```

---

# 4) 비용 함수 & 규칙 컴파일

- 기본비용: `w(e) = baseTime(e)` (초 단위 권장)
- 규정 적용:
\[
w'(e;\theta) = \begin{cases}
+\infty & \text{(차단)} \\
w(e) + \sum_{r\in R_e} \mathrm{penalty}(r;\theta) & \text{(통과)}
\end{cases}
\]

**타입 예시**  
- `oneway` → 반대방향 차단
- `timeBan` → 시간대 금지
- `weightLimit` → 차량/중량 조건
- `busOnly`/`toll`/`schoolZone` → 페널티 가산
- `permitBased` → `Permit` 보유 시 해제/완화
- 충돌 해결 순서: `Block > Penalty > Base` (상위법/Permit 우선)

---

# 5) RNE 파이프라인 (RNE-first)

## 5.1 의사코드
```
input: q, e, θ
PQ ← [(q,0)]; dist[q]=0; REACHED=∅
while PQ not empty:
  (u, du) ← pop_min(PQ)
  if du > e: break
  REACHED ← REACHED ∪ {u}
  for each (u->v) with cost w'(u,v;θ):
    alt = du + w'(u,v;θ)
    if alt < dist[v] and alt ≤ e:
      dist[v]=alt; push (v,alt)
return REACHED, dist
```

## 5.2 후처리
- `Q_S(e;θ)`의 노드/세그먼트 위에서만 **POI 검색**, **규정 집계**, **시각화**.
- `Q_S`의 MBR/Hull을 이용해 **2차 필터**(대용량 시 가속).

---

# 6) INE/IER (보조 전략)

- **INE(1-NN)**: RNE 확장 로직 그대로, 최초 도달 대상이 해답.
- **IER(k-NN)**: 2D point 인덱스로 유클리드 후보 N → 네트워크 비용으로 검증, `d_max`로 조기 중단.

---

# 7) Neo4j GDS — 컨텍스트 프로젝션 (CLI Ready)

```bash
# === 환경변수 ===
NEO4J_USER=neo4j
NEO4J_PASS=password
VEHICLE=truck
NOW="2025-10-30T09:00:00+09:00"
GRAPH_NAME="road_ctx_${VEHICLE}"

# (선택) 그래프 드롭
cypher-shell -u $NEO4J_USER -p $NEO4J_PASS "
CALL gds.graph.drop('$GRAPH_NAME', false) YIELD graphName RETURN graphName;"
```

```bash
# === 프로젝션 생성 ===
cypher-shell -u $NEO4J_USER -p $NEO4J_PASS "
CALL gds.graph.project(
  '$GRAPH_NAME',
  { RoadNode: { properties: ['point'] } },
  {
    SEGMENT: {
      type: 'SEGMENT',
      orientation: 'NATURAL',
      properties: ['cost'],
      cypher: '
        WITH datetime("$NOW") AS dt, "$VEHICLE" AS vType
        MATCH (a:RoadNode)-[e:SEGMENT]->(b:RoadNode)
        OPTIONAL MATCH (e)-[:IN_ZONE]->(:Zone)-[:ENFORCES]->(r:Regulation)
        WITH a,b,e,collect(r) AS regs, dt, vType

        WHERE all(r IN regs WHERE
          CASE r.type
            WHEN "oneway"      THEN e.dir = r.dir
            WHEN "timeBan"     THEN NOT (dt.time >= r.start AND dt.time <= r.end)
            WHEN "weightLimit" THEN (vType <> "truck" OR e.axleWeight <= r.limit)
            ELSE true END)

        WITH a,b,
             e.baseTime
             + reduce(p=0, rr IN regs |
                 p + CASE rr.type
                       WHEN "busOnly"  THEN 300
                       WHEN "toll"     THEN rr.timePenalty
                       WHEN "schoolZone" THEN CASE WHEN (dt.time >= rr.start AND dt.time <= rr.end) THEN rr.extraTime ELSE 0 END
                       ELSE 0 END ) AS cost
        RETURN id(a) AS source, id(b) AS target, cost AS cost
      '
    }
  }
) YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;
"
```

---

# 8) RNE 실행 (두 가지 루트)

## 8.1 루트 A — 앱/스크립트에서 PQ 확장 (권장)
- 인접리스트를 한 번 가져와 캐시하고, 아래 파이썬/노드로 RNE PQ를 구현.

```python
# rne_expand.py (스켈레톤)
from heapq import heappush, heappop
INF = 10**18
def rne_expand(adj, src, e):
    dist = {src:0}
    pq = [(0, src)]
    reached = set()
    while pq:
        d,u = heappop(pq)
        if d>e: break
        if u in reached: continue
        reached.add(u)
        for v,w in adj.get(u, []):
            nd = d + w
            if nd <= e and nd < dist.get(v, INF):
                dist[v] = nd
                heappush(pq, (nd, v))
    return reached, dist
```

## 8.2 루트 B — GDS 스트림 + 비용 필터
> GDS 버전에 따라 함수명이 상이할 수 있으므로 테스트 필요.

```bash
SRC_ID=123
E_MAX=900

cypher-shell -u $NEO4J_USER -p $NEO4J_PASS "
CALL gds.beta.traverse.stream('$GRAPH_NAME', {
  sourceNode: $SRC_ID, relationshipWeightProperty: 'cost'
})
YIELD nodeId, cost
WITH nodeId, cost WHERE cost <= $E_MAX
RETURN nodeId, cost ORDER BY cost ASC;
"
```

---

# 9) IER (k-NN) — CLI 패턴

```bash
QLON=127.0; QLAT=37.5; K=3; N=50

cypher-shell -u $NEO4J_USER -p $NEO4J_PASS "
WITH point({longitude:$QLON, latitude:$QLAT}) AS qPoint
MATCH (p:POI)
WITH p ORDER BY distance(p.point, qPoint) ASC
WITH collect(p)[0..$N] AS cand

// cand를 애플리케이션에서 하나씩 Dijkstra → d_max 갱신하며 평가
RETURN size(cand) AS candidateCount;
"
```

---

# 10) 에이전트(Agent) 사용 가이드 (검색 친화 쿼리 힌트)

- **파일 태그**: `RNE`, `INE`, `IER`, `neo4j`, `gds`, `projection`, `range`, `shortestPath`, `permit`, `timeBan`
- **질의 예**:
  - "RNE로 900초 반경 도달 집합을 구하고 POI 필터링하는 코드 찾아줘"
  - "truck 컨텍스트로 그래프 프로젝션 만드는 cypher 보여줘"
  - "weightLimit 규정이 있을 때 차단/가중치 분기 로직"

---

# 11) 검증 & 메트릭

- Parsing Precision/Recall, Decision Accuracy, Latency@P95, Cache Hit Rate
- 골든셋: (θ, 기대 차단/페널티, SNDB citation) 50~100 케이스

---

# 12) TODO / 커스터마이즈 포인트

- [ ] SNDB 정식 명칭/스키마/소유자/갱신주기 반영
- [ ] 규정 타입 사전 고정(팀 합의)
- [ ] 컨텍스트 JSON Schema 확정
- [ ] GDS 버전별 RNE 스트림 함수명 검증

---

## 부록) 이공계적 요소 · 인문학적 요소 · ASCII 예시

### 이공계적 요소
- 반경 \(e\)는 서비스 규모/지연 예산에 맞게 동적으로 조정
- 가중치 단위는 초로 통일; 거리 기반은 `baseTime=length/speed` 변환

### 인문학적 요소
- RNE는 **"지금 닿을 수 있는 도시의 윤곽"**을 먼저 그린 뒤, 그 경계 안에서 의미를 채우는 방법

### ASCII 예시
```
        POI*
      /          n3--n4--n5  \      e=900초
   |    |    \  \     θ=(truck, 23:30)
 q-n1--n2---- n6-n7
       n0 (timeBan)  X  ← 차단
```
