# 04_DATASETS — 데이터셋 일관 관리

## 명명 규칙
- `dsXX_<purpose>.md` — 메타데이터 문서
- `data/dsXX_<purpose>_v<n>.parquet` — 실제 데이터 (gitignore 권장)

## 데이터셋 목록
- `ds01` — Phase 2 자가 생성 (1k-5k 매스 + Radiance 결과)
- `ds02` — Phase 3 한국 건축 매스 (Vworld 3D + 도시건축통합지도) — *Open question*
- `ds03` — Plan B: 해외 공개 (BuildingNet, ShapeNet 일부)
- `ds04` — Phase 2 typology 라벨 (수동 1k)

## 라이선스 검토 (필수)
모든 외부 출처 데이터는 *학습 가능 라이선스* 검토. 결과는 `07_DECISIONS/ADR005_external_dataset_source.md` 에 기록.
