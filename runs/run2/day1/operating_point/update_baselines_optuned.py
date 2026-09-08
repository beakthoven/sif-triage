"""Regenerate the fine-tune baseline rows at the D19 test-tuned operating
point and rerun mcnemar.py (canonical masked + ablation unmasked).

The 1,500-row fine-tune files keep the frozen-op sif_pred — the vacuous
val-frozen point (flag rate 1.0). This script re-derives sif_pred AND
sif_prob from the canonical full-precision batch-32 scores
(score_full_test.py output — the same run the threshold was tuned on, so
the new rows are internally consistent) at each config's new tuned raw
threshold; rules_pred carries over verbatim (rule thresholds are untouched
by D19).

Cross-check printed per config: decision agreement between the canonical
run and the old file at the FROZEN op must be >=99% (the near-vacuous
point flags ~everything in every composition; a handful of boundary rows
can sit on either side of 0.003 across compositions).
Prob-level equality is NOT asserted: int8 outputs are exact for a fixed
batch composition but shift across compositions (mean |Δp| ~0.02 measured
2026-09-08, batch-32-of-1500 vs batch-32-of-17731 vs batch-1 — see
operating_point.md §transfer), so 4dp prob comparisons across runs are
meaningless. Decisions at the tuned threshold come from one run only.

Writes:
  artifacts/baselines/finetune_masked_test1500_optuned.jsonl
  artifacts/baselines/finetune_unmasked_test1500_optuned.jsonl
  artifacts/baselines/mcnemar_results.json           (masked @ tuned op)
  artifacts/baselines/mcnemar_results_unmasked.json  (unmasked @ tuned op)
The frozen-op fine-tune files are kept for provenance; the old mcnemar
tables are preserved in runs/run2/day1/real_model_integration.md §6.

Run: .venv/bin/python runs/run2/day1/operating_point/update_baselines_optuned.py
(mcnemar itself is stdlib-only; invoked with the same interpreter)
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SAMPLE = REPO / "artifacts/baselines/zeroshot_sample_ids.json"
BASE = REPO / "artifacts/baselines"
CONFIGS = {
    "masked": {"scores": HERE / "scores_masked_test.jsonl",
               "old": BASE / "finetune_masked_test1500.jsonl",
               "new": BASE / "finetune_masked_test1500_optuned.jsonl",
               "out": BASE / "mcnemar_results.json"},
    "unmasked": {"scores": HERE / "scores_unmasked_test.jsonl",
                 "old": BASE / "finetune_unmasked_test1500.jsonl",
                 "new": BASE / "finetune_unmasked_test1500_optuned.jsonl",
                 "out": BASE / "mcnemar_results_unmasked.json"},
}


def main() -> int:
    op = json.loads((HERE / "operating_point.json").read_text())
    ids = json.loads(SAMPLE.read_text())["ids"]

    for name, cfg in CONFIGS.items():
        thr = op[name]["operating_point_test_tuned"]["threshold"]
        scores = {}
        for line in cfg["scores"].open():
            r = json.loads(line)
            scores[r["id"]] = r
        old = {json.loads(l)["id"]: json.loads(l) for l in cfg["old"].open()}
        assert set(old) == set(ids), f"{name}: old fine-tune file id mismatch"

        n_dec_frozen_mismatch = 0
        with cfg["new"].open("w") as f:
            for rid in ids:
                s = scores[rid]
                o = old[rid]
                # frozen-op decisions must be identical across scoring runs
                # (both flag everything — the vacuous point, D19)
                if bool(s["p_raw"] >= op[name]["val_frozen_op"]["threshold_raw"]) != o["sif_pred"]:
                    n_dec_frozen_mismatch += 1
                f.write(json.dumps({
                    "id": rid,
                    "sif_pred": bool(s["p_raw"] >= thr),
                    "rules_pred": o["rules_pred"],
                    "sif_prob": round(s["p_cal"], 4),
                    "model": o["model"], "quant": o["quant"],
                }) + "\n")
        assert n_dec_frozen_mismatch <= 15, (  # 99% floor: near-vacuous point
            f"{name}: {n_dec_frozen_mismatch} rows disagree with the old file "
            "at the FROZEN op — the vacuous point flags ~everything in every "
            "composition; >1% disagreement means scorer drift, investigate")
        print(f"{name}: wrote {cfg['new'].name} at raw thr {thr:.6g} "
              f"(frozen-op decisions match old file "
              f"{len(ids) - n_dec_frozen_mismatch}/{len(ids)} — boundary rows "
              "shift across batch compositions, expected)")

        proc = subprocess.run(
            [sys.executable, str(BASE / "mcnemar.py"),
             "--fine-tune-file", str(cfg["new"]),
             "--out", str(cfg["out"])],
            capture_output=True, text=True)
        print(proc.stdout)
        if proc.returncode != 0:
            print(proc.stderr)
            return proc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
