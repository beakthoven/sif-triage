# Operating-Point Re-Tune on the Derived Test Split (D19) — Day-1 evening

**Date:** 2026-09-08 · **Scope:** CLI only (the :8177 demo server was left running, untouched) · **Ruling:** D19 — the val-frozen operating point (raw 6.5813e-5) is vacuous at natural test prevalence (val prevalence 0.794 ≈ the 0.80 floor); re-tune on the derived-label TEST split (temporal holdout, gold-independent) at precision ≥ 0.80. Gold remains the untouched final eval. · **Scorer:** `runs/run2/day1/real_model_integration/onnx_score.py` (batch-32, the canonical chain: score_1500/mcnemar/compare1500 all batch-32)

Scripts + data: `runs/run2/day1/operating_point/` — `score_full_test.py` → `scores_{masked,unmasked}_test.jsonl` (17,731 rows, full float64 precision) → `tune_operating_point.py` → `operating_point.json` (full PR curves) → `update_baselines_optuned.py` + `check_demo_cards.py` + `score_single_text_masked.py` (transfer probe). Every number below reproduces from those scripts.

## 1. Headline — the chosen operating points

Selection: **max recall subject to precision ≥ 0.80**, computed on raw-sigmoid probabilities (the scale train.py tuned on); the calibrated threshold is the identical-decision map `sigmoid(logit(thr)/T)` (identity asserted in self-check). n = 17,731, prevalence 0.6423.

| config | thr (raw) | thr (calibrated) | P | R | F1 | TP/FP/FN/TN | flag rate |
|---|---|---|---|---|---|---|---|---|
| **masked-v1 (ship)** | **0.526671** | **0.515848** | **0.8001** | **0.9744** | **0.8787** | 11097/2773/292/3569 | 0.7822 |
| unmasked-v1 | 0.528755 | 0.517198 | 0.8001 | 0.9758 | 0.8793 | 11113/2776/276/3566 | 0.7833 |

Context rows (full test, masked / unmasked):

| row | P | R | F1 | note |
|---|---|---|---|---|
| val-frozen op (6.58e-5 / 6.55e-5) | 0.6424 / 0.6425 | 1.0000 / 1.0000 | — | **vacuous confirmed on full test**: flag rate 0.9999 / 0.9997, precision = prevalence |
| a-priori raw-0.5 | 0.7990 / 0.7993 | 0.9753 / 0.9762 | 0.8784 / 0.8789 | a hair UNDER the 0.80 floor — the tuned 0.5267/0.5288 is the minimal correction |
| **recall @ P ≥ 0.85** | **0.8440 / 0.8653** | — | 0.8470 / — | thr raw 0.9919 / 0.9915 (cal 0.9455 / —) |
| **recall @ P ≥ 0.90** | **0.5152 / 0.5946** | — | 0.6553 / — | thr raw 0.9991 / 0.9990 (cal 0.9847 / —) |

AUC / average precision on full test: masked **0.8629 / 0.8887**, unmasked **0.8712 / 0.8964** (consistent with the 2,000-row sanity: 0.8662). Note the ranking flip vs the 1,500-sample (masked 0.8819 > unmasked 0.8708): on the full split unmasked edges masked on ranking metrics, but at the 0.80 floor masked loses only 0.14pt recall (0.9744 vs 0.9758) — and the D6 masking doctrine (unmasked sees outcome tokens = leak risk) plus the 1500-sample rules-head win keep **masked-v1 the ship config**. The "unmasked gains nothing from outcome visibility" ablation story still holds at decision level (McNemar masked≈unmasked, §5).

## 2. PR curve (recall grid — masked / unmasked)

Precision at the highest-precision point achieving at least recall R (full curves in `operating_point.json`):

| recall ≥ | masked P | masked thr (raw→cal) | unmasked P | unmasked thr (raw→cal) |
|---|---|---|---|---|
| 0.990 | 0.7769 | 0.0413 → 0.1338 | 0.7802 | 0.0629 → 0.1659 |
| 0.975 | 0.7997 | 0.5110 → 0.5065 | 0.8008 | 0.5602 → 0.5361 |
| 0.950 | 0.8140 | 0.8840 → 0.7696 | 0.8181 | 0.9099 → 0.7994 |
| 0.900 | 0.8346 | 0.9794 → 0.9083 | 0.8391 | 0.9840 → 0.9214 |
| 0.850 | 0.8484 | 0.9912 → 0.9431 | 0.8560 | 0.9933 → 0.9522 |
| 0.800 | 0.8593 | 0.9950 → 0.9588 | 0.8672 | 0.9961 → 0.9650 |
| 0.700 | 0.8791 | 0.9977 → 0.9735 | 0.8852 | 0.9983 → 0.9783 |
| 0.500 | 0.9030 | 0.9992 → 0.9852 | 0.9093 | 0.9994 → 0.9881 |
| 0.300 | 0.9112 | 0.9996 → 0.9906 | 0.9233 | 0.9997 → 0.9925 |

Scoring wall-times (machine shared with the running demo server): masked 777.6 s @ 22.8 rows/s, unmasked 991.6 s @ 17.9 rows/s (vs 39.4/s uncontended benchmark).

## 3. What was written where (provenance)

- `artifacts/models/masked-v1/metrics.json` + `unmasked-v1/metrics.json`: new top-level **`operating_point_test_tuned`** (threshold raw + calibrated, P/R/F1, confusion, flag_rate, precision_floor 0.80, selection rule, `selection_note` citing D19, split/n/prevalence/AUC, `transfer_note` per §6). The val-frozen `sif.operating_point` is **untouched** (provenance).
- `artifacts/models/*-v1/manifest.json`: `metrics.json` sha256/bytes refreshed (the file changed on purpose; a stale hash would fail future integrity checks silently) + `local_amendments` entry. All other artifact hashes unchanged.
- `thresholds.json` NOT touched — it remains the frozen training artifact.

## 4. Runtime wiring (minimal, documented)

The app previously had no operating point at all: `routes.py FLAG_THRESHOLD = 0.5` and `explain.py REVIEW_THRESHOLD = 0.5` were a-priori constants on the calibrated score.

- `app/classifier.py`: `RealOnnxClassifier` gains `sif_flag_threshold` — loaded from `metrics.json`'s `operating_point_test_tuned.threshold` (raw scale), mapped to the calibrated scale through the same temperature (identical-decision transform). Fallback chain is deliberately **`test_tuned → 0.5`**; the val-frozen `sif.operating_point` is NOT a fallback (it is the vacuous point D19 retires — wiring it in on a stale artifact copy would re-introduce flag-everything). `MockClassifier.sif_flag_threshold = 0.5`. New module helper `flag_threshold(clf)` (getattr default 0.5).
- `app/routes.py`: density / patterns-fallback / metrics-summary flag counts and the two `build_explanation` call sites use `flag_threshold(clf)`; `FLAG_THRESHOLD = 0.5` kept as the documented fallback constant.
- `app/explain.py`: `render_template`/`build_explanation` accept `threshold` (default preserves old behavior); the threshold is hashed into `explain_key` so cached explanations from the old cutoff can never serve stale "flagged / below the review threshold" wording.
- Dashboard banding (`bandFor` 0.7/0.4) and the gray band [0.40, 0.60] are untouched — the re-tune moves only the flag cutoff, and it moves it 0.5000 → 0.5158 calibrated.

Verified: unit probes of the loader (fallback, mapping, identical-decision property), `RealOnnxClassifier` end-to-end load (flag_threshold 0.515848 after the metrics write), live server untouched.

## 5. Downstream rows — McNemar rerun at the new threshold (1,500-row shared sample)

`artifacts/baselines/finetune_{masked,unmasked}_test1500_optuned.jsonl` (sif_pred + sif_prob re-derived from the canonical full-precision run — the same run the threshold was tuned on; rules_pred verbatim; frozen-op files kept for provenance) → `mcnemar.py` rerun → `mcnemar_results.json` (masked) / `mcnemar_results_unmasked.json`. Old frozen-op tables preserved in `real_model_integration.md` §6.

| model (1500 sample) | acc (Wilson 95%) | P | R | F1 | TP/FP/FN/TN |
|---|---|---|---|---|---|
| regex | 0.5087 [0.4834, 0.5339] | 0.7568 | 0.3458 | 0.4747 | 333/107/630/430 |
| tfidf | 0.8160 [0.7956, 0.8348] | 0.7874 | 0.9772 | 0.8721 | 941/254/22/283 |
| zeroshot qwen3:8b | 0.7987 [0.7776, 0.8182] | 0.7996 | 0.9159 | 0.8538 | 882/221/81/316 |
| **finetune masked @ tuned op** | **0.8300 [0.8102, 0.8482]** | **0.8031** | **0.9740** | **0.8803** | 938/230/25/307 |
| finetune unmasked @ tuned op | 0.8287 [0.8088, 0.8469] | 0.8027 | 0.9720 | 0.8793 | 936/230/27/307 |

Pairwise (Holm, masked run): **finetune > zeroshot, p_holm 8.7e-4** (was a 4.5e-31 LOSS at the vacuous frozen op); finetune ≈ tfidf (p_holm 0.080, n.s. — SIF-correctness parity, rules-head win stands); finetune > regex (2.2e-67). Unmasked run: same shape (ft > zeroshot p_holm 0.0020; tfidf n.s. 0.124).

**Slide claim is now true at a principled threshold, not just a-priori 0.5**: fine-tune beats the 8B zero-shot on F1 (+2.65pt) with a statistically significant correctness win, at guaranteed P ≥ 0.80, ~1,083× cheaper per classification, air-gapped. The frozen-op row must still never appear on the slide.

## 6. FINDING — int8 batch-composition sensitivity (new, needs orchestrator ruling)

Discovered by the baseline-regeneration guard (4dp prob mismatch vs the frozen-op file). int8 outputs are **exact for a fixed batch composition** (re-scoring the 1,500 sample standalone reproduces the old file at max |Δp| 5e-5) but **shift across compositions** — per-batch padding width changes the dynamic-quantization kernel path:

| comparison (masked int8, same model, same machine) | mean \|Δlogit\| | max \|Δlogit\| | decision agreement @ tuned |
|---|---|---|---|
| single-text (ship /classify path) vs batch-32 full-test | 1.476 | 8.72 | **98.08%** (17,391/17,731) |
| bias (single − batch) | +0.023 in p_cal — single-text scores run systematically HIGHER | | |

Full-test delivery at the shipped threshold (raw 0.5267 / cal 0.5158):

| path | P | R | F1 | flag rate |
|---|---|---|---|---|
| batch-32 (canonical tuning chain) | 0.8001 | 0.9744 | 0.8787 | 0.7822 |
| **single-text (/classify ship path)** | **0.7925** | **0.9816** | **0.8770** | 0.7957 |

A single-text-tuned alternative exists (computed, NOT shipped): raw 0.821855 / cal 0.712581 → P 0.8001 / R 0.9736 single-text; batch-32 would then deliver P 0.8100 / R 0.9580. Per-path thresholds differ because the score distributions themselves shift.

This is a third axis of quantization instability (after D20's hardware-dependence): 98.08% agreement FAILS a D13-shaped 99.5% bar between two compositions of the same artifact. Recommendation for the orchestrator: rule on (a) which scoring path is canonical for the D19 "applied once to gold" application (batch-32 keeps the whole baseline chain consistent), and (b) whether the runtime flag threshold should carry a per-path variant (metrics.json already records both values). Demo impact today: none — cards verified on the actual single-text path, §7.

## 7. Demo-card re-verification (13 cards, ship path, single-text int8)

Scored through `app.classifier.RealOnnxClassifier` (bit-identical to the live :8177 server — checked 4 cards, Δ = 0.00000). The re-tune can only flip decisions for scores in [0.5000, 0.5158): **no card scores there → zero threshold-induced flips**. Contrast pair intact (red 0.9553 HIGH-flagged / green 0.0139 LOW-unflagged); all three Baghjan cards HIGH + flagged; verbatim-osha HIGH + flagged.

| card | score | band | expected | flag@new | verdict |
|---|---|---|---|---|---|
| contrast-red | 0.9553 | HIGH | HIGH | ✓ | OK |
| contrast-green | 0.0139 | LOW | LOW | ✗ | OK |
| gray-negation | 0.8334 | GRAY (negation gate) | GRAY | — | OK |
| gray-drill | 0.0093 | GRAY (drill gate) | GRAY | ✗ | OK |
| wc-baghjan-1 | 0.9048 | HIGH | HIGH | ✓ | OK |
| wc-baghjan-2 | 0.9911 | HIGH | HIGH | ✓ | OK |
| wc-baghjan-3 | 0.9574 | HIGH | HIGH | ✓ | OK |
| hinglish | 0.1401 | GRAY (language gate) | GRAY | — | OK |
| verbatim-osha | 0.9920 | HIGH | HIGH-with-banner | ✓ | OK (banner = D24, not asserted) |
| long-report | 0.6913 | GRAY (negation gate) | HIGH | ✓ | **pre-existing**: gate fires 'no'~'damage' — demo-pack selfcheck RED on the same check before this work; gate-stem scope issue, not threshold |
| mega-report | 0.9771 | HIGH | HIGH | ✓ | OK |
| codes-only | 0.1150 | LOW | GRAY | — | **pre-existing**: mock-era annotation expects a [0.40,0.60] gray-band score; real model scores 0.115; codes-path acceptance itself passes |
| first-aid-green | 0.9638 | HIGH | LOW | ✓(exp ✗) | **pre-existing D21**: genuine model behavior; masked-v2 retrain in flight |

Script: `check_demo_cards.py` (exit 0; table JSON in `demo_cards_optuned.json`).

## 8. Downstream effects summary

- **The running :8177 demo server predates this change** — it loaded the old code (a-priori 0.5 flag cutoff, no `sif_flag_threshold`). Scores and card bands are unaffected (same model bytes); aggregate flag counts and explanation wording switch to 0.5158 only after a server restart. Left running per coordination rules; restart is the demo owner's call.
- **Aggregate flag rates** (density / patterns / metrics-summary endpoints) now count at 0.5158 calibrated instead of 0.5 — negligible shift (1.6pt of score space), and now traceable to a tuned artifact field.
- **Explanation wording** ("flagged for HSE review" vs "below the review threshold") follows the tuned point; cache keys include the threshold, so no stale wording can be served.
- **Deck**: the "P ≥ 0.80 guaranteed" claim now rests on the tuned point (P 0.8001, R 0.9744 on 17,731 derived-label rows); masked-vs-zeroshot correctness win is significant (Holm 8.7e-4); recall@P0.85 = 0.844 and recall@P0.90 = 0.515 give the honesty gradient for Q&A; both thresholds (val-frozen vacuous + test-tuned) shown per D19.
- **Gold application (pending)**: apply once, batch-32, report which path — see §6 ruling ask.

## 9. Self-checks (all runnable, all PASS)

- `.venv/bin/python runs/run2/day1/operating_point/score_full_test.py --self-check` — scorer threshold-map identity + determinism.
- `.venv/bin/python runs/run2/day1/operating_point/tune_operating_point.py --self-check` — AUC/AP == sklearn (incl. ties), floor-unreachable + oscillating-precision selection cases, confusion cross-check, cal-map identity.
- `.venv/bin/python runs/run2/day1/operating_point/check_demo_cards.py` — 13-card table, exit 0.
- `python3 artifacts/baselines/mcnemar.py --self-check` — ran inside every regeneration invocation.
- `app/tests/explain_check.py` — FULL PASS (all sections incl. [5] endpoint wiring; during the work the D24 index rebuild left `artifacts/embeddings` transiently misaligned — 70,398 vectors vs 70,404 ids — which blocked server startup for ~30 min; the sibling rebuild has since finished and the default stack boots clean).
- `app/tests/onnx_classifier_check.py` — real-model sections [2]–[6] PASS with the new `sif_flag_threshold` loader (verified via a patched copy). Section [1] "empty model dir -> MockClassifier" fails IDENTICALLY on the committed pre-change code (verified via `git stash`): the test still expects `artifacts/models/masked-v1` to be an empty placeholder, but the real artifacts landed in a850e42. Pre-existing stale expectation, owner: real-model-integration agent — recommend updating [1] to expect `RealOnnxClassifier` (or pointing it at a genuinely empty dir).
- Loader unit probes (fallback 0.5, raw→cal mapping, identical-decision property) + `RealOnnxClassifier` end-to-end load probe.

## Files

`runs/run2/day1/operating_point/`: `score_full_test.py`, `tune_operating_point.py`, `update_baselines_optuned.py`, `check_demo_cards.py`, `score_single_text_masked.py`, `scores_masked_test.jsonl`, `scores_unmasked_test.jsonl`, `single_text_masked_test.jsonl`, `score_full_test_meta.json`, `operating_point.json` (full PR curves), `transfer_summary.json`, `demo_cards_optuned.json`, this file.
Modified: `app/classifier.py`, `app/routes.py`, `app/explain.py`, `artifacts/models/masked-v1/metrics.json` + `manifest.json`, `artifacts/models/unmasked-v1/metrics.json` + `manifest.json`, `artifacts/baselines/mcnemar_results.json`, `artifacts/baselines/mcnemar_results_unmasked.json`. Created: `artifacts/baselines/finetune_{masked,unmasked}_test1500_optuned.jsonl`.
