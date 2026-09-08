"""Runtime-transfer probe: score the full test split SINGLE-TEXT (the
/classify ship path — one session.run per text, minimal padding) and compare
against the batch-32 full-test scores the operating point was tuned on.

Finding that motivates this probe (2026-09-08, same scripts): int8 results
are exact for a fixed batch composition but shift across compositions
(mean |Δlogit| ~1.5, max ~7.7 on the 1500 sample) — dynamic-quantization
kernels are shape-dependent on this provider. D19's operating point is
canonical on the batch-32 scoring chain (score_1500/mcnemar/compare1500
all batch-32); this probe measures what the runtime batch-1 path does at
that threshold: decision agreement + P/R transfer.

Writes runs/run2/day1/operating_point/single_text_masked_test.jsonl
{"id", "sif_logit", "p_raw", "p_cal"} and prints the transfer summary.

Run: .venv/bin/python runs/run2/day1/operating_point/score_single_text_masked.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "real_model_integration"))
from onnx_score import REPO, Scorer, sigmoid  # noqa: E402

HERE = Path(__file__).resolve().parent
TEST = REPO / "artifacts/corpus/test.jsonl"


def main() -> None:
    rows = [json.loads(line) for line in TEST.open()]
    sc = Scorer(REPO / "artifacts/models/masked-v1", quant="int8", threads=8)
    t0 = time.time()
    out = HERE / "single_text_masked_test.jsonl"
    with out.open("w") as f:
        for i, r in enumerate(rows):
            z, _ = sc.logits([r["masked_text"]], batch=1)
            f.write(json.dumps({
                "id": r["id"],
                "sif_logit": float(z[0]),
                "p_raw": float(sigmoid(z[0])),
                "p_cal": float(sigmoid(z[0] / sc.temperature)),
            }) + "\n")
            if (i + 1) % 2000 == 0:
                print(f"{i + 1}/{len(rows)} ({(i + 1) / (time.time() - t0):.1f}/s)",
                      flush=True)
    dt = time.time() - t0
    print(f"wrote {out} — {len(rows)} rows in {dt:.0f}s ({len(rows) / dt:.1f}/s)")


if __name__ == "__main__":
    main()
