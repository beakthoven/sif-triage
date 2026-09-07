# Phase 1 — Kaggle/GPU Training Infrastructure (PS 26165)

Validator: kaggle-infra-engineer · 2026-09-08 · VERIFIED = measured live today via Kaggle MCP probe (kernel `beakthoven/sif-phase1-t4-probe`, id 133477027), PyPI/GitHub APIs.

## 1. Findings (numbers)

- **F1 T4x2 IS obtainable — C1 was a wrong enum, not a hard limit.** Phase 0 passed `machineShape="nvidiaTeslaT4X2"` (silently ignored). Passing `machineShape="NvidiaTeslaT4"` today returned **2x Tesla T4, 15,360 MiB each, driver 580.159.04** (VERIFIED, nvidia-smi). Matches kaggle-api issue #821: `machine_shape` in kernel metadata is the working mechanism.
- **F2 Preinstalled torch 2.10.0+cu128 WORKS on T4** (sm_75 ∈ arch_list sm_70…sm_120; CUDA matmul+reduction executed OK). **No torch pin needed on the T4 path.** The sm_60 breakage is P100-only.
- **F3 Quota billing is trivial:** T4x2 probe (full create→run→complete) billed **12.764 GPU-s**; total used 44.7s / 108,000s. Boot largely unbilled; T4x2 did not double-bill in this probe (VERIFIED; INFERRED it generalizes).
- **F4 Internet in-session VERIFIED:** pypi.org, huggingface.co, download.pytorch.org all HTTP 200 from the kernel.
- **F5 MCP-spawned kernels have NO Kaggle API credentials** (`~/.kaggle/kaggle.json` absent; KAGGLE_USERNAME/KEY MISSING). In-kernel `kaggle datasets push` mirroring is **impossible**; MCP also exposes no secrets parameter.
- **F6 P100 contingency without downgrade:** torch **2.10.0+cu126 keeps sm_60** (Kaggle/docker-python#1546, verified on Kaggle P100; cu126 cp312 x86_64 wheel exists, sha confirmed). C1's "≤2.6/cu124" is unnecessary — keep torch 2.10 either way.
- **F7 ONNX export stack:** optimum **1.27.0** (2025-07-30) ships a `modernbert` ONNX config for **text-classification AND token-classification** (MIN_TRANSFORMERS 4.48); its `[onnxruntime]` extra pins `transformers>=4.36,<4.54` → **transformers==4.53.3**. Newer optimum-onnx 0.1.0 (2025-12-23) also has modernbert, allows transformers <4.58 → fallback **transformers==4.57.6**. Both verified in tagged source.
- **F8 flash-attn unusable on T4 (sm_75) and P100 (sm_60)** (FA2 needs sm_80+); transformers auto-falls back to SDPA (VERIFIED in source). Do not install flash-attn; no action needed.
- **F9 T4 fp16 tensor cores (65 TFLOPS)** restore the handoff's 15–40 min/run estimate; P100 fallback ≈2–3× slower (INFERRED).

## 2. Risks

- **SEV1: none.** C1 is resolved (T4x2 restored; working P100 fallback exists).
- **SEV2-1** T4 allocation is best-effort; any session can still land P100 → every kernel needs an auto-detect cell (if capability < (7,0): uninstall torch*, `pip install torch==2.10.0 --index-url cu126`).
- **SEV2-2** transformers 4.53.3 (2025) × preinstalled torch 2.10 (2026) is an untested pair → export gate (below) must run BEFORE training (C4). Fallback: 4.57.6 + optimum-onnx 0.1.0.
- **SEV2-3** No in-kernel credentials (F5) → artifact mirror = post-completion MCP retrieval only (verified byte-identical). Mid-session death loses progress → **one config per kernel, ≤45 min each**, checkpoint every epoch into `/kaggle/working`.
- **SEV3** osha.gov in-session reachability unprobed (use Kaggle Datasets); retrievability of failed-session outputs INFERRED; fp16-only (no bf16 on T4) — irrelevant at this scale.

## 3. Recommendations per architecture element

- **"Kaggle 2x T4 fine-tune"** — **ADOPT**, now literally true. Run one config per GPU via `CUDA_VISIBLE_DEVICES` subprocesses, or sequentially; **reject DDP** (debugging surface for zero need).
- **Torch pin (C1)** — **MODIFY**: primary = no pin (stock 2.10+cu128 on T4); fallback cell = cu126 reinstall. **REJECT** cu124/torch≤2.6 as primary.
- **Library pins** — **ADOPT**: `transformers==4.53.3`, `optimum[onnxruntime]==1.27.0`, `onnxruntime==1.29.0`; fallback `transformers==4.57.6` + `optimum-onnx==0.1.0`. Custom multi-task head: raw `torch.onnx.export` (dynamic axes) + `quantize_dynamic(QInt8)` — TasksManager only maps standard heads.
- **"Checkpoint every epoch → push to private Kaggle Dataset"** — **MODIFY** (F5): per-epoch ckpt + metrics + `manifest.json` in `/kaggle/working`; orchestrator retrieves via MCP after COMPLETE. Short runs are the session-death insurance.
- **Export smoke gate (C4, before training)** — **ADOPT**, exact spec: (1) GPU op assert; (2) install pins; (3) 1 fp16 training step of ModernBERT-base seq-cls (num_labels=8) + token-cls on 32 dummy texts; (4) optimum ONNX export, parity assert max|Δlogit|<1e-3 on 8 texts; (5) int8 `quantize_dynamic`, assert |Δlogit|<0.05 + report size; (6) raw torch.onnx.export of 2-head wrapper, same parity; (7) write `gate_result.json`. Est. 15 min.
- **Data staging** — **MODIFY**: OSHA CSV (55 MB) + synthetic corpus (~10 MB) as pinned Kaggle Datasets (mounted inputs, deterministic); ASRS via direct HF resolve-URLs in-notebook (F4; ~270 MB, INFERRED ≤3 min at Kaggle egress) with a Kaggle-Dataset fallback. One-time upload cost ≈5–15 min local uplink.
- **Quota budget** — **ADOPT**: gate 0.5h + 4 training configs ×1h + final retrain/export 1.5h + retries 2h ≈ **8h pessimistic / 30h**; baselines are CPU-only (0h). Re-probe GPU each session start.

## 4. Verdict

**GO.** C1 downgrades from project-killer to a one-line enum fix: 2x T4 with stock torch 2.10 is VERIFIED working today, quota billing is negligible, and a verified P100/cu126 fallback removes the last single-point-of-failure. Remaining work: the env-detect cell, the pin set, and the export gate kernel — all specified above, all cheap.
