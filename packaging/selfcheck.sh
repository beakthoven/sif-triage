#!/usr/bin/env bash
# selfcheck.sh — mandatory runnable check for run.sh (the offline demo spine).
#
# Two full cycles of: start -> /api/health -> /api/classify (span-validity
# invariant checked server-side contract) -> dashboard HTML at / -> stop ->
# port-free verification. Uses the real run.sh, no mocks of the harness.
# Exit 0 = pass. Run: packaging/selfcheck.sh   (custom port: SIF_PORT=8230)
#
# Dashboard proof is title-free on purpose — titles drift and the old
# grep 'SIF-Precursor' broke when the title became "Safety Report Triage —
# OIL India". The stable markers are: served index.html contains id="root",
# the referenced JS bundle fetches 200, and /api/health returns status=ok
# with a real classifier name.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PORT="${SIF_PORT:-8177}"
BASE="http://127.0.0.1:$PORT"
CYCLES=2
FAILED=0

say() { printf '[selfcheck] %s\n' "$*"; }
fail() { printf '[selfcheck] FAIL: %s\n' "$*" >&2; FAILED=1; }

# Loud, specific preflight: these tools are hard requirements of the check
# below (jq parses the API contracts, bc times startup, ss resolves which
# pid holds our port). Fail before any cycle rather than mid-cycle.
for tool in jq bc ss; do
    command -v "$tool" >/dev/null 2>&1 || {
        printf '[selfcheck] FAIL: required tool "%s" is not installed — install it and rerun\n' "$tool" >&2
        exit 1
    }
done

# --allow-mock only when no ONNX artifact exists yet (run.sh has the same
# resolution order; the flag is inert once the real artifact lands).
MOCK_FLAG=()
if ! compgen -G "artifacts/models/*/*.onnx" >/dev/null && [ ! -f app/artifacts/model.onnx ]; then
    MOCK_FLAG=(--allow-mock)
    say "no ONNX artifact present — cycles run with --allow-mock"
fi

# Clean slate — but port-aware. Match run.sh's port-scoped pidfile so only
# this selfcheck's own leftover process can be stopped; another port is left
# alone (each cycle's start then diagnoses anything else holding OUR port).
PIDFILE="$REPO_ROOT/.run/uvicorn-$PORT.pid"
pidfile_pid="$(cat "$PIDFILE" 2>/dev/null || true)"
port_pid="$(ss -tlnpH "sport = :$PORT" 2>/dev/null | grep -o 'pid=[0-9]*' | head -n1 | cut -d= -f2 || true)"
if [ -n "$port_pid" ] && [ "$port_pid" = "$pidfile_pid" ]; then
    "$REPO_ROOT/run.sh" --stop >/dev/null 2>&1 || true   # our own leftover
fi

for cycle in $(seq 1 "$CYCLES"); do
    say "=== cycle $cycle/$CYCLES ==="

    # Fail before starting if something already holds our port — otherwise a
    # failed previous stop cascades into confusing "already running" behavior.
    if curl -sf --max-time 2 "$BASE/api/health" >/dev/null 2>&1; then
        fail "cycle $cycle: port $PORT already serves /api/health BEFORE start — previous stop failed or a foreign process holds the port; aborting"
        break
    fi

    t0=$(date +%s.%N)
    if ! "$REPO_ROOT/run.sh" "${MOCK_FLAG[@]}" >/tmp/sif-selfcheck-start.log 2>&1; then
        cat /tmp/sif-selfcheck-start.log >&2
        fail "cycle $cycle: run.sh start exited non-zero"
        break
    fi
    t1=$(date +%s.%N)
    startup_s=$(echo "$t1 - $t0" | bc)
    say "startup: ${startup_s}s (uvicorn start -> /api/health 200)"

    # health
    health="$(curl -sf "$BASE/api/health")" || { fail "cycle $cycle: /api/health curl failed — server did not come up (start log: /tmp/sif-selfcheck-start.log)"; break; }
    status="$(jq -r '.status' <<<"$health")"
    classifier="$(jq -r '.classifier' <<<"$health")"
    [ "$status" = "ok" ] || fail "cycle $cycle: health.status=$status (expected ok)"
    case "$classifier" in MockClassifier|RealOnnxClassifier) : ;; *) fail "cycle $cycle: health.classifier='$classifier' is not a real classifier (expected RealOnnxClassifier, or MockClassifier only under --allow-mock)";; esac
    say "health ok (classifier=$classifier)"

    # classify: 200, score in range, spans satisfy text[start:end]==span.text
    resp="$(curl -sf -X POST "$BASE/api/classify" -H 'Content-Type: application/json' \
        -d '{"text":"Worker grinding without face shield near live H2S flowline; LOTO not applied on the pump; kick reported on the pit."}')" \
        || { fail "cycle $cycle: /api/classify curl failed"; break; }
    jq -e '
        (.sif_score >= 0 and .sif_score <= 1)
        and (.rule_probs | length == 7)
        and (.well_control == true)
        and (.evidence_spans | length > 0)
    ' >/dev/null <<<"$resp" || fail "cycle $cycle: classify contract violated: $resp"
    spans_ok="$(jq -r --arg t "Worker grinding without face shield near live H2S flowline; LOTO not applied on the pump; kick reported on the pit." \
        '[.evidence_spans[] | .text == $t[.start:.end]] | all' <<<"$resp")"
    [ "$spans_ok" = "true" ] || fail "cycle $cycle: span invariant text[start:end]==span.text violated"
    score="$(jq -r '.sif_score' <<<"$resp")"
    say "classify ok (sif_score=$score, spans valid, well_control tag on)"

    # dashboard served by the same process at / — title-free proof (titles
    # drift; the old 'SIF-Precursor' grep broke on the rename to
    # "Safety Report Triage — OIL India"). Stable markers: id="root" plus a
    # JS bundle that actually serves, on top of the healthy API above.
    html="$(curl -sf "$BASE/")" || { fail "cycle $cycle: GET / (dashboard) curl failed"; break; }
    grep -q 'id="root"' <<<"$html" || fail "cycle $cycle: / did not serve the React shell (no id=\"root\" in index.html)"
    asset="$(grep -o '/assets/index-[^"]*\.js' <<<"$html" | head -n1)"
    if [ -z "$asset" ]; then
        fail "cycle $cycle: served index.html references no /assets/index-*.js bundle"
    else
        curl -sf "$BASE$asset" >/dev/null || fail "cycle $cycle: dashboard JS asset $asset not served"
    fi
    say "dashboard ok (React shell + $asset served by FastAPI)"

    # stop and verify the port is actually free
    "$REPO_ROOT/run.sh" --stop >/dev/null 2>&1 || fail "cycle $cycle: run.sh --stop non-zero"
    sleep 0.5
    if curl -sf --max-time 2 "$BASE/api/health" >/dev/null 2>&1; then
        fail "cycle $cycle: /api/health still answers after --stop"
    fi
    [ ! -f "$PIDFILE" ] || fail "cycle $cycle: $PIDFILE left behind"
    say "stop ok (port free, pidfiles cleaned)"
done

if [ "$FAILED" -ne 0 ]; then
    say "SELFCHECK FAIL"
    exit 1
fi
say "SELFCHECK PASS ($CYCLES clean cycles)"
