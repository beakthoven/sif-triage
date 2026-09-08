#!/usr/bin/env bash
# Start (or --stop) the 4 blind-labeling servers on 127.0.0.1:8001-8004.
#
#   gold/start_labeling.sh          start all four, print URLs
#   gold/start_labeling.sh --stop   stop all four
#   gold/start_labeling.sh --status show who is up + labeling progress
#
# Logs: .run/gold_labelers/<labeler>.log · PIDs: .run/gold_labelers/<labeler>.pid
# Labels append to artifacts/gold/labels/labeler_<x>.jsonl (re-run resumes).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
RUN_DIR=.run/gold_labelers
LABELERS=(a b c d)
PORTS=(8001 8002 8003 8004)
mkdir -p "$RUN_DIR"

port_busy() { ss -ltn 2>/dev/null | grep -q "127.0.0.1:$1 "; }

stop_all() {
    for i in "${!LABELERS[@]}"; do
        lab=${LABELERS[$i]}; pidfile="$RUN_DIR/$lab.pid"
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null && \
               grep -q "labeler_app.py" "/proc/$pid/cmdline" 2>/dev/null; then
                kill "$pid" && echo "stopped labeler_$lab (pid $pid)"
            else
                echo "labeler_$lab: pid $pid not running (stale pidfile removed)"
            fi
            rm -f "$pidfile"
        else
            echo "labeler_$lab: no pidfile"
        fi
    done
}

status() {
    for i in "${!LABELERS[@]}"; do
        lab=${LABELERS[$i]}; port=${PORTS[$i]}
        if port_busy "$port"; then
            prog=$($PY - "$port" <<'EOF'
import json, sys, urllib.request
try:
    d = json.load(urllib.request.urlopen(
        f"http://127.0.0.1:{sys.argv[1]}/api/next", timeout=3))
    print(f"{d['done']}/{d['total']} labeled")
except Exception as e:
    print(f"up (progress unreadable: {e})")
EOF
)
            echo "labeler_$lab  http://127.0.0.1:$port/  UP   $prog"
        else
            echo "labeler_$lab  http://127.0.0.1:$port/  down"
        fi
    done
}

case "${1:-start}" in
    --stop)   stop_all ;;
    --status) status ;;
    start|"")
        if [ "${1:-start}" != "start" ] && [ "${1:-start}" != "" ]; then
            echo "usage: $0 [--stop|--status]" >&2; exit 2
        fi
        for i in "${!LABELERS[@]}"; do
            lab=${LABELERS[$i]}; port=${PORTS[$i]}
            if port_busy "$port"; then
                echo "labeler_$lab: port $port already busy — leaving it alone " \
                     "(resume: just open the URL; stop: $0 --stop)"
                continue
            fi
            nohup "$PY" gold/labeler_app.py --labeler "$lab" --port "$port" \
                --host "${HOST:-127.0.0.1}" \
                >> "$RUN_DIR/$lab.log" 2>&1 &
            echo $! > "$RUN_DIR/$lab.pid"
        done
        sleep 1
        echo
        status
        echo
        echo "Each labeler reads gold/RUBRIC.md, then opens THEIR url. Ctrl-C/nohup-exit"
        echo "is safe — progress is in artifacts/gold/labels/. Stop all: $0 --stop"
        ;;
esac
