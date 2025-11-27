# 법률 타입 구분 문제 해결 (2025-11-20)

## 문제 상황

### 1. 발견된 문제들
- **파싱 오류**: 모든 결과가 "국토의 계획 및 이용에 관한 법률::제6장::제94조"로 표시
- **타입 미구분**: 법률/시행령/시행규칙이 구분되지 않음
- **중복 결과**: 같은 결과가 2개씩 나타남
- **다양성 부족**: 다양한 법률 타입에서 결과가 나오지 않음

### 2. 근본 원인

한국 법규는 다음과 같은 계층 구조를 가짐:
```
헌법 (Constitution)
└─ 법률 (Law) - 국회 제정
   ├─ 시행령 (Enforcement Decree) - 대통령령
   └─ 시행규칙 (Enforcement Rules) - 부령
```

**문제**: JSON 파일에서 세 가지 법률 타입이 모두 같은 `full_id` 패턴을 사용
```
법률:     "국토의 계획 및 이용에 관한 법률::제1장::제1조"
시행령:   "국토의 계획 및 이용에 관한 법률::제1장::제1조"  (동일!)
시행규칙: "국토의 계획 및 이용에 관한 법률::제1조"      (동일!)
```

이로 인해:
- Neo4j에서 노드 ID 충돌
- 검색 결과 중복
- 법률 타입 구분 불가

## 해결 방법

### 수정된 파일
1. `backend/law/scripts/json_to_neo4j.py`
2. `backend/law/scripts/neo4j_loader.py`

### 핵심 변경사항

#### 1. 법률명에 타입 추가 (json_to_neo4j.py)
```python
law_name = law_info['law_name']
law_type = law_info['law_type']
law_with_type = f"{law_name}({law_type})"
```

#### 2. full_id 변환 (json_to_neo4j.py)
```python
# 변경 전: "국토의 계획 및 이용에 관한 법률::제1장::제1조"
# 변경 후: "국토의 계획 및 이용에 관한 법률(법률)::제1장::제1조"

original_full_id = unit['full_id']
new_full_id = original_full_id.replace(law_name, law_with_type, 1)
```

#### 3. unit_path 변환 (json_to_neo4j.py)
```python
original_unit_path = unit['unit_path']
new_unit_path = original_unit_path.replace(law_name, law_with_type, 1)
```

#### 4. LAW 노드 full_id 수정 (json_to_neo4j.py)
```python
# 변경 전: law_full_id = f"{law_with_type}::{law_type}"  # 잘못됨!
# 변경 후: law_full_id = law_with_type  # 올바름!
```

#### 5. LAW 노드 생성 수정 (neo4j_loader.py)
```python
# 변경 전: full_id = f"{law_name}::{law_type}"
# 변경 후: full_id = f"{law_name}({law_type})"
```

#### 6. 모든 관계(relationships)에도 적용 (json_to_neo4j.py)
- CONTAINS 관계
- NEXT 관계
- CITES 관계

### 예상 결과

변경 후 각 법률 타입은 고유한 full_id를 가짐:

```
법률:
"국토의 계획 및 이용에 관한 법률(법률)::제1장::제1조"

시행령:
"국토의 계획 및 이용에 관한 법률(시행령)::제1장::제1조"

시행규칙:
"국토의 계획 및 이용에 관한 법률(시행규칙)::제1조"
```

## 다음 단계

### 1. Neo4j 데이터베이스 재구축
```bash
cd backend/law/scripts
python json_to_neo4j.py --all
```

### 2. 임베딩 재생성
수정된 full_id로 HANG 노드들의 임베딩을 다시 생성해야 함:
```bash
cd backend
.venv/Scripts/python.exe law/scripts/add_hang_embeddings.py
```

### 3. 테스트
- 검색 결과에서 법률 타입이 구분되는지 확인
- 중복 결과가 사라졌는지 확인
- 다양한 법률 타입에서 결과가 나오는지 확인

## 장기 계획

현재 수정은 Neo4j 로더(step2)만 수정했음. 장기적으로는:

1. **step1 (PDF→JSON 파서)** 수정
   - JSON 생성 시점부터 law_type을 full_id에 포함
   - 모든 JSON 파일 재생성

2. **일관성 유지**
   - JSON과 Neo4j 데이터 구조 통일
   - 향후 유지보수 용이성 확보

## 참고 자료

- 한국 법령 체계: 헌법 > 법률 > 시행령 > 시행규칙
- 각 타입은 독립적인 문서로, 조 번호도 독립적으로 관리됨
- 예: 법률 제36조 ≠ 시행령 제36조 (완전히 다른 조문)
