# Phase-0 Validation: Kaggle MCP Training Environment (PS 26165)

Validator: phase0-validator (Kaggle cluster) · Date: 2026-09-07 20:41–20:46 UTC · All values measured live on this machine via Kaggle MCP unless marked INFERRED.

## Method
Two GPU script-kernels created via `save_notebook` (`kernelType=script`, `language=python`, `enableGpu=true`, `kernelExecutionType=SaveAndRunAll`), polled via `get_notebook_session_status`, outputs read via `list_notebook_session_output` / `download_notebook_output`.
- Run 1: `beakthoven/sif-phase0-gpu-probe` v1 (kernel_id 133475761) — full probe (nvidia-smi, torch, CPU/RAM/disk, file round-trip).
- Run 2: `beakthoven/sif-phase0-t4-probe` v1 (kernel_id 133475889) — retry with `machineShape="nvidiaTeslaT4X2"` explicitly requested.

## Measured findings (per-run evidence in kernel logs)

| Probe | Run 1 (default GPU) | Run 2 (T4×2 requested) |
|---|---|---|
| GPU model | Tesla P100-PCIE-16GB | Tesla P100-PCIE-16GB |
| GPU count | 1 | 1 |
| nvidia-smi rc | 0 (driver 580.159.04, CUDA 13.0) | 0 |
| torch preinstalled | 2.10.0+cu128, cuda avail=True, count=1 | 2.10.0+cu128, count=1 |
| torch↔GPU compat | **FAIL: sm_60 below torch min sm_70** (explicit UserWarning; supports sm_70–sm_120) | same FAIL |
| Python | 3.12.13 | — |
| CPU / RAM / disk | 4 cores / 31.3 GiB (32,870,488 kB) / 21.0 GB total, 20.9 GB free on `/kaggle/working` | — |
| Wall-clock create→COMPLETE | ~95 s (20:41:53→20:43:28) | ~90 s |
| GPU quota charged | 19.116 s | +12.825 s (31.941 s total) |

Quota (measured `get_accelerator_quota` before/after): GPU 108000 s total = **exactly 30 h/week**, 0 used before, 31.941 s after both probes; reserved 0; refreshes 2026-09-12. TPU quota also present: 72000 s, unused.

Artifact path (write→retrieve): **VERIFIED end-to-end.** Worker wrote `/kaggle/working/probe_result.json` (68 B) → listed by `list_notebook_session_output` → `download_notebook_output` returned signed kaggleusercontent URL → `curl` from this machine: HTTP 200, 68 bytes, payload byte-identical (`{"ok": true, "ts": 1788813749.37..., "marker": "sif-phase0-26165"}`).

## Verdicts vs HANDOFF claims

| Claim | Verdict | Evidence |
|---|---|---|
| Training compute = Kaggle via MCP | VERIFIED | 2 sessions created, ran, completed; outputs retrieved |
| 2x NVIDIA T4 GPUs | **FAILED → CORRECTED: 1x Tesla P100-PCIE-16GB** | Two independent runs both got a single P100; explicit `machineShape=nvidiaTeslaT4X2` ignored/overridden by backend |
| ~30 GPU-h/week quota | VERIFIED | 108000 s measured; billing sane (31.9 s for two ~90 s probes; boot largely unbilled, INFERRED) |
| (Implicit) preinstalled torch usable for GPU training | **FAILED** | torch 2.10.0+cu128 lacks sm_60 kernels; `torch.cuda.is_available()`=True is misleading — first CUDA kernel will raise "no kernel image". Fix: install sm_60-capable torch (e.g. ≤2.6/cu124) in-session with `enableInternet=true`, or get T4s |
| Notebook can write file & we can retrieve it locally | VERIFIED | byte-identical round-trip, curl 200 |

## Cleanup
Both sessions COMPLETE, 0 s reserved — nothing to cancel. The two probe kernels remain on account `beakthoven` (private scripts, ~zero cost; no MCP delete tool exists). Scratch: /tmp/probe_url.txt, /tmp/probe_result_dl.json.

## Impact on build plan
P100-16GB (not 2x T4): no tensor cores → fp16 speedup limited, expect ~2–4x slower mixed-precision than T4 (INFERRED from arch); 16 GB VRAM still ample for ModernBERT-base batch 32 seq128. 30 h/week quota is real and untouched. Mandatory plan change: pin an sm_60-compatible torch wheel in the training notebook or resolve T4 allocation before Day-1 training; re-probe session type each training day (allocation may vary, INFERRED).
