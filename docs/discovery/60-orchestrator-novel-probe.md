# Orchestrator probe — model behaviour on NOVEL text

**Author:** Hy4 (orchestrator, text-only). **Date:** 2026-09-25.
**Status:** directional probe, n = 18. **NOT a validated evaluation** — labels are my own
domain judgement, not human gold. Reproduced below so anyone can re-run it.

## Why this probe exists

Phase 0 agents reported a 71 % flag rate (3,587 / 5,056) in the live demo database. A flag
rate that high would destroy any triage value proposition. Before accepting either "the
model is broken" or "it's all fine," I needed to separate **the behaviour of the model**
from **the composition of the seeded demo database**.

Agents had already established that `demo_pre.db` is seeded from `artifacts/demo/bulk_ingest_5k.csv`,
whose rows are verbatim training/eval corpus rows (top-1 near-dup cosine measured at 0.99998).
So the demo database is largely **memorised** data. To see what the model actually does, I
queried it with text that appears in no training corpus.

## Method

POST /api/classify against the live stack on `http://127.0.0.1:8177/` (real
`RealOnnxClassifier`, `onnx:masked-v2/sif_multitask_int8.onnx`), bodies authored by me this
session. Decision threshold taken as the tuned operating point 0.658 (measured live by an
earlier agent; `classifier.py:179`).

## Result 1 — the score distribution is bimodal, not a ranking

Over 1,000 stored reports (`/api/reports?limit=1000`):

| percentile | sif_score |
|---|---|
| min | 0.004 |
| p10 | 0.011 |
| median | 0.966 |
| p90 | 0.996 |
| max | 0.999 |

Only **12 of 1,000** reports land inside the configured gray band [0.40, 0.60].
`/api/metrics/summary` independently: `flag_rate 0.7095`, `mean_score 0.6997`.

A "review-priority ranking" cannot prioritise when scores pile at 0.01 and 0.99 with an
empty middle. The confidence gray gate is nearly inert by construction (78 hits in 5,056).

## Result 2 — the model detects PHYSICAL MECHANISM, not BARRIER FAILURE

10 novel cases, 6 authored as genuine process-safety precursors, 4 as benign.

| case | expectation | score | spans | flagged @0.658 |
|---|---|---|---|---|
| crude oil tank entry, no gas detector, isolations unverified, no standby | FLAG | 0.2857 | 0 | no |
| valve replaced on running pump without LOTO | FLAG | 0.2801 | 0 | no |
| welding on tank roof near open oily drain, fire watch absent | FLAG | 0.1259 | 1 | no |
| two men in vessel during nitrogen purge, no BA | FLAG | 0.8899 | 0 | YES |
| 12 t spool traversed over crew in pipe rack | FLAG | 0.9606 | 1 | YES |
| bleed valve opened on pressurised gas header believed de-pressurised | FLAG | 0.9032 | 0 | YES |
| contractor name spelling corrected | CLEAR | 0.0144 | 0 | no |
| toolbox talk reminding about safety glasses | CLEAR | 0.0093 | 0 | no |
| pickup dented bumper at base camp | CLEAR | 0.0348 | 0 | no |
| fire & safety training for 34 contract workers | CLEAR | 0.0109 | 0 | no |

- **Benign: 4/4 correctly cleared**, mean 0.0173. Excellent true-negative behaviour. No false alarms.
- **Genuine precursors: only 3/6 flagged.** Mean 0.5742, median 0.5878, range 0.126 → 0.961.
- **Evidence spans: 2 produced across all 10 cases.** Two of the three *correctly flagged*
  precursors returned **zero** evidence spans.

Earlier 8-case probe (same method) agrees: housekeeping 0.0153, extinguisher inspection
0.0062, fire drill 0.0147 all cleared; a romanised-Hindi hand-in-machine guarding incident
scored **0.0074**; and a 2 m step-ladder slip with no injury scored **0.9340** — ranked
*above* the workover well-control case at 0.8739.

## Interpretation — the structural finding

The three **misses** are all *procedural barrier failures*:

- no gas test before tank entry (Energy Isolation / Confined Space),
- no LOTO on a running pump (Energy Isolation),
- hot work beside an open oily drain with the fire watch gone (Hot Work / Permit).

The three **hits** are all *physical mechanisms*: something heavy moving over people,
something pressurised releasing, somebody trapped inside a vessel.

That split is explained by how the labels were made. Training labels are derived
deterministically from **OIICS codes** on **OSHA realised-severe-injury narratives**, which
record what physically happened to an injured person — struck-by, caught-in, fall,
electrocution. They do **not** record the absent control. So the model learned mechanism,
not barrier state.

**This is a direct gap against the problem statement**, which explicitly asks for *barrier
failures*, *energy sources*, and *IOGP Life-Saving Rule* violations — not merely the presence
of high-energy mechanism. We do the first well and the second poorly.

It also explains the headline anomaly end to end: the demo database is seeded with rows that
contain realised mechanisms and were memorised (hence 0.999 scores and a 71 % flag rate),
while genuinely novel text reveals a model with strong true negatives but weak procedural
recall and almost no evidence spans.

## Result 3 — the verdict is NOT stable under paraphrase

Eight surface paraphrases of **one** scenario (confined-space entry with no atmosphere test and
unverified isolation — among the most lethal routine activities in oil & gas). Meaning held
constant; only phrasing varied.

| # | score | verdict @0.658 | wording |
|---|---|---|---|
| 1 | 0.8093 | flagged | "Entry was made into the crude oil storage tank for cleaning..." |
| 2 | 0.8607 | flagged | "A worker entered the crude oil tank to clean it without conducting a gas test..." |
| 3 | 0.4662 | NOT flagged | "Confined space entry into the storage tank was performed without atmospheric testing..." |
| 4 | 0.0262 | NOT flagged | "The vessel was entered for cleaning purposes. Atmosphere was not tested..." |
| 5 | 0.4207 | NOT flagged | "Cleaning crews went inside the crude storage tank even though nobody had..." |
| 6 | 0.8270 | flagged | "Without testing the air inside the tank or verifying its isolation, maintenance staff..." |
| 7 | 0.0260 | NOT flagged | "Tank cleaning was carried out by entering the vessel; no gas testing took place..." |
| 8 | 0.6092 | NOT flagged | "An employee cleaned the inside of the crude oil tank after entry, with no gas detector..." |

n = 8, mean 0.5057, **sd 0.3383**, min 0.0260, max 0.8607, **range 0.8347**. Flagged 3/8.
**The verdict flips under paraphrase.**

The two near-zero variants (#4, #7) are the ones written in **passive voice** ("the vessel was
entered", "tank cleaning was carried out"). Sensitivity looks surface-syntactic, not semantic.

Why this is the most serious finding in Phase 0: a paraphrase is something any reviewer, any
report author, and any judge can produce by accident. If rephrasing flips whether a precursor
reaches human review, then **the review-priority ranking is not decision-grade** — not because
the model is badly trained, but because the decision boundary is not robust. This is
demonstrable live on stage in under a minute.

## Result 4 — outcome leakage is real, but inconsistent

Paired probe, identical scenario, varying only whether a realised outcome is stated:

| scenario | no outcome | with outcome | delta |
|---|---|---|---|
| LOTO omitted on running pump | 0.2801 | 0.8144 | **+0.5343** |
| no gas test before tank entry | 0.8093 | 0.7860 | −0.0233 |
| suspended load traversed over crew | 0.9636 | 0.9951 | +0.0315 |
| 2 m ladder slip | 0.9450 | 0.9598 | +0.0148 |

The LOTO case jumps 0.53 when "hospitalised" is added — outcome vocabulary still influences
the score despite the documented outcome-masking stage. Note also that the *no-outcome*
tank-entry case reads 0.8093 here against **0.2857** for the same scenario in Result 2, where
the only difference was the extra clause "No standby man was posted". Adding an aggravating
detail **lowered** the score by 0.52 — the wrong direction.

## Interpretation — synthesis

Four symptoms, one root cause: **the decision boundary is memorised rather than semantic.**

1. Demo database scores are saturated at 0.99 because those rows *are* the training corpus
   (measured top-1 near-dup cosine 0.99998) → the 71 % flag rate is a seeding artifact.
2. Novel text scores are wildly unstable under paraphrase (sd 0.34).
3. Procedural barrier failures (no gas test, no LOTO, no fire watch) are missed; only physical
   mechanisms are caught — because OIICS training labels encode mechanism, not absent controls.
4. Outcome vocabulary still moves the score despite masking.

Presenting a high-precision calibrated "review priority score" is therefore **not defensible**
to an OIL technical panel. See `docs/redesign-plan.md` for the proposed response.

## Result 5 — self-consistency fixes RELIABILITY but not VALIDITY

I wrote 16 surface paraphrases each of one tank-entry scenario and one benign scenario and
measured what paraphrase-averaging buys.

| set | n | mean | sd | flagged/16 |
|---|---|---|---|---|
| tank entry, no gas test | 16 | 0.3179 | 0.3078 | 3 |
| benign administrative | 16 | 0.0111 | 0.0046 | 0 |

Averaging over random paraphrase subsets:

| estimator | tank sd | benign sd |
|---|---|---|
| single score | 0.3078 | 0.0046 |
| mean of 4 | 0.1313 | 0.0020 |
| mean of 8 | 0.0756 | 0.0011 |

So paraphrase-averaging is a genuine **reliability** fix: it cuts the tank-scenario spread by
~4× at n=8 (and ~2.3× even at n=4), and at ~20 ms a call it costs ~160 ms — affordable. A
"verdict stability" gray state driven by the spread slots straight into the existing
10-gate humility design.

**But it stabilises around 0.318, which is still below the 0.658 threshold.** The consensus
answer for this scenario is *wrong*, not merely noisy. Averaging therefore cannot rescue
procedural barrier failures; that needs different training signal, not smoothing.

Reliability and validity are separate defects and need separate fixes. Both are listed in
`docs/redesign-plan.md`.

## What the model IS reliably good at (the honest basis for a product claim)

Benign/administrative text is cleared with conviction: mean 0.0111, sd 0.0046, **0 of 16
false flags**. Physical high-energy mechanisms are caught: suspended load over personnel
0.9606, pressurised release 0.9032, personnel inside a vessel during nitrogen purge 0.8899.
The failure is concentrated in **procedural barrier absence** — exactly the IOGP
Life-Saving-Rule slice the problem statement names.

## Result 6 — the model penalises the NEAR-MISS REGISTER (train/serve skew)

`data_pipeline/masking.py` replaces 25 outcome stems with `[OUTCOME]`. It is applied at
**training** time (`build_corpus.py:209,274`) and **never at inference** — verified this
session: no `mask_text` call exists anywhere in `app/` (only comments and unrelated ONNX
`attention_mask`).

I scored identical texts raw (today's behaviour) vs masked (what the model was trained on):

| case | RAW | MASKED | delta |
|---|---|---|---|
| LOTO omitted, no outcome stated | 0.2801 | 0.2801 | 0.0000 |
| same + "severe crush injuries and was hospitalised" | 0.8144 | 0.9806 | +0.1662 |
| same + "Fortunately no injury occurred, but the crew recognised exposure" | 0.1000 | 0.4489 | **+0.3489** |
| realised fracture + hospitalised after fall from platform | 0.9747 | 0.9945 | +0.0198 |
| same mechanism, no outcome stated | 0.9408 | 0.9408 | 0.0000 |

Two consequences, both measured:

1. **A near-miss report scores LOWER than the identical hazard with the good outcome removed.**
   Base scenario 0.2801 → adding *"Fortunately no injury occurred"* gives **0.1000** (−0.180,
   a 64 % reduction). Masking restores it to 0.4489. This is an anti-feature at the core of the
   product: UA/UC and near-miss characteristically state that nobody was hurt, and the model
   reads that sentence as reassurance rather than as genre. The safer the report sounds, the
   less likely it reaches review.

2. **Outcome vocabulary still moves the score** despite the masking stage — evidence that the
   leak was never fully closed and is compounded by being absent at serve time.

**Runtime masking is therefore a validated, cheap fix** for this specific failure mode
(measured +0.349 on the near-miss case). It does **not** fix Result 3's paraphrase instability —
I tested that too, and for the 16 tank-entry paraphrases raw and masked scores came back
**identical** because those texts contain no outcome words. The two defects are independent.

Note this contradicts the naive hypothesis I set out with: masking is not the cause of the
instability. Applying it anyway is correct for consistency, and I recommend it, but for a
different and narrower reason than stabilisation.

## Honesty boundary

- n = 18 total, labels are my own expert opinion, **not** the human gold set.
- Deeply consistent with a disclosure already in the README: the ASRS stratum recall was
  **0.00** (aviation, fully out of distribution). This looks like the same fragility, closer to home.
- **Required follow-up:** build a proper labelled process-safety probe set (target n ≥ 100,
  ≥2 independent labelers, IOGP-rule-stratified) and measure recall per barrier type. Only then
  can any number here be quoted externally.

## Reproduce

Any classify call: POST `http://127.0.0.1:8177/api/classify` with
`{"text": "...", "source": "probe"}`. Prompts verbatim above.
