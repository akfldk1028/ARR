# exp013 — B6 Core Planner + B7 Explanation Generator 통합 시연

**Date**: 2026-05-06 21:36 KST (수동 검증)
**Phase**: 2
**작업 ID**: B6 Core Planner + B7 Explanation Generator
**범위**: 강남 SSIEA 우승 매스 → 코어 배치 → 자연어 설명

## B6 Core Planner

### 원리
매스 footprint + typology → *서비스 코어 (엘리베이터+계단+화장실)* 위치 자동 배치.

10 typology 별 배치 전략:
| Typology | Strategy | 위치 |
|---|---|---|
| additive / subtractive / grid | centroid | 무게중심 |
| tower_podium | tower_centroid | upper part 무게중심 |
| lshape / cross | wing_intersection | 두 wing 교차점 |
| ushape / courtyard | inset_one_wing | 한쪽 wing 안쪽 (마당 회피) |
| radial | centroid | 정중앙 |
| hshape | bridge_center | 가운데 bridge |

### 구현 디테일
- 코어 사이즈: default 4×4m (16m²)
- footprint 안에 안 들어가면 → representative_point 위치 변경
- 그래도 안 들어가면 → 코어 축소 (4→3→2→1.5m)

### 단위 검증 (4개 테스트)
- ✅ 30×30 box footprint → centroid (15,15) 4×4 코어
- ✅ Empty footprint → notes=['footprint_empty']
- ✅ 10 typology 모두 strategy 정의
- ✅ 5×5 좁은 footprint → 4×4 들어감 (경계 case)

### API
```python
from design.services.core_planner import plan_core
plan = plan_core(footprint_utm, typology="subtractive", core_size_m=4.0)
# CorePlan(typology='subtractive', core_polygon_utm=...,
#          inside_footprint=True, distance_to_boundary=2.5,
#          typology_strategy='centroid')
```

## B7 Explanation Generator

### 원리
매스 결과 (수치 + 법규 + typology + 사례) → 한국어 자연어 설명.

**LLM 모드** (gpt-4o-mini, OPENAI_API_KEY 필요): 자연스러운 paragraph
**Template fallback**: 정해진 구조 + 동적 수치 삽입

### Template 출력 예시 (실측)

입력:
- 부지: 일반상업지역, BCR 80% / FAR 1300% / H 50m
- Typology: subtractive
- 결과: BCR 56.3%, FAR 951.3%, H 16.8m, FA 5142m², daylight 72/100
- 사례: 강남 테헤란로 'tower_podium'

출력 (template 모드):
```
본 부지(일반상업지역)에 박스 제거형 매스를 6층 규모로 추천합니다.

규제 검증: 건폐율 56.3% (한도 80%) ✅, 용적률 951.3% (한도 1300%) ✅,
높이 16.8m (한도 50m) ✅, 인접대지 이격 3.05m.

총 연면적 5,142m², 일조 점수 72/100점.

비슷한 사례: 강남 테헤란로 일반상업 — 매스 형태 tower_podium —
역삼동 일대 사례. 1~3F 저층 commercial podium + 상층 office tower...
```

### 단위 검증 (4개 테스트)
- ✅ Typology 한국어 변환 (`subtractive` → `박스 제거형`)
- ✅ 위반 시 ⚠️ 표시 (BCR 90% with limit 60%)
- ✅ Precedent 정보 포함 (강남 테헤란로)
- ✅ 주거지역 시 정북일조 자동 언급

### API
```python
from design.services.explanation_generator import generate_explanation

text = generate_explanation(
    metrics={"bcr": 56, "far": 951, "height": 16.8, "floor_area": 5142,
             "daylight_score": 72, "min_setback": 3.05},
    typology="subtractive",
    site={"zone": "일반상업지역", "bcr_limit": 80, "far_limit": 1300, "height_limit_m": 50},
    precedent={"name": "강남 테헤란로", "description": "역삼동 사례"},
    core=core_plan,
    use_llm=True,  # LLM 시도, 실패 시 template fallback
)
```

## 통합 시나리오 (Frontend 운영)

```
사용자가 부지 선택 (PNU/주소)
   ↓
SiteFeatures 추출
   ↓
B5 typology_recommender.recommend() → top-3 typology
   ↓
B3 precedent_rag.search() → 비슷한 사례 1-3건
   ↓
사용자가 typology 선택
   ↓
SSIEA + A6 repair → 우승 매스
   ↓
B6 plan_core() → 서비스 코어 위치
   ↓
B7 generate_explanation() → 자연어 설명 paragraph
   ↓
Frontend Cesium: 매스 + 코어 + envelope + 설명 카드 동시 표시
```

## 변경 파일
- `design/services/core_planner.py` (신규, B6)
- `design/services/explanation_generator.py` (신규, B7)
- 4 + 4 unit tests (CorePlannerTest, ExplanationGeneratorTest)

## 한계 + 다음

- B6: 1세대 휴리스틱 — multi-core (대규모) / podium-tower 분리 코어 미지원
- B7: template 한국어 약간 robotic — LLM 모드가 더 자연스러우나 API key 필수
- 통합 SSE 스트리밍에 B6/B7 결과 추가 미연동 (frontend 작업 필요)

## 회귀
**171/171 design 테스트 통과**.
