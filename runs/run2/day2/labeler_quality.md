# Labeler quality & the labeler-C question — evidence pack (Day 2 night)

Scope: gold-set human labeling integrity for the deck + Q&A defense. Every
number below is recomputed from raw artifacts by
`runs/run2/day2/selfcheck_gold_analysis.py` (run: `python3
runs/run2/day2/selfcheck_gold_analysis.py` — recomputes all figures from
`artifacts/gold/labels/labeler_{a,b,c,d}.jsonl` + `gold_items.jsonl` +
`model_scores.jsonl` and asserts equality with the published
`gold_metrics_{all4,noC}.json` / `agreement_{all4,noC}.json`; exit 0 = all
checks pass). **No human label or adjudication artifact was written or
modified by this analysis** — labels are read-only inputs.

Protocol reference: `gold/RUBRIC.md` (~150 items each, 1.5–2 h expected;
blind; S/N/U; first 20 items = identical calibration pilot for all four).

## 1. Per-labeler profiles (latest-wins per item, mirroring `export_labels.py`)

| labeler | items | S / N / U | SIF rate | unsure rate | median s/item | dup re-save rows | unassigned items |
|---|---|---|---|---|---|---|---|
| A | 171 | 99 / 57 / 15 | 58% | 9% | **12 s** | 0 | 0 |
| B | 173 | 117 / 23 / 33 | 68% | 19% | **13 s** | 3 | 0 |
| C | 169 | 46 / 114 / 9 | **27%** | 5% | **2 s** | **103** | 0 |
| D | 177 | 124 / 38 / 15 | 70% | 8% | 4 s | 5 | 0 |

Reading time = delta between consecutive *unique* items in first-appearance
order (duplicate re-save rows share a timestamp and are not reading events).

**The C evidence cluster (behavioral, not disagreement-based):**

- **Median 2 s/item**; 51% of C's item-to-item gaps are ≤2 s, 60% ≤5 s. Gold
  texts run ~60–120 words plus a title; 2 s is below any plausible read
  (~1500+ wpm sustained). Rubric budget was 1.5–2 h for ~150 items
  (≈40–50 s/item expected; A and B land at 11–13 s median).
- **21 same-second bursts** of unique items (largest: 6 distinct items saved
  inside one second, e.g. 19:16:20Z; a run of G0036/G0433/G0420 re-saves at
  19:18:50–52Z) and **103 exact-duplicate re-save rows** (272 rows for 169
  unique items, zero label changes on re-save) — batch/rapid-fire saving,
  not item-by-item reading.
- Inverted marginal: C is the only non_sif-majority labeler (67% N vs
  peers' 13–33% N) and the lowest unsure rate (5%) — fast *and* certain,
  the opposite of the expected speed–caution trade.
- Honest counterweight: D is also fast (4 s median, 57% of gaps ≤5 s) but
  D's marginal matches the peers (70% S) and D has the *best* pairwise
  agreement in the set (below). Reading speed alone does not convict;
  the case against C is the cluster: speed + bursts + re-saves + inverted
  marginal.

## 2. Pairwise agreement (items labeled by both, 3-way exact, latest label)

| pair | n | agree | S/N-only agree (n) |
|---|---|---|---|
| A–B | 48 | 60.4% | 80.6% (36) |
| A–D | 49 | 73.5% | 85.7% (42) |
| B–D | 36 | **86.1%** | 96.7% (30) |
| A–C | 32 | 59.4% | 63.0% (27) |
| B–C | 40 | **42.5%** | 57.1% (28) |
| C–D | 45 | 55.6% | 60.0% (40) |

Every pair containing C is worse than every pair not containing C
(max C-pair 59.4% < min non-C-pair 60.4%).

## 3. Pilot (20 identical items, all 4 labelers) and Fleiss' κ

| subset | all-4 | without C |
|---|---|---|
| calibration pilot (20 items) | κ = 0.2962 ± 0.0997, raw 35.0% | κ = 0.3305 ± 0.1397, raw 50.0% |
| double-labeled (spec'd κ subset) | κ = 0.346 ± 0.072 (n=130), raw 63.85% | κ = 0.4912 ± 0.097 (n=73), raw 78.08% |

C matches the A/B/D majority on only **12/20** pilot items — the 20 items
that were identical for everyone and reviewed together per the rubric.

## 4. How much of the all-4 "consensus" rests on C alone

The consensus policy (unanimous label across an item's raters) makes a
single-rater item trivially "consensus". Measured:

- **89 of 400 consensus items (22%) carry only C's label** (61 osha, 14
  asrs, 14 synthetic); C-solo labels run 68 N / 21 S.
- The model agrees with C-solo labels on only **39/89 (44%)**, vs
  **170/224 (76%)** on A/B/D-solo items.
- Consequence for the metrics: **37 of the 38 OSHA false positives** in the
  all-4 report are items where the only human label is C's `non_sif`
  (including e.g. G0148 "natural gas ignited … bilateral arm burns and a
  burn to the neck" → C: non_sif). The all-4 FP count — and therefore the
  all-4 precision of 0.838 — is materially a measurement of C's labeling
  behavior. The FN side is clean: **0 of 23** OSHA FNs are C-solo.

## 5. Exclusion options — both full metrics tables (recomputed, verified)

Operating point identical in both: p_raw ≥ 0.7464006 (D27 frozen, applied
once). "noC" = same pipeline, C's labels dropped.

**ALL-4** (`gold_metrics_all4.json`): coverage 400 consensus / 500, 100
pending adjudication (60 disagreement / 40 unsure), 0 unlabeled.

| stratum | n | pos | prev | recall [95% CI] | precision [95% CI] | F1 | TP/FP/FN/TN |
|---|---|---|---|---|---|---|---|
| **real pooled (headline)** | 313 | 238 | 0.760 | **0.824 [0.770, 0.867]** | 0.838 [0.785, 0.879] | 0.831 | 196/38/42/37 |
| osha_2024_25 | 267 | 219 | 0.820 | 0.895 [0.847, 0.929] | 0.838 [0.785, 0.879] | 0.865 | 196/38/23/10 |
| asrs | 46 | 19 | 0.413 | 0.000 [0.000, 0.168] | — | — | 0/0/19/27 |
| synthetic (never pooled) | 87 | 14 | 0.161 | 0.929 [0.685, 0.987] | 0.265 [0.162, 0.403] | 0.413 | 13/36/1/37 |

Rules (real pooled): macro-F1 = **0.523** over 1 qualifying rule
(line_of_fire, 70 pos, TP/FP/FN 63/108/7, P 0.368 / R 0.900); all other
rules <50 positives → "Other" (87 pos, P 0.430 / R 0.460 / F1 0.444).

**NO-C** (`gold_metrics_noC.json`): coverage 338 consensus / 500, 70 pending
adjudication (26 / 44), **92 unlabeled (SEV2 INCOMPLETE_LABELING)**.

| stratum | n | pos | prev | recall [95% CI] | precision [95% CI] | F1 | TP/FP/FN/TN |
|---|---|---|---|---|---|---|---|
| **real pooled (headline)** | 260 | 236 | 0.908 | **0.809 [0.754, 0.854]** | 0.990 [0.963, 0.997] | 0.890 | 191/2/45/22 |
| osha_2024_25 | 224 | 217 | 0.969 | 0.880 [0.830, 0.917] | 0.990 [0.963, 0.997] | 0.932 | 191/2/26/5 |
| asrs | 36 | 19 | 0.528 | 0.000 [0.000, 0.168] | — | — | 0/0/19/17 |
| synthetic (never pooled) | 78 | 16 | 0.205 | 0.938 [0.717, 0.989] | 0.357 [0.230, 0.508] | 0.517 | 15/27/1/35 |

Rules: macro-F1 = **0.593** (line_of_fire only: 63 pos, 59/77/4, P 0.434 /
R 0.937); Other 74 pos, P 0.463 / R 0.514 / F1 0.487.

**Trade-off summary:** dropping C buys precision (0.838 → 0.990) and κ
(0.346 → 0.491) but *costs* recall (0.824 → 0.809), coverage (400 → 338
consensus; 92 items become unlabeled, an SEV2 flag), and real-pooled n
(313 → 260, prevalence 0.760 → 0.908 — the surviving noC consensus is a
heavily positive-selected subset).

## 6. Recommendation (for the deck + adjudication session)

1. **Report BOTH configurations in the deck appendix.**
2. **Headline = all-4.** It is the configuration with no exclusion decision
   to defend: any post-hoc labeler exclusion announced alongside a precision
   jump invites "you tuned your eval". All-4 is also *not* the flattering
   number where it matters — recall **drops** without C (0.824 → 0.809), so
   all-4 does not hide misses; and its precision (0.838) is if anything
   pessimistic, because 37/38 OSHA FPs rest on C-solo labels (§4).
3. **The exclusion basis, if C is ever excluded, is behavioral** — 2 s
   median reading time with 21 same-second multi-item bursts and 103
   duplicate re-save rows = the protocol (read each report, one judgment per
   report) was not executed — **not** disagreement-based. Excluding a
   labeler because their labels disagree with the model or the majority
   would be circular with the evaluation the gold set exists to anchor, and
   we do not do it.
4. **Unless the morning adjudication materially changes the picture.** 100
   items (all-4) are pending adjudication; if rulings land and shift the
   all-4 confusion materially, re-run
   `gold/compute_gold_metrics.py` (score cache makes it seconds) and re-visit
   this recommendation with fresh numbers.

*Provenance note: an earlier intermediate export (`artifacts/gold/
gold_metrics.json`, 2026-09-09 01:19, a 3-labeler partial snapshot: 348
consensus / 72 unlabeled) shows real-pooled FP=43/FN=25 and line_of_fire
F1 0.580 (84 FP). Those figures are superseded by the canonical all-4/no-C
pair above (generated 01:31); quote only the canonical pair.*
