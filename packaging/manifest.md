# USB Tarball Manifest — SIF-Precursor Detection Engine (PS 26165)

Bare-metal, 100% offline demo bundle (ARCHITECTURE runtime section; D5, D18).
Build: `packaging/make_tarball.sh` → `packaging/sif-demo-usb-<date>.tar.gz`.
**Dated build snapshot (2026-09-25):** sizes below were measured on this
machine (`du -sh`, MiB), and describe the then-built
`packaging/sif-demo-usb-20260925.tar.gz` — 339M gz, 189 entries. They are not
measurements of the current tree; rebuilds drift by a few KB and entry counts
track app/ as siblings land code.

## In the tarball

| Component | Path in tarball | Size | Notes |
|---|---|---|---|
| Runtime API code | `app/` | 256K | FastAPI + onnxruntime + SQLite/numpy near-dup index; explanation templates. `app/runtime.db*` (dev/live DB) excluded; `app/tests/` ships along (selfcheck helpers) |
| Dashboard (prebuilt) | `dashboard/dist/` | 1.7M | Vite build; served by FastAPI StaticFiles mount at `/` — one process, no second server |
| Model artifacts | `artifacts/models/masked-v2/` | 149M | **INT8 ship variant `sif_multitask_int8.onnx` (145M)** + ModernBERT `tokenizer/` (3.5M `tokenizer.json`) + per-epoch metrics, `thresholds.json`, export-gate + provenance (`manifest.json`, `export_gate.json` — gate status lives there, not asserted here) |
| Near-dup runtime | `artifacts/embeddings/` | 143M | MiniLM `all-MiniLM-L6-v2` vendored ONNX (`minilm/`, 87M — `app/config.py:embed_model_dir`) + precomputed corpus index (`corpus_embeddings_fp16.npy` 52M + `corpus_ids.jsonl` 3.7M — `app/storage.py:_load_corpus_index`, the verbatim-corpus paste-attack banner) |
| Precomputed pattern stats | `artifacts/patterns/` | 912K | Lift-ranked facet co-occurrence served by `/api/patterns` (precompute doctrine) |
| Frozen label spec | `spec/label_spec.yaml` | 12K | H2-frozen SIF definition + OIICS era maps + masking stems (spec hash ships with model metrics) |
| Python wheels | `packaging/wheels/` | 116M | **41 wheels** for `requirements.txt` — offline `pip install --no-index` (py3.14 manylinux x86_64); closure verified 2026-09-25 (below) |
| Requirements pin | `requirements.txt` | 4K | fastapi, uvicorn[standard], pydantic, numpy, threadpoolctl, onnxruntime, tokenizers, structlog, prometheus-client, pydantic-settings; pandas is commented as pipeline-only — **no torch or pyarrow at runtime** |
| Startup script | `run.sh` | 8K | The demo spine: preflight → ollama → uvicorn :8177 → health-wait → demo URL; `--stop` cleans up |
| Install + self-check | `packaging/install.sh`, `packaging/selfcheck.sh` | 12K | Target-side offline install; two-cycle start→health→classify→stop verification (selfcheck needs `jq`, `bc` + `ss` from iproute2) |
| Docs | `README.md`, `packaging/manifest.md` | 24K | Repo README + this manifest |

**Dated build snapshot (2026-09-25):** tarball total was 339M gzipped (measured,
not estimated); this figure describes that build, not the current tree.

## Deliberately excluded

| Excluded | Size (why) |
|---|---|
| `artifacts/models/masked-v2/sif_multitask_fp32.onnx` + `.onnx.data` | 599M — repo-side export provenance; run.sh/classifier resolution prefers the INT8 artifact, so shipping fp32 would be ~599M of dead weight (excluded by make_tarball since 2026-09-25) |
| `data/` raw OSHA/ASRS CSVs (72M) | raw research, not demo runtime |
| `artifacts/demo/` (46M), `artifacts/qa-evidence/` (12M), `artifacts/gold/` (3.2M), `artifacts/baselines/` (2.0M) | demo-building/eval provenance; the tarball carries **no pre-seeded DB** — the near-dup index warms from the shipped corpus index + live ingests |
| `.venv/` (458M) | not relocatable (absolute shebangs) — wheels + `install.sh` rebuild it on target in ~1 min |
| `training/`, `data_pipeline/`, `pipeline/`, `gold/`, `tests/`, `notebooks/`, `dashboard/src+node_modules`, `.git/` | dev-only |

## MiniLM near-dup index — shipped

`all-MiniLM-L6-v2` ONNX (87M) is vendored at `artifacts/embeddings/minilm/` and
the precomputed corpus index (70,398 × 384 fp16 + ids, ~108M fp32 in RAM)
ships alongside. `app/main.py` configures the embedder and `SQLiteStorage`
mmaps the corpus matrix at startup. Degradation paths, if either is absent:
corpus index missing → *silent* session-rows-only near-dup (log warning,
`app/storage.py`); MiniLM ONNX missing → hashed n-gram fallback
(`app/embedder.py:HashedEmbedder`). `make_tarball.sh` now hard-fails on a
missing `minilm/model.onnx` or corpus pair so a bundle cannot ship degraded.
Near-dup banner threshold 0.91 — measured from the embedding curve
(`artifacts/embeddings/threshold_report.md`, `app/config.py:near_dup_threshold`).

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

System requirements: Linux x86_64, Python 3.14 exactly (the bundled wheels are
cp314; `install.sh` enforces the match and prints the `pip download` rebuild
line if the target interpreter differs), `jq` + `bc` + `ss` (iproute2) for
`selfcheck.sh`, 4 CPU cores, 8 GB RAM free (ONNX INT8 ~1 GB RSS; +3.2 GB if
qwen3:4b rewording runs; +~110M for the fp32 corpus near-dup matrix), no docker,
no network.

## Offline verification

The measurements below are dated verification snapshots for the 2026-09-25
build, not claims about the current tree.

- **2026-09-25 (this machine):** clean extract of the built tarball into /tmp,
  then `packaging/install.sh` inside `unshare -rn` — no network interface at
  all, stronger than trusting `pip --no-index` alone. Result: pip resolved
  **all 41 wheels offline**, the then-current import contract (fastapi, uvicorn,
  onnxruntime, tokenizers, numpy, pandas, threadpoolctl, structlog,
  prometheus_client, pydantic_settings) passed, the model artifact was
  detected, **exit 0**.
- **2026-09-25 wheel closure audit:** at that dated build, 41 wheels on disk =
  exactly the 41-package transitive closure of `requirements.txt` (1:1 — nothing missing,
  nothing unused). Root causes fixed this session: `requirements.txt` had
  gained `threadpoolctl` (BLAS pinning, `app/storage.py` ORT starvation fix)
  after the 2026-09-08 wheels snapshot, which alone made `pip --no-index` die
  on resolution; the same-day A5 additions (`structlog`, `prometheus-client`,
  `pydantic-settings`) would have broken it again — wheels added same session:
  threadpoolctl 3.7.0, structlog 26.1.0, prometheus-client 0.26.0,
  pydantic-settings 2.15.0. uvicorn's colorama extra is win32-only and
  correctly absent from the dir.
- **2026-09-08 (this machine):** socket-level air-gap audit of a running stack —
  the only outbound URL in `app/` is `http://localhost:11434` (ollama, loopback);
  listeners were `127.0.0.1:8177` + `127.0.0.1:11434` with **zero** non-loopback
  connections (`ss -tnp`). *Not re-run against the current build — due at the
  Day-3 rehearsal alongside the real ethernet-unplug.*
- Known demo-day caveat: the venue browser must point at `127.0.0.1:8177`, and
  any OS-level proxy env vars should be unset (nothing here honors them, but the
  *browser* might).
