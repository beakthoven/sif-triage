# EXPORT-GATE Report — Day-1 Critical Path (PS 26165)

**Verdict: GREEN** · 2026-09-08 · build agent: training-model + export-gate
Final kernel: [`beakthoven/sif26165-export-gate-final`](https://www.kaggle.com/code/beakthoven/sif26165-export-gate-final) (kernel_id 133485703, v1, SaveAndRunAll)

The training + export + quantization + parity path is proven end-to-end BEFORE any
real training, exactly as D1/D12/D13 require. Training configs are unblocked.

## Environment (measured in-kernel)

| Item | Value |
|---|---|
| GPU | **2× Tesla T4** (sm_75), 15,360 MiB each, driver 580.159.04 — via `machineShape="NvidiaTeslaT4"` (D1) |
| torch | 2.10.0+cu128 preinstalled — **no reinstall needed** (auto-detect cell ran, P100 branch not taken) |
| transformers | 4.57.6 (pinned, D12) · onnxruntime 1.29.0 · onnxscript (for dynamo exporter) |
| Backbone | answerdotai/ModernBERT-base, 149.0 M params, `attn_implementation="sdpa"` |
| Model | `training/model.py` embedded verbatim — kernel-side sha256 `6027f410…1312e3` **byte-identical to repo file** |
| GPU quota | 583 GPU-s consumed by all 3 gate kernels (44.7 s → 627.7 s of 108,000 s) |

## Gate results (final run)

| Check | Threshold | Measured | Pass |
|---|---|---|---|
| Train path: probe loss on batch-0, 3 steps (fp16 autocast, AdamW) | decreases | 1.96608 → **1.63156** (step losses [2.025, 2.049, 1.838]) | ✅ |
| fp32 ONNX vs torch, max\|Δlogit\|, 100 samples | ≤ 1e-4 all heads | sif **1.14e-05** · rules **1.58e-06** · span **4.43e-05** | ✅ |
| int8 sigmoid-label agreement, binary head, 100 samples | ≥ 99.5% | **100%** (1.0) | ✅ |

Aux: 128-step marker-task fit final loss 0.726; eval-100 sif |logit| mean 6.14
(non-degenerate decision boundary); fp32 + int8 both ran **full-batch dynamic**
inference (dynamic axes work). Timings (s): pins 21.7 · model load 27.6 ·
3 train steps 18.0 · 125-step spread 21.8 · export 41.5 · fp32 parity 50.4 ·
quantize 15.1 · int8 parity 20.9 · **total 234.9 s**.

## Failure chain (2 RED runs, diagnosed, fixed — full honesty)

1. **v1 `sif26165-export-gate-dayone` (id 133484713) — RED.** Legacy TorchScript
   exporter (`dynamo=False`, opset 17): export + quantize succeeded but fp32 parity
   max|Δlogit| ≈ **1.05/0.84/1.14** across heads — the legacy trace mis-traces
   ModernBERT's attention in transformers 4.57.6 (inputs had zero padding, so a
   mask bug alone cannot explain Δ~1). int8 agreement 0.92 inherited the broken
   graph. **Ruling: the legacy exporter is BANNED for this stack.**
2. **v2 `sif26165-export-gate-dynamo-retry` (id 133485327) — RED.** `dynamo=True`
   export succeeded but torch auto-converted opset 18→17 via fallback converter;
   `quantize_dynamic` then crashed in strict shape inference:
   `ShapeInferenceError: Inferred shape and existing shape differ in dimension 0:
   (768) vs (1)`. fp32 parity was never reached (stage-order flaw: quantize ran
   before parity).
3. **v3 — GREEN.** Fixes: dynamo + `opset_version=18` (no version conversion);
   `w.eval()` on the export wrapper; fp32 parity measured **before** quantize;
   quantize falls back to stripping `graph.value_info` (the (768)-vs-(1)
   annotation conflict persists even at opset 18 — strip cures it:
   `quantize: "after value_info strip"`); chunked-inference fallback for static
   shapes (not needed — full_batch worked).

## Production notes for the training kernels (load-bearing)

- Export recipe: `torch.onnx.export(..., dynamo=True, opset_version=18)` →
  strip `value_info` → `quantize_dynamic(QInt8)`. Legacy exporter must not be used.
- dynamo exporter writes fp32 as **graph + external data** (`*.onnx` 2.4 MB +
  `*.onnx.data` ~594 MB) — retrieval must fetch BOTH files. int8 re-saves inline
  (single 151.3 MB file) and is the deploy artifact.
- One quantize warning is benign: `unsupported type to quantize for tensor
  'unsqueeze'` (int64 tensor skipped).
- int8 |Δlogit| is large in this synthetic overfit regime (max ~3-4; logits are
  scale ~6) yet decision agreement is 100% — the D13 int8 metrics (AUC drop ≤0.005,
  recall@p0.8 drop ≤0.01) must still be re-measured on the REAL trained model at
  the pre-ship gate; this gate proves the mechanics, not the trained-model deltas.
- P100/cu126 fallback cell is in every kernel (untested live — T4s were allocated
  on all 3 runs today).

## Artifacts (under `artifacts/export-gate/`, sha256-verified vs kernel manifest)

- `final-green/gate_result.json` — full verdict JSON
- `final-green/model.py` — sha256 `6027f410…1312e3` = repo `training/model.py`
- `final-green/sif_multitask_fp32.onnx` (2.4 MB graph) sha `6c0697f9…4782949` ✅ match
- `final-green/sif_multitask_fp32.onnx.data` (596,115,456 B weights) sha
  `0d4dfbfb…a1794` — also proves ~600 MB checkpoint retrieval works (needed for
  per-epoch mirrors)
- `final-green/sif_multitask_int8.onnx` (151,345,767 B) sha `5e3807d0…96cfca0` ✅
  match — deploy artifact
- `run1-legacy-exporter-RED/`, `run2-dynamo-opset17-RED/` — gate_result.json + model.py of the two RED runs

## Step-1 deliverable (local)

- `training/model.py` — `SIFMultiTaskModel` (ModernBERT-base + sif/rule/span heads,
  dict forward) + `build_model()` factory. No dynamic control flow.
- `training/selfcheck_model.py` — runnable; local AST+compile check **passed**
  (torch absent locally); forward-shape check ran implicitly on Kaggle (all three
  kernels instantiated and trained the identical file).
