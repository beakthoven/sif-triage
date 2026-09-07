# REVISED 72-HOUR PLAN — run2 (post-Phase-1)

Supersedes HANDOFF.md Part D. Sequenced around validated facts: T4-via-enum GPU path, bare-metal runtime, corrected gold budget, early human escalations. Parallel streams: **D**ata pipeline ∥ **T**raining ∥ **S**ystem (API+dashboard).

## Day 1 — validate → freeze → data + first training

| Hour | Stream | Task |
|---|---|---|
| H0 | HUMAN | Two escalations in parallel: (a) docker root fix (30 min, non-critical); (b) CPU power-clamp investigation (charger/BIOS/platform profile) |
| H0 | ALL | `git init` + initial commit; venv setup; read ARCHITECTURE.md + DECISION_LOG.md |
| H0–2 | D+T jointly | **LABEL SPEC FREEZE (the single load-bearing gate):** SIF-positive definition (D15), dual OIICS era maps (D9), mask stem list (D6), span-supervision decision (D2), rule quotas, gold protocol (D7/D8) → `label_spec.yaml` + hash |
| H1–3 | T | Kaggle smoke kernel: auto-detect GPU cell → torch check → 500-sample ModernBERT forward/backward → **export-gate kernel** (hand-rolled ONNX export + quantize_dynamic + two-tier parity on the real 3-head module) — BEFORE any training (C4) |
| H2–8 | D | OSHA parse/strip/dedup → dual-map label derivation → token-neutralization masking → ASRS pull + weak negatives → splits (temporal hard, grouped train, near-dup screen) → publish Kaggle Dataset |
| H4–10 | D | Synthetic OIL corpus: cloud-LLM generation (stratified inverse-frequency quotas, OIL 24-term vocab, 3 register exemplars) → 8-gram Jaccard dedup → outcome-leak reject → TF-IDF+LogReg LLM-ism AUC<0.9 iterate |
| H6–12 | T | Config A (masked) + Config B (unmasked) training runs, sequential per kernel; per-epoch checkpoints; MCP retrieval after each; fast baselines (regex, TF-IDF+LogReg) |
| H8–12 | S | FastAPI skeleton + ingestion/validation + SQLite schema + Storage protocol (parallel-safe: API contract from ARCHITECTURE.md, model mocked) |

**Day-1 exit criteria:** label_spec.yaml frozen+hashed; export gate GREEN; ≥1 trained masked model retrieved locally with baseline table row; corpus v1 on disk.

## Day 2 — system + full training + gold prep

| Hour | Stream | Task |
|---|---|---|
| H24–30 | T | Remaining ablation configs (C/D/E per NLP engineer's 5-config set); zero-shot qwen3:8b baseline (local overnight precompute; cap n=200 only if clamp persists); temperature scaling; final ONNX int8 + parity gate → versioned artifact |
| H24–36 | S | Inference service (onnxruntime, 8 threads, char-offset spans server-validated) → 6 input gates (confidence, negation, language, near-dup incl. synthetic index, drill filter, codes-path) → explanation renderer + Ollama contract layer → pattern mining (lift-ranked co-occurrence + Wilson CIs) → review/override loop |
| H30–40 | S | Dashboard: feed+highlights, amber triage card, 4 gray states, density ranking + FLIP re-rank, pattern cards, review queue; navy theme + hazard stripe; 1920×1080 |
| H36 | HUMAN | **Gold labeling STARTS (evening)** — blind protocol, outcome-redacted text + EventTitle only, local labeling form; 500 + 150 double; 6-8 person-h across team |
| H40–44 | S | Hindi phrasebook (30 strings, cloud-QA'd); precompute ALL demo-corpus LLM outputs; 90s fallback recording v1 |

**Day-2 exit criteria:** end-to-end demo path works on mocked → real model; final model artifact versioned; gold labeling ≥50% done.

## Day 3 — proof

| Hour | Task |
|---|---|
| H48–56 | Gold labeling COMPLETE → Fleiss' κ (150 double) → recall@precision-0.80 + corrected Wilson CIs per stratum (real-only headline) → baseline table + Holm-corrected McNemar → span token-F1 on 100-report adjudicated subset → redaction-ablation experiment (2h) |
| H50–60 | Adversarial suite green (10 + 5 new); 50-row golden regression; Playwright e2e (webapp-testing skill); latency re-measured (clamp-dependent); bare-metal run.sh + tarball packaging; README + architecture diagram + honest-claims section |
| H58 | HUMAN | Domain-expert review of ~50 synthetic reports (optional, if outreach landed) |
| H60–66 | Q&A deck (never-say sentences, corrected citations, Baghjan answer, contamination-hygiene appendix); metrics money slide with CORRECTED CIs |
| H66–72 | Final fresh-eyes swarm validation vs PS text + revised acceptance bar → **full rehearsal, ethernet unplugged, 1920×1080** → fallback recording final |

## Standing protocols

- Every swarm prompt ends agents with `<<SCORES {...}>>`; aggregate with `pipeline/aggregate_scores.py`.
- 2-4 agent adversarial review per critical component as it lands (Doctrine 2).
- Every deck claim traces to a measurement from this machine, this run (Doctrine 1).
- Update `kb/KNOWLEDGE_BASE.md` whenever a fact changes; log verdicts in `VALIDATION_LOG.md`.
- If a stream slips: cut order = span head → pattern mining → Hindi → zero-shot baseline n.
