# C4 — DRL Bootstrap

**기간**: 8-12주 | **학습**: ✅ 본격 (GPU 16GB+, 수일~1주)

## 목적
GA Pareto 결과 1k+ 부지 → DRL policy 학습. 학습된 policy는 *새 부지 zero-shot ms 추론*.

## 모델 후보
- **PPO** (OpenAI baselines, stable-baselines3) — 단일 agent
- **MADDPG** (Multi-Agent DDPG) — 매스 + 평면 동시
- **Imitation Learning warm-start** + RL fine-tune

## 학습 데이터
- Phase 2 GA + Surrogate 결과 1k+ 부지의 Pareto front

## 통합
- DRL policy → 박스 적층 또는 SDF action space 출력
- 추론: 새 부지 입력 → policy(부지) → 매스 (ms)

## 학계 참고
- Tian+ 2025 *Energy & Buildings* — GAN+DRL dormitory
- Chen+ 2024 *Automation in Construction* — MADDPG renovation

## Open Questions
- Action space — discrete (typology 선택) vs continuous (gene 직접) vs hybrid?
- Reward shaping — Pareto 점수 vs hypervolume 변화율?
