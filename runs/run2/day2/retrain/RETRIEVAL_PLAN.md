# Day-2 retrieval plan (masked-v2)

## Source of truth
Kernel writes to `/kaggle/working` + `manifest.json` (files{name:{sha256,bytes}}).
Retrieval = `runs/run2/day1/retrieve.py <manifest> <urls.json> <outdir>` (ranged
parallel curl, sha256 verify, skip-cached). URLs come from MCP
`list_notebook_session_output` for the kernel session.

## Insurance (during run)
Poll `get_notebook_session_status` + `list_notebook_session_output` every ~5 min.
As soon as `metrics-ep{N}.json` appears, download to
`runs/run2/day2/retrain/insurance/` (per-epoch snapshots = loss of kernel ≠ loss of
val metrics). Mark `progress.json` stages.3_epoch_metrics_insurance.

## Final retrieval (after kernel completes)
Outdir: `artifacts/models/masked-v2/`
Priority order (small → large; mirrors day-1):
1. metrics.json, metrics-ep{1,2,3}.json, thresholds.json, export_gate.json,
   manifest.json, train.py, model.py, label_spec.yaml
2. tokenizer/ (3 files; not manifest-hashed — kernel-wrapper written)
3. sif_multitask_fp32.onnx (2.95 MB graph) + sif_multitask_fp32.onnx.data (~596 MB)
4. sif_multitask_int8.onnx (~152 MB, deploy candidate)
5. ckpt-ep{1,2,3}.pt (~1.79 GB each) — DEFERRED (remain in Kaggle output bundle;
   day-1 proved 1.75 MB/s ≈ 17 min each; retrieve only on orchestrator request)

## Verification
Every manifest-listed file must sha256-match before stage 5 marked done.
Report verification count in retrain_report.md.
