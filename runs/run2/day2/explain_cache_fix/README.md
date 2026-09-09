# FIX — Poisoned explanation cache (final_audit_ps_compliance F1 / final_audit_rehearsal F3)

Date: 2026-09-09 ~21:30–23:55 IST. Owner: audit-fix wave, explanation-cache agent.

## Root cause

`artifacts/explanations/precompute.py`'s `_NullStorage` gate stub implemented only
`nearest()`. After D25, `gate_near_dup` calls `nearest_base_batch()`/`nearest_session()`
→ `AttributeError` → `run_gates` degraded it to a triggered `gate error: AttributeError:
'_NullStorage' object has no attribute 'nearest_base_batch'` GateState
(`app/gates.py`) → `render_template` baked it into the template → qwen3:4b reworded the
poisoned template into plain-English prose → 63/63 cached explanations (13 demo cards +
top-50 feed reports) contained the error string in BOTH `template` and `reworded`.

## Fix (code)

`artifacts/explanations/precompute.py`:
1. `_NullStorage` now implements `nearest_base_batch` (returns `[None] * len(vecs)`)
   and `nearest_session` (returns `None`) — every Storage method the gates call.
2. The harness now attaches the REAL storage by default (`SQLiteStorage` over `--db`
   + the corpus near-dup index), mirroring `routes._predict_with_gates` exactly —
   including the `well_control`/`flag_thr` kwargs added to `run_gates` tonight —
   so cached gate text matches live behavior (e.g. verbatim-osha's near-dup banner
   appears in the post-state DB's cache and correctly not in the pre-state's).
   `--null-gates` forces the stub (offline/test).
3. Serial warmup of the threadpoolctl ctypes scan (`_blas_single_thread`, added to
   storage.py tonight by another agent) and the NSS/getaddrinfo path BEFORE workers
   start — without it, a 4-worker run deadlocked (import lock vs dynamic-loader
   lock; py-spy evidence). Runs with the warmup: 2× deadlock-free, 0.44–0.50 rows/s.

`app/tests/explain_check.py`: new section `[4c]` — loads the precompute harness,
runs `_gen_one`/`_predict` under `_NULL_STORAGE`, asserts no `gate error` text in the
payload and that near_dup degrades to `index empty` instead of an error state.
Full suite: **EXPLAIN CHECK PASS** (last run 23:5x IST, port 8195).

## Purge + regeneration

- The 63 poisoned rows were purged twice over the evening as the demo DB was rebuilt
  by the demo-rebuild agent (mid-run swaps lost one completed regeneration — rows are
  keyed by sha256(text+model+threshold), so re-runs are idempotent and resume-safe).
- Final regeneration: `SIF_MODEL_PATH=artifacts/models/masked-v2/sif_multitask_int8.onnx
  precompute.py run --workers 4 --timeout 60` over 63 rows (13 cards + top-50 feed)
  per DB — 63/63, 0 errors, real ONNX + real ollama (ledgers: `results_demo_pre.jsonl`,
  `results_demo_post.jsonl`, `results_runtime.jsonl` for the lost first run).
- Stray rows cleaned from the live DB: ids 4549–4557 (5 `smoke` test rows from another
  agent + 3 persisted live-pastes from browser verification + 1 from the post-swap
  re-verification paste) deleted from reports/predictions/embeddings/report_hashes.
  All four tables now 4,548 rows, MAX(id)=4548.

## Acceptance (all PASS)

| DB | reports | precomputed | rows with 'gate error'/'_NullStorage'/'AttributeError' |
|---|---|---|---|
| `app/runtime.db` (live :8177) | 4,548 | 63 | **0** |
| `artifacts/demo/demo_pre.db` | 4,548 | 63 | **0** |
| `artifacts/demo/demo_post.db` | 5,048 | 70 | **0** |

- `acceptance_payload_dump.txt` — full payload dump of the live DB's precomputed
  table (63 rows); `grep -c 'gate error'` → 0 (grep exit 1).
- Live HTTP (`POST /api/classify?explain=1&llm=0`, stateless, no DB writes):
  contrast-red / verbatim-osha / wc-baghjan-1 → `cached=true, source=ollama`,
  clean reworded + template; feed report #4548 → clean.
- Browser (Playwright, live :8177): contrast-red "Why this score?" panel renders
  "phrased by local LLM · cached" with clean prose, no error strings —
  screenshot `verify_contrast_red_panel_postswap.png` (pre-swap shots of all three
  cards also kept: `verify_contrast_red_panel.png`, `verify_verbatim_osha_panel.png`,
  `verify_wc_baghjan_1_panel.png`).

## Evidence files

- `acceptance_payload_dump.txt` — live-DB payload dump (grep target).
- `demo_post.poisoned.db` — pre-purge copy of demo_post.db (63 poisoned rows intact).
- `results_demo_pre.jsonl` / `results_demo_post.jsonl` / `results_runtime.jsonl` —
  precompute run ledgers (126 rows regenerated, 0 errors; runtime.jsonl is the first
  run whose writes were lost to a demo-DB swap, kept for the record).
- `precompute_results.poisoned-ledger.jsonl` — the original poisoned run's ledger.
- `verify_*.png` — browser screenshots.

## Notes / handoff items

- The live server's in-memory session near-dup tier still holds the 9 deleted rows
  until its next restart (the demo script restarts after `cp demo_pre.db
  app/runtime.db`, so this self-heals; I did not restart :8177 — demo-rebuild
  agent's call).
- WATCH ITEM (not mine, for the storage.py owner): `_blas_single_thread`'s
  threadpoolctl init is not race-safe under multi-threaded first use (deadlock
  observed in the precompute harness when workers raced it against getaddrinfo's
  import-lock path). The live server is single-user at demo time, but concurrent
  first-ever near-dup queries could in principle trip it.
- The dashboard's paste flow now persists (`?persist=1`, routes.py 21:21) — any
  browser-driven paste verification adds a report row; clean up afterward.
