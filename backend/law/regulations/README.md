# 적용 법규 목록

시스템에 구현된 건축법규 41개 항목의 공식 근거 + 코드 적용 방식.

## Core 규제 (11개)

| # | 규제 | 근거 법조문 | 문서 |
|---|------|-----------|------|
| 1 | [건폐율](01_bcr.md) | 국토계획법 시행령 §84① | 21개 zone 상한값 |
| 2 | [용적률](02_far.md) | 국토계획법 시행령 §85① | 21개 zone 상한값 |
| 3 | [높이제한](03_height.md) | 건축법 §60, 시행령 §82 | 가로구역별 (삭제된 도로사선 포함) |
| 4 | [정북일조사선](04_sunlight.md) | 건축법 §61①, 시행령 §86① | 전용+일반주거만 |
| 5 | [가각전제](05_corner_cutoff.md) | 건축법 §46①, 시행령 §31 | 8m 미만 도로 모퉁이 |
| 6 | [인접대지 이격](06_adjacent.md) | 건축법 §58 | 0.5m 기본 (조례) |
| 7 | [건축선 후퇴](07_building_line.md) | 건축법 §46-47 | 조례 의존 |
| 8 | [주차](08_parking.md) | 주차장법 시행령 별표1 | 용도별 |
| 9 | [조경](09_landscaping.md) | 건축법 §42, 시행령 §27 | 200m2 이상 |
| 10 | [건축지정선](10_building_designation.md) | 국토계획법 §49-52 | 지구단위계획구역 |
| 11 | [채광 인동간격](11_daylighting.md) | 건축법 §61②, 시행령 §86③ | 공동주택만 |

## Extended 규제 (31개)

Group A (5개): zone-dependent → `zoning_limits_extended.json`
Group B (10개): scale-dependent → `regulation_calculator_ext.py`
Group C (16개): text-only → `regulation_calculator_ext.py`

→ 상세: [extended/](extended/) (TODO)
