# HANDOFF — SIH 2026 PS 26165 (OIL)

## Current status — read this before relying on historical material

This is a current-state handoff for the local-first triage and evidence-extraction application. The claim boundary is **triage, extraction, and queue compression only**. Do not claim injury/fatality prediction, prediction accuracy, deployment-prevalence precision, or reviewer-time savings. The approximately 20% literature figure refers to the share of **recordable injuries** with SIF potential (BST/Mercer ORC 2011; Martin & Black 2015), not the share of reports or near-miss reports.

The implementation is FastAPI + SQLite + NumPy + pure-Python gates + ONNX Runtime INT8 ModernBERT, with a React 19 / TypeScript / Vite 8 / Tailwind 4 dashboard using HashRouter. Runtime is designed for local/offline use; no PyTorch runtime or Docker critical path. The UI has queue, report, analytics, ingest, decisions, and settings routes. The adopted UI model is Astryx-derived semantic tokens mapped to Tailwind 4 plus motion-primitives interactions, not StyleX. The confirmed docs exist: [`docs/design-system-spec.md`](docs/design-system-spec.md) and [`docs/design-system-token-gallery.md`](docs/design-system-token-gallery.md).

## Current measurements and caveats

- Demo seed v3 (2026-09-26): 4,548 rows; 338 flagged (7.43%) at threshold 0.5647. This is a synthetic-seed measurement, not field prevalence. Source: [`docs/overhaul-summary.md`](docs/overhaul-summary.md).
- Runtime masking and self-consistency (`SIF_SELF_CONSISTENCY_N=4` by default) are enabled. In the paired near-miss probe, adding “Fortunately no injury occurred” changed 0.5819 → 0.3042 without masking (−0.278), and 0.5819 → 0.5632 with masking (−0.019). Self-consistency supports reliability, not validity.
- Ten general gates, seven barrier-absence gates, and `verdict_stability` are live (18 total). The stability gate routes an N-variant result to review when fewer than 75% of variants agree; it does not alter the score or operating point. Expert-authored probe, not human gold (2026-09-27; threshold 0.5647): barrier n=22 flag recall 0.2727 and routed recall 0.8182; mechanism n=12 flag recall 0.8333 and routed recall 0.9167; benign n=16 false-flag rate 0.0625 and false-gray rate 0.0625, with 0/16 benign barrier-gate false-grays. Routed recall counts model flags OR gray-gate routing, not model flags alone. Source: [`artifacts/qa-evidence/probe_process_safety.json`](artifacts/qa-evidence/probe_process_safety.json).
- Calibration diagnostics exist: temporal test n=17,731 ECE 0.1475 / Brier 0.1580; gold-consensus n=407 ECE 0.1765 / Brier 0.1830. These do not establish deployment calibration.
- Bulk ingest measured approximately 7.3 rows/s in the cited 500-row run. The old 45.6 rows/s claim is withdrawn.
- The INT8 export gate is `pass:false` (agreement 0.993; AUC drop 0.1305).
- `/api/classify` and stored `/api/reports` GET responses return the server-owned band, `flag_threshold`, and gray-band bounds. Stored rows are re-banded from the current classifier operating point when read. Date filters are available on reports and density, and analytics exposes a custom range. Ingest-job DELETE supports cooperative cancellation before commit; once a job is committing or finished, cancellation is rejected (409).
- The real-model adversarial suite now passes 18/18 cases plus #10b; its contracts accept ensemble-appropriate case #2 dispositions and permit a genuine `verdict_stability` gray while still rejecting other unexpected gray routes. The isolated browser e2e suite passed 10/10 in the prior 2026-09-26 run (port 8232 throwaway-DB stack with the real INT8 classifier).

See [`docs/overhaul-summary.md`](docs/overhaul-summary.md) for exact command outcomes, limitations, and current run instructions. For the runtime architecture see [`docs/architecture.md`](docs/architecture.md); for design decisions see [`docs/backend-stack-decision.md`](docs/backend-stack-decision.md) and [`docs/frontend-stack-decision.md`](docs/frontend-stack-decision.md).

## Fresh local setup

Prerequisites: Python 3.14, Node/npm, and the INT8 ONNX model at `artifacts/models/masked-v2/sif_multitask_int8.onnx`. The model artifact is not tracked by git; obtain it from the packaged bundle (the pendrive payload) or use a working tree where it is already present. Installing dependencies requires network access; inference is local. A fresh start creates an empty `app/runtime.db`; this setup does not seed demo rows.

```bash
# From the repository root
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cd dashboard && npm ci && npx tsc -b && npx vite build
cd ..
./run.sh
```

Open `http://127.0.0.1:8177/#/queue`. Other routes: `/#/report/1`, `/#/analytics`, `/#/ingest`, `/#/decisions`, `/#/settings`. Check `http://127.0.0.1:8177/api/health` for `"classifier":"RealOnnxClassifier"`. Stop a process started through `run.sh` with `./run.sh --stop`.

## Isolated browser e2e

Never use the live 8177 server for mutating browser tests. From the repo root, start the isolated server after confirming port 8232 is free; the Playwright config does not manage server lifecycle:

```bash
E2E_PORT=8232 bash dashboard/e2e/serve-isolated.sh
```

In a second terminal:

```bash
cd dashboard && PLAYWRIGHT_BASE_URL=http://127.0.0.1:8232 E2E_API=http://127.0.0.1:8232 npm run test:e2e
```

Stop only the process you started with Ctrl-C and confirm its port is free. The script defaults to 8232; `E2E_PORT` can override it. The Playwright config does not manage server lifecycle, so start this server yourself. During this audit port 8232 was occupied by another real-model process and a later process appeared there independently; both were left untouched. Tests were run on 8234 and did not fully pass.

## Superseded historical material

The former mission plan, vendor comparisons, proposed architecture, timelines, estimates, and acceptance targets have been removed from this handoff because they mixed plans with shipped facts and carried unsupported or contradictory claims. Use the current docs above. Do not revive old statements about 3-class metrics, chat exclusion, a D5/h5 threshold, “vendor comparison” results, or `GROUNDED_MODEL`: no primary in-repository evidence for those assertions was established in this audit. Do not state “20–25% of reports”; the literature figure is recordable injuries. The current product claim remains triage + extraction + queue compression only.