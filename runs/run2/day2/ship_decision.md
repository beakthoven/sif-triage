# SHIP DECISION — masked-v1 vs masked-v2 (PS 26165)

- **Date:** 2026-09-08 · **Agent scope:** CLI in-process eval (no server/DB touch; :8177 untouched)
- **Recommendation: SHIP masked-v2** (int8, single-text D27 path, op raw 0.746401 / cal 0.658108). Keep masked-v1 as the one-env-var fallback artifact (`SIF_MODEL_PATH`).
- All scoring: `onnx_score.Scorer` int8 **single-text batch=1** (the D27 canonical ship path) unless marked otherwise. Rule assertions use the **training order** (`train.py:87` = `onnx_score.RULES`), NOT the scrambled app `RULE_KEYS` zip (SEV1-1, fixed in parallel by another agent).
- Scripts + raw outputs: `runs/run2/day2/ship_eval/` (parity_v2.py/json, score_full_test_v2.py, single_text_masked_v2_test.jsonl, tune_op_v2.py, operating_point_v2.json, parity_at_op.py/json, first_aid_eval.py, first_aid_results.json, demo_cards_v2.py/json, mcnemar_v2.py, mcnemar_6model.json, spans_compare.py/json).

## 1. Headline comparison

| Metric (derived test split, n=17,731, prevalence 0.6423) | masked-v1 | masked-v2 | Δ |
|---|---|---|---|
| AUC, single-text ship path | 0.8548 | **0.8680** | +0.013 |
| AUC, batch-32 (provenance) | 0.8629 | — (not run; single-text is canonical, D27) | |
| AP, single-text | 0.8851 | **0.8931** | +0.008 |
| Op point (max R @ P≥0.80, single-text) | raw 0.821855 / cal 0.712581 | raw 0.746401 / cal 0.658108 | |
| Precision @ op | 0.8001 | 0.8000 | = |
| **Recall @ op** | 0.9736 | **0.9748** | +0.001 |
| F1 @ op | 0.8783 | 0.8788 | +0.001 |
| Recall @ P≥0.85 | 0.7727 | **0.8619** | **+0.089** |
| Recall @ P≥0.90 | 0.4742 | **0.5318** | +0.058 |
| Confusion @ op (TP/FP/FN/TN) | 11097/2773/292/3569 | 11102/2775/287/3567 | ≈ |
| Val AUC (torch, ep3) | 0.9966 | 0.9969 | +0.0003 |
| Val span token-F1 | 0.9948 | 0.9709 | −0.024 (no visible diff on real text, §6) |
| Val rules macro-F1 (≥50 support) | 0.9672 | 0.9645 | −0.003 (within same-seed noise band, retrain_report) |

v1 numbers re-derived from the day-1 single-text full-test scores
(`runs/run2/day1/operating_point/single_text_masked_test.jsonl`); v1's D27 op
reproduces exactly from those scores (P 0.8001 / R 0.9736 ✓). Note v1's
metrics.json AUC field (0.8629) is the batch-32 number — on the canonical
single-text path v1 is 0.8548.

## 2. Local parity — masked-v2 int8 (D13/D20 protocol)

Kaggle-side int8 gate was RED (AUC drop 0.1305, agreement 0.99296 vs torch —
retrain_report.md), the same provider-dependent phenomenon as v1 day-1
(D20: Kaggle RED, local PASS). Local measurements:

| Check | Gate | v2 result | Verdict |
|---|---|---|---|
| 200 test rows (seed 123), batch-32 same composition, @ frozen val op | agree ≥0.995, ΔAUC ≤0.005, Δrecall ≤0.01 | agree 0.9900 (2 flips), ΔAUC −0.0056, Δrecall 0.0 | **FAIL agreement** |
| 2,000 test rows (seed 42), batch-32, @ frozen val op | same | agree 0.9925 (15 flips), ΔAUC 0.0165, Δrecall 0.0 | FAIL |
| 2,000 rows **single-text ship path**, @ frozen val op | same | agree 0.9925 (15 flips), **ΔAUC 0.0035**, Δrecall 0.0 | AUC PASS, agree FAIL |
| Full val int8 (6,820) vs torch 0.9969 | ΔAUC ≤0.005 | int8 AUC 0.993411, **Δ 0.0035** | PASS |
| fp32 val subset (1,000, seed 5) vs int8 same rows | ΔAUC ≤0.005 | fp32 0.997408 / int8 0.993233, Δ 0.0042 | PASS |

The frozen-op agreement leg (0.9925) is measured at raw threshold 6.85e-5 — a
score region with near-zero density, where flips are harmless (both decisions
flag everything that matters). **The decision-relevant measurement is new
(1b): int8-vs-fp32 agreement AT THE TUNED OP on the ship path:**

| Model | agree @ tuned op (n=2,000) | P int8 / fp32 | R int8 / fp32 | max Δlogit |
|---|---|---|---|---|
| masked-v1 | 0.9830 (34 flips) | 0.7976 / 0.7972 | 0.9704 / 0.9836 | ~7 |
| masked-v2 | 0.9770 (46 flips) | 0.8015 / 0.7968 | 0.9696 / 0.9813 | ~7 |

Both models fail the 99.5% agreement leg at the tuned op (the op sits in the
mid-range where int8 logit noise moves decisions; flip rows swing e.g.
p 0.017↔0.975). D20's "ship int8" was ruled on frozen-op agreement — this
tuned-op flip rate had not been measured for v1 either. **Mitigation that
makes this acceptable:** the operating point is tuned ON the int8
single-text chain itself, so the shipped system is self-consistent; the
`SIF_MODEL_QUANT=fp32` fallback must be documented as NOT decision-equivalent
(97.7-98.3%), not as "same decisions". v2 is marginally noisier than v1
(46 vs 34 flips) — consistent with its worse Kaggle int8 gate; both are the
same int8 phenomenon, ranking intact (ΔAUC ≤0.004), boundary noisy.

## 3. THE FIRST-AID TEST (D21) — verdict: FIXED, and it generalizes

| Group | n | v1 flagged | v2 flagged | v1 p_raw mean/max | v2 p_raw mean/max |
|---|---|---|---|---|---|
| demo `first-aid-green` card | 1 | **1 (0.9960)** | 0 (**0.1531**) | — | — |
| fa_a train50 (seed 21) — IN v2 training data | 50 | 1 (syn-fa-a-0169 @ 0.9818) | 0 | 0.064 / 0.982 | 0.0010 / 0.0079 |
| **unseen20 (agent-written paraphrases)** | 20 | **3** (0.8455, 0.8708, 0.9064) | **0** | 0.231 / 0.906 | 0.0011 / 0.0052 |

- The demo card drops from 0.996 raw (p_cal 0.964, HIGH flag — D21) to
  0.153 raw (p_cal 0.262, clean LOW card). **The scripted encore beat works.**
- Contamination discipline: the 50 fa_a rows are in `train_final_v4.jsonl`
  (verified: all 500 ids present), so v2-clean there is exposure, not proof.
  The 20 paraphrases (new mechanisms: cable-tie cut, wasp/bee sting, steam
  scald, blister, knee bump, sliver, coolant splash, drum-lid jam…) were
  written fresh and are in NO training file: v1 still flags 15% of them;
  v2 clears all 20 with headroom (max 0.0052 vs op 0.746).
- Illustrative: syn-fa-a-0169 ("bumped his hard hat on an open junction box
  door; helmet bore the impact") — v1 flags 0.9818, v2 0.0004.

## 4. Thirteen demo cards — masked-v2 (in-process app-path mirror; rule order = training order)

Band on calibrated score (HIGH ≥0.7 / MOD 0.4-0.7 / LOW <0.4; GRAY = gray gate fired);
flag @ v2 op cal 0.658108; gates via app/gates.py (near-dup not evaluated — needs
the live index; synthetic cards fire it by design, D24).

| Card | Expected | v2 score → band | flag | wc | Top rule (p), TRUE order | Gates | Verdict |
|---|---|---|---|---|---|---|---|
| contrast-red | HIGH · flag · LoF dom | 0.934 → HIGH | ✓ | true (over-tag, = v1) | **line_of_fire (0.85)** ✓ (v1: 0.44) | — | PASS band/flag/rule |
| contrast-green | LOW · no-flag | 0.012 → LOW | ✗ ✓ | false ✓ | — | — | PASS (contrast 0.934 vs 0.012) |
| gray-negation | GRAY (negation) | 0.930 (gray) | — | false ✓ | working_at_height 0.55 | negation ✓ | PASS |
| gray-drill | GRAY (drill) | 0.013 (gray) | ✗ ✓ | false ✓ | — | drill ✓ | PASS |
| wc-baghjan-1 | HIGH · CS dom · wc | 0.896 → HIGH | ✓ | true ✓ | **confined_space (0.94)** ✓ (v1: 0.69) | — | PASS |
| wc-baghjan-2 | HIGH · EI dom · wc | 0.995 → HIGH | ✓ | true ✓ | **energy_isolation (1.00)** ✓ (v1: 0.94) | — | PASS |
| wc-baghjan-3 | HIGH · HW dom · wc | 0.985 → HIGH | ✓ | true ✓ | **hot_work (0.98)** ✓ (v1: 0.99) | — | PASS |
| hinglish | GRAY (language) | 0.019 (gray) | — | true (bop kw, = v1) | — | language ✓ | PASS |
| verbatim-osha | HIGH · flag · LoF dom | 0.996 → HIGH | ✓ | false ✓ | **line_of_fire (0.89)** ✓ (v1: 0.84) | (near-dup banner by design) | PASS |
| long-report | HIGH · flag · chunked | 0.473 (gray) | ✗ | true (= v1) | energy_isolation 0.18 | negation FP + confidence + long_input | DEVIATION (= v1: gray via negation FP; v2 also lands in confidence band — chunked positional collapse, SEV1-2 territory) |
| mega-report | HIGH · 7 bars | 0.975 → HIGH | ✓ | true ✓ | energy_isolation (0.95); 1/7 over tuned thresholds | — | PASS band/flag; DEV: 7-bars expectation unmet in BOTH models (v1: only hot_work 0.84) — bars render sub-threshold; narrate probability bars, not "all fire" |
| codes-only | codes-path accept, not eaten | 0.068 → LOW | ✗ ✓ | false ✓ | EI 0.01 (kw tag only) | min_length OFF, "codes path: LOTO" ✓ | PASS core (renders LOW slate not confidence-gray — same as v1, day-1 known) |
| first-aid-green | LOW · no-flag | **0.262 → LOW** | ✗ ✓ | false ✓ | — | — | **PASS — the D21 FP is gone** (v1: 0.964 HIGH flag) |

Tally v2: **11 clean/consistent PASS + 1 known-pattern DEVIATION (long-report,
grayed by the negation gate in BOTH models) + 1 PASS-with-note (codes-only)**.
v1 same table: first-aid-green was a HIGH-flag DEVIATION; all four
rule-annotated cards show the expected dominant rule under the TRUE order
(this empirically confirms SEV1-1 as the root cause of day-1 "rule drift"
F3/D22 — with the correct zip, v1's drift disappears too; v2's dominant-rule
probabilities are stronger: LoF 0.85 vs 0.44, CS 0.94 vs 0.69).

## 5. 1500-sample McNemar — 6 models (Holm-corrected)

Shared sample `zeroshot_sample_ids.json`; labels = derived `sif_label`.
ft-v1-st = v1 single-text scores @ D27 raw 0.821855 (NEW row, canonical path);
ft-v1-b32 = published day-1 row (batch-32 @ raw 0.52667, pre-D27 provenance);
ft-v2-st = v2 single-text @ raw 0.746401 (this eval).

| model | acc | P | R | F1 | TP/FP/FN/TN |
|---|---|---|---|---|---|
| regex | 0.5087 | 0.7568 | 0.3458 | 0.4747 | 333/107/630/430 |
| tfidf | 0.8160 | 0.7874 | 0.9772 | 0.8721 | 941/254/22/283 |
| zeroshot (qwen3:8b) | 0.7987 | 0.7996 | 0.9159 | 0.8538 | 882/221/81/316 |
| ft-v1-b32 | 0.8300 | 0.8031 | 0.9740 | 0.8803 | 938/230/25/307 |
| ft-v1-st | **0.8353** | 0.8065 | 0.9782 | **0.8841** | 942/226/21/311 |
| ft-v2-st | 0.8307 | 0.8048 | 0.9720 | 0.8805 | 936/227/27/310 |

Pairwise Holm p (selected): ft beats regex ~1e-68 everywhere; ft-v2-st beats
zeroshot p=0.0018 (ft-v1-st 0.00018); **tfidf vs ft-v1-st p=0.023 (sig),
tfidf vs ft-v2-st p=0.122 (n.s.)**; v2 vs v1 n.s. (p_holm 0.51 vs ft-v1-st,
1.0 vs ft-v1-b32). Honest read: on derived labels v1 and v2 are
indistinguishable; both beat regex and the LLM baseline; the tfidf margin is
thin at these op points and crosses Holm significance for v1-st only. (tfidf
still ships no rules/spans/calibration story; the fine-tune's edge is the
P≥0.80 guarantee + artifacts, and gold — not derived labels — is the final
arbiter per spec.)

## 6. Span quality — 20 real test reports (seed 11), both models, raw token-level

v1 ≡ v2. Fallback rate identical (16/20 both), spans emitted identical
(52 both). Where the span head crosses 0.5 the spans are the same clean
phrases (' crushed' 1.00, ' caught between' 0.92-1.00); elsewhere both fall
back to sub-word top-token fragments (day-1 F9/SEV3-4 — unchanged, in both
models, orthogonal to the ship choice). v2's val span token-F1 drop
(0.9948→0.9709) shows no visible effect on real 2024-25 OSHA text.
Substring validity held on every span (asserted).

## 7. Recommendation

**Ship masked-v2.** The D21 first-aid false positive — a scripted demo-card
failure and a real FP class (3/20 unseen paraphrases flagged by v1) — is
fixed with a 100× score margin and no collateral: derived-test AUC +0.013
(single-text), recall@P0.80 +0.001, recall@P0.85 **+0.089**, cards strictly
better (12/13 vs 11/13 clean, first-aid-green fixed, stronger dominant-rule
bars), spans a wash, McNemar a wash vs v1.

Counterweights, disclosed: int8-vs-fp32 flip rate at the tuned op slightly
worse for v2 (46 vs 34/2000 — same phenomenon, both fail the 99.5% leg at
the tuned op; ship path is self-consistent because the op was tuned on it);
val span F1 −0.024 (invisible on real text); tfidf McNemar margin n.s. for
v2 on the 1500 sample (sig for v1-st).

**Ship configuration:** `SIF_MODEL_PATH=artifacts/models/masked-v2` (int8
default), op raw 0.746401 / cal 0.658108 loaded from
`masked-v2/metrics.json operating_point_test_tuned` (written this eval;
manifest sha256/bytes refreshed, `local_amendments` entry added). The app
threshold loader picks it up automatically. masked-v1 remains the fallback
artifact. Gold application: run `gold/compute_gold_metrics.py --model-dir
artifacts/models/masked-v2` (score cache is fingerprint-keyed, so v1's cache
is untouched). fp32 fallback is NOT decision-equivalent (97.7% at op) —
document, don't claim.

Files written by this eval: everything under `runs/run2/day2/ship_eval/`,
`artifacts/models/masked-v2/metrics.json` (+`operating_point_test_tuned`),
`artifacts/models/masked-v2/manifest.json` (sha refresh + amendment),
`artifacts/baselines/finetune_masked_v2_test1500_optuned.jsonl`,
`artifacts/baselines/finetune_masked_test1500_optuned_singletext.jsonl`.
No git operations; :8177 untouched.
