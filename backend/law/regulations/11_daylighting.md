# 11. 채광 인동간격 (채광사선)

## 법적 근거
- **법률**: 건축법 제61조 제2항
- **시행령**: 건축법 시행령 제86조 제3항 (Neo4j 확인)

## 조문 내용

### 건축법 §61②
"다음 각 호의 어느 하나에 해당하는 **공동주택**(일반상업지역과 중심상업지역에 건축하는 것은 제외한다)은 채광(採光) 등의 확보를 위하여 대통령령으로 정하는 높이 이하로 하여야 한다."

### 시행령 §86③ (Neo4j 확인)

**제1호** (채광사선):
"건축물(기숙사는 제외)의 각 부분의 높이는 그 부분으로부터 채광을 위한 창문 등이 있는 벽면에서 직각 방향으로 인접 대지경계선까지의 수평거리의 **2배**(근린상업지역 또는 준주거지역의 건축물은 **4배**) 이하로 할 것"

> 다세대주택 예외: 수평거리 1m 이상이면 조례 기준 적용 (단서)

**제2호** (인동간격):
"같은 대지에서 두 동 이상이 서로 마주보고 있는 경우 건축물 각 부분 사이의 거리는 다음 각 목"
- 가목: 채광창 방향 → 높이의 0.5배 (도시형생활주택 0.25배)
- 나목: 측벽 상호간 → 4m 이상
- 다목: 채광창 없는 벽 + 측벽 → 8m 이상
- 단서: 동지 9시~15시 2시간 연속 일조 확보 가능 시 대체

**제3호**: 도로 사이에 두고 마주보는 경우 도로 중심선을 인접 대지경계선으로 봄

## 적용 범위
- **공동주택만**: 아파트, 다세대, 연립, 다가구
- **제외**: 일반상업/중심상업 (§61② 괄호)
- `building_type` 판별 로직: design/views.py line 425-431

## 코드 적용

### 채광사선 배수
| 용도지역 | multiplier | 근거 |
|---------|-----------|------|
| 일반 (주거 등) | 2 | §86③제1호 본문 |
| 근린상업/준주거 | 4 | §86③제1호 괄호 |

### 3D envelope
`_compute_daylight_diagonal_envelope()`:
- **인접경계선**에서 안쪽으로 경사면 (도로변 아님!)
- 경사면 기울기 = multiplier (H = distance × mult)
- max_depth: `min(parcel_span * 0.5, 30m)`

## 사용 파일
| 파일 | 역할 |
|------|------|
| `land/services/regulation_calculator_ext.py` | `daylighting_spacing` (applies, rule) |
| `land/services/setback_geometry.py` | `_compute_daylight_diagonal_envelope()` |
| `design/views.py` | `daylight_diagonal_multiplier` 설정 (building_type 판별) |
| `frontend/src/design/components/SiteMapPanel.tsx` | Cesium Wall 렌더링 |
