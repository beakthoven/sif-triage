"""Pipeline validation control: reproduce the Kaggle val metrics with the
local scorer.

The derived-test AUC (0.874 fp32 / 0.866 int8) is far below val (0.9966).
Before attributing that to the 2024-25 label-map degradation (SEV1-10:
high-energy prefix rate 55.4% -> 30.7%), prove the LOCAL scoring path
reproduces the val numbers the training run measured:
  - int8 ONNX on FULL val (6,820 rows): Kaggle measured AUC 0.9050
    (0.99658 - 0.09159 drop) and agreement 0.99296 vs torch-fp32.
  - fp32 ONNX on 1,000 val rows (subset for time): expect AUC ~= 0.9966.

Writes val_control.json next to this script.
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from onnx_score import REPO, Scorer, sigmoid  # noqa: E402

from sklearn.metrics import roc_auc_score  # noqa: E402

HERE = Path(__file__).resolve().parent


def main():
    rows = [json.loads(l) for l in (REPO / "artifacts/corpus/val.jsonl").open()]
    y = np.array([int(r["sif_label"]) for r in rows])
    texts = [r["masked_text"] for r in rows]
    print(f"val rows {len(rows)}, prevalence {y.mean():.4f}")

    sc8 = Scorer(REPO / "artifacts/models/masked-v1", quant="int8", threads=8)
    thr = sc8.sif_threshold
    t0 = time.time()
    z8, _ = sc8.logits(texts)
    t8 = time.time() - t0
    p8 = sigmoid(z8)
    auc8 = float(roc_auc_score(y, p8))

    sub = random.Random(5).sample(range(len(rows)), 1000)
    sc32 = Scorer(REPO / "artifacts/models/masked-v1", quant="fp32", threads=8)
    t0 = time.time()
    z32, _ = sc32.logits([texts[i] for i in sub])
    t32 = time.time() - t0
    p32 = sigmoid(z32)
    auc32 = float(roc_auc_score(y[sub], p32))
    # int8 on the same subset for a like-for-like drop
    auc8_sub = float(roc_auc_score(y[sub], p8[sub]))
    agree_sub = float(((p8[sub] >= thr) == (p32 >= thr)).mean())

    out = {
        "int8_full_val": {
            "n": len(rows),
            "auc": round(auc8, 6),
            "kaggle_int8_val_auc_expected": round(0.9965776545446866 - 0.09159214852637176, 6),
            "recall_at_frozen_op": round(float(((p8 >= thr) & (y == 1)).sum() / (y == 1).sum()), 4),
            "precision_at_frozen_op": round(float(((p8 >= thr) & (y == 1)).sum() / max((p8 >= thr).sum(), 1)), 4),
            "flag_rate": round(float((p8 >= thr).mean()), 4),
            "seconds": round(t8, 1),
        },
        "fp32_val_subset_seed5": {
            "n": 1000,
            "auc_fp32": round(auc32, 6),
            "auc_int8_same_rows": round(auc8_sub, 6),
            "auc_drop": round(auc32 - auc8_sub, 6),
            "agreement_at_frozen_op": round(agree_sub, 6),
            "seconds": round(t32, 1),
        },
        "torch_val_reference": {"auc": 0.9965776545446866, "op": "recall 1.0 @ thr 6.5813e-05, precision 0.80003"},
    }
    (HERE / "val_control.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
