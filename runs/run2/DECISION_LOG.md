# DECISION LOG — Phase 1 adjudication (orchestrator rulings)

Aggregated swarm signal: Phase 0 go_no_go mean **8.00/10** (n=10, severity 0.4) — foundation solid.
Phase 1 go_no_go mean **6.75/10 for the architecture as written** (n=12, 15 SEV1 flags, several overlapping) — the modifications below move it to go. Raw: `phase0_scores.aggregated.json`, `phase1_scores.aggregated.json`.

## Rulings on cross-specialist conflicts

| # | Conflict | Sides | RULING | Why (evidence) |
|---|---|---|---|---|
| D1 | GPU/torch strategy | Prosecutor: "unresolved P100 torch pin = SEV1" vs Kaggle engineer: "resolved" | **ADOPT kaggle engineer** | Live-verified today: correct enum `NvidiaTeslaT4` → 2x T4 (sm_75), preinstalled torch 2.10.0+cu128 runs natively; P100 fallback needs only cu126 reinstall (still ships sm_60), NOT a ≤2.6 downgrade. Mandatory: auto-detect cell in every notebook; export-gate kernel before training. C1 superseded (see VALIDATION_LOG). |
| D2 | Span head: keep or cut | NLP engineer: keep as weak-supervision vs Prosecutor: cut to keyword-attribution | **KEEP, weakly-supervised, with fallback** | Span highlight is the core demo wow and supervision comes free from keyword anchors already needed for labeling functions. Acceptance metric redefined honestly (substring-validity 100% + token-F1 ≥0.80 on 100 adjudicated spans). If training shows poor span quality, ship keyword-attribution — decision frozen at Day-1 H2 label-spec freeze. |
| D3 | Bulk ingest SLA | MLOps: "≥500/s impossible, set ≥30/s" vs Demo red-teamer: "150-330/s bucketed realistic" | **SLA = ≥30/s sustained; report measured number; demo step precomputed** | Both agree ≥500/s is arithmetically impossible (~19 TFLOP/s needed, CPU delivers ~1). The honest bar is the worst-case guarantee (≥30/s) plus a measured unthrottled number on the slide. Demo never depends on live throughput. |
| D4 | Runtime LLM size | Handoff: qwen3:8b vs Local-LLM engineer: measured 4b better | **SHIP qwen3:4b** | Measured n=50: 4b = 96% first-try verbatim spans, 0% failure after retry, 4.1 tok/s (throttled), ~3.2 GB RSS; 8b = 92%, 8% unrecoverable, 2.3 tok/s, +2.6 GiB. 8b kept installed for dev-time rewording generation + zero-shot baseline. |
| D5 | Runtime DB | Handoff §C: Postgres+pgvector vs MLOps + full-stack: SQLite+numpy | **SQLite + numpy ships** | Docker daemon down; brute-force cosine over 110k×384 MiniLM embeddings measured 20-25 ms/query even throttled — pgvector buys nothing at this scale. Storage protocol abstraction preserves a swap. Docker fix stays a human task for Label Studio/packaging, not the demo. |
| D6 | Outcome-masking | Handoff: "strip outcome clauses" vs NLP engineer: token-level neutralization | **Token-level neutralization, positives AND negatives** | Clause-stripping measured to leave 19.1% of rows empty; neutralization 0% empty, length preserved. Data-pipeline engineer: negatives must be masked too (96.8% of low-energy rows hospitalized). Stem list frozen in label_spec.yaml. |
| D7 | Gold set size/cost | Handoff: 300-500 labels, ~4 person-h, Day 3 vs Eval engineer: 12-15 person-h | **MVP: 500 single + 150 double, 6-8 person-h, START Day 2 evening** | The 4h budget buys no κ and no adjudication — and κ/anti-circularity is the load-bearing defense. Double-labeled 150-item subset gives Fleiss' κ. Day-3-only start risks the whole metrics slide. |
| D8 | Gold composition | Skeptic: per-stratum reporting vs implicit pooled | **~300 OSHA 2024-25 (≤150 oil-gas NAICS) + 100 ASRS + 100 synthetic; real-only headline; synthetic never pooled** | The eval must answer "will it work on OIL's reports" honestly: real-data strata carry the headline, synthetic is disclosed separately. |
| D9 | OIICS 2024 fix | Handoff: "dual maps OR parent-code rollup" vs Data-pipeline engineer | **Dual era-conditional maps ONLY** | 2024 break is a full code RENUMBERING (62x: struck-by→animal bites; 43x: fall-to-lower→fall-same-level) — rollup is mathematically impossible and would scramble the entire 17,746-row temporal test set. SEV1 caught before build. |
| D10 | Splits | Handoff: "employer-grouped + temporal" vs Data-pipeline: incoherent | **Temporal hard boundary; employer-grouping within-train; near-dup screen across boundary** | 42% of test rows share employer with train; cross-boundary near-dup measured tiny (0.13% at J≥0.5). |
| D11 | Methodology claims | Skeptic: redaction-ablation inference invalid | **Weaken claim wording; keep experiment** | P(amputation) ranges 0.007–0.82 across fixed EventTitle strata — mechanism ≈ outcome proxy; ablation reported as robustness evidence. Experiment kept (2h, high Q&A value). Contamination hygiene protocol adopted (see ARCHITECTURE.md). |
| D12 | Export path | Handoff: optimum[onnxruntime] vs MLOps: hand-rolled | **Hand-rolled torch.onnx.export + quantize_dynamic** | optimum-onnx 0.1.0 pins transformers<4.58 and supports only 4 standard modernbert tasks — custom 3-head module impossible. Pin transformers==4.57.6. Note ORT 1.29 renamed quant_dynamic→quantize_dynamic. |
| D13 | Parity gate | Handoff: \|Δlogit\|<1e-3 vs MLOps: two-tier | **Two-tier** | int8 quantization error makes 1e-3 logit gate theater. fp32 export ≤1e-4; int8 decision-level: AUC drop ≤0.005, recall@p0.8 drop ≤0.01, agreement ≥99.5%. |
| D14 | Triage card color | Handoff §B.8: "red SIF card" vs UX: framing leak SEV1 | **Amber "review priority" band** | Red + % + "detected" visually violates the triage-not-prediction doctrine in front of HSE judges. WCAG: amber-400 on navy = 11.2:1 AAA vs red-500 4.98:1. Score labeled "triage score", never "%". |
| D15 | SIF-positive definition | Handoff: 55.4% (or 59.8% with heat) vs Data-pipeline: 74.7% possible | **Freeze exact definition in label_spec.yaml at H2** | Measured swing 55.4%→74.7% depending on definition — this is the single most load-bearing spec decision; everything downstream (class balance, thresholds, metrics) depends on it. |

## Rejected proposals (documented per Doctrine 2 — these become Q&A defense)

| Proposal | Rejected because |
|---|---|
| Snorkel for weak supervision | Last release 2024-02 (frozen); deterministic labeling functions suffice — one less dependency. |
| Postgres + pgvector at runtime | Docker down; numpy brute-force measured 20-25 ms/query — pgvector is dead weight at 110k vectors. |
| optimum / optimum-onnx export | Version-locked, no custom multi-task head support. Hand-rolled export it is. |
| qwen3:8b as runtime LLM | Measured worse than 4b on the actual task AND +2.6 GiB RAM. |
| Clause-strip outcome masking | 19.1% of rows become empty — destroys the corpus. |
| ≥500 reports/s bulk SLA | Violates arithmetic on this CPU (~1 TFLOP/s vs ~19 needed). |
| OIICS parent-code rollup for 2024 break | Codes were renumbered, not re-titled — rollup scrambles labels. |
| Employer-grouped test split | 42% of test rows share employer with train — incoherent with temporal split. |
| Live Hindi translation | 4B Hindi gibberish-prone ("shock"→"शोक"/grief), 8B ~1/6 nonsense — phrasebook only. |
| Ollama ≥0.33 upgrade as C10 fix | Verified: 0.33.3 still ignores think:false without format. The fix is `format:<schema>` on every call. |
| Sankey/fancy pattern-mining viz | Plain-sentence top-5 pattern cards with n + Wilson CIs — honest and legible. |
| Runtime LLM facet tagging for pattern mining | Latency + failure surface; structured facets from generator/OIICS suffice. |

## SEV1 register (all 15 flags → disposition)

1. **P100 torch pin** (prosecutor, kaggle) → RESOLVED by D1 (T4 via correct enum; cu126 fallback; auto-detect cell).
2. **Docker daemon down** (toolchain, prosecutor, demo red-teamer) → demo critical path REMOVED (D5, bare-metal run.sh); human fix H0 for tooling.
3. **CPU 0.85 GHz clamp** (machine validator, MLOps, full-stack, local-LLM, demo, prosecutor) → OPEN: human task H0 (power profile); precompute doctrine + revised SLA (D3) de-risk the demo; every latency number re-measured Day 3.
4. **OIICS 2024 renumbering** (data-pipeline) → RESOLVED by D9.
5. **Span-head supervision hole** (prosecutor, NLP) → RESOLVED by D2.
6. **Drill filter missing** (demo red-teamer) → ADDED to gates (ARCHITECTURE.md).
7. **Short-codes input rejected by min-length validator** (demo red-teamer) → ADDED codes-path gate.
8. **Handoff CI numbers wrong** (eval engineer) → RESOLVED: corrected CIs in ARCHITECTURE.md acceptance bar; recompute before slides.
9. **Contamination graph uncontrolled** (skeptic) → RESOLVED: hygiene protocol adopted.
10. **Label-map degradation in eval years** (skeptic: 55.4%→30.7%) → accounted in gold sampling (D8).
11. **Red SIF card framing leak** (UX) → RESOLVED by D14.
12. **"20-25% of near-miss reports" misquote** (HSE) → RESOLVED: corrected citation (ARCHITECTURE.md).
13. **No well-control/barrier concept** (HSE — Baghjan exposure) → ADDED deterministic well-control tag.
14. **Synthetic 8-10k at local speed = ~100h** (prosecutor) → RESOLVED: dev-time cloud generation (already constraint-legal).
15. **"Ollama 8B ~3.2 GB" handoff error** (prosecutor: that's the 4B RSS; 8B ≈ 5.3-5.6 GiB) → moot under D4 (ship 4b).

**OPEN after planning phase:** CPU clamp (human, H0) · docker (human, H0, non-critical) · T4 allocation is best-effort day-to-day (auto-detect cell covers) · label spec freeze decisions (D2 span fallback, D15 SIF definition) due Day-1 H2.

## Post-freeze adjudications (Day 1)

| # | Issue | RULING | Rationale |
|---|---|---|---|
| D16 | LLM-ism gate FAIL: TF-IDF+LogReg separates synthetic from real at AUC 1.0000, even register-matched vs 1,318 oil-gas-only OSHA rows | **Ship with disclosure; no mitigation drops** | Top tells are stylistic register markers ("hrs", date numerals, GGS/EPS openers, "found/checked/done" closures), not LLM-isms. Purpose of the gate = prevent label-confounded shortcuts; register is BALANCED across synthetic pos/neg (both use GGS/hrs), so the SIF label is unconfounded. Synthetic is ~10% of train; gold eval has a separate never-pooled synthetic stratum; v2 generation applied diversity mandates. Residual risk disclosed in deck appendix. |
| D17 | train_mix spec inconsistency: ratios (0.55+0.10) imply ~65% prevalence but spec says target 0.40 | **Ratios win; prevalence ≈0.635 measured** | The 0.40 figure was a drafting error (gold prevalence target >=0.40 is the real constraint). Plain BCE (NLP engineer) assumes near-balanced; 65/35 qualifies; threshold tuned on val anyway. |
| D18 | Zero-shot baseline (qwen3:8b, n=1500 test): P 0.7996 / R 0.9159 / F1 0.8538 | **Recorded as the LLM baseline row** | Over-predicts SIF (221 FP vs 81 FN) — the fine-tune's calibrated threshold story ("same recall at guaranteed precision, 1/1000th cost, air-gapped") is intact. 0 schema failures across 1500 calls with the format-contract. OLLAMA_NUM_PARALLEL=6 required for concurrency (serialize otherwise) — added to run.sh checklist. |
