# ARCHITECTURE v2 — SIF-Precursor Detection Engine (PS 26165)

> **2026-09-25 (production overhaul):** this file is preserved as the adjudicated v2 record
> (dev-time pipeline detail and Phase-1 rulings remain valid). The single accurate architecture
> reference — runtime components, measured latencies, gate family, explanation two-tier,
> human-in-the-loop loop, CLAIM BOUNDARY and honest limitations — is now
> [`docs/architecture.md`](../../docs/architecture.md).

Status: ADJUDICATED. Supersedes HANDOFF.md Part C where they conflict. Produced by Phase 1 swarm (12 specialists) + orchestrator adjudication, 2026-09-08. Rulings in `DECISION_LOG.md`; evidence in `phase0-validation/` and `phase1-architecture/`.

Changes vs Part C are marked **[CHANGED]** / **[NEW]** / **[CUT]**.

```
DEV-TIME (cloud legal; only public/synthetic data leaves the machine)
  OSHA SIR parse ──► strip/whitespace-normalize ──► dedup (66 exact + near-dup screen)
       │
       ▼
  OIICS label derivation — DUAL ERA-CONDITIONAL MAPS (v1: 2015-23, v2: 2024-25) [CHANGED]
  (2024 break is a full code RENUMBERING — parent-code rollup is mathematically
   impossible; era-conditional prefix maps frozen in label_spec.yaml)
       │
       ├──► SIF label: definition frozen in label_spec.yaml (high-energy mechanism
       │    set; measured swing 55.4%→74.7% depending on definition — freeze at H2)
       ├──► 7 learnable IOGP rules (PTW/"Work Authorisation" + Bypassing declared
       │    out-of-scope: <0.1% detectable — honesty slide, never faked)
       └──► [NEW] deterministic well-control/barrier tag (Baghjan-class events the
            9 personal-safety rules don't cover; keyword/code rules, cheap)
       │
  Outcome-mask: TOKEN-LEVEL NEUTRALIZATION, applied to positives AND negatives [CHANGED]
  (clause-stripping measured to empty 19.1% of rows; neutralization: 0% empty,
   length preserved; stem list frozen in label_spec.yaml)
       │
  Negatives: OSHA low-energy rows (masked) + ASRS (weak labels from
  Events_Anomaly/Assessments fields; register + counterfactual language) [CHANGED]
       │
  Synthetic OIL corpus 8-10k — dev-time CLOUD LLM generation [CHANGED]
  (local generation at 4 tok/s ≈ 100h — impossible. Register seeded from 2,756
   OSHA oil-gas-NAICS rows + SmartQHSE vignettes + OIL vocabulary list from HSE
   reviewer; inverse-frequency rule quotas — EI/CS have only 47/29 seed rows;
   8-gram Jaccard dedup; outcome-leak rejection; LLM-ism detector = TF-IDF+LogReg
   AUC iterated <0.9) [Snorkel CUT — plain deterministic labeling functions]
       │
       ▼
  Splits: TEMPORAL HARD (train ≤2023 / test 2024-25) + employer-grouping WITHIN
  train only + cross-boundary near-dup screen (measured 0.13% at J≥0.5) [CHANGED]
  (42% of test rows share employer with train — grouped test split is incoherent)
       │
       ▼
  Kaggle GPU (auto-detect cell: prefer 2x T4 sm_75 via machineShape enum
  "NvidiaTeslaT4"; fallback 1x P100 sm_60 + torch cu126 reinstall) [CHANGED]
  torch 2.10+cu128 works on T4 as-is; pinned transformers==4.57.6
  ModernBERT-base multi-task (attn_implementation="sdpa" — no FA2 on sm_60/75):
    head 1: SIF binary — plain BCE (near-balanced) [CHANGED]
    head 2: 7-rule multi-label — per-rule capped pos_weight + per-rule tuned
            thresholds [CHANGED]
    head 3: token-span head — WEAKLY SUPERVISED from keyword anchors [CHANGED]
            (fallback if quality poor: keyword-attribution highlighting)
  seq_len=128 (verified p99=112 tokens on corpus) ✓
  masked + unmasked variants sequentially in ONE session; 5-config ablation A–E
  ~25-60 min/run on P100, faster on 2xT4; full job roster ≈ 8 GPU-h of 30h quota
  Export-gate kernel runs BEFORE any training [NEW]
       │
       ▼
  ONNX export: HAND-ROLLED torch.onnx.export + onnxruntime quantize_dynamic [CHANGED]
  (optimum-onnx 0.1.0 unusable: pins transformers<4.58, no custom-head support)
  Two-tier parity gate [CHANGED]:
    fp32 export: |Δlogit| ≤ 1e-4
    int8: decision-level — AUC drop ≤0.005, recall@p0.8 drop ≤0.01,
          label agreement ≥99.5%
  Artifact mirror: per-epoch checkpoints in /kaggle/working, one-config-per-kernel
  (≤45 min), post-completion MCP retrieval (byte-identical path verified);
  NO in-kernel dataset push (MCP kernels have no Kaggle API creds) [CHANGED]
       │
       ▼
  Baselines (one table, Holm-corrected paired McNemar): regex / TF-IDF+LogReg /
  zero-shot qwen3:8b (local overnight precompute ~2-4h; cap n=200 only if
  throttle persists) / fine-tune

RUNTIME (100% local; bare-metal, no docker dependency) [CHANGED]
  CSV/Excel upload · paste box · JSON API (column-mapping config)
       ▼
  Ingestion → validation → SQLite + numpy near-dup index (MiniLM embeddings,
  brute-force cosine measured 20-25 ms/query over 110k×384 even throttled) [CHANGED]
  (Postgres+pgvector CUT from ship path — docker daemon down; Storage protocol
   abstraction keeps a Postgres swap possible; near-dup index INCLUDES the
   synthetic corpus so training-row paste attacks are caught)
       ▼
  FastAPI + onnxruntime: ModernBERT INT8 multi-task (8 threads; 16 is worse)
       → SIF triage score (calibrated, temperature-scaled; "triage score",
         never "% accuracy") [CHANGED]
       → rule probabilities (7 rules, per-rule thresholds; PTW/Bypass shown
         as declared-out-of-scope) + well-control/barrier tag [CHANGED]
       → evidence spans (span head with keyword-attribution fallback — the
         fallback is the de-facto live path, KB §11; CHAR offsets computed
         server-side against canonical text, self-validated
         text[start:end]==span before render) [CHANGED]
       → input gates: confidence · negation (NegEx-style) · language · near-dup
         banner (threshold from measured MiniLM embedding curve, not guessed)
         [NEW gates:] drill/simulation filter · short-codes path ("LOTO not
         applied" must NOT be eaten by the min-20-char validator) · long-input
         sliding-window chunking with max-pool + OOD badge
       ▼
  Explanation renderer: deterministic templates (label, rule, spans, confidence)
       └── optional Ollama qwen3:4b Q4_K_M rewording [CHANGED from 8b — measured
           better: 96% first-try verbatim spans, 0% failure after 1 retry, n=50;
           8b was worse AND +2.6 GiB RAM]
           Invocation contract: /api/chat + think:false + format:<JSON-schema>
           ON EVERY CALL (schema is what suppresses thinking — /no_think and
           bare think:false both verified broken); pydantic validation +
           exact-substring span check + 1 retry → template fallback [CHANGED]
       ▼
  Hindi: 33-string dev-time cloud-QA'd phrasebook, UI chrome only (EN/हिं
  toggle); report text never machine-translated live [CHANGED]
       ▼
  React dashboard (shadcn/ui + Tailwind, navy theme, IBM Plex, amber hazard-
  stripe signature; designed/rehearsed at 1920×1080):
    · report feed + highlighted evidence
    · triage card: AMBER "review priority" band (red CUT — framing leak),
      equal-weight Confirm / Not-SIF override buttons, "model proposes,
      HSE disposes" footer [CHANGED]
    · 4 engineered gray states (low-confidence / negation / non-English /
      near-dup) as one humility system
    · site/activity precursor-density ranking (ranked table + FLIP re-rank
      animation — the money beat)
    · pattern mining: lift-ranked activity×location×barrier co-occurrence on
      structured facets with n + Wilson CIs — honest stats, no LLM tagging [CHANGED]
    · review/override queue (overrides → future gold labels; export path)
```

## Claim boundary (unchanged doctrine, corrected citations)

- Triage + extraction precision + time saved. Never prediction accuracy.
- **[CORRECTED]** The "~20%" figure is ~20% of *recordable injuries* with SIF potential (BST/Mercer ORC 2011; Martin & Black 2015) — NOT "20-25% of near-miss reports". Cite precisely; measure and report our own flag rate.
- **[CORRECTED]** IOGP rule 8 is officially "Work Authorisation" — display "Work Authorisation (Permit to Work)".
- **[NEW]** Baghjan answer: "The precursors existed and were buried in routine reports — we make them impossible to bury." (WOC 48h→12h, BOP pulled before cement set, no officer on site — verified facts.) Never claim the tool would have prevented it.
- **[CHANGED]** Redaction-ablation claim weakened: mechanism text is a near-deterministic proxy for outcome within strata (P(amputation) 0.007–0.82 across fixed EventTitle strata) — report the ablation as robustness evidence, not "mechanism not outcome" proof.

## Contamination hygiene protocol [NEW]

1. Generator LLM (synthetic corpus) ≠ zero-shot baseline LLM (qwen3:8b local) ≠ any LLM that touches the label spec or gold materials. Provider separation documented in the deck appendix.
2. Gold labelers see outcome-redacted text + EventTitle only (kills hindsight bias); never see model/LLM output; label spec frozen before labeling starts.
3. κ is human-vs-human (Fleiss', 150-item double-labeled subset) — never model-vs-human as validity.
4. Gold composition ~300 OSHA 2024-25 (up to 150 oil-gas NAICS) + 100 ASRS + 100 synthetic; headline metrics on real-only strata; synthetic reported separately, never pooled.
5. Note: label-map quality degrades in eval years (high-energy prefix rate 55.4%→30.7% in 2024-25, v1→v2 break) — gold sampling accounts for it.

## Acceptance bar (revised §E — corrections adjudicated)

- **Accurate:** recall@precision-0.80 with CORRECTED Wilson CIs (500 gold @ ≥40% enriched prevalence → width ≤0.12; the handoff's [0.80,0.95]@300 and [0.85,0.94]@1000 were both wrong — recompute before slides freeze). Beats regex + TF-IDF baselines (Holm-corrected McNemar p<0.05). Spans: substring-validity 100% + token-F1 ≥0.80 vs adjudicated spans on 100-report subset [CHANGED from "exact-match ≥95%" — human-human exact agreement is far below 95%].
- **Fast:** <100 ms p95 classification UNTHROTTLED (est. 35-75 ms; throttled measured 244 ms — contingency: precompute + seq-bucketing + Day-1 power-fix human task). Bulk ingest: ≥30 reports/s classify-only sustained [CHANGED from ≥500/s — arithmetically impossible on this CPU; ~150-330/s estimated unthrottled with bucketing; demo bulk step precomputed].
- **Tested:** two-tier ONNX parity gate; 50-row golden regression; adversarial suite (§B.3 + 5 new from demo red-teamer) all gated; Playwright e2e.
- **Reliable:** 100% offline demo on BARE METAL (run.sh: uvicorn + static React + SQLite; docker NOT on critical path); template fallback every LLM call; gray-card paths.
- **Production-shaped:** one-command startup; schema-validated ingestion; versioned model artifacts (ONNX + metrics.json + label_spec hash); override→label loop; README with architecture diagram + honest-claims section.
- **Validated:** every deck claim measured on this machine in the last 72h.

## Non-delegable human tasks (revised)

1. **[H0 — Day 1, first hour]** Docker: enable daemon + add user to docker group (needs root; `sudo -n` verified working — ~30 min). Needed for Label Studio + packaging niceties, NOT for the demo itself.
2. **[H0 — Day 1, first hour]** Power clamp: all cores stuck at 0.85 GHz under load (41.5°C, performance governor — likely platform power limit). Investigate charger/battery/BIOS/UEFI settings. Every latency number depends on this.
3. **[Day 2 evening — start]** Blind gold labeling: 500 single + 150 double-labeled, 6-8 person-hours [CHANGED from 300-500/4h Day 3]. Labelers never see model output.
4. Demo-day physical presence + rehearsal attendance (ethernet unplugged).
5. (Optional) Domain-expert review of ~50 synthetic reports.
