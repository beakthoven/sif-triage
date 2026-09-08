# kernel_runner.md — Kaggle MCP runbook for training/train.py (wave 3)

One config per kernel, ≤45 min each (F5: MCP-spawned kernels have **no**
Kaggle API creds → no in-kernel dataset push; artifacts are retrieved
post-completion via MCP, byte-identical path verified by the export gate).
Two kernels total: `masked` then `unmasked`.

## Step 0 — Stage the corpus as a Kaggle Dataset (one-time)

The kernel cannot see this repo. Upload as a private Kaggle Dataset:

1. Zip/locate `train.jsonl`, `val.jsonl`, `test.jsonl` (corpus-dir contract
   documented in `training/train.py` docstring).
2. Upload via MCP `upload_dataset_file` for each of: `train.jsonl`,
   `val.jsonl`, `test.jsonl`, plus **`training/train.py` and
   `training/model.py`** (model.py is FROZEN — kernel-side sha256 must equal
   the repo file; the export gate already verified this path).
3. Note the dataset slug, e.g. `<user>/sif26165-corpus-v1`. Pin the version.

## Step 1 — Launch one kernel per config

MCP `save_notebook` (or `create_notebook_session` for interactive) with:

- `language: "python"`, `kernelType: "script"`
- **`machineShape: "NvidiaTeslaT4"`** — exact enum case (D1: the
  `nvidiaTeslaT4X2` variant is silently ignored; this enum returns 2× T4,
  sm_75, stock torch 2.10.0+cu128, no reinstall needed)
- `enableGpu: true`, `enableInternet: true`
- `kernelDataSources: ["<user>/sif26165-corpus-v1"]`

Notebook cells:

**Cell 1 — GPU auto-detect (MANDATORY in every kernel, D1).** Handles the
P100 fallback: torch 2.10.0+cu126 keeps sm_60 — never downgrade below 2.10.

```python
import subprocess, sys, torch
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    print(f"GPU: {name} capability sm_{cap[0]}{cap[1]} torch {torch.__version__}")
    if cap < (7, 0):  # P100 (sm_60): cu126 wheel still ships sm_60
        print("P100 detected -> reinstalling torch 2.10.0+cu126")
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y",
                        "torch", "torchvision", "torchaudio"], check=False)
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "torch==2.10.0", "--index-url",
                        "https://download.pytorch.org/whl/cu126"], check=True)
        print("RESTART the kernel session after reinstall, then skip to Cell 2")
else:
    raise RuntimeError("No GPU allocated — re-probe; do not train on CPU")
```

**Cell 2 — copy code, smoke the plan.**

```python
import shutil, pathlib
src = pathlib.Path("/kaggle/input/sif26165-corpus-v1")
work = pathlib.Path("/kaggle/working")
for f in ("train.py", "model.py"):
    shutil.copy(src / f, work / f)
!cd /kaggle/working && python train.py --dry-run --corpus-dir /kaggle/input/sif26165-corpus-v1 --config masked
```

**Cell 3 — train + export + gate (one config per kernel).**

```python
!cd /kaggle/working && python train.py \
    --corpus-dir /kaggle/input/sif26165-corpus-v1 \
    --config masked --epochs 3 --batch 32 --seq 128 --lr 2e-5 \
    --out /kaggle/working --resume
```

(`--resume` makes a re-run after session death pick up from the newest
`ckpt-ep*.pt`. For the second kernel change `--config unmasked`.)

Expected: ~15–40 min on 2×T4 (fp16 tensor cores), 25–60 min on P100.
Per-epoch `ckpt-ep{N}.pt` + `metrics-ep{N}.json` land in `/kaggle/working`;
final phase writes `sif_multitask_fp32.onnx`, `sif_multitask_int8.onnx`,
`thresholds.json`, `export_gate.json`, `manifest.json`.

## Step 2 — Post-completion retrieval checklist (MCP)

Wait for session COMPLETE (`get_notebook_session_status`), then
`download_notebook_output` for **every** file — the dynamo exporter writes
fp32 weights as an EXTERNAL sidecar; missing it silently breaks the gate:

- [ ] `manifest.json` — read FIRST; it lists every artifact + sha256
- [ ] `sif_multitask_fp32.onnx` **AND `sif_multitask_fp32.onnx.data`**
      (~596 MB — both, always)
- [ ] `sif_multitask_int8.onnx` (~151 MB — the deploy artifact)
- [ ] `thresholds.json` (frozen sif threshold @p≥0.80, temperature,
      per-rule thresholds, pos_weight)
- [ ] `metrics.json` + all `metrics-ep*.json`
- [ ] `export_gate.json` (`pass: true`; fp32 max|Δlogit| ≤1e-4, int8
      agreement ≥99.5%, AUC drop ≤0.005, recall@p0.8 drop ≤0.01)
- [ ] `ckpt-ep*.pt` (resume + re-export insurance)

Then locally: recompute `sha256` of each retrieved file and compare against
`manifest.json` — mismatch = truncated download, re-fetch before use.

## Failure playbook

- **T4 not allocated (P100)** → Cell 1 handles it; expect 2–3× slower.
- **Session death mid-epoch** → relaunch same kernel; `--resume` continues.
  Death mid-export → rerun; training ckpts are already safe.
- **Export gate RED on fp32 parity** → never ship; check that nothing
  reintroduced the legacy exporter (banned) or flipped `dynamo=False`.
- **int8 parity marginal** → decision-level only (D13); re-measure on the
  trained model — the Day-1 gate proved mechanics, not trained-model deltas.
- **Quota**: full job roster ≈ 8 GPU-h of 30 h (gate 0.5 + 2 configs × ~1 h
  + retries); T4×2 billing measured negligible (12.8 GPU-s for a full probe).
