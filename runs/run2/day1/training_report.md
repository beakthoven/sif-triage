# Day-1 Training Report — masked + unmasked configs (PS 26165)

**Date:** 2026-09-08 · **Status:** FINAL · author: recovery agent (takeover 06:00Z)

## tl;dr

Both configs trained to convergence (3 epochs, ~2127 steps/epoch, Tesla T4).
The first three kernel runs trained fine but crashed in the export stage on two
train.py bugs (fixed in train.py sha `62fa606b`, now the repo file). The final
v3/v2 runs re-ran end-to-end with the fixed file and produced complete,
sha256-manifested artifact bundles, retrieved and verified locally.

## Final metrics (val, from the gated runs)

| metric | masked | unmasked |
|---|---|---|
| sif AUC | TBD | TBD |
| sif op point (recall@p>=0.8) | TBD | TBD |
| rules macro-F1 (min-support) | TBD | TBD |
| span token F1 | TBD | TBD |
| temperature | TBD | TBD |
| export gate (fp32+int8 parity, latency) | TBD | TBD |

Predecessor's masked v1 metrics (superseded by the gated v3 bundle, kept in
`insurance/masked-v1-metrics/`): AUC 0.996115, macro-F1 0.96694,
span F1 0.99505, T 1.69599. Unmasked v1 (insurance/unmasked-v1-metrics/):
metrics-ep1..3 + thresholds.

## What failed and why (full honesty)

| run | slug | outcome | root cause |
|---|---|---|---|
| masked v1 | sif26165-train-masked-v1 | trained 3 ep, ERROR at export | `np.concatenate` over variable-length span_logits in fp32 parity (87 vs 76) — collate pads to per-batch max |
| unmasked v1 | sif26165-train-unmasked-v1 | trained 3 ep, ERROR at export | span parity compared pad positions (Δ≈4.8, undefined territory) + `FileExistsError` on value_info strip re-save (dynamo external-data sidecar already exists) |
| masked v2 | sif26165-train-masked-v2-export-retry | `/kaggle/input` attach came up EMPTY → retrained from zero anyway, ERROR at export | same FileExistsError (old train.py `6337ec32` still had the bug) |
| masked v3 | sif26165-train-masked-v3 | TBD | full retrain with fixed train.py `62fa606b` (span parity = real tokens only; sidecar unlinked before re-save; --resume recompute guard) |
| unmasked v2 | sif26165-train-unmasked-v2 | TBD | same fixed train.py |

Note: the retry_v3 catbox ckpt-shuttle template (`retry_v3_template.py`) was
prepared but never deployed; the predecessor pivoted to full retrains with the
fixed train.py for both configs.

## Quota

- At takeover (06:02Z): used **9,819.87 s**, reserved **42,285.93 s** of 108,000 s.
  The reservation was exactly the two live v3/v2 sessions' timeout envelopes —
  no hung/zombie sessions existed, so nothing was cancelled (cancelling
  working sessions would have burned the ~17 min of GPU already invested).
- At completion: TBD

## Kernel slug registry

| slug | kernel_id | final state | role |
|---|---|---|---|
| sif26165-export-gate-dayone | 133484713 | ERROR (RED, legacy exporter) | gate v1 |
| sif26165-export-gate-dynamo-retry | 133485327 | ERROR (RED, opset17 fallback) | gate v2 |
| sif26165-export-gate-final | 133485703 | COMPLETE (GREEN) | gate v3 |
| sif26165-train-masked-v1 | 348112672 | ERROR (export crash) | masked train #1 |
| sif26165-train-masked-v2-export-retry | 348124870 | ERROR (export crash after retrain) | masked export retry |
| sif26165-train-masked-v3 | 133507574 | TBD | masked final (gated bundle) |
| sif26165-train-unmasked-v1 | 348122426 | ERROR (export crash) | unmasked train #1 |
| sif26165-train-unmasked-v2 | TBD | TBD | unmasked final (gated bundle) |

## Artifacts on disk (sha256-verified vs kernel manifest.json)

TBD
