# Q&A PREP — SIF-Precursor Engine (SIH 26165)

No dedicated Q&A-auditor artifact exists in `runs/run2/`, so this is built from the
DECISION_LOG (15 adjudicated rulings + 12 rejected proposals), the SEV1 register, and
the day-1/day-2 deviation reports. Every answer carries its evidence pointer. Gold
placeholders fill from `artifacts/gold/gold_metrics.json` after labeling.

**Posture:** confident on engineering, humble on scope. Every "we don't" is paired with
the designed mitigation. When a number is asked for, give the measured number and its
n — never round up.

---

## The 12 hardest questions

### Q1. "Isn't this just predicting accidents? Who is liable when you're wrong?"
**A:** No — it's a triage queue. The system ranks reports by review priority and shows
its evidence; a human disposes of every flag ("model proposes, HSE disposes" is on the
triage card itself). There is no prediction output, no "% accuracy", no "SIF detected"
anywhere in the UI — the card is an amber *review-priority* band, not a red alert
(DECISION_LOG D14). A wrong flag costs a reviewer ~30 seconds; a buried precursor costs
what buried precursors cost. Override buttons (Confirm / Not-SIF) are equal-weight, and
overrides are logged as future gold labels.

### Q2. "Your '~20%' statistic — where is it from, exactly?"
**A:** ~20% of *recordable injuries* carry SIF-potential mechanisms — BST/Mercer ORC
2011; Martin & Black 2015. We deliberately do **not** say "20–25% of near-miss reports";
that misquote was caught in our own review (SEV1-12) and corrected. And we measure our
own flag rate instead of borrowing one: on the 5,048-report demo corpus the engine flags
71.0%, and the operating point is precision-guaranteed (≥0.80) — you tune the queue
length, we don't hide it.

### Q3. "You have zero OIL data. Why should this work on our reports?"
**A:** Honest answer: that's the core data risk, and we engineered around it instead of
pretending it away. (a) Backbone is 105,996 real US OSHA regulatory narratives — the
high-energy *mechanisms* (struck-by, falls, stored energy, hot work) are
industry-universal. (b) A 9,687-row synthetic corpus teaches OIL register: 24-term OIL
vocabulary gate passed 24/24 (GGS, GCS, christmas tree, WOC, kick ≥50 rows each).
(c) The proof instrument is the gold set: 500 blind-labeled reports — 300 real OSHA
2024–25 with a 150-row oil-gas-NAICS oversample, 100 ASRS, 100 synthetic — headline
metrics on **real data only**, synthetic reported separately, never pooled (D8).
Gold recall @ P≥0.80: **{{GOLD_RECALL}}** [{{GOLD_RECALL_CI}}].

### Q4. "Would your tool have prevented Baghjan?"
**A:** We never claim that — it's on our what-we-don't-claim slide. The verified facts:
wait-on-cement cut from 48 h to 12 h, the BOP pulled before the cement set, no OIL
officer on site. Our claim is narrower: *the precursors existed and were buried in
routine reports — we make them impossible to bury.* And we built the deterministic
well-control/barrier tag precisely because the 7 personal-safety rules don't cover
Baghjan-class events (SEV1-13). Then stop talking. Never improvise on this question.

### Q5. "Your synthetic data — a TF-IDF can tell it apart from real text at AUC 1.0. Isn't it just fake data?"
**A:** Measured, disclosed, and ruled on (D16). The detector's top features are
*register* markers — "hrs", date numerals, GGS/EPS openers — i.e., Indian contractor
prose vs US inspector prose, not LLM artifacts; the same detector separates registers
even against oil-gas-only OSHA rows. Critically, register is **balanced across
synthetic positives and negatives**, so the SIF label is unconfounded by the tells.
Synthetic is 13.6% of training, carries the thin rules (confined-space real support is
~0.2–0.7%), and gold reports the synthetic stratum separately, never pooled. It is
coverage augmentation, claimed as nothing more.

### Q6. "Val AUC 0.997 but test AUC 0.868 — your model doesn't generalize."
**A:** Both numbers are on the slide precisely because we don't hide the gap. The val
split is saturated (79.4% prevalence ≈ the 0.80 precision floor — near-vacuous), and
the test split crosses the 2024 OIICS **code renumbering**: the derived labels degrade
there (high-energy prefix rate falls 55.4%→30.7% in 2024–25). A val control reproduces
the training-side numbers exactly, so it's label-map noise + saturation, not a pipeline
bug (measured, D19). This is exactly why the final arbiter is **human-labeled gold**,
not derived labels.

### Q7. "TF-IDF is statistically tied with your fine-tune (p = 0.122). Why the transformer?"
**A:** True on derived labels, and we disclose it on the baselines slide. What TF-IDF
doesn't ship: a precision-≥0.80-guaranteed operating point, calibrated scores, the
7-rule multi-label head (fine-tune rules exact-set 0.819 vs tfidf 0.788), evidence
spans, and an explanation layer. And derived labels are a proxy — the blind gold set is
the arbiter. (Gold-vs-baselines McNemar requires baseline scores on the gold items —
that wiring is a Day-3 task per gold_metrics_pipeline.md; if it lands, quote
**{{GOLD_MCNEMAR_TFIDF_P}}** here, otherwise rest on the derived-sample table + the
capability list, and say the gold head-to-head is the fine-tune vs the proxy labels
tonight.) Either way: the fine-tune *does* beat the 8B zero-shot LLM significantly
(p = 0.0018) at 1/1083 the per-row latency.

### Q8. "Why not just run an LLM zero-shot over the reports?"
**A:** We measured it — that's a baseline row, not a hypothetical. Zero-shot qwen3:8b:
F1 0.854, 13.0 s/report, needs a GPU-class box or a very patient reviewer, and it
over-predicts SIF (221 FP vs 81 FN). Our int8 model: F1 0.881, ~12 ms median, CPU-only,
air-gapped — 1,083× cheaper per classification, with calibration and a tuned operating
point. The LLM still has a job in our system: optional rewording of deterministic
explanations (qwen3:4b, schema-constrained, with template fallback on every call).

### Q9. "Your INT8 export failed its own parity gate on Kaggle. Is the deployed model broken?"
**A:** The Kaggle-side gate was RED (ΔAUC 0.13 on ranking) and we didn't ship on that
evidence — we re-measured on the demo machine: full-val int8 AUC 0.9934 vs torch 0.9969
(Δ0.0035, PASS); quantization error is execution-provider-dependent (D20). Remaining
honest wrinkle: at the tuned operating point int8-vs-fp32 flip ~2% of decisions
(46/2,000) — so the operating point was tuned **on the int8 single-text chain itself**,
making the shipped system self-consistent; fp32 is a documented, not-decision-equivalent
fallback (one env var). Ranking is intact; boundary noise is disclosed.

### Q10. "IOGP has 9 life-saving rules. Where are Permit-to-Work and Bypassing?"
**A:** Declared out of scope and shown greyed in the UI — never faked. Measured basis:
Permit-to-Work (rule 8, officially "Work Authorisation") is effectively
zero-detectable in free text (1 genuine hit in the whole corpus) and Bypassing ~0.08%.
Faking two bars would be exactly the kind of dishonesty this tool exists to kill. The
well-control/barrier tag partially covers the process-safety side those rules miss.

### Q11. "How do we know your gold evaluation isn't circular or gamed?"
**A:** Four controls, all enforced by tooling, not promises: (1) labelers see only
outcome-redacted text + event title — never model output, never derived labels
(machine-verified: zero provenance fields in the labeler payload); (2) the label spec
was frozen and sha256-hashed *before* labeling started; (3) the operating point was
frozen on the temporal holdout and applied to gold **once** — no re-tuning on gold;
(4) agreement is human-vs-human Fleiss' κ on a 150-item double-labeled subset +
20-item pilot — **{{GOLD_KAPPA}}** — never model-vs-human dressed up as validity.
Judgment arithmetic, if a judge counts: **690 emitted = 500 primary + 150 double +
20 pilot × 2** — the 40 extra are the pilot calibration round (`pilot_ids` and
`n_judgments_emitted: 690` in `artifacts/gold/sample_manifest.json`).
Contamination separation: the synthetic-corpus generator LLM, the zero-shot baseline
LLM, and any LLM near the gold materials are three different things.

### Q12. "Will it actually run in our environment? What does it need?"
**A:** It's running right now with the network cable unplugged (that's a scripted demo
beat). Requirements: Linux x86-64, Python 3.14, 4 cores, 8 GB RAM, no network, no
docker. One command — `./run.sh` — brings up model + API + dashboard + SQLite; a USB
tarball (775 MB) with vendored wheels installs offline; the packaging self-check runs
two full start→classify→stop cycles. Measured on this laptop: p95 19.7 ms classify,
37.3 reports/s live bulk ingest, near-dup lookup p95 3.8 ms over a 70k-vector index.

---

## Bench questions (short answers)

- **"Hindi reports?"** UI chrome is bilingual (33-string QA'd phrasebook); report text
  is *never* machine-translated live — the language gate grays non-English reports and
  routes them to a human. Live translation was measured and rejected (4B gibberish-prone).
- **"Drills polluting the queue?"** Deterministic drill/simulation gate routes them out.
- **"Someone pastes a training row to make you look smart?"** The near-dup banner fires:
  "matches a training record — memory, not generalization", cosine shown. We demo this
  attack on ourselves on purpose.
- **"Long reports?"** Sliding-window chunking with max-pool + a CHUNKED badge;
  10k-char cap; nothing is silently truncated.
- **"Terse codes like 'LOTO not applied'?"** 16 chars, accepted via the short-codes
  path, keyword-tagged Energy Isolation, routed to review as low-information.
- **"What does the demo DB contain?"** 5,048 seeded reports (synthetic OIL register +
  one verbatim OSHA row used for the near-dup beat), all labeled as demo data.

## Never-say list (verbatim bans)

1. "SIF detected" / "the model detected" → say **"flagged for review"**.
2. "prediction" / "predicts incidents" → say **"triage" / "review priority"**.
3. "accuracy %" / "98% accurate" → say **"triage score"**; quote P/R at the op point with n.
4. "20–25% of near-miss reports" → the citation is **~20% of recordable injuries**
   (BST/Mercer ORC 2011; Martin & Black 2015).
5. "It would have prevented Baghjan" → **"precursors were buried; we make them
   impossible to bury."**
6. "trained on OIL data" → **US OSHA proxy + synthetic + ASRS, all disclosed**.
7. "covers all 9 IOGP rules" → **7 learnable; 2 declared out of scope**.
8. Any unmeasured latency/throughput ("500 reports/s", "<100 ms" without the measured
   19.7 ms p95 next to it) → quote only measured numbers from the last 72 h.
9. "the AI explains" without qualification → **deterministic template first; LLM only
   rewords, with fallback**.
10. "real-time translation" → **phrasebook chrome only; language gate grays the rest**.
11. Val AUC 0.997 as a headline → **the slide number is derived-test 0.868 + gold
    {{GOLD_RECALL}}**; val saturation is a disclosure, not a brag.
12. "fully automated HSE" → **"model proposes, HSE disposes."**

## If a number is challenged live

Open `artifacts/gold/gold_metrics.md` (post-labeling) or
`runs/run2/day2/ship_decision.md` / `runs/run2/kb/KNOWLEDGE_BASE.md` — every deck number
traces to a file, a script, and a seed. The doctrine answer: *"every number on that
slide was measured on this machine in the last 72 hours; here is the artifact."*
