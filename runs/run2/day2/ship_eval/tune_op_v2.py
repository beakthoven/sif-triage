"""masked-v2 operating point re-tune (D19/D27 protocol) on the single-text
full-test scores written by score_full_test_v2.py.

Selection (frozen): max recall subject to precision >= 0.80, decisions on
p_raw = sigmoid(logit), tuned on the derived-label TEST split (temporal
holdout, gold-independent). The D27 amendment is built in from the start:
the scores ARE the single-text ship path, so the tuned threshold is the
single-text-tuned operating point (no batch32 variant needed; the v1
batch32_tuned block is kept only in v1's metrics for provenance).

Reuses runs/run2/day1/operating_point/tune_operating_point.py's verified
curve/selection math (its --self-check runs here first).

Writes:
  runs/run2/day2/ship_eval/operating_point_v2.json   (full analysis + PR curve)
  artifacts/models/masked-v2/metrics.json            (+ operating_point_test_tuned)
  artifacts/models/masked-v2/manifest.json           (metrics.json sha256/bytes
                                                      refreshed + local_amendments)

Run: .venv/bin/python runs/run2/day2/ship_eval/tune_op_v2.py
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "runs/run2/day1/operating_point"))

import tune_operating_point as top  # noqa: E402

MODEL_DIR = REPO / "artifacts/models/masked-v2"
SCORES = HERE / "single_text_masked_v2_test.jsonl"
FLOOR = 0.80

SELECTION_NOTE = (
    "D19 (runs/run2/DECISION_LOG.md): the val-frozen operating point "
    "(sif.operating_point) is vacuous at natural test prevalence — val "
    "prevalence 0.794 ~= the 0.80 precision floor, flag rate ~1.0 on test. "
    "Re-tuned on the derived-label TEST split (temporal holdout, "
    "gold-independent; artifacts/corpus/test.jsonl). The gold set remains "
    "the untouched final eval. Tuned 2026-09-08 by "
    "runs/run2/day2/ship_eval/tune_op_v2.py on SINGLE-TEXT scores "
    "(score_full_test_v2.py) — D27: single-text is the canonical scoring "
    "path everywhere, so this threshold is tuned on the deployment chain "
    "itself; no batch32 variant exists for v2."
)


def main() -> int:
    top.self_check()  # verified math, fails loudly

    rows = [json.loads(line) for line in SCORES.open()]
    import numpy as np
    y = np.array([r["sif_label"] for r in rows], dtype=np.int64)
    p = np.array([r["p_raw"] for r in rows], dtype=np.float64)
    n, n_pos = len(y), int(y.sum())
    prevalence = n_pos / n

    tcfg = json.loads((MODEL_DIR / "thresholds.json").read_text())
    temperature = float(tcfg["temperature"])
    frozen_raw = float(tcfg["sif_threshold"])

    curve = top.pr_curve(y, p)
    auc = top.auc_mann_whitney(y, p)
    ap = top.average_precision(curve, prevalence)
    main_op = top.select_at_floor(curve, FLOOR, n_pos, n)
    main_op["threshold_calibrated"] = top.cal_map(main_op["threshold"], temperature)
    extras = {f"recall_at_precision_{f:.2f}": top.select_at_floor(curve, f, n_pos, n)
              for f in (0.85, 0.90)}
    frozen = top.at_threshold(y, p, frozen_raw)
    apriori = top.at_threshold(y, p, 0.5)

    result = {
        "config": "masked-v2",
        "scoring": "single-text batch=1 int8 (D27 ship path; score_full_test_v2.py)",
        "n": n, "n_pos": n_pos, "prevalence": prevalence,
        "auc": auc, "average_precision": ap, "temperature": temperature,
        "val_frozen_op": {"threshold_raw": frozen_raw,
                          "threshold_calibrated": top.cal_map(frozen_raw, temperature),
                          **{k: v for k, v in frozen.items() if k != "threshold"}},
        "apriori_0.5_raw": apriori,
        "operating_point_test_tuned": main_op,
        **extras,
        "pr_curve": [{"threshold": t, "precision": pr, "recall": rc}
                     for t, pr, rc in curve],
    }
    (HERE / "operating_point_v2.json").write_text(json.dumps(result, indent=1) + "\n")

    print(f"[masked-v2] n={n} prevalence={prevalence:.4f} AUC={auc:.4f} AP={ap:.4f}")
    print(f"  tuned: thr_raw={main_op['threshold']:.6g} "
          f"thr_cal={main_op['threshold_calibrated']:.6g} "
          f"P={main_op['precision']:.4f} R={main_op['recall']:.4f} "
          f"F1={main_op['f1']:.4f} "
          f"TP/FP/FN/TN={main_op['confusion']['tp']}/{main_op['confusion']['fp']}/"
          f"{main_op['confusion']['fn']}/{main_op['confusion']['tn']} "
          f"flag_rate={main_op['flag_rate']:.4f}")
    for k, v in extras.items():
        print(f"  {k}: " + (f"R={v['recall']:.4f} thr={v['threshold']:.6g}"
                            if not v.get("floor_unreachable") else "UNREACHABLE"))
    print(f"  val-frozen (vacuous check): P={frozen['precision']:.4f} "
          f"R={frozen['recall']:.4f} flag_rate={frozen['flag_rate']:.4f}")
    print(f"  a-priori 0.5: P={apriori['precision']:.4f} R={apriori['recall']:.4f} "
          f"F1={apriori['f1']:.4f}")

    # --- write operating_point_test_tuned into masked-v2 metrics.json -------
    mp = MODEL_DIR / "metrics.json"
    metrics = json.loads(mp.read_text())
    metrics["operating_point_test_tuned"] = {
        "threshold": main_op["threshold"],
        "threshold_calibrated": main_op["threshold_calibrated"],
        "precision": main_op["precision"],
        "recall": main_op["recall"],
        "f1": main_op["f1"],
        "confusion": main_op["confusion"],
        "flag_rate": main_op["flag_rate"],
        "precision_floor": FLOOR,
        "selection": "max recall subject to precision >= 0.80",
        "selection_note": SELECTION_NOTE,
        "split": "artifacts/corpus/test.jsonl",
        "scores": str(SCORES.relative_to(REPO)),
        "n": n,
        "prevalence": prevalence,
        "auc": auc,
        "temperature": temperature,
    }
    mp.write_text(json.dumps(metrics, indent=1) + "\n")

    manifest_path = MODEL_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    blob = mp.read_bytes()
    entry = manifest["files"].setdefault("metrics.json", {})
    entry["sha256"] = hashlib.sha256(blob).hexdigest()
    entry["bytes"] = len(blob)
    manifest.setdefault("local_amendments", []).append(
        "2026-09-08: metrics.json gained operating_point_test_tuned (D19 "
        "test-split re-tune, D27 single-text-tuned from the start — scores "
        "are the batch=1 ship path; no batch32 variant); sha256/bytes "
        "refreshed. All other files unchanged from the Kaggle run.")
    manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"updated {mp} + {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
