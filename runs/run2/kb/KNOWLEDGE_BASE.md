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
- Hindi: 33-string cloud-QA'd phrasebook, UI chrome only.
- OIL vocabulary: 24-term list + 3 contractor-register example reports in `phase1-architecture/hse-domain-reviewer.md`.

## 7. Open risks after planning

1. **CPU clamp unresolved** (human H0) — all latency numbers provisional.
2. Docker fix pending (human H0, non-critical).
3. T4 allocation best-effort day-to-day (auto-detect cell covers).
4. Label-spec freeze decisions pending (D2 span fallback, D15 SIF definition) — Day-1 H2.
5. HSE data_risk score 7 (domain reviewer): no real OIL data exists — mitigated by honest eval design (D8) but never fully closable.

## 8. Build-phase facts (added 2026-09-08, Day 1)

- **CPU clamp RESOLVED 2026-09-08 morning** (see /CPU_CLAMP_REPORT.md): unclamped measurements — qwen3:4b 22.7/157.7 tok/s; all-core load holds 3.25/4.7 GHz. Watch item: 99°C under synthetic burn (thermal, not platform).
- **Ollama server was found stopped** (pid 48245 gone) — restarted via `nohup ollama serve`. For demo: server autostart must be part of run.sh / boot checklist.
- **Corpus built** (artifacts/corpus/): train 61,378 / val 6,820 (employer-group-disjoint) / test 17,731. Test prevalence 64.23% matches spec v2 64.21%. Boundary screen: 12 dropped at J≥0.5. Train/val employer overlap = 0. Zero residual outcome stems in 85,929 masked rows.
- **ASRS Events_Anomaly** is a semicolon-separated list — anomaly screening must test EVERY element, not the first (first-element logic would under-screen).
- **Synthetic generation**: 8,811/9,036 rows; ei_d resumed (45→270); cs_d has 76 within-file dup 8-grams + 1 leak → QA gate handles. Generator self-checks use the frozen masking._PATTERN directly.
- **Export-gate production recipe** (GREEN on 2x T4): torch.onnx.export(dynamo=True, opset_version=18) → strip value_info → quantize_dynamic(QInt8). Legacy TorchScript exporter BANNED for ModernBERT@4.57.6 (Δlogit ~1.0). fp32 parity 1.1e-5..4.4e-5; int8 binary agreement 100%. 583 GPU-s consumed.
- Label spec FROZEN v1.0.0, sha256 db94628372c076f0d37429cdfe81e3e9d301751d376b163a7fcbc399c73b2f51. **Hash convention (documented 2026-09-09, resolves the audit's db946283-vs-96114b09 mismatch):** spec_sha256 = hash of the file with the self-referential `spec_sha256:` line excluded (`grep -v '^spec_sha256:' spec/label_spec.yaml | sha256sum` → db946283…, re-verified). The raw file-bytes hash at freeze was 96114b09… — that is the per-file hash in the Kaggle staging manifests. Bookkeeping only; frozen content byte-identical to commit 106b37a.
- **Synthetic share of train (corrected 2026-09-09):** 13.6% = 9,687/71,065, measured on `train_final_v4.jsonl` (osha 49,343 / asrs 12,035 / syn 9,687). Supersedes D16's "~10%" v3-era planning estimate — quote 13.6%.
- **Deadline: 2026-09-10 15:00 IST** (~57h from Day-1 05:40). Cron checkpoints: T-31h (Sep 9 08:00), T-19h (Sep 9 20:00 gold gate), T-6h (Sep 10 09:00 final gate), T-2h (Sep 10 13:00 rehearsal gate).

## 9. Mid-build facts (added 2026-09-08 ~11:30 IST)

- **Kaggle MCP cannot create datasets** (no create_dataset tool; blob uploads succeed but dataset finalize is permission-denied) → corpus staged via catbox HTTPS + sha256 manifest (see runs/run2/day1/staging/STAGING.md). Kernel outputs chain via /kaggle/input datasets.
- **Kaggle subagent timeout risk is real**: 2h cap hit mid-pipeline. Kernel templates + staging manifest + retrieve.py must always be on disk BEFORE the agent needs them (they were — recovery was possible).
- **Masked config val metrics (ep3)**: AUC 0.9961, AP 0.9987, recall@p>=0.80 = 1.0 @ threshold 6.1e-5, rules macro-F1 0.967 (confined_space low-support 9 rows, F1 0.714), span token-F1 0.995, temperature 1.696, 726s/epoch on T4. REMINDER: derived-label val; gold is the honest eval.
- **Near-dup**: MiniLM index 70,398×384 fp16 = 54.1MB, load 0.1s, nearest p95 3.8ms. Measured threshold 0.91 (verbatim 1.0; 2-3-word twins p5 0.895; template max 0.907; masked-text pastes p5 0.872 — partial coverage, disclosed). **D24**: index = train_final_v2 minus the 6 synthetic demo-card rows (rebuilt with `embed_corpus.py --exclude-ids artifacts/demo/demo_corpus.jsonl`); full-corpus original kept as `corpus_index_full_backup.npy`.
- **MiniLM pooling**: masked mean-pool + L2 norm (NOT CLS); reproduces sbert.net reference to 4.5e-5.
- **Explanation layer**: qwen3:4b thinks INSIDE JSON string fields on open-ended rewording even with format+think:false — fix = template-only user message + one-shot example. Score-mutation guard needed (model mutated 0.28→0:28). Cache TTL 300s for template-fallback entries.
- **Ollama concurrency**: OLLAMA_NUM_PARALLEL=6 mandatory (default 1 slot = serial). ~13s/row zero-shot under 6-thread load.
- **Demo corpus**: 13 cards + bulk_ingest_5k.csv (5,050 rows; Kathalguri re-rank beat: #2 n=31 → #1 n=96; holds only if model flags all 96 target-cell rows — verify with real ONNX Day 3).
- **Well-control register conflict**: "kill line/kill mud/killed the well" hits the frozen outcome stem 'kill' — synthetic WC register uses bullhead/choke/weighted mud instead.
- **train_final_v3.jsonl = 70,565 rows** (vocab gate 24/24 PASS; synthetic pool 9,187).

## 10. Integration-phase facts (added 2026-09-08 ~18:00 IST)

- **Ship config: masked-v1, int8, single-text path.** Val: AUC 0.9966, macro-rule-F1 0.9672, span tok-F1 0.9948, T 1.684. Derived TEST (n=17,731): AUC 0.8629 — the val↔test gap is v2-era label-map degradation + val saturation, NOT a bug (val control reproduces torch exactly).
- **Ship operating point (D19+D27): raw 0.821855 / calibrated 0.712581 → P 0.8001 / R 0.9736 / F1 0.8770 on full derived test, single-text path.** The val-frozen 6.58e-5 is vacuous (val prevalence 79.4% ≈ precision floor → flags everything). Recall@P0.85 = 0.844, @P0.90 = 0.515. Gold applies the same per-row path.
- **Training report's "ship fp32" recommendation is SUPERSEDED by D20**: its int8-RED was measured on Kaggle hardware (ΔAUC 0.0916); on the demo machine int8 full-val AUC 0.9937 vs torch 0.9966 (Δ0.0029 PASS) and decisions are int8≡fp32 on all probed cards. Quantization is provider-sensitive — documented.
- **int8 batch-composition shift (D27)**: dynamic quantization computes scales per tensor per batch — batchmates shift each other's logits (mean |Δp| 0.031). Batch-32 int8 classification is ILLEGAL in production; the app classifies per-row everywhere. fp32 is batch-invariant (Δ=0.0).
- **McNemar at ship threshold (n=1500 shared sample, Holm-corrected)**: finetune F1 0.8803 > tfidf 0.8721 (p 0.080 n.s.) > zeroshot 0.8538 (finetune significantly better, p 8.7e-4) >> regex 0.4747 (p 2.2e-67). "Beats an 8B zero-shot LLM at 1/1083rd per-classification latency" is now a measured claim.
- **Latency (masked-v1, superseded — see §12 for the v2 final)**: p50 11.9 / p95 19.7 / p99 40.2 ms single-text; bulk ingest 33.73 reports/s (SLA ≥30/s PASS; 5,050 rows in 149.7s under load).
- **Ablation read**: masked ≈ unmasked on val (ΔAUC +0.0001); masking neither helps nor hurts at saturation — final word on the gold set.
- **Demo cards**: 13 cards verified vs real model; 3 behavioral deviations (first-aid FP → D21 retrain; long-report negation gate → fixed suite expectation; codes-only stale mock annotation). Kathalguri beat: 96/96 flagged, #1 confirmed. Rule-attribution drift on 7 cards → narrate probability bar (D22).

## 11. Post-review + ship facts (added 2026-09-08 ~23:15 IST)

- **SEV1 rule-logit order scramble** (found by review swarm): ONNX rule_logits in train.py order, app zipped alphabetical — 6/7 rules mislabeled. Fixed + self-check against train.py. D22 "rule drift" was THIS bug — ruling re-opened and resolved; contrast-red now LoF-dominant as scripted.
- **Positional dead zone**: CLS pooling discounts mid-window tokens; stride 96→64 cut decisive-safe valleys 12→2; residual = gray-band routing (honest). 10k-char input cap added (200k chars: 15.9s → 0.63-1.22s).
- **Span head is effectively dead at runtime** (max token prob ~0.3, fires on punctuation; val token-F1 0.995 does not reproduce) → the D2 keyword-attribution fallback is the de-facto live path; spans now meaningful phrases ('welding', 'sparks', 'LOTO'). The span-F1 gold metric must be measured against THIS reality (token-F1 vs adjudicated spans may be low — headline extraction metric becomes substring-validity + keyword-anchor precision).
- **SQLite concurrency**: single shared connection corrupted under any concurrent read; RLock everywhere → 0 failures in all probe modes; throughput cost none (8-thread useful throughput +87%).
- **int8 batch shift + tuned-op parity**: int8 vs fp32 decision agreement at the tuned op: 97.7-98.3% (fails 99.5% leg) — acceptable because op is tuned on the int8 single-text chain itself; fp32 fallback documented as NOT decision-equivalent.
- **Ship: masked-v2 int8.** Op-point raw 0.746401/cal 0.658108 → P 0.80003 / R 0.9748 / F1 0.8788 (full derived test, single-text). First-aid FP fixed (card 0.153; 0/20 unseen paraphrases flagged). McNemar: v2 ≈ v1 (p 0.51); both >> regex, > zeroshot (p 0.0018); tfidf vs ft-v2 n.s. (0.122) — disclosed.
- Gold pipeline ready: score cache fingerprint-keyed (auto-rescores on model swap); 500 items pre-scored with v2.
- Demo DB re-seeded with scrubbed CSV (5,048 rows); tarball rebuilt with v2.

## 12. Audit-wave final verification (added 2026-09-09 ~23:00 IST; full detail: runs/run2/day2/latency_v2_final.md)

- **Machine unclamped verified**: 16-thread burn holds 3.44–4.76 GHz (mean 3.94). Idle scaling_cur_freq 1.3–2.4 GHz is normal amd-pstate downclock, NOT the clamp. Thermal watch: Tctl ~99–100°C under sustained all-core load — bulk-phase measurements taken heat-soaked read ~45% slow; measure in cool windows.
- **masked-v2 final latency (int8 single-text ship path)**: model-only p50 11.4 / p95 17.7 / p99 20.5 ms (200 real test rows); seq128 p50 21.1 / p95 24.6 / p99 27.8 ms; fp32 fallback seq128 p50 44.2 ms. Live API e2e (gates + MiniLM near-dup incl.): p50 28.0 / p95 56.0 ms real rows; seq128 p50 42.5 / p95 46.9 ms. Bulk ingest **45.56/s** (5,048 accepted in 110.8s, SLA ≥30/s PASS).
- **FIXED (SEV2 perf): OpenBLAS spin threads starve the next ORT run.** The near-dup matmuls (BLAS gemm/gemv) left spinning workers; the following classify predict went 21→77–97 ms; live /api/classify was ~150 ms. Fix: `threadpoolctl.threadpool_limits(1, "blas")` around the 3 matmul sites in app/storage.py (`_blas_single_thread`, no-op fallback if absent; dep added to requirements.txt). Full ship path 127→28 ms; live API 150→42.5 ms p50; bulk ingest 37.3→45.6/s. Takes effect on server restart (live stack restarted 22:08 IST with the fix).
- **masked-v2 positional dead zone worse than v1 — FLAGGED, not re-baselined (Sep 9 23:10).** postreview_fix_check [2] probe: v1 min 0.251, 2/16 valleys; v2 min 0.030, 13/16 valleys at 0.03–0.38, BELOW the gray band → fails the equivalent-in-kind bar on the probe. But real-input exposure is small: only 153/17,731 test rows are multi-window; on 60 real long rows v1 ≈ v2 (mean 0.951/0.942, 3 flips both ways, 1/60 v2 silent-green <0.40). App plumbing exonerated (D27 solo-window parity delta 4e-5). Mitigations for T-6h gate: accept+disclose, or gate `chunked + score<0.40 → review`, or v1 fallback (not recommended). Test deliberately left failing.
- **Regression battery vs masked-v2 (test ports, throwaway DBs)**: api_smoke PASS (incl. 8th gate well_control_watch + persist=1), adversarial 18/18 PASS, onnx_classifier_check PASS, near_dup_embed_check PASS, explain_check PASS, pattern_mine_selfcheck PASS, demo_pack_selfcheck PASS; postreview_fix_check FAIL on the positional probe above only. Log: runs/run2/day2/regression_log.txt.
- onnx_classifier_check.py + postreview_fix_check.py now honor SIF_MODEL_PATH (default masked-v2).
- **D29**: chunked-low-score gate (9th gate) ships; v2 positional dead-zone residual converted to gray-review routing.
- **BLAS threadpool fix**: OpenBLAS spinning workers starved onnxruntime — threadpool_limits(1) around matmuls; live API p50 150→42.5ms, ingest 37.3→45.6/s.
- **masked-v2 final latency (unclamped, measured)**: model p50/p95/p99 = 11.4/17.7/20.5 ms; API e2e p95 46.9ms; ingest 45.6/s.

## 12. Gold results (added 2026-09-10 ~03:50 IST)

- **All 4 label queues complete** (801 raw judgments, 500 items). Headline (human-consensus, all-4): real pooled n=313 — **P 0.838 / R 0.824 / F1 0.831**; OSHA stratum P 0.838 / R 0.895. κ (doubles, n=130) = 0.346; pilot κ 0.296.
- **Labeler C outlier** (behavioral: 2s median/item, 6-items/s bursts, 0.27 label rate vs 0.58-0.70, worst pairwise): noC sensitivity → P 0.990 / R 0.809 / κ 0.491; 37/38 OSHA FPs are C-solo labels. Headline stays all-4 (no exclusion to defend); noC disclosed in appendix.
- **LLM panel (cloud, rubric-fed, blind)**: per-model agreement with human consensus 0.68-0.71; 4-model majority 0.7253 (OSHA stratum 0.82, ASRS 0.54, synthetic 0.53). Reported-only transparency metric; never touched a label.
- **LLM adjudication panel (user decision D30)**: 4 models × 3 personas ruled the 100 disputed items (72 SIF / 22 non-SIF / 6 tie-unsure). Supplementary variant: real pooled n=394 — P 0.838 / R 0.726 (disputed items are disproportionately model-misses the panel calls SIF — the "hard cases" effect, disclosed).
- **ASRS stratum: recall 0.00 (19/19 missed, max p 0.0017)** — aviation is fully OOD; also self-inflicted (ASRS is train-only-negatives). Deck must disclose.
- **Synthetic stratum: P 0.265-0.357** — conservative over-flagging of mechanism-rich near-miss negatives; the review-queue containment story.
