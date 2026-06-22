# 06. 인접대지 이격

## 법적 근거
- **법률**: 건축법 제58조 (대지 안의 공지)
- **시행령**: 건축법 시행령 제80조의2 (대지 안의 공지)

## 조문 내용

### 건축법 §58
"건축물을 건축하는 경우에는 건축선 및 인접 대지경계선으로부터 6미터 이내의 범위에서 대통령령으로 정하는 바에 따라 해당 지방자치단체의 조례로 정하는 거리 이상을 띄워야 한다."

### 핵심
- **6미터 이내** 범위에서 **조례**로 정함
- 조례 미제정 시 관행적으로 **0.5m** 적용
- 건축물 용도·규모별 차등 (조례에 따름)

## 코드 적용
- 기본값: **0.5m** (모든 zone 동일)
- 조례 override 시스템 지원 (`ordinance_overrides/`)
- LLM 동적 추출 지원 (`regulation_prompts.py` adjacent 프롬프트)

## 시각화
- 2D: 빨간 실선 (인접 변 0.5m 안쪽 오프셋)
- 건축가능영역: 전체 필지에서 0.5m buffer(-) → 초록 polygon

## 사용 파일
| 파일 | 역할 |
|------|------|
| `land/data/zoning_limits.json` | `adjacent_setback_m: 0.5` |
| `land/services/regulation_calculator.py` | `_resolve_adjacent_setback()` |
| `land/services/setback_geometry.py` | `_offset_edges_inward()` (adjacent edges) |
| `land/data/regulation_prompts.py` | LLM 추출 프롬프트 |
