# 53 — Visual QA: the two live input flows (paste-classify, bulk ingest)

Date: 2026-09-25. Target: isolated instance `http://127.0.0.1:8199/` — fresh copy of `artifacts/demo/demo_pre.db` (4,548 reports), `RealOnnxClassifier` on `artifacts/models/masked-v2/sif_multitask_int8.onnx` (verified via `/api/health`). The frozen 8177 stack was never touched (a concurrent session was driving it; the shared MCP browser was contended, so all captures below come from a private Playwright chromium instance, viewport 1440×900, read back as images). Read-only against source; server killed after. Evidence: `artifacts/qa-evidence/flows-*.png` (16 files).

## Method / timings measured

- Classify latency (browser `performance` resource entries, per request): first call **668 ms** (model warm-up), then **117 ms** and **100 ms** steady-state. Submit→rendered verdict settle: 394–818 ms wall.
- Bulk ingest: click → **native `confirm()`** → `GET /live_ingest_500.csv` (200) → `POST /api/ingest` with the 500-row CSV JSON. Server-side duration measured directly: **80.6 s** for 500 rows (≈6.2 rows/s). Client budget is **90 s** (`api.ts ingestCsv`), so the beat survives with ≤10 s margin on this machine.
- Console: **zero** errors/warnings/pageerrors across all runs. Network: **zero** non-200 responses.

## FLOW 1 — Paste & classify (`flows-03/04/05-*`)

What the user sees, in order: empty textarea (placeholder "Paste a UA/UC or near-miss report here…", disabled Classify + `Ctrl+Enter to classify` hint) → button swaps to "Classifying…" with spinner while the verdict panel shows skeleton bars + "Classifying…" → settled card. Loading feedback is production-shaped. Defects, in priority order:

1. **The flagship SIF case does not flag.** Well DKD-3 BOP-blind-ram-removed / 3-t suspended load / workers in cellar / no PTW renders as **two stacked "Manual review required" cards**: "Uncertain score" (`score 0.487 in gray band [0.4, 0.6]`) and "Possible well-control concern" (`triage score 0.487 < flag threshold 0.658`). A textbook SIF precursor lands at 0.487 — below flag threshold. The honest gate copy saves it from looking broken, but a judge sees "model unsure" on the exact scenario the product exists for. Model-underscore finding for the redesign plan, not just UI.
2. **Same report rendered twice, no single source of truth.** Two near-identical review cards (same quote, same metadata, two Confirm/Not buttons each) with no combined score/band/evidence summary.
3. **Inverted information asymmetry.** The benign card is the richest in the app: green "Low review priority", **triage score 0.01**, three "Matching life-saving rules" bars (Working at Height / Driving / Energy Isolation, all 0.00), "Why this score?", "Record review outcome". The dangerous card shows **no score band, no rule bars, no evidence spans, no latency** — only terse mono lines inside "Technical detail". Contrast between dangerous and benign is legible (review vs green) but the danger case gets the least explanatory surface.
4. Adversarial "Fire drill completed, no hazards." → no false alarm: single card "Report mentions a drill or test", `drill badge: fire drill`, routed to review ("never auto-cleared"). Correct, but the drill card hides the score entirely, and visually it is the same "Manual review required" family as the killer BOP case — the two could not be told apart at a glance.
5. "UA/UC" jargon in the placeholder is unexplained; no example text or paste-affordance affordances. Minor.

## FLOW 2 — Bulk ingest / demo batch (`flows-06…09-*`)

Sequence as the user experiences it: Insights → Locations table → "Run demo batch" → **native browser confirm** ("Ingest the 500-report demo batch? Real classification, about 15 seconds. This runs once per session.") → button swaps to disabled "Ingesting reports…" + a thin paced progress bar (0→92% in ~15 s, aria-valuenow ticking) → **~75 s silent crawl 92→100%** → red inline "**Ingest failed — live data unchanged. Check the API and retry.**" → table unchanged.

Defects, in priority order:

1. **False failure on the money beat (SEV-1).** The server actually finished and persisted all 500 rows (`/api/health` 4,551→**5,051**); a direct re-POST returned `received:500, accepted:0, skipped_duplicates:500`. The client aborted at its 90 s budget while the server kept going (80.6 s measured on a direct call, >90 s under browser overhead) and then rendered "live data unchanged" — a false statement. A judge who clicks retry double-ingests 500 more rows (dedup hides them, but the count/queue churn).
2. **The dialog promises "about 15 seconds"; reality is 80–90+ s** on this demo laptop (~6 rows/s vs the 37 rows/s in code comments). Either shrink the batch, raise the budget, or stream.
3. **Progress bar is paced fiction, not measured progress.** It reaches 92% on a timer, then idles while the real work continues. No row count, no ETA, **no cancel** during the ~90 s.
4. **No in-session re-rank on failure.** After the false failure the density table stays frozen at the pre-state. The re-rank is real server-side (Kathalguri GCS 88→213, #2→#1; verified via `/api/density`) and appears **only after a manual reload** (`flows-09-density-after-reload.png`) — where the "Movement" column resets to 0 for every row, killing the climb story on any reload.
5. Density table itself: **Flag rate renders "100.0per 100" (missing space) on every row** and every row shows Flagged == Reports (sif_rate 1.0) — the column carries zero signal as rendered and reads as broken.
6. Error surfacing itself is good: honest red inline message, button re-enabled for retry, nothing fabricated. That is the right pattern — it is just being applied to a failure that never happened.

## Verdict

Flow 1: production-shaped interaction and latency (~0.1 s), but the verdict surface undersells the model on the flagship case and duplicates the review card. Flow 2: demo-shaped — native confirm, paced progress, promise/reality gap of 5–6×, and a false-failure path that can corrupt the demo narrative. Both flows need the ingest path fixed and the verdict card unified (one card: score, band, rules, evidence, decision) before the finale.

Files: flows-01-initial-landing, flows-03-sif-{typed,loading,result}, flows-04-benign-{typed,loading,result}, flows-05-adversarial-{typed,loading,result}, flows-06-insights-before, flows-07-ingest-during-{00,05}, flows-07b-probe-after, flows-08-insights-after, flows-09-density-after-reload (all under `artifacts/qa-evidence/`).