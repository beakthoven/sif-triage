# PLAN-COMPLETION AUDIT — run2 final validation (read-only)

Auditor: final swarm, plan-completion track. Date: 2026-09-10.
Sources audited: `runs/run2/REVISED_PLAN.md`, `HANDOFF.md` Part E (acceptance bar),
`runs/run2/CHECKPOINTS.md`, `runs/run2/DECISION_LOG.md` (D1–D30),
`runs/run2/kb/KNOWLEDGE_BASE.md`, `docs/deck/{deck,qa_prep}.md`,
`artifacts/gold/gold_metrics_final.md`, `runs/run2/day2/regression_log.txt`,
`runs/run2/day3/final_packaging.md`, `tests/adversarial_suite.py`, `artifacts/gold/labels/`.

Status legend: **DONE** / **PARTIAL** (shipped with documented deviation) /
**CUT** (dropped; justification noted) / **MISSING** (promised, not found, no cut-line).

---

## 1. Day-by-day scorecard vs REVISED_PLAN.md

### Day 1 — validate → freeze → data + first training

| Planned item | Status | Evidence / notes |
|---|---|---|
| H0 human escalation: docker root fix (30 min, non-critical) | **CUT — justified** | Never fixed; D5 removed docker from the critical path (bare-metal `run.sh` + SQLite ships instead). Docker-dependent Label Studio also dropped (custom `gold/labeler_app.py` used). Clean cut-line in DECISION_LOG D5/SEV1-2. |
| H0 human escalation: CPU clamp | **DONE** | Resolved twice (Sep 8 morning; recurred post-reboot Sep 9, root procedure found: platform_profile kick). `CPU_CLAMP_REPORT.md`, CHECKPOINTS Sep 9 20:50. |
| git init + venv | **DONE** | `.git/` present; KB §5. |
| Label-spec freeze H0–2 (D15/D9/D6/D2, gold protocol D7/D8) | **DONE** | `spec/label_spec.yaml` frozen v1.0.0 05:45, sha256 convention documented (hash-mismatch repair logged Sep 9). |
| Kaggle smoke kernel + export-gate BEFORE training (C4) | **DONE** | Export-gate GREEN on 2x T4 (fp32 parity ≤4.4e-5) before any training run; KB §8. |
| OSHA parse/dedup → dual-map labels → masking → ASRS → splits | **DONE** | Corpus 86k rows; dual era-conditional OIICS maps (D9); token-neutralization masking both classes (D6); temporal hard split + near-dup screen (D10). |
| Publish Kaggle Dataset | **PARTIAL — justified** | Kaggle MCP cannot create datasets (permission-denied, KB §9) → catbox HTTPS staging + sha256 manifests. Functionally equivalent; documented. |
| Synthetic OIL corpus: quotas, 8-gram dedup, outcome-leak reject | **DONE** | 9,036 rows, all quotas met after top-up (v2); leak + dedup gates in `data_pipeline/`. |
| Synthetic: LLM-ism detector AUC < 0.9, iterate | **PARTIAL — gate FAILED, disclosed** | AUC 1.0000 even register-matched. Ruled D16: ship with disclosure (register tells, label-unconfounded, 13.6% of train, separate gold stratum). Gate criterion never met; the *disclosure* shipped, the *<0.9 target* did not. |
| Config A (masked) + Config B (unmasked) training | **DONE** | Both trained on 2x T4 Day 1; masked-v2 retrain Day 1 evening (D21 first-aid fix). |
| Fast baselines (regex, TF-IDF+LogReg) | **DONE** | Baseline table complete; McNemar Holm-corrected (Sep 8 17:45). |
| FastAPI skeleton + ingestion + SQLite schema + Storage protocol | **DONE** | SQLite substituted for Postgres per D5 (docker down; numpy brute-force measured sufficient). |

**Day-1 exit criteria:** label spec frozen+hashed ✓ · export gate GREEN ✓ · ≥1 trained masked
model retrieved ✓ (after 2h-timeout recovery) · baseline row ✓ · corpus on disk ✓. **PASS.**

### Day 2 — system + full training + gold prep

| Planned item | Status | Evidence / notes |
|---|---|---|
| Remaining ablation configs C/D/E (NLP engineer's 5-config set) | **MISSING — quiet drop** | Only masked/unmasked (+masked-v2 retrain) ever ran. No ruling, no cut-line anywhere in DECISION_LOG/CHECKPOINTS. Not in the standing cut order (span → patterns → Hindi → zero-shot n). Low demo impact, but a promised ablation set silently became 2 configs. |
| Zero-shot qwen3:8b baseline (cap n=200 only if clamp persists) | **DONE — exceeded** | n=1500, 0 schema failures (clamp resolved, so full run). P 0.7996/R 0.9159/F1 0.8538. |
| Temperature scaling | **DONE** | T=1.684 (v1) / 1.6484 (v2), in artifact metrics.json. |
| Final ONNX int8 + parity gate → versioned artifact | **DONE** | Two-tier parity (D13); Kaggle-side RED adjudicated D20 (provider-dependent), local PASS; D27 single-text canonical path; versioned `artifacts/models/masked-v2/`. |
| Inference service (onnxruntime, char-offset spans server-validated) | **DONE** | Span invariant `text[start:end]==span.text` asserted pre-render; selfcheck enforces it. |
| 6 input gates | **DONE — exceeded** | 9 gates ship (confidence, negation, language, near-dup, drill, codes, well-control watch [SEV1-13], chunked-low-score [D29], validation). |
| Explanation renderer + Ollama contract layer | **DONE** | Deterministic templates + qwen3:4b rewording, format-contract, score-mutation guard; cache poisoning (63 rows) found by audit wave and purged Sep 9. |
| Pattern mining (lift-ranked co-occurrence + Wilson CIs) | **DONE** | `pattern_mine_selfcheck` PASS; pattern cards with n + Wilson CIs live (screenshots, demo beat 83.1s). Survived the cut order. |
| Review/override loop | **DONE** | Override persistence fixed + probed Sep 9 21:05 (404s on live paste were caught by the audit wave). |
| Dashboard: feed, amber triage, 4 gray states, density + FLIP re-rank, pattern cards, review queue; navy theme + hazard stripe; 1920×1080 | **DONE — redesigned** | All functional elements verified in screenshots + live beats. The navy/hazard-stripe skin was deliberately replaced by the calm-light redesign (D14 anti-red doctrine extended); 1366px variants also shot. |
| Gold labeling STARTS Day-2 evening (H36) | **DONE — late** | Slipped ~26h (machine slept Sep 9 daytime): labeling ran Sep 9 20:00 → Sep 10 01:30; C re-label finished **16:25 — after the 15:00 deadline**. Recovered, but the plan's Day-2-evening start did not happen. |
| Hindi phrasebook (30 strings, cloud-QA'd) | **DONE — scope as-planned** | 33 strings, UI chrome only (KB §6; the "37" was a miscount, corrected). Live translation was rejected in planning (4B gibberish measured) — the phrasebook-only scope IS the plan, disclosed on deck slide 11. No quiet narrowing. |
| Precompute ALL demo-corpus LLM outputs | **DONE** | Cached explanations; fallback recording uses cached phrasing. |
| 90s fallback recording v1 | **DONE** | Superseded by final 91.0s webm (Day 3), ffprobe-verified, every beat frame-checked. |

**Day-2 exit criteria:** end-to-end demo on real model ✓ · final artifact versioned ✓ ·
gold ≥50% by gate — ✗ at T-19h gate (4/500 at 08:00, started that evening), recovered
to 801 judgments by 01:30. **PASS with schedule deviation.**

### Day 3 — proof

| Planned item | Status | Evidence / notes |
|---|---|---|
| Gold complete → Fleiss' κ | **DONE — n shortfall** | All 500 items labeled, 0 unlabeled. κ 0.513 ± 0.066 but on **n=130 doubles, not the planned 150** (D7). Unannounced shortfall; CIs still reported honestly. |
| recall@precision-0.80 + corrected Wilson CIs per stratum, real-only headline | **DONE** | `gold_metrics_final.md`: real pooled P 0.976 [0.948,0.989] / R 0.836 [0.788,0.874]; per-stratum table present. **Caveat: headline covers only 407/500 consensus items; 93 excluded as adjudication-pending (SEV3-flagged in the artifact, not on the slide).** |
| Baseline table + Holm McNemar | **PARTIAL** | Done on the 1,500-row derived-label sample (slide 9). Gold-level McNemar (vs baselines on gold items) never wired; qa_prep Q7 rehearses the fallback answer explicitly. Acceptable, rehearsed. |
| Span token-F1 on 100-report adjudicated subset | **CUT — documented post-hoc** | Span head is dead at runtime (max token prob ~0.3, fires on punctuation — KB §11); the D2 keyword-attribution fallback is the de-facto ship path. The 100-report adjudicated span set was never created, so token-F1 is unmeasurable; the metric was replaced by substring-validity 100% (self-validated). Disclosed on deck slides 7–8. This matches the D2 pre-authorized fallback, but the *adjudicated-span eval* leg silently vanished — no adjudication instrument was ever built. |
| Redaction-ablation experiment (2h) | **MISSING — quiet drop** | D11 explicitly KEPT this experiment ("high Q&A value"). No artifact, no run, no cut-line. Deck slide 7 substitutes the Day-1 masked-vs-unmasked ΔAUC (a different, weaker experiment). The D11-weakened claim wording survives, so no false claim ships — but the promised robustness experiment was never run. |
| Adversarial suite green (10 + 5 new) | **DONE — exceeded** | 18/18 PASS in final regression log (23:10). NOTE: deck + README still say **17/17** — stale by one. |
| 50-row golden regression | **CUT — quiet** | No 50-row golden regression file exists. Substituted by the 7-suite regression battery (api_smoke, adversarial, onnx_classifier, near_dup, explain, pattern_mine, demo_pack selfchecks). Functionally covered, never formally cut. |
| Playwright e2e (webapp-testing skill) | **DONE** | e2e screenshots day1/day2, `money_beat_e2e.cjs`, `fallback_record.cjs` headless pass. |
| Latency re-measured (clamp-dependent) | **DONE** | `latency_v2_final.md` (unclamped verified): model p95 17.7ms, API e2e p95 46.9ms, ingest 45.6/s. NOTE: deck/qa_prep still quote v1-era **19.7ms / 37.3/s** — stale (conservative on throughput, but 19.7ms is the *old model's* number). |
| bare-metal run.sh + tarball packaging | **DONE** | `sif-demo-usb-20260910.tar.gz` 775,426,622 B (=740 MiB; deck's "775 MB" is the same number in decimal — consistent), sha256 3c5690d7, selfcheck 2 clean cycles. |
| README + architecture diagram + honest-claims | **DONE** | README §Architecture + §Honest claims present. |
| H58 domain-expert review of ~50 synthetic reports (optional) | **CUT — pre-authorized optional** | Never happened ("if outreach landed" — it didn't). Disclosed as roadmap item on slide 12. Clean deferral, explicitly optional in the plan. |
| Q&A deck (never-say, citations, Baghjan, contamination appendix) | **DONE** | `qa_prep.md`: 12 hard questions + bench + 12 never-say bans; contamination appendix pointers in deck. Gaps in coverage enumerated in §3 below. |
| Metrics money slide with corrected CIs | **DONE — with one stale cell** | Slide 8 has final gold numbers (0.98/0.84/κ 0.51) ✓ but **rules macro-F1 cell says 0.52 while the final artifact says 0.683** (one rule ≥50 positives). Conservative-wrong; fix or rehearse. |
| Final fresh-eyes swarm validation | **DONE** | Sep 9 19:40, 6 auditors; found 5 real defects (clamp, cache poison, money beat, WC gap, override 404s), all fixed by 21:05. The process worked as designed. |
| Full rehearsal, ethernet unplugged, 1920×1080 | **DONE** | Sep 10 13:20 physical-unplug proof (nmcli off → external dead, demo fully functional). |
| Fallback recording final | **DONE** | 91.0s webm, frame-verified beats. |

---

## 2. Acceptance bar (HANDOFF Part E) — element status

| Element | Status | Evidence |
|---|---|---|
| recall@P0.80 with CIs on blind gold | **DONE** | R 0.836 [0.788, 0.874] @ P 0.976, n=318 real pooled. Exceeds the bar. |
| Beats regex + TF-IDF significantly (McNemar p<0.05) | **PARTIAL — half missed, disclosed** | Beats regex decisively (p≈1e-68) and zero-shot LLM (p=0.0018); **TF-IDF tie (p=0.122) disclosed on slide 9 + qa_prep Q7** rather than met. On derived labels only. |
| Span exact-match ≥95% on gold | **REDEFINED → met on redefinition** | D2/KB §6 redefined to substring-validity 100% + token-F1 ≥0.80 on adjudicated spans. Substring-validity: 100% enforced. Token-F1 leg: never measured (no adjudicated span set). Original ≥95% exact-match was declared unattainable in planning. |
| <100 ms p95 classify | **DONE** | v2 final: model p95 17.7ms, e2e p95 46.9ms. |
| Bulk ingest ≥500/s | **REDEFINED → met** | D3: ≥500/s arithmetically impossible on this CPU → SLA ≥30/s sustained. Final measured 45.6/s. Pass on the adjudicated bar. |
| ONNX parity gate | **DONE** | Two-tier (D13); local int8 PASS, provider-sensitivity disclosed (D20). |
| 50-row golden regression | **SUBSTITUTED** | 7-suite regression battery; no literal 50-row golden file. |
| Adversarial suite all gated | **DONE** | 18/18. |
| Playwright e2e | **DONE** | |
| 100% offline demo verified by unplugging | **DONE** | Physical nmcli-off proof Sep 10 13:20. |
| Template fallback for every LLM call | **DONE** | Explanation layer + cache; fallback in selfcheck. |
| Gray-card path for low confidence | **DONE** | Confidence gate + D29 chunked-low-score gate. |
| one-command `docker compose up` | **SUBSTITUTED — justified** | Docker daemon unfixable in-window → `./run.sh` bare-metal, one command, selfcheck-verified (D5). The *spirit* (one-command bring-up) is met; the letter (compose) is not. |
| Column-mapping ingestion config, versioned artifacts, override→label loop | **DONE** | |
| README + architecture diagram + honest-claims | **DONE** | |
| Every deck claim traces to a measurement | **DONE with 3 stale cells** | All numbers trace to artifacts; three cells quote superseded measurements (adversarial 17/17 vs 18/18; latency 19.7ms/37.3/s vs v2-final 17.7/46.9/45.6; rules macro-F1 0.52 vs 0.683). None are directionally optimistic except arguably 19.7ms (v1 model-only number presented beside the <100ms bar, while ship-path e2e is 46.9ms — still passing). |

---

## 3. Special-focus findings (the promised-but-quiet items)

1. **Hindi phrasebook scope** — *as planned, not narrowed.* The plan promised exactly
   "phrasebook (30 strings, cloud-QA'd)"; 33 shipped, chrome-only, live translation
   rejected on measurement in Phase 1. Deck slide 11 disclaims live Hindi ML. Clean.

2. **Pattern mining** — *shipped.* Lift-ranked co-occurrence + Wilson CIs, selfcheck
   PASS, live demo beat. Survived its place in the cut order.

3. **Span head** — *the biggest honest downgrade.* Trained (val tok-F1 0.995), dead at
   runtime (KB §11), D2 fallback live. Deck discloses (slides 7–8) — **but qa_prep has
   no rehearsed answer** for "does the span head in your architecture diagram actually
   work?" and the promised adjudicated-span eval never existed.

4. **Gold protocol deviation D30 (LLM adjudication)** — *contained, undisclosed in
   deck/qa_prep.* The LLM panel's 100 rulings sit in `artifacts/gold/labels/adjudication_llm.jsonl`
   and a supplementary metrics variant exists, but the **final headline is human-only**
   (panel rulings never applied; 93 disputed items remain excluded as adjudication-pending,
   SEV3-flagged in `gold_metrics_final.md`). The integrity containment held. However:
   neither deck nor qa_prep mentions the panel's existence. If a judge asks "did any LLM
   touch your gold pipeline?", the rehearsed Q11 answer (contamination-separated,
   human-vs-human κ) is *true of the headline* but incomplete about the repo's contents.

5. **Deferred domain-expert review** — *cleanly deferred.* Was explicitly optional
   ("if outreach landed"); now a roadmap line on slide 12. No exposure.

---

## 4. The 5 most likely judge-visible gaps + qa_prep coverage

| # | Gap | In qa_prep? | Exposure |
|---|---|---|---|
| 1 | **ASRS stratum recall = 0.000** (19/19 missed, aviation fully OOD, self-inflicted train-only-negatives) — invisibly pooled into the "real pooled" headline n=318 (OSHA-only recall is 0.895). KB §12 says "deck must disclose"; the money slide shows no per-stratum table. | **NO** | A judge asking "break your 0.836 recall down by source" gets an unrehearsed 0.00. Highest-risk gap. Rehearse: "aviation is out-of-distribution by construction — ASRS was train-only negatives; the OSHA 2024–25 stratum, the one that proxies OIL, is 0.895." |
| 2 | **93/500 gold items excluded** (adjudication-pending: 44 disagreement + 49 unsure). Slides say "500 blind-labeled reports"; strata sum to 407. qa_prep's only arithmetic answer ("690 emitted") is additionally **stale** — C's re-label left 731 human judgments on disk (171+176+201+183), so the rehearsed count no longer matches the files. | **NO** | Any judge who counts. Rehearse: "500 labeled, 407 unanimous-consensus scored, 93 disputed held out rather than majority-voted — the conservative choice; ruling them is a one-command re-run." Fix the 690 line before showtime. |
| 3 | **D30 LLM adjudication panel** exists in the repo (unused in headline). Undisclosed anywhere judge-facing. | **NO** | Only fires if a judge inspects artifacts or asks "any LLM near gold?" — but the current Q11 answer would then read as a dodge. Rehearse the containment story: panel ran under user decision D30, rulings quarantined in a separate file, headline computed before/without them, human adjudication still available as superseding upgrade. |
| 4 | **Deck/artifact number drift**: rules macro-F1 0.52 (slide 8) vs 0.683 (gold_metrics_final.md); adversarial 17/17 (deck+README) vs 18/18 (regression log); latency 19.7ms/37.3/s (deck+qa_prep) vs v2-final 17.7/46.9/45.6 (KB §12). | Partially | Low individually (all still pass their bars; the 0.52 is conservative-wrong), but "your own slide disagrees with your own artifact" is exactly the kind of thread HSE judges pull. One-pass number sync recommended if the freeze allows doc-only edits. |
| 5 | **Span head dead at runtime** — disclosed on slides 7–8 but **not rehearsed** in qa_prep, and "evidence spans" are beat 1 of the demo. | **NO** (deck only) | Judge: "is that highlight from the model?" Honest rehearsed answer exists implicitly (substring-validated keyword-attribution fallback, span head kept as research artifact) — it just isn't in qa_prep. |

Covered adequately by qa_prep (no action): TF-IDF tie (Q7), zero-shot comparison (Q8),
int8 parity wrinkle (Q9), LLM-ism AUC 1.0 (Q5), val-vs-test AUC gap (Q6), missing 2 IOGP
rules (Q10), Baghjan (Q4), circularity mechanics (Q11, minus the D30/93-item caveats above).

---

## 5. Verdict

**Ship-state: ~92% of plan delivered; nothing false ships.** Every headline claim on the
deck traces to a real artifact, and every *dropped* capability that reaches the UI is
disclosed on a slide (span fallback, TF-IDF tie, 2 out-of-scope rules, LLM-ism AUC).

**Three quiet drops without cut-lines** (process violations of the plan's own cut-order
protocol, none demo-visible): ablation configs C/D/E, the D11 redaction-ablation
experiment, the literal 50-row golden regression.

**Two disclosure debts** that are artifacts-honest but deck/qa_prep-silent: the 93-item
adjudication-pending exclusion (and the now-stale "690" arithmetic), and the existence
of the D30 LLM adjudication panel. **One un-disclosed stratum landmine:** ASRS recall 0.00.

None of these are ship-blockers for a student hackathon demo; all five §4 gaps are
one-paragraph fixes to qa_prep.md. The plan's own doctrine — "every claim traces to a
measurement" — held; the gap is that three measurements never got made (C/D/E, redaction
ablation, span token-F1) and their absence was never announced.
