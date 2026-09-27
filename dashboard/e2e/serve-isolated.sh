#!/usr/bin/env bash
# Isolated demo stack for Playwright e2e — port 8232, throwaway DB.
#
# NEVER points at :8177 (the live demo). Copies artifacts/demo/demo_pre.db to a
# fresh mktemp dir so ingest tests cannot mutate the shipped demo state, pins
# the real INT8 artifact, and disables the ollama rewording (SIF_EXPLAIN_LLM=0 —
# the deterministic template is the e2e floor, and a cold reword would stall
# the paste card for seconds).
#
# Used as the Playwright webServer (dashboard/playwright.config.ts); can also
# be run by hand while iterating:
#   dashboard/e2e/serve-isolated.sh &   # Ctrl+C / kill when done
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT="${E2E_PORT:-8232}"

DB_DIR="$(mktemp -d /tmp/sif-e2e-db-XXXXXX)"
cp "$REPO_ROOT/artifacts/demo/demo_pre.db" "$DB_DIR/demo_pre.db"
[ -f "$REPO_ROOT/artifacts/demo/demo_pre.db-wal" ] && \
    cp "$REPO_ROOT/artifacts/demo/demo_pre.db-wal" "$DB_DIR/" || true

MODEL="$REPO_ROOT/artifacts/models/masked-v2/sif_multitask_int8.onnx"
if [ ! -f "$MODEL" ]; then
    echo "serve-isolated.sh: INT8 artifact missing at $MODEL" >&2
    exit 1
fi

export SIF_DB_PATH="$DB_DIR/demo_pre.db"
export SIF_MODEL_PATH="$MODEL"
export SIF_HOST="127.0.0.1"
export SIF_PORT="$PORT"
export SIF_EXPLAIN_LLM=0

cd "$REPO_ROOT"
exec "$REPO_ROOT/.venv/bin/python" -m uvicorn app.main:app \
    --host "$SIF_HOST" --port "$PORT" --workers 1
