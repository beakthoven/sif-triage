#!/usr/bin/env python3
"""Ingest-only latency re-measure (patched tree) — waits for a cool, quiet
machine, then POSTs the 5,050-row demo CSV to a throwaway server on :8195
with a throwaway DB. Records Tctl + load + mean MHz before/after so thermal
throttling is visible in the record.

Run: .venv/bin/python runs/run2/day2/ingest_remeasure.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEST_PORT = 8195
MODEL_DIR = REPO / "artifacts" / "models" / "masked-v2"


def tctl() -> float:
    out = subprocess.run(["sensors"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "Tctl" in line:
            return float(line.split("+")[1].split("°")[0])
    return float("nan")


def load1() -> float:
    return float(Path("/proc/loadavg").read_text().split()[0])


def cpu_ghz() -> float:
    mhz = []
    for p in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_cur_freq"):
        try:
            mhz.append(int(p.read_text()) / 1e6)
        except OSError:
            pass
    return sum(mhz) / len(mhz) if mhz else float("nan")


def main() -> int:
    print("waiting for quiet window (load1 < 2.0 and Tctl < 85C, 10 min cap)...", flush=True)
    deadline = time.time() + 600
    while time.time() < deadline:
        t, l = tctl(), load1()
        print(f"  Tctl={t:.1f}C load1={l:.2f}", flush=True)
        if t < 85.0 and l < 2.0:
            break
        time.sleep(20)
    else:
        print("no quiet window in 10 min — measuring anyway (documented)", flush=True)

    tmp = tempfile.TemporaryDirectory(prefix="sif-ingest-rem-")
    env = dict(os.environ,
               SIF_DB_PATH=str(Path(tmp.name) / "ing.db"),
               SIF_MODEL_PATH=str(MODEL_DIR),
               SIF_EXPLAIN_LLM="0")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(TEST_PORT)],
        cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{TEST_PORT}/api"
        for _ in range(100):
            try:
                with urllib.request.urlopen(base + "/health", timeout=2) as resp:
                    h = json.loads(resp.read())
                if h["status"] == "ok":
                    break
            except Exception:
                time.sleep(0.3)
        else:
            raise SystemExit("test server did not come up")
        print(f"server up: {h['model_version']}", flush=True)
        print(f"pre : Tctl={tctl():.1f}C load1={load1():.2f} cpu={cpu_ghz():.2f}GHz", flush=True)
        csv_text = (REPO / "artifacts/demo/bulk_ingest_5k.csv").read_text()
        body = json.dumps({"csv": csv_text, "source": "ingest-remasure"}).encode()
        req = urllib.request.Request(base + "/ingest", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=1800) as resp:
            ing = json.loads(resp.read())
        wall = time.perf_counter() - t0
        rate = ing["accepted"] / wall
        print(f"post: Tctl={tctl():.1f}C load1={load1():.2f} cpu={cpu_ghz():.2f}GHz", flush=True)
        print(f"INGEST: received={ing['received']} accepted={ing['accepted']} "
              f"skipped_dup={ing['skipped_duplicates']} wall={wall:.1f}s "
              f"rate={rate:.2f}/s SLA>=30: {'PASS' if rate >= 30 else 'FAIL'}", flush=True)
    finally:
        server.terminate()
        server.wait(timeout=15)
        tmp.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
