---
title: SIF Precursor Triage — SIH 2026 PS 26165
emoji: 🛢️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# SIF Precursor Triage — OIL India (SIH 2026 PS 26165)

Local-first triage and evidence-extraction support for Unsafe-Act /
Unsafe-Condition and near-miss reports. A ModernBERT multi-task model served
through ONNX Runtime proposes a calibrated triage score; deterministic gates
route uncertain and barrier-failure cases to review; an HSE reviewer decides.

**Model proposes; an HSE reviewer disposes.**

- Paste a report or bulk-ingest CSV → triage score + rule probabilities +
  evidence spans, with the server's operating point named on every screen.
- 18 deterministic gates, including seven barrier-absence families
  (energy isolation, gas test, permit, fire watch, standby, atmosphere monitoring,
  fall protection) and verdict-stability routing for ensemble-unstable scores.
- Duplicate clustering: near-identical reports collapse under one row —
  44% register compression on the demo data (1,019 groups over 4,548 rows).
- Full decision audit trail: reviewer identity, rationale, timestamps.

> **Claim boundary:** triage, evidence extraction, and queue compression
> only — not an injury/fatality predictor. The demo register is synthetic
> OIL-style seed data, not real OIL incident records. See the in-app
> "Data & limitations" dialog for every stated limitation.
