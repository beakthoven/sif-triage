# Phase 1 — Methodology Skeptic / Scientific Integrity Prosecutor

Role: methodology-skeptic. Date: 2026-09-08. VERIFIED = measured by me on this machine (pandas, `data/January2015toNovember2025.csv`); INFERRED marked.

## 1. Findings (numbers first)

- **VERIFIED: temporal held-out pool = 17,746 rows (2024–25)**; oil-gas NAICS (211/213) in that pool = **364 rows** (2,756 total). A real-only, closest-to-OIL-genre gold stratum is feasible but capped at ~364.
- **VERIFIED: high-energy OIICS string-prefix rate drops 55.4% (all years) → 30.7% (2024–25)** — the deterministic label map degrades exactly in the eval years (OIICS v1→v2). Training-label prevalence ≠ gold-pool prevalence; do not extrapolate metrics across the break.
- **VERIFIED (redaction-ablation confound):** within fixed EventTitle strata, P(Amputation>0) = 0.73 ("caught in running equipment"), 0.76 ("compressed/pinched"), 0.82 ("struck against moving machinery"), vs 0.007–0.013 (falls). Mechanism text is a near-deterministic proxy for outcome severity. Masking outcome *words* removes lexical signal, not statistical signal.
- **VERIFIED (CI widths, Wilson, observed recall 0.88):** 300 gold @20% prevalence → 60 positives, CI width 0.16; 500 @50% → width 0.08; a 300-item real-only stratum @40% → 120 positives, width 0.12. Per-stratum headlines are affordable only at n≥500 with enriched prevalence.
- **INFERRED (gold-as-ground-truth):** blind human labels of SIF-*potential* on text are inter-rater agreement with a rubric, not observed fatal outcomes. "Gold" measures construct-by-consensus. The sentence is defensible only with "human-adjudicated under a pre-registered rubric" attached and κ reported.

## 2. Risks

- **SEV1-1 — Redaction-ablation overclaim.** §B.5's "score holds → mechanism, not outcome, drives it" is invalid: mechanism and outcome are confounded in realized-injury data (numbers above), and the corpus is 100% post-injury (restricted range — no exposure survived unscathed). An OIL HSE expert kills this in one question.
- **SEV1-2 — Uncontrolled contamination graph.** Generator LLM, zero-shot baseline LLM, label-spec drafting, and synthetic gold items are not provider-separated anywhere in §B–§D. If one LLM family shapes synthetic training text, the baseline comparison, and the labeling rubric, "fine-tune ≈ zero-shot" and recall-on-gold partly measure self-agreement.
- **SEV2-1 — "Deterministic high-energy-mechanism detection"** conflates deterministic *label derivation* with learned *detection*, and the construct is P(text|mechanism, severe outcome) — "looks like past injury reports" is a fair description unless the 2-sentence defense (§3) is on the slide.
- **SEV2-2 — Synthetic items in gold.** If gold contains LLM-generated items and the headline metric pools them, recall is partly measured against the generator's own SIF concept.
- **SEV2-3 — κ undefined.** Model-vs-human κ is not validity; human-vs-human κ on a double-labeled subset is the only defensible reading.
- **SEV3-1 — Label-map degradation in eval years** (55.4%→30.7%) unaddressed in gold sampling plan.

## 3. Recommendations (per architecture element)

- **recall@precision-0.80 on blind gold — MODIFY.** Gold = 500: ~300 OSHA 2024–25 held-out (include up to ~150 of the 364 oil-gas NAICS rows), ~100 ASRS, ~100 synthetic OIL-register. Provenance recorded, hidden from labelers. Headline metric on the real-only strata; synthetic stratum reported separately, never pooled. Prevalence enriched to ≥40%.
- **Metric-slide sentences — MODIFY (the line):** Defensible: "On 400 real, held-out injury/near-miss narratives adjudicated blind by N labelers under a pre-registered rubric (κ=…), the system recalls R of human-flagged SIF-potential cases at precision ≥0.80 [Wilson CI]." Overclaim (never): "detects SIF potential with R recall." Defensible: "Two labelers agreed at κ=…±SE on a 150-item double-labeled subset." Overclaim: "agrees with human experts at κ." Defensible: "matches a zero-shot cloud LLM (vendor B) within 1.5 F1 at ~1/1000th cost, offline." Overclaim: "as good as an LLM." Redaction: see below.
- **Redaction ablation — MODIFY claim, keep experiment.** Strongest honest version: "Ranking is stable when explicit outcome vocabulary is removed, so the classifier does not rely on outcome words themselves; because mechanism descriptions correlate with severity in realized-injury data (P(amputation) 0.01–0.82 across mechanism strata), we cannot exclude reliance on mechanism-as-outcome-proxy, and the test covers only post-injury texts."
- **Construct validity — MODIFY with 2-sentence defense:** "SIF-precursor literature (Martin & Black 2015; EEI) defines potential by high-energy hazard exposure, independent of outcome. We operationalize exposure via mechanisms that federal human coders associated with hospitalization/amputation in 106k realized records — a documented proxy, not outcome prediction." Residual weakness (say it first): selection is conditioned on severe outcomes; the model learns what high-energy exposure looks like *after someone was hurt*, and only the ASRS near-miss stratum partially tests the unwounded-exposure case.
- **Contamination hygiene — ADOPT as mandatory protocol:** generator LLM (vendor A) ≠ zero-shot baseline (vendor B) ≠ any LLM used for span pre-annotation; label spec authored by humans citing IOGP/OISD rule text only, no LLM-drafted examples; labelers never see model output, provenance, or rationales; publish the contamination graph in README.
- **Baseline table, temporal+employer splits, outcome-masking, PTW/Bypass declared out-of-scope — ADOPT unchanged.**

## 4. Honest-claims paragraph (README/deck, verbatim)

"This system is a triage tool: it flags reports describing high-energy hazard mechanisms and tags them to IOGP Life-Saving Rules, so human reviewers see the highest-exposure reports first. It was trained on 106k U.S. federal post-injury narratives and aviation near-misses — public proxy data, because no OIL incident text exists outside OIL. On a blind, human-adjudicated set of held-out real reports, it recalls [R, CI] of human-flagged SIF-potential cases at precision ≥0.80, with inter-labeler agreement κ=[…]. It does not predict injuries or fatalities, and two Life-Saving Rules (Permit to Work, Bypassing Safety Controls) are declared out of scope because they are invisible in narrative text. Every override in the review queue becomes a human-verified label for the next iteration."

## Verdict

Architecture is buildable; the *claims layer* is not. Fix SEV1-1/SEV1-2 before the deck is written — both are wording/protocol fixes, zero new engineering.
