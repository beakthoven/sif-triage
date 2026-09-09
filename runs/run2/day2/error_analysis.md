# Error analysis — model vs all-4 human consensus (Day 2 night)

Setup: gold truth = unanimous human label (all-4 configuration, 400 consensus
/ 500 items, 100 pending adjudication). Model = `artifacts/models/masked-v2`
int8, single-text D27 path, frozen operating point p_raw ≥ 0.7464006 applied
once. All numbers recomputed and verified against
`artifacts/gold/gold_metrics_all4.json` by
`runs/run2/day2/selfcheck_gold_analysis.py` (exit 0). Analysis is read-only
on human labels.

Confusion (all-4 consensus): **real pooled 196/38/42/37** (TP/FP/FN/TN);
osha 196/38/23/10; asrs 0/0/19/27; synthetic 13/36/1/37.

*Provenance note: the brief's "43 FP / 25 FN, line_of_fire F1 0.58 / 84 FP"
matches the superseded intermediate `gold_metrics.json` (3-labeler partial
snapshot, 348 consensus / 72 unlabeled). Canonical numbers below come from
the all-4 export. See labeler_quality.md §5.*

## 1. False positives — 38 OSHA + 36 synthetic

**Provenance caveat first (honesty requirement): 37 of the 38 OSHA FPs are
items whose only human label is labeler_c's solo `non_sif`** (0 of 23 OSHA
FNs are C-solo; labeler_quality.md §4). Some are genuinely questionable
calls — G0148 "natural gas ignited … bilateral arm burns and a burn to the
neck" (p=1.000) is `non_sif` only because C said so. The no-C configuration
(FP=2, P=0.990) shows what the FP class looks like without C. So: read the
taxonomy below as "where model and C disagree" as much as "where the model
errs"; morning adjudication resolves these 89 C-solo items for real.

**Shape of the errors: every OSHA FP is confident — 0 of 38 sit below
p=0.9.** These are not threshold-marginal cases; the model is sure.

FP taxonomy (38 OSHA):

- **Low-energy finger/hand caught-between — 19/38 (50%).** Fingertip and
  knuckle events: manifold shifts onto a little finger (G0114, p=1.000),
  fan blade takes a knuckle (G0245), wrench/flange pinch (G0098), gate
  latch (G0189). Mechanism: the line-of-fire signature ("caught between",
  "crushed", pinch) is exactly what the SIF head learned, and
  outcome-masking removed the severity cue that lets a human read
  "fingertip [OUTCOME]" as minor-permanent rather than life-threatening.
  The model cannot see energy *scale* once the outcome is blanked.
- **Vehicle / mobile equipment, low energy — 13/38.** E.g. G0212: boom-lift
  wheel runs over a foot while boarding it out of mud (p=1.000). "Ran over"
  fires the struck-by detector; humans read survivable, foot-level contact.
- **Other — 6/38.** Two flash fires (G0148, G0077), two falls-to-lower
  (G0014 scaffold fall!, G0299 stairway), hot-mud burns (G0286). This bucket
  contains the clearest C-solo label-quality suspects (G0148, G0014).

**Synthetic over-flagging (36 FP of 49 flags, P=0.265 [0.162, 0.403],
median FP p_raw = 0.994).** Provenance is mixed (only 11/36 C-solo), so
this one *is* genuine model behavior. Mechanism: synthetic negatives are
mechanism-rich by construction — they narrate energy-isolation, pressure,
hot-work and lifting vocabulary in OIL register, with the barrier holding
or the contact narrowly missed (G0492: rusted bleed plug, pressure ejects
a grease cap past a fitter's chin, p=0.999; G0488: wrong breaker locked,
live transformer hums in hand, p=0.999). The model weights *mechanism
presence* over *barrier-held / near-miss negation* language — a
conservative bias. Framing for the deck: this is the review-queue
containment story — the system is a triage layer (D14): an over-flag costs
a reviewer minutes, an under-flag costs a missed precursor, and the
operating point (max recall at precision ≥ 0.80) chooses that asymmetry
deliberately. Synthetic is reported separately and never pooled (spec
gold.reporting).

## 2. False negatives — 23 OSHA + 19 ASRS + 1 synthetic (C-clean)

0 of the 23 OSHA FNs rest on C — these are real misses. 5 of 23 sit just
under the threshold (p 0.529–0.644); the rest are below 0.05.

- **Same-level falls with serious outcomes — 8/23.** G0194: slips on a
  mopped floor, strikes head, skull [OUTCOME] (p=0.001); G0003: trips on a
  pallet, broken hip (p=0.002); G0119: slips on rock, broken femur
  (p=0.004). Mechanism: the frozen SIF definition (B_middle, D15) and the
  training *negative pool* (spec: same-level-fall codes 42x/7xx as
  low-energy negatives) taught the model "same-level fall = non-SIF". The
  human rubric asks "could this have killed" — a backward fall with head
  strike on concrete qualifies. This is a documented spec-vs-rubric
  tension (the negative-pool codes are the model's blind spot), the single
  most defensible FN class to name in Q&A.
- **Heat / overexertion medical — 5/23.** G0232: 96°F, chest pains and
  cramping (p=0.001); G0222: rhabdomyolysis during smokejumper training
  (p=0.002). No high-energy mechanical mechanism → model silent; humans
  judge heat-stroke-class exposure as SIF-potential.
- **Low-height falls — 3+.** G0108: steps off a 6-inch platform, [OUTCOME]
  tib/fib (p=0.644); G0210: falls off a rolling chair (p=0.564).
- **Struck-by near-misses just under threshold — the honest near-band.**
  G0027: forklift strikes a pedestrian, broken ankle (p=0.548); G0110:
  machinery tire backs onto a worker's hip (p=0.529). These are genuine
  model misses, not definition edge cases.

## 3. ASRS recall 0.00 — the honest explanation for the deck

19/19 consensus-positive ASRS items missed; **max p_raw = 0.0017, median
0.0009** against a 0.7464 threshold. This is not borderline — the model
actively rejects the stratum. Two compounding mechanisms:

1. **OOD register.** ASRS narratives are aviation (CRM issues, SID crossing
   restrictions, landing-gear extension failures — e.g. G0376, aircraft
   powers up toward the chock crew, p=0.0014). The training distribution is
   OSHA oil-gas industrial-mechanism text; masked-v2 is a domain mechanism
   detector, not a generic hazard reader. ASRS was included in gold exactly
   as this OOD stress stratum (D8).
2. **Self-inflicted by training policy — disclose this plainly.** ASRS rows
   are in *training* as weak-labeled **negatives** (spec
   `negatives.sources.asrs_weak`, usage `train_only_never_eval`). The model
   had every incentive to learn "aviation register → negative". Gold then
   labeled ASRS by the rubric and found 19/46 consensus-positive. The
   recall-0.00 row is partly a train/eval label-policy conflict, not a pure
   capability measurement.

Deck line: the engine is scoped to industrial upstream reports; the ASRS
stratum is disclosed as OOD stress with recall 0.000 [0.000, 0.168], and it
bounds the deployment claim rather than denting the OSHA headline
(0.895 [0.847, 0.929]).

## 4. Per-rule gold metrics — what the deck may and may not say

Real-pooled, per-rule one-vs-rest at the frozen per-rule thresholds
(`masked-v2/thresholds.json`); verified against `gold_metrics_all4.json`:

| rule | gold pos | TP/FP/FN | P | R | F1 | ≥50 pos? |
|---|---|---|---|---|---|---|
| line_of_fire | 70 | 63/108/7 | 0.368 | 0.900 | 0.523 | **yes** |
| working_at_height | 29 | 22/22/7 | 0.500 | 0.759 | 0.603 | no |
| driving | 8 | 2/11/6 | 0.154 | 0.250 | 0.190 | no |
| energy_isolation | 10 | 4/5/6 | 0.444 | 0.400 | 0.421 | no |
| hot_work | 10 | 6/10/4 | 0.375 | 0.600 | 0.462 | no |
| safe_mechanical_lifting | 21 | 6/5/15 | 0.545 | 0.286 | 0.375 | no |
| confined_space | 9 | 0/0/9 | — | 0.000 | — | no |
| **Other (merged, disclosed)** | 87 | 40/53/47 | 0.430 | 0.460 | 0.444 | — |

**The plain statements the deck must make:**

- **"Rules macro-F1 = 0.523" is one rule, not seven.** Only line_of_fire
  clears the spec'd ≥50-gold-positives bar (`cs_ei_support_weakness`); the
  macro-F1 is LoF's F1 restated. Never present it as a 7-rule average.
- **The rules head is a secondary, explanatory signal** — the UI shows
  per-rule probability bars and never asserts a single rule (D22). The
  triage decision comes from the SIF head alone.
- **line_of_fire: recall 0.900 at precision 0.368 (108 FP).** The rule head
  fires broadly on caught-between/struck-by text — the same low-energy
  mechanism confusion as the SIF head's FP class (§1), amplified. It is a
  recall net for highlighting, not a filter.
- **confined_space recall 0/9** matches the frozen spec's known weakness
  (0.35% of real positives; synthetic quotas carried training) — disclosed
  at freeze, confirmed on gold.
- no-C configuration for comparison: LoF 63 pos, 59/77/4, P 0.434 / R 0.937
  / F1 0.593; macro-F1 0.593 (still LoF alone ≥50).

## 5. What changes after adjudication

100 items (60 disagreement / 40 unsure) are pending morning adjudication,
and 89 C-solo items contaminate the FP count (§1). Both move the FP/FN
counts; the FN *taxonomy* above (C-clean) and the ASRS finding will not
change qualitatively. Re-run `gold/compute_gold_metrics.py` after rulings
land, then re-run `runs/run2/day2/selfcheck_gold_analysis.py` — every number
in this report and labeler_quality.md is asserted by it.
