# Day-1 Data Pipeline Report — Stream D: Real Corpus (OSHA + ASRS)

Date: 2026-09-08 · Owner: data-pipeline agent (Stream D) · Builder: `data_pipeline/build_corpus.py` (stdlib+pandas+numpy; imports `oiics_maps.py`/`masking.py` unmodified) · Seed: 42 everywhere · Runtime: ~4 min end-to-end.

Artifacts emitted:
- `artifacts/corpus/train.jsonl` (61,378) · `val.jsonl` (6,820) · `test.jsonl` (17,731)
- `artifacts/corpus/splits.json` (leakage audit) · `artifacts/corpus/build_log.txt`
- `artifacts/asrs/asrs-aviation-reports-train.jsonl` (270 MB source, HF `elihoole/asrs-aviation-reports`, ungated)

Schema per row (validated by re-reading all three files): `{id, text, masked_text, sif_label, rules, primary_rule, well_control, site:null, activity:null, barrier:null, source, employer, event_date, naics, oiics_event}`. Synthetic slots NOT included (merge comes later).

## 1. Measured vs spec expectations

| item | spec expectation | measured | verdict |
|---|---|---|---|
| OSHA rows loaded | 105,996 | 105,996 | exact |
| exact-dedup excess (pre-split) | "~66 (65 train, 1 test, 2 cross)" | 68 = 65 within-train + 1 within-test + 2 cross-boundary | consistent (the 2 cross pairs drop the v2 copy) |
| train-era / test-era after dedup | 88,250 / 17,746 pre-dedup | 88,185 / 17,743 | dedup delta only |
| low-energy pool (v1 42x/7xx, v2 43x/7xx) | 14,961 | 14,961 pre-dedup (12,209 v1 + 2,752 v2); 12,202 v1 after dedup | exact |
| amputated excluded from pool | 219 | 219 total, 167 in v1 (used), 12,035 usable v1 negatives | exact |
| SIF positives (B_middle, frozen) | v1 65.52% / v2 64.21% | v1 57,804 pos; **test prevalence 64.23%** | matches |
| test rule distribution | spec `measured.rule_distribution_multi_hot.v2` | LoF 47.43 / WaH 17.64 / driving 12.04 / EI 2.78 / HW 3.77 / SML 4.30 / CS 0.67 | matches v2 column to ±0.02pp |
| boundary screen J≥0.5 drop | 0.13% (1,500-row sample) | **12 / 17,743 = 0.068%** dropped | consistent |
| boundary screen J≥0.3 report | 0.53% (sample) | 62 / 17,743 = 0.35% flagged | consistent |
| masked_text outcome-leak | 0 residual stems | 0 rows with residual stem (all 85,929 rows re-checked) | pass |
| train/val employer disjointness | group-disjoint | 0 shared normalized employers | pass |
| test employer overlap with train | ~42% (F5, lower bound) | 35.29% (normalization: lowercase + strip punctuation) | accepted residual, disclosed in splits.json |

## 2. Splits

- **train** 61,378 = osha_positive 38,711 + osha_low_energy_negative 10,632 + asrs_negative 12,035
- **val** 6,820 = osha_positive 5,417 + osha_low_energy_negative 1,403 (ASRS excluded — spec: `train_only_never_eval`); employer-grouped holdout, exactly 10.0% of real-train size, group-disjoint from train
- **test** 17,731 = all 2024-01-01..2025-11-30 rows after dedup (3 dropped) and boundary screen (12 dropped); natural distribution

Mix sizing: low-energy negatives are the binding pool → all 12,035 usable v1 negatives used; positives sampled 44,128 of 57,804; ASRS sampled 12,035 of 18,055 usable (ratios 0.55:0.15:0.15 of the real 85%).

## 3. Prevalence

| split | prevalence | note |
|---|---|---|
| train (real only) | **63.07%** | below the 64.7% ratio-implied value because the 10% val holdout is drawn from OSHA rows only (ASRS stays fixed) |
| val | 79.43% | OSHA-only mix 0.55:0.15 → ~78.6% expected; group-granular holdout gives 79.4% |
| test | 64.23% | natural v2 distribution |
| **projected final train** (with frozen 9,000 synthetic = 6,000 pos/3,000 neg) | **63.53%** | synthetic share of final = 12.8% |

**⚠ SPEC INCONSISTENCY FLAGGED (needs orchestrator ruling):** `negatives.train_mix_ratios` (0.55 pos / 0.15+0.15+0.05 neg / 0.10 synth-pos) arithmetically implies **65%** positive prevalence, but `target_train_prevalence: 0.40` states 40%. Both cannot hold; I obeyed the five frozen ratios (the actionable spec). Hitting 0.40 with these negative pools would require osha_positive ≈ 0.30 instead of 0.55. Recorded in `splits.json → prevalence.spec_note`. Downstream threshold tuning (precision ≥ 0.80 on val) should treat 0.40 as non-binding until ruled.

Also note: with synthetic frozen at 9,000 and real train at 61,378, the synthetic share is 12.8%, not the 15% the ratios imply — the two frozen numbers (9,000 rows vs 15% share) are mutually inconsistent at this corpus size.

## 4. Rule distribution (multi-hot, % of split)

| rule | train | val | test | spec v1 (full corpus) |
|---|---|---|---|---|
| line_of_fire | 43.35 | 54.81 | 47.43 | 48.78 |
| working_at_height | 16.75 | 20.70 | 17.64 | 17.37 |
| driving | 2.46 | 3.18 | 12.04 | 11.55 |
| energy_isolation | 2.22 | 2.64 | 2.78 | 2.32 |
| hot_work | 3.44 | 4.38 | 3.77 | 3.78 |
| safe_mechanical_lifting | 3.17 | 4.09 | 4.30 | 3.55 |
| confined_space | 0.21 | 0.13 | 0.67 | 0.29 |

Driving collapses in train (2.46% vs 11.55% corpus-wide) **by design**: driving codes (2x) are not B_middle SIF prefixes, so driving rows enter the corpus only via keyword LFs (forklift/skid-steer mentions) inside the selected pools. Test keeps the natural 12.04%. CS/EI remain thin in real data (0.21%/2.22% train) — as the spec anticipates, synthetic quotas carry them.

## 5. ASRS findings (Day-1 open item CLOSED — anomaly semantics spot-check)

Spot-check: 200 random rows (seed 42) + full-file value counts of `Events_Anomaly`.

Findings:
1. **`Events_Anomaly` is a SEMICOLON-separated LIST of anomalies per report** (e.g. `'Aircraft Equipment Problem Critical; Conflict Airborne Conflict; Ground Excursion Runway'`), each element = category + subcategory SPACE-joined. A first-element-only screen would misclassify many rows — screening must test **every** element. Implemented accordingly.
2. Category semantics (manual read of sampled narratives): procedural categories (`ATC Issue`, `Deviation*`, `Airspace Violation`, `Deviation / Discrepancy - Procedural*`, `Aircraft Equipment Problem*`) are operational/administrative reports — good class-0 register material. Energy-release categories are the `Conflict*` (NMAC/airborne/ground), `Inflight Event / Encounter*` (wake vortex, CFTT/CFIT incl. GPWS pull-up narratives, turbulence injuries, loss of control, VFR-into-IMC), `Ground Event / Encounter*` (ground strikes, gear-up, jet blast, FOD), `Ground Excursion/Incursion*`, plus onboard `Smoke / Fire / Fumes` (thermal, hot-work class) and `Illness / Injury` (person-harm outcome rows).
3. `Assessments.1_Primary Problem` (values: Aircraft / Human Factors / Procedure / Ambiguous / Company Policy / Environment / Chart Or Publication) carries no additional high-energy signal beyond the anomaly list — used as documentation only, not screened on.

Screen result (full train shard, 38,655 rows): **20,482 dropped (53.0%)** — Conflict 6,709 · Inflight Event/Encounter 7,242 · Ground Event/Encounter 3,487 · Smoke/Fire/Fumes 1,659 · Ground Incursion 801 · Illness/Injury 361 · Ground Excursion 223 — plus 114 short (<20-word) and 4 exact-dup narratives → **18,055 usable**, 12,035 sampled (train-only, never eval, per spec). ASRS narratives masked with `masking.py`; `id=asrs-<ACN>`, `event_date` from `Time_Date` (YYYYMM→YYYY-MM-01).

## 6. Boundary screen implementation notes

8-gram Jaccard, distinctive-shingle inverted index as sorted numpy arrays (2,363,606 postings / 2,271,528 unique shingles over 88,185 train-era narratives); shingles with df>256 would be excluded as boilerplate — **none occurred** (0 excluded). Intersection counted on indexed shingles, union on full shingle sets (slightly conservative). 1 test row had <8 tokens (unscreenable, kept). blake2b-8B shingle hashes.

## 7. Data quirks found (documented, handled)

- 5 OSHA report IDs (2015010015/16/18/20/21) are reused for 2 genuinely different incidents each (same ID, different narrative/Event). Emitted ids disambiguated deterministically: `osha-<ID>-a` / `osha-<ID>-b`.
- ASRS `Events_Anomaly` list semantics (§5.1) — first-element screening would have under-dropped by ~35pp.

## 8. Self-check (ran, PASS)

End-to-end build; JSONL re-read validation (exact 15-key schema, label ∈ {0,1}, rules ⊆ 7-rule set, no null text, no cross-split id collisions); 0 residual outcome stems in any `masked_text`; train/val normalized-employer overlap = 0; prevalence/rule tables above printed. Log: `artifacts/corpus/build_log.txt`.

## 9. Open items handed off

1. **Prevalence ruling** (§3): 0.40 target vs ratio-implied ~0.65 — orchestrator must pick; changing ratios is a spec version bump.
2. Val is OSHA-only per `train_only_never_eval` for ASRS — val prevalence (79.4%) therefore differs from both train (63.1%) and test (64.2%); threshold-tuning agent should be aware.
3. Cross-era employer overlap 35.29% (my normalization) — accepted residual per D10, disclosed in splits.json.
