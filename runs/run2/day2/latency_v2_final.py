#!/usr/bin/env python3
"""Final masked-v2 latency re-measure — machine UNCLAMPED (Sep 9, night wave).

Replaces the masked-v1 numbers on record (p95 19.7 ms, 33.73/s bulk). Measures
the SHIP config (artifacts/models/masked-v2, int8, single-text D27 path):

  A. model-only, in-process RealOnnxClassifier.predict:
     A1. seq128 canonical single-window text x 200 runs (same protocol as the
         v1 19.7 ms measurement — app/tests/onnx_bench.py SEQ128_TEXT)
     A2. 200 real derived-test rows (seed 20260909, realistic length mix,
         some multi-window chunked)
     A3. fp32 comparison, seq128 x 50 runs (SIF_MODEL_QUANT=fp32 fallback)
  B. end-to-end API on the LIVE demo stack :8177 (masked-v2, gates incl.
     near-dup on the real 70k index): POST /api/classify x 200 over the same
     200 real test rows + x 200 seq128 (wire + gates + classify).
  C. bulk ingest rate: throwaway uvicorn :8190 + throwaway SQLite, POST the
     full 5,050-row demo CSV, wall time -> reports/s (SLA >= 30/s).

Writes runs/run2/day2/latency_v2_final.json and prints the markdown table.

Run: .venv/bin/python runs/run2/day2/latency_v2_final.py
"""
from __future__ import annotations

import json
import os
import random
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

OUT_JSON = Path(__file__).with_suffix(".json")
LIVE_BASE = "http://127.0.0.1:8177/api"
TEST_PORT = 8190
MODEL_DIR = REPO / "artifacts" / "models" / "masked-v2"

# Same text as app/tests/onnx_bench.py (>=126 body tokens = exactly one full
# seq-128 window) so numbers are directly comparable to the v1 record.
SEQ128_TEXT = (
    "Night shift derrick hand was grinding a flange on the live flowline near the "
    "mud pumps without a face shield while the crane was lifting a suspended load "
    "over the walkway; the harness anchor point on the scaffold was missing, the "
    "confined space tank entry had no gas test, LOTO was not applied on the pump "
    "motor, the vehicle was speeding on the lease road and the rigging sling showed "
    "damage; sparks fell near the open hatch and the crew kept working at height "
    "without fall arrest while the supervisor signed the permit from the office "
    "trailer and the doghouse radio stayed silent during the whole lifting operation"
)


def cpu_ghz() -> float:
    mhz = []
    for p in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_cur_freq"):
        try:
            mhz.append(int(p.read_text()) / 1e6)
        except OSError:
            pass
    return sum(mhz) / len(mhz) if mhz else float("nan")


def cpu_temp() -> float:
    try:
        out = subprocess.run(["sensors"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if "Tctl" in line:
                return float(line.split("+")[1].split("°")[0])
    except Exception:
        pass
    return float("nan")


def governor() -> str:
    p = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    return p.read_text().strip() if p.exists() else "?"


def pct(vals: list[float], q: float) -> float:
    vals = sorted(vals)
    k = (len(vals) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def summarize(lat_ms: list[float]) -> dict:
    return {
        "n": len(lat_ms),
        "p50": round(pct(lat_ms, 0.50), 2),
        "p95": round(pct(lat_ms, 0.95), 2),
        "p99": round(pct(lat_ms, 0.99), 2),
        "mean": round(statistics.fmean(lat_ms), 2),
        "min": round(min(lat_ms), 2),
        "max": round(max(lat_ms), 2),
    }


def post_classify(base: str, text: str, timeout: float = 30.0) -> float:
    """One POST /api/classify round trip; returns wall ms."""
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        base + "/classify", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()
    return (time.perf_counter() - t0) * 1000.0


def main() -> int:
    results: dict = {"env": {}}
    print(f"governor={governor()}  cpu={cpu_ghz():.2f} GHz  temp={cpu_temp()}C")
    results["env"] = {
        "governor": governor(), "cpu_ghz_start": round(cpu_ghz(), 3),
        "temp_c_start": cpu_temp(), "model_dir": str(MODEL_DIR.relative_to(REPO)),
    }

    # ---- A. model-only -------------------------------------------------------
    from app.classifier import RealOnnxClassifier

    os.environ.pop("SIF_MODEL_QUANT", None)
    clf = RealOnnxClassifier(MODEL_DIR)
    n_body = len(clf._tokenizer.encode(SEQ128_TEXT, add_special_tokens=False).ids)
    print(f"[A] model={clf.model_version} quant={clf.quant} T={clf.temperature} "
          f"flag_threshold={clf.sif_flag_threshold} seq128_body_tokens={n_body}")
    results["model"] = {
        "model_version": clf.model_version, "quant": clf.quant,
        "temperature": clf.temperature,
        "sif_flag_threshold": clf.sif_flag_threshold,
        "seq128_body_tokens": n_body,
    }

    rows = []
    with open(REPO / "artifacts/corpus/test.jsonl") as f:
        for line in f:
            rows.append(json.loads(line)["masked_text"])
    sample = random.Random(20260909).sample(rows, 200)

    for name, texts, warmup in (
        ("A1_seq128_x200", [SEQ128_TEXT] * 200, 10),
        ("A2_realtest_x200", sample, 5),
    ):
        for t in texts[:warmup]:
            clf.predict(t)
        lat = []
        for t in texts:
            t0 = time.perf_counter()
            clf.predict(t)
            lat.append((time.perf_counter() - t0) * 1000.0)
        s = summarize(lat)
        results[name] = s
        print(f"  {name}: p50={s['p50']} p95={s['p95']} p99={s['p99']} "
              f"mean={s['mean']} min={s['min']} max={s['max']}")
    n_chunked = sum(1 for t in sample if len(clf._tokenizer.encode(t, add_special_tokens=False).ids) > 126)
    results["A2_realtest_x200"]["n_chunked_inputs"] = n_chunked
    print(f"    (A2: {n_chunked}/200 inputs chunked >1 window)")

    os.environ["SIF_MODEL_QUANT"] = "fp32"
    clf32 = RealOnnxClassifier(MODEL_DIR)
    for _ in range(5):
        clf32.predict(SEQ128_TEXT)
    lat = []
    for _ in range(50):
        t0 = time.perf_counter()
        clf32.predict(SEQ128_TEXT)
        lat.append((time.perf_counter() - t0) * 1000.0)
    s = summarize(lat)
    results["A3_fp32_seq128_x50"] = s
    print(f"  A3_fp32_seq128_x50: p50={s['p50']} p95={s['p95']} p99={s['p99']}")
    os.environ.pop("SIF_MODEL_QUANT", None)
    del clf, clf32

    # ---- B. end-to-end API on the live stack ---------------------------------
    with urllib.request.urlopen(LIVE_BASE + "/health", timeout=10) as resp:
        health = json.loads(resp.read())
    print(f"[B] live :8177 health: {health['model_version']} "
          f"classifier={health['classifier']} n_reports={health['n_reports']}")
    results["live_health"] = health
    if "masked-v2" not in health["model_version"]:
        raise SystemExit("live stack is not masked-v2 — refusing to measure")

    for name, texts in (("B1_api_seq128_x200", [SEQ128_TEXT] * 200),
                        ("B2_api_realtest_x200", sample)):
        for t in texts[:5]:
            post_classify(LIVE_BASE, t)
        lat = [post_classify(LIVE_BASE, t) for t in texts]
        s = summarize(lat)
        results[name] = s
        print(f"  {name}: p50={s['p50']} p95={s['p95']} p99={s['p99']} "
              f"mean={s['mean']} max={s['max']}")

    # ---- C. bulk ingest on throwaway server ----------------------------------
    tmp = tempfile.TemporaryDirectory(prefix="sif-lat-ingest-")
    env = dict(os.environ,
               SIF_DB_PATH=str(Path(tmp.name) / "lat.db"),
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
            raise SystemExit("test server did not come up on :8190")
        print(f"[C] throwaway server up: {h['model_version']} — ingesting 5,050-row CSV")
        csv_text = (REPO / "artifacts/demo/bulk_ingest_5k.csv").read_text()
        body = json.dumps({"csv": csv_text, "source": "latency-final"}).encode()
        req = urllib.request.Request(base + "/ingest", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=1200) as resp:
            ing = json.loads(resp.read())
        wall = time.perf_counter() - t0
        rate = ing["accepted"] / wall
        results["C_bulk_ingest"] = {
            "received": ing["received"], "accepted": ing["accepted"],
            "rejected": ing["rejected"],
            "skipped_duplicates": ing["skipped_duplicates"],
            "wall_s": round(wall, 1), "reports_per_s": round(rate, 2),
            "sla_pass": rate >= 30.0,
        }
        print(f"  ingest: received={ing['received']} accepted={ing['accepted']} "
              f"skipped_dup={ing['skipped_duplicates']} wall={wall:.1f}s "
              f"rate={rate:.2f}/s SLA>=30: {'PASS' if rate >= 30 else 'FAIL'}")
    finally:
        server.terminate()
        server.wait(timeout=15)
        tmp.cleanup()

    results["env"]["cpu_ghz_end"] = round(cpu_ghz(), 3)
    results["env"]["temp_c_end"] = cpu_temp()
    OUT_JSON.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {OUT_JSON}")
    print(f"end: cpu={cpu_ghz():.2f} GHz temp={cpu_temp()}C")
    return 0


if __name__ == "__main__":
    sys.exit(main())
