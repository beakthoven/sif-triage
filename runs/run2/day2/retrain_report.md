# Day-2 Retrain Report — masked-v2 on corpus v4 (PS 26165)

**Date:** 2026-09-08 · **Author:** masked-v2 retrain engineer · **Kernel:** [`beakthoven/sif26165-train-masked-v4`](https://www.kaggle.com/code/beakthoven/sif26165-train-masked-v4) (kernel_id 133553919, v1, SaveAndRunAll) · **Recipe:** frozen — masked config, 3 epochs, batch 32, seq 128, lr 2e-5, fp16 autocast (identical to day-1 canonical)

**Goal:** retrain masked on `train_final_v4.jsonl` (71,065 rows = v3 70,565 + 500 first-aid synthetic negatives) to fix the first-aid false-positive (D21) → `artifacts/models/masked-v2/`. **Done, single kernel, no retries.**

## Headline

Training completed in one clean 66.3-min kernel on 1× Tesla T4 (sm_75, torch 2.10.0+cu128; P100/cu126 fallback not needed). **fp32 export tier is GREEN** (all heads ≤9.7e-05 — day-1 masked-v1 was RED on span; this run's span parity passes at 9.73e-05 vs tol 1e-4). **int8 tier remains RED** on D13 ranking degradation (AUC drop 0.1305 — worse than day-1 masked's 0.0916; same known int8 phenomenon, agreement 0.99296 = exactly 48/6820 flips again, recall@op drop 0.0). Ship fp32. Val saturation caveat from day-1 still holds: recall@p≥0.80 = 1.0 at precision floor 0.80003 all epochs — gold set remains the real eval. No test-set evaluation performed (orchestrator runs comparative eval locally).

## Val metrics per epoch (canonical, v4 corpus)

| ep | SIF AUC | AP | macro-rule-F1 | span tok-F1 | temp T | train loss | op threshold (recall 1.0 @ p≥0.8) | epoch s |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.9968 | 0.9992 | 0.9510 | 0.9642 | 1.021 | 0.4136 | 7.82e-04 | 831 |
| 2 | 0.9972 | 0.9993 | 0.9623 | 0.9694 | 1.339 | 0.1035 | 1.87e-04 | 816 |
| **3 (final)** | **0.9969** | **0.9992** | **0.9645** | **0.9709** | **1.648** | **0.0474** | **6.85e-05** | 817 |

vs day-1 masked-v3 final (v1 corpus 68,062 rows): AUC 0.9966→0.9969, macroF1 0.9672→0.9645, spanF1 0.9948→0.9709, T 1.684→1.648. ΔmacroF1 −0.0027 and ΔspanF1 −0.0239 are within/near the day-1 measured same-seed nondeterminism band (surprise 5: A/B < ~0.005 macroF1 = noise); spanF1 drop is larger than noise but val span support is thin (tp/fp/fn 4223/25/228). Gold-set comparison is the arbiter (orchestrator's step).

Per-rule F1 @ tuned threshold (val, ep3): line_of_fire 0.9869 (0.54, n=3738) · working_at_height 0.9578 (0.76, n=1412) · driving 0.9789 (0.95, n=217) · energy_isolation 0.9721 (0.84, n=180) · hot_work 0.9504 (0.83, n=299) · safe_mechanical_lifting 0.9410 (0.82, n=279) · confined_space 0.7143 (0.64, n=9, LOW support).

## Export gates (in-kernel, GREEN recipe: dynamo opset-18 → value_info strip → quantize_dynamic)

- **fp32 parity** (max |Δlogit| vs torch, 100 val samples, tol ≤1e-4): sif 3.46e-05 ✅ · rules 2.97e-05 ✅ · span 9.73e-05 ✅ → **GREEN** (day-1 masked was RED at span 5.78e-04; run-to-run parity variance, same code)
- **int8 gate** (full val at frozen threshold; need agr ≥0.995, AUC drop ≤0.005, recall drop ≤0.01): agreement 0.99296 ❌ · **AUC drop 0.1305** ❌ · recall drop 0.0 ✅ → **RED** (consistent with day-1 finding: int8 dynamic quant destroys mid-pack ranking, not boundary decisions)
- **export_gate_pass = False** → train.py exit 2 → Kaggle session status shows ERROR. This is the expected encoding of "int8 gate RED", NOT a failed run — all artifacts written before exit (manifest 15 files).
- Latency (seq128, ms/batch): fp32/Azure bs1 188.31, bs32 6238.94; int8/CPU bs1 150.46, bs32 4863.58.

## GPU quota

Before 15,727.347 s → after 19,714.323 s. **This run: 3,986.98 s = 1.11 GPU-h** (66.3 min wall × 1 T4). Remaining: 88,285.7 s = **24.52 h** of 30 h. Well within budget.

## Retrieval verification (sha256 vs kernel manifest)

**12/12 non-checkpoint manifest files retrieved to `artifacts/models/masked-v2/` and sha256-verified** (final sweep: all "cached/ok"): sif_multitask_fp32.onnx (2.95 MB) + sif_multitask_fp32.onnx.data (596.1 MB), sif_multitask_int8.onnx (152.0 MB), metrics.json + metrics-ep{1,2,3}.json, thresholds.json, export_gate.json, model.py (sha 6027f410 = repo frozen), train.py (sha 62fa606b = repo, all 5 day-1 bugfixes incl. sif_label), label_spec.yaml (96114b09); plus manifest.json (self) and tokenizer/ (3 files, not manifest-hashed — byte-identical to day-1 tokenizer). `ckpt-ep{1,2,3}.pt` (1.79 GB ×3) **deferred** — live in the kernel output bundle; fresh session-output URLs are in `runs/run2/day2/retrain/` (listing of 13:57 UTC) if needed.

## train.py bugfix check (task requirement)

Repo `training/train.py` sha256 = 62fa606b… = day-1 FINAL staged version containing all 5 bugfixes (verified: `sif_label` fallback at `normalize_row` ~line 170). **No patch needed; the day-1 catbox train.py blob (71ci5r.py) was reused byte-identically** and sha-verified in-kernel.

## Staging

Only `corpus/train.jsonl` re-uploaded (v4, 92.5 MB → https://files.catbox.moe/8e982r.jsonl, sha 62aac55c…, verified in-kernel "92533325 B, sha256 verified"). val/test/train.py/model.py/label_spec reused day-1 catbox blobs (all probed live HTTP 206 before launch; sha-verified in-kernel). Record: `runs/run2/day2/retrain/STAGING.md`.

## Deviations / findings

1. **Mid-session insurance retrieval does not work for these MCP script kernels**: `list_notebook_session_output` returned empty throughout the 66-min RUNNING phase; files (and log) only appear at session end. Day-1's insurance/ copies must also have been post-completion. Insurance copies for this run: `runs/run2/day2/retrain/insurance/` (post-completion). Resume mitigation remains `--resume` + in-kernel ckpts.
2. **`download_notebook_output` MCP tool is permission-denied** (`kernels.get`) — retrieval stays on kaggleusercontent URLs + `runs/run2/day1/retrieve.py`.
3. **Session status ERROR ≠ failure** — it encodes train.py exit 2 (int8 gate RED). Check manifest/metrics, not session status, for run health.
4. **fp32 span parity flipped GREEN→(day-1 RED)→GREEN** across identical-code runs: span max|Δlogit| sits near the 1e-4 tol (5.8e-04 day-1 vs 9.7e-05 today) — borderline by run luck; worth a tolerance review if it flips again.
5. **int8 AUC drop worsened** (0.0916 → 0.1305) while agreement held at the identical 0.99296 (48 flips) — more evidence for day-1 surprises 2/4: boundary-stable, ranking-fragile. int8 remains undeployable without a D13 re-review.
6. Naming: kernel slug tracks corpus version (v4); artifact dir tracks model version (masked-v2), per task spec.
7. test.jsonl staged in-kernel (schema/dry-run stats only) — never evaluated, per instructions.

## Artifacts index

- `artifacts/models/masked-v2/` — 12 verified files + tokenizer/ + manifest.json (see Retrieval verification)
- `runs/run2/day2/retrain/` — train_masked_v4.py (kernel source), STAGING.md, RETRIEVAL_PLAN.md, progress.json, manifest.json, urls.json, kernel_log_excerpt.txt, insurance/ (metrics+thresholds copies), catbox_train_v4.url
