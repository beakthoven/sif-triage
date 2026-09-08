"""Decision-level int8-vs-fp32 parity AT THE TUNED OPERATING POINT (the
decision that actually ships), single-text, both models.

The D13 gate's agreement leg is quoted at the frozen val op (6.85e-5 for v2),
a threshold sitting in empty score space where quantization noise flips
low-density rows. The load-bearing question is whether int8 and fp32 agree
at the threshold the runtime actually applies — the test-tuned op.

Re-scores the seed-42 2,000-row test sample single-text (D27 path) with
int8 + fp32 for masked-v1 and masked-v2; reports decision agreement at each
model's own tuned op, flips with their p_raw values, and max|dlogit|.

Writes parity_at_op.json. Run AFTER tune_op_v2.py (reads both metrics.json).
Run: .venv/bin/python runs/run2/day2/ship_eval/parity_at_op.py
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "day1" / "real_model_integration"))
from onnx_score import REPO, Scorer, sigmoid  # noqa: E402

HERE = Path(__file__).resolve().parent


def main():
    test = [json.loads(l) for l in (REPO / "artifacts/corpus/test.jsonl").open()]
    sample = random.Random(42).sample(test, 2000)
    y = np.array([r["sif_label"] for r in sample])
    out = {}
    for name in ("masked-v1", "masked-v2"):
        mdir = REPO / f"artifacts/models/{name}"
        op = json.loads((mdir / "metrics.json").read_text())[
            "operating_point_test_tuned"]
        thr = float(op["threshold"])
        sc8 = Scorer(mdir, quant="int8", threads=8)
        sc32 = Scorer(mdir, quant="fp32", threads=8)
        z8 = np.array([sc8.logits([r["masked_text"]], batch=1)[0][0] for r in sample])
        z32 = np.array([sc32.logits([r["masked_text"]], batch=1)[0][0] for r in sample])
        p8, p32 = sigmoid(z8), sigmoid(z32)
        d8, d32 = p8 >= thr, p32 >= thr
        flips = np.nonzero(d8 != d32)[0]
        flip_rows = [{"id": sample[i]["id"], "y": int(y[i]),
                      "p_int8": round(float(p8[i]), 6),
                      "p_fp32": round(float(p32[i]), 6)} for i in flips]
        block = {
            "n": len(sample),
            "op_threshold_raw": thr,
            "agreement": round(float((d8 == d32).mean()), 6),
            "n_flips": len(flips),
            "flips": flip_rows,
            "max_abs_dlogit": round(float(np.abs(z8 - z32).max()), 4),
            "mean_abs_dlogit": round(float(np.abs(z8 - z32).mean()), 4),
            "recall_int8": round(float((d8 & (y == 1)).sum() / (y == 1).sum()), 4),
            "recall_fp32": round(float((d32 & (y == 1)).sum() / (y == 1).sum()), 4),
            "precision_int8": round(float((d8 & (y == 1)).sum() / max(d8.sum(), 1)), 4),
            "precision_fp32": round(float((d32 & (y == 1)).sum() / max(d32.sum(), 1)), 4),
        }
        out[name] = block
        print(f"{name}: agreement@tuned_op {block['agreement']} "
              f"({block['n_flips']} flips / {block['n']}), "
              f"P {block['precision_int8']} vs {block['precision_fp32']}, "
              f"R {block['recall_int8']} vs {block['recall_fp32']}")
        for f in flip_rows[:20]:
            print(f"   flip {f['id']} y={f['y']} p8={f['p_int8']} p32={f['p_fp32']}")
    (HERE / "parity_at_op.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {HERE / 'parity_at_op.json'}")


if __name__ == "__main__":
    main()
