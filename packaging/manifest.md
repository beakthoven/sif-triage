# USB Tarball Manifest — SIF-Precursor Detection Engine (PS 26165)

Bare-metal, 100% offline demo bundle (ARCHITECTURE runtime section; D5, D18).
Build: `packaging/make_tarball.sh` → `packaging/sif-demo-usb-<date>.tar.gz`.
Sizes measured on this machine, 2026-09-08 (`du -sh`).

## In the tarball

| Component | Path in tarball | Size | Notes |
|---|---|---|---|
| Runtime API code | `app/` | 304K | FastAPI + onnxruntime + SQLite/numpy near-dup index; explanation templates |
| Dashboard (prebuilt) | `dashboard/dist/` | 1.4M | Vite build; served by FastAPI StaticFiles mount at `/` — one process, no second server |
| Model artifacts | `artifacts/models/` | 2.1M now + **ONNX pending** | Vendored ModernBERT `tokenizer/tokenizer.json` (2.1M) + per-epoch metrics. The export-gated `sif_multitask_int8.onnx` (est. ~150–170M) drops in from the Kaggle run before the final build — `*.onnx` is gitignored, **this tarball is the model transport** |
| Precomputed pattern stats | `artifacts/patterns/` | 880K | Lift-ranked facet co-occurrence served by `/api/patterns` (precompute doctrine) |
| Frozen label spec | `spec/label_spec.yaml` | 12K | H2-frozen SIF definition + OIICS era maps + masking stems (spec hash ships with model metrics) |
| Python wheels | `packaging/wheels/` | 116M | 37 wheels for `requirements.txt` — offline `pip install --no-index` (py3.14 manylinux x86_64) |
| Requirements pin | `requirements.txt` | 4K | fastapi, uvicorn[standard], pydantic, numpy, onnxruntime, tokenizers, pandas, pyarrow — **no torch at runtime** |
| Startup script | `run.sh` | 8K | The demo spine: preflight → ollama → uvicorn :8177 → health-wait → demo URL; `--stop` cleans up |
| Install + self-check | `packaging/install.sh`, `packaging/selfcheck.sh` | 6K | Target-side offline install; two-cycle start→health→classify→stop verification |

**Tarball total: ~120M today; est. ~280M once the INT8 ONNX lands.**

## Deliberately excluded

| Excluded | Size (why) |
|---|---|
| `data/` raw OSHA/ASRS CSVs (72M), `runs/` research | raw research, not demo runtime |
| `artifacts/asrs/` 258M, `artifacts/corpus/` 270M, `artifacts/export-gate/` 716M, `artifacts/synthetic/` 16M, `artifacts/gold/`, `artifacts/baselines/` | training/eval research artifacts; the demo's near-dup index embeds at ingest time and needs no corpus files |
| `.venv/` (413M) | not relocatable (absolute shebangs) — wheels + `install.sh` rebuild it on target in ~1 min |
| `training/`, `data_pipeline/`, `pipeline/`, `gold/`, `tests/`, `notebooks/`, `dashboard/src+node_modules`, `.git/` | dev-only |

## MiniLM (near-dup index) — PENDING

`all-MiniLM-L6-v2` ONNX (~90M budget) lands with the real near-dup index task and
will be vendored into `artifacts/models/minilm/`. Until then the index runs the
deterministic hashed n-gram embedding (`app/classifier.py:pseudo_embed`), which
already satisfies the near-dup gate contract. Tarball rebuild picks MiniLM up
automatically (whole `artifacts/models/` ships).

## Ollama model blobs (optional rewording LLM)

Ollama itself is a system binary and the model store lives **outside** the
tarball (`~/.ollama/models`, not repo data). Runtime LLM = **qwen3:4b** (D4);
qwen3:8b is dev-time only (zero-shot baseline precompute).

| Model | Size (this machine) | Ship? |
|---|---|---|
| `qwen3:4b` | 2.5 GB | yes, for reworded explanations |
| `qwen3:8b` | 5.2 GB | no — dev-only |

Two ways to provision the target (the demo works without either — template
fallback carries every explanation by design):

1. **Online target (preferred):** `ollama pull qwen3:4b` before the venue unplug.
2. **Sneakernet:** copy the store blobs + manifest from a prepared machine:
   ```bash
   # on the prepared machine
   tar -czf ollama-qwen3-4b.tar.gz -C ~/.ollama/models \
       blobs manifests/registry.ollama.ai/library/qwen3
   # on the target (as the ollama user)
   tar -xzf ollama-qwen3-4b.tar.gz -C ~/.ollama/models
   ollama list   # verify qwen3:4b appears
   ```
   Either way, the server must run with `OLLAMA_NUM_PARALLEL=6` (D18) — `run.sh`
   sets it when it starts ollama itself, and leaves an already-running server alone.

## Target-side install (fully offline)

```bash
tar -xzf sif-demo-usb-<date>.tar.gz -C /opt/sif-demo   # or anywhere
cd /opt/sif-demo
packaging/install.sh     # venv + pip --no-index from bundled wheels, ~1 min
./run.sh                 # demo at http://127.0.0.1:8177/
packaging/selfcheck.sh   # optional: two start→health→classify→stop cycles
```

System requirements: Linux x86_64, Python 3.14 (the bundled wheels are cp314;
rebuild `packaging/wheels` with `pip download` if the target interpreter differs),
4 CPU cores, 8 GB RAM free (ONNX INT8 ~1 GB RSS; +3.2 GB if qwen3:4b rewording
runs), no docker, no network.

## Offline verification (2026-09-08, this machine — socket-level, real unplug is Day 3)

- Code audit: the only outbound URL in `app/` is `http://localhost:11434`
  (ollama, loopback). Nothing else in the runtime opens a socket.
- With the full stack up (`./run.sh --allow-mock`): listeners are
  `127.0.0.1:8177` (uvicorn) and `127.0.0.1:11434` (ollama) only; the uvicorn
  process holds **zero** non-loopback connections (`ss -tnp`), while serving
  health/classify/dashboard.
- Target-side install proven air-gap-safe: `packaging/install.sh` installs all
  37 wheels with `pip --no-index --find-links=packaging/wheels` (verified from a
  clean extract of the tarball), then `./run.sh` came up and served
  health + classify + dashboard from the extracted copy.
- Known demo-day caveat: the venue browser must point at `127.0.0.1:8177`, and
  any OS-level proxy env vars should be unset (nothing here honors them, but the
  *browser* might). Real ethernet-unplug rehearsal: Day 3.
