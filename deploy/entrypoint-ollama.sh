#!/usr/bin/env bash
# Full-feature cold start: bundle fetch + warmed demo DB + ollama + uvicorn.
#
# Identical to deploy/entrypoint.sh except:
#   1. The seeded DB is the build-time pre-warmed copy (explanations cached
#      in the `precomputed` table) when /app-data-warm/demo_pre.db.tar.gz
#      exists; otherwise it falls back to the bundle's pristine seed.
#   2. `ollama serve` starts alongside uvicorn (SIF_EXPLAIN_LLM=1).
#
# The bundle still comes from the private dataset/release (weights, index,
# pristine seed) — only the DB selection differs.
set -euo pipefail

BUNDLE_DIR="${BUNDLE_DIR:-/app-data/bundle}"
DB_PATH="${SIF_DB_PATH:-/app-data/runtime.db}"
MODEL_REL="masked-v2/sif_multitask_int8.onnx"

if [ ! -f "$BUNDLE_DIR/$MODEL_REL" ]; then
    if [ -n "${BUNDLE_GH_RELEASE:-}" ]; then
        if [ -z "${GITHUB_TOKEN:-}" ]; then
            echo "entrypoint: BUNDLE_GH_RELEASE is set but GITHUB_TOKEN is not." >&2
            exit 1
        fi
        echo "entrypoint: fetching runtime bundle from GitHub release ${BUNDLE_GH_RELEASE} …"
        python /app/fetch_bundle.py "$BUNDLE_DIR" --github "$BUNDLE_GH_RELEASE"
    elif [ -n "${BUNDLE_REPO:-}" ] && [ -n "${HF_TOKEN:-}" ]; then
        echo "entrypoint: fetching runtime bundle from dataset ${BUNDLE_REPO} …"
        python /app/fetch_bundle.py "$BUNDLE_DIR" "$BUNDLE_REPO"
    else
        echo "entrypoint: runtime bundle missing and no bundle source configured" \
             "(mount it, or set BUNDLE_REPO + HF_TOKEN, or BUNDLE_GH_RELEASE + GITHUB_TOKEN)." >&2
        exit 1
    fi
fi

if [ ! -f "$DB_PATH" ]; then
    if [ -f /app-data-warm/demo_pre.db.tar.gz ]; then
        echo "entrypoint: seeding demo register from the PRE-WARMED copy" \
             "(explanations cached)"
        mkdir -p /tmp/warm && tar -xzf /app-data-warm/demo_pre.db.tar.gz -C /tmp/warm
        cp /tmp/warm/demo_pre.db "$DB_PATH"
    else
        echo "entrypoint: warm DB not found; seeding the pristine demo register"
        cp "$BUNDLE_DIR/demo_pre.db" "$DB_PATH"
    fi
fi

echo "entrypoint: starting ollama serve (NUM_PARALLEL=1)"
OLLAMA_NUM_PARALLEL=1 nohup ollama serve >/tmp/ollama.log 2>&1 &

echo "entrypoint: starting uvicorn on 0.0.0.0:${PORT:-7860}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}" --workers 1
