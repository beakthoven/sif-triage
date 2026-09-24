# Pendrive Demo — plug-and-play USB build (PS 26165)

Self-contained, offline, cross-OS demo stick. Complement to (not replacement
for) `make_tarball.sh` — the tarball is the dev/ops transport; the pendrive
layout is the *presentation* artifact: plug in, double-click, demo runs.

## Stick layout (FAT32, no symlinks, no exec-bit dependence)

```
START-HERE.txt            one-page: what/how/troubleshoot
START-LINUX.sh            extract-on-first-run + start + open browser
START-WINDOWS.bat         same for Win10/11 (uses inbox tar.exe + curl.exe)
VERSION                   build stamp; bump → hosts re-extract on next run
payload.tar.gz            app/ + dashboard/dist + masked-v2 INT8 model +
                          MiniLM + corpus near-dup index + patterns +
                          label_spec + seed/demo_pre.db + extras  (~240M)
runtimes/linux-py314.tar.gz   python-build-standalone 3.14.7 (glibc x86_64)
                              + runtime deps preinstalled offline from
                              packaging/wheels (131M)
runtimes/win-py314.zip        python.org embeddable 3.14.x amd64 +
                              Lib/site-packages preinstalled (win_amd64
                              cp314 wheels), ._pth rewritten (116M)
extras/ollama-qwen3-4b.tar.gz ollama manifest+blobs for qwen3:4b (2.3G) —
                              auto-imported by START-LINUX.sh when the host
                              has ollama but not the model
extras/fallback_recording.webm full demo walkthrough video (the no-machine fallback)
```

## Design decisions

- **Extract-to-cache, never run off the stick.** FAT32 has no symlinks (venv/
  pbs layouts need them), removable mounts can be noexec, and SQLite WAL on
  vfat is asking for corruption. First run unpacks to
  `~/.cache/sif-demo` (Linux) / `%LOCALAPPDATA%\sif-demo` (Windows); VERSION
  stamp gates re-extraction. The stick is never written to — safe to pull
  after startup, immune to read-only mounts.
- **Portable interpreters, not system python.** Host python versions are
  unpredictable (wheels here are cp314); python-build-standalone (Linux) and
  the official embeddable zip (Windows) make the runtime hermetic.
  `python -m uvicorn` invocation — no console-script entry points needed.
- **Windows gets plain `uvicorn`, not `uvicorn[standard]`.** uvloop has no
  win_amd64 build; the standard extras are perf niceties the demo path
  doesn't need (`dl/requirements-win.txt`).
- **Ollama stays optional.** Template explanations carry the demo by design
  (D4 fallback). The stick *auto-imports* qwen3:4b only when the host already
  has ollama installed; it never installs ollama itself (system-level change,
  not plug-and-play's business).
- **DB seeding is copy-once.** `demo_pre.db` → `runtime.db` only if absent;
  reviewer overrides made during a demo survive restarts. Delete the cache
  dir to reset.
- **Env contract:** start scripts set `SIF_MODEL_PATH`, `SIF_DB_PATH`,
  `SIF_PORT`; everything else resolves relative to the payload root
  (`app/config.py` defaults), which preserves repo layout.

## Build / rebuild

```bash
packaging/pendrive/bg_downloads.sh         # runtimes + win wheels (network)
packaging/pendrive/bg_ollama.sh            # qwen3:4b sidecar from ~/.ollama
# payload staging: see the cp block in git history / rebuild from repo root
tar -czf packaging/pendrive/stick/payload.tar.gz -C packaging/pendrive/staging payload
packaging/pendrive/assemble_runtimes.sh    # → stick/runtimes/*
date +%Y%m%d-%H%M > packaging/pendrive/stick/VERSION
rsync -a --delete packaging/pendrive/stick/ /run/media/$USER/CACHUOS/
```

Payload ships the **ship model only** (masked-v2 INT8 + tokenizer +
thresholds/metrics/manifest jsons) — fp32 weights and dev variants stay in
the repo (D20/D27; tarball doctrine).

## Verification

- Linux path: fully tested — extract with `SIF_DEMO_HOME=<tmp>`, boot on
  `SIF_PORT=8179`, health + classify + dashboard 200, stop. Also tested
  directly off the vfat stick (`bash START-LINUX.sh` from the mount).
- Windows path: structurally verified (embeddable layout, `._pth`, win_amd64
  native wheels present for onnxruntime/pydantic-core/tokenizers/numpy/
  pandas/pyarrow); **not execution-tested** — no Windows host available.
  Fallback recording on the stick covers the worst case.
