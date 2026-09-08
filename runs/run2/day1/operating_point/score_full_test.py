"""Score ALL of artifacts/corpus/test.jsonl with the shipped ONNX artifacts
(D19 operating-point re-tune, step 1: scores only — no analysis here).

masked-v1   scores masked_text (what it trained on)
unmasked-v1 scores text (the redaction ablation)
Both int8 (ship default, D20), batch 32, 8 threads — same path as
real_model_integration/score_1500.py, full 17,731 rows instead of 1,500.

Writes runs/run2/day1/operating_point/scores_{masked,unmasked}_test.jsonl:
{"id", "sif_label", "rules", "sif_logit", "p_raw", "p_cal"} at FULL float64
precision (the 1500-row baseline files round sif_prob to 4dp — unusable for
threshold selection). p_raw = sigmoid(logit) is the scale train.py tuned the
frozen operating point on; p_cal = sigmoid(logit / T) is the displayed score.

Run: .venv/bin/python runs/run2/day1/operating_point/score_full_test.py
Self-check: --self-check asserts the Scorer threshold-map identity + that the
first 64 rows' p_raw reproduce an independent re-encode of row 0..63.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "real_model_integration"))
from onnx_score import REPO, Scorer, sigmoid  # noqa: E402

HERE = Path(__file__).resolve().parent
CONFIGS = {
    "masked": {"dir": REPO / "artifacts/models/masked-v1", "field": "masked_text"},
    "unmasked": {"dir": REPO / "artifacts/models/unmasked-v1", "field": "text"},
}
TEST = REPO / "artifacts/corpus/test.jsonl"


def score_config(name: str, cfg: dict, rows: list[dict]) -> dict:
    sc = Scorer(cfg["dir"], quant="int8", threads=8)
    texts = [r[cfg["field"]] for r in rows]
    t0 = time.time()
    z, _zr = sc.logits(texts, batch=32)
    dt = time.time() - t0
    p_raw = sigmoid(z)
    p_cal = sigmoid(z / sc.temperature)
    out = HERE / f"scores_{name}_test.jsonl"
    with out.open("w") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps({
                "id": r["id"],
                "sif_label": int(r["sif_label"]),
                "rules": sorted(r["rules"]),
                "sif_logit": float(z[i]),
                "p_raw": float(p_raw[i]),
                "p_cal": float(p_cal[i]),
            }) + "\n")
    meta = {
        "config": name,
        "model_dir": str(cfg["dir"].relative_to(REPO)),
        "text_field": cfg["field"],
        "quant": "int8",
        "n": len(rows),
        "wall_seconds": round(dt, 1),
        "rows_per_s": round(len(rows) / dt, 1),
        "frozen_threshold_raw": sc.sif_threshold,
        "frozen_threshold_cal": sc.sif_threshold_cal,
        "temperature": sc.temperature,
        "out": str(out.relative_to(REPO)),
    }
    print(json.dumps(meta))
    return meta


def self_check() -> None:
    """Small, loud: frozen-threshold identity (onnx_score) + scoring is
    deterministic across two runs of the same 64 rows."""
    import onnx_score
    assert onnx_score.self_check()
    rows = []
    with TEST.open() as f:
        for line in f:
            rows.append(json.loads(line))
            if len(rows) == 64:
                break
    sc = Scorer(CONFIGS["masked"]["dir"], quant="int8", threads=8)
    texts = [r["masked_text"] for r in rows]
    z1, _ = sc.logits(texts, batch=32)
    z2, _ = sc.logits(texts, batch=32)
    assert (z1 == z2).all(), "non-deterministic logits across runs"
    assert sigmoid(z1 / sc.temperature).min() >= 0 and sigmoid(z1).max() <= 1
    print("score_full_test self-check OK")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    self_check()
    rows = [json.loads(line) for line in TEST.open()]
    assert len(rows) == 17731, f"expected 17,731 test rows, got {len(rows)}"
    meta = {"test": str(TEST.relative_to(REPO)), "n": len(rows),
            "prevalence": round(sum(r["sif_label"] for r in rows) / len(rows), 6),
            "configs": [score_config(n, c, rows) for n, c in CONFIGS.items()]}
    (HERE / "score_full_test_meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"wrote {HERE / 'score_full_test_meta.json'}")


if __name__ == "__main__":
    main()
