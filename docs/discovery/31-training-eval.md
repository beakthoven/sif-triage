# 31 — Training / Evaluation / Metrics audit (Phase 0 discovery, read-only)

Date: 2026-09-25. Scope: training/, gold/, artifacts/gold/, artifacts/models/masked-v2/,
runs/run2 (day1/day2/day3, KB, DECISION_LOG), README, HANDOFF, docs/deck (spot checks).
Method: every README "Honest claims" number traced to an artifact on disk; no retraining,
no recomputation-to-match; read-only (only this file written).

Note: `docs/redesign-plan.md` and `docs/backend-stack-decision.md` (the stated feed docs)
**do not exist** on disk. Audit proceeded from README/HANDOFF/KB/DECISION_LOG as ground truth.

## Files read (fully unless noted)

| File | LoC | Notes |
|---|---|---|
| README.md | 153 | full |
| HANDOFF.md | 239 | training/eval claims in §A.4/B.5/E |
| training/train.py | 934 | seed/hyperparams/temp/export-gate sections |
| training/model.py / selfcheck_model.py | 53/71 | skimmed, both trivial and healthy |
| gold/compute_gold_metrics.py | 953 | head, wilson/kappa/self-check sections |
| gold/sample_gold.py | 509 | sampling + leakage guards |
| gold/RUBRIC.md / RUNBOOK_HUMANS.md | 66/211 | blind protocol |
| gold/labeler_app.py | 289 | blindness verified (serves masked_text + title only) |
| gold/export_labels.py, adjudicate.py, simulate_labeling.py, gold_common.py | 198/494/369/34 | grep-level only |
| artifacts/gold/gold_metrics_final.{md,json} | 56/328 | canonical |
| artifacts/gold/agreement_final.json, gold_metrics_all4{.md}.json, all4v2.md, sample_manifest.json | — | |
| artifacts/models/masked-v2/{metrics,export_gate}.json, manifest.json | 102/29 | |
| runs/run2/{kb/KNOWLEDGE_BASE.md,DECISION_LOG.md} | 157/89 | |
| runs/run2/day2/{ship_decision.md, latency_v2_final.{md,json}, ship_eval/{parity_at_op,mcnemar_6model}.json, error_analysis.md} | 182/510/649 | |
| runs/run2/day2/{training_report,retrain_report}.md (grep), day3 audit .md files (grep/excerpts), docs/deck/{deck,qa_prep}.md (excerpts) | — | partial |

## CLAIM VERIFICATION TABLE

| # | Claim (README) | Artifact | Value in artifact | Verdict |
|---|---|---|---|---|
| 1 | Blind gold, real-pooled n=318: P 0.976 [0.948,0.989], R 0.836 [0.788,0.874], F1 0.900 | `artifacts/gold/gold_metrics_final.md:13`, `.json` strata.real_pooled | P 0.9755 [0.9476,0.9887], R 0.8357 [0.7883,0.8741], F1 0.9002, n=318, 286 pos | **VERIFIED** (caveats: findings F2/F6/F7) |
| 2 | Fleiss κ 0.513 ± 0.066, 130 doubles | `agreement_final.json` | κ 0.5129; SE 0.0657 (json) / 0.0655 (gold_metrics_final.md) — both round to 0.066 | **VERIFIED** (SE differs by 0.0002 between two artifacts — bootstrap noise, cosmetic) |
| 3 | 500 reports: 300 OSHA 2024-25 (incl 150 oil-gas) + 100 ASRS + 100 synthetic, 4 labelers | `sample_manifest.json` | counts 300/100/100, oil_gas_sampled 150 (from a 364-row pool), seed 42, 4 labeler queues | **VERIFIED with caveat** — "4 labelers" counts rater identities; labeler C's whole queue was re-labeled post-deadline by a "careful replacement labeler" (F2) |
| 4 | ASRS stratum recall 0.00 | gold_metrics_final.json strata.asrs | 0.0 [0, 0.168], 0/19 pos | **VERIFIED, framing incomplete** — ASRS also supplied 12,035 training negatives (F4) |
| 5 | Synthetic stratum P 0.347, reported separately, never pooled | gold_metrics_final.json strata.synthetic | P 0.3469 [0.229,0.487]; headline_stratum = real_pooled; synthetic excluded from pooled table | **VERIFIED** (but the stratum is train-overlapping, F5) |
| 6 | 93 split/unsure items excluded pending adjudication | gold_metrics_final.json gold.n_adjudication=93 (44 disagreement + 49 unsure); `adjudication_queue_final.jsonl` = 93 lines | 93 | **VERIFIED** (sensitivity when adjudicated: F7) |
| 7 | Op point max recall @ P≥0.80 → P 0.8000 R 0.9748 F1 0.8788, derived-label holdout n=17,731 | `artifacts/models/masked-v2/metrics.json` operating_point_test_tuned | P 0.80003, R 0.97480, F1 0.87881, n 17731, prevalence 0.6423, AUC 0.8680 | **VERIFIED** (proxy derived labels, disclosed in README row) |
| 8 | Classify latency p50 11.4 / p95 17.7 / p99 20.5 ms CPU-only | `runs/run2/day2/latency_v2_final.json` A2_realtest_x200 | 11.39 / 17.66 / 20.52 ms, n=200, int8, 8 threads, machine unclamped | **VERIFIED** |
| 9 | Bulk ingest 45.6 reports/s (5,050→5,048, 110.8 s) | `latency_v2_final.md` §3 Run 2 (clean window) | 45.56/s, 110.8 s, Tctl-gated; **but** `latency_v2_final.json` C_bulk_ingest records only the heat-soaked Run 1: 21.40/s, sla_pass false | **VERIFIED via md; JSON on disk contradicts** — clean-run output was never saved as JSON (F9) |
| 10 | Evidence spans 100% exact-substring validity | runtime invariant `app/classifier.py:165,538` (`text[start:end] == span.text` re-checked); ship_decision.md §6 asserts validity on 20-report sample | 100% on everything rendered (by enforcement), asserted on n=20 | **VERIFIED as an invariant; NOT a quality metric** — the planned token-F1-on-100-adjudicated-spans eval was never built (F10) |
| 11 | Near-dup threshold 0.91, 70,398-vector MiniLM index, p95 3.8 ms | KB §9; `artifacts/embeddings/corpus_ids.jsonl` = **70,398 lines (re-counted this audit)**; `app/tests/near_dup_embed_check.py` PASS (verbatim 1.000 / twin 0.997) | matches | **VERIFIED** |
| 12 | Fine-tune beats zero-shot qwen3:8b, McNemar Holm p=0.0018, 1083× lower latency | `runs/run2/day2/ship_eval/mcnemar_6model.json` (ft-v2-st vs zeroshot) | p_holm 0.0018239, n=1500, derived labels; 1083× in KB §10/DECISION_LOG | **VERIFIED** (labels are derived, not gold — disclosed) |
| 13 | Fine-tune vs TF-IDF+LogReg not significant p=0.122 | mcnemar_6model.json (tfidf vs ft-v2-st) | p_holm 0.12235 (n.s.); tfidf vs ft-v1-st p 0.0233 IS significant — disclosed in ship_decision §5 | **VERIFIED** |
| 14 | Training cost 4.19 + 1.11 GPU-h of 30 h quota | `day1/training_report.md:66` (15,099.6 s), `day2/retrain_report.md:32` (3,986.98 s, 1×T4) | 4.19 + 1.11 = 5.30 GPU-h, 24.52 h remaining | **VERIFIED** |
| 15 | "Calibrated" triage score | `metrics.json:65` temperature 1.6484147310256958; `train.py:486-503,857` (LBFGS on **val** logits) | T fit on val only; **zero ECE/Brier/reliability-diagram anywhere on disk** (repo-wide grep); eval-engineer's adopted plan ("ECE + reliability diagram on the large derived-label test", phase1-architecture/eval-metrics-engineer.md:42) was never implemented; day1/gold_metrics_pipeline.md:102 says ECE on gold "deliberately absent" | **T VERIFIED / "calibrated" NOT SUPPORTED** (F3) |
| 16 | README pointer `artifacts/gold/gold_metrics_final.md` | exists | matches README numbers exactly | **VERIFIED** (artifact present, not missing) |

Not reproducible from disk (no retraining allowed here, so marked, not failed): none of the
above required recomputation; every number traced to a stored artifact. The one number whose
machine-readable artifact disagrees with the headline is #9 (bulk ingest).

## FINDINGS

**F1 — SEV1 (honesty). Shipped INT8 artifact failed its own export parity gate.**
`artifacts/models/masked-v2/export_gate.json`: `int8_parity {agreement 0.99296, auc_drop
0.13055, recall_at_op_drop 0.0, pass: false}`, top-level `pass: false`;
`manifest.json` records `"export_gate_pass": false`. Gate spec (D13): agreement ≥99.5%,
ΔAUC ≤0.005 — both legs failed on Kaggle. Ship justification (ship_decision.md §2):
quantization error is execution-provider-dependent (D20: Kaggle RED, local ΔAUC 0.0035
PASS); int8-vs-fp32 decision agreement at the **tuned** op is 97.7% (46/2000 flips,
`ship_eval/parity_at_op.json` masked-v2 agreement 0.977); the operating point was tuned
**on the int8 single-text chain itself**, so the shipped system is self-consistent, and
the op-point P/R/F1 in metrics.json were measured with the shipped int8 artifact — not
extrapolated from fp32. Flip magnitudes are large (p 0.017↔0.975) — this is boundary
noise on ~2% of rows, bounded by the gray-gate/review-queue design. Disclosure status:
ship_decision §2 + KB §10/§11 + deck qa_prep Q9 (good, honest) — but the README
"honest claims" table has **no int8-parity row**, and the deck's training slide says
"Export gate: fp32 parity ≤9.7e-5 GREEN" (deck.md:150) without the int8 leg's RED.
*Recommendation: shipping is defensible — the metrics that ship were measured on the
shipped artifact and the self-consistency argument is real — but the gate failure must
appear in the README honest-claims table and once on the deck itself, not only in Q&A prep.*

**F2 — SEV1 (honesty). The headline gold numbers rest on a post-deadline replacement
re-label of labeler C's entire queue, disclosed only in run logs.** Sequence
(CHECKPOINTS.md:38-42, KB §12/§13, day2/error_analysis.md, day3/plan_completion_audit.md:51):
original labeler C was an outlier (2 s/item, 0.27 label rate); 37/38 OSHA FPs were C-solo
`non_sif` labels (error_analysis.md §1). Decision: re-label C's 169-item queue blind with a
"careful replacement labeler" (19 s/item). Numbers locked at the 15:00 deadline (12:10) with
C partial: P 0.982 / R 0.823 / F1 0.896 (n=297), κ 0.547 (n=110). C re-label finished 16:25 —
**after the deadline**; final metrics regenerated 16:23 IST: P 0.976 / R 0.836 / F1 0.900
(n=318), κ 0.513. The re-label is recorded in CHECKPOINTS/KB §13 but **not** in README's
honest-claims row nor in gold_metrics_final.md (which says only "4 labelers"). The
pre-re-label counterfactual is preserved (`gold_metrics_all4.md`: P 0.838 / κ 0.346).
`artifacts/gold/` is **not git-tracked** (0 files), so the original C judgments have no
versioned snapshot; on-disk judgment counts (labeler files sum 731) reconcile with no
documented total (690 design / 801+169 process) — the repo's own audits flag this.
*Assessment: a blind re-label of a demonstrably careless rater is methodologically
defensible and the direction was predictable from the error analysis — but swapping a
rater after seeing that they cause your FPs, after the deadline, and then reporting only
the improved numbers with "4 labelers" is exactly the shape of a hostile kill-question.
Disclose it on the metrics surface or soften the row.*

**F3 — SEV1 (honesty). "Calibrated" is unsupported; only temperature-scaled.**
T=1.6484 was fit once per epoch on **validation** sif logits by LBFGS (train.py:486-503,
called at train.py:857/892; metrics.json:65). There is **no ECE, no Brier score, no
reliability diagram, no calibration set anywhere** in the repo (grep across training/,
gold/, app/, artifacts/, runs/run2: only tokenizer-vocab "ece" and planning docs). The
eval-metrics-engineer ruling that was ADOPTED ("ECE + reliability diagram on the large
derived-label test", eval-metrics-engineer.md:42) was never implemented. What IS measured:
precision at the tuned op = 0.8000 by construction on derived test. A judge asking "show
me your reliability curve" has no artifact to point to. *Call it "temperature-scaled"
until an ECE/Brier number exists (computable offline on the 17,731-row test scores in
`runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl` without retraining).*

**F4 — SEV2. ASRS recall 0.00 is partly by construction, not just OOD.** ASRS supplied
**12,035 training negatives** (KB §8: train 61,378 = osha 49,343 / asrs 12,035 / syn 9,687;
sample_manifest asrs `dropped:in_corpus_train: 12035`). Gold ASRS items were correctly
excluded from literal train rows (sample_gold.py:187-219 leakage guard), but the model was
trained that this entire register is non-SIF. README's "aviation is fully
out-of-distribution" is true and incomplete — the honest sentence adds "ASRS was our
negatives source; zero recall there is an expected consequence, and aviation is not a
deployment domain."

**F5 — SEV2. The synthetic gold stratum has no train-leakage guard.**
sample_gold.py:242-258 `sample_synthetic()` samples 100 rows from
`artifacts/synthetic/clean_combined.jsonl` with **no check against train ids** — while the
module docstring (sample_gold.py:9-10) promises "gold must never contain training rows"
(honored for ASRS) and OSHA items come from the held-out test pool. The synthetic corpus
is 13.6% of training (9,687/71,065, KB §8) drawn from the same generation family, so the
100 gold synthetic items are train-overlapping with high probability. Impact is contained
— synthetic is never pooled, and its measured behavior is over-flagging (P 0.347), the
opposite of memorization — but **synthetic recall 0.944 must never be cited as
generalization**. (Corpus jsonl files are not on disk to verify id-level overlap; only
hashes are recorded.)

**F6 — SEV2. Gold prevalence is enriched; the 0.976 precision is not
prevalence-transferable.** Gold pooled prevalence 0.899 (OSHA stratum 0.950) vs derived-test
natural prevalence 0.6423 and production (unknown, lower). sample_manifest.json shows the
enrichment was deliberate (`prevalence_target 0.4`, `achieved_prevalence_proxy 0.75`,
`enrichment_ratio 1.1677`, oil-gas 115/150 SIF-proxy) using **derived labels as the proxy**
— deterministic, gold-label-independent, so not circularity, but the sampling used model-
independent proxy labels toward a positive-heavy mix. Recall is prevalence-robust;
precision is not. The README table does place derived-test P 0.8000 (at 0.64 prevalence)
directly above the gold row, which mitigates — add one explicit caveat sentence.

**F7 — SEV3. 93 excluded items: adjudication never happened; sensitivity is adverse.**
gold_metrics_final.json: `n_adjudicated 0`, 93 pending (44 disagreement + 49 unsure). The
planned human adjudication session was replaced by an LLM persona panel (D30, with
containment: headline stayed human-consensus-only, panel rulings in
`adjudication_llm.jsonl` (100 rows) never entered labels, κ human-only — containment
verifiable in gold_metrics_final.json `adjudication.rulings.n_applied: 0`). The interim
panel-adjudicated variant (`gold_metrics_all4_paneladj.json`, KB §12) shows the "hard
cases" effect: real pooled n=394 → **P 0.838 / R 0.726** — disputed items are
disproportionately model misses. No final-generation panel-adjusted variant exists on
disk. Expect the question "what is recall if you rule the 93?" — the honest answer is
"lower, likely ~0.73-0.79; ruling them is a one-command re-run."

**F8 — SEV3. Reproducibility: re-runnable in principle, not guaranteed in practice.**
Retained: kernels in-repo (runs/run2/day1/kernels/*.py, day2/retrain/train_masked_v4.py,
frozen recipe 3 ep / bs 32 / seq 128 / lr 2e-5, SEED=42 with full rng state,
train.py:126,269-279), spec hash frozen (db946283…, documented hash convention KB §8),
input sha256s (sample_manifest.json inputs, staging manifests
day1/staging/sha256_manifest.txt, day2/retrain/manifest.json), transformers==4.57.6 pinned
(requirements-dev.txt). Missing/unpinned: torch = Kaggle stock 2.10.0+cu128 (kernel
auto-detects, does not pin), numpy/scikit-learn unpinned, corpus jsonl and 1.8 GB
ckpt-ep*.pt **not on disk** (hashes only in manifests), catbox staging URLs are ephemeral,
fp16 autocast + GradScaler on T4 is not bit-deterministic. A re-run today reproduces the
recipe, not the bytes.

**F9 — SEV3. Stale references / dead artifacts (all conservative-direction).**
(a) `sample_manifest.json n_judgments_emitted: 690` — stale vs actual (audits admit the
count no longer reconciles); (b) compute_gold_metrics.py docstring still says
"masked-v1 … 0.821855" (code is parameterized; header text stale);
(c) gold/RUNBOOK_HUMANS.md adjudication section describes the superseded human session and
references `_all4` filenames (kept as historical protocol record per readme_hygiene_audit);
(d) KNOWLEDGE_BASE.md has two "## 12" sections and README points to "§10–12" while the
canonical gold correction sits in §13; (e) latency_v2_final.json holds only the
contaminated 21.4/s bulk run while the clean 45.56/s exists only in the .md table;
(f) intermediate `gold_metrics_all4v2.md` (INCOMPLETE_LABELING, 41 unlabeled) retained
alongside final; (g) metrics.json retains the vacuous val op point 6.85e-5 alongside the
tuned one (documented D19, fine).

**F10 — SEV3. The span-quality eval silently vanished.** Acceptance bar
(HANDOFF §E: "span exact-match ≥95% on gold") was redefined (D2/KB §6) to
"substring-validity 100% + token-F1 ≥0.80 on a 100-report adjudicated span subset"; the
adjudicated span set was never built, token-F1-on-gold never measured, and KB §11 records
the span head is "effectively dead at runtime" (max token prob ~0.3) — the keyword
fallback is the de-facto live path. Disclosed in day3/plan_completion_audit.md:67 and
deck slides; README's span claim is accurate but narrow. Do not let a judge hear "the
model highlights evidence" without the "keyword-attribution fallback is the live path"
qualifier.

**F11 — info.** κ SE differs 0.0655 (md) vs 0.0657 (json) — bootstrap rep noise; the
12:10-vs-16:23/16:25 ordering of "final metrics generated" vs "C re-label finished" is
ambiguous by ~2 min in CHECKPOINTS. Cosmetic.

## CONFIDENCE WE CAN DEFEND (hostile Q&A)

Strong, single-artifact traceable:
- Operating point P 0.8000 / R 0.9748 / F1 0.8788 on n=17,731 derived-label holdout
  (metrics.json; threshold tuned on that split, applied once to gold — no re-tuning on gold,
  recorded in the artifact itself).
- Latency p50/p95/p99 and bulk rate on clean windows; the OpenBLAS-starvation root cause
  and fix are documented with before/after numbers.
- McNemar results including the unflattering one (tfidf n.s. p=0.122 for v2, sig for v1)
  and regex/zeroshot comparisons on one shared sample.
- Training cost arithmetic (seconds billed, per-run, per-report).
- Blind labeling: protocol hard rules (RUBRIC.md:54-66), app serves only masked text +
  title (labeler_app.py:101-103), queue blind, no stratum, opaque ids.
- Label derivation: deterministic from frozen OIICS maps (data_pipeline/oiics_maps.py,
  spec sha db946283…), zero residual outcome stems verified (KB §8), gold never in train
  (OSHA from test pool; ASRS leakage guard enforced, 12,035 dropped).
- The never-pooled synthetic stratum and the disclosed out-of-scope rules.

Defensible with added disclosure (current surfaces are quiet about):
- INT8 gate failure + 97.7% tuned-op agreement (F1), the labeler-C replacement (F2),
  "calibrated" wording (F3), ASRS train-negatives confound (F4), synthetic-train overlap
  (F5), gold prevalence enrichment (F6), 93-pending sensitivity (F7).

Not defensible as currently worded:
- "Calibrated triage scores" as probabilistic calibration.
- Any implication that the 100% substring-validity number measures span quality.
- Any use of the synthetic-stratum recall (0.944) as a generalization claim.

## RECOMMENDATION (before judges see this)

1. README honest-claims: add one row — "INT8 export gate: Kaggle-side gate RED
   (ΔAUC 0.13); re-measured locally ΔAUC 0.0035; int8↔fp32 decision agreement 97.7% at
   the tuned op; op tuned on the int8 chain itself; fp32 fallback is documented
   non-decision-equivalent." Add the same one-liner to the deck's training slide
   (deck.md:150 currently states only the fp32 GREEN).
2. Gold row: append "one labeler's queue (169 items) was blind re-labeled by a careful
   replacement after a quality review; pre-replacement metrics (P 0.838, κ 0.346) are
   preserved in artifacts/gold/gold_metrics_all4.md" — or soften "4 labelers" to
   "4 rater queues (one re-labeled blind after a quality check)".
3. Replace "calibrated" with "temperature-scaled (T fit on validation)" everywhere, or
   compute ECE/Brier on the existing 17,731 test scores first (no retraining needed).
4. ASRS disclosure: add "ASRS supplied 12,035 training negatives" to the recall-0.00 line.
5. Label the synthetic stratum "drawn from the synthetic corpus family used in training;
   reported separately, never pooled; recall not a generalization claim."
6. Pre-build the Q&A answer for the 93 pending items using the panel-variant recall 0.726
   as the stated sensitivity bound.
7. Fix stale refs: n_judgments 690, compute docstring model/threshold, KB §12 duplication,
   RUNBOOK D30 pointer. Optionally snapshot artifacts/gold into git or runs/ for
   versioning (it is currently untracked, so the pre-relabel C labels are unrecoverable).