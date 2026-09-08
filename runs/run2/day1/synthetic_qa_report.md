# Day-1 Synthetic QA + Corpus Merge Report

**Scope:** SIH 26165 SIF-precursor engine, Day-1 critical path. QA of `artifacts/synthetic/raw/*.jsonl` (31 jsonl files, 9,036 rows), merge of survivors into `artifacts/corpus/train_final.jsonl`.
**Scripts:** `data_pipeline/qa_synthetic.py`, `data_pipeline/merge_corpus.py`. **Stats:** `artifacts/synthetic/qa_stats.json`, `artifacts/corpus/train_final_merge_summary.json`.

## 1. Headline

- Rows in: **9036** → survivors: **6684** (74.0%)
- Outcome leaks dropped: **1** (`syn-cs_d-0290`, stem `died` — the known cs_d leak)
- AI-ism drops: **0** (none of the 6 banned phrases present)
- Schema drops: **0** (all 9,036 rows valid against the 10-field schema + enums)
- Within-file 8-gram dup drops: **122** (cs_d 71, sml_b 47, cs_c 3, ei_d 1 — first occurrences kept)
- Cross-file Jaccard≥0.5 drops: **0**; vs-corpus Jaccard≥0.5 drops: **0** (79,109 real rows indexed, 263 boilerplate shingles capped at df>25)
- LLM-ism gate: **FAIL** — 10-fold AUC **1.0000** before and **1.0000** after the one permitted mitigation (dropped most-templated quartile, 2229 rows). Shipped with disclosure per 20-min stop rule.
- train_final.jsonl: **68062** rows = 61378 real + 6684 synthetic; actual prevalence **0.6356**

## 2. Per-file QA table

| file | in | leak | ai-ism | dup(in-file) | J(cross) | J(corpus) | llm-ism drop | survivors |
|---|---|---|---|---|---|---|---|---|
| cs_a.jsonl | 290 | 0 | 0 | 0 | 0 | 0 | 179 | **111** |
| cs_b.jsonl | 290 | 0 | 0 | 0 | 0 | 0 | 109 | **181** |
| cs_c.jsonl | 290 | 0 | 0 | 3 | 0 | 0 | 70 | **217** |
| cs_d.jsonl | 290 | 1 | 0 | 71 | 0 | 0 | 103 | **115** |
| cs_e.jsonl | 290 | 0 | 0 | 0 | 0 | 0 | 50 | **240** |
| cs_f.jsonl | 290 | 0 | 0 | 0 | 0 | 0 | 97 | **193** |
| drv_a.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 77 | **223** |
| drv_b.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 58 | **242** |
| drv_c.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 38 | **262** |
| ei_a.jsonl | 270 | 0 | 0 | 0 | 0 | 0 | 28 | **242** |
| ei_b.jsonl | 270 | 0 | 0 | 0 | 0 | 0 | 33 | **237** |
| ei_c.jsonl | 270 | 0 | 0 | 0 | 0 | 0 | 20 | **250** |
| ei_d.jsonl | 270 | 0 | 0 | 1 | 0 | 0 | 0 | **269** |
| ei_e.jsonl | 270 | 0 | 0 | 0 | 0 | 0 | 22 | **248** |
| hw_a.jsonl | 293 | 0 | 0 | 0 | 0 | 0 | 183 | **110** |
| hw_b.jsonl | 293 | 0 | 0 | 0 | 0 | 0 | 80 | **213** |
| lof_a.jsonl | 240 | 0 | 0 | 0 | 0 | 0 | 28 | **212** |
| neg_a.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 22 | **278** |
| neg_b.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 170 | **130** |
| neg_c.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 4 | **296** |
| neg_d.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 105 | **195** |
| neg_e.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 24 | **276** |
| neg_f.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 133 | **167** |
| neg_g.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 147 | **153** |
| neg_h.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 113 | **187** |
| neg_i.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 146 | **154** |
| neg_j.jsonl | 300 | 0 | 0 | 0 | 0 | 0 | 3 | **297** |
| sml_a.jsonl | 340 | 0 | 0 | 0 | 0 | 0 | 45 | **295** |
| sml_b.jsonl | 340 | 0 | 0 | 47 | 0 | 0 | 38 | **255** |
| wah_a.jsonl | 270 | 0 | 0 | 0 | 0 | 0 | 34 | **236** |
| wah_b.jsonl | 270 | 0 | 0 | 0 | 0 | 0 | 70 | **200** |
| **TOTAL** | **9036** | **1** | **0** | **122** | **0** | **0** | **2229** | **6684** |

Note: brief expected ~76 within-file dups in cs_d; measured 71 (plus 3 cs_c, 1 ei_d, 47 sml_b = 122 total). Screen semantics: any shared 8-gram with an earlier kept row in the same file → drop the later row, keep first occurrence.

## 3. LLM-ism detector (spec gate: 10-fold AUC < 0.9)

- Setup: TF-IDF (1–2 gram, 5,000 features) + LogReg, 10-fold stratified CV. Real pool: masked OSHA train sample n=8,382, length-decile-matched to the 8,913 synthetic rows.
- **Initial AUC: 1.0000 — GATE FAIL.**
- Mitigation (the ONE permitted): drop most templated quartile (CV P(synthetic) >= q75) — 2229 rows dropped → n_synth=6684.
- **Post-mitigation AUC: 1.0000 — STILL FAIL. Stopped per 20-min budget; ship with disclosure.**

Top-20 discriminating features (synthetic direction), initial:

`at (+4.952)`, `now (+3.313)`, `hrs (+2.625)`, `during (+2.572)`, `ggs (+2.466)`, `near (+2.429)`, `before (+2.357)`, `one (+2.217)`, `for (+2.199)`, `no (+2.015)`, `found (+2.004)`, `with (+1.992)`, `fitter (+1.945)`, `2024 (+1.944)`, `2025 (+1.941)`, `only (+1.786)`, `around (+1.689)`, `not (+1.666)`, `is (+1.666)`, `kept (+1.637)`

Top-20 after mitigation:

`at (+4.542)`, `now (+3.148)`, `during (+2.454)`, `hrs (+2.444)`, `ggs (+2.372)`, `near (+2.358)`, `before (+2.261)`, `one (+2.116)`, `for (+2.039)`, `no (+1.934)`, `with (+1.908)`, `2024 (+1.873)`, `2025 (+1.872)`, `found (+1.848)`, `fitter (+1.841)`, `only (+1.710)`, `is (+1.639)`, `kept (+1.607)`, `not (+1.574)`, `duliajan (+1.558)`

**Interpretation:** the tells are *register/domain*, not subtle LLM-isms: OIL installation tokens (`ggs`, `duliajan`), contractor-register function words and narrative openers (`at`, `during`, `now`, `hrs`, `one`, `around`), date numerals (`2024`, `2025`), and trade nouns (`fitter`). A TF-IDF detector separates OIL-register contractor prose from US OSHA inspector narratives trivially — the two corpora differ by construction. Closing this gap requires real OIL-register negatives (not available Day-1) or register-matched generation against an OIL real corpus, not more filtering. **Disclosure: the synthetic stratum is detector-separable from OSHA text at AUC≈1.0; detector-weak ≠ indistinguishable (spec caveat applies doubly). Mitigation to a register-matched ablation is a training-time control, not a claim of realism.**

## 4. Vocab coverage (gate: each of 24 OIL terms in ≥50 survivor rows)

| term | rows | gate | status |
|---|---|---|---|
| GGS | 1548 | 50 | ok |
| GCS | 466 | 50 | ok |
| EPS | 861 | 50 | ok |
| CTF | 210 | 50 | ok |
| wellhead/manifold | 261 | 50 | ok |
| christmas tree | 173 | 50 | ok |
| flowline | 245 | 50 | ok |
| workover rig | 172 | 50 | ok |
| BOP | 25 | 50 | **MISS** |
| WOC (waiting on cement) | 12 | 50 | **MISS** |
| mud pump/mud tank | 114 | 50 | ok |
| SRP/horse head | 108 | 50 | ok |
| H2S/sour gas | 69 | 50 | ok |
| LEL/gas detector | 135 | 50 | ok |
| kick | 5 | 50 | **MISS** |
| POOH/RIH | 73 | 50 | ok |
| flare pit | 52 | 50 | ok |
| hot work/cold work permit | 69 | 50 | ok |
| PSV | 68 | 50 | ok |
| QRT | 121 | 50 | ok |
| Duliajan | 822 | 50 | ok |
| monsoon waterlogging | 79 | 50 | ok |
| contractor (M/s ...) | 587 | 50 | ok |
| wild elephant movement | 77 | 50 | ok |

**Misses (3/24):** BOP = 25, WOC (waiting on cement) = 12, kick = 5. All three are well-control/process-safety register — the generators under-produced Baghjan-class vocabulary (365 survivor rows carry the `well_control` flag, but the specific vocabulary is thin). Recommend a small targeted top-up generation for these 3 terms (or accept as disclosed limitation: the engine is personal-safety LSR scope per HSE reviewer SEV1 boundary).

## 5. Final corpus (Task 2)

- `artifacts/corpus/train_final.jsonl`: **68062** rows = 61378 train + 6684 QA-passing synthetic (TRAIN ONLY; val/test untouched, 0 synthetic ids — asserted).
- Schema: exactly 15 keys on every row (asserted uniform). Synthetic rows gained `masked_text` (masker re-run, **0 changes asserted** — outcome-leak filter upstream guarantees), `employer/event_date/naics/oiics_event = null`, `primary_rule` via spec tie-order, `source = synthetic_positive|synthetic_negative`. `register` and `jaccard_max` are kept in `clean/*.jsonl`, not carried into the merged corpus.
- Shuffle: seed 42.

### Actual vs frozen mix ratios

| source | frozen | actual |
|---|---|---|
| asrs_negative | 0.15 | 0.1768 |
| osha_low_energy_negative | 0.15 | 0.1562 |
| osha_positive | 0.55 | 0.5688 |
| synthetic_negative | 0.05 | 0.0313 |
| synthetic_positive | 0.1 | 0.0669 |

- Actual train prevalence: **0.6356** (positives = osha_positive + synthetic_positive).
- Synthetic share of train: 0.0982 (0.067 pos / 0.031 neg — frozen targets 0.10/0.05, now unreachable: survivors are only 74% of the 9,000 assumption and the LLM-ism mitigation removed 2,229 more).

### Per-rule synthetic counts vs frozen quotas (primary rule, positives)

| rule | quota (9k) | actual (primary) | actual (containment) | shortfall |
|---|---|---|---|---|
| line_of_fire | 231 | 212 | 358 | +8.2% |
| working_at_height | 535 | 387 | 445 | +27.7% **>10%** |
| hot_work | 586 | 330 | 333 | +43.7% **>10%** |
| safe_mechanical_lifting | 677 | 591 | 621 | +12.7% **>10%** |
| driving | 900 | 727 | 808 | +19.2% **>10%** |
| energy_isolation | 1351 | 1247 | 1319 | +7.7% |
| confined_space | 1720 | 1057 | 1057 | +38.5% **>10%** |
| _negatives | 3000 | 2133 | 2133 | +28.9% **>10%** |

Quota table sums: primary counts 4551 == tagged positives 4551 (asserted). Untagged positives: 0; tagged negatives: 46 (46 neg rows carry rule tags — schema-valid, noted).

**Quota shortfalls >10%:** working_at_height (−27.7%), hot_work (−43.7%), safe_mechanical_lifting (−12.7%), driving (−19.2%), confined_space (−38.5%), negatives (−28.9%). Root cause: LLM-ism mitigation removed 2,229 rows concentrated in the most-templated files (hw_a lost 183/293, neg_b 170/300, cs_a 179/290). energy_isolation (−7.7%) and line_of_fire (−8.2%) are within tolerance. The two spec-critical weak-support rules (confined_space, energy_isolation) land at 1,057 and 1,247 primary positives — still ≥9.5× the ≥50-gold-positive macro-F1 floor.

## 6. Deviations logged (for orchestrator adjudication)

1. **train_mix_ratios vs all-survivors.** Frozen ratios (55/15/15/10/5) assumed 9,000 synthetic; actual synthetic = 6,684 → actual ratios {'asrs_negative': 0.1768, 'osha_low_energy_negative': 0.1562, 'osha_positive': 0.5688, 'synthetic_negative': 0.0313, 'synthetic_positive': 0.0669}. Proceeded with all-survivors per Day-1 instruction; no down-sampling applied.
2. **target_train_prevalence: 0.40 is internally inconsistent with the frozen ratios** — osha_positive 0.55 + synthetic_positive 0.10 imply prevalence ≈ 0.65, and the actual merged prevalence is 0.6356. Flagged; needs spec adjudication (either the target line or the ratios are wrong).
3. **LLM-ism gate failed and stays failed after the single permitted mitigation** — shipped with disclosure (§3). The 2,229-row mitigation drop is itself a deviation from 'drop the most templated quartile' being optional: it was applied and did not close the gap.
4. **Vocab coverage gate missed for 3/24 terms** (BOP 25, WOC 12, kick 5 vs ≥50) — well-control register under-generated; recommend targeted top-up or disclosed limitation.
5. **synthetic_target_rows 9,000 not met** (6,684 survivors, −25.7%): 1 leak, 122 within-file dups, 2,229 LLM-ism mitigation drops.

## 7. Self-checks (all PASS)

- `train_final.jsonl` row count == `train.jsonl` + survivors (61,378 + 6,684 = 68,062) ✓
- No `syn-` id in val.jsonl / test.jsonl ✓
- Zero outcome-stem matches in clean synthetic (re-scanned post-hoc: 0) ✓
- Quota table primary counts sum == tagged positive survivors (4,551) ✓
- Per-file drop accounting reconciles to rows_in for all 33 files (asserted in QA) ✓
- 15-key schema uniform across all 68,062 train_final rows ✓; masker on synthetic text: 0 changes ✓; no duplicate synthetic ids ✓

## 8. Register-matched re-test (addendum, Day-1 follow-up)

The §3 critique was that the gate conflates *OIL contractor register vs US OSHA inspector register* with *synthetic vs real*. Re-run register-matched: real pool restricted to **OSHA oil-gas NAICS (211/213) narratives from `train.jsonl` only** (`masked_text`), synthetic pool = the 6,684 clean survivors. Same protocol: TF-IDF (1–2 gram, 5,000 features) + LogReg, stratified 10-fold CV, seed 42.

- **Pool discrepancy:** spec/protocol quote 2,756 oil-gas NAICS (211/213) narratives — that count was measured on the full 106k OSHA dataset pre-split. The temporal train split (`train.jsonl`) contains **1,318** (211: 97, 213: 1,221); the remainder sits in the 2024–25 test split. Only `train.jsonl` was used, per instruction.
- **PRIMARY (balanced + length-matched):** 1,318 real vs 1,019 synthetic (synthetic length distribution does not cover the real decile tails — largest feasible match), **AUC = 1.0000 — STILL ≥ 0.9, gate remains FAIL.**
- **SENSITIVITY (unbalanced):** 1,318 real vs all 6,684 synthetic, **AUC = 1.0000.**

**Top-20 synthetic-direction features, verbatim (balanced run):**

`at (+2.882)`, `now (+1.768)`, `near (+1.593)`, `ggs (+1.508)`, `for (+1.481)`, `during (+1.469)`, `found (+1.446)`, `with (+1.442)`, `one (+1.302)`, `before (+1.272)`, `hrs (+1.191)`, `no (+1.149)`, `eps (+1.032)`, `not (+1.020)`, `kept (+1.016)`, `2025 (+1.014)`, `checked (+0.952)`, `all (+0.949)`, `done (+0.942)`, `at ggs (+0.931)`

**Top-20 (unbalanced run):**

`at (+2.424)`, `for (+1.506)`, `with (+1.454)`, `now (+1.389)`, `during (+1.329)`, `hrs (+1.250)`, `near (+1.226)`, `ggs (+1.223)`, `found (+1.098)`, `before (+1.086)`, `no (+1.052)`, `one (+1.041)`, `2025 (+1.030)`, `not (+1.025)`, `2024 (+1.006)`, `around (+0.955)`, `is (+0.911)`, `only (+0.857)`, `eps (+0.847)`, `fitter (+0.829)`

**Verdict:** register-matching does not close the gap — the detector separates synthetic from real oil-gas OSHA text perfectly even when the real pool is same-industry. The surviving tells are *stylistic*, not topical:

1. **Narrative openers / sentence-initial placement** — `at` (esp. the 2-gram `at ggs`), `now`, `near`, `during`, `before`, `around`, `one`: synthetic rows habitually open "At GGS-2 ... around 02:40 hrs ..."; OSHA narratives open "An employee was ...".
2. **Time/register markers** — `hrs`, `2024`, `2025` (DD.MM.YYYY date numerals; OSHA text rarely carries explicit years).
3. **Staccato report-closure verbs** — `found`, `kept`, `checked`, `done`, `not`, `no`, `all`: short clipped status sentences ("Entry made in logbook. Training done.") vs OSHA's single flowing third-person narrative.
4. **Installation token saturation** — `ggs`, `eps`: real US oil-gas narratives never name Indian installation types; this axis is partly inherent to the domain transfer and cannot be fully closed without diluting the OIL vocabulary the corpus exists to teach.

**Guidance for top-up generators (to dodge these tells):** ban sentence-initial "At/Now/Near/During/Before/Around/One" in >10% of rows; ban the "At <site> ... <time> hrs" opener pattern; forbid explicit calendar dates with years; replace clipped closure sentences ("Training done.", "Entry made.", "Kept under observation.") with varied embedded clauses; distribute site types (reduce GGS/EPS frequency toward the 24-term distribution: more flowline/CTF/wellhead/SRP contexts); vary sentence-initial subjects (person-first, equipment-first, condition-first).

**Disclosure (unchanged in substance):** the synthetic corpus remains detector-separable from real text at AUC ≈ 1.0 under both framings (US-OSHA-general and oil-gas-register-matched). Ship with disclosure; treat synthetic as register/coverage augmentation for thin rules, never as realism. Mitigation path is generator-side style diversification (above), not further row filtering — the templated-quartile cut already failed to move the AUC.
