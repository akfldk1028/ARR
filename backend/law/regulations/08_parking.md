# 08. 주차

## 법적 근거
- **법률**: 주차장법 제19조 (부설주차장 설치)
- **시행령**: 주차장법 시행령 별표1 (부설주차장 설치 기준)

## 적용
- 건축물 용도·규모별 주차대수 산정
- 시설면적 기준 (일반: 150m²당 1대, 주거: 세대당 등)
- 지자체 조례로 강화 가능

## 코드 적용
- `parking_rule`: 텍스트만 ("용도별 주차대수 산정")
- `parking_article`: "주차장법 시행령 별표1"
- 구체적 대수 계산은 미구현 (건축물 용도·면적 필요)

## 사용 파일
| 파일 | 역할 |
|------|------|
| `land/data/zoning_limits.json` | `parking_article` |
| `land/services/regulation_calculator.py` | `_resolve_parking()` |
