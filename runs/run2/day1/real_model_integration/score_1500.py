"""Score the shared 1,500-row eval sample with the fine-tuned artifacts ->
the baseline-row schema mcnemar.py consumes.

masked-v1   scores masked_text (what it trained on; what regex/tfidf/
            zeroshot baselines also saw)
unmasked-v1 scores text (the redaction ablation — it trained on unmasked)

Row schema: {"id", "sif_pred", "rules_pred", "sif_prob", "model", "quant"}
— superset of the zero-shot rows' {"id", "sif_pred", "rules_pred", ...};
mcnemar.load_preds reads only id/sif_pred/rules_pred.

Decisions: SIF at the frozen operating point from each config's canonical
thresholds.json (sigmoid(z) >= thr; temperature-mapped equivalent asserted
in onnx_score.self_check). Rules at per-rule frozen thresholds on raw
sigmoid (same form as train.py tune_f1_threshold).

Writes artifacts/baselines/finetune_{masked,unmasked}_test1500.jsonl and
score1500_meta.json next to this script (wall times feed the cost claim).
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from onnx_score import REPO, Scorer, sigmoid  # noqa: E402

HERE = Path(__file__).resolve().parent
SAMPLE = REPO / "artifacts/baselines/zeroshot_sample_ids.json"
CONFIGS = {
    "masked": {"dir": REPO / "artifacts/models/masked-v1", "field": "masked_text"},
    "unmasked": {"dir": REPO / "artifacts/models/unmasked-v1", "field": "text"},
}


def main():
    ids = json.loads(SAMPLE.read_text())["ids"]
    want = set(ids)
    rows = {}
    with (REPO / "artifacts/corpus/test.jsonl").open() as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in want:
                rows[r["id"]] = r
    assert len(rows) == len(ids), f"{len(rows)} != {len(ids)}"

    meta = {}
    for name, cfg in CONFIGS.items():
        sc = Scorer(cfg["dir"], quant="int8", threads=8)
        texts = [rows[i][cfg["field"]] for i in ids]
        t0 = time.time()
        z, zr = sc.logits(texts, batch=32)
        dt = time.time() - t0
        sif_pred = sc.decide(z)
        rules_pred = sc.decide_rules(zr)
        out = REPO / "artifacts" / "baselines" / f"finetune_{name}_test1500.jsonl"
        with out.open("w") as f:
            for i, rid in enumerate(ids):
                f.write(json.dumps({
                    "id": rid,
                    "sif_pred": bool(sif_pred[i]),
                    "rules_pred": rules_pred[i],
                    "sif_prob": round(float(sigmoid(z[i] / sc.temperature)), 4),
                    "model": f"{name}-v1", "quant": "int8",
                }) + "\n")
        meta[name] = {
            "file": str(out.relative_to(REPO)),
            "n": len(ids),
            "wall_seconds": round(dt, 1),
            "rows_per_s": round(len(ids) / dt, 1),
            "sif_threshold": sc.sif_threshold,
            "temperature": sc.temperature,
            "flag_rate": round(float(sif_pred.mean()), 4),
        }
        print(name, json.dumps(meta[name]))
    (HERE / "score1500_meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"wrote score1500_meta.json")


if __name__ == "__main__":
    main()
