"""Latency on THIS machine (ARCHITECTURE acceptance bar: <100 ms p95
classify; D3 SLA: >=30 reports/s classify-only sustained, batch 32).

Ship path = app.classifier.RealOnnxClassifier.predict (int8, 8 threads,
sliding window for long texts — p99 corpus length is 112 tokens so nearly
all rows are single-window). Bulk path = onnx_score.Scorer batched logits.

Writes latency.json next to this script.
"""
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.classifier import RealOnnxClassifier  # noqa: E402
from onnx_score import Scorer  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / "latency.json"


def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = int(k)
    return xs[f] if f + 1 >= len(xs) else xs[f] + (xs[f + 1] - xs[f]) * (k - f)


def main():
    rows = [json.loads(l) for l in (REPO / "artifacts/corpus/test.jsonl").open()]
    random.Random(7)  # seed fixed for sample reproducibility
    texts = random.Random(7).sample([r["masked_text"] for r in rows], 200)

    clf = RealOnnxClassifier(REPO / "artifacts/models/masked-v1")  # int8, 8 threads
    assert clf.quant == "int8"
    for t in texts[:10]:  # warmup
        clf.predict(t)
    lat = []
    for t in texts:
        t0 = time.perf_counter()
        clf.predict(t)
        lat.append((time.perf_counter() - t0) * 1000)
    single = {
        "n": len(lat),
        "p50_ms": round(pct(lat, 0.50), 2),
        "p95_ms": round(pct(lat, 0.95), 2),
        "p99_ms": round(pct(lat, 0.99), 2),
        "mean_ms": round(statistics.mean(lat), 2),
        "min_ms": round(min(lat), 2),
        "max_ms": round(max(lat), 2),
        "pass_p95_lt_100ms": pct(lat, 0.95) < 100.0,
    }
    print("single-text (RealOnnxClassifier int8, 8 threads):", single)

    # Batch-32 throughput, classify-only (sif+rules logits), 640 rows.
    scorer = Scorer(REPO / "artifacts/models/masked-v1", quant="int8", threads=8)
    bulk_texts = [r["masked_text"] for r in rows[:640]]
    scorer.logits(bulk_texts[:64])  # warmup
    t0 = time.perf_counter()
    scorer.logits(bulk_texts, batch=32)
    dt = time.perf_counter() - t0
    batch = {
        "rows": len(bulk_texts),
        "batch_size": 32,
        "seconds": round(dt, 3),
        "rows_per_s": round(len(bulk_texts) / dt, 1),
        "ms_per_batch32": round(dt / (len(bulk_texts) / 32) * 1000, 1),
        "pass_sla_30rps": (len(bulk_texts) / dt) >= 30.0,
    }
    print("batch-32 throughput:", batch)

    out = {
        "machine": "AMD Ryzen AI 7 350 (16 logical), CPUExecutionProvider, "
                   "intra_op=8, ORT_ENABLE_ALL; power clamp RESOLVED "
                   "(CPU_CLAMP_REPORT.md) — cores boost under load",
        "model": "artifacts/models/masked-v1/sif_multitask_int8.onnx",
        "single_text_predict": single,
        "batch32_classify_only": batch,
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
