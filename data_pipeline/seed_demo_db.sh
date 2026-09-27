#!/usr/bin/env bash
# Seed a demo DB through the REAL /api/ingest path (demo-day parity — same
# validation, batching, gates, thresholds, storage the UI uses).
# Usage: seed_demo_db.sh <port> <db_path> <csv_path> <source_label> [keep]
#   Without "keep", <db_path> is DELETED first (idempotent re-runs). With
#   "keep", an existing DB is opened and the CSV is ingested on top of it
#   (how demo_post.db is built from a copy of demo_pre.db).
# Kills the uvicorn it started when done. Never touches :8177.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${1:?port}"; DB="${2:?db path}"; CSV="${3:?csv}"; SRC="${4:?source label}"
MODE="${5:-fresh}"
if [ "$MODE" != "keep" ]; then
  mkdir -p "$(dirname "$DB")"
  rm -f "$DB" "$DB-wal" "$DB-shm"
fi

SIF_DB_PATH="$DB" SIF_PORT="$PORT" \
SIF_MODEL_PATH="$REPO/artifacts/models/masked-v2/sif_multitask_int8.onnx" \
  "$REPO/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --workers 1 &
UVPID=$!
cleanup() { kill "$UVPID" 2>/dev/null || true; wait "$UVPID" 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 0.5
done
health="$(curl -sf "http://127.0.0.1:$PORT/api/health")"
echo "health: $health"
case "$health" in
  *RealOnnxClassifier*) : ;;
  *) echo "FATAL: classifier is not RealOnnxClassifier — aborting (no MOCK seeding)"; exit 1 ;;
esac

"$REPO/.venv/bin/python" - "$PORT" "$CSV" "$SRC" <<'PY'
import json, sys, time, urllib.request
port, csv_path, src = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(csv_path, encoding="utf-8").read()
body = json.dumps({"csv": text, "source": src}).encode()
t0 = time.perf_counter()
req = urllib.request.Request(
    f"http://127.0.0.1:{port}/api/ingest", data=body,
    headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=3600) as r:
    out = json.loads(r.read())

# app.routes.py ingest has two shapes: 200 IngestResult (sync, <=100 unique
# rows / idempotent replay) or 202 IngestJobAccepted (bulk job id to poll).
if out.get("job_id") and out.get("poll") and out.get("status") == "queued":
    while True:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}{out['poll']}", timeout=60) as pr:
            st = json.loads(pr.read())
        if st["status"] in ("done", "error"):
            break
        time.sleep(2.0)
    if st["status"] == "error":
        raise SystemExit(f"ingest job failed: {st.get('detail')}")
    out = st

print(json.dumps({
    "received": out["received"], "accepted": out["accepted"],
    "rejected": out["rejected"],
    "skipped_duplicates": out.get("skipped_duplicates"),
    "elapsed_s": round(time.perf_counter() - t0, 1),
}))
PY

curl -sf "http://127.0.0.1:$PORT/api/metrics/summary"
echo
echo "seeded: $DB"
