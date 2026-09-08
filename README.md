# SIF-Precursor Detection Engine

**SIH 2026 Problem Statement 26165 — OIL India Limited**

A local-first triage engine that surfaces Serious Injury & Fatality (SIF) precursors
buried in routine incident and near-miss reports, so HSE reviewers can prioritize
what to read first. **"Model proposes, HSE disposes."**

> **Claim boundary:** this is a triage + extraction tool. We report triage score,
> extraction precision, and reviewer time saved — **never prediction accuracy**.
> See [Honest claims](#honest-claims).

## Architecture

<!-- TODO: architecture diagram (rendered figure goes here) -->
Source of truth: [`runs/run2/ARCHITECTURE.md`](runs/run2/ARCHITECTURE.md)
(adjudicated v2, 2026-09-08) with rulings in [`runs/run2/DECISION_LOG.md`](runs/run2/DECISION_LOG.md).

Dev-time: OSHA SIR + ASRS data → era-conditional OIICS label maps → token-level
outcome neutralization → synthetic OIL corpus (cloud LLM) → temporal hard split →
ModernBERT-base multi-task fine-tune on Kaggle GPU → hand-rolled ONNX export →
two-tier parity gate → INT8 artifact.

Runtime (100% local, bare metal): CSV/Excel/paste/JSON ingestion → validation +
near-dup index (SQLite + numpy) → FastAPI + onnxruntime INT8 multi-task model →
SIF triage score (calibrated), 7-rule probabilities + well-control/barrier tag,
evidence spans → deterministic explanation templates (optional Ollama qwen3:4b
rewording with template fallback) → React dashboard with 4 engineered gray states.

## Repository layout

| Path | Contents |
|---|---|
| `app/` | FastAPI runtime service + explanation renderer |
| `data_pipeline/` | Parse, dedup, label derivation, masking, synthetic corpus, splits |
| `training/` | Kaggle notebooks/scripts: fine-tune, export, parity gate |
| `dashboard/` | React dashboard (shadcn/ui + Tailwind, navy theme) |
| `spec/` | Frozen specs (`label_spec.yaml` etc.) + `spec/drafts/` |
| `artifacts/` | Versioned model artifacts (ONNX + metrics.json + label_spec hash) |
| `tests/` | Golden regression, adversarial suite, parity checks |
| `notebooks/` | Exploratory / validation notebooks |

## Quickstart

<!-- TODO: one-command startup (run.sh: uvicorn + static React + SQLite) — owner: API agent -->
```bash
# Placeholder — the runtime bring-up lands here once app/ is built.
# Design target: bare-metal, offline, no docker on the critical path.
pip install -r requirements.txt
# run.sh  (uvicorn + static dashboard + SQLite)  ← to be added
```

Dev/training environment (torch CPU wheel locally; real training on Kaggle):
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
```

## Honest claims

<!-- TODO: full claims table with measured numbers (every deck claim measured on
     this machine within 72h of the demo — ARCHITECTURE.md acceptance bar) -->

What this system is:

- A **triage and evidence-extraction tool** that ranks reports by review priority
  and highlights the text spans behind each flag.
- Calibrated **triage scores** — never "% accuracy", never "SIF detected".
- Statistics with honest uncertainty: pattern mining reports n + Wilson CIs;
  metrics carry corrected Wilson confidence intervals.

What this system is not:

- **Not a predictor of injuries or fatalities.** We never claim prediction accuracy.
- The "~20%" figure is ~20% of *recordable injuries* having SIF potential
  (BST/Mercer ORC 2011; Martin & Black 2015) — **not** "20-25% of near-miss
  reports". We measure and report our own flag rate.
- IOGP Life-Saving Rules 8 (Work Authorisation / Permit to Work) and Bypassing
  Safety Controls are **declared out of scope** (<0.1% detectable in free text) —
  shown as such in the UI, never faked.
- On Baghjan-class events: the precursors existed and were buried in routine
  reports — we make them impossible to bury. We do **not** claim this tool would
  have prevented any past incident.

Gray states (low-confidence / negation / non-English / near-duplicate) are a
first-class humility system, not error paths.
