# Deploying the demo for judges — always-on, $0

**The requirement:** judges open the submission at an unknown time. The link
must be up 24/7 without anyone touching it, reset itself to a clean state,
and run the FULL stack — real INT8 classifier, 18 gates, N=4 ensemble,
duplicate clustering, ingest jobs, decisions audit trail.

**The answer:** a Docker Space on Hugging Face (free CPU basic: 2 vCPU /
16 GB — the app measures ~550 MB RSS), kept awake by a health ping. Weights
live in a **private** HF dataset; the container pulls them at cold start, so
nothing sensitive goes into any public repo.

Measured costs: Space $0 · dataset storage $0 (312 MB, well inside free) ·
Actions keep-alive ~2,160 of your 3,000 included minutes (or UptimeRobot,
unlimited, $0). Total: **$0**.

## One-time prep (5 minutes)

1. Hugging Face account → https://huggingface.co/settings/tokens →
   **New token**, role **write** (needed to create repos + be readable by
   the Space). Copy it.
2. Install the CLI once: `pip install -U "huggingface_hub[cli]"`, then
   `export HF_TOKEN=hf_xxx` (or `hf auth login`).

## Deploy (10 minutes, run from the repo root)

1. **Create the private dataset** (web UI): https://huggingface.co/new-dataset
   → name `sif-runtime-bundle` → **Private** → Create.
2. **Upload the runtime bundle** (~312 MB: INT8 model + tokenizer, MiniLM
   embedder + corpus index, pristine demo DB):
   ```bash
   BUNDLE_REPO=<hf-user>/sif-runtime-bundle bash deploy/upload-bundle.sh
   ```
3. **Create the Space** (web UI): https://huggingface.co/new-space → name
   `sif-triage` → SDK **Docker** → **Public** (judges must reach it without
   HF accounts) → Create.
4. **Push the app** (app code, built dashboard, Dockerfile, entrypoint):
   ```bash
   SPACE_REPO=<hf-user>/sif-triage bash deploy/push-space.sh
   ```
5. **Set the Space's secrets** (web UI → the Space → Settings →
   "Variables and secrets"):
   - Secret `HF_TOKEN` = the token from prep (read access to the dataset)
   - Variable `BUNDLE_REPO` = `<hf-user>/sif-runtime-bundle`
6. **Keep-alive** — pick ONE:
   - **UptimeRobot** (recommended): https://uptimerobot.com free account →
     new HTTP monitor → URL `https://<hf-user>-sif-triage.hf.space/api/health`
     → interval 5 minutes. Done.
   - **GitHub Actions**: the workflow `.github/workflows/keepalive.yml` is
     already in the repo — just set the repo variable
     `SPACE_URL = https://<hf-user>-sif-triage.hf.space`
     (repo Settings → Secrets and variables → Actions → Variables).

## Verify like a judge (2 minutes)

- `https://<hf-user>-sif-triage.hf.space/api/health` →
  `"classifier":"RealOnnxClassifier"`, `"n_reports":4548`
- Open the Space URL → queue loads with the compression line
  ("1,019 duplicate groups · 2,028 reports collapsed")
- Paste a report on the ingest page → score, band, gates, evidence spans
- Record a decision → it appears in the decisions register
- Language toggle EN/हिं, "Data & limitations" dialog opens

## Operating notes

- **First build/cold start:** Space build ~3–5 min (pip install), first
  boot ~1–3 min (312 MB bundle download from HF CDN + model load + 4.5k-row
  gate backfill). After that it stays warm under the keep-alive ping.
- **Every restart = pristine register.** Storage is ephemeral on free
  Spaces: restarts re-download the bundle and re-seed the 4,548-row demo DB.
  For unknown-time judging this is a feature — judges never inherit your
  test pastes. Decisions persist for the container's lifetime.
- **Ollama rewording is off** (`SIF_EXPLAIN_LLM=0`, the project default):
  the deterministic explanation templates are the product floor. Flipping
  it on needs a ≥8 GB plan and adds cold-start fragility — don't for the
  demo.
- **Concurrency:** one uvicorn worker handles several simultaneous judges
  (async I/O; classify is CPU-serialized at ~1–3 s each on 2 shared vCPU).
- **Logs:** the Space's "Logs" tab shows uvicorn + entrypoint output.
- **Updating the app:** re-run `push-space.sh` — the Space rebuilds
  automatically. Updating weights: re-run `upload-bundle.sh`, then restart
  the Space once.

## Redundancy (recommended for submission)

- **Backup Space:** repeat steps 3–6 with name `sif-triage-2`. Put the
  primary URL in the submission; keep the backup in your pocket (also
  useful if a build breaks at 2 AM — the old Space keeps serving until you
  push).
- **Different-platform backup:** the same image runs anywhere Docker does
  (`docker build -f deploy/Dockerfile -t sif-triage .`). If your Student
  Pack still lists Azure for Students ($100, no card), a 2 vCPU / 4 GB VM
  covers ~2–3 months always-on with a persistent disk.
- **Live demo-day tool:** GitHub Codespaces (Pro: 180 core-h/month) —
  `run.sh` now honors `SIF_HOST=0.0.0.0`, so forward port 8177 as Public
  and demo from your repo directly.

## What goes where (security)

| Artifact | Where | Visibility |
|---|---|---|
| App code + dashboard | GitHub repo | private |
| Model + embedder + index + seed DB | HF dataset `sif-runtime-bundle` | **private** (token-gated) |
| Running demo | HF Space `sif-triage` | public URL, no auth |

The app has no authentication by design (local-first tool). A public demo
URL means anyone can POST reports — acceptable for demo week; the Space's
ephemeral reset bounds any pollution.
