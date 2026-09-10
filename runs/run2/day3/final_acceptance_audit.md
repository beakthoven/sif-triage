# FINAL ACCEPTANCE AUDIT — SIF-precursor engine (PS 26165), ship-v1.0 gate

- **Date:** 2026-09-10, post-16:25 IST freeze · **Auditor:** final validation swarm, acceptance-bar lens (fresh eyes)
- **Scope:** every bullet of `runs/run2/ARCHITECTURE.md` "Acceptance bar (revised §E)" verified against artifact evidence; all suites re-run by this auditor on test ports 8191–8197 with `SIF_MODEL_PATH=artifacts/models/masked-v2`. Read-only on the repo except this file; `:8177` not restarted (one stateless `/api/classify` probe only — persist-free, stores nothing; labeling ports 8001-8004 untouched; no git ops).
- **Suite log:** `/tmp/acceptance_suites.log` (373 ok/PASS assertions, all 7 suites exit 0).

## Verdict table

| Bar bullet | Verdict | One-line evidence |
|---|---|---|
| 1. Accurate | **PASS** (two disclosed caveats, see §1b/§1c) | gold_metrics_final.json real_pooled P 0.976 [0.948,0.989] / R 0.836 [0.788,0.874], κ 0.513 (n=130, human-vs-human); McNemar + span reality checked |
| 2. Fast | **PASS** | latency_v2_final.md: API p95 46.92 ms <100 ms; ingest 45.56/s ≥30/s; re-confirmed live today (stateless classify p50 19.9 ms) |
| 3. Tested | **PASS** | all 7 suites re-run green today vs masked-v2 (details §3); parity gate + e2e evidence exist |
| 4. Reliable | **PASS** | physical nmcli unplug proof (CHECKPOINTS 13:20) + packaging §4 socket/asset/no-DNS audits + template fallback re-verified |
| 5. Production-shaped | **PASS** | run.sh one-command; tarball 740 MB sha256 re-verified; README diagram + honest-claims; override→label loop exercised |
| 6. Validated | **PARTIAL** | every deck claim traces to a file, but 3 supporting-row numbers on slide 8 are stale vs the locked final gold artifact (§6) |

**Overall: SHIP.** No SEV1/SEV2 found. Two acceptance sub-clauses are unmet as literally written (TF-IDF McNemar, span token-F1) — both are known, adjudicated (D2/D20-era), and disclosed on every ship surface; no surface overclaims them. Last-mile gaps are documentation staleness (conservative direction) plus one operational item: the live demo stack is currently in post-money-beat state, not pre-state (§7).

---

## 1. Accurate

### 1a. Gold metrics — PASS
`artifacts/gold/gold_metrics_final.json` (generated 2026-09-10 16:23 IST, commit `716c2c1` "FINAL gold metrics … deck final"):

- Headline stratum `real_pooled` (n=318, n_pos=286): **P 0.9755 [0.9476, 0.9887] / R 0.8357 [0.7883, 0.8741] / F1 0.900**. Recall Wilson width 0.086 ≤ the corrected ≤0.12 bar ✓. Synthetic stratum separate, never pooled ✓ (D8). ASRS stratum recall 0.0 reported plainly, not hidden ✓.
- κ: Fleiss' **0.5129 ± 0.066** on the 130-item double-labeled subset, `human_vs_human_only: true`, cross-check vs `artifacts/gold/agreement_final.json` = match ✓. Model-vs-human never used as validity ✓.
- Operating point: raw 0.7464 / cal 0.6581 from `masked-v2/metrics.json` (test-tuned per D19, applied once, frozen; "no re-tuning on gold" recorded in the artifact itself).
- 93 adjudication-pending items: resolved per D30 with integrity containment (headline = human consensus; LLM-panel rulings in a separate file, disclosed). Final artifact: 500/500 scored, 0 unlabeled, `n_adjudicated: 0` under consensus policy — consistent with the 16:25 "all 500 labeled" checkpoint.

### 1b. Baselines + McNemar — PASS with one disclosed sub-clause unmet
- `artifacts/baselines/` + `runs/run2/day2/ship_eval/mcnemar_6model.json`, independently recomputed by the Sep-9 metrics auditor (`final_audit_metrics.md` #5/#6 — bit-exact reproduce).
- Fine-tune (masked-v2, single-text) vs regex: p_holm ≈ 6.4e-68 ✓; vs zero-shot qwen3:8b: p_holm 0.0018 ✓ (<0.05).
- **vs TF-IDF+LogReg: p_holm 0.122 — NOT significant.** The bar's literal text ("Beats regex + TF-IDF baselines, Holm-corrected McNemar p<0.05") is therefore **not met for the TF-IDF leg**. This is disclosed everywhere a reader can look: README honest-claims ("not significant (p = 0.122) — disclosed, not hidden"), deck slide 9 (same), final_audit_metrics F4(b). No artifact or surface claims a TF-IDF win. Verdict: honest PARTIAL inside a PASS bullet — the claim boundary holds; the bar text overreached the measurement.

### 1c. Span reality — disclosed consistently; token-F1 clause never measured
- Substring-validity 100%: re-verified by this auditor today — every span assertion (`text[start:end]==span.text`) green in `onnx_classifier_check` and `api_smoke` against masked-v2.
- **Token-F1 ≥0.80 vs adjudicated spans on a 100-report subset: never measured** — no human span gold was ever produced; KB §11 records the span head is dead at runtime and the D2 keyword-attribution fallback is the de-facto live path.
- Disclosure consistency checked surface by surface: ARCHITECTURE.md:87-90 (amended, "fallback is the de-facto live path — KB §11") ✓; deck.md:136-138 (slide 7 verbatim fix landed: "highlights ship via the keyword-attribution fallback … gold span quality is measured against the shipped path") ✓; deck.md:177-179 (slide 8: "we ship the honest fallback and say so") ✓; README:121 claims only 100% substring-validity ✓; demo script Beat 1 narrates the no-span card honestly (script_90s.md:58-61) ✓. No surface claims learned-span accuracy.
- Verdict: bar's token-F1 clause unmet-as-written, but the shipped claims are scoped to the shipped reality — the honest-fallback doctrine is intact.

## 2. Fast — PASS

- `runs/run2/day2/latency_v2_final.md` (masked-v2, machine verified unclamped first, 2026-09-09 ~22:10-23:00 IST):
  - API end-to-end on live :8177 (full gate stack incl. near-dup over 70,398-vector index): **p95 46.92 ms** (seq128 ×200) / 56.03 ms (real test rows ×200) — both <100 ms bar ✓.
  - Model-only ship path: p50 11.39 / p95 17.66 / p99 20.52 ms ✓.
  - Bulk ingest 5,050-row CSV: **45.56 reports/s** clean run (thermal-contamination protocol documented: heat-soaked 21.4/s run invalidated, clean-window re-run gated on Tctl <85°C) — ≥30/s SLA ✓.
- Fresh corroboration by this auditor (today, live :8177, stateless `/api/classify`, n=10 warm, ~30-word input): p50 19.9 / p95 ~22.2 ms, score 0.897, `RealOnnxClassifier` masked-v2 int8 — machine unclamped and ship-path latency on record holds.
- Provenance note: README/deck still quote the v1-era p95 19.7 ms / 37.3 /s in places; the v2 final numbers exist and are equal or better on the bars that matter (API p95 46.9 ms is the honest end-to-end figure).

## 3. Tested — PASS (re-run by this auditor, 2026-09-10)

All with `SIF_MODEL_PATH=artifacts/models/masked-v2`, ports 8191–8197 (8190–8199 band respected; :8177 untouched; throwaway DBs per-suite):

| Suite | Port | Result |
|---|---|---|
| `app/tests/onnx_classifier_check.py` | — (in-proc) | **PASS** — contract incl. RULE_HEAD_ORDER vs train.py, span substring validity, WC tag, T from metrics.json |
| `app/tests/explain_check.py` | 8193 | **PASS** — template correctness, silent ollama-down fallback, span-reject/retry state machine, cache round-trip, endpoint wiring |
| `app/tests/near_dup_embed_check.py` | — (in-proc) | **PASS** — verbatim 1.0000 / twin 0.997 / unrelated 0.342 vs threshold 0.91; SQLite round-trip |
| `app/tests/api_smoke.py` | 8191 | **PASS** — health → classify → ingest (idempotent replay) → views → near-dup → override round-trip → paste-persist |
| `tests/adversarial_suite.py` | 8192 | **PASS 18/18** (+ empty-text 422) — incl. #18 novel well-control precursor → WC-watch gray; #5 2000-word → `chunked_low` GRAY (D29 mitigation live) |
| `data_pipeline/pattern_mine_selfcheck.py` | 8196/8197 | **PASS** — ran via a port-shifted `/tmp` copy (`/tmp/pm_selfcheck_819x.py`; repo file untouched, ports 8187/8188 → 8196/8197) — lift/Wilson parity, patterns.json sanity, live-fallback path |
| `artifacts/demo/selfcheck_demo_pack.py` | — | **PASS** — 13 cards, 5,050-row CSV composition, Kathalguri #2→#1 re-rank arithmetic |

- Two-tier ONNX parity gate: fp32 |Δlogit| ≤ 3.5e-5 (gate ≤1e-4) ✓ (`masked-v2/export_gate.json`); int8 decision-level on the ship path (`ship_eval/parity_v2.json` `single_text_ship_path`, n=2000): ΔAUC 0.0035 ≤0.005 ✓, recall@op drop 0.0 ≤0.01 ✓, **label agreement 99.25% vs the ≥99.5% gate — formally below the D13 letter; shipped per D20 adjudication with local parity disclosed**. Note the `export_gate.json` inside the model dir is the Kaggle-side RED record (`"pass": false`); the passing local evidence lives in `ship_eval/parity_v2.json`. Both exist; the adjudication trail (D20) is what reconciles them.
- "50-row golden regression" (bar text): no artifact by that name exists; the role is filled by the regression battery in `latency_v2_final.md` §4 + `postreview_fix_check.py`, whose [2] positional scan deliberately remains RED as the honest v2 positional-valley flag (D29; mitigation verified live — see adversarial #5 above).
- Playwright e2e: `day2/e2e_01–05`, `day3/product_01–08`, `day3/redesign_01–16`, `day3/final_rehearsal_*` — zero-console-error record.

## 4. Reliable — PASS

- **Offline, physical proof:** CHECKPOINTS.md Sep 10 13:20 — `nmcli networking off` → external dead, full demo functional (classify 0.91 + LoF bar, density, dashboard), network restored. This converts the deck's air-gap line from planned to proven.
- **Offline, audit-trail proof:** `day3/final_packaging.md` §4 — loopback-only listeners (uvicorn 127.0.0.1:8177, ollama 127.0.0.1:11434), zero established outbound sockets from demo processes; same-origin vendored assets (no googleapis/gstatic/cdn; the only external-origin string in the bundle is React's static error-doc URL, never fetched); no-DNS/bogus-proxy function test passed with a control failure proving the proxy was inert.
- **Template fallback on every LLM call:** re-verified today in `explain_check` [2] (silent fallback, 0.01 s fast-failure) and [4b] (fallback TTL: fresh served, stale retried/upgraded). run.sh carries the demo without ollama by design. Fallback insurance: `artifacts/demo/fallback_recording.webm` (91 s, ffprobe-verified) + `day3/fallback_record.cjs`.
- Gray-card humility paths: all 8 gates exercised green in api_smoke + adversarial runs today.

## 5. Production-shaped — PASS

- **One-command startup:** `run.sh` (preflight → ollama w/ OLLAMA_NUM_PARALLEL=6 → uvicorn 127.0.0.1:8177 serving API + static dashboard; `--stop` pidfile discipline; `--allow-mock` gated behind a loud banner and absent from the tarball path).
- **Tarball:** `packaging/sif-demo-usb-20260910.tar.gz` — **775,426,622 bytes (740 MB), sha256 `3c5690d7…31b005d9` re-computed by this auditor, matches `final_packaging.md`**; payload contents enumerated there (masked-v2 int8 ONNX + thresholds + manifest, today's dist, app/, patterns, spec, wheels, run.sh, install/selfcheck/manifest). `packaging/selfcheck.sh`: 2 clean start→classify→stop cycles with RealOnnxClassifier on record.
- **README:** architecture diagram (mermaid) + honest-claims section + quickstart + offline/USB install path — present and internally consistent (staleness nits below).
- **Schema-validated ingestion:** exercised today (api_smoke [4] alias mapping, 422 on garbage override, adversarial 422 on empty text).
- **Versioned model artifacts:** `masked-v2/` carries ONNX + metrics.json + thresholds.json + manifest.json + label_spec.yaml copy; gold metrics record the ONNX + spec sha256-12 digests.
- **Override→label loop:** api_smoke [7] re-verified — override 201 → GET /review → latest-wins JSONL export ("future gold labels"); `gold/export_labels.py` exists for the gold-side handoff.
- **Staleness nits (non-blocking, conservative direction):** README:125 says adversarial "17/17" (now 18/18); README latency/ingest rows quote v1-era numbers (19.7 ms / 37.3 /s) instead of the v2 finals (API p95 46.9 ms / 45.56 /s); README honest-claims table has no row for the final gold metrics at all.

## 6. Validated — PARTIAL (last-mile gaps)

Systematic trace exists: `day2/final_audit_claims.md` (every ship-surface claim re-verified against a primary artifact, Sep 9). This auditor spot-verified the fixes landed: B1 (script Beat 1 narrates the no-span reality) ✓, B2 (masking = "robustness evidence, not proof of mechanism-reading", deck.md:148) ✓, C1 (unplug claim → now physically proven, moot) ✓, C2 (slide 7 span wording) ✓, C4 (HANDOFF.md:29 correction annotation) ✓, C5 ("Flag rate" in density.tsx:191 / patterns.tsx:13) ✓, C7 (33-string phrasebook) ✓. Deck slide 8 headline quadrant matches the FINAL gold artifact (P "0.98" = 0.9755, R "0.84" = 0.8357, CIs [0.788,0.874]/[0.948,0.989] exact, κ 0.51 ± 0.07 n=130) ✓.

**Gaps found (all on deck slide 8's supporting row, `docs/deck/deck.md`):**

1. **`:176` rules macro-F1 "0.52"** traces to the superseded `gold_metrics_all4.md` variant (0.5228). The locked final artifact (`gold_metrics_final.json`/:md) says **0.683** (line_of_fire, the only ≥50-positive rule). Understated, not overstated — but inconsistent with the deck's own headline source.
2. **`:165` "n=243 flagged"** matches no variant (all4 = 234, all4v2 = 223, final = **245**).
3. **`:173-175` judgment arithmetic "690 emitted"** traces to `sample_manifest.json` (`n_judgments_emitted: 690`) — the *emitted design*, but the actual process completed 801 judgments + the 169-item C re-label; a judge counting from `artifacts/gold/labels*/` will not land on 690.

Residual SEV3s from the Sep-9 claims audit never fully applied: C3 slogan "It reads exposure, not keywords" survives at `script_90s.md:69` (the deck side was fixed); C6(b) optional "synthetic demo data" UI chip not applied (provenance remains disclosed on deck slide 6 + ingest dialog + script §120 "synthetic facet corpus").

## 7. Environmental observation (not a bar bullet, but demo-relevant)

The live :8177 stack is **not in the pre-state** the ship record describes: `/api/health` reads **n_reports=5050** and density #1 = Kathalguri GCS 213/213 (post-money-beat), vs the documented pre-state 4,548 / Kathalguri #2 88/88 (restore was proven at ~15:00, `final_packaging.md` §3). Something re-played the ingest after the 13:20 freeze (untracked `final_rehearsal_*.png` at ~16:54 IST corroborate a post-freeze pass). **Before demo: restore pre-state** — `./run.sh --stop`, `rm -f app/runtime.db-shm/-wal`, `cp artifacts/demo/demo_pre.db app/runtime.db`, `./run.sh` (the documented, already-proven procedure). Also note `app/runtime.db-shm/-wal` are dirty in git status — expected from a live DB, not a code change.

## Files this audit relied on (primary evidence)

`artifacts/gold/gold_metrics_final.json` + `.md` · `artifacts/gold/agreement_final.json` · `artifacts/baselines/{mcnemar_results.json, classical_report.md}` · `runs/run2/day2/ship_eval/{mcnemar_6model.json, parity_v2.json, parity_at_op.json}` · `artifacts/models/masked-v2/{metrics.json, export_gate.json, manifest.json, thresholds.json}` · `runs/run2/day2/latency_v2_final.md` (+`.json`/`.py`) · `runs/run2/day2/final_audit_{metrics,claims}.md` · `runs/run2/day3/final_packaging.md` · `runs/run2/CHECKPOINTS.md` · `runs/run2/kb/KNOWLEDGE_BASE.md` · `run.sh` · `packaging/` (tarball sha re-computed) · `README.md` · `docs/deck/deck.md` · `artifacts/demo/script_90s.md` · `/tmp/acceptance_suites.log` (this auditor's suite re-runs).

**Bottom line:** the acceptance bar is substantively met. Nothing found today blocks ship. Fix-forward list (none blocking): deck slide 8 supporting-row numbers (macro-F1 0.683, n=245, judgment arithmetic), README staleness nits, restore demo pre-state before the room.
