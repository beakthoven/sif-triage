#!/usr/bin/env python3
"""eval_calibration.py — ECE + Brier for the SIF head, written into metrics.json.

Renamed 2026-09-25 from calibrate_eval.py (same logic; the manifest's
local_amendments note keeps the original-name history).

A4 (calibration workstream). train.py fit_temperature() fits T on val sif
logits only (train.py:486-503); metrics.json ships T=1.6484 with no
calibration metric anywhere. This script closes that gap:

  ECE   — expected calibration error, equal-width bins (default 15),
          sum_b (n_b/N) * |acc_b - conf_b|
  Brier — mean((p - y)^2)

on every held-out (score, label) source that exists on disk:

  test  runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl
        derived-label TEST split (temporal holdout, gold-independent),
        single-text batch=1 int8 scores (score_full_test_v2.py), with
        sif_label / p_raw / p_cal per row. The raw corpus split
        (artifacts/corpus/test.jsonl) is NOT on this disk; the labels ship
        inside this scores file instead.
  gold  artifacts/gold/model_scores.jsonl joined with consensus labels
        reconstructed from artifacts/gold/labels_merged_final.jsonl minus
        artifacts/gold/adjudication_queue_final.jsonl (matches
        gold_metrics_final.json's consensus policy; n=407 expected).

p_cal = sigmoid(logit(p_raw)/T) with T read from thresholds.json — the
deployment transform (app/classifier.py maps the raw threshold through the
same T). Both raw and calibrated variants are reported so the effect of the
temperature is visible. T was fit on val only, so ECE/Brier here are
held-out numbers, not resubstitution.

Writes (fields ADDED, nothing removed — metrics.json gains "calibration"):
  artifacts/models/masked-v2/metrics.json   calibration block
  artifacts/models/masked-v2/manifest.json  files["metrics.json"] sha/bytes
                                            refreshed + local_amendments note
                                            (same amendment path tune_op_v2.py
                                            established)

If a source is missing the script says SKIP for it and moves on; with NO
held-out source present it writes nothing and exits 0 with a clear message
("re-run when the held-out scores are present").

Run: .venv/bin/python training/eval_calibration.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL_DIR = REPO / "artifacts" / "models" / "masked-v2"

TEST_SCORES = REPO / "runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl"
GOLD_SCORES = REPO / "artifacts/gold/model_scores.jsonl"
GOLD_LABELS = REPO / "artifacts/gold/labels_merged_final.jsonl"
GOLD_QUEUE = REPO / "artifacts/gold/adjudication_queue_final.jsonl"

AMENDMENT_TAG = "eval_calibration.py"   # marker used to keep amendments idempotent


def ece(y, p, bins):
    """Expected calibration error over equal-width bins (last bin closed)."""
    n = len(y)
    edges = [i / bins for i in range(bins + 1)]
    err = 0.0
    for b in range(bins):
        lo, hi = edges[b], edges[b + 1]
        idx = [i for i, v in enumerate(p)
               if (lo <= v < hi) or (b == bins - 1 and v == 1.0)]
        if not idx:
            continue
        acc = sum(y[i] for i in idx) / len(idx)
        conf = sum(p[i] for i in idx) / len(idx)
        err += len(idx) / n * abs(acc - conf)
    return err


def brier(y, p):
    return sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / len(y)


def bin_table(y, p, bins):
    """Per-bin (count, mean_p, mean_y) for the reliability printout."""
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, v in enumerate(p)
               if (lo <= v < hi) or (b == bins - 1 and v == 1.0)]
        if not idx:
            out.append(None)
            continue
        out.append({"n": len(idx),
                    "mean_p": round(sum(p[i] for i in idx) / len(idx), 4),
                    "mean_y": round(sum(y[i] for i in idx) / len(idx), 4)})
    return out


def sha256_file(path, _buf=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(_buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def consensus_gold_labels():
    """Reproduce gold_metrics_final.json's consensus policy: unanimous label
    across the item's raters, no 'unsure', not in the adjudication queue."""
    queue_ids = set()
    if GOLD_QUEUE.exists():
        for line in GOLD_QUEUE.open(encoding="utf-8"):
            if line.strip():
                queue_ids.add(json.loads(line)["gold_id"])
    labels = {}
    for line in GOLD_LABELS.open(encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        vals = [d["label"] for d in row["labels"].values()]
        if row["gold_id"] in queue_ids:
            continue
        if len(set(vals)) == 1 and vals[0] in ("sif", "non_sif"):
            labels[row["gold_id"]] = 1 if vals[0] == "sif" else 0
    return labels, len(queue_ids)


def load_test():
    rows = [json.loads(l) for l in TEST_SCORES.open(encoding="utf-8")
            if l.strip()]
    y = [int(r["sif_label"]) for r in rows]
    return y, [r["p_raw"] for r in rows], [r["p_cal"] for r in rows], \
        ("runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl",
         "derived-label TEST split (temporal holdout, gold-independent); "
         "raw corpus split artifacts/corpus/test.jsonl is NOT on this disk — "
         "labels ship inside the scores file")


def load_gold():
    labels, n_queue = consensus_gold_labels()
    y, praw, pcal = [], [], []
    for line in GOLD_SCORES.open(encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r["gold_id"] not in labels:
            continue
        y.append(labels[r["gold_id"]])
        praw.append(r["p_raw"])
        pcal.append(r["p_cal"])
    return y, praw, pcal, (
        "artifacts/gold/model_scores.jsonl + consensus labels from "
        "artifacts/gold/labels_merged_final.jsonl",
        f"consensus policy of gold_metrics_final.json: unanimous rater "
        f"label, no 'unsure', minus {n_queue} adjudication-pending items; "
        f"reconstructed n_consensus={len(labels)} (expected 407)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ece-bins", type=int, default=15)
    ap.add_argument("--metrics", default=str(MODEL_DIR / "metrics.json"),
                    help="metrics.json to amend (default masked-v2)")
    args = ap.parse_args(argv)

    thr_path = MODEL_DIR / "thresholds.json"
    temperature = None
    if thr_path.exists():
        temperature = json.loads(thr_path.read_text()).get("temperature")

    datasets = {}
    for name, loader in (("test", load_test), ("gold", load_gold)):
        try:
            datasets[name] = loader()
        except FileNotFoundError as e:
            print(f"SKIP [{name}]: held-out source not on disk ({e}) — "
                  f"re-run eval_calibration.py when it is present")
    if not datasets:
        print("SKIPPED — no held-out (score, label) data found anywhere; "
              "metrics.json left untouched.")
        return 0

    cal = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                         time.gmtime()),
           "ece_bins": args.ece_bins, "temperature": temperature,
           "metric_defs": "ECE = sum_b (n_b/N)*|acc_b - conf_b| over "
                          f"{args.ece_bins} equal-width bins; "
                          "Brier = mean((p-y)^2). p_cal = "
                          "sigmoid(logit(p_raw)/T); T fit on val only "
                          "(train.py fit_temperature) so these are held-out."}
    for name, (y, praw, pcal, src) in datasets.items():
        blk = {"source": src[0], "labels": src[1], "n": len(y),
               "prevalence": sum(y) / len(y),
               "ece_p_cal": ece(y, pcal, args.ece_bins),
               "brier_p_cal": brier(y, pcal),
               "ece_p_raw": ece(y, praw, args.ece_bins),
               "brier_p_raw": brier(y, praw)}
        cal[name] = blk
        print(f"[{name}] n={len(y)} prevalence={blk['prevalence']:.4f}")
        print(f"  p_cal: ECE={blk['ece_p_cal']:.4f} "
              f"Brier={blk['brier_p_cal']:.4f}")
        print(f"  p_raw: ECE={blk['ece_p_raw']:.4f} "
              f"brier={blk['brier_p_raw']:.4f}")

    # cross-check: the calibrated threshold must be decision-equivalent to the
    # raw one (it is the same cut mapped through T) — fails loudly if p_cal
    # was written with a different transform than thresholds.json temperature
    op = None
    mpath = Path(args.metrics)
    metrics = json.loads(mpath.read_text(encoding="utf-8"))
    op = metrics.get("operating_point_test_tuned")
    if op and "test" in datasets:
        y, praw, pcal, _ = datasets["test"]
        raw_thr, cal_thr = op["threshold"], op["threshold_calibrated"]
        agree = sum((pr >= raw_thr) == (pc >= cal_thr)
                    for pr, pc in zip(praw, pcal))
        blk = cal["test"]
        blk["decision_agreement_pcal_vs_praw"] = round(agree / len(y), 6)
        if agree != len(y):
            print(f"WARNING: calibrated/raw decision mismatch on "
                  f"{len(y) - agree} rows — p_cal transform or temperature "
                  f"disagrees with thresholds.json; inspect before trusting.")
        else:
            print(f"[test] decision agreement p_cal@{cal_thr:.6f} vs "
                  f"p_raw@{op['threshold']:.6f}: {agree}/{len(y)} (identical)")

    metrics["calibration"] = cal
    mpath.write_text(json.dumps(metrics, indent=1) + "\n",
                     encoding="utf-8")
    print(f"wrote calibration block -> {mpath}")

    manifest_path = mpath.parent / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if "metrics.json" in manifest.get("files", {}):
            manifest["files"]["metrics.json"] = {
                "sha256": sha256_file(mpath),
                "bytes": mpath.stat().st_size}
        note = (f"{time.strftime('%Y-%m-%d')}: {AMENDMENT_TAG} added the "
                f"calibration block (ECE/Brier on held-out test + gold "
                f"consensus, p_cal and p_raw) — fields added only; "
                f"sha256/bytes refreshed. All other files unchanged.")
        manifest["local_amendments"] = [
            a for a in manifest.get("local_amendments", [])
            if AMENDMENT_TAG not in a] + [note]
        manifest_path.write_text(json.dumps(manifest, indent=1) + "\n",
                                 encoding="utf-8")
        print(f"refreshed manifest metrics.json sha/bytes -> {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
