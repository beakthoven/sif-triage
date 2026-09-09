"""Final-audit: in-process verifier for the live ship config.

1. Instantiate RealOnnxClassifier on artifacts/models/masked-v2 (the exact
   loader code path the :8177 server ran) and dump the loaded operating
   point, temperature, rule thresholds.
2. Re-run a 50-row single-text latency sample on the int8 model and compare
   against the claimed p50 11.9 / p95 19.7 / p99 40.2 ms (measured Day-1 on
   masked-v1; v2 is the same architecture/quant).
3. CPU freq snapshot to confirm the clamp stays off during measurement.
"""
import json
import random
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.classifier import RealOnnxClassifier  # noqa: E402


def cpu_ghz():
    out = subprocess.run(
        ["grep", "-m", "8", "model name\\|cpu MHz", "/proc/cpuinfo"],
        capture_output=True, text=True).stdout
    mhz = [float(l.split(":")[1]) for l in out.splitlines() if "MHz" in l]
    return sum(mhz) / len(mhz) / 1000 if mhz else float("nan")


def main():
    clf = RealOnnxClassifier(REPO / "artifacts/models/masked-v2")
    print(f"model_version      = {clf.model_version}")
    print(f"quant              = {clf.quant}")
    print(f"temperature        = {clf.temperature!r}")
    print(f"sif_flag_threshold = {clf.sif_flag_threshold!r}  (expect 0.6581082996119922)")
    print(f"rule_thresholds    = {json.dumps(clf.rule_thresholds, sort_keys=True)}")

    # 50-row latency sample: deterministic seed, median-length-ish real test rows
    rows = []
    with open(REPO / "artifacts/corpus/test.jsonl") as f:
        for line in f:
            r = json.loads(line)
            rows.append(r["masked_text"])
    rng = random.Random(20260909)
    sample = rng.sample(rows, 50)

    # warmup (5 rows, not timed)
    for t in sample[:5]:
        clf.predict(t)

    lat = []
    for t in sample:
        t0 = time.perf_counter()
        clf.predict(t)
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    n = len(lat)
    def pct(p):
        k = (n - 1) * p
        lo, hi = int(k), min(int(k) + 1, n - 1)
        return lat[lo] + (lat[hi] - lat[lo]) * (k - lo)
    print(f"\nlatency n={n} (single-text predict, int8, 8 threads, incl. tokenize+chunk+spans)")
    print(f"  p50 = {pct(0.50):6.2f} ms   p95 = {pct(0.95):6.2f} ms   p99 = {pct(0.99):6.2f} ms")
    print(f"  mean = {sum(lat)/n:6.2f} ms   min = {lat[0]:6.2f}   max = {lat[-1]:6.2f}")
    print(f"  cpu GHz during run: {cpu_ghz():.2f}")
    toks = [len(clf._tokenizer.encode(t, add_special_tokens=False).ids) for t in sample]
    print(f"  sample token lens: min {min(toks)} med {sorted(toks)[25]} max {max(toks)} "
          f"(chunked rows: {sum(1 for x in toks if x > 126)})")


if __name__ == "__main__":
    main()
