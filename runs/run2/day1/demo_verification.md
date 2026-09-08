# Demo Verification — REAL trained model (masked-v1 int8) — SIH 26165

- **Date:** 2026-09-08 · **Agent scope:** server (`:8177`), demo verification
- **Stack:** FastAPI @ `http://127.0.0.1:8177` · `RealOnnxClassifier` · `onnx:masked-v1/sif_multitask_int8.onnx` (T=1.6840) · SQLite `app/runtime.db`
- **Model val metrics (insurance/):** SIF AUC 0.9966 · operating point recall 1.0 @ precision 0.80 (thr 6.58e-5) · rules macro-F1 0.967 (confined_space low-support n=9, F1 0.714) · span token-F1 0.995
- **Method:** mock killed, `app/runtime.db` wiped, server restarted with `SIF_MODEL_PATH=artifacts/models/masked-v1`, bulk re-seeded, then every check run live against the real model. Zero browser console errors/warnings throughout.

---

## 1. Stack restart with the real model

| Step | Result |
|---|---|
| Kill mock | mock was `MockClassifier` pid **174691** (the `/tmp/sif-api.pid`→169811 entry was **stale**, process already gone). Killed 174691; `:8177` freed; stale pidfile removed. |
| Wipe DB | `app/runtime.db` (+`-shm`/`-wal`) deleted → clean state (`n_reports: 0`). |
| Start real model | `SIF_MODEL_PATH=artifacts/models/masked-v1 .venv/bin/python -m app.main` → pid **175427** (written to `/tmp/sif-api.pid`). Health: `RealOnnxClassifier`, `onnx:masked-v1/sif_multitask_int8.onnx`. Model loads in **0.38 s**; single-classify ~13–95 ms on the clamped CPU. |

## 2. Bulk re-seed — `bulk_ingest_5k.csv` (5,050 rows)

| Metric | Value | Bar | Verdict |
|---|---|---|---|
| Rows received / accepted / rejected | 5050 / 5050 / 0 | — | PASS |
| Verbatim `osha-2024010011` present in CSV | yes (exactly once) | required for near-dup beat | PASS |
| **Ingest rate (live, inline path)** | **5.33 reports/s** (947.53 s wall) | ≥30/s | **DEVIATION** |
| Post-ingest flag rate (score ≥ 0.5) | 3665/5050 = **0.7257** (mean 0.6984) | report measured | measured |
| Gate triggers during ingest | near_dup 3040 · drill 44 · negation 41 · confidence 36 · long_input 25 | — | — |

The 5.33/s is the **known inline single-text bottleneck** (`app/routes.py` ponytail note: "the real ONNX path needs the batch-worker queue — single-text calls can't hit the bulk SLA") compounded by the CPU clamp (H0 open). Per D3 the demo bulk step is **precomputed** and the honest bar is "report the measured number" — **this is the measured number**. Adjudicate: batch-worker queue, or accept precompute + quote 5.33/s.

## 3. Kathalguri money beat — VERIFIED, no fallback needed

Site×activity cell **Kathalguri GCS × DG exhaust duct inspection**, flag = `sif_score ≥ 0.5`:

| | rank | n | flagged | rate |
|---|---|---|---|---|
| Pre-ingest (seed corpus) | #2 | 31 | 31 | 1.000 |
| **Post-ingest (seed + 5,050)** | **#1** | **96** | **96** | **1.000** |

- **Flag-all requirement: MET — 96/96 target-cell rows flagged (rate 1.0000).** The 65 CSV rows (50 planted + 15 sampled) scored min 0.8074 / max 0.9838 / mean 0.9442; the 31 pre-seed rows all flagged by the real model (direct-classifier check). Nothing fell below 0.5.
- Margin over runner-up: **#2 = Workover Rig #7 × derrick/mast climbing, n=46 → margin 50.** Matches `script_90s.md` §6 arithmetic exactly (31 pre + 50 planted + 15 sampled = 96; "over runner-up 46").
- Live dashboard (`/api/density?by=site`) shows **Kathalguri GCS #1 (n=213, rate 1.00)**; `?by=activity` shows **DG exhaust duct inspection #1 (n=65, rate 1.00)**. (Site-level n=213 ≠ site×activity n=96 — the dashboard density is single-facet; the n≈96 figure is the site×activity cell, verified above.)

## 4. Thirteen demo cards — per-card PASS/DEVIATION

Band: HIGH ≥0.7 · MODERATE 0.4–0.7 · LOW <0.4 · GRAY = a gray-action gate fired. "ND" = near-dup banner fired (cosine 1.0 — all synthetic-corpus cards are verbatim in the training+synthetic index, see **F6**).

| Card | Expected | Actual score → band | wc | Top rule (prob) | Key gates | Verdict |
|---|---|---|---|---|---|---|
| contrast-red | HIGH · flag · **LoF dom** | 0.955 → HIGH | **true**(exp F) | **confined_space 0.44** (LoF 0.005) | neg/drill off ✓ · ND | **PASS** band/flag — DEV: rule=Confined Space not LoF; wc over-tag |
| contrast-green | LOW · no-flag | 0.014 → LOW | false ✓ | working_at_height 0.00 | neg/drill off ✓ · ND | **PASS** (the contrast: 0.955 vs 0.014) |
| gray-negation | GRAY (negation) | 0.833 (gray) | false ✓ | driving 0.67 | **negation fires → gray** ✓ | **PASS** |
| gray-drill | GRAY (drill) | 0.009 (gray) | false ✓ | confined_space 0.00 | **drill fires → gray** ✓ · ND | **PASS** |
| wc-baghjan-1 | HIGH · flag · **CS dom** · wc | 0.905 → HIGH | **false**(exp T) | **working_at_height 0.69** (CS 0.004) | ND | **PASS** band/flag — DEV: wc tag missed; rule=WAH not CS |
| wc-baghjan-2 | HIGH · flag · **EI dom** · wc | 0.991 → HIGH | **false**(exp T) | **hot_work 0.94** (EI 0.007) | ND | **PASS** band/flag — DEV: wc tag missed; rule=Hot Work not EI |
| wc-baghjan-3 | HIGH · flag · **HW dom** · wc | 0.957 → HIGH | true ✓ | **line_of_fire 0.99** (HW 0.047) | ND | **PASS** band/flag/wc — DEV: rule=LoF not Hot Work |
| hinglish | GRAY (language) | 0.140 (gray) | true(bop) | working_at_height 0.08 | **language fires → gray** ✓ | **PASS** |
| verbatim-osha | HIGH + near-dup banner · flag | 0.992 → HIGH | false ✓ | confined_space 0.84 (exp LoF) | **near_dup fires → banner** ✓ | **PASS** (banner: cosine 1.000 vs ingested row 2399) — DEV: rule=CS not LoF |
| long-report | HIGH · flag · neg OFF · chunked | 0.691 → MODERATE | false ✓ | hot_work 0.32 | **negation FIRES → gray** ✗ · long_input fires ✓ | **DEVIATION** — negation false-positive grays the encore card; band MODERATE not HIGH |
| mega-report | HIGH · flag · **all 7 rules** · wc | 0.977 → HIGH | true ✓ | line_of_fire 0.84 | neg off ✓ · long_input off ✓ | **PASS** band/flag/wc — DEV: only LoF lights high (hot_work 0.23, rest <0.1), not 7/7 |
| codes-only | GRAY (confidence) · codes-path accept | 0.115 → LOW | false ✓ | hot_work 0.01 | min_length OFF ✓ "codes path: LOTO" | **PASS** core (accepted, not eaten) — DEV: renders LOW slate not confidence-gray; EI 0.003 |
| first-aid-green | LOW · no-flag · neg OFF | **0.964 → HIGH · flag=TRUE** | false ✓ | confined_space 0.29 | neg off ✓ | **DEVIATION** — model REDS a first-aid case (false positive) |

**Tally:** 5 clean PASS (contrast-green, gray-negation, gray-drill, hinglish, verbatim-osha) · 5 PASS-on-band/flag with rule/wc deviation (contrast-red, wc-baghjan-1/2/3, mega-report) · 3 behavioral DEVIATION (long-report, codes-only, first-aid-green).

## 5. Adversarial suite — `tests/adversarial_suite.py` (real model)

**14/17 hard pass + 3 mock-tuned expectation deviations.** All 7 gates fire correctly, no crashes, schema valid, span invariant holds on every case. The 3 failures are **score expectations tuned for the mock's seeded Beta distribution**, not gate/robustness regressions:

| # | Case | Expectation (mock-tuned) | Real-model actual | Note |
|---|---|---|---|---|
| 2 | sarcasm | confidence gray band [0.4,0.6] | score **0.0117** → LOW, no gray | mock sha256-seeded the band; real model correctly scores the non-report very low |
| 13 | `LOTO not applied` | `energy_isolation ≥ 0.35` | EI prob **0.003** | mock added +0.35 for keyword anchors; codes-path acceptance still PASSES |
| 16 | hero weld | `hot_work == max(rule_probs)` | **line_of_fire 1.00** leads (HW 0.005); sif 0.927 HIGH | gate behavior correct (no gray — B1 fix holds); only rule-ranking expectation fails |

`api_smoke.py` → **SMOKE PASS** (span validity, determinism, 7 rules, well-control, all 7 gates, ingest, near-dup, override round-trip) — no score-tuned assertions, so unaffected.

`onnx_classifier_check.py` → **stale at step [1]** (`assert masked-v1 → MockClassifier`); masked-v1 is now populated, which is the entire point of this task. The check also hardcodes `MODEL_DIR=export-gate/final-green` (random-weights), not the real artifact. **Real-model contract verified inline** against masked-v1 (steps 2–6 equivalent): real load (int8, T=1.684), contract on sample, determinism, chunked 1500-word path, temperature hook, edge inputs, `dropped_spans == 0` — **ALL PASS**. The committed test needs its step-[1] fixture and `MODEL_DIR` updated (adjudicate owner; left unmodified to avoid cross-agent conflict).

## 6. E2E hero paste flow + money shots (browser, chrome-devtools MCP, 1920×1080)

Hero weld paste → **scored card with real highlight**: amber `▲ HIGH REVIEW PRIORITY`, Band HIGH, triage score 0.93, 95 ms, Rule Line of Fire 1.00 (2nd Confined Space 0.04), out-of-scope declared, evidence span `grinding` highlighted, Confirm/Not-SIF + "Model proposes, HSE disposes". No gray gate (B1 fix holds). **0 console errors.**

Screenshots in `runs/run2/day1/e2e/screenshots/`:

| File | Content |
|---|---|
| `real_scored_card.png` | hero weld paste → scored HIGH card, `grinding` span highlighted, LIVE header `5050 reports` |
| `real_density_kathalguri.png` | density view: **#1 Kathalguri GCS (213, 100.0/100, mean 0.95)** |
| `real_neardup_banner.png` | verbatim-osha → `⧉ Matches a training record — memory, not generalization`, cosine=1.000 vs row 2399, DUP badge |

**Integration note (F8):** the built dashboard has `VITE_API_BASE=http://localhost:8177` baked in, so served at `127.0.0.1:8177` (the doctrine address) it falls to OFFLINE/mock mode (CORS, no same-origin). All live shots were taken via `http://localhost:8177/`. Adjudicate: rebuild with `VITE_API_BASE=""` (same-origin) or pin the demo to `localhost`.

## 7. Deviations needing orchestrator adjudication (prioritized)

1. **F1 — `first-aid-green` HIGH false positive (0.964).** Real model REDS a steri-strip first-aid case. **Not** int8 quantization — fp32 agrees (0.980). Genuine model behavior on this phrasing ("spanner slipped… cut"). Adversarial #15 (a *different* first-aid text) passed. Rehearsed fallback exists ("this is why humans dispose"). Adjudicate: accept+fallback, or add a first-aid/low-energy guard.
2. **F2 — export parity gate FAILED on the shipped int8** (`manifest.export_gate_pass: false`; `export_gate.json pass: false`): int8 AUC drop **0.0916** (> 0.005), agreement **0.99296** (< 0.995); fp32 span Δlogit 5.78e-4 (> 1e-4). The shipped artifact does not pass its own two-tier gate. Demo-visible decisions are **not** quantization artifacts (int8 vs fp32 decision-equivalent on all probed cards), but the failed gate needs a ruling: ship int8 with disclosure, ship fp32 (`SIF_MODEL_QUANT=fp32`), or re-export.
3. **F3 — rule-attribution drift (7 cards).** Triage score is well-calibrated (contrast 0.955 vs 0.014; near-dup; Kathalguri) but the *dominant rule bar* frequently differs from the demo annotations (contrast-red/verbatim: LoF→Confined Space; wc-1: CS→Working-at-Height; wc-2: EI→Hot Work; wc-3 + hero weld: Hot Work→LoF; mega: only LoF lights). The "names the rule — Line of Fire" beat needs per-card re-scripting or acceptance. (Rule macro-F1 0.967 on val, but confined_space low-support n=9.)
4. **F4 — `long-report` negation false-positive.** The 380-word encore card grays via negation (`'no'~'damage'`); the gate is arguably correct (the report does say "no damage") but the annotation expected it OFF. Encore "chunked scored card" becomes a gray card (chunked badge still fires).
5. **F5 — well-control keyword gap.** App `_WELL_CONTROL_KEYWORDS` ⊂ label_spec `wellcontrol_keywords` — missing `christmas tree`, `h2s`, `wellhead`, `workover`, `lost circulation`, `gas migration`, `snubbing`, `coiled tubing`. wc-baghjan-1/2 lose the wc tag (rely on christmas tree/h2s); wc-3 gets it via `bop`. Align app list to the frozen spec.
6. **F6 — near-dup banner fires on every synthetic-corpus demo card** (contrast pair, wc-1/2, gray-drill). By design (`runtime_near_dup_index_includes_synthetic: true`) — the demo cards ARE training rows — but the 90 s script's beats 1–4 expect clean cards. Adjudicate: accept the banner as the "memory, not generalization" story, exclude the 13 demo texts from the index, or re-choreograph.
7. **F7 — bulk ingest 5.33/s < 30/s SLA** (inline path + clamp; see §2). Precompute doctrine (D3) already covers the demo; ruling needed only on whether to quote 5.33/s or build the batch-worker queue.
8. **F8 — dashboard `VITE_API_BASE=localhost:8177`** breaks same-origin at the 127.0.0.1 doctrine address (see §6). One-line rebuild.
9. **F9 — span quality.** Substring-validity 100% (`dropped_spans=0`) but highlights are sub-word fragments (` grinding`, `ethe`, `striking scaffold`), not the annotated phrase-level spans — weakens the "shows you exactly why, in the report's own words" beat. (val span token-F1 0.995, but demo/OOD texts fall to the top-token fallback.)
10. **F10 — onnx_classifier_check stale** (see §5): step-[1] fixture + hardcoded `MODEL_DIR` assume masked-v1 empty. Update to the real artifact.

## 8. Final state — DEMO-ARMED, left running

- Server **live** on `127.0.0.1:8177`, pid **175427** (`/tmp/sif-api.pid`), `RealOnnxClassifier` `onnx:masked-v1/sif_multitask_int8.onnx`, **5,050 reports**, 0 overrides.
- `app/runtime.db` holds the ingested bulk corpus (working-tree-modified runtime artifact — **not** committed; no `git add`/`commit` performed anywhere).
- Ollama at `:11434` untouched (left running per instructions).
- Scratch helpers (untracked, not committed): `.run/bulk_ingest_client.py`, `.run/verify_cards.py`, `.run/cards_result.json`, `.run/bulk_ingest_result.json`.
