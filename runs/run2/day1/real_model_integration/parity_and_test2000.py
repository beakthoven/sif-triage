"""Two jobs in one pass over the model (saves re-inference):

1. PARITY (D13 tier-2, local): fp32 ONNX vs int8 ONNX on 200 corpus rows
   (seed 123): decision agreement at the frozen threshold >= 0.995,
   AUC drop <= 0.005, recall@op drop <= 0.01. Extended to the 2,000-row
   test sample for a stable estimate (200-row AUC is noisy).
   Tier-1 (torch vs fp32 ONNX, |dlogit| <= 1e-4) was measured on Kaggle at
   export time — no torch here; values cited in the report.
2. DERIVED-TEST SANITY: 2,000 random rows (seed 42) from
   artifacts/corpus/test.jsonl scored with the masked int8 artifact;
   SIF AUC + recall/precision at the frozen operating point (canonical
   thresholds.json; stale insurance-copy values cross-checked).

Writes parity.json, test2000.json, test2000_scores.csv next to this script.
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from onnx_score import Scorer, sigmoid  # noqa: E402

from sklearn.metrics import roc_auc_score  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
MASKED = REPO / "artifacts/models/masked-v1"
STALE_INSURANCE = {"threshold": 6.103742451126668e-05, "temperature": 1.6959888935089111}


def load_test():
    rows = []
    with (REPO / "artifacts/corpus/test.jsonl").open() as f:
        for line in f:
            r = json.loads(line)
            rows.append({"id": r["id"], "text": r["masked_text"],
                         "y": int(r["sif_label"]), "rules": r["rules"]})
    return rows


def op_metrics(y, prob, thr):
    d = prob >= thr
    y = np.asarray(y)
    tp = int((d & (y == 1)).sum()); fp = int((d & (y == 0)).sum())
    fn = int(((~d) & (y == 1)).sum()); tn = int(((~d) & (y == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"threshold": thr, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "flag_rate": round(float(d.mean()), 4)}


def parity_block(name, y, p_fp32, p_int8, thr):
    d32, d8 = p_fp32 >= thr, p_int8 >= thr
    agree = float((d32 == d8).mean())
    auc32 = float(roc_auc_score(y, p_fp32))
    auc8 = float(roc_auc_score(y, p_int8))
    y = np.asarray(y)
    rec32 = float((d32 & (y == 1)).sum() / max((y == 1).sum(), 1))
    rec8 = float((d8 & (y == 1)).sum() / max((y == 1).sum(), 1))
    block = {
        "n": len(y),
        "agreement": round(agree, 6),
        "n_flips": int((d32 != d8).sum()),
        "auc_fp32": round(auc32, 6), "auc_int8": round(auc8, 6),
        "auc_drop": round(auc32 - auc8, 6),
        "recall_at_op_fp32": round(rec32, 4), "recall_at_op_int8": round(rec8, 4),
        "recall_at_op_drop": round(rec32 - rec8, 4),
        "pass_d13": bool(agree >= 0.995 and (auc32 - auc8) <= 0.005
                         and (rec32 - rec8) <= 0.01),
    }
    print(f"parity[{name}]:", json.dumps(block))
    return block


def main():
    rows = load_test()
    parity_rows = random.Random(123).sample(rows, 200)
    test_rows = random.Random(42).sample(rows, 2000)
    print(f"loaded {len(rows)} test rows; parity n=200 (seed 123), "
          f"test2000 n=2000 (seed 42); pos: parity "
          f"{sum(r['y'] for r in parity_rows)}, test2000 {sum(r['y'] for r in test_rows)}")

    sc8 = Scorer(MASKED, quant="int8", threads=8)
    thr, temp = sc8.sif_threshold, sc8.temperature
    print(f"canonical frozen: thr={thr:.10g} T={temp:.10f} "
          f"(stale insurance copy: {STALE_INSURANCE['threshold']:.6g} / "
          f"{STALE_INSURANCE['temperature']:.4f})")

    t0 = time.time()
    z8_par, _ = sc8.logits([r["text"] for r in parity_rows])
    z8_test, _ = sc8.logits([r["text"] for r in test_rows])
    t_int8 = time.time() - t0
    print(f"int8 scoring: {len(parity_rows) + len(test_rows)} rows in {t_int8:.1f}s")

    sc32 = Scorer(MASKED, quant="fp32", threads=8)
    t0 = time.time()
    z32_par, _ = sc32.logits([r["text"] for r in parity_rows])
    z32_test, _ = sc32.logits([r["text"] for r in test_rows])
    t_fp32 = time.time() - t0
    print(f"fp32 scoring: {len(parity_rows) + len(test_rows)} rows in {t_fp32:.1f}s")

    y_par = [r["y"] for r in parity_rows]
    y_test = [r["y"] for r in test_rows]
    p32_par, p8_par = sigmoid(z32_par), sigmoid(z8_par)
    p32_test, p8_test = sigmoid(z32_test), sigmoid(z8_test)

    parity = {
        "threshold": thr, "temperature": temp,
        "max_abs_dlogit_200": round(float(np.abs(z32_par - z8_par).max()), 4),
        "max_abs_dlogit_2000": round(float(np.abs(z32_test - z8_test).max()), 4),
        "rows_200_seed123": parity_block("200 rows (seed 123)", y_par, p32_par, p8_par, thr),
        "rows_2000_seed42": parity_block("2000 rows (seed 42)", y_test, p32_test, p8_test, thr),
        "seconds": {"int8": round(t_int8, 1), "fp32": round(t_fp32, 1)},
    }
    (HERE / "parity.json").write_text(json.dumps(parity, indent=1) + "\n")

    sanity = {
        "sample": "2000 random rows, seed 42, artifacts/corpus/test.jsonl (masked_text)",
        "n": len(y_test), "n_pos": int(sum(y_test)),
        "prevalence": round(sum(y_test) / len(y_test), 4),
        "auc_int8": round(float(roc_auc_score(y_test, p8_test)), 6),
        "auc_fp32": round(float(roc_auc_score(y_test, p32_test)), 6),
        "val_auc_reference": 0.9965776545446866,
        "frozen_op_canonical": op_metrics(y_test, p8_test, thr),
        "frozen_op_stale_insurance_thr": op_metrics(
            y_test, p8_test, STALE_INSURANCE["threshold"]),
        "decision_note": "flag iff sigmoid(z/T) >= sigmoid(logit(thr)/T) "
                         "<=> sigmoid(z) >= thr (identity asserted in "
                         "onnx_score.self_check)",
    }
    (HERE / "test2000.json").write_text(json.dumps(sanity, indent=1) + "\n")
    print("test2000 sanity:", json.dumps(sanity, indent=1))

    with (HERE / "test2000_scores.csv").open("w") as f:
        f.write("id,y,sif_logit_int8,sif_logit_fp32\n")
        for r, a, b in zip(test_rows, z8_test, z32_test):
            f.write(f"{r['id']},{r['y']},{a:.6f},{b:.6f}\n")
    print("wrote parity.json, test2000.json, test2000_scores.csv")


if __name__ == "__main__":
    main()
