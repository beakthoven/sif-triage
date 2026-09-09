# Final latency re-measure — masked-v2 (ship config), machine UNCLAMPED

- **Date:** 2026-09-09 ~22:10–23:00 IST (audit-fix wave, night before deadline)
- **Model:** `artifacts/models/masked-v2/sif_multitask_int8.onnx` (int8, single-text D27 path), T=1.6484, flag threshold cal 0.658108
- **Replaces:** the on-record numbers were masked-v1 (KB §10: p50 11.9 / p95 19.7 / p99 40.2 ms; bulk 33.73/s). This is the v2 re-measure the record needed.
- **Machine state verified unclamped first:** governor=performance; 16-thread all-core burn held **3.44–4.76 GHz** (mean 3.94 GHz) for 15s — no 0.85 GHz clamp. Idle `scaling_cur_freq` reads 1.3–2.4 GHz (normal amd-pstate idle downclock; boost under load confirmed). Watch item stands: Tctl hits ~99–100°C under sustained all-core load (thermal, not platform).
- **Scripts:** `runs/run2/day2/latency_v2_final.py` (A/B/C below, output `latency_v2_final.json`), `runs/run2/day2/ingest_remeasure.py` (clean ingest re-run).

## Headline table (vs v1 record)

| Measurement | masked-v1 (on record) | **masked-v2 (this run)** | SLA | Verdict |
|---|---|---|---|---|
| Model-only, real test rows ×200, p50 / p95 / p99 | 11.9 / 19.7 / 40.2 ms | **11.39 / 17.66 / 20.52 ms** | p95 <100 ms | PASS |
| Model-only, seq128 single window ×200, p50 / p95 / p99 | (19.7 p95 was this-class) | **21.11 / 24.56 / 27.77 ms** | p95 <100 ms | PASS |
| Model-only fp32 fallback, seq128 ×50 p50 / p95 | 52 ms-class | **44.23 / 48.16 ms** | — | reference |
| **API end-to-end, live :8177** (POST /api/classify, full gate stack incl. MiniLM near-dup over the 70k index), seq128 ×200 | ~48–56 ms (card pastes, Day-1 night) | **p50 42.54 / p95 46.92 / p99 50.01 ms** | p95 <100 ms | PASS |
| API end-to-end, live :8177, real test rows ×200 | — | **p50 28.04 / p95 56.03 / p99 85.38 ms** | p95 <100 ms | PASS |
| Bulk ingest, 5,050-row demo CSV → throwaway server + DB | 33.73 /s (v1); 37.3 /s (v2, Day-1 night) | **45.56 /s** | ≥30 /s | PASS |

All A numbers: in-process `RealOnnxClassifier.predict` (the exact ship path), 8 intra-op threads, warmup excluded. A2 uses 200 real `artifacts/corpus/test.jsonl` masked rows (seed 20260909; 1/200 multi-window chunked). B uses the LIVE demo stack (n=5,048 reports, near-dup over 70,398-row corpus index + session tier) — measured while the demo-rebuild agent's stack was on the **patched** tree (see §2).

## 2. SEV2-class finding FIXED this wave: OpenBLAS spin threads starve the next ORT run

**Symptom:** live `/api/classify` p50 was **~150 ms** on the quieted stack tonight (min 121), 3× the ~48 ms from Day-1 night. Model-only was 21 ms — so ~110–130 ms of "overhead" that no single gate explained (all gates ≤7 ms combined).

**Root cause (bisected in-process):** the near-dup gate's numpy BLAS matmuls (70,398×384 corpus index + session tier). OpenBLAS's multithreaded gemm/gemv leaves its worker threads spinning after the call; the **next** onnxruntime intra-op run (the following classify) then starves on contended cores: predict 21 ms → 77–97 ms after a single near-dup matmul. The matmuls themselves are memory-bound (108 MB fp32 stream) — 2.9 ms at any thread count, so threads buy nothing there.

**Fix (app/storage.py, this wave):** wrap the three near-dup matmul sites (`nearest_base_batch`, `nearest_session`, `nearest`) in `threadpoolctl.threadpool_limits(limits=1, user_api="blas")` via `_blas_single_thread()` (graceful no-op fallback if threadpoolctl absent; added to requirements.txt). Measured, same process, quiet machine:

| Path | before fix | after fix |
|---|---|---|
| full in-process ship path (predict + validate + 8 gates) | 126.9 ms p50 | **28.1 ms p50** |
| predict immediately after near-dup gate | 76.6 ms p50 | 13.4 ms p50 |
| near-dup gate itself | 2.9 ms | 2.9 ms (unchanged) |
| live :8177 /api/classify seq128 ×200 | p50 ~150 ms | **p50 42.5 ms** |

Gate results byte-identical before/after (same triggered state + detail strings). Regression battery (below) ran on the patched tree — all near-dup assertions green.

**Deployment note:** the fix takes effect on server restart. The live :8177 stack was restarted by the demo-rebuild agent at 22:08 IST (after the 22:04 patch) and serves the fixed latency (browser-measured 51 ms on the contrast-red card, screenshot `e2e_02`).

## 3. Bulk ingest

Run 1 (22:13, full script): 5,048 accepted / 5,050 received (2 exact-dup skips, designed), wall 235.9 s → **21.40/s — FAIL**, but the phase ran with Tctl ending at **100°C** straight after 40 min of wave-wide load (ollama explanation regen at 700%+ CPU) — heat-soaked, throttled. Treated as contaminated.

Run 2 (clean window, `ingest_remeasure.py`, gated on Tctl <85°C + load1 <2):

| Run | Tctl pre/post | load1 pre | wall | rate | Verdict |
|---|---|---|---|---|---|
| 1 (contaminated) | ~55→100°C | high | 235.9 s | 21.40/s | invalid (thermal) |
| 2 (clean) | 54.2→88.0°C | 1.92 | 110.8 s | **45.56/s** | **PASS (≥30/s)** |

The clean run is **+22% faster than Day-1 night's 37.3/s** on identical input — consistent with the §2 fix: pre-fix, each chunk's corpus-tier matmul poisoned the following per-row int8 predicts in the ingest loop too.

## 4. Regression battery (all vs masked-v2, test ports 8191–8195, throwaway DBs)

Log: `runs/run2/day2/regression_log.txt`. Run 22:07–22:08 IST on the current tree (incl. the wave's WC-watch gate + persist=1 changes and the storage fix above).

| Suite | Result | Notes |
|---|---|---|
| `app/tests/onnx_classifier_check.py` | **PASS** | now honors `SIF_MODEL_PATH` (default masked-v2; was hardcoded masked-v1) |
| `app/tests/postreview_fix_check.py` | **FAIL — real model regression, see §5** | sections [1][3][4][5][6][7][8] all PASS on v2 (verified via non-raising harness); only the [2] positional scan fails |
| `app/tests/near_dup_embed_check.py` | **PASS** | verbatim 1.000 / twin 0.997 / unrelated 0.342 vs threshold 0.91 |
| `app/tests/explain_check.py` | **PASS** | template + fallback + cache + endpoint wiring (LLM disabled) |
| `app/tests/api_smoke.py` | **PASS** | incl. new 8th gate (well_control_watch) + persist=1 round-trip |
| `tests/adversarial_suite.py` | **PASS 18/18** (+empty-text 422) | 17+1 incl. new #18 novel well-control precursor → WC-watch gray |
| `data_pipeline/pattern_mine_selfcheck.py` | **PASS** | incl. wilson parity vs app.routes |
| `artifacts/demo/selfcheck_demo_pack.py` | **PASS** | 5,050-row CSV intact, Kathalguri re-rank arithmetic green |

## 5. OPEN FINDING: masked-v2 positional dead zone is worse than v1 (not fixed tonight)

`postreview_fix_check.py` [2] plants a hazard sentence ("Worker fell 6 meters … taken to hospital") at 16 positions inside filler text and asserts worst-case score >0.20, valleys(<0.4) ≤5 — the stride-64 fix acceptance bar, met by masked-v1:

| Model | min score | valleys (<0.4) / 16 |
|---|---|---|
| masked-v1 | 0.251 | 2 |
| **masked-v2** | **0.030** | **13** |

v2 fires when the hazard is near a window start (0.79 at offsets 0/64) but decays to 0.03–0.19 mid-window — **below the gray band → silent auto-green** on long (>~90-word) reports whose hazard sentences all land mid-window. Day-1 demo cards are unaffected (their hazard phrases repeat/appear early; long-report card scores 0.75). This is inherent to CLS pooling + v2's training mix — NOT fixable in test/config code, and retraining is out of scope tonight. **Suggested mitigation for adjudication:** route `chunked=True` inputs with score < gray_band_low to review instead of auto-green (one-line gate change), or accept + disclose. The test was deliberately NOT weakened; it now correctly fails against the ship model.

## 6. Browser e2e (live :8177, 1920×1080, Playwright)

Five key screens, **zero console errors** (the single 404 in the log is another agent's dead tab on :8191, unrelated origin):

| Screenshot | Screen | State |
|---|---|---|
| `runs/run2/day2/e2e_01_feed.png` | Feed (live queue, 200 reports) | LIVE · masked-v2 · amber band doctrine |
| `runs/run2/day2/e2e_02_paste_contrast_red.png` | Live paste: contrast-red card | HIGH 0.93, **51 ms**, Line of Fire 0.85 leading, WC tag, persisted #4554 |
| `runs/run2/day2/e2e_03_density.png` | Density table | mid-reseed state (demo agent rebuilding; Kathalguri #2 pre-ingest) |
| `runs/run2/day2/e2e_04_patterns.png` | Patterns (lift-ranked, Wilson CIs) | Kathalguri DG-duct cell present |
| `runs/run2/day2/e2e_05_review.png` | Review queue | all 4 sentinel gate types incl. new well-control watch |

Note: demo DB count read 4,548 during capture — the demo-rebuild agent was mid-reseed; screenshots reflect the live stack at 22:20–22:45 IST.
