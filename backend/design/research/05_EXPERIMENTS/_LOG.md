# 실험 로그

매번 실험 추가 시 본 표에 한 줄 추가.

| ID | 날짜 | Phase | 변경 항목 | 결과 (HV/feasible%/etc) | 결론 |
|---|---|---|---|---|---|
| **exp001** | 2026-05-06 | Phase 1 시작 시점 | Baseline (SSIEAJob 5섬×15 + 박스 적층) | 강남 16% / 분당 **0%** / 춘천 27% feasible | 분당 0% feasible — A6 Repair 정확 정당화 |
| **exp003** | 2026-05-06 | A6 | Repair Operator 적용 + 5종 버그 fix (road_setback, is_multi reset, boundary semantic, UTM area 일치) | 강남 12→**100%** / 분당 6→**99.97%** / 춘천 16→**99.93%**. HV 강남 +480%, 분당 +478%, 춘천 +148% | A6 hard constraint 강제 효과 *모든 부지 99.93~100% feasible* 도달. 152/152 회귀 통과 |
| **exp002** | 2026-05-06 | A1 | NSGA3Job vs SSIEAJob (둘 다 A6 repair on, 2 obj) | 강남 HV +34%, 분당 +13%, 춘천 +5%. Pareto 다양성 3-5배. **runtime 10배** (1.6s→17s) | NSGA3 HV/다양성 우월, 속도 trade-off. 4+ obj는 exp006 follow-up |
| **exp004** | 2026-05-06 | A3 | normalized vs binary penalty (SSIEA, repair off) | 강남 HV +50%, 분당 **+3598%**, 춘천 +11% | 정규화 효과 정량 검증. 빡빡한 제약일수록 극대. A6와 독립 효과 |
| **exp005** | 2026-05-06 | A2 | Radiance UDI/sDA 실측 | ⏸️ BLOCKED — pyradiance 미설치 | 인터페이스+fallback 완료 (A2 done). 바이너리 설치 후 별도 PR로 활성화 |
| **exp006** | 2026-05-06 | A1 follow-up | 4-objective NSGA3 vs SSIEA | NSGA3 HV +189~375%, Pareto 다양성 2~4배. Runtime 8~10x | NSGA-III 진짜 강점 정량 검증 (2 obj +5~34% 대비 11~43배 격차) |
| **exp007** | 2026-05-06 | A6+A3 | A6×A3 시너지 매트릭스 (2x2) | A6 dominant, A3는 A6 OFF일 때만 의미. 시너지 *부재* | 두 작업 redundant (같은 문제 다른 방식). A6가 production default |
| **exp008** | 2026-05-06 | B1b | Surrogate Training (RandomForest/MLP/GP, 3000 sample) | **MLP best mean R²=0.82** (floor_area/FAR R²=0.92, daylight 0.78, bcr 0.66). 학습 0.49s | floor_area/FAR 거의 deterministic. daylight/bcr 추가 데이터 필요. Production 가용성: BO guide OK, 시뮬레이터 대체 부족 |
| **exp009** | 2026-05-06 | B2 | Naive BO vs SSIEA (same HV metric, 강남 부지) | BO 100 evals HV=125k vs SSIEA 100 evals HV=173k → **BO -27%** (honest negative) | Geometric eval 빠름 → BO 무용. Radiance 활성화(30s/매스) 후 진가. Proper EI + GP + 큰 init 필요 |
| **exp010** | 2026-05-06 | B5 | Typology Benchmark — 10 typology × 3 fixture × 2 reps | Winners: 강남/분당=**subtractive** (552k/95k), 춘천=**radial** (270k). 절차적(additive/sub/grid) > typological(lshape~hshape) | 절차적 매스 표현력 우월. radial 광활 부지 특화. tower_podium/courtyard 의외로 약함 |
| **exp011** | 2026-05-06 | B3 | PrecedentRAG offline (keyword) — 10 case corpus | 4 query 모두 top-1 의미적 정확 (zone+typology 매칭) | 인프라 작동 확인. OpenAI API 연동 시 cosine 자동 전환. 도시건축통합지도 자동 수집 follow-up |
| **exp012** | 2026-05-06 | B4 | Heterogeneous Island (BLX/DE) vs Homo (BLX×5) | 강남 +2%, **분당 -44%**, 춘천 +2%. 평균 -13% (honest negative) | DE 외삽 → 빡빡한 제약(분당 25m) 에서 악화. Production = homogeneous BLX 유지 |
| **exp013** | 2026-05-06 | B6+B7 | Core Planner 휴리스틱 + Explanation Generator (template+LLM) 통합 시연 | 10 typology 코어 strategy 매핑. Template 한국어 paragraph 자연스러움 | B6/B7 인프라 완료. SSIEA 결과 → 코어 + 자연어 설명 자동 생성 |

## 실험 명명 규칙
- `expXXX` — 3자리 ID, 시간순
- 각 실험은 별도 .md 파일로 (`expXXX_<short_name>.md`)
- 변경 항목은 작업 ID(A1/B1 등)와 일치
