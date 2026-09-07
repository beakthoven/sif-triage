# Phase 1 — Data Pipeline Engineer (PS 26165)

All numbers MEASURED on `data/January2015toNovember2025.csv` (105,996×28, pandas) on this machine, 2026-09-08, unless marked INFERRED.

## 1. Findings

**F1 — The OIICS 2024 break is a renumbering, not a title artifact (SEV1).** Handoff §B.2 and VALIDATION_LOG P0-1 frame it as comma-loss/whitespace in titles. Measured truth: v2.01 reassigned code *meanings*. Same 2-digit prefix, different event:
- `62x`: 2015-23 "Struck by falling object" (n=14,607) → 2024-25 "Animal bites" (n=192)
- `43x`: fall-to-lower-level (n=15,012) → fall-on-same-level (n=2,497)
- `64x`: caught-in-running-equipment (n=21,462) → struck-by-falling-object (n=2,164)
- `65x`: collapsing-structure (n=236) → struck-by/caught-in running powered equipment (n=4,053)
- `44x` (jump-to-lower): **eliminated** in v2 (0 rows post-2023)

**Parent-code rollup is mathematically impossible** — the parent itself changed meaning. Handoff §B.2's "dual maps OR roll up to parent codes" contains a live landmine. Since 2024-25 (17,746 rows) is exactly the temporal TEST set, a single map or rollup leaves training correct but scrambles test labels → per-rule F1 collapses silently at evaluation, the worst failure mode. Dual era-conditional maps are mandatory, not optional.

**F2 — Era-conditional map, measured.** Codes→rules (v1: WaH=43x/44x, LoF=62x/63x/64x/65x, Driving=2xx, HW=31x/32x, EI=51x, CS=56x; v2: WaH=41x, LoF=63x/64x/65x/66x, Driving=2xx, HW=31x/32x, EI=51x, CS=56x) + narrative/SourceTitle keyword LFs (CS/EI/HW/SML): unmatched 25.3% (26,801), multi-rule 5.91% (6,261), SIF-positive (rule union) 74.7% (79,195). Per-rule: LoF 44.2%, WaH 17.4%, Driving 8.9%, HW 3.8%, SML 3.7%, EI 2.2%, CS 0.7% (744). **SIF-label definition is a free choice swinging positives from 55.4% (5-prefix) to 74.7% (rule union) — must be frozen in the spec.**

**F3 — Negatives.** Unmatched rows are 96.8% hospitalized, 4.8% amputated — real severe injuries. As negatives they are only usable outcome-masked; exclude the 219 amputated low-energy rows. Low-energy pool (same-level falls v1-42x/v2-43x + overexertion 7xx): 14,961. ASRS: screen out high-energy `Events_Anomaly` (airborne conflict etc.) before calling anything a negative (INFERRED until ASRS anomaly semantics are spot-checked Day 1).

**F4 — Oil-gas seed (NAICS 211/213): 2,756 rows.** Per-rule: LoF 1,610, WaH 300, HW 250, SML 187, Driving 106, **EI 47, CS 29** — EI/CS seeds too thin to style-anchor alone; synthetic must carry those rules.

**F5 — Splits: employer-grouped ∧ temporal is incoherent.** 67,879 unique employers; 4,839 appear in both eras; **42.0% of test rows have their employer in train** (lower bound — "u.s. postal service"/"usps"/"united states postal service" are unnormalized variants). Hard both-way grouping would force dropping 42% of test.

**F6 — Dedup.** Exact: 65 excess train, 1 test, 2 cross-boundary. Near-dup (8-gram Jaccard, 1,500-row test sample vs all train, distinctive-shingle index): J≥0.5: 2 (0.13%), J≥0.3: 8 (0.53%). Worst pair is verbatim "An employee was struck by a forklift." Dedup pre-split + cross-boundary screen at J≥0.5 is sufficient — verified small, not zero.

## 2. Risks

- **SEV1-1: OIICS v2 renumbering** — any single-map/rollup implementation silently corrupts 100% of test labels (F1).
- **SEV2-1: Outcome-mask must cover negatives too.** Unmasked OSHA negatives (96.8% hospitalized) leak outcome text into class 0; model learns "outcome words = SIF" even harder. Masking spec must state: mask applies to every OSHA row regardless of class; dual masked+unmasked variants of the full train set + masked copy of eval for the ablation.
- **SEV2-2: SIF-label definition unfrozen** (55.4% vs 74.7%, F2).
- **SEV2-3: CS (744) / EI (2,300) marginal classes**; OG seeds 29/47. Without heavy synthetic quota these are decoration.
- **SEV2-4: employer∧temporal incoherence** (F5) — unspecified composition = arbitrary leakage.
- **SEV3:** Snorkel stale (C11); mask sensitivity to word list (70.4% vs 76.4% — list must be frozen); ASRS negative labels are weak by construction — never in eval.

## 3. Recommendations per architecture element

- **Dual OIICS maps: ADOPT + MODIFY.** Era-conditional code maps exactly as F2 (code lists frozen in `label_spec.yaml`); explicitly **REJECT parent-code rollup**. Validate map on `EventTitle` per prefix per era (assert no prefix has mixed-era semantics).
- **Snorkel: REJECT.** The derivation is deterministic (codes + regex) — no generative label-model needed. Plain python LFs; C11 risk deleted.
- **Multi-rule rows: ADOPT multi-label.** Keep full rule set as target vector; deterministic precedence (keyword rules > code rules; fixed tie-order) only for primary_rule used in stratification/macro-F1.
- **Outcome-masking: MODIFY.** Frozen 12-stem list in `label_spec.yaml`; clause-split, drop clause iff it has an outcome stem AND no mechanism cue (`struck by|caught|fell|contact|pinned`); else token-mask. Mechanism words ("crushed between") survive. Masked + unmasked variants of every train row.
- **Negatives: MODIFY.** Train mix ≈ OSHA-pos 55% / OSHA low-energy-neg 15% (amp=0, masked) / ASRS-neg 15% (anomaly-screened) / synth-pos 10% / synth-neg 5% → ~40% prevalence; tune threshold on val for precision ≥0.80. Eval on 2024-25 OSHA + blind gold only; ASRS/synthetic never in headline metrics.
- **Synthetic corpus: MODIFY (C5 replacement).** Style seeds = 2,756 OG OSHA narratives (outcome-masked, entity-swapped) + SmartQHSE vignettes + SmartQHSE org's `iogp-life-saving-rules-2018`/`hse-glossary`/`hse-acronym-dictionary` (verified to exist, Phase-0) for DGMS/OISD-register vocabulary. Per-rule quotas inverse to F4 frequency (CS/EI heaviest). Dev-time cloud LLM legal (public data only). LLM-ism detector: TF-IDF+LogReg real-vs-synth, 10-fold AUC — minutes with installed sklearn; iterate temperature/length/misspelling injection until AUC<0.9. Honest caveat: detector-weak ≠ indistinguishable.
- **Splits: MODIFY.** Temporal hard (train ≤2023, test 2024-25); employer-grouping only for train/val split; accept cross-era employer overlap, mitigate with cross-boundary J≥0.5 screen + normalized-employer leakage audit in `splits.json`.
- **Dedup: ADOPT.** Order verified correct; add the J≥0.5 cross-boundary pass (F6).

## 4. Output artifact set (training-notebook contract)

`label_spec.yaml` (frozen maps/regexes/stems/ratios/split policy) · `osha_labeled.parquet` (id, upa, event_date, era, employer_norm, narrative_raw, narrative_masked, sif, rules[7], primary_rule, oiics_event, event_title_norm, naics4, is_oilgas, amp_flag, hosp_flag, dup_group_id) · `asrs_negatives.parquet` (acn, narrative, anomaly, weak_neg_reason) · `synth_oil.parquet` (text, rule, sif, gen_model, seed_id, detector_score, jaccard_max) · `splits.json` (ids, groups, boundary near-dup report) · `train/val/test.jsonl` (text, sif, rules[7], weak span labels from LF match offsets).

## 5. Verdict

Pipeline direction is sound; the v2-renumbering trap and five spec-level freezes are the difference between a working eval and silent garbage. With F2 map + frozen spec, Day-1 data plan is executable as scheduled.

<<SCORES {"ps":"26165","role":"data-pipeline-engineer","go_no_go":6,"severity":1,"feasibility":8,"data_risk":3}>>
