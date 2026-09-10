# DECK NUMBERS FINAL AUDIT — ship-v1.0 (PS 26165)

- **Date:** 2026-09-10, ~17:15 IST · **Auditor:** validation swarm agent (deck numbers) · **Mode:** read-only (no files modified except this report; no git operations)
- **Scope:** every quantitative claim in `docs/deck/deck.md`, `docs/deck/qa_prep.md`, `docs/deck/demo_card.md`, `README.md`, recomputed/traced to artifacts.
- **Canonical sources:** `artifacts/gold/gold_metrics_final.json` (2026-09-10T10:53Z, real_pooled headline, n=318), `artifacts/models/masked-v2/metrics.json`, `runs/run2/day2/ship_eval/mcnemar_6model.json`, `runs/run2/day2/latency_v2_final.md` (+`.json`), `runs/run2/day2/ship_decision.md`, `runs/run2/day2/demo_final_state.md`, `runs/run2/day2/regression_log.txt`, `artifacts/gold/sample_manifest.json`, `runs/run2/day1/{training_report,data_pipeline_report,synthetic_qa_report}.md`, `runs/run2/day2/retrain_report.md`, `artifacts/baselines/zeroshot_report.md`, `runs/run2/day1/real_model_integration.md`, `artifacts/demo/script_90s.md` + `money_beat_e2e.log`.

## VERDICT: CONDITIONAL PASS — 10 hard mismatches must be fixed before the deck is shown

The gold headline itself is clean: every P/R/κ/CI figure on the money slide matches
`gold_metrics_final.json` (not the all4/all4v2 intermediates) — with two exceptions
(rules macro-F1 and the precision n). The systemic problem is elsewhere: **the deck,
README, demo card and Q&A prep all still quote the superseded masked-v1 latency/throughput
record** (19.7 ms / 37.3 /s / 39.4 /s / 17-17) even though `latency_v2_final.md` exists
precisely to replace it, and **the presenter-facing files still contain unfilled
`{{GOLD_*}}` placeholders**. None of the stale numbers are optimistic — the v2 truth is
*better* (17.7 ms, 45.6/s, 18/18) — but "quote only measured numbers" is the project's
own doctrine, and two demo_card lines contradict the rehearsed script's arithmetic.

---

## A. FAIL — wrong or stale numbers (must fix)

| # | File:line | Claim | Artifact truth | Source |
|---|---|---|---|---|
| F1 | deck.md:176 (slide 8) | Gold rules macro-F1 **"0.52"** | **0.683** — the 0.52 is the stale `gold_metrics_all4.json` intermediate (0.5228). "One rule (line_of_fire) met the ≥50 bar" is correct; the value is not. | `gold_metrics_final.json` rules.macro_f1 = 0.6828 |
| F2 | deck.md:165 (slide 8) | precision "95% CI [0.948, 0.989] (**n=243** flagged)" | CI ✓ matches final [0.9476, 0.9887]; **n is wrong: 245** (239 TP + 6 FP). 243 matches NO gold variant (all4 234, all4v2 223, noC 193, gold_metrics.json 205). | `gold_metrics_final.json` real_pooled.precision.n = 245 |
| F3 | README.md:119 · deck.md:167,189,222 · qa_prep.md:126,159 · demo_card.md:32,45,82-83 | classify **p95 19.7 ms** (README also p50 11.9 / p99 40.2) | These are the **masked-v1** numbers. Ship model (masked-v2, unclamped): model-only **p50 11.39 / p95 17.66 / p99 20.52 ms**; live API e2e p50 28.0 / p95 56.0 ms (real rows), seq128 p95 46.9 ms. `latency_v2_final.md` header: "Replaces: the on-record numbers were masked-v1 (11.9/19.7/40.2)". | `runs/run2/day2/latency_v2_final.md` headline table |
| F4 | README.md:120 · deck.md:223 · qa_prep.md:127 · demo_card.md:29,45,82 | bulk ingest **37.3 reports/s** (5,050 rows, 135.3 s) | Superseded Day-1-night figure. Final clean-window re-measure: **45.56/s** (5,048 accepted / 110.8 s, SLA ≥30/s PASS). The 37.3/s run predates the OpenBLAS threadpool fix. | `latency_v2_final.md` §3 |
| F5 | deck.md:224 · demo_card.md:45,83 | "**39.4/s** classify-only batch-32" | v1-era number AND the int8 batch-32 path is **prohibited** (D27: single-text is the only legal classify path; batch composition shifts logits). Should not be a quotable number at all. | DECISION_LOG D27; KB §10/§11 |
| F6 | README.md:125 · deck.md:229 | adversarial suite **17/17 PASS** | Suite is now **18** cases (case #18 novel well-control precursor → WC-watch gray, added in the audit wave); final runs 22:07 + 23:10 both **18/18 PASS**. | `regression_log.txt:262`; `tests/adversarial_suite.py` CASES len = 18 |
| F7 | demo_card.md:4,14 | pre-stage: health shows "**n_reports: 5048**" / "5,048 reports seeded" | Scripted **pre-state is 4,548** (script_90s.md:32: "`n_reports: 4548` … Kathalguri GCS #2"). 5,048 is the POST-state after the live 500-row ingest. As written, the checklist misdiagnoses a correct pre-state as broken — or waves through a post-state where the money beat is already spent. Verified live at audit time: health = 4,548 ✓. | `artifacts/demo/script_90s.md:19-32`; live `/api/health` 17:14 IST |
| F8 | demo_card.md:30 | money beat "was **#2 with 31**" | Verified live twice: pre-state Kathalguri GCS = **#2 with 88 reports** (88/88 flagged). Script says "number two, eighty-eight reports". 31 is the stale cell pre-seed count from the superseded one-phase seed. | `money_beat_e2e.log` BEFORE table; live `/api/density` 17:14 IST (Moran 98 #1, Kathalguri 88 #2) |
| F9 | demo_card.md:29 | bulk beat: say "**Five thousand** register rows ingested", point at "**5,048 accepted**, 37.3/s" | The scripted live beat uploads the **500-row** file — UI prints "accepted **500/500**", wall ~12-15 s; script's say-line is "Five **hundred** register rows". 5,048 is the post-state DB total, not the ingest count. Presenter would quote a number the screen contradicts. | `script_90s.md` beat 5; `money_beat_e2e.log` ("received":500,"accepted":500, wall 12.1s) |
| F10 | qa_prep.md:42,78,114,163 · demo_card.md:32 | unfilled placeholders: `{{GOLD_RECALL}}`, `{{GOLD_RECALL_CI}}`, `{{GOLD_KAPPA}}`, `{{GOLD_MCNEMAR_TFIDF_P}}` | Fillable now: **R 0.836 [0.788, 0.874]**, **κ 0.513 ± 0.07** (n=130). EXCEPTION: gold-vs-baselines McNemar never landed (no artifact exists; `gold_metrics_pipeline.md:99` scopes it out) — Q7 must use its written fallback ("rest on the derived-sample table + capability list"), not a number. The demo CLOSE beat (demo_card.md:32) literally contains "{{GOLD_RECALL}}". | `gold_metrics_final.json`; grep of artifacts/gold + runs/run2/day3 |

## B. WARN — disclosure gaps / untraceable / needs recheck

| # | File:line | Issue |
|---|---|---|
| W1 | qa_prep.md:59 (Q5) | "confined-space real support is **~0.2–0.7%**" — untraceable. KB §3 says CS is proxy-dependent **0.29–2.5%**; v2 val support is 9/6,820 = 0.13%; gold real-pooled 7/318 = 2.2%. No artifact yields 0.2–0.7%. |
| W2 | deck.md (all), qa_prep.md, README.md | **ASRS stratum recall 0.00 (19/19 missed)** is disclosed nowhere in the four files. KB §12 (gold results): "Deck must disclose." Related omission: headline is computed on 407 consensus items with **93 still adjudication-pending** (SEV3 flag in the metrics file); the deck's "all 500 items labeled" is true (0 unlabeled) but the pending-adjudication caveat is absent. |
| W3 | deck.md:273-275 · demo_card.md:30 | Cell "**96/96**, min score 0.760 vs 0.658 threshold" traces to demo_final_state.md §1 (Sep-8 one-phase seed: 65 CSV + 31 pre-seed, min 0.7601 ✓). The Sep-9 two-phase redesign note (script_90s.md sensitivity) says "DG-duct cell **empty** pre-ingest", conflicting with the 31 pre-seed figure. Site-level numbers (88→**213/213**, Moran 105) are re-verified live (Sep-9 e2e + my check today); the cell-level 96 was **not** re-verified under the two-phase design. Threshold 0.658108 ✓, min 0.7601 ✓ for the record as written. |
| W4 | deck.md:90 · README.md:28 | mermaid "p95 ≈ 20 ms" — defensible either way (v1 19.7; v2 model-only 17.7; v2 seq128 24.6) but if F3 is fixed, say "≈18 ms" or annotate model-only vs e2e. |

## C. Verified clean — claim → evidence (representative, all exact)

**Gold (slide 8 / README):** recall 0.84 [0.788, 0.874] n=286 ✓; precision 0.98 ✓ (n wrong, F2); κ 0.51 ± 0.07, n=130 ✓ (0.5129, bootstrap SE 0.0655); composition 500 = 300 OSHA (150 oil-gas) + 100 ASRS + 100 synthetic ✓ (`sample_manifest.json` counts); 690 = 500 primary + 150 double + 20 pilot × 2 ✓ (`n_judgments_emitted: 690`, `pilot_ids` len 20, double 90+30+30); "real-only headline, synthetic never pooled" ✓ (headline_stratum: real_pooled).

**Operating point / derived test:** P 0.8000 · R 0.9748 · F1 0.8788 · n=17,731 · prevalence 0.6423 · flag rate 78.3% · R@P≥0.85 = 0.8619 · R@P≥0.90 = 0.5318 · raw 0.746401 / cal 0.658108 · T = 1.6484 — all exact vs `masked-v2/metrics.json operating_point_test_tuned` + `ship_decision.md` §1. Val AUC 0.9969 · rules macro-F1 0.9645 · span tok-F1 0.9709 ("agreement 0.97") · test AUC 0.8680 · AP 0.8931 ✓. Masking ablation ΔAUC ≈0.00 val / +0.011 test ✓ (KB §10; DECISION_LOG masked 0.8819 vs unmasked 0.8708).

**Baselines (slide 9) — every cell recomputed from `mcnemar_6model.json` (n=1,500, Holm):** regex 0.509/0.757/0.346/0.475 ✓ (p_holm vs ft-v2 = 6.4e-68, "≈1e-68" ✓); tfidf 0.816/0.787/0.977/0.872, p=0.122 ✓ (0.1224); zeroshot 0.799/0.800/0.916/0.854, p=0.0018 ✓ (0.00182); ft-v2 0.831/0.805/0.972/0.881 ✓ (0.8307/0.8048/0.9720/0.8805). **1,083×** ✓ = 13,000 ms / 12 ms (`real_model_integration.md:94`; zeroshot mean 13.00 s/row, 0/1500 failures — `zeroshot_report.md`). Rules exact-set 0.819 vs 0.788 (qa_prep Q7) ✓ (0.81933 / 0.78800). Zeroshot 221 FP vs 81 FN ✓.

**Parity:** Kaggle int8 ΔAUC 0.13 ✓ (0.1305, retrain_report.md); local int8 0.9934 vs torch 0.9969, Δ0.0035 ✓; 46/2,000 tuned-op flips ✓ (0.9770, ship_decision §2); fp32 export parity ≤9.7e-5 ✓ (span 9.73e-5).

**Corpus/data:** OSHA 105,996 ✓ · ASRS 47,723 ✓ · synthetic 9,687 ✓ · train 71,065 = 61,378 real + 9,687 synthetic ✓ · 13.6% ✓ (9,687/71,065 = 0.1363) · oil-gas 2,756 (2.60%) ✓ · seq p99 = 112 tokens ✓ · test = 2024-01-01..2025-11-30 ✓ · synthetic-detector AUC ≈1.0 disclosed ✓ (D16) · vocab gate 24/24 ✓ (KB §9; synthetic_qa_report §10.2 closed the 3 WC-term misses).

**Near-dup:** threshold 0.91 ✓, index 70,398×384 fp16 ✓ (byte-exact: 70,398×384×2 + 128 header = 54,065,792 B = `corpus_embeddings_fp16.npy`), p95 3.8 ms ✓ (KB §9); verbatim-osha banner cosine 1.000 ✓.

**Cost/packaging:** 4.19 + 1.11 GPU-h of 30 h ✓ (training_report.md: 15,099.6 s; retrain_report.md: 3,986.98 s); int8 artifact 152 MB ✓ (151,989,330 B); USB tarball 775 MB ✓ (775,353,704 B and 775,426,622 B both on disk); self-check 2 clean cycles ✓ (demo_final_state §6).

**Demo cards (demo_card.md scores):** 13 cards ✓; contrast-red 0.93 / LoF 0.85 ✓; green 0.01 ✓; wc-1 0.90 / CS 0.94 ✓; wc-3 0.98 / span `Welding` ✓; long-report 0.75 / 233 ms ✓; mega 0.98 ✓; codes-only 0.07 ✓; first-aid 0.26 ✓ — all = demo_final_state.md §2 live verification. Site post-state #1 213/213, rate 1.0, mean 0.958 ✓ (e2e log + live). Demo flag rate 71.0% (3,584/5,048) ✓ arithmetic + demo_final_state §1.

**Citation discipline:** "~20% of recordable injuries (BST/Mercer ORC 2011; Martin & Black 2015)" — corrected form used consistently in all four files; the "20–25% of near-miss reports" misquote appears only in never-say lists ✓. Baghjan framing, PTW/Bypassing out-of-scope (<0.1%), 33-string phrasebook, 10k-char cap, "LOTO not applied" = 16 chars — all ✓.

## D. Live-stack observation (not a deck number; resolved during audit)

At 17:12 IST the health endpoint briefly read n_reports 5,050 with Kathalguri already #1
(post-state) — the final-rehearsal agent was mid-restore (its `14_restored_prestate`
screenshot is 17:10). Re-checked 17:14: **pre-state confirmed correct** — health 4,548,
density Moran #1 (98) / Kathalguri #2 (88/88), matching the money-beat BEFORE table
exactly. On-disk `app/runtime.db` = 4,548 rows. No action needed; noted so nobody
double-restores.

## E. Exact replacement strings (for whoever patches)

- p95 19.7 ms → **p95 17.7 ms** (model-only; live e2e p95 56 ms if the e2e number is wanted) — 9 locations across the 4 files (F3).
- 37.3 reports/s → **45.6 reports/s** (5,048 accepted, 110.8 s) — 6 locations (F4); delete "39.4/s classify-only batch-32" entirely (F5).
- 17/17 → **18/18** (F6).
- Slide 8: "0.52" → "**0.68**" (F1); "(n=243 flagged)" → "(n=**245** flagged)" (F2).
- demo_card: pre-stage `n_reports: 5048` → `4548`; "was #2 with 31" → "was #2 with 88"; "Five thousand" → "Five hundred"; "5,048 accepted, 37.3/s" → "accepted 500/500 live, ~15 s" (F7-F9).
- Fill {{GOLD_RECALL}} = **0.836 [0.788, 0.874]**, {{GOLD_KAPPA}} = **0.513 ± 0.07 (n=130)**; strike {{GOLD_MCNEMAR_TFIDF_P}} per Q7's own fallback (F10).
- Add ASRS recall-0.00 + 93-pending-adjudication disclosure per KB §12 (W2).
