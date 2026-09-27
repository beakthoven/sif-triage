# SIH 2026 PS 26165 — Current Overhaul Summary

**Project:** Local-first triage and evidence-extraction support for Oil India Limited (OIL) Unsafe-Act / Unsafe-Condition and near-miss reports. **Claim boundary:** triage, extraction, and queue compression only — never prediction of injury/fatality or prediction accuracy.

This summary replaces the superseded implementation narrative. It distinguishes measurements from this seed, from targeted probes, and from held-out evaluation data. Synthetic-seed behavior and expert-authored probes are not field prevalence or human-gold estimates.

## Current implementation

- **Backend:** FastAPI, SQLite, NumPy, pure-Python gates, and an ONNX Runtime INT8 ModernBERT multi-task classifier. Runtime is intended to be local/offline; PyTorch is not a runtime dependency. SQLite now has a declared busy timeout, secondary indexes, and an actions table.
- **Dashboard:** React 19, TypeScript, Vite 8, Tailwind 4, HashRouter. Surfaces: queue, report detail, analytics, ingest, decisions, and settings. Routes are `/#/queue`, `/#/report/:id`, `/#/analytics`, `/#/ingest`, `/#/decisions`, and `/#/settings`. The design contract and token gallery are [`design-system-spec.md`](design-system-spec.md) and [`design-system-token-gallery.md`](design-system-token-gallery.md).
- **Design/stack decisions:** Astryx-derived semantic tokens mapped onto Tailwind 4 plus motion-primitives for interaction; not a StyleX migration. FastAPI, SQLite, NumPy, and hand-written gates were retained. Postgres/pgvector, broker queues, OpenTelemetry, rule-engine libraries, Skiper UI, and IndicXlit (torch dependency) were rejected or deferred; see the [backend](backend-stack-decision.md) and [frontend](frontend-stack-decision.md) decisions.
- **Gates:** ten general gates, seven explicit barrier-absence gates, and `verdict_stability` (18 total) are live. The ten general gates are min_length, negation, language, confidence, drill, near_dup, long_input, well_control_watch, chunked_low_score, and severity_watch. The stability gate routes only when `n_variants >= 2` and `verdict_stability < 0.75`; it does not change the score or the 0.5647 operating point. The seven barrier gates look for absent energy isolation, gas testing, permit, fire watch, standby, atmosphere monitoring, and fall protection. This is deterministic routing support, not proof that a report is safe or a barrier failure was comprehensively detected.

## Measurements and what they mean

- **Demo seed v3 (final, 2026-09-26):** 4,548 rows ingested through the real `/api/ingest` path with the N=4 ensemble on the write path — **all stored predictions carry `n_variants=4` with spread**, and zero rows contain the `[OUTCOME]` mask token (the v2 memorised rows leaked it; v3 uses raw OSHA narratives). **338 flagged (7.43%)** at the re-tuned operating point 0.5647; precursor recall on the 830 labeled precursors 290/830 (**34.9%**, was 28% at the old point); routine-row false flags 9/3,670 (**0.25%**); 19 near-duplicate triggers (the deliberate memorised subset) versus 3,021 in the old seed; contractor fill 4,514/4,548; density values vary realistically. These are properties of the synthetic demo seed and the current scoring chain, not OIL field rates. The earlier v2 6.2%-versus-~20% seed comparison was a historical discrepancy; the dominant cause was low model recall on the register's procedural precursors (the operating-point shift from the ensemble was minor — recall 0.9701 → 0.9770 on the test split), which the deterministic barrier-failure gates compensate at system level by routing low-score barrier cases to review.
- **Operating point re-tuned on the serving path:** threshold **0.5647** calibrated (raw 0.6056, T=1.648 unchanged), selected by the same max-recall-at-precision-≥-0.80 rule on the N=4 ensemble scores over the n=17,731 derived-label test split (P 0.8002 · R 0.9770 · F1 0.8798). Provenance: `artifacts/demo/ensemble_operating_point_v2.json`; applied to `metrics.json` with the manifest sha refreshed; the prior 0.6581 single-text point is preserved in both artifacts.
- **Near-miss regression probe:** without runtime masking, adding “Fortunately no injury occurred” moved the LOTO scenario from 0.5819 to 0.3042 (−0.278). With runtime masking it moved 0.5819 to 0.5632 (−0.019). Runtime masking and deterministic self-consistency (`SIF_SELF_CONSISTENCY_N=4` by default) are enabled. Self-consistency is a reliability aid, not a validity or accuracy claim. Probe context: [`60-orchestrator-novel-probe.md`](discovery/60-orchestrator-novel-probe.md); implementation: `app/classifier.py`.
- **Barrier probe (2026-09-27):** expert-authored, not human gold. At threshold 0.5647, barrier stratum n=22 had model flag recall 0.2727 and routed recall 0.8182 (flags OR gray-gate routes); mechanism n=12 had flag recall 0.8333 and routed recall 0.9167; benign n=16 had false-flag rate 0.0625 and false-gray rate 0.0625, with zero benign barrier-gate false-grays. Source: [`probe_process_safety.json`](../artifacts/qa-evidence/probe_process_safety.json). Trip/bypass, inspection-tag removal and driving violations remain documented out of scope in `app/gates.py` with reasons. Four prior misses now route through the existing energy-isolation and permit families plus the new fall-protection family; remaining barrier recall is still incomplete.
- **Calibration:** measured, not absent. On the derived-label temporal test split (n=17,731), calibrated ECE 0.1475 and Brier 0.1580. On the gold-consensus sample (n=407), ECE 0.1765 and Brier 0.1830. These are calibration diagnostics for their named samples; they do not establish deployment performance. Source and definitions: `artifacts/models/masked-v2/metrics.json`, generated by `training/eval_calibration.py`.
- **Bulk ingest:** approximately 7.3 rows/s in the cited 500-row measurement, not 45.6 rows/s. Source: `docs/discovery/24-be-api.md`.
- **Build and regression evidence:** the real-model adversarial suite passed 18/18 cases plus #10b on 2026-09-26 (`RealOnnxClassifier`; `tests/adversarial_suite.py`). The browser e2e suite passed 10/10 on 2026-09-26 against an isolated throwaway-DB stack (`dashboard/e2e/dashboard.spec.ts`). API smoke, Python tests, and TypeScript checks pass. The process-safety probe reproduces its checked-in results; it is expert-authored, not human gold.

## Known limitations and shipped fixes

- **Report-page threshold fix (shipped):** the verdict reads `prediction.flag_threshold` from the prediction payload; parsing the explanation template remains only as a legacy fallback. The fix was covered by the 10/10 browser e2e run on 2026-09-26 (`dashboard/e2e/dashboard.spec.ts`).

1. The model is trained on proxy/synthetic text, not OIL's own report register. Demo-seed rates are not field prevalence.
2. Model recall on the demo register's **procedural** precursors is low (34.9% flagged at the re-tuned point) while physical-mechanism recall is strong — this is the dominant cause of the gap between the seed's ~18% precursor share and the 7.43% flag rate. Deterministic barrier gates route some low-score cases to review; system routed recall on the expert-authored probe is higher than model flag recall, but neither number establishes human-gold performance.
3. Barrier recall remains incomplete in the small expert-authored probe (2026-09-27; threshold 0.5647): barrier n=22 model flag recall 0.2727 and routed recall 0.8182; mechanism n=12 flag recall 0.8333 and routed recall 0.9167; benign n=16 false-flag rate 0.0625 and false-gray rate 0.0625. Routed recall counts flagged OR gray-routed cases. The probe is not human-gold validation; source: [`probe_process_safety.json`](../artifacts/qa-evidence/probe_process_safety.json).
4. Runtime masking materially reduced the tested near-miss penalty, but a single paired probe does not establish general validity. Self-consistency stabilizes repeated surface variants; it does not make the mean score correct.
5. The INT8 export gate is recorded as `pass:false` in `artifacts/models/masked-v2/export_gate.json` (agreement 0.993; AUC drop 0.1305). Keep this qualification visible.
6. `/api/classify` returns `band`, `flag_threshold`, and gray-band bounds from the classifier; stored-report GET endpoints reconstitute all four fields at read time from the current classifier operating point and gray-band settings. Explanation endpoints return explanation data only, not a prediction payload.
7. Date filters now exist on `/api/reports` and `/api/density`, and the analytics UI offers a custom date range. `DELETE /api/ingest/{job_id}` supports cooperative cancellation before commit; cancellation is rejected with 409 once a job is committing or already finished.
8. The browser end-to-end suite passed 10/10 as of 2026-09-26 (isolated throwaway-DB stack on port 8232, real INT8 classifier).
9. The live demo on port 8177 was not restarted or mutated. The isolated stability-gate check used port 8240 with a throwaway DB and confirmed that the requested unstable text is gray-routed while a stable routine text is not; the server was stopped and the port confirmed free.
10. No validated deployment-prevalence precision, injury-prediction accuracy, or reviewer-time-saved measurement is claimed.

The literature figure of approximately 20% refers to the share of **recordable injuries** with SIF potential (BST/Mercer ORC 2011; Martin & Black 2015). It is not the share of reports or near-miss reports.

## Run instructions

Fresh checkout prerequisites: Python 3.14, Node/npm, and the INT8 model at `artifacts/models/masked-v2/sif_multitask_int8.onnx`. The model artifact is not tracked by git; obtain it from the packaged bundle (the pendrive payload) or use a working tree where it is already present. Dependency installation needs network; model inference is local. On first start, SQLite creates an empty runtime database at `app/runtime.db`; the command below does not seed demo rows.

```bash
# From the repository root
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cd dashboard && npm ci && npx tsc -b && npx vite build
cd ..
./run.sh
```

`./run.sh` starts the API and serves the built dashboard on `http://127.0.0.1:8177/`. The root redirects client-side to `/#/queue`; deep links use `/#/report/1`, `/#/analytics`, `/#/ingest`, `/#/decisions`, and `/#/settings`. The server also supports an SPA fallback for path requests such as `/queue`, but hash URLs are the canonical links. For pre-seeded demo data, supply an existing database through `SIF_DB_PATH`; this fresh-checkout snippet does not load one.

For isolated browser tests, start the throwaway-DB server from the repository root after confirming port 8232 is free. The Playwright config does not manage server lifecycle:

```bash
E2E_PORT=8232 bash dashboard/e2e/serve-isolated.sh
```

In a second terminal:

```bash
cd dashboard && PLAYWRIGHT_BASE_URL=http://127.0.0.1:8232 E2E_API=http://127.0.0.1:8232 npm run test:e2e
```

Stop only the server started by `serve-isolated.sh` (Ctrl-C) and confirm port 8232 is free. The script defaults to 8232; `E2E_PORT` can override it. At initial inspection another real-model process was already listening on 8232 (health reported 4,551 reports), so it was left untouched. A separate process later appeared on 8232 without being started by this audit; it too was left untouched. Use a confirmed-free port if 8232 is occupied.

## Verification observed in this documentation audit

- `.venv/bin/python --version`: Python 3.14.7. `./run.sh --help` and shell syntax checks passed; full `./run.sh` startup was not verified. A historical `packaging/selfcheck.sh` attempt on 8236 failed; the explanation recorded at the time (a shared `.run/uvicorn.pid`) is superseded. `run.sh` now uses a port-scoped `.run/uvicorn-<PORT>.pid`; the selfcheck script's own legacy-pidfile assertion was being aligned in this session. This note does not claim a new selfcheck pass.
- `cd dashboard && npx tsc -b --noEmit && npx vite build`: passed. Then `npm ci && npx tsc -b && npx vite build` also passed (0 vulnerabilities from npm audit); Vite warned about a >500 kB chunk and unsupported native config-loader features, while route chunks and a lazy charts chunk were produced.
- Isolated Playwright run against port 8232 (temporary DB, `RealOnnxClassifier`, 4,548 seeded rows), 2026-09-26 after the fixes: **10/10 passed** (`npx tsc -b` and `npx vite build` also passed; the rebuilt dist is what the live 8177 demo serves, and report pages 4557 and 1 were verified in-browser to show the score, band, full-precision 0.5647 operating point, and stability wording instead of the withheld notice). Earlier runs on the pre-fix tree are superseded: four-then-seven of nine passed with the withheld-verdict and label drift failures recorded above.
- Port 8232 was occupied by a separate real-model process (health reported 4,551 reports); another process later appeared there independently. Neither was touched. For documented port 8232 instructions, confirm availability before starting the isolated server.

*Model proposes; an HSE reviewer disposes.*

**Evidence and related docs:** [`README.md`](../README.md), [`architecture.md`](architecture.md), [`implementation-plan.md`](implementation-plan.md), [`design-system-spec.md`](design-system-spec.md), [`design-system-token-gallery.md`](design-system-token-gallery.md).

## Claims removed or corrected from the superseded draft

Removed unsupported/wrong model claims: “PR-AUC 0.5826” as a current system result, a 0.5× PR-AUC runtime smoke-gate description, nine total gates, post-LoRA SD 0.15, barrier miss 0.19, old 0.28→0.10 values presented as current behavior, and the claim that ECE/Brier do not exist. The model startup does have a PR-AUC smoke gate; it does not turn the failing INT8 export-parity result into a pass. Replaced stale 71% / 5,162-row demo claims with the dated demo seed v3 measurements above; prior v2 measurements are historical. Corrected gold prevalence wording to 89.9% positive, not negative. The human-gold metrics cited above are from the historical 0.658108 operating point; current-threshold re-evaluation is documented in `artifacts/gold/gold_metrics_current_point_20260926.md` with its single-text limitation. Removed the unmeasured 5–10 minutes/report estimate and nonexistent setup commands (`app.init_db`, `app.seed`, `app.selfcheck`, `python -m app.gates --validate-gates`). Withdrawn claims that the current end-to-end suite passes. This handoff no longer carries the earlier 3-class metrics, chat-exclusion, D5/h5 threshold, vendor-comparison, or `GROUNDED_MODEL` assertions because no backing project evidence for them was established in this audit.