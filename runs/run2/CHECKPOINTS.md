# CHECKPOINTS — build timeline (all times IST; deadline Sep 10 15:00)

| Time | Checkpoint |
|---|---|
| Sep 8 05:37 | Day-1 start (T-57h). Planning phase complete, committed. |
| Sep 8 05:45 | label_spec.yaml FROZEN v1.0.0 (spec_sha256 db946283… = sha256 of the file with the self-referential `spec_sha256:` line excluded — convention documented + re-verified 2026-09-09; raw file-bytes hash 96114b09… is the per-file hash in kernel manifests). Cron sentinels set: T-31h/T-19h/T-6h/T-2h. |
| Sep 8 05:45 | CPU clamp RESOLVED (verified: qwen3:4b 22.7 tok/s, all-core 3.25/4.7GHz). Report: /CPU_CLAMP_REPORT.md. |
| Sep 8 07:45 | Wave-1+2 done: corpus 86k rows; synthetic 8,811; export-gate GREEN (2xT4, parity 1e-5); API+dashboard shells. |
| Sep 8 08:14 | Synthetic complete 9,036 rows. QA+merge launched. |
| Sep 8 08:25 | Training agent launched (masked+unmasked on Kaggle). |
| Sep 8 08:53 | Zero-shot baseline DONE (qwen3:8b: P0.7996/R0.9159/F1 0.8538, 0/1500 failures). OLLAMA_NUM_PARALLEL=6 discovered. |
| Sep 8 09:50 | QA v1 merge: train_final 68,062 rows; LLM-ism AUC 1.0 (disclosure, D16); quotas shortfall → top-up round. |
| Sep 8 10:28 | v2 top-up merged: train_final_v2 70,404 rows; ALL quotas met; gold set 500 rows READY for labeling. |
| Sep 8 10:02 | Masked config trained (3 epochs): val AUC 0.9961, macro-F1 0.967, span F1 0.995, recall@p0.80 = 1.0. |
| Sep 8 11:20 | Training agent TIMED OUT mid export/retrieval (2h cap). ~42,850s quota reserved by live kernels. Recovery agent launched 11:26. |
| Sep 8 11:10 | Midday wave done: MiniLM near-dup (threshold 0.91 measured, p95 3.8ms), run.sh+tarball verified, explanation layer (20/20 reword), phrasebook (33 strings — the "37" first recorded here was a miscount, corrected 2026-09-09), demo corpus 13 cards + 5,050-row bulk CSV + 90s script, WC vocab gate PASS 24/24, train_final_v3 70,565 rows. |

## Ahead
- Sep 9 08:00 (T-31h cron): training results must be local; ONNX parity on real model; baselines row complete.
- Sep 9 20:00 (T-19h cron): GOLD LABELING STARTS (human, 6-8 person-h; tool: gold/labeler_app.py ports 8001-8004).
- Sep 10 09:00 (T-6h cron): final gate — metrics, adversarial suite, packaging.
- Sep 10 13:00 (T-2h cron): rehearsal gate — feature freeze, offline rehearsal.
| Sep 8 15:15 | Integration verdicts: latency p95 19.7ms PASS; ingest 33.7/s PASS; op-point vacuous → D19 re-tune; first-aid FP → D21 retrain queued. |
| Sep 8 17:45 | D19/D27: ship threshold raw 0.821855/cal 0.712581 (P0.8001/R0.9736 single-text on full test). McNemar: ft > zeroshot significant (p=8.7e-4). |
| Sep 8 18:10 | v4 corpus (71,065 rows) → masked-v2 retrain launched (background, ~2.5h). D28 CSV scrubbed (only intentional verbatim-osha remains). |
| Sep 8 20:15 | Review swarm found 6 SEV1s (rule-logit ORDER SCRAMBLE — true cause of D22 drift; positional dead zone; sqlite concurrency corruption; explain 500s; dashboard span duplication; VITE base). masked-v2 retrain done (val AUC 0.9969). |
| Sep 8 21:30 | All SEV1s fixed + probed. SHIP DECISION: masked-v2 (first-aid FP fixed 0.996→0.153, 0/20 unseen paraphrases; op-point raw 0.7464 → P0.80003/R0.9748; AUC edge +0.013). Gold pipeline pre-scored with v2. |
| Sep 8 23:10 | Demo final state: stack on masked-v2, 5,048 reports seeded, money beats verified, screenshots, tarball rebuilt. Day-1 complete. |
| Sep 9 08:00→18:55 | T-31h cron fired late (machine asleep; coalesced delivery on wake). GATE PASS: (1) training complete — masked-v1 + unmasked-v1 + masked-v2 all retrieved; (2) parity adjudicated (D20/D27: local int8 PASS on single-text ship path); (3) baselines complete incl. McNemar. Labeling: 4/500 items — human task pending tonight. Services restored: labelers up (ports 8001-8004), fresh tunnels issued, demo stack restarting. NOTE: LAN IP changed on reboot → 172.18.172.226. cloudflared moved to ~/.local/bin (persistent). |
| Sep 9 18:55 | Wake. Machine had slept through the day. T-31h gate verified PASS. Services restored (labelers + fresh tunnels + demo). LAN IP changed to 172.18.172.226. |
| Sep 9 19:40 | Fresh-eyes validation swarm (6 auditors): PS-compliance ✓, claims ✓ (11 sentence fixes), metrics all reproduce — BUT: clamp returned post-reboot, explanation cache poisoned (63 rows), money beat unexecutable as scripted, WC-miss hazard found, override 404s on live paste. |
| Sep 9 20:50 | CPU clamp fixed AGAIN — root procedure found: platform_profile kick (low-power→performance) restores boost instantly. Added to CPU_CLAMP_REPORT.md + demo-morning checklist. Verified 24.1 tok/s. |
| Sep 9 21:05 | Audit fix wave: money beat REBUILT + verified live (pre-state DB, 500-row live ingest, 14.1s, Kathalguri 88→213 #1); override persistence + well-control watch gate added (18/18 adversarial); all deck/claim fixes applied; spec-hash convention repaired. Explanation cache purge + final regression running. |
| Sep 9 20:00→23:04 | T-19h gold gate (delivered late, coalesced). LABELING IN PROGRESS: A 52/171, B ~176 (done), C 3, D 57 — 288 judgments logged via tunnels. Dashboard wired ✓, adversarial 18/18 ✓, demo precompute re-running. Explanation-cache purge + final regression agents in flight. |
| Sep 10 01:30 | ALL 4 labeling queues complete (801 judgments). Provisional gold metrics (all-4): real pooled P 0.838 / R 0.824 / F1 0.831, κ 0.346. Labeler C flagged as outlier (2s median read time, 0.27 label rate, worst pairwise agreement) — noC sensitivity: P 0.990 / R 0.809, κ 0.491. Adjudication queue: 100 items (tooling ready on port 8010). LLM cloud panel launched (DashScope: deepseek-v4-pro, glm-5.2, qwen3.8-max, deepseek-v4-flash). |
| Sep 10 02:10 | Adjudication mode built + dry-run green (100 items, pipeline override verified). Labeler-quality + error-analysis reports written (37/38 OSHA FPs are C-solo labels). Headline decision deferred to post-adjudication: all-4 recommended (no exclusion to defend). |
| Sep 10 03:50 | LLM rater panel done (4 cloud models, 0 errors): majority-vs-human-consensus 0.7253 (OSHA 0.82). LLM adjudication panel done: 72/22/6 (SIF/non/unsure) on the 100 disputed. Supplementary metrics computed. Headline = human-consensus-only (P 0.838 / R 0.824). ALL measurement work complete. Remaining: deck final numbers, packaging rebuild, rehearsal. |
| Sep 10 09:30 | T-6h FINAL GATE. Machine healthy (23.0 tok/s, no clamp). Gold metrics computed (all variants); C re-labeling in progress (21/169). Deck + Q&A + README done. Adversarial 18/18. Remaining: tarball rebuild (redesign landed after last build), fallback recording, offline rehearsal (13:00 gate). |
