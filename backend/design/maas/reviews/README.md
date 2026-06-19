# MAAS Reviews

This directory keeps MAAS-specific review records close to the implementation.
Use it for review gates, defect logs, and follow-up decisions that affect
`design.maas`.

Current rule:

- Do not call a MAAS candidate legally complete just because geometry generation
  succeeds.
- Every candidate must be reviewable through the canonical evidence bundle
  `arr.maas.evidence.v0`.
- Missing law, parking, datum, VWorld, or agent-review evidence must remain
  `needs_evidence`, not `pass`.

Related tests:

- `ARR/backend/design/test_maas_export.py`

Related memory:

- `docs/ai-session-memory/MAAS_EVIDENCE_BUNDLE.md`
- `docs/ai-session-memory/MAAS_RESEARCH.md`

