#!/usr/bin/env bash
# selfcheck.sh — mandatory runnable check for run.sh (the offline demo spine).
#
# Two full cycles of: start -> /api/health -> /api/classify (span-validity
# invariant checked server-side contract) -> dashboard HTML at / -> stop ->
# port-free verification. Uses the real run.sh, no mocks of the harness.
# Exit 0 = pass. Run: packaging/selfcheck.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASE="http://127.0.0.1:${SIF_PORT:-8177}"
CYCLES=2
FAILED=0

say() { printf '[selfcheck] %s\n' "$*"; }
fail() { printf '[selfcheck] FAIL: %s\n' "$*" >&2; FAILED=1; }

# --allow-mock only when no ONNX artifact exists yet (run.sh has the same
# resolution order; the flag is inert once the real artifact lands).
MOCK_FLAG=()
if ! compgen -G "artifacts/models/*/*.onnx" >/dev/null && [ ! -f app/artifacts/model.onnx ]; then
    MOCK_FLAG=(--allow-mock)
    say "no ONNX artifact present — cycles run with --allow-mock"
fi

"$REPO_ROOT/run.sh" --stop >/dev/null 2>&1 || true   # clean slate

for cycle in $(seq 1 "$CYCLES"); do
    say "=== cycle $cycle/$CYCLES ==="

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
    health="$(curl -sf "$BASE/api/health")" || { fail "cycle $cycle: /api/health"; break; }
    status="$(jq -r '.status' <<<"$health")"
    classifier="$(jq -r '.classifier' <<<"$health")"
    [ "$status" = "ok" ] || fail "cycle $cycle: health.status=$status"
    case "$classifier" in MockClassifier|RealOnnxClassifier) : ;; *) fail "cycle $cycle: bad classifier $classifier";; esac
    say "health ok (classifier=$classifier)"

    # classify: 200, score in range, spans satisfy text[start:end]==span.text
    resp="$(curl -sf -X POST "$BASE/api/classify" -H 'Content-Type: application/json' \
        -d '{"text":"Worker grinding without face shield near live H2S flowline; LOTO not applied on the pump; kick reported on the pit."}')" \
        || { fail "cycle $cycle: /api/classify"; break; }
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

    # dashboard served by the same process at /
    html="$(curl -sf "$BASE/")" || { fail "cycle $cycle: GET / (dashboard)"; break; }
    grep -q 'id="root"' <<<"$html" || fail "cycle $cycle: / did not serve the React shell"
    grep -q 'SIF-Precursor' <<<"$html" || fail "cycle $cycle: dashboard title missing"
    asset="$(grep -o '/assets/index-[^"]*\.js' <<<"$html" | head -n1)"
    curl -sf "$BASE$asset" >/dev/null || fail "cycle $cycle: dashboard JS asset $asset not served"
    say "dashboard ok (index.html + $asset served by FastAPI)"

    # stop and verify the port is actually free
    "$REPO_ROOT/run.sh" --stop >/dev/null 2>&1 || fail "cycle $cycle: run.sh --stop non-zero"
    sleep 0.5
    if curl -sf --max-time 2 "$BASE/api/health" >/dev/null 2>&1; then
        fail "cycle $cycle: /api/health still answers after --stop"
    fi
    [ ! -f .run/uvicorn.pid ] || fail "cycle $cycle: uvicorn pidfile left behind"
    say "stop ok (port free, pidfiles cleaned)"
done

if [ "$FAILED" -ne 0 ]; then
    say "SELFCHECK FAIL"
    exit 1
fi
say "SELFCHECK PASS ($CYCLES clean cycles)"
