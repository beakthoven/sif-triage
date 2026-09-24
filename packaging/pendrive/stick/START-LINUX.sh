#!/usr/bin/env bash
# START-LINUX.sh — plug-and-play SIF-precursor demo (OIL India, SIH 2026 PS 26165)
#
# Double-click or:  bash START-LINUX.sh
#
# First run extracts a self-contained Python + the app to a local cache
# (~/.cache/sif-demo) — nothing needs to be installed, no network needed.
# Later runs start in seconds. The USB stick itself is never written to.
set -euo pipefail

STICK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRATCH="${SIF_DEMO_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/sif-demo}"
PORT="${SIF_PORT:-8177}"
BASE="http://127.0.0.1:${PORT}"

say()  { printf '[sif-demo] %s\n' "$*"; }
die()  { printf '[sif-demo] ERROR: %s\n' "$*" >&2; exit 1; }

# Already up? Just open the dashboard.
if curl -sf --max-time 2 "$BASE/api/health" >/dev/null 2>&1; then
    say "demo already running — opening $BASE/"
    (xdg-open "$BASE/" >/dev/null 2>&1 &) || true
    exit 0
fi

# --- first-run (or version-bump) extract -----------------------------------
if [ ! -f "$SCRATCH/VERSION" ] || ! cmp -s "$STICK/VERSION" "$SCRATCH/VERSION"; then
    say "first run on this machine — unpacking to $SCRATCH (one time, ~1 min)..."
    mkdir -p "$SCRATCH"
    tar -xzf "$STICK/payload.tar.gz" -C "$SCRATCH"
    tar -xzf "$STICK/runtimes/linux-py314.tar.gz" -C "$SCRATCH"
    cp "$STICK/VERSION" "$SCRATCH/VERSION"
fi

PY="$SCRATCH/python/bin/python3"
[ -x "$PY" ] || die "runtime extract broken ($PY missing) — delete $SCRATCH and retry"
PAYLOAD="$SCRATCH/payload"
[ -f "$PAYLOAD/artifacts/models/masked-v2/sif_multitask_int8.onnx" ] || die "model missing in payload"

# --- demo database: seed once, never overwrite a reviewed one ---------------
if [ ! -f "$SCRATCH/runtime.db" ]; then
    cp "$PAYLOAD/seed/demo_pre.db" "$SCRATCH/runtime.db"
    say "demo database seeded (4,548 reports)"
fi

# --- optional: ollama rewording LLM (template fallback works without it) ----
if command -v ollama >/dev/null 2>&1; then
    if ! curl -sf --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
        OLLAMA_NUM_PARALLEL=6 nohup ollama serve >"$SCRATCH/ollama.log" 2>&1 &
        for _ in $(seq 1 60); do
            curl -sf --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1 && break
            sleep 0.5
        done
    fi
    if ! ollama list 2>/dev/null | grep -q '^qwen3:4b' && [ -f "$STICK/extras/ollama-qwen3-4b.tar.gz" ]; then
        say "installing qwen3:4b into local ollama (one time, ~1 min)..."
        tar -xzf "$STICK/extras/ollama-qwen3-4b.tar.gz" -C "${OLLAMA_MODELS:-$HOME/.ollama/models}" \
            --checkpoint=2000 --checkpoint-action=echo="  ... %{%T}t" 2>/dev/null || \
        tar -xzf "$STICK/extras/ollama-qwen3-4b.tar.gz" -C "${OLLAMA_MODELS:-$HOME/.ollama/models}"
    fi
else
    say "ollama not installed — running with built-in explanation templates (fully supported)"
fi

# --- start the app -----------------------------------------------------------
cd "$PAYLOAD"
export SIF_MODEL_PATH="$PAYLOAD/artifacts/models/masked-v2/sif_multitask_int8.onnx"
export SIF_DB_PATH="$SCRATCH/runtime.db"
export SIF_PORT="$PORT"

"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --workers 1 \
    >"$SCRATCH/uvicorn.log" 2>&1 &
UV_PID=$!
trap 'kill $UV_PID 2>/dev/null || true' EXIT INT TERM

ok=0
for _ in $(seq 1 120); do
    if curl -sf --max-time 2 "$BASE/api/health" >/dev/null 2>&1; then ok=1; break; fi
    kill -0 $UV_PID 2>/dev/null || break
    sleep 0.5
done
[ "$ok" -eq 1 ] || { tail -n 20 "$SCRATCH/uvicorn.log" >&2; die "app did not start — see $SCRATCH/uvicorn.log"; }

say "DEMO READY: $BASE/"
(xdg-open "$BASE/" >/dev/null 2>&1 &) || true
say "leave this window open; Ctrl-C stops the demo"
wait $UV_PID
