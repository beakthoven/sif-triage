"""PR-curve analysis + operating-point selection on the derived TEST split
(D19). Reads the full-precision score files written by score_full_test.py
(no model needed — re-runnable in milliseconds).

Selection rule (frozen by the task, mirrors train.py operating_point):
  operating point = max recall subject to precision >= 0.80
Decisions use p_raw = sigmoid(logit) — the scale the val-frozen point was
tuned on. The calibrated (displayed) threshold is the identical-decision map
thr_cal = sigmoid(logit(thr_raw)/T); PR curves are invariant to the choice.

Also reports: recall@P>=0.85, recall@P>=0.90, the val-frozen op row, the
a-priori raw-0.5 row, AUC (Mann-Whitney, tie-corrected), average precision.

Writes:
  runs/run2/day1/operating_point/operating_point.json   (all numbers + PR curve)
  artifacts/models/{masked,unmasked}-v1/metrics.json    (+ operating_point_test_tuned,
                                                         val-frozen sif.operating_point KEPT)
  artifacts/models/{masked,unmasked}-v1/manifest.json   (metrics.json sha256/bytes refreshed —
                                                         the file changed on purpose, the hash
                                                         record must not silently stale)

Run: .venv/bin/python runs/run2/day1/operating_point/tune_operating_point.py
Self-check (--self-check): AUC/AP/selection validated against sklearn on
random data + two constructed edge cases (floor unreachable, oscillating
precision). No model or score files needed.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
FLOOR_MAIN = 0.80
FLOORS_EXTRA = (0.85, 0.90)
SELECTION_NOTE = (
    "D19 (runs/run2/DECISION_LOG.md): the val-frozen operating point "
    "(sif.operating_point) is vacuous at natural test prevalence — val "
    "prevalence 0.794 ~= the 0.80 precision floor, flag rate 1.0 on test. "
    "Re-tuned on the derived-label TEST split (temporal holdout, "
    "gold-independent; artifacts/corpus/test.jsonl). The gold set remains "
    "the untouched final eval. Tuned 2026-09-08 by "
    "runs/run2/day1/operating_point/tune_operating_point.py."
)


# ---------------------------------------------------------------- metrics --
def auc_mann_whitney(y: np.ndarray, p: np.ndarray) -> float:
    """P(pos score > neg score) + 0.5*P(tie), via average ranks."""
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=np.float64)
    sp = p[order]
    i = 0
    while i < len(p):
        j = i
        while j + 1 < len(p) and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0  # average 1-based rank
        i = j + 1
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def pr_curve(y: np.ndarray, p: np.ndarray) -> list[tuple[float, float, float]]:
    """(threshold, precision, recall) at every distinct score, decision
    p >= thr. Computed on one descending sweep; thresholds are the distinct
    score values themselves (flag the top-k)."""
    order = np.argsort(-p, kind="mergesort")
    ys = y[order]
    ps = p[order]
    n_pos = int(ys.sum())
    tp_c = np.cumsum(ys)
    fp_c = np.cumsum(1 - ys)
    # distinct-score boundaries: keep index i when ps[i+1] < ps[i]
    keep = np.nonzero(np.diff(ps) < 0)[0]
    keep = np.append(keep, len(ps) - 1)
    out = []
    for i in keep:
        tp, fp = int(tp_c[i]), int(fp_c[i])
        out.append((float(ps[i]), tp / (tp + fp), tp / n_pos))
    return out


def average_precision(curve: list[tuple[float, float, float]], prevalence: float) -> float:
    """AP = sum over recall steps of step * precision (sklearn convention),
    including the (recall 0 -> first recall) start and the tail to recall 1."""
    ap = 0.0
    r_prev = 0.0
    for _, prec, rec in curve:
        ap += (rec - r_prev) * prec
        r_prev = rec
    ap += (1.0 - r_prev) * prevalence  # flag-everything tail
    return ap


def select_at_floor(curve: list[tuple[float, float, float]], floor: float,
                    n_pos: int, n: int) -> dict:
    """Max recall subject to precision >= floor. Tie-break: higher precision,
    then earlier (larger threshold). floor_unreachable mirrors train.py."""
    best = None
    for thr, prec, rec in curve:
        if prec >= floor - 1e-12:
            key = (rec, prec, thr)
            if best is None or key > best[0]:
                best = (key, thr, prec, rec)
    if best is None:
        return {"floor": floor, "floor_unreachable": True}
    _, thr, prec, rec = best
    tp = int(round(rec * n_pos))
    flagged = None
    for t, pr, rc in curve:  # recover FP from the same prefix
        if t == thr and pr == prec and rc == rec:
            fp = int(round(tp / prec - tp)) if prec > 0 else 0
            flagged = tp + fp
            break
    fp = flagged - tp
    fn = n_pos - tp
    tn = n - n_pos - fp
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"floor": floor, "floor_unreachable": False, "threshold": thr,
            "precision": prec, "recall": rec, "f1": f1,
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "flag_rate": flagged / n}


def at_threshold(y: np.ndarray, p: np.ndarray, thr: float) -> dict:
    pred = p >= thr
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int(((~pred) & (y == 1)).sum())
    tn = int((~pred & (y == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"threshold": float(thr), "precision": prec, "recall": rec, "f1": f1,
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            "flag_rate": float(pred.mean())}


def logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def cal_map(thr_raw: float, temperature: float) -> float:
    """Identical-decision map raw -> calibrated (onnx_score.self_check)."""
    return 1.0 / (1.0 + math.exp(-logit(thr_raw) / temperature))


# ---------------------------------------------------------------- analysis --
def analyze(name: str, scores_path: Path, model_dir: Path) -> dict:
    rows = [json.loads(line) for line in scores_path.open()]
    y = np.array([r["sif_label"] for r in rows], dtype=np.int64)
    p = np.array([r["p_raw"] for r in rows], dtype=np.float64)
    n, n_pos = len(y), int(y.sum())
    prevalence = n_pos / n
    tcfg = json.loads((model_dir / "thresholds.json").read_text())
    temperature = float(tcfg["temperature"])
    frozen_raw = float(tcfg["sif_threshold"])

    curve = pr_curve(y, p)
    auc = auc_mann_whitney(y, p)
    ap = average_precision(curve, prevalence)

    main = select_at_floor(curve, FLOOR_MAIN, n_pos, n)
    main["threshold_calibrated"] = cal_map(main["threshold"], temperature)
    extras = {f"recall_at_precision_{f:.2f}": select_at_floor(curve, f, n_pos, n)
              for f in FLOORS_EXTRA}
    frozen = at_threshold(y, p, frozen_raw)
    apriori = at_threshold(y, p, 0.5)

    result = {
        "config": name, "n": n, "n_pos": n_pos, "prevalence": prevalence,
        "auc": auc, "average_precision": ap, "temperature": temperature,
        "val_frozen_op": {"threshold_raw": frozen_raw,
                          "threshold_calibrated": cal_map(frozen_raw, temperature),
                          **{k: v for k, v in frozen.items() if k != "threshold"}},
        "apriori_0.5_raw": apriori,
        "operating_point_test_tuned": main,
        **extras,
        "pr_curve": [{"threshold": t, "precision": pr, "recall": rc}
                     for t, pr, rc in curve],
    }
    return result


def update_model_artifacts(model_dir: Path, result: dict, scores_rel: str) -> None:
    """Add operating_point_test_tuned to metrics.json (val-frozen kept), then
    refresh metrics.json's sha256/bytes in manifest.json."""
    mp = model_dir / "metrics.json"
    metrics = json.loads(mp.read_text())
    op = result["operating_point_test_tuned"]
    metrics["operating_point_test_tuned"] = {
        "threshold": op["threshold"],
        "threshold_calibrated": op["threshold_calibrated"],
        "precision": op["precision"],
        "recall": op["recall"],
        "f1": op["f1"],
        "confusion": op["confusion"],
        "flag_rate": op["flag_rate"],
        "precision_floor": FLOOR_MAIN,
        "selection": "max recall subject to precision >= 0.80",
        "selection_note": SELECTION_NOTE,
        "split": "artifacts/corpus/test.jsonl",
        "scores": scores_rel,
        "n": result["n"],
        "prevalence": result["prevalence"],
        "auc": result["auc"],
        "temperature": result["temperature"],
    }
    mp.write_text(json.dumps(metrics, indent=1) + "\n")

    manifest_path = model_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    blob = mp.read_bytes()
    entry = manifest["files"].setdefault("metrics.json", {})
    entry["sha256"] = hashlib.sha256(blob).hexdigest()
    entry["bytes"] = len(blob)
    manifest.setdefault("local_amendments", []).append(
        "2026-09-08: metrics.json gained operating_point_test_tuned (D19 "
        "test-split re-tune); sha256/bytes refreshed. All other files "
        "unchanged from the Kaggle run.")
    manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"updated {mp} + {manifest_path}")


# --------------------------------------------------------------- selfcheck --
def self_check() -> None:
    from sklearn.metrics import average_precision_score, roc_auc_score

    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 4000)
    p = np.clip(rng.normal(y * 0.8, 1.0), 0, 1)
    assert abs(auc_mann_whitney(y, p) - roc_auc_score(y, p)) < 1e-9
    curve = pr_curve(y, p)
    assert abs(average_precision(curve, y.mean()) - average_precision_score(y, p)) < 1e-9

    # ties: duplicated scores must match sklearn exactly
    p2 = np.round(p, 1)
    assert abs(auc_mann_whitney(y, p2) - roc_auc_score(y, p2)) < 1e-9

    # constructed: floor unreachable -> flagged, no bogus threshold
    # (precision at every distinct-score prefix is <= 0.5)
    y3 = np.array([0, 1, 0, 1, 0, 0, 0, 0])
    p3 = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2])
    sel = select_at_floor(pr_curve(y3, p3), 0.80, int(y3.sum()), len(y3))
    assert sel["floor_unreachable"] is True

    # constructed: oscillating precision — max-recall eligible point wins
    # even though an earlier prefix also clears the floor
    y4 = np.array([1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    p4 = np.linspace(0.99, 0.01, len(y4))
    c4 = pr_curve(y4, p4)
    sel = select_at_floor(c4, 0.80, int(y4.sum()), len(y4))
    eligible = [(t, pr, rc) for t, pr, rc in c4 if pr >= 0.80 - 1e-12]
    assert abs(sel["recall"] - max(rc for _, _, rc in eligible)) < 1e-12
    assert sel["precision"] >= 0.80
    # confusion cross-check against at_threshold at the same threshold
    cross = at_threshold(y4, p4, sel["threshold"])
    assert cross["confusion"] == sel["confusion"], (cross, sel)

    # cal_map is the identical-decision map (identity from onnx_score)
    z = np.linspace(-30, 20, 2001)
    T = 1.683972954750061
    raw_thr = 0.42
    cal_thr = cal_map(raw_thr, T)
    sig = lambda x: 1 / (1 + np.exp(-x))
    assert ((sig(z) >= raw_thr) == (sig(z / T) >= cal_thr)).all()
    print("tune_operating_point self-check OK: AUC/AP==sklearn, ties, "
          "floor-unreachable, oscillation, confusion cross-check, cal-map identity")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    self_check()
    results = {}
    for name in ("masked", "unmasked"):
        scores_path = HERE / f"scores_{name}_test.jsonl"
        model_dir = REPO / "artifacts" / f"models/{name}-v1"
        res = analyze(name, scores_path, model_dir)
        results[name] = res
        op = res["operating_point_test_tuned"]
        print(f"[{name}] n={res['n']} prevalence={res['prevalence']:.4f} "
              f"AUC={res['auc']:.4f} AP={res['average_precision']:.4f}")
        print(f"  tuned: thr_raw={op['threshold']:.6g} thr_cal={op['threshold_calibrated']:.6g} "
              f"P={op['precision']:.4f} R={op['recall']:.4f} F1={op['f1']:.4f} "
              f"TP/FP/FN/TN={op['confusion']['tp']}/{op['confusion']['fp']}/"
              f"{op['confusion']['fn']}/{op['confusion']['tn']} "
              f"flag_rate={op['flag_rate']:.4f}")
        for k, v in res.items():
            if k.startswith("recall_at_precision_"):
                print(f"  {k}: R={v.get('recall')} thr={v.get('threshold'):.6g}"
                      if not v.get("floor_unreachable") else f"  {k}: UNREACHABLE")
        fr = res["val_frozen_op"]
        print(f"  val-frozen: P={fr['precision']:.4f} R={fr['recall']:.4f} "
              f"flag_rate={fr['flag_rate']:.4f} (vacuous check)")
        ap5 = res["apriori_0.5_raw"]
        print(f"  a-priori 0.5: P={ap5['precision']:.4f} R={ap5['recall']:.4f} F1={ap5['f1']:.4f}")
        update_model_artifacts(model_dir, res, str(scores_path.relative_to(REPO)))
    out = HERE / "operating_point.json"
    out.write_text(json.dumps(results, indent=1) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
