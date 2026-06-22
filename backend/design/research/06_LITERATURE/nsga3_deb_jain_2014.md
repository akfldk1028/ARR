# Deb & Jain 2014 — NSGA-III 원전

**저자**: Deb, K., & Jain, H.
**저널**: IEEE Transactions on Evolutionary Computation, 18(4)
**DOI**: 10.1109/TEVC.2013.2281534

## 핵심
NSGA-II의 4+ objectives 한계 극복. *Reference point* 기반 선택. 4-15개 목적함수까지 안정.

## 우리 시스템과의 연결
- Phase 1 A1 작업으로 통합 (`pymoo` 라이브러리)
- 매스 평가가 *4+ objectives* 가 되었을 때 NSGA-II 한계 극복

## 적용 검증 사례
Zhao+ 2022 *Applied Energy* — dormitory daylight optimization NSGA-III +41% 검증
