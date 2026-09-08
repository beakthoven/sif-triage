"""1500-sample row for masked-v2 + 6-model Holm-corrected McNemar table.

Models (all on the shared 1,500-row zero-shot eval sample,
artifacts/baselines/zeroshot_sample_ids.json; labels = derived sif_label in
artifacts/corpus/test.jsonl):
  1. regex      — artifacts/baselines/regex_test1500.jsonl
  2. tfidf      — artifacts/baselines/tfidf_test1500.jsonl
  3. zeroshot   — artifacts/baselines/zeroshot_qwen3_8b_test1500.jsonl
  4. ft-v1-b32  — artifacts/baselines/finetune_masked_test1500_optuned.jsonl
                  (the published day-1 row: batch-32 scores @ batch32-tuned
                  raw 0.52667; provenance caveat in output)
  5. ft-v1-st   — NEW: v1 re-derived from the canonical single-text full-test
                  scores (runs/run2/day1/operating_point/
                  single_text_masked_test.jsonl) @ the D27 single-text-tuned
                  raw 0.821855; rules_pred carried from the published row
                  (rule thresholds untouched by D19/D27).
  6. ft-v2-st   — NEW: masked-v2 from THIS run's single-text full-test scores
                  (single_text_masked_v2_test.jsonl) @ v2's single-text-tuned
                  op (metrics.json operating_point_test_tuned); rules_pred
                  from the same canonical run's rule probs at v2's per-rule
                  thresholds.

Statistics via artifacts/baselines/mcnemar.py's verified functions (its
self-check runs first). Writes mcnemar_6model.json +
artifacts/baselines/finetune_masked_v2_test1500_optuned.jsonl +
artifacts/baselines/finetune_masked_test1500_optuned_singletext.jsonl.

Run: .venv/bin/python runs/run2/day2/ship_eval/mcnemar_v2.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "artifacts" / "baselines"))

import mcnemar  # noqa: E402

BASE = REPO / "artifacts/baselines"
V1_ST_SCORES = REPO / "runs/run2/day1/operating_point/single_text_masked_test.jsonl"
V2_ST_SCORES = HERE / "single_text_masked_v2_test.jsonl"


def build_v1_st_row(ids):
    op = json.loads((REPO / "artifacts/models/masked-v1/metrics.json").read_text())[
        "operating_point_test_tuned"]
    thr = float(op["threshold"])
    assert abs(thr - 0.821855) < 1e-9, thr
    scores = {json.loads(l)["id"]: json.loads(l) for l in V1_ST_SCORES.open()}
    old = {json.loads(l)["id"]: json.loads(l)
           for l in (BASE / "finetune_masked_test1500_optuned.jsonl").open()}
    assert set(old) == set(ids)
    out = BASE / "finetune_masked_test1500_optuned_singletext.jsonl"
    with out.open("w") as f:
        for rid in ids:
            s, o = scores[rid], old[rid]
            f.write(json.dumps({
                "id": rid,
                "sif_pred": bool(s["p_raw"] >= thr),
                "rules_pred": o["rules_pred"],
                "sif_prob": round(s["p_cal"], 4),
                "model": "masked-v1", "quant": "int8",
                "path": "single-text @ D27 op 0.821855",
            }) + "\n")
    return out, thr


def build_v2_row(ids):
    mdir = REPO / "artifacts/models/masked-v2"
    op = json.loads((mdir / "metrics.json").read_text())["operating_point_test_tuned"]
    thr = float(op["threshold"])
    rthr = json.loads((mdir / "thresholds.json").read_text())["rule_thresholds"]
    scores = {json.loads(l)["id"]: json.loads(l) for l in V2_ST_SCORES.open()}
    out = BASE / "finetune_masked_v2_test1500_optuned.jsonl"
    with out.open("w") as f:
        for rid in ids:
            s = scores[rid]
            fired = [r for r, p in s["rule_probs"].items() if p >= rthr[r]]
            f.write(json.dumps({
                "id": rid,
                "sif_pred": bool(s["p_raw"] >= thr),
                "rules_pred": sorted(fired),
                "sif_prob": round(s["p_cal"], 4),
                "model": "masked-v2", "quant": "int8",
                "path": f"single-text @ v2 op {thr:.6g}",
            }) + "\n")
    return out, thr


def main() -> int:
    mcnemar.self_check()
    ids = json.loads((BASE / "zeroshot_sample_ids.json").read_text())["ids"]
    labels = mcnemar.load_labels()

    v1_st_path, v1_thr = build_v1_st_row(ids)
    v2_path, v2_thr = build_v2_row(ids)
    print(f"ft-v1-st row @ raw {v1_thr} -> {v1_st_path.name}")
    print(f"ft-v2-st row @ raw {v2_thr:.6g} -> {v2_path.name}")

    files = {
        "regex": BASE / "regex_test1500.jsonl",
        "tfidf": BASE / "tfidf_test1500.jsonl",
        "zeroshot": BASE / "zeroshot_qwen3_8b_test1500.jsonl",
        "ft-v1-b32": BASE / "finetune_masked_test1500_optuned.jsonl",
        "ft-v1-st": v1_st_path,
        "ft-v2-st": v2_path,
    }
    models = {}
    for name, path in files.items():
        models[name] = mcnemar.model_metrics(name, mcnemar.load_preds(path), labels)
    pairs = mcnemar.pairwise(models)
    mcnemar.print_report(models, pairs)

    out = {
        "sample": "artifacts/baselines/zeroshot_sample_ids.json (n=1500)",
        "labels": "derived sif_label/rules from artifacts/corpus/test.jsonl",
        "provenance": {
            "ft-v1-b32": "published day-1 row: batch-32 scores @ batch32-tuned "
                         "raw 0.52667 (update_baselines_optuned.py; pre-D27)",
            "ft-v1-st": "single-text full-test scores @ D27 raw 0.821855 "
                        "(single_text_masked_test.jsonl); rules_pred from the "
                        "published row (rule thresholds untouched)",
            "ft-v2-st": "masked-v2 single-text full-test scores "
                        "(runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl) "
                        f"@ v2 single-text-tuned raw {v2_thr:.6g}; rules_pred "
                        "from the same run at v2 per-rule thresholds",
        },
        "models": {n: {k: v for k, v in m.items() if not k.startswith("_")}
                   for n, m in models.items()},
        "pairs": pairs,
    }
    (HERE / "mcnemar_6model.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"\nwrote {HERE / 'mcnemar_6model.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
