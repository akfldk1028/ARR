# ds02 — 한국 건축 매스 데이터셋 ⚠️ Open Question

**용도**: Phase 3 C1 SDF / C2 Diffusion 학습
**크기 목표**: 1,000+ 매스 (3D)
**상태**: **확보 가능성 미검증**

## 후보 출처
1. **Vworld 3D** — LOD1 박스 위주, LOD2/3 매스 가능성 검토 필요
2. **도시건축통합지도** (국토교통부) — 라이선스 검토
3. **건축 잡지** (공간, 건축계 등) — 라이선스 위험
4. **수동 모델링** — 비용 폭증

## 위험 (R1)
ds02 확보 실패 시 → ds03 (해외 공개) 으로 대체 + transfer learning

## 다음 행동 (Phase 3 진입 전)
1. Vworld 3D LOD 수준 직접 확인 (샘플 10건 다운로드)
2. 도시건축통합지도 라이선스 문의 (공공데이터포털)
3. 결과 `07_DECISIONS/ADR005_external_dataset_source.md` 기록
