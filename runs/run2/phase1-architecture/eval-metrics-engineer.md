# Phase 1 — Evaluation & Metrics Engineer (PS 26165)

Role: attack the numbers we claim on stage. All arithmetic re-run on this machine (python3, Wilson score interval z=1.96, exact binomial McNemar power). VERIFIED = measured here; INFERRED = reasoned.

## 1. Findings (with numbers)

**1a. The handoff's published CIs are WRONG (VERIFIED).** §B.5 claims "300@20% prevalence → recall CI [0.80,0.95]; 1000 → [0.85,0.94]". Recall CIs depend on the count of *positives*, not total n. Recomputed Wilson 95% at recall=0.85, 20% prevalence:

| gold n | positives | recall CI (correct) | handoff claim |
|---|---|---|---|
| 300 | 60 | **[0.739, 0.919]** (±9.0pp) | [0.80, 0.95] ✗ |
| 500 | 100 | **[0.767, 0.907]** (±7.0pp) | — |
| 1000 | 200 | **[0.794, 0.893]** (±4.9pp) | [0.85, 0.94] ✗ |

Both handoff intervals are too narrow and mis-centered. If a judge recomputes, our money slide dies. **Minimum n for a defensible claim (VERIFIED):** ±5pp at recall 0.85 needs **196 positives** → n=980 random @20% prevalence, **or n≈500 enriched to 40% SIF-positive**. Precision side: 0.80 precision on ~125 flagged of 500 → CI ±7pp.

**1b. Labeling-rate arithmetic (VERIFIED arithmetic; rate INFERRED).** 300–500 @30s = 2.5–4.2h single-pass — handoff math checks. But median narrative is 31 words + binary judgment + 7-rule tag: budget **45s**. Real cost of a *credible* protocol (double-label for κ): 500 double = 1000 judgments = **12.5 person-hours** (3.1h each ×4). The "~4 person-hours" line buys only single-pass, **zero κ** — and κ is on the money slide. Span annotation adds 30–60s/report → cannot ride the main pass.

**1c. Per-rule ≥50-positives rule (VERIFIED).** Using measured OSHA proxy prevalences (phase0 iogp-coverage.md), n=500 random: Line of Fire 198 ✓, Working at Height 80 ✓, Driving 55 (P(≥50)=0.80, risky) ✓, **Hot Work 18 ✗, Lifting 15.5 ✗, Energy Isolation 6 ✗, Confined Space 1.5 ✗**. Macro-F1 as specified averages **only 3 rules** — judges will ask why a "9-rule" system reports 3.

**1d. McNemar power (VERIFIED, exact binomial).** p<0.05 needs discordant pairs: b+c=25 @80/20 split → power 0.89; b+c=15 → 0.65. On 100 gold positives with a 20pp recall gap vs regex, expect b+c≈25–30 → adequate but not safe; vs zero-shot LLM (expected small gap) the gold is **underpowered**.

**1e. Zero-shot LLM baseline cost (INFERRED from measured tok/s, machine-ollama.md).** qwen3:8b Q4_K_M, /api/chat + `/no_think` (C10 mandatory), JSON schema, ~150-tok prompt + ~60-tok output: clamped (current 0.85GHz, ~4 tok/s gen) ≈ 25–30s/report → **500 ≈ 3.5–4.2h**; unclamped (historical 147/23 tok/s) ≈ **35–45 min**. Feasible; run overnight Day 2→3. Do not extend to >1k rows unless unclamped.

## 2. Risks

- **SEV2-1:** Wrong CIs on the money slide ([0.80,0.95] etc.) — hostile Q&A recomputes in 30s; credibility cascade into every other claim.
- **SEV2-2:** Gold budget as planned (~4 person-hours) yields no κ, no adjudication — the anti-circularity kill-question (A.5.2) loses its teeth.
- **SEV2-3:** Macro-F1 computable on only 3/7 rules at n=500 random; EI/CS have near-zero support.
- **SEV2-4:** "Span exact-match ≥95%" is undefined and likely unattainable: human–human exact span agreement is typically 60–80% (INFERRED); a 95% bar against a single human's span is setting ourselves up to fail our own acceptance bar (§E).
- **SEV3-1:** ECE on ~100 gold positives is binning-noise; meaningless as a headline.
- **SEV3-2:** McNemar vs zero-shot LLM underpowered on gold alone.

## 3. Recommendations (per architecture element)

- **Gold CI numbers — REJECT as written.** Use 1a table. Headline: "recall 0.85 [0.77, 0.91], n=500 gold (100 positives)".
- **Gold protocol — MODIFY.** n=700 = **500 random** (unbiased precision + headline recall) + **200 rule-stratified enrichment** (quota ~50/rule for LoF/WaH/Driving/HotWork/Lifting; per-rule F1 only, stratification disclosed). Labeling: full double-label on the random 500, single-label enrichment; disagreements adjudicated by a 3rd labeler citing the spec. Budget: ~1200 judgments ≈ 12–15 person-hours (2.5–3.75h each ×4). Fallback if time squeezes: 500 single + 150 double audit subset for κ (5.5–8 person-hours) — never zero overlap.
- **Label spec (freeze BEFORE labeling) — ADOPT with contents:** (i) construct = "exposure where one more barrier failure could plausibly be fatal" (triage, not prediction); (ii) labelers see **outcome-redacted narrative + EventTitle only** (NatureTitle/part-of-body hidden → kills hindsight bias AND matches the model's masked input — apples-to-apples vs circularity); (iii) 7 rule definitions + 2 worked examples each, multi-rule allowed; (iv) negation/drill/exercise handling rules; (v) borderline policy ("judge the mechanism, not the outcome; uncertain → non-SIF"); (vi) 20-report calibration pilot → spec v1.0 frozen → labeling starts. κ: pairwise Cohen on double-labels + **Fleiss' κ on a 20% quad-labeled subset**, bootstrap SE.
- **Operating point — ADOPT with protocol.** Threshold = min score with precision ≥0.80 on the **dev split (derived labels)**, frozen, applied once to gold. Report full PR curve behind the single point; gold precision from the random stratum only.
- **Baselines — MODIFY.** Same splits for all four systems; paired McNemar per item; **Holm correction across 3 comparisons**; report Δrecall with CI, not bare p. Run McNemar on both gold (unbiased) and the ≥5k derived-label temporal test set (power; disclose proxy labels). Zero-shot = local qwen3:8b, scheduled overnight.
- **Macro-F1 rule filter — MODIFY.** Report per-rule F1 over the 5 enrichment-supported rules; declare EI/CS "insufficient gold support" alongside PTW/Bypass "out of scope" — same honesty pattern as §B.1.
- **Calibration — ADOPT with fix.** Temperature on dev split only. ECE + reliability diagram on the large derived-label test; gold gets a 4-bin diagram, no ECE number.
- **Span ≥95% — MODIFY.** Redefine acceptance: (a) exact-substring validity = 100% (structural); (b) mean token-F1 vs adjudicated human spans ≥0.80 on a **100-report span subset** (2 labelers + adjudication, +~1.5 person-hours); (c) publish human–human agreement as the ceiling. If (b) fails, drop the numeric span claim, keep highlights unquantified.
- **Outcome-validation experiment — ADOPT, time-boxed 2h.** AUC of SIF-score vs Amputation>0 within fixed EventTitle strata + redaction ablation on the derived-label test set (ONNX inference ~25 min for 50k rows). Cheap, and it is the direct rebuttal to the outcome-leakage trap (B.2.2). State the restricted-range caveat on the slide.

## 4. Verdict

The eval *architecture* (blind gold, dev-frozen threshold, paired tests, baselines table) is sound; the eval *arithmetic* is not. Every published CI is wrong in the optimistic direction, the labeling budget buys half the protocol the money slide needs, the rules metric collapses to 3 classes without stratification, and the span bar is self-sabotage as defined. All fixes fit inside the 3-day plan and cost only labeling hours we already have. Fix the numbers before they freeze into slides.

<<SCORES {"ps":"26165","role":"eval-metrics-engineer","go_no_go":6,"severity":0,"feasibility":8,"data_risk":2}>>
