# Protocol Draft — Label Spec, Component B
## Masking / Negatives / Splits / Synthetic / Gold

Status: DRAFT for H2 freeze, 2026-09-08. Implements adjudicated rulings D6, D7, D8, D10, D11 (+ D15 interface). Machine-readable mirror: `protocol_fragment.yaml` — to be merged verbatim into `label_spec.yaml` at freeze. Evidence base: `runs/run2/phase1-architecture/{data-pipeline-engineer,eval-metrics-engineer,methodology-skeptic,hse-domain-reviewer}.md`, `runs/run2/kb/KNOWLEDGE_BASE.md` §2. All corpus numbers cited here were measured on `data/January2015toNovember2025.csv` (105,996 rows).

---

## B1. Outcome-masking protocol (D6)

**Decision: token-level outcome neutralization, applied to positives AND negatives. Clause-stripping is rejected** (measured: empties 19.1% of rows; neutralization: 0% empty, median length 100% preserved).

**Algorithm** (implemented in `data_pipeline/masking.py`, stdlib-only, self-checking):

1. One case-insensitive regex, 25 stems; multi-word phrases ordered before single-word stems so the longest match wins.
2. Every match is replaced in place with the token `[OUTCOME]`. No clause, sentence, or row is ever removed.
3. Adjacent `[OUTCOME] [OUTCOME]` runs are collapsed to a single `[OUTCOME]` (readability only; whitespace otherwise untouched).
4. Applied to every OSHA narrative regardless of derived class (pos or neg), and to synthetic negatives that imitate OSHA register. Rationale (SEV2-1): 96.8% of low-energy negative rows are hospitalized — masking only positives would teach the model "outcome words = SIF".

**Frozen stem list (25):**

Phrases: `crush syndrome`, `loss of / lost … eye(s)`, `(first|second|third|1st|2nd|3rd)[-]degree burn(s)`, `intensive care (unit)`, `trauma center/centre`, `life[-]flight`.
Stems (inflection-covered): `amputat`, `fractur`, `hospital`, `kill`, `fatal`, `death(s)`, `died`, `sever(e|ely|ed|ing|s)`, `unconscious`, `unresponsive`, `resuscitat`, `paraly`, `coma`, `icu`, `airlift`, `medevac`, `surgery/surgical`, `succumb`, `injur`.

Inclusion rule: mask outcome / severity / disposition signal (what happened to the person, how bad, where they were taken); never mask mechanism signal (`struck by`, `caught in`, `fell`, `pinned`, `crushed between` all survive — verified by unit assertions).

Documented trade-offs (frozen knowingly):
- `sever…` covers severe/severely/severed but **not** "several" (explicit alternation).
- `injur` masks "injury" even in "no injury occurred" → "no [OUTCOME] occurred"; the negation survives.
- `burn` alone is NOT masked (Hot-Work mechanism signal); only degree-qualified burns are severity leaks.
- `coma`/`airlift` can rare-hit proper nouns (e.g. Comal County) — rarer than the leak they close.

**Measured self-check (5,000-row sample of the real CSV, seed 42):** 0.00% empty rows (gate: 0); 75.3% of rows have ≥1 hit (consistent with the measured 70–76% word-list-dependent leak rate); mean 1.01 tokens masked/row; median length preserved 1.000.

**Freezing note:** the leak rate is word-list sensitive (measured swing 70.4% vs 76.4% across candidate lists) — any stem change after H2 is a `label_spec` version bump and invalidates masked-variant comparisons.

**Ablation variants:** the pipeline emits both masked and unmasked variants of every train row, plus a masked copy of eval (D11 redaction ablation). Claim wording per skeptic: ranking stability under redaction = robustness evidence, NOT "mechanism not outcome" proof (P(amputation) 0.007–0.82 across fixed EventTitle strata).

---

## B2. Negatives construction

Three negative sources, each with a stated weakness:

1. **ASRS weak-label negatives** (train-only, never eval). Weak label derived from `Events_Anomaly` + `Assessments.1_Primary Problem` fields (register + counterfactual language is what we want the model to see in class 0). Mandatory pre-screen: drop any row whose `Events_Anomaly` indicates high-energy (airborne conflict etc.) before it may be called a negative — ASRS anomaly semantics spot-check is a Day-1 open item (INFERRED until then).
2. **OSHA low-energy rows, masked.** Pool: same-level falls (v1 42x / v2 43x) + overexertion (7xx) = 14,961 rows. **Exclude the 219 amputated low-energy rows** outright (4.8% of the pool — real severe injuries that would poison class 0). Remaining rows are 96.8% hospitalized → usable only through the B1 mask.
3. **Synthetic negatives** (see B4): low-energy scenarios (first-aid, same-level slip, overexertion, no-harm near-miss with counterfactual language).

**Target train-mix ratios** (per data-pipeline engineer; tunes threshold on val for precision ≥0.80):

| component | share |
|---|---|
| OSHA positives (derived labels) | 55% |
| OSHA low-energy negatives (masked, amp=0) | 15% |
| ASRS negatives (anomaly-screened) | 15% |
| Synthetic positives | 10% |
| Synthetic negatives | 5% |

→ ~40% SIF prevalence in train. Eval (B5) contains **no** weak negatives: ASRS and synthetic never enter headline metrics.

---

## B3. Split protocol (D10)

1. **Temporal hard boundary:** train ≤ 2023-12-31, test = 2024-01-01 → 2025-11-30 (17,746 rows). No exceptions.
2. **Employer-grouping within train only** (train/val split). Cross-era employer grouping is incoherent: 42.0% of test rows share an employer with train (67,879 unique employers, 4,839 in both eras; lower bound — "u.s. postal service"/"usps" variants unnormalized). Accepted residual: employer leakage across the boundary exists and is disclosed.
3. **Cross-boundary near-dup screen:** 8-gram Jaccard, distinctive-shingle index, drop/flag test rows at J ≥ 0.5 vs any train row. Measured tiny: 0.13% (2/1,500 sample) at J≥0.5, 0.53% at J≥0.3. Dedup order: exact-dedup pre-split (66 excess: 65 train, 1 test, 2 cross) → split → J≥0.5 boundary screen.
4. Leakage audit trail: normalized-employer overlap + boundary near-dup counts are written into `splits.json`.

Note (SEV): the OIICS v1→v2 code renumbering sits exactly at this boundary (label-map high-energy prefix rate 55.4% → 30.7% in eval years) — dual era-conditional maps are mandatory (D9, owned by label-spec component A); gold sampling (B5) accounts for the degraded map.

---

## B4. Synthetic OIL corpus spec (8–10k rows)

**Generation:** dev-time cloud LLM (constraint-legal: only public/synthetic text leaves the machine). Local generation rejected (~100 h at local speed). Register seeded from: 2,756 OSHA oil-gas-NAICS (211/213) narratives (outcome-masked, entity-swapped), SmartQHSE major-incident vignettes, and the OIL vocabulary list below. Generator LLM is contamination-separated per B6.

**Rule quotas — dampened inverse-frequency from measured seed counts** (F4: LoF 1,610 / WaH 300 / HW 250 / SML 187 / Driving 106 / EI 47 / CS 29). Pure inverse-frequency would put 44% of the corpus in CS; we dampen with w ∝ 1/√n_seed. Table for a 9,000-row corpus (6,000 positive / 3,000 negative, matching the 10:5 train-mix ratio); scale linearly for 8k/10k:

| rule | seed rows | weight (1/√n, normed) | positive quota |
|---|---|---|---|
| Line of Fire | 1,610 | 3.8% | 231 |
| Working at Height | 300 | 8.9% | 535 |
| Hot Work | 250 | 9.8% | 586 |
| Safe Mechanical Lifting | 187 | 11.3% | 677 |
| Driving | 106 | 15.0% | 900 |
| Energy Isolation | 47 | 22.5% | 1,351 |
| Confined Space | 29 | 28.7% | 1,720 |

Rationale: EI/CS seeds (47/29 rows) are too thin to style-anchor; synthetic must carry those rules or they are decoration. Negatives (3,000): low-energy OIL-register scenarios, no rule tag.

**OIL vocabulary list (24 terms, from HSE domain reviewer — all verified genuine Indian upstream terms):** GGS, GCS, EPS, CTF, wellhead/manifold, christmas tree, flowline, workover rig, BOP, WOC (waiting on cement), mud pump/mud tank, SRP (sucker rod pump)/horse head, H2S/sour gas, LEL/gas detector, kick, POOH/RIH, flare pit, hot work/cold work permit, PSV, QRT, Duliajan, monsoon waterlogging, contractor (M/s …), wild elephant movement near installation. Register target: contractor Hinglish-leaning incident prose (3 worked examples in `phase1-architecture/hse-domain-reviewer.md`), not polished English.

**Quality gates (every row, hard):**
1. **8-gram Jaccard dedup** vs (a) rest of synthetic corpus, (b) full OSHA corpus — reject above threshold; per-row `jaccard_max` recorded.
2. **Outcome-leak rejection:** any generated row matching an unmasked B1 outcome stem is regenerated or masked before acceptance (positives ship outcome-masked; leak check runs pre-mask to catch generator sloppiness).
3. **LLM-ism detector:** TF-IDF + LogReg, real-vs-synth 10-fold AUC; iterate generation (temperature / length / misspelling injection) until **AUC < 0.9**. Honest caveat on the slide: detector-weak ≠ indistinguishable.
4. Vocabulary coverage check: each of the 24 terms appears in ≥ N rows (N set at freeze; flag, not reject).

---

## B5. Gold protocol (D7, D8)

**Composition (n = 500):** ~300 OSHA 2024-25 held-out (include **up to 150** of the 364 available oil-gas NAICS rows — the closest-to-OIL real stratum, feasible but capped at 364) + 100 ASRS + 100 synthetic OIL-register. Provenance recorded, hidden from labelers. Prevalence enriched to ≥40% SIF-positive (recall CI width ≤0.12 on the 300-item real stratum).

**Blind labeling:**
- Labelers see **outcome-masked narrative (B1) + EventTitle only**. NatureTitle / Part-of-Body / Hospitalized / Amputation are hidden — kills hindsight bias AND matches the model's masked input (apples-to-apples vs circularity).
- Labelers never see model output, LLM output, or provenance. Label spec (construct = "exposure where one more barrier failure could plausibly be fatal"; borderline policy: judge the mechanism, not the outcome; uncertain → non-SIF) is **frozen before labeling starts**; 20-report calibration pilot precedes freeze.
- Volume (D7): **500 single-labeled + 150 double-labeled** subset, 6–8 person-hours, starting Day 2 evening. Disagreements adjudicated by a 3rd labeler citing the frozen spec.
- **Agreement: Fleiss' κ on the double-labeled subset (human-vs-human only)** — never model-vs-human as validity. Bootstrap SE. Reported as "Two labelers agreed at κ=…±SE on a 150-item double-labeled subset."

**Reporting:**
- Headline metrics on **real-only strata** (OSHA + ASRS), reported per stratum; **synthetic stratum reported separately, never pooled** (SEV2-2: pooling would partly measure the generator's own SIF concept).
- Defensible sentence (skeptic, verbatim target): "On 400 real, held-out injury/near-miss narratives adjudicated blind by N labelers under a pre-registered rubric (κ=…), the system recalls R of human-flagged SIF-potential cases at precision ≥0.80 [Wilson CI]."
- Operating point: threshold frozen on dev split (derived labels, precision ≥0.80), applied once to gold; full PR curve behind the single point; gold precision from the random stratum only.
- Gold acknowledges construct limits: blind text labels measure construct-by-consensus under a pre-registered rubric, not observed fatal outcomes; selection is conditioned on severe outcomes (restricted range) — only the ASRS stratum partially tests unwounded exposure.

---

## B6. Contamination hygiene (D11, mandatory)

1. **Generator LLM (synthetic corpus, vendor A) ≠ zero-shot baseline LLM (qwen3:8b local) ≠ any LLM that touches the label spec, span pre-annotation, or gold materials.** Provider separation is documented in the deck appendix and the contamination graph is published in the README.
2. Label spec authored by humans citing IOGP/OISD rule text only — no LLM-drafted examples.
3. Labelers never see model output, provenance, or rationales (B5).
4. κ is human-vs-human — never model-vs-human as validity.
5. Near-dup index at runtime includes the synthetic corpus, so training-row paste attacks are caught.

---

## Open items owned by this component

- ASRS `Events_Anomaly` high-energy screen semantics spot-check (Day 1, blocks B2 item 1).
- Synthetic vocabulary-coverage floor N and final corpus size 8k vs 10k (freeze with generation budget).
- Interface: SIF-positive definition freeze (D15, component A) determines the OSHA-positive 55% pool this mix draws from.
