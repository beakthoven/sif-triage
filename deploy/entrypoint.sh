#!/usr/bin/env bash
# Cold-start sequence for the SIF triage container.
#   1. Ensure the runtime bundle exists under $BUNDLE_DIR — download it from
#      the private HF dataset $BUNDLE_REPO (auth: $HF_TOKEN) when missing.
#   2. Seed a fresh demo register from the pristine seed DB when missing.
#   3. Serve FastAPI + dashboard on 0.0.0.0:${PORT:-7860}.
#
# $BUNDLE_DIR is EPHEMERAL on free hosts (HF Spaces without persistent
# storage): every container restart re-downloads the bundle and re-seeds the
# register — a deliberate demo property. Judges always meet a clean,
# verified 4,548-row register; nothing from earlier sessions lingers.
set -euo pipefail

BUNDLE_DIR="${BUNDLE_DIR:-/app-data/bundle}"
DB_PATH="${SIF_DB_PATH:-/app-data/runtime.db}"
MODEL_REL="masked-v2/sif_multitask_int8.onnx"

if [ ! -f "$BUNDLE_DIR/$MODEL_REL" ]; then
    if [ -n "${BUNDLE_GH_RELEASE:-}" ]; then
        # GitHub mode: BUNDLE_GH_RELEASE=<owner/repo@tag>, auth via GITHUB_TOKEN.
        if [ -z "${GITHUB_TOKEN:-}" ]; then
            echo "entrypoint: BUNDLE_GH_RELEASE is set but GITHUB_TOKEN is not" \
                 "(a read-only PAT for that private repo is required)." >&2
            exit 1
        fi
        echo "entrypoint: fetching runtime bundle from GitHub release ${BUNDLE_GH_RELEASE} …"
        python /app/fetch_bundle.py "$BUNDLE_DIR" --github "$BUNDLE_GH_RELEASE"
    elif [ -n "${BUNDLE_REPO:-}" ] && [ -n "${HF_TOKEN:-}" ]; then
        echo "entrypoint: fetching runtime bundle from dataset ${BUNDLE_REPO} …"
        python /app/fetch_bundle.py "$BUNDLE_DIR" "$BUNDLE_REPO"
    else
        echo "entrypoint: runtime bundle missing at $BUNDLE_DIR/$MODEL_REL, and no" \
             "bundle source is configured." >&2
        echo "entrypoint: mount a bundle at \$BUNDLE_DIR, or set BUNDLE_REPO + HF_TOKEN" \
             "(HF dataset), or BUNDLE_GH_RELEASE + GITHUB_TOKEN (GitHub release)." >&2
        echo "entrypoint: see deploy/DEPLOY.md / deploy/DEPLOY-GITHUB.md." >&2
        exit 1
    fi
fi

if [ ! -f "$DB_PATH" ]; then
    echo "entrypoint: seeding demo register from the pristine seed"
    cp "$BUNDLE_DIR/demo_pre.db" "$DB_PATH"
fi

echo "entrypoint: starting uvicorn on 0.0.0.0:${PORT:-7860}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}" --workers 1
