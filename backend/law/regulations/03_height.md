# 03. 높이제한

## 법적 근거
- **법률**: 건축법 제60조 (건축물의 높이 제한)
- **시행령**: 건축법 시행령 제82조 (가로구역별 높이 지정 절차)
- **국토계획법**: 국토계획법 시행령 제80조 (용도지역별 높이 제한)

## 현행법 구조

### 건축법 제60조
- 제1항: 허가권자는 **가로구역**을 단위로 건축물의 높이를 지정·공고할 수 있다
- 제2항: 특별시장/광역시장은 조례로 정할 수 있다

### 시행령 제82조 (현행 — 4개 항)
- ①항: 가로구역별 높이 지정 시 고려사항 (토지이용계획, 도로너비, 상하수도, 도시미관, 발전계획)
- ②항: 지방건축위원회 심의
- ③항: 용도·형태별 차등 가능
- ④항: 완화기준은 건축조례

### ~~도로사선 (폐지)~~
- 이전 시행령 §82에 있었던 "전면도로폭 × 배수" 규정은 **완전 삭제**됨
- Neo4j 직접 확인: 현행 §82에 "전면도로" 배수 관련 조항 없음
- `zoning_limits.json`: `road_diagonal.multiplier → null` (21개 zone 모두)

## 가로구역별 높이 데이터
- **전국 통합 API 없음**
- Vworld `getLandUseAttr` → "가로구역별 최고높이 제한지역"(UDX200) 감지 가능 (존재여부만)
- 서울시: PDF 가이드북 (data.go.kr/15098099)
  - 지정구역 13.46km² (45개 간선도로)
  - 산정구역 55.5km² (상업/준주거/준공업)

## 적용 로직
- `height_limit_m`: 현재 null (외부 데이터 없이 특정 불가)
- API 응답: `"rule": "가로구역별 높이제한 적용"`
- overlay_zones.json에서 "가로구역별 최고높이 제한지역" 인식 → restrictions에 표시

## 사용 파일
| 파일 | 역할 |
|------|------|
| `land/data/zoning_limits.json` | `height_limit_m` (null), `road_diagonal` (null) |
| `land/services/regulation_calculator.py` | `_resolve_height()`, `_resolve_road_diagonal()` |
| `land/data/overlay_zones.json` | "가로구역별 최고높이 제한" 인식 |
| `land/formatters.py` | 높이제한 표시 |
