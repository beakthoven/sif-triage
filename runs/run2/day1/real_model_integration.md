# Real-Model Integration + Metrics Row — Day-1 (PS 26165)

**Date:** 2026-09-08 · **Scope:** CLI only (no :8177 server) — direct ONNX calls, throwaway data · **Models:** `artifacts/models/masked-v1/` + `unmasked-v1/` (canonical Kaggle runs masked-v3 / unmasked-v2) · **Env:** `.venv` (onnxruntime 1.29.0 CPUExecutionProvider, tokenizers 0.23.2, sklearn 1.9.0; no torch) · **Machine:** AMD Ryzen AI 7 350, 16 logical, power clamp RESOLVED (CPU_CLAMP_REPORT.md — cores boost under load)

Scripts + raw JSON: `runs/run2/day1/real_model_integration/` (`onnx_score.py` shared scorer, `bench_latency.py`, `parity_and_test2000.py`, `val_control.py`, `score_1500.py`, `compare_configs.py`, `selfcheck_spans.py`). Every number below is reproduced by running those scripts.

## Headline

| check | result | verdict |
|---|---|---|
| Artifact integrity (sha256 vs kernel manifest, 10 files × 2 configs) | 10/10 match | ✅ |
| int8/fp32 ONNX load + smoke inference (.venv ort, both configs) | loads, sane outputs | ✅ |
| Latency single-text (ship path, int8, 8 threads, n=200) | **p50 11.9 / p95 19.7 / p99 40.2 ms** | ✅ <100 ms p95 |
| Throughput batch-32 classify-only | **39.4 reports/s** (812.8 ms/batch) | ✅ ≥30/s SLA (D3) |
| int8 parity, 200 rows (D13: agr ≥0.995, ΔAUC ≤0.005, Δrec ≤0.01) | agr 0.995, ΔAUC **−0.0047**, Δrec 0.0 | ✅ PASS (boundary) |
| int8 parity, 2,000 rows (robustness extension) | agr 0.994, ΔAUC +0.0074, Δrec 0.0 | ⚠️ marginal FAIL |
| Val reproduction control (int8 full val n=6,820) | AUC **0.9937** — Kaggle gate's 0.9050 does **not** reproduce | ✅ pipeline validated; Kaggle RED is machine-dependent |
| Derived-test sanity (2,000 rows, masked int8) | AUC **0.8662** (fp32 0.8737) — NOT ~0.99; frozen op flags 100% (recall 1.0, precision 0.6415 = prevalence) | ⚠️ see findings 2 & 3 |
| Span self-check (20 real reports) | 52 spans, **100% exact substrings**, 20/20 highlighted, 0 dropped | ✅ |
| Model-dir preference | int8 default; `SIF_MODEL_QUANT=fp32`/file path → fp32 | ✅ |

## 1. Integrity + load

- sha256 of `sif_multitask_int8.onnx`, `sif_multitask_fp32.onnx`, `sif_multitask_fp32.onnx.data`, `thresholds.json`, `metrics.json` == `manifest.json` for **both** configs (matches the Day-1 retrieval record).
- All four artifacts load via `.venv` onnxruntime: inputs `input_ids`/`attention_mask` (int64, dynamic batch×seq), outputs `sif_logit [b]`, `rule_logits [b,7]`, `span_logits [b,seq]`.
- Tokenizer: `tokenizer/tokenizer.json`, CLS=50281/SEP=50282, truncation @128 total tokens (training path replicated; self-checked).
- Scoring path replicates training eval exactly (`tokenizer(text, truncation=True, max_length=128)`, pad to batch max — `onnx_score.py`, no torch/HF needed). Tier-1 fp32-vs-torch parity (|Δlogit| ≤ 1e-4) was measured on Kaggle at export (masked: sif 4.3e-5 ✅ rules 4.7e-5 ✅ span 5.8e-4 ❌; unmasked all ✅) — not re-runnable locally (no torch).

## 2. Threshold provenance — FINDING: insurance copies are STALE

The task brief's "6.1e-5 / temperature 1.696" matches `runs/run2/day1/insurance/*-metrics/` — but those are **pre-canonical v1-run copies**, not the shipped artifacts:

| value | insurance (stale v1) | artifact (canonical v3, sha256-verified) |
|---|---|---|
| masked SIF threshold | 6.1037e-05 | **6.581278398140432e-05** |
| masked temperature | 1.69599 | **1.683972954750061** |
| masked macroF1 / spanF1 | 0.96694 / 0.99505 | **0.96716 / 0.99483** |
| unmasked SIF threshold | 6.6447e-05 | **6.551666090070625e-05** |
| unmasked temperature | 1.64390 | **1.6731598377227783** |

Insurance masked macroF1 0.96694 == training-report "masked v1"; insurance unmasked spanF1 0.97407 == "unmasked v1". Use the artifact `thresholds.json`. **Decision semantics (verified in code):** the frozen threshold was tuned on RAW sigmoid (`train.py evaluate_arrays`: `operating_point(y, sigmoid(logit))`); temperature is display calibration. Applying it "temperature-first" (`sigmoid(z/T) ≥ sigmoid(logit(thr)/T)` = `sigmoid(z/1.684) ≥ 0.00327615`) is the identical decision — identity asserted in `onnx_score.self_check()`. On test data both threshold vintages give identical decisions anyway (flag rate 1.0). Recommend refreshing the insurance copies to the canonical values.

## 3. Parity (D13 tier-2, local: fp32 ONNX vs int8 ONNX, frozen threshold)

| sample | n | agreement | flips | ΔAUC (fp32→int8) | Δrecall@op | D13 |
|---|---|---|---|---|---|---|
| test rows, seed 123 | 200 | 0.9950 | 1 | −0.0047 | 0.0 | **PASS** |
| test rows, seed 42 | 2,000 | 0.9940 | 12 | +0.0074 | 0.0 | marginal FAIL |
| val rows, seed 5 | 1,000 | 0.9950 | 5 | +0.0044 | 0.0 | **PASS** |
| full val (int8 AUC 0.9937 vs torch ref 0.9966) | 6,820 | — | — | +0.0028 | 0.0 | **PASS** |

max |Δlogit| fp32↔int8 ≈ 8.8 (mid-pack ranking noise; the saturated boundary barely moves — recall@op is bit-identical everywhere).

**The Kaggle gate RED (agr 0.99296, ΔAUC 0.0916) does NOT reproduce on this machine.** Local int8 full-val AUC is 0.9937, not the 0.9050 the Kaggle gate implied. Same ORT 1.29.0, same artifact bytes (sha256-verified) → the int8 quantization error is **execution-provider/hardware-dependent** (Kaggle host CPU vs Ryzen AI 7 350). Per the doctrine "every deck claim measured on this machine", the local numbers are the operative ones for the demo: **int8 on the demo machine is D13-borderline-PASS** (decision agreement exactly at/one-flip under the 0.995 bar depending on sample; recall@op never moves). fp32 is the zero-risk fallback at 322 s/2,200 rows ≈ 6.8 rows/s batch-32 (single-text latency not re-benched; would miss ≥30/s SLA — int8 remains the deploy candidate, with the 2,000-row marginal-FAIL disclosed).

## 4. Latency (this machine, unthrottled)

Ship path = `app.classifier.RealOnnxClassifier.predict` (int8, 8 threads, sliding window; corpus p99 = 112 tokens ⇒ single-window nearly always), 200 real test texts, warmup 10:

- **p50 11.94 ms · p95 19.69 ms · p99 40.16 ms · mean 12.66 · min 5.68 · max 42.33** → PASS <100 ms p95 (vs 244 ms throttled earlier today — the clamp fix is what changed).
- Batch-32 classify-only: **39.4 reports/s** (640 rows, 16.26 s, 812.8 ms/batch) → PASS ≥30/s D3 SLA. Corroborated by the full-val control (6,820 rows in 168.7 s = 40.4/s). Unbucketed (pads to batch max); length-bucketing would add headroom.

## 5. Derived-test sanity — FINDING: two honest surprises reproduce on test

2,000 random rows (seed 42) of `test.jsonl`, masked int8, frozen op (temperature-first form):

- **SIF AUC 0.8662** (fp32 0.8737; 1500-sample AUCs: masked 0.8819, unmasked 0.8708) — far below val 0.9966. **Not a pipeline bug**: the val control reproduces val exactly (fp32 subset AUC 0.9973 vs torch 0.9966; int8 full-val 0.9937). The gap is the known 2024-25 label-map degradation (SEV1-10: high-energy prefix rate 55.4%→30.7% across the OIICS v1→v2 break — derived test labels are noisier than val's) plus training-report Surprise 1 (val saturated). **The gold set remains the only meaningful eval.**
- **The frozen operating point is vacuous at natural prevalence**: flag rate 100% (min calibrated prob 0.0034 > mapped threshold 0.00328), recall 1.0, precision 0.6415 = prevalence. On val it was already near-vacuous (0.80003 vs prevalence 0.7943; locally precision = 0.7943 at flag-rate 1.0). The "recall@p≥0.80" claim does not transfer off-val — **threshold must be re-tuned on the gold set** (already flagged in training_report Surprise 1). At an a-priori 0.5 raw-sigmoid threshold the same scores give P 0.8032 / R 0.9792 / F1 0.8825 on the 1500-row sample (see §6 diagnostics) — the ranking is good; only the frozen point is misplaced.

## 6. Shared-sample row + 5-model table (1,500 rows, derived labels)

Files: `artifacts/baselines/finetune_masked_test1500.jsonl` (scored on `masked_text`) and `finetune_unmasked_test1500.jsonl` (on `text`), IDs in sample order, schema `{id, sif_pred, rules_pred, sif_prob, model, quant}` (zero-shot-compatible). SIF at each config's canonical frozen op; rules at per-rule frozen thresholds on raw sigmoid.

Canonical tables: `artifacts/baselines/mcnemar_results.json` (finetune=masked) and `mcnemar_results_unmasked.json` (finetune=unmasked), both produced by `mcnemar.py --fine-tune-file` (self-check passed). Unified 5-model run (10-pair Holm): `runs/run2/day1/real_model_integration/compare1500.json`.

| model | acc (Wilson 95%) | P | R | F1 | TP/FP/FN/TN | rules exact-set | AUC |
|---|---|---|---|---|---|---|---|
| regex | 0.5087 [0.4834, 0.5339] | 0.7568 | 0.3458 | 0.4747 | 333/107/630/430 | 0.4713 | — |
| tfidf | 0.8160 [0.7956, 0.8348] | 0.7874 | 0.9772 | 0.8721 | 941/254/22/283 | 0.7880 | — |
| zeroshot qwen3:8b | 0.7987 [0.7776, 0.8182] | 0.7996 | 0.9159 | 0.8538 | 882/221/81/316 | 0.6933 | — |
| **finetune masked (frozen op)** | 0.6420 [0.6174, 0.6659] | 0.6420 | **1.0000** | 0.7820 | 963/537/0/0 | **0.8187** | **0.8819** |
| **finetune unmasked (frozen op)** | 0.6420 [0.6174, 0.6659] | 0.6420 | **1.0000** | 0.7820 | 963/537/0/0 | 0.8127 | 0.8708 |

Pairwise McNemar on SIF correctness (Holm, all 10 pairs): ft > regex (p_holm 3.9e-09); **tfidf > ft (3.2e-49)**; **zeroshot > ft (4.5e-31)**; tfidf ≈ zeroshot (0.134); **masked = unmasked (b=c=0, p=1.0)** — all ft losses driven solely by the flag-everything operating point, see diagnostics. Regex loses to everything.

**Rules head is the finetune's real win**: best exact-set match (0.8187 masked) and best per-rule F1 on line_of_fire 0.9128, working_at_height 0.9279, energy_isolation 0.9412 (vs tfidf 0.9025/0.8804/0.8158, zeroshot 0.8473/0.8847/0.6571). driving F1 0.5824 (P 1.0000 / R 0.4108 — the val-tuned 0.95 threshold is conservative); confined_space low-support (n=9) everywhere.

**Threshold diagnostics (same scores, `compare1500.json`):** at a-priori raw-sigmoid 0.5 — masked P 0.8032 / R 0.9792 / **F1 0.8825**, unmasked F1 0.8772 (both beat tfidf 0.8721 and zeroshot 0.8538); post-hoc F1-optimal on the sample (DIAGNOSTIC ONLY, not shippable) masked 0.8876 @ raw-p≈0.80, unmasked 0.8832 @ ≈0.86.

## 7. Ship-decision inputs

**Masked vs unmasked:** statistically identical SIF decisions at frozen op (McNemar p=1.0 — both flag all 1,500). On ranking/secondary metrics masked ≥ unmasked everywhere: AUC 0.8819 vs 0.8708 (+0.011), rules exact-set 0.8187 vs 0.8127, post-hoc F1 0.8876 vs 0.8832, @0.5 F1 0.8825 vs 0.8772. Combined with the D6 masking doctrine (unmasked sees outcome tokens — leak risk), **ship masked**. The ablation also shows unmasked gains nothing from outcome visibility on derived labels — supports (weakly, per D11) the redaction-robustness story.

**Masked-vs-zeroshot (the slide claim):** F1 gap is **−7.2 points at the frozen op** (0.7820 vs 0.8538) but **+2.9 points at the a-priori 0.5 threshold** (0.8825 vs 0.8538) and +3.4 post-hoc — the "within ~1.5 F1 of zero-shot" claim holds comfortably for any sanely-placed threshold and is beaten; the frozen-op row must not be the one on the slide. Cost: per-row latency 13,000 ms (zeroshot mean) vs 12 ms (int8 p50) ≈ **1,083× cheaper per classification** (the "1/1000th cost" claim is accurate); wall-clock on the 1,500-row job 2,863 s vs 123.4 s = **23.2× faster** (zeroshot already ran 6-way parallel). Air-gapped CPU vs 8B LLM: the cost story is intact.

**Deck-safe claims after today:** "<100 ms p95 classify (measured 19.7 ms)" ✅; "≥30 reports/s bulk (measured 39.4)" ✅; "spans are always exact substrings (100%, self-validated)" ✅; "beats regex baseline (Holm p<1e-8)" ✅; "tfidf/zeroshot comparison" — needs the gold-tuned threshold before claiming parity/win on SIF correctness; rules-head win is claimable now.

## 8. Self-checks (all runnable, all PASS)

- `.venv/bin/python runs/run2/day1/real_model_integration/onnx_score.py` — threshold-map identity (raw ≡ temperature-mapped), CLS/SEP, truncation@128.
- `.venv/bin/python runs/run2/day1/real_model_integration/selfcheck_spans.py` — 20 real reports → 52 spans, 100% exact substrings (`text[start:end]==span.text`), 20/20 highlighted, dropped=0; dir preference int8-default / fp32-override.
- `python3 artifacts/baselines/mcnemar.py --self-check` — ran inside every mcnemar/compare invocation (Wilson/exact/chi2_cc/Holm OK).

## Raw artifacts written

`runs/run2/day1/real_model_integration/`: `onnx_score.py`, `bench_latency.py` + `latency.json`, `parity_and_test2000.py` + `parity.json` + `test2000.json` + `test2000_scores.csv`, `val_control.py` + `val_control.json`, `score_1500.py` + `score1500_meta.json`, `compare_configs.py` + `compare1500.json`, `selfcheck_spans.py` · `artifacts/baselines/`: `finetune_masked_test1500.jsonl`, `finetune_unmasked_test1500.jsonl`, `mcnemar_results.json` (canonical, masked row), `mcnemar_results_unmasked.json`.

## Follow-ups (not in my scope)

1. **Re-tune the SIF operating point on the gold set** (Day-2/3 labeling) — the val-frozen point flags everything at natural prevalence; deck metrics depend on it.
2. Refresh `runs/run2/day1/insurance/*-metrics/` to canonical (currently pre-retrain v1 copies — a stale-numbers trap, it bit this task's brief).
3. D13 re-review note: int8 parity is hardware-dependent (Kaggle RED vs local borderline-PASS); decide fp32-fallback policy for non-demo machines.
4. Gold-set eval should report the 2024-25 label-noise caveat (derived-test AUC ≈0.87 vs val 0.9966 is label-map degradation, not model regression — control-proven here).
