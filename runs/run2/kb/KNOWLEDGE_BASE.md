# KNOWLEDGE BASE — run2 (living document)

Consolidates HANDOFF.md Part B + Phase 0 validation + Phase 1 swarm findings. Where this conflicts with HANDOFF.md, THIS WINS (every entry re-measured 2026-09-08). Update as new facts land. Evidence: `../phase0-validation/`, `../phase1-architecture/`.

## 1. Data assets (validated)

| Asset | Status | Key facts |
|---|---|---|
| `data/January2015toNovember2025.csv` | VERIFIED, byte-identical to live osha.gov zip (md5-matched) | 105,996 rows × 28 cols; Final Narrative 0% missing, median 182 chars/31 words, p95=371, max 2134; dates 2015-01-01→2025-11-30 |
| `elihoole/asrs-aviation-reports` (HF) | VERIFIED | 47,723 rows (38,655/4,295/4,773), Apache-2.0, ungated, 270/30/33MB JSONL; 111 fields; **NO label column** — weak labels from `Events_Anomaly`, `Assessments.1_Primary Problem` |
| `SmartQHSE/major-process-safety-incidents-2026` | VERIFIED | 15 vignettes, CC-BY-4.0; rich content in `data.jsonl` (17 fields); use raw URLs (datasets-server broken) |
| `SmartQHSE/named-process-safety-incidents-extended-2026` | VERIFIED | 44 rows (card says 40), CC-BY-4.0, terse one-liners |
| `electricsheepafrica/africa-synth-...-nigeria` | **FAILED — useless** | 3,000 rows, 5 categorical columns, ZERO prose. Not a style reference. |
| SmartQHSE org (34 datasets) | VERIFIED exists | ≥12 process-safety-relevant (iogp-life-saving-rules, hse-glossary, hazop-guidewords, risk-matrix) — register/vocabulary grounding |

## 2. OSHA data facts (validated; corrections marked)

- Hospitalized = counts 0–6; **Amputation = counts 0–2 [C7]**; binarize >0. Loss of Eye = 35 rows (drop).
- 66 excess exact-duplicate narratives; dedup before split.
- NatureTitle whitespace variants: 18,428 rows — `.strip()` everything.
- OIICS 2024 break = **full code RENUMBERING** (62x struck-by→animal bites; 43x fall-to-lower→fall-same-level; 64x caught-in→struck-by). EventTitle double-space rate 0.18%→66.11%. **Dual era-conditional maps mandatory; parent rollup impossible.**
- High-energy prefix coverage (string-prefix, mixed code lengths): 62*=14,799; 64*=23,626; 43*=17,509; 51*=2,106; 32*=713 → 58,753 = 55.4%; +53* (4,632) → 59.8%. Caveat: 32*/53* buckets are loose (32* = v2 fires/explosions; 53* includes 1,912 "contact with hot objects").
- **SIF-positive definition swings 55.4%→74.7% depending on definition → freeze in label_spec.yaml.**
- **Label-map degradation: high-energy prefix rate falls 55.4%→30.7% in 2024-25** (v1→v2 break sits inside eval pool).
- Oil-gas NAICS (211/213) = 2,756 rows = 2.60%; EI/CS rule seeds only 47/29 rows → inverse-frequency synthetic quotas.
- Outcome leakage: P(Amp>0|'amputat')=98.6%; 'almost'=28 rows, 'could have'=3; overall leak-rate word-list dependent (70-76%) → freeze stem list in label spec.
- "An employee was": opens 63.6% of narratives (contains-anywhere 70.9%) [C8].
- Vocab rarity: workover=36, christmas tree=13, h2s=12 rows.
- seq_len=128 VERIFIED with real ModernBERT tokenizer: p99=112 tokens, 0.38% truncated.
- Clause-strip masking empties 19.1% of rows → token-level neutralization; mask negatives too (96.8% of low-energy rows are hospitalized).
- Splits: 42% of 2024-25 test rows share employer with train → temporal hard + grouping within-train + near-dup screen (0.13% at J≥0.5).

## 3. IOGP rule coverage (validated load-bearing claims)

- PTW effectively ZERO-detectable (1 genuine row of 3 "permit" hits); Bypassing 0.08-0.09% → declared out-of-scope, never faked.
- Line of Fire dominant under every proxy (39.6-45.1%); top-3 (LoF+WaH+Driving) = 66.7-68.9%.
- Per-rule CS/EI percentages are proxy-dependent (0.29-2.5% / 1.2-6.5%) — quote ranges, not points.
- **[NEW]** IOGP rule 8 official name: "Work Authorisation" (display "Work Authorisation (Permit to Work)"); Indian PSUs adapt (BPCL runs 12 rules).

## 4. Compute environment (validated)

- **Kaggle: 2x Tesla T4 (sm_75) via machineShape enum "NvidiaTeslaT4"** — verified live; preinstalled torch 2.10.0+cu128 works. **Fallback: 1x P100 (sm_60)** — reinstall torch cu126 (still ships sm_60 kernels); cu128+ dropped Pascal. Auto-detect cell mandatory in every notebook.
- Kaggle worker: python 3.12.13, 4 CPU, 31.3 GiB RAM, 21 GB disk; internet works in-session.
- **MCP-spawned kernels have NO Kaggle API credentials** → no in-kernel dataset push; per-epoch checkpoints to /kaggle/working + post-completion MCP retrieval (byte-identical verified). One config per kernel ≤45 min.
- Quota: 30 GPU-h/week (108,000s, refresh 2026-09-12); probe cost ~32s; full job roster ~8h.
- Demo machine: Ryzen AI 7 350 8c/16t AVX-512 ✓; 30.6 GiB RAM (~17 free) ✓; 514 GB free ✓; Radeon 860M gfx1152, no NVIDIA ✓.
- **CPU currently clamped 0.85 GHz under load** (41.5°C, performance governor): qwen3:4b 3.7-4.4 tok/s (vs 22.9 historical), ONNX int8 p95 244 ms (vs ~35-75 est. unthrottled). Human task H0.
- Docker daemon DOWN (no socket, no group, no compose). `sudo -n` works → human fix ~30 min, NOT on demo critical path (bare-metal run.sh ships).
- onnxruntime: 8 threads optimal; 16 worse (HT contention). quantize_dynamic renamed in ORT 1.29.

## 5. OSS stack (validated)

- ModernBERT-base 149.6M, Apache-2.0, ships official ONNX incl. int8 (sanity anchor at /tmp/mlops-bench/).
- transformers now v5.x → **pin 4.57.6** for training/export; optimum-onnx 0.1.0 unusable (pins <4.58, no custom heads) → hand-rolled export.
- Snorkel 0.10.0 frozen (2024-02) → REJECTED; deterministic LFs.
- qwen3:4b (2.33 GiB) SHIPS as runtime LLM; qwen3:8b (4.87 GiB) dev-time/baseline only. **Ollama contract: /api/chat + think:false + format:<schema> on EVERY call** (/no_think broken; 0.33.3 doesn't fix it).
- MiniLM-L6-v2 ✓; near-dup: numpy cosine 20-25 ms/110k vectors throttled; threshold from measured embedding curve (template twins hit 0.81; distinct pairs max 0.62).
- Label Studio 28,231★ Apache-2.0 active (needs docker — optional). Blind labeling may use a simple local web form instead.
- Node v26.4.0 / npm 12.0.2 ✓; React 19.2.8 + TanStack + Recharts 3.10.1 + shadcn 4.21.0 verified compatible.
- pandas 3.0.5 / pyarrow / sklearn 1.9.0 cp314 wheels ✓; uv 0.11.29 present; torch NOT installed locally (cp314 CPU wheel exists when needed).
- Not a git repo → git init at build start.

## 6. Demo & claims (validated/corrected)

- Adversarial suite: 10 §B.3 + 5 new (Baghjan narrative, Assamese script, codes-only "LOTO not applied", own synthetic row, first-aid non-SIF). **Drill filter was entirely missing** — added. Codes-only path added (min-20-char validator was eating attack #4-class inputs).
- Near-dup index must include synthetic corpus; threshold measured, not guessed.
- Latency SLAs revised: classify <100 ms p95 unthrottled; bulk ≥30/s sustained (≥500/s impossible); demo bulk step precomputed.
- Citation fix: ~20% SIF potential = share of RECORDABLE INJURIES (BST/Mercer ORC 2011; Martin & Black 2015), not near-miss reports.
- Baghjan framing: "precursors existed and were buried — we make them impossible to bury" (WOC 48h→12h, BOP pulled before cement set, contractor John Energy, no officer on site).
- Gold CI corrections: 300@20% → [0.739, 0.919]; 500@≥40% enriched → width ≤0.12; n=1000 → [0.794, 0.893]. Handoff's intervals were wrong — never quote them.
- Span metric: substring-validity 100% + token-F1 ≥0.80 vs adjudicated spans (100-report subset). "Exact-match ≥95%" was unattainable.
- Hindi: ~30-string cloud-QA'd phrasebook, UI chrome only.
- OIL vocabulary: 24-term list + 3 contractor-register example reports in `phase1-architecture/hse-domain-reviewer.md`.

## 7. Open risks after planning

1. **CPU clamp unresolved** (human H0) — all latency numbers provisional.
2. Docker fix pending (human H0, non-critical).
3. T4 allocation best-effort day-to-day (auto-detect cell covers).
4. Label-spec freeze decisions pending (D2 span fallback, D15 SIF definition) — Day-1 H2.
5. HSE data_risk score 7 (domain reviewer): no real OIL data exists — mitigated by honest eval design (D8) but never fully closable.
