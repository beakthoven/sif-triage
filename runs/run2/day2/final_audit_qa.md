# FINAL AUDIT — HOSTILE Q&A SIMULATOR (PS 26165, run2, Phase 3 gate)

**Lens:** OIL HSE expert judge (25y upstream) + suspicious technical evaluator.
**Date:** 2026-09-09 ~00:30 IST. **Auditor posture:** verify-with-evidence; every number below was re-read from disk or re-measured against the live stack (`:8177`, masked-v2 int8, 5,048 reports — confirmed via `/api/health`).

**Verified-on-disk anchors used throughout:** `artifacts/models/masked-v2/metrics.json` (op raw 0.746401/cal 0.658108, P 0.8000/R 0.9748/F1 0.8788, test AUC 0.8680, n=17,731) · `runs/run2/day2/ship_eval/operating_point_v2.json` + `mcnemar_6model.json` + `first_aid_results.json` + `parity_at_op.json` · `spec/label_spec.yaml` (v1.0.0) · `artifacts/gold/sample_manifest.json` (500 items, 150 double) · `artifacts/corpus/train_final_v4.jsonl` (71,065 rows) · `artifacts/demo/demo_corpus.jsonl` (13 cards) · `runs/run2/day2/ship_decision.md`, `retrain_report.md`, `demo_final_state.md`.

---

## PART 1 — The 12 hardest questions, honest answers, and traps

### Q1 (methodology, circularity): "Your training labels are derived from OIICS codes by your own rules. Your test metrics are computed against those same derived labels. Isn't the model just re-deriving your own heuristic? Where is the independent ground truth?"

**Best honest answer (verified):** "Correct — derived-label test metrics (AUC 0.8680, n=17,731) measure fidelity to a frozen, code-deterministic spec, not human truth. The independent ground truth is the blind human gold set: 500 items (`artifacts/gold/sample_manifest.json`: 300 OSHA 2024-25 incl. 150 oil-gas NAICS + 100 ASRS + 100 synthetic, seed 42, input SHAs recorded), labelers see outcome-redacted text + EventTitle only, never model output; 150-item double-labeled subset gives Fleiss' κ human-vs-human. Label spec frozen *before* labeling started; generator LLM ≠ baseline LLM ≠ anything touching gold (contamination protocol, ARCHITECTURE.md). Headline metrics will be reported on real-only strata; synthetic never pooled (D8)."

**Trap analysis:** Claiming the 0.868 test AUC is "human-validated" — it is not; it's derived-label. Claiming κ exists — as of this audit, labeling is *in progress* (`artifacts/gold/labels/labeler_a.jsonl` created 2026-09-09 00:12, 460 bytes — literally started minutes ago). Any κ number quoted on stage before the T-19h gold gate is fabricated. Also fatal: "the model agrees with the labels 97% of the time" — that's recall at the tuned op against its own spec.

### Q2 (methodology, definition): "'SIF potential' is not a defined quantity anywhere. You invented the label. Defend it."

**Best honest answer (verified):** "We measured the definitional swing before freezing: candidate definitions span 55.4%→74.7% positive rate (`spec/label_spec.yaml: sif_candidates_measured`). We froze B_middle — a strict, era-conditional, code-only high-energy mechanism set (v1 prefixes 31/32/43/44/45/51/62/63/64/65; v2 31/32/41/51/63/64/65/66) — chosen because its era gap is 1.3pp (65.52%→64.21%) vs A_strict's 4.8pp; C_broad mixed mechanisms; D_keyword wasn't code-deterministic. The definition is deterministic and re-derivable by anyone from the frozen spec. We never claim it predicts injuries — it ranks reports by review priority."

**Trap analysis:** Quoting the legacy era-blind 55.4% anchor as the definition — it collapses to 30.7% in 2024-25 (D9, label-map degradation sits inside the eval pool). Saying "industry-standard definition" — there isn't one; the honest move is *measured sensitivity + freeze*, which they have. Never improvise a definition on stage that isn't B_middle.

### Q3 (domain-data): "This is American OSHA injury data — amputations, hospitalizations, US construction register. OIL's exposure is Assam oilfields, DGMS/OISD regulation, the Mines Act. Why should anything transfer? Where is DGMS in this system?"

**Best honest answer (verified):** "Three parts. (1) Honesty: no real OIL data exists publicly — this risk is on our register and never fully closable (KB §7, data_risk 7). (2) Mitigation: 2,756 OSHA oil-gas-NAICS rows anchor realism; 9,687 synthetic OIL-register rows (measured: 13.6% of train_final_v4 — osha 49,343 / asrs 12,035 / syn 9,687) carry GGS/EPS/well-servicing register seeded from the OSHA oil-gas rows + SmartQHSE vignettes + a 24-term OIL vocabulary from an HSE reviewer (vocab gate 24/24 PASS); ASRS adds near-miss register negatives. Gold oversamples oil-gas (150 rows) and reports strata separately. (3) DGMS/OISD: vocabulary grounding via SmartQHSE hse-glossary/acronym dictionaries — but there is no DGMS-form mapping, no Mines Act schedule integration. That is out of scope for a triage prototype and we say so."

**Trap analysis:** Claiming the synthetic corpus "closes" the domain gap — their own LLM-ism detector says a TF-IDF separates synthetic from real at AUC 1.0000 (D16; see Q4). Claiming ASRS (aviation) validates oil — it's negatives/register only, disclosed. Claiming any DGMS compliance feature — none exists on disk (DGMS appears only in planning docs, flagged as "needs an explicit owner — currently nobody"). A judge who knows OISD-STD-116 or DGMS circulars will find nothing; the only survivable line is "triage layer upstream of any statutory reporting; regulation mapping is future work."

### Q4 (methodology, synthetic): "A TF-IDF with logistic regression can tell your synthetic training rows from real ones at AUC 1.0000 — your own gate FAILED and you shipped anyway. Why doesn't the model just learn 'synthetic register = SIF'?"

**Best honest answer (verified):** "The gate's purpose was to prevent *label-confounded* shortcuts, and D16 records why that specific failure mode doesn't bite: the register tells are balanced across synthetic positives AND negatives (both use GGS/hrs/'found-checked-done' closures), so register carries no signal about the SIF label. Synthetic is 13.6% of the training mixture. The gold eval has a separate synthetic stratum that is never pooled with real strata — if the model only works on synthetic, the real-only headline exposes it. v2/v4 generation applied diversity mandates. Residual risk is disclosed in the deck appendix."

**Trap analysis:** Saying "the LLM-ism gate passed" — it failed at AUC 1.0000; they shipped with disclosure (D16). Getting caught re-litigating it on stage looks like hiding. Note also: D16's text says "~10% of train" but the actual v4 mixture is 13.6% (9,687/71,065, measured from `train_final_v4.jsonl` + merge summary) — quote 13.6% or "about an eighth", not the stale 10%.

### Q5 (methodology, eval size): "Your gold set is 500 items, and your humans were still labeling it the night before the demo. At best your confidence interval is ±0.12. How is that validation?"

**Best honest answer (verified):** "The CIs are computed, not hand-waved: 500 items at ≥40% enriched prevalence gives Wilson width ≤0.12 — the handoff's original intervals were wrong and were corrected before slides (KB §6). 150 items are double-labeled for Fleiss' κ — human-vs-human agreement, never model-vs-human as validity. The gold manifest records input file SHAs and the enrichment design (oil-gas 150/364 available, 115 SIF-in-sample). Status honestly: labeling is in progress tonight; κ and gold metrics land at the T-19h gate. If gold disagrees with the derived-label numbers, gold wins and we say which moved."

**Trap analysis:** Quoting the handoff's wrong CIs ([0.80,0.95]@300 or [0.85,0.94]@1000 — explicitly marked "never quote them" in KB §6). Claiming κ > 0.X before it exists. Also, a sharp judge may check the judgment arithmetic: manifest says 500 items, `n_judgments_emitted: 690` while primary(500)+secondary(150)=650 — the extra 40 are the 20 pilot items × 2; be ready to explain the pilot mechanism rather than looking surprised by their own manifest.

### Q6 (technical, masking): "Why does your demo need outcome masking at all? If you have to delete the word 'amputated' from every report, haven't you admitted the model can't tell mechanism from outcome — and real OIL reports won't arrive pre-masked?"

**Best honest answer (verified):** "Masking is de-biasing, and it is applied at runtime too — the runtime ingests through the same frozen token-neutralization (`spec/label_spec.yaml` masking section: `[OUTCOME]` token, stems frozen, apply to positives AND negatives, measured 0% empty rows vs 19.1% empty under clause-stripping, which is why clause-strip was rejected in D6). The leakage was measured, not imagined: P(amputation>0 | 'amputat' in text) = 98.6%; 96.8% of low-energy rows are hospitalized — an unmasked model reads the outcome column off the page. Masked ≥ unmasked on held-out data (v1: AUC 0.8819 vs 0.8708, 1500-sample). What we do NOT claim: that masking proves the model uses mechanism not outcome — within fixed EventTitle strata, P(amputation) still swings 0.007–0.82, so mechanism text is a near-deterministic proxy for outcome (D11). We report the ablation as robustness evidence only."

**Trap analysis:** Overclaiming "the model learns mechanism, not outcome" — D11 explicitly weakened that claim; a technically literate judge quoting the 0.007–0.82 proxy number catches the overclaim. Also fatal: being unsure whether runtime text is masked (it is — same frozen masker).

### Q7 (technical, quantization): "Your own export gate on the training hardware was RED — int8 AUC drop 0.1305 — and your shipped artifact's manifest literally says `export_gate_pass: false`. You shipped a model that failed its own gate. Explain."

**Best honest answer (verified — this is all on disk):** "Three facts, all disclosed. (1) The int8 failure is provider-dependent: Kaggle-side ΔAUC 0.1305 RED (`retrain_report.md`), but on the deployment machine int8 full-val AUC 0.9934 vs torch 0.9969 = Δ0.0035, PASS on the D13 gate (D20; same phenomenon as v1 day-1). (2) The decision-relevant check — int8-vs-fp32 agreement *at the tuned operating point* on the single-text ship path — is 97.7–98.3%, which fails the 99.5% leg; we measured it, published it (`ship_decision.md` §2, `parity_at_op.json`), and mitigated by tuning the operating point ON the int8 single-text chain itself, so the deployed threshold is calibrated to the deployed arithmetic. (3) `SIF_MODEL_PATH`/`SIF_MODEL_QUANT=fp32` is a one-env-var fallback, documented as NOT decision-equivalent. The manifest's `export_gate_pass: false` is the Kaggle-side record; the per-file SHA table in the same manifest is what we verify against."

**Trap analysis:** Saying "the gate passed" — it didn't, and the manifest field proves it; the only answer is the provider-dependent story above. Hiding the 97.7% agreement-at-op number — it's the weakest honest number in the build and the team already published it; own it. Also: dynamic int8 quantization is batch-composition-sensitive (D27: batch-32 decisions shift, mean |Δp| 0.031) — that's why the app classifies single-text everywhere; if asked "can you batch for throughput", the answer is "fp32 yes (Δ=0.0), int8 no — measured".

### Q8 (technical, statistics): "Your val AUC is 0.997 and your test AUC is 0.868 — a thirteen-point generalization gap. And you tuned your operating point on the test set. That's test-set leakage by definition."

**Best honest answer (verified):** "The gap is diagnosed, not ignored: the 2024 OIICS renumbering degrades the label map inside the eval years (high-energy prefix rate 55.4%→30.7% at the v1→v2 break), and val saturates (prevalence 79.4% ≈ the 0.80 precision floor) — the val control reproduces exactly, so it's spec drift, not a pipeline bug (D19). The val-frozen threshold (6.85e-5) was *vacuous* on test — flag rate 1.0, precision = prevalence — we caught that ourselves and disclosed it. The operating point was re-tuned on the derived-label temporal holdout (raw 0.746401 → P 0.8000/R 0.9748) precisely because the frozen one was meaningless; the human-labeled gold set — which the threshold never touched — remains the final eval, scored through the identical single-text path (D19+D27). The PR curve and both thresholds go on the slide."

**Trap analysis:** Quoting 0.997 as the headline on stage — a judge who finds 0.868 in the appendix owns the room. Denying that op-tuning-on-test is a form of leakage — the defense is the *untouched human gold*, not denial. If gold lands materially below P 0.80, the honest line is "derived labels overstate; here's the human number" — pre-rehearse it.

### Q9 (technical, baselines): "Your own McNemar table says TF-IDF is statistically tied with your transformer — p = 0.122. Why does this need a neural network at all?"

**Best honest answer (verified, `mcnemar_6model.json`):** "On derived labels at the ship threshold: fine-tune F1 0.8788 vs TF-IDF 0.8721 — Holm-corrected McNemar p 0.122, not significant; we disclose it. The fine-tune is significantly better than the zero-shot 8B LLM (F1 0.8538, p 0.0018) at 1/1083rd the per-classification latency, and demolishes regex (F1 0.4747, p 2.2e-67). The transformer earns its keep on what TF-IDF can't do: 7-rule multi-label probabilities (macro-F1 0.965), calibrated triage scores, evidence spans, and — the real bet — human-label gold performance, where register-shifted OIL text is exactly where lexical models degrade. If gold shows TF-IDF competitive on real strata, we'll say so."

**Trap analysis:** Claiming the acceptance bar "beats TF-IDF at p<0.05" is met — it is not, on derived labels. The bar lives or dies on the gold set tonight. A judge with the McNemar table (it's in the repo) asking "is your acceptance criterion met?" must get "not yet on derived labels; gold decides" — anything else is a lie with a paper trail.

### Q10 (domain, Baghjan): "Baghjan was not a line-of-fire problem. It was a well-control and barrier-management failure — WOC cut 48h→12h, BOP pulled before cement set, no officer on site. Your nine personal-safety rules don't cover any of that. What does your system actually do about the next Baghjan?"

**Best honest answer (verified live — see Probe 1):** "We added a deterministic well-control/barrier tag precisely because the 9 rules don't cover it (SEV1-13). It is keyword/code-based, cheap, and register-independent — I can show it firing on a novel well-control narrative right now. Our framing is rehearsed and bounded: the Baghjan precursors existed and were buried in routine reports; we make them impossible to bury. We never claim the tool would have prevented it. Where the neural score is weak on novel well-control text — and it is — the deterministic tag plus the gray-state humility system is the safety net, and we disclose that."

**Trap analysis — THE LIVE-FIRE FINDING OF THIS AUDIT:** All three demo WC cards (wc-baghjan-1/2/3, scoring 0.90/0.99/0.98 per `demo_final_state.md`) are **verbatim training rows** (confirmed: `demo_corpus.jsonl` texts ∈ `train_final_v4.jsonl`; 6 of 13 demo cards are in-train — all 3 WC cards, both contrast-pair cards, and gray-drill), and D24 deliberately excluded them from the near-dup index so the "memory, not generalization" banner does NOT fire on them. When I pasted a *novel* Baghjan-class precursor (Probe 1), the model scored **0.033** — the WC tag fired, the neural model completely missed it. If a judge pastes their own well-control narrative and gets 0.03 LOW next to a demo card that scored 0.99, the demo's strongest beat becomes an exposé of memorization. The rehearsed line "our well-control tag catches what nine rules cannot" survives ONLY if delivered as "deterministic tag" — never "the model catches it". Pre-rehearse the judge-paste scenario for WC text specifically; the script's "Judge's own report → GO unconditionally" row is dangerous for this class.

### Q11 (domain, PTW/Bypassing): "Two of the nine IOGP Life-Saving Rules — Work Authorisation and Bypassing Safety Controls — are exactly where Baghjan-class organizational failures live. You show them greyed out. So your system can't see the two rules that matter most?"

**Best honest answer (verified live):** "Correct, and it's measured honesty, not a gap we paper over: PTW is effectively zero-detectable in free text (1 genuine row of 3 'permit' hits in 105,996 OSHA narratives), Bypassing 0.08–0.09% — the data does not contain the signal, so we declare both out of scope and show them greyed in the UI (`/api/rules` live: `in_scope: false`, threshold null — verified tonight). Faking a PTW probability would be the actual dishonesty. What we cover: the 7 rules with measurable signal, plus the well-control/barrier tag for the process-safety class. IOGP rule 8 is displayed by its official name — 'Work Authorisation (Permit to Work)'."

**Trap analysis:** Apologizing vaguely instead of quoting the detectability numbers — the numbers ARE the defense ("<0.1% detectable" is a stronger answer than "it's hard"). Conversely, never imply the greyed rules are "coming soon" with a trained model — there is no training signal; a PTW model on this data would be astrology. If asked "how would you ever cover PTW", the honest answer is structured permit-system integration, not NLP on narratives.

### Q12 (domain, language): "Half of OIL's field workforce reports in Hindi or Assamese. Your engine is English-only. Isn't that disqualifying for a deployment in Assam?"

**Best honest answer (verified live — Probe 2):** "The interface speaks Hindi — a ~30-string cloud-QA'd phrasebook covers UI chrome with an EN/हिं toggle. Report text is NEVER machine-translated live, by adjudicated decision with measurements behind it: the 4B model produces Hindi gibberish ('shock' → 'शोक'/grief), the 8B is ~1/6 nonsense. What the engine does with a Devanagari report is the honest thing: the language gate fires and routes it to gray review with a 'language not yet supported' badge — I pasted a Hindi fall-from-height report tonight and it returned gray with non-ASCII ratio 0.79, no silent mis-score. A wrong English score on a Hindi report is the disqualifying behavior; a designed gray state is not."

**Trap analysis:** Attempting live translation on stage (the script itself says "Never attempt live translation — rehearsed refusal line ready" — follow it). Claiming "Hindi support" without immediately scoping it to UI chrome + honest gray routing. The phrase "the engine honestly says when a report is beyond its language" (demo script 0:38–0:47) is exactly right — don't improve on it ad hoc.

---

## PART 2 — Live adversarial probes (run tonight against :8177, masked-v2 int8)

All via stateless `POST /api/classify` (no store touched; labeling ports 8001–8004 and `artifacts/gold/labels*/` untouched).

### Probe 1 — Novel Baghjan-class well-control precursor (my own text, not in any corpus)
> "During well servicing operations at well NHK-619, the crew observed mud gains of about three barrels at the active pit while tripping out. The well started flowing during connections. The driller shut in the BOP and the well was brought under control by bullheading kill-weight mud. No injury and no spill occurred."

**Result: SIF score 0.0331 (LOW, threshold 0.6581) · all 7 rule probs ≤0.016 · `well_control: true` · negation gate → GRAY** ('no'~'kill' — the known "kill-weight mud" register conflict from KB §9 is still live in the gate lexicon; also 'no'~'injury').

**Diagnostic isolation** (same text, negation sentence removed): score **0.0224**, negation off, WC tag still on. → The LOW score is the model, not the gate. **The neural model does not generalize to novel well-control narratives; only the deterministic tag catches them.** The demo's 0.90–0.99 WC scores are verbatim training rows (verified: texts ∈ train_final_v4.jsonl). Net UI behavior is defensible (gray + WC tag = routed to review, not auto-greened) but the score contrast vs the demo cards is a stage hazard (see Q10 trap).

### Probe 2 — Devanagari Hindi high-energy report (fall from height, no harness)
> "पाइप रैक पर काम करते समय कर्मचारी का सेफ्टी हार्नेस लाइफलाइन से नहीं बंधा था। वह संतुलन खोकर लगभग 20 फीट नीचे गिर गया और उसे तुरंत अस्पताल ले जाना पड़ा।"

**Result: score 0.0368 (meaningless, as designed) · language gate → GRAY** (`devanagari, non_ascii_ratio=0.79 > 0.15`). Exactly the designed behavior: no silent mis-scoring of non-English text. PASS.

### Probe 3 — Genuine high-energy event wrapped in negation + first-aid register
> "During maintenance at GGS-2 Kathalguri, the scaffold platform collapsed while two fitters were standing on it and both fell about 15 feet to the ground. Fortunately no one was injured and both were discharged after first aid."

**Result: score 0.9682 HIGH · Working-at-Height 0.98 · negation gate correctly did NOT fire** — "fortunately" is a counterfactual suppressor that scopes the 'no'~'injur' pair (`gates.py:46-49,155-161`). This is the sharpest gate-design question on stage ("does your negation gate silence real SIFs?") and the system answered it correctly on a novel input. Also confirms the D21 first-aid fix did not overcorrect: a real fall-from-height with "first aid" in the text still flags HIGH (the fixed first-aid FP card itself reads 0.15 raw / 0.26 cal, and 0/20 unseen first-aid paraphrases flag — `first_aid_results.json`, verified). PASS — and a genuinely good demo answer if a judge tries this attack live.

**Probe-adjacent observation:** live `/api/classify` e2e latency tonight measured 93–169 ms (3 samples, includes gates + near-dup over the seeded index, under labeling-load), vs KB §10's model-only p95 19.7 ms. Don't quote sub-20 ms as end-to-end API latency on stage.

---

## PART 3 — Findings register (severity-ranked)

1. **SEV2 — Demo WC/contrast cards are verbatim training rows (6/13: all 3 wc-baghjan cards, contrast-red, contrast-green, gray-drill), and D24 removed them from the near-dup index so the memory banner can't fire.** Rationalized as demo optics ("they play the user's own reports"), documented in D24 — but the script never discloses it, and Probe 1 proves the neural model does NOT generalize to the exact class (well-control) those cards showcase. If any judge probes with their own WC narrative, the 0.99-vs-0.03 contrast is indefensible unless pre-empted with the "deterministic tag, not the model" framing. **Action before rehearsal: add one scripted line at the WC beat — "the barrier tag is deterministic; the neural score on novel well-control text is a known gap we're honest about" — and rehearse a judge-paste of novel WC text.**
2. **SEV3 — `export_gate_pass: false` in the shipped artifact's own manifest** (Kaggle-side int8 RED, ΔAUC 0.1305). Adjudicated (D20, local PASS) and disclosed in `ship_decision.md`, but the artifact-metadata surface contradicts the ship story at first read. Q7 answer above is the only safe line.
3. **SEV3 — Frozen spec hash recorded wrong in KB/CHECKPOINTS/manifest top-level `spec_sha256` (db946283…) vs actual file (96114b09…) at the freeze commit itself** (verified: `git show 106b37a:spec/label_spec.yaml | sha256sum` = 96114b09). Content has NOT drifted since freeze — this is a bookkeeping error, not label drift; the manifest's per-file entry and the retrain kernel log both carry the correct hash. Fix the doc fields or be ready to explain the mismatch if a judge runs the hash.
4. **SEV4 — D16's "synthetic ~10% of train" is stale**: v4 mixture measured at 13.6% (9,687/71,065). Quote the measured number.
5. **SEV4 — Gold judgment-count arithmetic (690 emitted vs 650 from primary+secondary)** needs a one-line explanation (20 pilot items × 2, per `pilot_ids`) rehearsed.
6. **Acceptance-bar status (honest):** "beats TF-IDF at p<0.05" is NOT met on derived labels (p 0.122); int8 agreement-at-op leg fails 99.5% (97.7–98.3%); gold metrics + κ do not exist yet (labeling began 00:12 tonight). The architecture's own doctrine says gold is the arbiter — the final gate tomorrow morning is where these land.
7. **Strengths verified live:** Hindi gray routing (Probe 2), counterfactual-aware negation gate on a genuine SIF (Probe 3), PTW/Bypassing honestly greyed in the API, first-aid fix holding on novel text, health endpoint truthful (5,048 reports, masked-v2 int8).

## Verdict

The build is unusually honest — most traps have documented, measured answers. The two live dangers on stage are (a) the WC memorization contrast (finding 1) and (b) quoting val-derived or stale numbers (0.997 AUC, "~10% synthetic", handoff CIs, a not-yet-existing κ). Both are rehearsable in the remaining hours.

<<SCORES {"ps":"26165","role":"hostile_qa_simulator","go_no_go":7,"severity":4,"feasibility":7,"data_risk":7}>>
