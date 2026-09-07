# Phase 0 Validation — Cluster: Local Toolchain (PS 26165)

Validator: phase0-validator (toolchain). Date: 2026-09-08. All values measured on this machine today unless marked INFERRED.

## Findings

| # | Claim (HANDOFF / task) | Measured | Verdict |
|---|---|---|---|
| 1 | Python 3.14.6 present | `python3 --version` → Python 3.14.6 (`/usr/bin/python3`); pip 26.1.2 | VERIFIED |
| 2 | venv works | `python3 -m venv /tmp/probe-venv` OK; venv pip upgraded to 26.2.1 | VERIFIED |
| 3 | pandas+pyarrow+scikit-learn install on py3.14 | `pip install` exit 0 in probe venv: pandas 3.0.5, pyarrow 25.0.1, sklearn 1.9.0; all import | VERIFIED |
| 4 | cp314 wheel availability risk | PyPI JSON: cp314 manylinux x86_64 wheels exist for pandas 3.0.5 (4), pyarrow 25.0.1 (4), scikit-learn 1.9.0 (2), numpy 2.5.3 (4). The feared "libs lag py3.14" risk does NOT exist today; pyenv/conda/docker fallback NOT needed | VERIFIED (risk clear) |
| 5 | uv/conda/pyenv | uv 0.11.29 at /usr/bin/uv; conda NOT FOUND; pyenv NOT FOUND | PARTIAL (uv yes, conda/pyenv no) |
| 6 | "No torch installed yet" (HANDOFF §B.1) | `import torch` → ModuleNotFoundError; no torch in system pip | VERIFIED |
| 7 | CPU torch wheel for cp314 | download.pytorch.org/whl/cpu: `torch-2.14.0%2Bcpu-cp314-cp314-manylinux_2_28_x86_64.whl` exists (also 2.13.0, 2.12.1). PyPI torch 2.14.0 also has cp314 wheel (CUDA-bundled). Local CPU fallback training (§B.5) is unblocked | VERIFIED |
| 8 | Docker usable (packaging plan §B.8/§D: docker-compose + `docker save`) | docker CLI 29.7.2 present BUT `docker info` exit 1: socket /var/run/docker.sock missing, daemon `inactive`+`disabled` (systemctl), user NOT in docker group; `docker pull hello-world` FAILED (daemon unreachable) | FAILED (as of now) |
| 9 | docker compose | `docker compose` → "unknown command"; no cli-plugins dir; no `docker-compose` binary | FAILED |
| 10 | node/npm present | node v26.4.0 (/usr/bin/node); npm 12.0.2 (~/.local/bin/npm) | VERIFIED |
| 11 | RAM/disk headroom for ~8–10 GB offline packaging | RAM 30Gi total, 17Gi available; disk 514G avail on / (HANDOFF said 517 GB — trivial drift) | VERIFIED (CORRECTED 517→514 GiB) |
| 12 | git + repo state | git 2.55.0 present; /home/dakkshesh/sih26-round2 is NOT a git repo (`git rev-parse` → fatal) | PARTIAL (git yes; no repo — init recommended for 3-day build) |

## Commands used
- `python3 --version`, `python3 -m pip --version`, `python3 -m venv /tmp/probe-venv`, probe-venv `pip install pandas pyarrow scikit-learn` + import test
- PyPI JSON API per package: counted `cp314` + `x86_64` + `linux` filenames for latest release
- `curl https://download.pytorch.org/whl/cpu/torch/` grep cp314
- `command -v uv conda pyenv docker node npm git` + `--version`
- `docker info`, `docker compose version`, `docker pull hello-world`, `systemctl is-active/is-enabled docker`, `id` (group check), ls of cli-plugins dirs
- `free -h`, `df -h`, `git -C ... rev-parse`

## Load-bearing impact
- **Docker is the only real blocker found.** The entire offline-packaging/demo plan (single docker-compose, `docker save` tarball, Label Studio compose) requires: starting/enabling the docker daemon (sudo), adding the user to the docker group (or rootless setup), and installing the compose plugin. All fixable in <30 min with root, but NONE of it works right now; Day-3 packaging would fail as-is.
- Python stack (incl. py3.14 wheels for every needed lib, CPU torch included) is fully green — no pyenv/conda/dockerized-dev mitigation needed; uv present as bonus.
- Not a git repo: recommend `git init` before the 72h build for checkpointing (INFERRED recommendation, not a claim).

Score inputs: go_no_go 7, severity 1 (docker/compose FAILED), data_risk 2 (all data/compute resources present; docker needs root setup).
