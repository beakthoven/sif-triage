# VALIDATION LOG — run2 (Doctrine 1: independent re-validation)

Phase 0 complete: 10/10 validators ran 2026-09-08, all claims re-measured on this machine.
Artifacts: `phase0-validation/*.md`. Aggregated scores: `phase0-validation.aggregated.json` (if generated).

| # | Fact cluster | Verdict | Key evidence |
|---|---|---|---|
| P0-1 | OSHA CSV structure + stats | VERIFIED (3 corrections) | 105,996×28 ✓; narrative stats to the digit; OIICS 2024 break ✓ (double-space 0.18%→66.11%); dups=66 ✓; oil-gas NAICS 2.60% ✓; vocab rarity ✓; P(Amp>0\|'amputat')=98.6% ✓ |
| P0-2 | OSHA→IOGP coverage proxy | VERIFIED (load-bearing claims) | PTW effectively 0 rows (only 1 of 3 "permit" hits is real PTW); Bypass 0.08–0.09% ✓; LoF dominant 39.6–45.1% ✓; top-3 = 66.7–68.9% >65% ✓. Per-rule CS/EI numbers proxy-dependent |
| P0-3 | NASA ASRS | VERIFIED | 47,723 rows exactly; Apache-2.0; ungated; 270/30/33MB; 302→CDN ✓. **No label column** (summarization task; derive weak labels from Events_Anomaly/Assessments) |
| P0-4 | SmartQHSE + synth HF sets | 1 FAILED | major-psi: 15 vignettes CC-BY-4.0 ✓ (use raw URLs, datasets-server broken); extended: 44 rows not 40; **nigeria-synth: FAILED — 5 categorical columns, zero prose, useless as style reference** |
| P0-5 | Kaggle GPU session | **2 FAILURES** | **GPU = 1x Tesla P100-16GB, not 2x T4** (T4 machineShape request ignored, 2 runs); **preinstalled torch 2.10.0+cu128 lacks sm_60 → CUDA ops crash on P100**; quota 30h ✓; artifact write→retrieve path byte-identical ✓; worker: py3.12.13, 4 CPU, 31.3GiB RAM, 21GB disk |
| P0-6 | Machine + Ollama | VERIFIED w/ 1 CORRECTED + 1 NEW | CPU/RAM/disk/GPU spec ✓ (gfx1152 inferred); **bench CORRECTED: currently 3.7–4.4 tok/s gen — all cores clamped to 0.85GHz** (41.5°C, performance governor; historical log shows 146.8/22.9 achievable); JSON-schema output ✓ verbatim spans; qwen3:4b RSS ~3.2GB ✓; **NEW: `think:false` ignored by 0.32.5+qwen3:4b on /api/generate → use /no_think or /api/chat** |
| P0-7 | OSS stack + models | VERIFIED (2 new risks) | ModernBERT-base 149.6M Apache-2.0 ✓ **ships official ONNX incl. int8**; MiniLM ✓; qwen3:8b 4.87GiB ✓; postgres16/pgvector images ✓; Label Studio 28,231★ Apache-2.0 active ✓; React19 stack ✓. **RISK: transformers now v5.16.1; optimum[onnxruntime] pulls brand-new optimum-onnx 0.1.0 — int8 export path untested under this combo**; Snorkel last release 2024-02 (frozen, repo alive) |
| P0-8 | Network + endpoints | VERIFIED | OSHA zip live, md5 byte-identical to local copy; HF/pypi/docker-hub/github/ollama-registry all 200; worst latency 2.1s |
| P0-9 | Toolchain | **1 FAILURE** | pandas/pyarrow/sklearn/torch cp314 wheels all exist (no py3.14 risk) ✓; uv present ✓; node 26.4.0 ✓; torch not installed ✓ (CPU wheel available); **docker daemon inactive/disabled, no compose plugin, user not in docker group — FAILED**; not a git repo |
| P0-10 | Prior artifacts + PS data | VERIFIED | 226 PS (172 SW) ✓; 26165 empty dataset link ✓; all_blocks.json = 155 verdicts ✓; aggregator reproduces byte-identically ✓; 26165 rank 1/8 phase3 (but 18/24 phase1); pipeline scripts stdlib-only, no bit-rot |

## Corrections register (plan changes forced by re-validation)

| # | Correction | Impact | Plan change |
|---|---|---|---|
| C1 | Kaggle GPU = **1x P100**, T4 request ignored; torch 2.10+cu128 incompatible (sm_60) | Training crashes without fix | **SUPERSEDED by Phase 1 kaggle-infra probe:** phase0 used an invalid enum (`nvidiaTeslaT4X2`); correct enum `NvidiaTeslaT4` returned **2x T4 (sm_75)** live, torch 2.10+cu128 runs natively. P100 fallback = reinstall torch **cu126** (still ships sm_60; cu128+ dropped Pascal) — NOT a ≤2.6 downgrade. Protocol: auto-detect GPU cell in every notebook + export-gate kernel before training. |
| C2 | **Docker daemon down**, no compose | Offline packaging + Label Studio + demo compose blocked | Human task: enable docker (root) early — Day 1, not Day 3. Fallback: rootless docker or podman; absolute fallback: bare-metal run scripts + tarball |
| C3 | **CPU clamped 0.85GHz now** → LLM 4 tok/s | Live-LLM demo layer at risk if condition persists | Precompute-everything doctrine already covers it; monitor; investigate power profile before demo; never make live LLM load-bearing |
| C4 | transformers v5.x + optimum-onnx 0.1.0 | ONNX int8 export path untested | Export smoke-test gate BEFORE training (handoff order: export probe first); pin transformers 4.x + optimum 1.x in notebook if v5 breaks; official ONNX exports of ModernBERT-base exist as sanity reference |
| C5 | Nigeria synth dataset has no text | Style reference for OIL-register gone | Synthetic corpus style anchored on OSHA narratives + SmartQHSE vignettes + DGMS/OISD vocabulary instead |
| C6 | ASRS has no label column | Near-miss negatives need weak labels | Derive from Events_Anomaly / Assessments.1_Primary Problem fields; treat as register/negative source only (as planned) |
| C7 | Amputation counts 0–2 (not 0–6) | Label binarization unaffected (>0) | No change; note corrected range |
| C8 | "An employee was" opener = 63.6% (70.9% = contains-anywhere) | Template-overfitting risk slightly lower | Keep de-boilerplate mitigation |
| C9 | 70.4% outcome-leakage is word-list dependent (76.4% w/ alt list) | Direction unchanged | Outcome-masking stays mandatory; define mask list explicitly in label spec |
| C10 | Ollama 0.32.5 ignores `think:false` on /api/generate with qwen3 | Wasted tokens/latency on reasoning | Use /api/chat + /no_think; consider bumping Ollama ≥0.33 as handoff suggested |
| C11 | Snorkel releases frozen at 0.10.0 (2024-02) | Weak-supervision dependency stale | Keep (stdlib-level usage) or replace with plain heuristic label functions; decide in Phase 1 |
| C12 | Not a git repo | No version control safety net | git init at build start |

## Session-direct checks (orchestrator, pre-swarm)

- gh auth as beakthoven: VERIFIED. Ollama 0.32.5 + serve running + qwen3:4b pulled: VERIFIED.
- Kaggle GPU quota 108000s (30h), 0s used, refresh 2026-09-12: VERIFIED (post-probe: 31.9s used).
- data/ files present, pipeline/aggregate_scores.py source read: VERIFIED.
