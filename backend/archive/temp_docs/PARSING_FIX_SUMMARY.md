# 법률 파싱 구조 오류 분석 및 해결 방안

## 발견된 문제

### 문제 요약
**제12장 (벌칙)** 에 **제4장 (도시·군관리계획)** 의 4개 절이 잘못 배정됨

### 잘못된 구조 (현재)
```
제4장 도시·군관리계획
├─ 제1절: 도시·군관리계획의 수립 절차 (빈 목차, 조 없음)
├─ 제2절: 용도지역·용도지구·용도구역 (빈 목차, 조 없음)
├─ 제3절: 도시·군계획시설 (빈 목차, 조 없음)
└─ 제4절: 지구단위계획 (빈 목차, 조 없음)

...

제12장 벌칙
├─ 제1절: 도시·군관리계획의 수립 절차 (23개 조 포함) ← 잘못!
├─ 제2절: 용도지역·용도지구·용도구역 (17개 조 포함) ← 잘못!
├─ 제3절: 도시·군계획시설 (15개 조 포함) ← 잘못!
├─ 제4절: 지구단위계획 (196개 조 포함) ← 잘못!
├─ 제140조: 벌칙
├─ 제140조의2: 벌칙
├─ 제141조: 벌칙
├─ 제142조: 벌칙
└─ 제143조: 양벌규정
```

### 올바른 구조 (공식 법령)
```
제4장 도시·군관리계획
├─ 제1절: 도시·군관리계획의 수립 절차 (23개 조)
├─ 제2절: 용도지역·용도지구·용도구역 (17개 조)
├─ 제3절: 도시·군계획시설 (15개 조)
└─ 제4절: 지구단위계획 (196개 조)

...

제12장 벌칙
├─ 제140조: 벌칙
├─ 제140조의2: 벌칙
├─ 제141조: 벌칙
├─ 제142조: 벌칙
└─ 제143조: 양벌규정
```

## 원인 분석

### 1. PDF 구조
국토의 계획 및 이용에 관한 법률 PDF는 다음 구조를 가짐:
- **목차 (Table of Contents)**: 초반부에 모든 장·절 제목만 나열
- **본문 (Body)**: 실제 법 조문 내용

### 2. Line Number 분석
```
Line 38:  제4장 도시·군관리계획
Line 39:  제1절 (목차)         ← 빈 항목
Line 53:  제2절 (목차)         ← 빈 항목
Line 64:  제3절 (목차)         ← 빈 항목
Line 74:  제4절 (목차)         ← 빈 항목
...
Line 195: 제12장 벌칙          ← 목차에서 제12장 발견
...
Line 739: 제1절 (본문)         ← 실제 내용 (제4장 소속이어야 함)
Line 961: 제2절 (본문)
Line 1165: 제3절 (본문)
Line 1330: 제4절 (본문)
```

### 3. 파서 동작 방식
`law/core/law_parser.py`의 `EnhancedKoreanLawParser`는 **컨텍스트 기반** 파싱:

```python
# 장 발견 시
def _try_parse_jang(self, line: str, line_num: int) -> bool:
    # ...
    self.current_jang = jang_unit   # 현재 장을 기억
    # ...

# 절 발견 시
def _try_parse_jeol(self, line: str, line_num: int) -> bool:
    # ...
    parent = self.current_jang      # 현재 장을 부모로 설정!
    if not parent:
        return False
    # ...
```

**문제 발생 과정:**
1. Line 38: 제4장 발견 → `current_jang = 제4장`
2. Line 39-74: 제1-4절 발견 → 제4장의 자식으로 등록 (정상)
3. Line 195: 제12장 발견 → `current_jang = 제12장` ← **컨텍스트 변경!**
4. Line 739-1330: 제1-4절 **다시 발견** → 제12장의 자식으로 등록 ← **오류 발생!**

### 4. 중복 파싱
- 목차의 "제1절 도시·군관리계획의 수립 절차" → 제4장에 등록 (내용 없음)
- 본문의 "제1절 도시·군관리계획의 수립 절차" → 제12장에 등록 (23개 조 포함)

## 해결 방안

### 방안 1: 사후 수정 (Post-Processing) ✅ 추천
파싱 후 JSON을 수정하는 스크립트 사용

**장점:**
- 기존 파서 수정 불필요
- 빠른 적용 가능
- 다른 법률에 영향 없음

**단점:**
- 임시방편적

**실행 파일:** `fix_law_structure.py`

**사용법:**
```bash
python fix_law_structure.py
```

### 방안 2: 파서 개선 (Parser Enhancement)
파서에 목차 감지 및 스킵 로직 추가

**개선 방향:**
1. **목차 감지:** 연속된 장·절 제목만 나오는 구간 인식
2. **스킵 모드:** 목차 구간은 메타데이터만 수집하고 노드 생성 안 함
3. **본문 모드:** 실제 조문이 나오면 노드 생성 시작

**수정 위치:** `law/core/law_parser.py`

```python
class EnhancedKoreanLawParser:
    def __init__(self, ...):
        # ...
        self.in_toc_mode = False  # 목차 모드 플래그
        self.toc_threshold = 10  # 연속 N개 장절만 나오면 목차로 판단
        self.consecutive_headers = 0
```

### 방안 3: PDF 전처리 (Pre-Processing)
PDF에서 목차 페이지를 제거하고 본문만 추출

**장점:**
- 가장 깔끔한 해결
- 다른 PDF에도 적용 가능

**단점:**
- PDF 구조 분석 필요
- 구현 복잡도 높음

## 적용 순서

### 1단계: 즉시 수정 (Post-Processing)
```bash
# 1. 구조 수정
python fix_law_structure.py

# 2. 검증
python analyze_jang12_structure.py

# 3. Neo4j 재로드
python law/scripts/json_to_neo4j.py --input law/data/parsed/국토의_계획_및_이용에_관한_법률_법률_fixed.json

# 4. 임베딩 재생성
python law/scripts/add_embeddings_v2.py
```

### 2단계: 파서 개선 (장기)
1. `law/core/law_parser.py`에 목차 감지 로직 추가
2. 테스트 케이스 작성
3. 전체 법률 재파싱

## 영향 범위

### 영향 받는 파일
- `law/data/parsed/국토의 계획 및 이용에 관한 법률_법률.json`
- Neo4j 데이터베이스의 JANG, JEOL, JO, HANG 노드
- 임베딩 데이터 (full_id가 변경됨)

### 영향 받지 않는 파일
- 다른 법률 JSON 파일 (시행령, 시행규칙 등)
- 파서 로직 (방안 1 사용 시)

## 검증 방법

### 1. JSON 검증
```bash
python analyze_jang12_structure.py
python find_jang4_problem.py
```

**기대 결과:**
- 제4장의 절: 4개 (모두 조 포함)
- 제12장의 절: 0개
- 제12장의 조: 48개 (벌칙 조문)

### 2. Neo4j 검증
```cypher
// 제4장 구조 확인
MATCH (j:JANG {full_id: '국토의 계획 및 이용에 관한 법률::제4장'})
MATCH (j)-[:CONTAINS]->(jeol:JEOL)
RETURN jeol.number as 절, count{(jeol)-[:CONTAINS]->(:JO)} as 조개수

// 제12장 구조 확인
MATCH (j:JANG {full_id: '국토의 계획 및 이용에 관한 법률::제12장'})
OPTIONAL MATCH (j)-[:CONTAINS]->(jeol:JEOL)
RETURN count(jeol) as 절개수  // 0이어야 정상
```

### 3. 임베딩 검증
```cypher
// 유사도 검색 테스트
MATCH (h:HANG)
WHERE h.full_id CONTAINS '제4장::제4절::제49조'
  AND h.embedding IS NOT NULL
RETURN h.full_id, h.content
LIMIT 1
```

## 참고 자료

### 공식 법령 구조
- 국가법령정보센터: https://www.law.go.kr/
- 국토의 계획 및 이용에 관한 법률 목차:
  - 제4장 도시·군관리계획 (제1-4절 포함)
  - 제12장 벌칙 (절 없음, 제140-143조만 포함)

### 생성된 파일
- `analyze_jang12_structure.py`: 제12장 구조 분석
- `find_jang4_problem.py`: 제4장 문제 분석
- `fix_law_structure.py`: 구조 수정 스크립트 v1
- `fix_law_structure_v2.py`: 구조 수정 스크립트 v2 (목차 제거 포함)

## 결론

**즉시 조치 필요:**
1. `fix_law_structure.py` 실행하여 JSON 수정
2. Neo4j 재로드
3. 임베딩 재생성

**장기 개선:**
- 파서에 목차 감지 로직 추가하여 근본 원인 해결
