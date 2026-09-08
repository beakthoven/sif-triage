# CHECKPOINTS — build timeline (all times IST; deadline Sep 10 15:00)

| Time | Checkpoint |
|---|---|
| Sep 8 05:37 | Day-1 start (T-57h). Planning phase complete, committed. |
| Sep 8 05:45 | label_spec.yaml FROZEN v1.0.0 (sha256 db946283…). Cron sentinels set: T-31h/T-19h/T-6h/T-2h. |
| Sep 8 05:45 | CPU clamp RESOLVED (verified: qwen3:4b 22.7 tok/s, all-core 3.25/4.7GHz). Report: /CPU_CLAMP_REPORT.md. |
| Sep 8 07:45 | Wave-1+2 done: corpus 86k rows; synthetic 8,811; export-gate GREEN (2xT4, parity 1e-5); API+dashboard shells. |
| Sep 8 08:14 | Synthetic complete 9,036 rows. QA+merge launched. |
| Sep 8 08:25 | Training agent launched (masked+unmasked on Kaggle). |
| Sep 8 08:53 | Zero-shot baseline DONE (qwen3:8b: P0.7996/R0.9159/F1 0.8538, 0/1500 failures). OLLAMA_NUM_PARALLEL=6 discovered. |
| Sep 8 09:50 | QA v1 merge: train_final 68,062 rows; LLM-ism AUC 1.0 (disclosure, D16); quotas shortfall → top-up round. |
| Sep 8 10:28 | v2 top-up merged: train_final_v2 70,404 rows; ALL quotas met; gold set 500 rows READY for labeling. |
| Sep 8 10:02 | Masked config trained (3 epochs): val AUC 0.9961, macro-F1 0.967, span F1 0.995, recall@p0.80 = 1.0. |
| Sep 8 11:20 | Training agent TIMED OUT mid export/retrieval (2h cap). ~42,850s quota reserved by live kernels. Recovery agent launched 11:26. |
| Sep 8 11:10 | Midday wave done: MiniLM near-dup (threshold 0.91 measured, p95 3.8ms), run.sh+tarball verified, explanation layer (20/20 reword), phrasebook (37 strings), demo corpus 13 cards + 5,050-row bulk CSV + 90s script, WC vocab gate PASS 24/24, train_final_v3 70,565 rows. |

## Ahead
- Sep 9 08:00 (T-31h cron): training results must be local; ONNX parity on real model; baselines row complete.
- Sep 9 20:00 (T-19h cron): GOLD LABELING STARTS (human, 6-8 person-h; tool: gold/labeler_app.py ports 8001-8004).
- Sep 10 09:00 (T-6h cron): final gate — metrics, adversarial suite, packaging.
- Sep 10 13:00 (T-2h cron): rehearsal gate — feature freeze, offline rehearsal.
