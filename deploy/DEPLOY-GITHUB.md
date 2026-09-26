# GitHub-only deploy (Koyeb) — always-on, $0, no Hugging Face account

Same architecture as the HF path; the only substitution is where the 312 MB
runtime bundle (INT8 model + MiniLM embedder + corpus index + seed DB)
lives: a **private GitHub Release asset** instead of a private HF dataset.
The container is identical — `deploy/Dockerfile`, `deploy/entrypoint.sh`,
`deploy/fetch_bundle.py` — verified locally end-to-end.

## Prerequisites (5 min, one-time)

1. `gh auth login` (the `gh` CLI, with your GitHub Pro account).
2. `docker` running locally (already verified working).
3. A Koyeb account: https://app.koyeb.com — **Sign up with GitHub**. Free
   tier: one always-on instance, 2 GB RAM, no card.
4. A GitHub **Personal Access Token** for the bundle download:
   github.com → Settings → Developer settings → Personal access tokens →
   Fine-grained → Generate. Contents: **Read-only** access to *this repo
   only*. Copy it.

## 1 — Push the repo to a PRIVATE GitHub repo

The deploy files (`deploy/`, `.dockerignore`, `run.sh` SIF_HOST change,
`.github/workflows/keepalive.yml`) are untracked in your local tree. Review
them, then:

```bash
git add run.sh .dockerignore .github/workflows/keepalive.yml deploy/
git commit -m "deploy: container + bundle fetch + keep-alive (GitHub-only, Koyeb path)"
git remote add origin git@github.com:<you>/sif-triage.git   # create the repo PRIVATE on github.com first
git push -u origin master
```

Keep the repo **private** — it carries the app, and the bundle asset below
inherits its visibility. The *Space/dashboard URL* is what goes public, not
the code or weights.

## 2 — Upload the runtime bundle to a private Release (312 MB)

```bash
# tar.gz already produced: /tmp/sif-runtime-bundle.tar.gz (232 MB compressed)
gh release create v1.0.0-bundle \
    /tmp/sif-runtime-bundle.tar.gz \
    --repo <you>/sif-triage \
    --title "Runtime bundle v1" --notes "INT8 model + MiniLM + corpus index + seed DB (private)"
```

## 3 — Point the container at the GitHub asset

`deploy/fetch_bundle.py` already supports the HF dataset mode; for the
GitHub mode set these envs on the Koyeb service instead:

- `BUNDLE_GH_RELEASE = <you>/sif-triage@v1.0.0-bundle`  (repo@tag)
- `GITHUB_TOKEN` = the read-only PAT from prerequisites
- (omit `BUNDLE_REPO` / `HF_TOKEN` entirely)

The entrypoint downloads `sif-runtime-bundle.tar.gz`, extracts into
`$BUNDLE_DIR`, seeds `demo_pre.db`, serves — exactly as verified locally.

## 4 — Deploy on Koyeb (web UI, ~5 min)

1. app.koyeb.com → **Create Service** → **GitHub** → pick your private
   `sif-triage` repo (grant Koyeb access).
2. Builder: **Dockerfile** → path `deploy/Dockerfile`, build context `/`.
3. Instance: free tier (2 GB). Port: `7860`. Health check path `/api/health`.
4. Env vars (from step 3) + `PORT=7860`.
5. Deploy → Koyeb builds the image (~5 min), assigns a
   `https://<service>-<org>.koyeb.app` URL.

## 5 — Keep-alive (prevents any idle sleep)

- **UptimeRobot** (free, unlimited): monitor
  `https://<service>-<org>.koyeb.app/api/health`, 5-min interval. OR
- **Actions**: repo already carries `.github/workflows/keepalive.yml` — set
  repo variable `SPACE_URL = https://<service>-<org>.koyeb.app`.

## Verify like a judge

`https://<service>.koyeb.app/api/health` → `"classifier":"RealOnnxClassifier"`,
`"n_reports":4548`; queue shows "1,019 duplicate groups · 2,028 reports
collapsed"; paste a report → score + gates + spans; record a decision →
appears in the register; EN/हिं toggle.

## Ops notes

- **Cold start:** ~5 min build + ~1–3 min first boot (bundle download from
  GitHub CDN + model load + 4.5k-row backfill), then warm under the ping.
- **Ephemeral SQLite:** every restart re-seeds the pristine 4,548-row
  register — the judges-see-a-clean-demo property. Persistent disk on Koyeb
  is a paid add-on; not needed for the demo.
- **Capabilities (all alive):** real INT8 classifier, N=4 ensemble +
  stability gate, 18 gates, duplicate clustering, CSV ingest + job cancel,
  decisions audit, analytics, EN/HI. Ollama rewording stays off (designed
  template floor) — same as every free-tier plan.
- **Backup:** the same image runs on HF Spaces (once your account is
  unblocked), Azure, or any Docker host — one env flip, zero code change.
