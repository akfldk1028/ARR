# Neo4j FOLLOWER Role 해결 방법

## 문제 원인
Neo4j가 클러스터 모드로 인식되어 FOLLOWER 역할로 실행 중입니다.

## 해결 방법

### 1단계: neo4j.conf 수정

neo4j_BASE.md 파일에서 다음 2줄을 수정했습니다:

1. **Line 297**: `initial.server.mode_constraint=NONE` (주석 제거)
2. **Line 357**: `dbms.routing.enabled=false` (주석 제거)

### 2단계: 실제 neo4j.conf 파일 복사

**Windows 명령 프롬프트(cmd)에서 실행:**

```cmd
copy /Y "D:\Data\11_Backend\01_ARR\backend\neo4j_BASE.md" "C:\Users\SOGANG1\.Neo4jDesktop2\Data\dbmss\dbms-23e9404b-8efc-4706-adc0-90e1c20445ab\conf\neo4j.conf"
```

### 3단계: Neo4j 재시작

1. Neo4j Desktop을 열기
2. 현재 실행 중인 Neo4j 데이터베이스 **정지 (Stop)**
3. 3-5초 대기
4. 데이터베이스 **시작 (Start)**

### 4단계: 연결 확인

Neo4j Browser에서 실행:

```cypher
SHOW DATABASES;
```

**neo4j** 데이터베이스의 **role**이 **standalone** 또는 **primary**인지 확인

### 5단계: APOC Trigger 설치 시도

Neo4j Browser에서 실행:

```cypher
:use neo4j
```

그 다음 `neo4j_triggers.md` 파일의 Trigger 1부터 차례대로 설치 시도

---

## 만약 여전히 FOLLOWER 오류가 발생하면

Neo4j 데이터베이스를 완전히 재생성해야 할 수 있습니다.

### 데이터 백업 (필요시)

Neo4j Browser에서:

```cypher
// 중요한 데이터 export
MATCH (n) RETURN n LIMIT 100;
```

### 데이터베이스 재생성

1. Neo4j Desktop에서 데이터베이스 정지
2. **Remove** 버튼 클릭 (데이터 삭제됨)
3. **Create New DBMS** 클릭
4. apoc.conf 파일 다시 생성
5. neo4j.conf 파일 다시 설정

---

## 수정된 설정 요약

```conf
# Line 297
initial.server.mode_constraint=NONE

# Line 357
dbms.routing.enabled=false
```

이 두 설정이 Neo4j를 standalone 모드로 강제합니다.
