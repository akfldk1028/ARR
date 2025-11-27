# Neo4j FOLLOWER Error 완전 해결 가이드

## 문제 원인 (웹 검색 결과 기반)

Neo4j Desktop은 **Enterprise Edition**을 사용하므로, 단일 인스턴스임에도:
- 클러스터 기능이 기본적으로 활성화됨
- System database가 cluster topology로 구성될 수 있음
- 데이터베이스가 PRIMARY/FOLLOWER 역할을 가지게 됨

## 해결 방법 3가지

---

### 방법 1: 데이터베이스 재생성 (가장 확실)

**Neo4j Browser에서 실행:**

```cypher
// 1. system database 선택
:use system

// 2. 기존 neo4j 데이터베이스 확인
SHOW DATABASES;

// 3. neo4j 데이터베이스 삭제 (데이터 손실 주의!)
DROP DATABASE neo4j IF EXISTS;

// 4. neo4j 데이터베이스 새로 생성 (topology 지정 없음)
CREATE DATABASE neo4j;

// 5. neo4j database 선택
:use neo4j

// 6. 확인
SHOW DATABASES;
```

**결과:** `role` 컬럼이 **standalone** 또는 **primary**(단일 primary)로 표시되어야 함

---

### 방법 2: ALTER DATABASE로 Topology 수정

**Neo4j Browser에서 실행:**

```cypher
// 1. system database 선택
:use system

// 2. 현재 topology 확인
SHOW DATABASE neo4j;

// 3. Topology를 단일 primary로 변경 시도
// 주의: 이미 FOLLOWER 상태면 이 명령은 실패할 수 있음
ALTER DATABASE neo4j SET TOPOLOGY 1 PRIMARY 0 SECONDARIES;

// 4. 확인
SHOW DATABASES;
```

**주의:**
- FOLLOWER 상태에서는 이 명령이 실패할 수 있습니다
- 그럴 경우 방법 1 사용 권장

---

### 방법 3: 데이터 디렉토리 삭제 후 재시작

**1. Neo4j Desktop에서 데이터베이스 정지**

**2. Windows 탐색기에서 데이터 디렉토리 삭제:**

```
C:\Users\SOGANG1\.Neo4jDesktop2\Data\dbmss\dbms-23e9404b-8efc-4706-adc0-90e1c20445ab\data\databases\neo4j\
```

**3. System database는 유지 (중요!):**

```
C:\Users\SOGANG1\.Neo4jDesktop2\Data\dbmss\dbms-23e9404b-8efc-4706-adc0-90e1c20445ab\data\databases\system\
```
이 폴더는 삭제하지 마세요!

**4. neo4j.conf 수정 (이미 완료됨):**

```conf
# Line 297
initial.server.mode_constraint=NONE

# Line 357
dbms.routing.enabled=false
```

**5. Neo4j Desktop에서 데이터베이스 시작**

**6. Neo4j Browser에서 확인:**

```cypher
SHOW DATABASES;
```

neo4j 데이터베이스가 자동으로 standalone 모드로 재생성됩니다.

---

## 권장 순서

### 1단계: 방법 1 시도 (가장 안전)
- 데이터가 중요하지 않으면 바로 DROP/CREATE
- 데이터가 중요하면 먼저 export 후 진행

### 2단계: 방법 1 실패 시 방법 3
- Neo4j 완전히 정지
- neo4j 데이터 디렉토리만 삭제
- 재시작

### 3단계: 여전히 문제 발생 시
- Neo4j Desktop에서 DBMS 완전히 삭제
- 새 DBMS 생성
- apoc.conf 및 neo4j.conf 재설정

---

## 설정 파일 최종 확인 사항

### C:\Users\SOGANG1\.Neo4jDesktop2\Data\dbmss\dbms-23e9404b-8efc-4706-adc0-90e1c20445ab\conf\neo4j.conf

```conf
# 다음 설정들이 주석 해제되어 있어야 함:
initial.server.mode_constraint=NONE
dbms.routing.enabled=false

# 다음 설정들은 주석 처리되어 있어야 함:
#dbms.cluster.endpoints=...
#server.cluster.listen_address=...
#server.cluster.advertised_address=...
#server.cluster.raft.listen_address=...
#server.cluster.raft.advertised_address=...
#server.routing.listen_address=...
#server.routing.advertised_address=...
```

### C:\Users\SOGANG1\.Neo4jDesktop2\Data\dbmss\dbms-23e9404b-8efc-4706-adc0-90e1c20445ab\conf\apoc.conf

```conf
apoc.trigger.enabled=true
apoc.trigger.refresh=60000
```

---

## APOC Trigger 설치

위 방법으로 FOLLOWER 오류 해결 후:

```cypher
// 1. neo4j database 선택
:use neo4j

// 2. APOC 설치 확인
RETURN apoc.version();

// 3. neo4j_triggers.md 파일의 Trigger 1부터 차례대로 실행
```

---

## 참고 문헌

- Neo4j Operations Manual: Managing databases in a cluster
- Neo4j Community Forum: Changing server from follower to leader
- Stack Overflow: No write operations are allowed (FOLLOWER error)
