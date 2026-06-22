# DRL 건축 적용 사례

## Chen+ 2024 — *Automation in Construction*
MADDPG (Multi-Agent DDPG) 적용 — 건물 renovation 의사결정.

## Tian+ 2025 — *Energy & Buildings*
GAN + DRL hybrid pipeline (dormitory). 우리 Phase 3 C4 가장 유사한 구조.
- GAN: 매스 생성
- DRL: 매스 → 평가 → action

## 우리 시스템과의 연결
- Phase 3 C4 DRL Bootstrap 핵심 참고
- Phase 2 GA Pareto 결과 → DRL warm-start (imitation learning)
- 학습된 policy: 새 부지 zero-shot ms 추론
