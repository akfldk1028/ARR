# 07. 건축선 후퇴

## 법적 근거
- **법률**: 건축법 제46조 (건축선의 지정), 제47조 (건축선에 따른 건축제한)

## 조문 내용

### 건축법 §46
- 제1항: 도로와 접한 부분에 건축선 지정 (시행령 §31 가각전제 포함)
- 제2항: 허가권자가 4m 이내 범위에서 건축선 별도 지정 가능 (도시지역)

### 건축법 §47
- 제1항: 건축물과 담장은 건축선의 수직면을 넘어서는 안 됨
- 제2항: 도로면으로부터 높이 4.5m 이하에 창문 등 돌출 불가

## 코드 적용
- `building_line_setback_m`: null (사이트별 조례 의존)
- 기본 도로변 후퇴: 1.0m (코드 내 default)
- 실제 건축선은 허가권자 지정 → 외부 데이터 필요

## 시각화
- 2D: 빨간 실선 (도로변 1.0m 안쪽 오프셋)
- `_classify_edges()`: 최장변을 도로로 추정

## 사용 파일
| 파일 | 역할 |
|------|------|
| `land/data/zoning_limits.json` | `building_line_article` |
| `land/services/regulation_calculator.py` | `_resolve_building_line()` |
| `land/services/setback_geometry.py` | `road_setback` 생성 |
