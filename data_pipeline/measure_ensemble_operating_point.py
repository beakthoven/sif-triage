"""Retune the masked-v2 SIF operating point for the runtime N=4 ensemble.

Scores the derived-label temporal test split through RealOnnxClassifier's
exact int8, single-row inference path. Selection reuses the existing max-recall
subject to precision >= 0.80 procedure from tune_op_v2.py. It does not change
the model artifact; it writes a provenance report under artifacts/demo/.

Run: SIF_SELF_CONSISTENCY_N=4 .venv/bin/python data_pipeline/measure_ensemble_operating_point.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO = REPO_ROOT
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "runs/run2/day2/ship_eval"))

from app.classifier import RealOnnxClassifier  # noqa: E402
from runs.run2.day2.ship_eval import tune_op_v2  # noqa: E402

MODEL = REPO_ROOT / "artifacts/models/masked-v2/sif_multitask_int8.onnx"
METRICS = MODEL.parent / "metrics.json"
TEST_SCORES = REPO_ROOT / "runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl"
TEST_TEXTS = REPO_ROOT / "data/January2015toNovember2025.csv"
REPORT = REPO_ROOT / "artifacts/demo/ensemble_operating_point_v2.json"
BATCH_SIZE = 64


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_narratives() -> dict[str, str]:
    with TEST_TEXTS.open(newline="", encoding="utf-8") as fh:
        return {row["ID"]: row["Final Narrative"] or "" for row in csv.DictReader(fh)}


def main() -> int:
    n_variants = int(os.environ.get("SIF_SELF_CONSISTENCY_N", "4"))
    if n_variants != 4:
        raise ValueError(f"this retune must match the deployed N=4 path, got N={n_variants}")

    rows = [json.loads(line) for line in TEST_SCORES.open(encoding="utf-8")]
    texts_by_id = test_narratives()
    texts = []
    labels = []
    ids = []
    for row in rows:
        ident = str(row["id"])
        if not ident.startswith("osha-"):
            raise ValueError(f"unexpected test id: {ident}")
        raw_id = ident.removeprefix("osha-")
        if raw_id not in texts_by_id:
            raise ValueError(f"missing source narrative for {ident}")
        ids.append(ident)
        texts.append(texts_by_id[raw_id])
        labels.append(int(row["sif_label"]))
    if len(set(ids)) != len(ids) or len(texts_by_id) < len(rows):
        raise ValueError("test IDs are duplicated or source narrative mapping is incomplete")

    clf = RealOnnxClassifier(MODEL)
    if clf.n_variants != 4:
        raise AssertionError(f"classifier loaded N={clf.n_variants}, expected N=4")
    import numpy as np

    scores: list[float] = []
    t0 = time.perf_counter()
    for start in range(0, len(texts), BATCH_SIZE):
        batch = clf.classify_batch(texts[start : start + BATCH_SIZE])
        if any(pred.n_variants != 4 or len(pred.variant_scores) != 4 for pred in batch):
            raise AssertionError("a test row did not return four variant scores")
        scores.extend(pred.sif_score for pred in batch)
        done = start + len(batch)
        if done % 1000 < BATCH_SIZE:
            print(f"scored {done}/{len(texts)} ({done / (time.perf_counter() - t0):.1f} rows/s)",
                  flush=True)
    elapsed = time.perf_counter() - t0

    if len(scores) != len(rows):
        raise AssertionError(f"scored {len(scores)} rows for {len(rows)} test examples")

    y = np.asarray(labels, dtype=np.int64)
    p = np.asarray(scores, dtype=np.float64)
    curve = tune_op_v2.top.pr_curve(y, p)
    selected = tune_op_v2.top.select_at_floor(curve, 0.80, int(y.sum()), len(y))
    if selected.get("floor_unreachable"):
        raise AssertionError("precision floor 0.80 is unreachable for N=4 scores")
    threshold_calibrated = float(selected["threshold"])
    temperature = float(clf.temperature)
    threshold_raw = 1.0 / (1.0 + math.exp(-temperature * math.log(
        threshold_calibrated / (1.0 - threshold_calibrated))))
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    old = metrics["operating_point_test_tuned"]
    old_cal = float(old["threshold_calibrated"])
    old_at_ensemble = tune_op_v2.top.at_threshold(y, p, old_cal)
    report = {
        "method": "masked-v2 int8 RealOnnxClassifier; N=4 runtime surface variants; score rounded to 4 decimals as persisted",
        "selection": "max recall subject to precision >= 0.80",
        "selection_implementation": "runs/run2/day2/ship_eval/tune_op_v2.py (PR curve and select_at_floor)",
        "source": {
            "labels": str(TEST_SCORES.relative_to(REPO_ROOT)),
            "narratives": str(TEST_TEXTS.relative_to(REPO_ROOT)),
            "split": "derived-label temporal test split; gold-independent, not final gold evaluation",
            "n": len(y),
            "prevalence": float(y.mean()),
        },
        "provenance_sha256": {
            "scores_file": sha256_file(TEST_SCORES),
            "narrative_source": sha256_file(TEST_TEXTS),
            "model_file": sha256_file(MODEL),
        },
        "temperature": temperature,
        "old_single_text_operating_point": {
            "threshold_raw": float(old["threshold"]),
            "threshold_calibrated": old_cal,
            "selection": "max recall subject to precision >= 0.80 on single-text scores",
            "ensemble_scores_at_old_threshold": old_at_ensemble,
        },
        "n4_ensemble_operating_point": {
            "threshold_raw_for_metrics_json": threshold_raw,
            "threshold_calibrated": threshold_calibrated,
            "precision": float(selected["precision"]),
            "recall": float(selected["recall"]),
            "f1": float(selected["f1"]),
            "confusion": selected["confusion"],
            "flag_rate": float(selected["flag_rate"]),
            "precision_floor": 0.80,
        },
        "runtime": {"elapsed_seconds": round(elapsed, 1), "batch_size": BATCH_SIZE},
        "limitations": "Retune is on derived labels, not human-adjudicated gold; operating point is not a field-prevalence claim.",
        "provenance_note": "Content hashes identify the exact scores, source narratives, and model used for this run.",
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["n4_ensemble_operating_point"], indent=2))
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
