#!/usr/bin/env bash
# run.sh — one-command OFFLINE bring-up of the SIF-precursor demo (PS 26165).
#
# Bare-metal spine (ARCHITECTURE runtime section, D5, D18):
#   ollama (optional rewording LLM, OLLAMA_NUM_PARALLEL=6 mandatory if we start it)
#   uvicorn app.main:app on 127.0.0.1:8177, workers 1
#   React dashboard served by the same FastAPI process (StaticFiles mount at /)
#   SQLite + numpy index, no docker, no network access at runtime.
#
# Usage:
#   ./run.sh              preflight checks, start everything, print demo URL
#   ./run.sh --stop       stop ONLY what run.sh started (pidfiles in .run/)
#   ./run.sh --allow-mock start even when the ONNX artifact is missing
#                         (loud MOCK banner — never acceptable on demo day)
#   ./run.sh --fresh      reset the demo DB from the pristine seed
#                         (artifacts/demo/demo_pre.db) before starting —
#                         backs up the previous DB first. Use for demo day
#                         so the register starts in the verified seed state
#                         instead of whatever earlier testing left behind.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

HOST="${SIF_HOST:-127.0.0.1}"
PORT="${SIF_PORT:-8177}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_URL="http://127.0.0.1:${OLLAMA_PORT}"
BASE_URL="http://${HOST}:${PORT}"
RUN_DIR="$REPO_ROOT/.run"
VENV_PY="$REPO_ROOT/.venv/bin/python"
DASHBOARD_DIST="$REPO_ROOT/dashboard/dist"

# Port-scoped so a selfcheck on another port can never collide with the live
# demo's pidfile/log (bug seen 2026-09-25: shared uvicorn.pid made selfcheck
# think the live server was its own child and fail the bring-up proof).
UVICORN_PIDFILE="$RUN_DIR/uvicorn-$PORT.pid"
UVICORN_LOG="$RUN_DIR/uvicorn-$PORT.log"
# Demo DB: mirrors app/config.py's default so --fresh resets the DB the
# server will actually open. The pristine seed is the demo-day source of truth.
DB_PATH="${SIF_DB_PATH:-$REPO_ROOT/app/runtime.db}"
DEMO_SEED_DB="$REPO_ROOT/artifacts/demo/demo_pre.db"

ALLOW_MOCK=0
FRESH=0
ACTION="start"
for arg in "$@"; do
    case "$arg" in
        --stop) ACTION="stop" ;;
        --allow-mock) ALLOW_MOCK=1 ;;
        --fresh) FRESH=1 ;;
        -h|--help) sed -n '2,21p' "$0"; exit 0 ;;
        *) echo "unknown flag: $arg (try --help)" >&2; exit 2 ;;
    esac
done

say()  { printf '[run.sh] %s\n' "$*"; }
warn() { printf '[run.sh] WARNING: %s\n' "$*" >&2; }
die()  { printf '[run.sh] ERROR: %s\n' "$*" >&2; exit 1; }

# --------------------------------------------------------------------------
# --stop: kill only pids we own (pidfiles), newest first.
# --------------------------------------------------------------------------
if [ "$ACTION" = "stop" ]; then
    stopped=0
    for name in "uvicorn-$PORT" ollama; do
        pidfile="$RUN_DIR/$name.pid"
        [ -f "$pidfile" ] || continue
        pid="$(cat "$pidfile")"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            say "stopping $name (pid $pid)"
            kill "$pid" 2>/dev/null || true
            for _ in $(seq 1 25); do
                kill -0 "$pid" 2>/dev/null || break
                sleep 0.2
            done
            kill -9 "$pid" 2>/dev/null || true
            stopped=1
        else
            say "$name pidfile present but process $pid is gone — cleaning up"
        fi
        rm -f "$pidfile"
    done
    if [ "$stopped" -eq 0 ]; then
        say "nothing started by run.sh is running (external ollama, if any, is left alone)"
    else
        say "stopped."
    fi
    exit 0
fi

# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------
[ -x "$VENV_PY" ] || die ".venv missing or broken. Create it once (online):
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"

[ -f "$DASHBOARD_DIST/index.html" ] || die "dashboard not built ($DASHBOARD_DIST/index.html missing). Build once (online):
  cd dashboard && npm ci && npm run build"

# --- model artifact: hard requirement unless --allow-mock ------------------
# Resolution order mirrors app/classifier.py: explicit env, then int8/fp32
# under artifacts/models/*, then the app/artifacts default. masked-v2 is the
# ship model (runs/run2/day2/ship_decision.md) and wins the glob.
MODEL_ONNX=""
if [ -n "${SIF_MODEL_PATH:-}" ]; then
    if [ -f "$SIF_MODEL_PATH" ]; then
        MODEL_ONNX="$SIF_MODEL_PATH"
    elif [ -d "$SIF_MODEL_PATH" ]; then
        MODEL_ONNX="$(find "$SIF_MODEL_PATH" -maxdepth 1 -name '*.onnx' | sort | head -n1)"
    fi
    [ -n "$MODEL_ONNX" ] || die "SIF_MODEL_PATH=$SIF_MODEL_PATH holds no .onnx artifact"
else
    for pat in "artifacts/models/masked-v2/sif_multitask_int8.onnx" \
               "artifacts/models/*/sif_multitask_int8.onnx" \
               "artifacts/models/*/model_int8.onnx" \
               "artifacts/models/*/sif_multitask_fp32.onnx" \
               "artifacts/models/*/model_fp32.onnx" \
               "artifacts/models/*/*.onnx" \
               "app/artifacts/model.onnx"; do
        for cand in $pat; do
            if [ -f "$cand" ]; then MODEL_ONNX="$cand"; break 2; fi
        done
    done
fi
if [ -n "$MODEL_ONNX" ]; then
    export SIF_MODEL_PATH="$MODEL_ONNX"
    say "model artifact: $MODEL_ONNX"
elif [ "$ALLOW_MOCK" -eq 1 ]; then
    warn "no ONNX artifact found — starting with MockClassifier (deterministic stub)."
    warn "MOCK MODE IS NOT DEMO-READY. Retrieve the export-gated artifact from Kaggle"
    warn "into artifacts/models/<variant>/ before demo day."
else
    die "no ONNX model artifact found (looked in artifacts/models/*/*.onnx, app/artifacts/model.onnx).
  The demo requires the export-gated INT8 model — retrieve it from the Kaggle
  run into artifacts/models/<variant>/ first. Dev-only bypass: ./run.sh --allow-mock"
fi

# --- port sanity ------------------------------------------------------------
if [ -f "$UVICORN_PIDFILE" ] && kill -0 "$(cat "$UVICORN_PIDFILE")" 2>/dev/null; then
    say "already running (uvicorn pid $(cat "$UVICORN_PIDFILE")) — demo at $BASE_URL/"
    exit 0
fi
if curl -sf --max-time 2 "$BASE_URL/api/health" >/dev/null 2>&1; then
    die "port $PORT already serves /api/health but not via run.sh — stop that process first"
fi

mkdir -p "$RUN_DIR"

# --- demo DB reset (--fresh) -------------------------------------------------
# Deterministic demo state: the register starts as the verified seed instead of
# whatever earlier testing left behind (2026-09-25: the live DB carried ~600
# e2e/smoke rows on top of the old seed). Previous DB is backed up, never
# silently discarded.
if [ "$FRESH" -eq 1 ]; then
    [ -f "$DEMO_SEED_DB" ] || die "--fresh: seed DB not found: $DEMO_SEED_DB"
    if [ -f "$DB_PATH" ]; then
        backup="$DB_PATH.$(date +%Y%m%d-%H%M%S).bak"
        cp "$DB_PATH" "$backup"
        say "backed up previous demo DB -> $backup"
    fi
    rm -f "$DB_PATH" "$DB_PATH-wal" "$DB_PATH-shm"
    cp "$DEMO_SEED_DB" "$DB_PATH"
    say "fresh demo DB: $DEMO_SEED_DB -> $DB_PATH"
fi
export SIF_DB_PATH="$DB_PATH"

# --- ollama: reuse a live server, never restart one we did not start --------
if curl -sf --max-time 2 "$OLLAMA_URL/api/version" >/dev/null 2>&1; then
    say "ollama already running at :$OLLAMA_PORT — leaving it as-is"
elif command -v ollama >/dev/null 2>&1; then
    say "starting ollama serve (OLLAMA_NUM_PARALLEL=6 — DECISION_LOG D18)"
    OLLAMA_NUM_PARALLEL=6 nohup ollama serve >"$RUN_DIR/ollama.log" 2>&1 &
    echo $! > "$RUN_DIR/ollama.pid"
    ok=0
    for _ in $(seq 1 60); do
        if curl -sf --max-time 2 "$OLLAMA_URL/api/version" >/dev/null 2>&1; then ok=1; break; fi
        sleep 0.5
    done
    [ "$ok" -eq 1 ] || die "ollama did not come up in 30s — see .run/ollama.log"
    say "ollama up: $(curl -sf "$OLLAMA_URL/api/version")"
else
    warn "ollama binary not found — LLM rewording disabled; deterministic"
    warn "explanation templates carry the demo (template fallback by design)."
fi

# --- uvicorn: API + static dashboard in one process -------------------------
say "starting uvicorn on $BASE_URL (workers 1; db: $DB_PATH; log: $UVICORN_LOG)"
nohup "$VENV_PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --workers 1 \
    >"$UVICORN_LOG" 2>&1 &
echo $! > "$UVICORN_PIDFILE"

ok=0
for _ in $(seq 1 120); do
    if health="$(curl -sf --max-time 2 "$BASE_URL/api/health" 2>/dev/null)"; then ok=1; break; fi
    kill -0 "$(cat "$UVICORN_PIDFILE")" 2>/dev/null || break
    sleep 0.5
done
if [ "$ok" -ne 1 ]; then
    tail -n 20 "$UVICORN_LOG" >&2 || true
    die "uvicorn did not become healthy in 60s — see $UVICORN_LOG"
fi

classifier="$(printf '%s' "$health" | sed -n 's/.*"classifier":"\([^"]*\)".*/\1/p')"
say "healthy: $health"
[ "$classifier" = "MockClassifier" ] && warn "running on MockClassifier — NOT demo-ready"
echo
say "DEMO READY:  $BASE_URL/          (dashboard)"
say "             $BASE_URL/api/health (health)  $BASE_URL/docs (OpenAPI)"
say "DB:          $DB_PATH"
say "Stop with:   ./run.sh --stop"
