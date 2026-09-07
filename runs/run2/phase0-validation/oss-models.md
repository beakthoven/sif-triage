# Phase 0 Validation — Cluster: Model repos + OSS stack availability
Validator: phase0-validator (oss-models) | Date: 2026-09-08 | Method: live probes on this machine (HF API, PyPI JSON, Ollama registry, Docker Hub API, `gh` CLI as beakthoven, npm registry). Nothing taken from HANDOFF.md at face value.

## Findings

| # | Claim | Measured (today) | Verdict |
|---|---|---|---|
| 1 | answerdotai/ModernBERT-base: Apache-2.0, ~149M, ONNX-tagged | license=apache-2.0; params F32=149,655,232; `onnx` tag present; repo itself ships `onnx/model.onnx` + int8/uint8/q4/fp16 variants (official exports exist, better than claimed); 4.75M downloads; lastModified 2025-01-15 | VERIFIED |
| 1b | ModernBERT-large variant | exists; apache-2.0; 395,881,664 params; `onnx` tag; community mirror onnx-community/ModernBERT-base-ONNX also exists | VERIFIED |
| 2 | sentence-transformers/all-MiniLM-L6-v2 | apache-2.0; 22.7M params; onnx+openvino tags; 251.4M downloads; lastModified 2026-06-01 (alive) | VERIFIED |
| 3 | PyPI stack availability | transformers 5.16.1 (Apache-2.0), optimum 2.3.0 (Apache), onnxruntime 1.29.0 (MIT), snorkel 0.10.0 (Apache-2.0), fastapi 0.141.1 (MIT), sqlmodel 0.0.42 (MIT), psycopg 3.3.5 (LGPL-3.0-only), pydantic 2.13.5 (MIT), scikit-learn 1.9.0 (BSD-3), datasets 5.0.1 (Apache-2.0), torch 2.14.0 (Apache-2.0+BSD/BSL/MIT bundle) | VERIFIED |
| 3a | snorkel maintenance | last PyPI release 0.10.0 = 2024-02-27 (2.5 yrs stale); GitHub snorkel-team/snorkel: 6,005★, NOT archived, last push 2026-06-08 → commits trickle, releases dead | PARTIAL |
| 3b | torch CPU wheel (linux) size | PyPI manylinux x86_64 wheel = 528 MB (CUDA-bundled). CPU-only `torch-2.14.0+cpu-cp312-manylinux_2_28_x86_64.whl` EXISTS in download.pytorch.org index (filename measured); size UNVERIFIABLE — server 403s HEAD/range from this machine | PARTIAL |
| 4 | Ollama registry qwen3:8b (~5GB Q4_K_M) + qwen3:4b | both manifests resolve: 8b = 5,225,387,677 B (4.87 GiB ≈ 5 GB ✓); 4b = 2,497,293,444 B (2.33 GiB). Local ollama 0.32.5 installed | VERIFIED |
| 5 | Docker Hub postgres:16 + pgvector pg16 | postgres:16 updated 2026-08-26, 160 MB. pgvector/pgvector tags: `pg16`, `0.8.6-pg16` (bookworm+trixie), updated 2026-08-13, ~156–161 MB | VERIFIED |
| 6 | Label Studio 28.2k★ Apache-2.0 actively maintained | 28,231★; license Apache-2.0 (API spdx_id + LICENSE file); pushed 2026-09-07 (yesterday); latest stable 1.23.0 (2026-03-13); nightly builds active | VERIFIED |
| 7 | node/npm LTS availability + local toolchain | local: node v26.4.0, npm 12.0.2; current LTS line = v24.20.0 "Krypton". Local is newer-than-LTS — fine for Vite/React builds | VERIFIED |
| 8 | shadcn/ui + TanStack Table/Query + Recharts React-19 compat | react latest = 19.2.8; @tanstack/react-table 9.2.4 peer `react>=18` ✓; @tanstack/react-query 5.102.8 peer `^18||^19` ✓; recharts 3.10.1 peer `^16..^19` ✓; shadcn CLI 4.21.0 exists + official ui.shadcn.com/docs/react-19 returns HTTP 200 | VERIFIED |

## Flags (not in original claims — new findings)
- **transformers is now v5.x** (5.16.1). optimum 2.3.0 declares `transformers>=4.29` (no upper bound) but ONNX export of ModernBERT under transformers v5 is UNTESTED — pin/verify before training; consider transformers 4.x pin as fallback. INFERRED risk.
- **optimum[onnxruntime] now resolves to split package `optimum-onnx` 0.1.0** (v0.1, brand new) — integration risk for the int8 export path; smoke-test export early (Day-1 plan already does this).
- psycopg3 is LGPL-3.0-only — fine as a linked library; note it if ever distributing modified psycopg.
- snorkel releases stale since 2024-02 — code works (Apache-2.0) but treat as frozen; alternatives (skweak, manual LF aggregation) if 0.10.0 breaks on Python 3.12+.

## Commands used
`curl huggingface.co/api/models/{answerdotai/ModernBERT-base,answerdotai/ModernBERT-large,sentence-transformers/all-MiniLM-L6-v2}` (+ /tree/main/onnx); `curl huggingface.co/api/models?search=ModernBERT onnx`; `curl pypi.org/pypi/<pkg>/json` ×11 (+ license_expression, snorkel release dates, optimum requires_dist, torch wheel listing); `curl download.pytorch.org/whl/cpu/torch/` (index); `curl registry.ollama.ai/v2/library/qwen3/manifests/{8b,4b}` (layer-size sum); `curl hub.docker.com/v2/repositories/{library/postgres/tags/16, pgvector/pgvector/tags?name=pg16}`; `gh repo view/release list -R HumanSignal/label-studio`; `gh api .../license`; `npm view react|@tanstack/react-table|@tanstack/react-query|recharts|shadcn version/peerDependencies`; `curl nodejs.org/dist/index.json`; `node --version`; `ollama --version`.

## Summary
Nothing dead, renamed, or license-hostile. 8/11 claims fully VERIFIED; 2 PARTIAL (snorkel release staleness; torch CPU wheel size unmeasurable from here though wheel exists). No FAILED. Two new risks logged: transformers-v5 × optimum-onnx-0.1.0 export path (untested combo), both mitigated by the existing Day-1 smoke-test gate.
