# 04. 정북일조사선

## 법적 근거
- **법률**: 건축법 제61조 제1항
- **시행령**: 건축법 시행령 제86조 제1항 (2023.9.12 개정)

## 조문 내용

### 건축법 §61①
"전용주거지역이나 일반주거지역에서 건축물을 건축하는 경우에는 건축물의 각 부분을 **정북(正北) 방향으로의 인접 대지경계선**으로부터 다음 각 호의 범위에서 건축조례로 정하는 거리 이상을 띄어 건축하여야 한다."

### 시행령 §86① (Neo4j 직접 확인)
- **제1호**: 높이 **10미터** 이하인 부분: 인접 대지경계선으로부터 **1.5미터** 이상
- **제2호**: 높이 **10미터**를 초과하는 부분: 해당 건축물 각 부분 높이의 **2분의 1** 이상

> 2023.9.12 개정 전에는 9미터 기준이었음. 현행 10미터 기준 확인 완료.

### §86② 적용 제외
1. 20미터 이상 도로에 접한 대지 (정비구역 등)
2. 건축협정구역 내
3. **인접대지가 비주거지역**인 경우

## 적용 범위

| 용도지역 | 적용 | 근거 |
|---------|------|------|
| 제1종전용주거 | ✅ | §61① "전용주거지역" |
| 제2종전용주거 | ✅ | §61① "전용주거지역" |
| 제1종일반주거 | ✅ | §61① "일반주거지역" |
| 제2종일반주거 | ✅ | §61① "일반주거지역" |
| 제3종일반주거 | ✅ | §61① "일반주거지역" |
| 준주거 | ❌ | "전용·일반주거지역만" 명시 |
| 상업/공업/녹지/관리/농림/자연환경보전 | ❌ | 적용 대상 아님 |

## 시각화

### 2D (OpenLayers)
`_compute_sunlight_setback_lines()` → **높이별 4단계 사선** FeatureCollection:
| 높이 | 이격 | 스타일 |
|------|------|--------|
| H=10m | 1.5m | 빨강 실선 5px |
| H=20m | 10m | 주황 점선 4px |
| H=30m | 15m | 연주황 점선 3px |
| H=40m | 20m | 연주황 점선 2px |

각 선은 `line.intersection(parcel_utm)`으로 필지 내부 클리핑.

### 3D (Cesium)
`_compute_sunlight_envelope()` → Wall 2개:
- Wall 1: 수직벽 (경계→1.5m, 높이 0→10m)
- Wall 2: 경사면 (1.5m→max_depth, slope 2:1)
- max_depth: `min(parcel_span * 0.4, 30m)`

## 사용 파일
| 파일 | 역할 |
|------|------|
| `land/data/zoning_limits.json` | `sunlight_setback.applies`, `rules`, `direction` |
| `land/services/regulation_calculator.py` | `_resolve_sunlight()` |
| `land/services/setback_geometry.py` | `_compute_sunlight_setback_lines()`, `_compute_sunlight_envelope()` |
| `frontend/src/land/hooks/use-vworld-map.ts` | `SUNLIGHT_HEIGHT_STYLES`, `drawSetbackLines()` |
| `frontend/src/design/components/SiteMapPanel.tsx` | Cesium Wall 렌더링 |
