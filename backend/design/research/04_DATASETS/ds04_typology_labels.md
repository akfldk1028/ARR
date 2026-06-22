# ds04 — Typology 라벨 데이터셋

**용도**: Phase 2 B5 typology 추천기 학습
**크기**: 1k 매스 + 수동 라벨
**비용**: 라벨링 1-2주 노동
**라이선스**: 자체 (자가 생성 + 사용자/도메인 전문가 라벨)

## 스키마
- 입력: 부지 특성 (면적, 도로폭, 용도지역 등 10-D)
- 출력: 10종 typology 중 하나 (Additive/Subtractive/Grid/L/U/Cross/Courtyard/Tower+Podium/H/Radial)

## 라벨링 워크플로우
1. ds01에서 1k 매스 추출
2. 매스 시각화 → 도메인 전문가가 typology 분류
3. 라벨 저장: `data/ds04_typology_labels_v1.parquet`

## 검증
- 라벨링 일관성 (1명이 동일 매스 2회 라벨 일치율 > 0.85)
- 다중 라벨러 시 Cohen's kappa > 0.6
