# 10. 건축지정선 / 건축한계선

## 법적 근거
- **법률**: 국토의 계획 및 이용에 관한 법률 제49조~제52조 (지구단위계획)
- **건축법**: 건축법 제77조의4 (건축협정)

## 개념
- **건축지정선**: 건축물이 반드시 닿아야 하는 선 (壁面線 지정)
- **건축한계선**: 건축물이 넘어서면 안 되는 선 (후퇴선)
- **적용 구역**: 지구단위계획구역 내에서만 지정

## 코드 적용
- `building_designation_applies`: 지구단위계획구역 감지 시 true
- `building_designation_setback_m`: 기본 2.0m (LLM override 가능)
- 감지 키워드: Vworld overlay에서 "지구단위계획구역" 포함 여부

### LLM 동적 추출
- `BUILDING_DESIGNATION_PROMPT`: Neo4j 검색 결과에서 지정선/한계선 거리 추출
- fallback: 2.0m (일반적 도로변 후퇴)

## 시각화
- 2D: 빨간 실선 (도로변 기준 지정선 거리 오프셋)
- 3D: Cesium polyline entity

## 사용 파일
| 파일 | 역할 |
|------|------|
| `land/services/regulation_calculator.py` | `_resolve_building_designation()` |
| `land/services/setback_geometry.py` | `building_designation_line` 생성 |
| `land/data/regulation_prompts.py` | `BUILDING_DESIGNATION_PROMPT` |
| `land/data/overlay_zones.json` | "지구단위계획구역" 인식 |
