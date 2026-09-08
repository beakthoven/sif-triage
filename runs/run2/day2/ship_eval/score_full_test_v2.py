"""Score the FULL derived test split (17,731 rows) with masked-v2 int8,
SINGLE-TEXT per-row (batch=1 — the D27 canonical ship path), capturing both
sif and rule logits. Mirrors score_single_text_masked.py (v1) exactly,
extended with rule probs so the 1500-row McNemar row can carry rules_pred
from the same canonical run.

Writes runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl
{"id", "sif_label", "sif_logit", "p_raw", "p_cal", "rule_probs": {7}}.

Run: .venv/bin/python runs/run2/day2/ship_eval/score_full_test_v2.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "day1" / "real_model_integration"))
from onnx_score import REPO, RULES, Scorer, sigmoid  # noqa: E402

HERE = Path(__file__).resolve().parent
TEST = REPO / "artifacts/corpus/test.jsonl"


def main() -> None:
    rows = [json.loads(line) for line in TEST.open()]
    sc = Scorer(REPO / "artifacts/models/masked-v2", quant="int8", threads=8)
    t0 = time.time()
    out = HERE / "single_text_masked_v2_test.jsonl"
    with out.open("w") as f:
        for i, r in enumerate(rows):
            z, rl = sc.logits([r["masked_text"]], batch=1)
            rp = sigmoid(rl[0])
            f.write(json.dumps({
                "id": r["id"],
                "sif_label": int(r["sif_label"]),
                "sif_logit": float(z[0]),
                "p_raw": float(sigmoid(z[0])),
                "p_cal": float(sigmoid(z[0] / sc.temperature)),
                "rule_probs": {rule: float(p) for rule, p in zip(RULES, rp)},
            }) + "\n")
            if (i + 1) % 2000 == 0:
                print(f"{i + 1}/{len(rows)} ({(i + 1) / (time.time() - t0):.1f}/s)",
                      flush=True)
    dt = time.time() - t0
    print(f"wrote {out} — {len(rows)} rows in {dt:.0f}s ({len(rows) / dt:.1f}/s)")


if __name__ == "__main__":
    main()
