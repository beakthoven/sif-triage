"""Latency benchmark for RealOnnxClassifier (ARCHITECTURE §E: <100 ms p95
unthrottled; bulk >=30 reports/s classify-only).

Measures, on this machine, per quant (int8 default, fp32 via --fp32):
  - seq128 single-text p50/p95/p99 over 200 predict() calls (single window,
    natural padding = seq-bucketing; ~126 body tokens fills the window)
  - batch-32 throughput (one padded batch of 32 through the session)
  - 1,500-word chunked end-to-end

Run: .venv/bin/python app/tests/onnx_bench.py [--fp32] [--runs N]
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.classifier import RealOnnxClassifier  # noqa: E402

MODEL_DIR = REPO_ROOT / "artifacts" / "models" / "masked-v2"

# ~135 words -> >=126 body tokens -> exactly fills one seq-128 window.
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


def pct(vals: list[float], q: float) -> float:
    vals = sorted(vals)
    k = (len(vals) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fp32", action="store_true", help="benchmark the fp32 artifact")
    ap.add_argument("--runs", type=int, default=200)
    args = ap.parse_args()

    import os
    os.environ["SIF_MODEL_QUANT"] = "fp32" if args.fp32 else "int8"
    clf = RealOnnxClassifier(MODEL_DIR)
    n_body = len(clf._tokenizer.encode(SEQ128_TEXT, add_special_tokens=False).ids)
    print(f"model: {clf.model_version}  (body tokens: {n_body}, 8 intra-op threads)")

    # warmup (session + arena alloc)
    for _ in range(10):
        clf.predict(SEQ128_TEXT)

    lat_ms: list[float] = []
    for _ in range(args.runs):
        t0 = time.perf_counter()
        clf.predict(SEQ128_TEXT)
        lat_ms.append((time.perf_counter() - t0) * 1000.0)
    print(f"\nseq128 single-text, n={args.runs}:")
    print(f"  p50 = {pct(lat_ms, 0.50):7.1f} ms")
    print(f"  p95 = {pct(lat_ms, 0.95):7.1f} ms")
    print(f"  p99 = {pct(lat_ms, 0.99):7.1f} ms")
    print(f"  mean = {statistics.fmean(lat_ms):5.1f} ms   min = {min(lat_ms):5.1f}   max = {max(lat_ms):5.1f}")

    # batch-32 throughput: 32 distinct-ish texts, one padded batch per round
    texts = [f"{SEQ128_TEXT} shift {i}." for i in range(32)]
    encs = [clf._tokenizer.encode(t, add_special_tokens=False) for t in texts]
    width = min(max(len(e.ids) for e in encs) + 2, clf.SEQ_LEN)
    ids = np.full((32, width), clf._pad_id, dtype=np.int64)
    mask = np.zeros((32, width), dtype=np.int64)
    for r, e in enumerate(encs):
        n = min(len(e.ids), width - 2)
        ids[r, 0] = clf._cls_id
        ids[r, 1:n + 1] = e.ids[:n]
        ids[r, n + 1] = clf._sep_id
        mask[r, :n + 2] = 1
    for _ in range(3):  # warmup
        clf._session.run(None, {"input_ids": ids, "attention_mask": mask})
    rounds = 10
    t0 = time.perf_counter()
    for _ in range(rounds):
        clf._session.run(None, {"input_ids": ids, "attention_mask": mask})
    dt = time.perf_counter() - t0
    print(f"\nbatch-32 throughput (batch seq={width}, {rounds} rounds):")
    print(f"  {32 * rounds / dt:6.1f} reports/s   ({dt / rounds * 1000:.0f} ms/batch)")

    # chunked 1,500-word input
    words = SEQ128_TEXT.split()
    long_text = " ".join(words[i % len(words)] for i in range(1500))
    t0 = time.perf_counter()
    lp = clf.predict(long_text)
    dt = time.perf_counter() - t0
    print(f"\n1,500-word chunked: {dt:.2f}s end-to-end (chunked={lp.chunked}, spans={len(lp.evidence_spans)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
