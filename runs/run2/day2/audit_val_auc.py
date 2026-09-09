"""Final-audit: independent int8 val-subset AUC recompute for masked-v2.

Mirrors parity_v2.py's fp32_subset_seed5 protocol (seed 5, 1,000 rows of
artifacts/corpus/val.jsonl, batch logits, int8) and compares against the
claimed auc_int8_same_rows = 0.993233 (torch val AUC reference 0.9969).
Run: PYTHONPATH=repo .venv/bin/python runs/run2/day2/audit_val_auc.py
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "day1" / "real_model_integration"))
from onnx_score import Scorer, sigmoid  # noqa: E402

REPO = HERE.parents[2]

val = []
with open(REPO / "artifacts/corpus/val.jsonl") as f:
    for line in f:
        r = json.loads(line)
        val.append({"id": r["id"], "text": r["masked_text"], "y": int(r["sif_label"])})
print(f"val rows: {len(val)}", flush=True)

sub = random.Random(5).sample(range(len(val)), 1000)
yv = np.array([val[i]["y"] for i in sub])
print(f"subset prevalence: {yv.mean():.4f}", flush=True)

sc8 = Scorer(REPO / "artifacts/models/masked-v2", quant="int8", threads=8)
print(f"thresholds.json: sif_threshold={sc8.sif_threshold} T={sc8.temperature}", flush=True)
t0 = time.time()
z8, _ = sc8.logits([val[i]["text"] for i in sub])
dt = time.time() - t0
auc8 = float(roc_auc_score(yv, sigmoid(z8)))
print(f"int8 seed-5 1000-row val AUC = {auc8:.6f}  (claimed 0.993233)  [{dt:.0f}s]", flush=True)
print(f"delta vs claimed: {auc8 - 0.993233:+.6f}; delta vs torch 0.9969: {0.9968976523973326 - auc8:+.6f}")
