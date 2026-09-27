# Backend Stack Decision

**Project:** SIH 2026 · PS 26165 · Oil India Limited
**Date:** 2026-09-25 · **Full evaluation:** `docs/discovery/44-res-backend-oss.md`

Every component was evaluated against: is what we run today still the best realistic choice for a
2–4 person team under hostile technical judging, or is there a more modern or more defensible
alternative?

Three constraints bind everything below and are absolute:

1. **Runtime is 100 % local with zero third-party cloud calls.** Dev-time cloud LLM use already
   happened (synthetic corpus generation); nothing may cross the boundary at inference.
2. **No torch at runtime.** Inference is ONNX-only. Any dependency pulling torch is disqualified.
3. **No docker on the critical path**, single machine, must run fully disconnected, ~5 GB RAM
   budget shared with the ONNX model and SQLite.

---

## 1. Verdict summary

| Component | Today | Decision | One-line justification |
|---|---|---|---|
| API framework | FastAPI + uvicorn | **KEEP** | ~0 ms to gain on an 18 ms model-bound path; alternatives cost a 402-LoC rewrite and `/docs`. |
| Serving | Hand-rolled `onnxruntime` in `classifier.py` | **KEEP** | No torch allowed; a serving layer adds surface without changing decisions. |
| Database | SQLite (WAL, single connection, RLock) | **KEEP + FIX** | Verified write 8k rows/s, reads 5–100 ms; the defects are missing `busy_timeout` and indexes, not the engine. |
| Analytics read-path | live full scan per request | **DEFER DuckDB** | It reads SQLite files directly; wrong *write* profile today, right later. |
| Near-dup / vector | brute-force numpy matmul | **KEEP numpy** | A brute-force problem: 19.7 ms extrapolated at 100k rows beats ANN library surface. |
| Background jobs | none | **BackgroundTasks + ThreadPoolExecutor** | The 11 rows/s bottleneck is per-row transaction overhead, not a queue problem. **No broker, ever.** |
| Sentinel gates | 423 LoC pure Python | **KEEP** | Rule-engine candidates are abandoned or LGPL; a DSL would add more than it removes. |
| Observability | silence | **ADD structlog + prometheus-client** | Minimum credible production story without collector infrastructure. |
| Config | frozen dataclass | **ADD pydantic-settings** | Removes hand-rolled bool/float env parsing. |
| Testing | 1 adversarial suite + 5 e2e | **ADD hypothesis** | Property tests for gates and span validity are cheaper than examples. |
| Indic language | none | **DEFER** | Zero Devanagari rows exist in any database we hold; demand is plausible but unproven. |

---

## 2. Why we did *not* modernise the interesting parts

**FastAPI → Litestar / Robyn / Starlette.** All three would buy ~0 ms. Measured single-report
classify latency is ~18 ms CPU-bound inside the ONNX session; the HTTP layer is not the cost.
Migrating `routes.py` (402 LoC) plus losing auto-generated OpenAPI for no measurable gain is a bad
trade for a judged prototype. The ceiling is the model, not the framework.

**SQLite → Postgres + pgvector.** Re-evaluated seriously, and it stays rejected. It needs a server
process and docker-shaped operations, which breaks constraint 3 and the air-gapped bring-up. Measured
today: `/density` full scan runs 21–103 ms at 4,548 rows; ingest is atomic with verified rollback and
idempotent replay. Nothing in our workload needs Postgres. The real findings were *configuration*
defects, so we fix those instead:
- **no `PRAGMA busy_timeout`** — a held external write lock produced a verified **5 s block then
  HTTP 500** on concurrent review writes;
- **zero secondary indexes**, forcing full scans on `overrides.report_id` and every facet `GROUP BY`.

**DuckDB** is the interesting near-miss and is therefore *deferred, not rejected*: it can query
SQLite files in place, so once the time-density reporting in §4 lands it becomes a clean read-side
accelerator with no migration risk. Its write profile is wrong for us today.

**Brute-force numpy → sqlite-vec / sqlite-vss / hnswlib / faiss.** Rejected. This is a brute-force
problem: measured 13.8 ms per `/classify` row and 19.7 ms extrapolated to 100k rows, against a
frozen 70,398-row base tier. ANN libraries add build surface, index maintenance, and quantisation
tuning to accelerate something already fast. `sqlite-vss` is additionally abandoned.

**Broker queues (Celery / dramatiq / rq / arq / Procrastinate).** Rejected categorically. The
measured 11 rows/s bulk ingest is **per-row transaction overhead**, not orchestration starvation.
The honest fix is batched SQLite commits plus `BackgroundTasks` for explanation precompute. A sqlite
job table is the ceiling if durability is ever genuinely needed — and it costs one table, not a
Redis-shaped dependency.

---

## 3. Rule engine — rejection confirmed with evidence

`app/gates.py` is 423 LoC of pure functions. A prior agent recommended keeping it; I asked for that
argument to be attacked. It survives:

- `durable-rules` — stalled since 2020.
- `pyknow` — abandoned.
- `experta` — LGPL-3.0, a poor licence fit for distribution alongside our artifacts.
- `python-rule-engine` — cannot express our gates, several of which are *not* rule-shaped at all:
  windowed regex over token spans, embedding-backed cosine comparison, and storage-backed
  near-duplicate lookups.

A declarative DSL would express nine of ten gates and require escaping the tenth into Python
anyway. **Deletion beats replacement here.**

---

## 4. Changes we *are* making

These come from Phase 0 root-cause work, not from library shopping. Detail in
`docs/redesign-plan.md` §8; numbers marked **[measured]** are mine, taken this session.

| Change | Why it is defensible |
|---|---|
| **Apply `mask_text` at inference** before scoring | `masking.py` runs at *training* time only — no `mask_text` call exists anywhere in `app/`. Fixing this skew measured **+0.349** on near-miss text, and repairs a genuine anti-feature: adding *"Fortunately no injury occurred"* to a scenario currently **drops** its score 0.280 → 0.100, when that sentence is the signature of the genre the PS is about. **[measured]** |
| **Self-consistency scoring** (score N surface variants, serve mean + spread) | The triage score is not stable: one confined-space scenario spans **0.026 → 0.861** across meaning-preserving paraphrases (sd 0.31), and the flagged/clear verdict **flips**. Mean-of-8 averaging cuts sd **0.308 → 0.076**. **[measured]** No new dependency. |
| **New `verdict_stability` gray gate** on that spread | Extends the existing 10-gate humility design rather than inventing a competing philosophy. Honest finding: averaging fixes *reliability*, not *validity* — it stabilises around 0.318, still unflagged, for procedural cases. Both halves get disclosed. |
| **ECE + Brier calibration reporting** | Scores are currently described as "calibrated" while **no ECE or Brier exists anywhere in the repo** (`train.py:486-503` fits T=1.648 on validation data only). Either measure it or stop saying it. |
| **Date index + time parameters** on `/density`, `/reports`, `/patterns` | No time dimension exists anywhere. Leading-indicator standards (API RP 754, IOGP 456) are time-series by definition. |
| **`gate_schema_version` + backfill recompute** | Persisted `gate_states` snapshots use an 8-gate schema while code emits 10 — `severity_watch` alone hides 45 real cases. Because the gates are pure functions, a recompute is safe and takes ~1 s. |
| **structlog + Prometheus RED metrics** | Replaces observability silence. **OpenTelemetry is rejected**: it needs collector/backend infrastructure a judged offline demo cannot run. Prometheus metrics plus structured JSON logs is the minimum *credible* production story. |
| **pydantic-settings** | Removes hand-rolled bool/float env parsing in `config.py`. Rejected dynaconf as over-scoped. |
| **hypothesis** | Property-based tests for gate determinism and evidence-span exact-substring validity. **Rejected `syrupy` snapshots** deliberately: they would ossify calibrated outputs we are about to change. |
| **Flip `SIF_EXPLAIN_LLM` default to 0** | The Ollama 4B reworder adds no information by construction, stalls **17.5 s** when the server is down **[measured]**, and its cache is already **0 % hit rate**. The deterministic template becomes the product; the LLM an opt-in extra. |

All four adopted dependencies were verified downloadable for **Python 3.14** this session
(structlog 26.1.0, prometheus-client 0.26.0, pydantic-settings 2.15.0, hypothesis 6.168.1).

---

## 5. Indic language — deferred, honestly

OIL's Assam workforce makes Hindi/Assamese field reports plausible. But we verified **0 Devanagari
rows in either demo database**, so demand is unproven against our own evidence. `IndicTrans2`
remains the viable path (MIT, CT2-int8; 1B indic→en = 1020 MB at 94.45 % token-match; 200M = 335 MB
at 85.64 %, which its publisher flags "not for production"), and the `ctranslate2` 4.8.2 cp314 wheel
was confirmed available. `IndicXlit` is rejected because its pip package pins `fairseq` → torch,
violating constraint 2. **Deferring a plausible-but-unproven feature is more defensible than
shipping it unmeasured.**

---

## 6. Honest limitations

- **Not verified:** IndicTrans2 CPU latency on our Ryzen (published figures are unspecified
  hardware, likely GPU); IndicTransToolkit's torch-free status; Indic Photo OCR v2 (source
  unreachable); `sqlite-vec`'s 67.84 ms figure is vendor-benchmarked on an M1 Pro, not this machine.
- Shipping-constraint note carried from `31-training-eval.md`: the shipped INT8 artifact's export gate
  recorded `pass:false` (agreement 0.993, ΔAUC 0.1305). Shipping it is defensible — the operating
  point was tuned on the int8 chain itself, local ΔAUC is 0.0035, and decision agreement at the op is
  97.7 % — but it must be surfaced rather than buried.
- This stack optimises for **credibility under examination**, not novelty. Several "modern" choices
  were declined because they would add operational surface to an air-gapped single-machine demo
  without changing a single triage decision.

---

## 7. One-paragraph defence

The defensible move here was subtraction, not replacement. We kept FastAPI, SQLite, numpy near-dup
and hand-written gates because every candidate alternative either bought nothing measurable on an
18 ms model-bound path, violated the offline/no-torch/no-docker constraints, or added operational
surface to a demo that must survive being unplugged. We rejected an Object-Oriented rule engine on
evidence (abandoned or LGPL candidates) and OpenTelemetry on infrastructure grounds. The changes that
*do* matter are not fashionable; they are a train/serve skew worth +0.349 on near-miss text, a
self-consistency measurement that converts our worst defect into visible signal, and calibration
metrics that let us honestly use the word "calibrated" — each measured on this machine rather than
assumed.
