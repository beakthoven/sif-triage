"""LOCAL two-tier parity for masked-v2 int8 (D13/D20 protocol, mirrors
runs/run2/day1/real_model_integration/parity_and_test2000.py + val_control.py
exactly, retargeted at artifacts/models/masked-v2).

Kaggle-side int8 gate for masked-v2 was RED (AUC drop 0.1305, agreement
0.99296 vs torch — runs/run2/day2/retrain_report.md). Day-1 masked-v1 showed
the identical Kaggle-RED/local-GREEN split (D20), so the local gate is the
deployability decision.

Checks:
  T2-200   : 200 test rows (seed 123) int8 vs fp32, same batch composition —
             decision agreement >= 0.995 at the frozen val op, AUC drop
             <= 0.005, recall@op drop <= 0.01 (D13 tier-2).
  T2-2000  : same gate on 2,000 test rows (seed 42) for a stable estimate.
  ST-2000  : the same 2,000 rows scored SINGLE-TEXT (batch=1, the D27 ship
             path) in both quants — decision agreement + max |dlogit| on the
             deployment chain itself.
  VAL      : int8 full val (6,820) AUC vs the torch checkpoint's val AUC
             (0.9969, metrics.json); fp32 on the seed-5 1,000-row subset.

Writes parity_v2.json next to this script.
Run: .venv/bin/python runs/run2/day2/ship_eval/parity_v2.py
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "day1" / "real_model_integration"))
from onnx_score import Scorer, sigmoid  # noqa: E402

from sklearn.metrics import roc_auc_score  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
MASKED_V2 = REPO / "artifacts/models/masked-v2"
TORCH_VAL_AUC = 0.9968976523973326  # masked-v2 metrics.json (torch, ep3)


def load_rows(path):
    rows = []
    with path.open() as f:
        for line in f:
            r = json.loads(line)
            rows.append({"id": r["id"], "text": r["masked_text"],
                         "y": int(r["sif_label"])})
    return rows


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
    print(f"parity[{name}]:", json.dumps(block), flush=True)
    return block


def main():
    test = load_rows(REPO / "artifacts/corpus/test.jsonl")
    par200 = random.Random(123).sample(test, 200)
    tst2000 = random.Random(42).sample(test, 2000)
    print(f"test rows {len(test)}; parity n=200 (seed 123, pos "
          f"{sum(r['y'] for r in par200)}), n=2000 (seed 42, pos "
          f"{sum(r['y'] for r in tst2000)})", flush=True)

    sc8 = Scorer(MASKED_V2, quant="int8", threads=8)
    sc32 = Scorer(MASKED_V2, quant="fp32", threads=8)
    thr, temp = sc8.sif_threshold, sc8.temperature
    print(f"v2 frozen val op: thr={thr:.10g} T={temp:.6f}", flush=True)

    out = {"model": "masked-v2", "frozen_val_threshold": thr, "temperature": temp}

    # --- same-composition batch parity (D13 tier-2, v1 protocol) -----------
    t0 = time.time()
    z8_200, _ = sc8.logits([r["text"] for r in par200])
    z8_2000, _ = sc8.logits([r["text"] for r in tst2000])
    t8 = time.time() - t0
    t0 = time.time()
    z32_200, _ = sc32.logits([r["text"] for r in par200])
    z32_2000, _ = sc32.logits([r["text"] for r in tst2000])
    t32 = time.time() - t0
    print(f"batch scoring: int8 {t8:.1f}s fp32 {t32:.1f}s", flush=True)

    out["batch32_same_composition"] = {
        "max_abs_dlogit_200": round(float(np.abs(z32_200 - z8_200).max()), 4),
        "max_abs_dlogit_2000": round(float(np.abs(z32_2000 - z8_2000).max()), 4),
        "rows_200_seed123": parity_block("200 (seed 123)", [r["y"] for r in par200],
                                         sigmoid(z32_200), sigmoid(z8_200), thr),
        "rows_2000_seed42": parity_block("2000 (seed 42)", [r["y"] for r in tst2000],
                                         sigmoid(z32_2000), sigmoid(z8_2000), thr),
        "seconds": {"int8": round(t8, 1), "fp32": round(t32, 1)},
    }

    # --- single-text ship-path parity (D27 chain) ---------------------------
    t0 = time.time()
    z8_st = np.array([sc8.logits([r["text"]], batch=1)[0][0] for r in tst2000])
    t8st = time.time() - t0
    t0 = time.time()
    z32_st = np.array([sc32.logits([r["text"]], batch=1)[0][0] for r in tst2000])
    t32st = time.time() - t0
    print(f"single-text scoring: int8 {t8st:.1f}s fp32 {t32st:.1f}s", flush=True)
    st_block = parity_block("2000 single-text", [r["y"] for r in tst2000],
                            sigmoid(z32_st), sigmoid(z8_st), thr)
    st_block["max_abs_dlogit"] = round(float(np.abs(z32_st - z8_st).max()), 4)
    st_block["mean_abs_dlogit"] = round(float(np.abs(z32_st - z8_st).mean()), 4)
    st_block["seconds"] = {"int8": round(t8st, 1), "fp32": round(t32st, 1)}
    out["single_text_ship_path"] = st_block

    # --- full-val AUC vs torch checkpoint -----------------------------------
    val = load_rows(REPO / "artifacts/corpus/val.jsonl")
    yv = np.array([r["y"] for r in val])
    t0 = time.time()
    z8_val, _ = sc8.logits([r["text"] for r in val])
    t8v = time.time() - t0
    auc8_val = float(roc_auc_score(yv, sigmoid(z8_val)))
    sub = random.Random(5).sample(range(len(val)), 1000)
    t0 = time.time()
    z32_val, _ = sc32.logits([val[i]["text"] for i in sub])
    t32v = time.time() - t0
    auc32_sub = float(roc_auc_score(yv[sub], sigmoid(z32_val)))
    auc8_sub = float(roc_auc_score(yv[sub], sigmoid(z8_val[sub])))
    out["val_control"] = {
        "int8_full_val": {"n": len(val), "auc": round(auc8_val, 6),
                          "delta_vs_torch_0.9969": round(TORCH_VAL_AUC - auc8_val, 6),
                          "seconds": round(t8v, 1)},
        "fp32_subset_seed5": {"n": 1000, "auc_fp32": round(auc32_sub, 6),
                              "auc_int8_same_rows": round(auc8_sub, 6),
                              "auc_drop": round(auc32_sub - auc8_sub, 6),
                              "seconds": round(t32v, 1)},
        "torch_val_auc_reference": TORCH_VAL_AUC,
        "note": "D13 int8 AUC-drop gate is decision-relevant on the fp32-vs-int8 "
                "drop; torch-vs-local-fp32 delta measures export fidelity.",
    }
    print("val_control:", json.dumps(out["val_control"]), flush=True)

    (HERE / "parity_v2.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {HERE / 'parity_v2.json'}")


if __name__ == "__main__":
    main()
