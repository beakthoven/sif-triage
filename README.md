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

One command brings up the whole demo — **bare-metal, 100% offline, no docker**
(uvicorn + static React dashboard + SQLite; ARCHITECTURE runtime section):

```bash
./run.sh            # preflight → ollama → API+dashboard on http://127.0.0.1:8177/
./run.sh --stop     # stop what run.sh started (pidfiles in .run/)
```

`run.sh` checks the .venv, the prebuilt dashboard, and the ONNX model artifact
(clear error + retrieval hint if the model is missing; dev-only bypass:
`./run.sh --allow-mock`). If ollama isn't running it starts one with
`OLLAMA_NUM_PARALLEL=6` (DECISION_LOG D18); an already-running ollama is reused
and never killed by `--stop`. If ollama is absent entirely, the deterministic
explanation templates carry the demo (template fallback by design).

**System requirements:** Linux x86_64 · Python 3.14 · 4 cores · 8 GB RAM free
(+3.2 GB if qwen3:4b rewording runs) · no network at demo time.

First-time setup (needs network once):

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd dashboard && npm ci && npm run build && cd ..
```

**Offline / USB install:** `packaging/make_tarball.sh` builds the air-gapped
bundle (code + prebuilt dashboard + model artifacts + vendored tokenizer +
Python wheels, excluding `data/` and `runs/` raw research — see
[`packaging/manifest.md`](packaging/manifest.md) for contents, exact sizes, and
ollama model-blob instructions). On the target: `packaging/install.sh` then
`./run.sh`. `packaging/selfcheck.sh` runs two full
start→health→classify→stop cycles as the bring-up proof.

**Demo flow:** open `http://127.0.0.1:8177/` → paste/upload incident reports →
triage card with amber review-priority band + highlighted evidence spans →
site/activity precursor-density ranking → pattern cards with n + Wilson CIs →
Confirm/Not-SIF override queue ("model proposes, HSE disposes").

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
