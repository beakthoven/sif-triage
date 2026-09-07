# Phase 0 Validation — Demo Machine Profile + Ollama Benchmark
Validator: machine-ollama cluster | Date: 2026-09-08 | Method: independent re-measurement, this machine

## Findings

| # | Claim (HANDOFF §B.4) | Measured now | Verdict |
|---|---|---|---|
| 1 | Ryzen AI 7 350, 8c/16t, Zen5, AVX-512 | `lscpu`: "AMD Ryzen AI 7 350 w/ Radeon 860M", 8 cores/socket × 2 threads = 16 CPUs, family 26/model 96 (Zen 5 Krackan), max 5.09 GHz. Flags include avx512f/dq/bw/vl/bf16/vnni/vpopcntdq. llama.cpp also reports AVX512=1 VNNI=1 BF16=1 | VERIFIED |
| 2 | 30 GB RAM, ~13 used idle | MemTotal 32,118,672 kB = 30.6 GiB; used 13.2 GiB (this session + spotify running, not strictly idle); available 17 GiB; swap 30 GiB unused | VERIFIED |
| 3 | ~517 GB free on / | `df -h /`: 514 GB avail (930 G total, 45% used) | VERIFIED (3 GB drift, normal) |
| 4 | Radeon 860M iGPU gfx1152, NO NVIDIA | lspci: only `c2:00.0 AMD Krackan [Radeon 840M/860M]` PCI_ID 1002:1114, amdgpu driver, /dev/kfd present. `nvidia-smi`: not found; no NVIDIA in lspci. gfx1152 itself NOT directly measurable (no rocminfo; dmesg restricted) — inferred from PCI ID 1002:1114. "860M" confirmed via CPU model string | VERIFIED (no-NVIDIA, 860M); gfx1152 INFERRED |
| 5 | Ollama 0.32.5 | `ollama --version` + `GET /api/version` → 0.32.5. Server was already running (PID 48245). qwen3:4b present, 2.5 GB blob | VERIFIED |
| 6 | qwen3:4b ~148–161 tok/s prompt, ~21 tok/s gen (temp 0, think=false) | NOW: prompt 21.4 tok/s (287 tok, cold, server-side `prompt eval time`) and 27.8 (short prompt); gen 3.7–4.4 tok/s across 7 runs (server-side eval timings). Warm identical-prompt runs report 1069+ tok/s but are prefix-cache artifacts (server log: only 1 token re-evaluated). Root cause measured: **all 16 CPUs pinned at 0.60–0.86 GHz during sustained generation** (sampled all cores ×15 s) despite governor=performance, EPP=performance, scaling_max 5.09 GHz, Tctl 41.5 °C, AC connected. Counter-evidence: same-machine server log from an earlier instance shows task 307 at **146.8 tok/s prompt / 22.9 tok/s gen** — the claimed numbers WERE real when unthrottled. Clamp cause INFERRED: firmware/platform power limit (USB-C PD contract reads 5 V; `energy_uj` unreadable w/o root) | CORRECTED — currently 21–28 prompt / 3.7–4.4 gen tok/s; claim corroborated historically; CPU freq clamp is the live condition |
| 7 | JSON-schema structured output works | `format` param with 5-field schema (incl. enum-constrained rule): output parsed, all required keys, types correct, `rule` ∈ enum, `evidence` is verbatim-exact substring of report. 1/1 test (claim said 4/4) | VERIFIED (capability); count PARTIAL |
| 8 | RAM footprint of qwen3:4b serving | `ollama ps`: SIZE 3.2 GB, 100% CPU; llama-server RSS 3,164,960 KB ≈ 3.0 GiB; ollama serve RSS 62 MB; system used-Mem delta +2.9 GB on load | VERIFIED (~3.0–3.2 GB) |

## Extra finding (builder-relevant)
`"think": false` on `/api/generate` is IGNORED by Ollama 0.32.5 + qwen3:4b: response contains reasoning text ("Okay, the user wants me to...") and exhausts num_predict (done_reason=length). Use `/no_think` in prompt or the chat API. The claimed benchmark conditions (think=false) therefore could not be replicated as stated; with format=schema the output was still forced to clean JSON.

## Commands (all run now, this machine)
`lscpu`; `grep flags /proc/cpuinfo`; `free -g`; `df -h /`; `lspci`; `nvidia-smi`; `ls /dev/kfd`; `cat /sys/class/drm/card1/device/uevent`; `ollama --version`; `pgrep -af ollama`; `curl /api/version,/api/ps,/api/generate`; python bench (`/tmp/bench_qwen3.py`, `_v2.py`) using server-side `prompt_eval_duration`/`eval_duration`; `grep print_timing /tmp/ollama.log`; per-core `scaling_cur_freq` sampling under load; `powerprofilesctl get`; amd_pstate sysfs; `ps -eo rss` for footprint.

## Impact on build
Machine spec and Ollama functionality match the handoff; structured output + exact-span extraction work. The live LLM path currently decodes at ~4 tok/s due to a whole-CPU frequency clamp (not thermal, not governor). Demo plan already treats LLM as precomputed encore — proceed, but the clamp MUST be investigated (adapter/BIOS/firmware) before any live-LLM rehearsal; at 0.85 GHz all CPU workloads (ONNX inference, ingest) are ~6× slower than spec.
