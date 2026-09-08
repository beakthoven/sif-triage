"""Unified 5-model comparison on the shared 1,500-row sample + ship-decision
inputs.

Reuses the verified statistics from artifacts/baselines/mcnemar.py
(model_metrics / pairwise / load_labels / load_preds — its self-check runs
on import of main() only, so we call self_check() explicitly here).

Outputs compare1500.json next to this script:
  - 5-model table (regex / tfidf / zeroshot / finetune_masked /
    finetune_unmasked): acc/P/R/F1 + Wilson CIs, Holm-corrected McNemar
    over all 10 pairs
  - AUC for the two fine-tune rows (they carry sif_prob; baselines don't)
  - ship-decision block: masked-vs-unmasked (AUC, recall@frozen-op, F1,
    McNemar) and the masked-vs-zeroshot F1 gap + measured cost ratio
"""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location(
    "mcnemar", REPO / "artifacts/baselines/mcnemar.py")
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)
mc.self_check()

from sklearn.metrics import roc_auc_score  # noqa: E402

FILES = {
    "regex": REPO / "artifacts/baselines/regex_test1500.jsonl",
    "tfidf": REPO / "artifacts/baselines/tfidf_test1500.jsonl",
    "zeroshot": REPO / "artifacts/baselines/zeroshot_qwen3_8b_test1500.jsonl",
    "ft_masked": REPO / "artifacts/baselines/finetune_masked_test1500.jsonl",
    "ft_unmasked": REPO / "artifacts/baselines/finetune_unmasked_test1500.jsonl",
}


def load_probs(path):
    out = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            out[r["id"]] = r.get("sif_prob")
    return out


def main():
    labels = mc.load_labels()
    models = {}
    for name, path in FILES.items():
        models[name] = mc.model_metrics(name, mc.load_preds(path), labels)
    pairs = mc.pairwise(models)
    mc.print_report(models, pairs)

    # AUC for fine-tune rows (calibrated sif_prob is a monotonic map of the
    # logit — AUC identical to raw-score AUC).
    aucs = {}
    ft_probs = {}
    for name in ("ft_masked", "ft_unmasked"):
        probs = load_probs(FILES[name])
        ft_probs[name] = probs
        ids = sorted(set(probs) & set(labels))
        y = [labels[i]["sif"] for i in ids]
        p = [probs[i] for i in ids]
        aucs[name] = round(float(roc_auc_score(y, p)), 6)
    print("AUC on 1500 sample:", aucs)

    # Threshold diagnostics: the frozen op (tuned on saturated 79.4%-positive
    # val) flags ~everything at natural test prevalence. Measure alternates
    # on the same scores. sif_prob is calibrated = sigmoid(z/T); the raw
    # sigmoid is sigmoid(z) = sigmoid(logit(p)*T) — recover z from p.
    def metrics_at(name, decide):
        tp = fp = fn = tn = 0
        for i, lab in labels.items():
            if i not in ft_probs[name]:
                continue
            d = decide(ft_probs[name][i])
            y = lab["sif"]
            tp += d and y; fp += d and not y
            fn += (not d) and y; tn += (not d) and not y
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": tp + fp + fn + tn,
                "precision": round(prec, 4), "recall": round(rec, 4),
                "f1": round(f1, 4),
                "flag_rate": round((tp + fp) / (tp + fp + fn + tn), 4)}

    temps = {"ft_masked": 1.683972954750061, "ft_unmasked": 1.6731598377227783}
    thrs = {"ft_masked": 6.581278398140432e-05, "ft_unmasked": 6.551666090070625e-05}

    def raw_sigmoid(p_cal, temp):  # invert calibrated prob back to raw sigmoid
        import math
        p_cal = min(max(p_cal, 1e-9), 1 - 1e-9)  # 4-dp file rounding guard
        z = temp * math.log(p_cal / (1 - p_cal))
        return 1 / (1 + math.exp(-z))

    diagnostics = {}
    for name in ("ft_masked", "ft_unmasked"):
        t, thr = temps[name], thrs[name]
        # a-priori untuned: raw sigmoid >= 0.5
        ap = metrics_at(name, lambda p: raw_sigmoid(p, t) >= 0.5)
        # post-hoc F1-optimal on this sample (diagnostic upper bound only)
        cand = sorted({raw_sigmoid(p, t) for p in ft_probs[name].values()})
        best = max(cand[::max(1, len(cand) // 400)], key=lambda c: metrics_at(name, lambda p: raw_sigmoid(p, t) >= c)["f1"])
        po = metrics_at(name, lambda p: raw_sigmoid(p, t) >= best)
        po["threshold_raw_sigmoid"] = float(best)
        diagnostics[name] = {"apriori_raw_sigmoid_0.5": ap, "posthoc_f1_optimal_DIAGNOSTIC_ONLY": po}
    print("threshold diagnostics:", json.dumps(diagnostics, indent=1))

    # Ship-decision block
    pair_m_u = next(p for p in pairs if {p["a"], p["b"]} == {"ft_masked", "ft_unmasked"})
    pair_m_z = next(p for p in pairs if {p["a"], p["b"]} == {"ft_masked", "zeroshot"})
    meta = json.loads((HERE / "score1500_meta.json").read_text())
    zs_wall_s = 2863.0  # zeroshot_run_meta.json: 08:05:29 -> 08:53:12
    ship = {
        "masked_vs_unmasked": {
            "auc": {"masked": aucs["ft_masked"], "unmasked": aucs["ft_unmasked"]},
            "recall_at_frozen_op": {
                "masked": models["ft_masked"]["recall"][0],
                "unmasked": models["ft_unmasked"]["recall"][0]},
            "precision_at_frozen_op": {
                "masked": models["ft_masked"]["precision"][0],
                "unmasked": models["ft_unmasked"]["precision"][0]},
            "f1": {"masked": models["ft_masked"]["f1"],
                   "unmasked": models["ft_unmasked"]["f1"]},
            "mcnemar": pair_m_u,
        },
        "masked_vs_zeroshot": {
            "f1_masked": models["ft_masked"]["f1"],
            "f1_zeroshot": models["zeroshot"]["f1"],
            "f1_gap": round(models["ft_masked"]["f1"] - models["zeroshot"]["f1"], 4),
            "mcnemar": pair_m_z,
        },
        "cost_1500_rows": {
            "zeroshot_qwen3_8b_wall_s": zs_wall_s,
            "finetune_masked_int8_wall_s": meta["masked"]["wall_seconds"],
            "wall_ratio": round(zs_wall_s / meta["masked"]["wall_seconds"], 1),
            "note": "zeroshot: qwen3:8b local Ollama, 6 parallel workers; "
                    "finetune: int8 ONNX CPU, batch 32, air-gapped",
        },
        "threshold_diagnostics": diagnostics,
    }
    out = {
        "sample": "artifacts/baselines/zeroshot_sample_ids.json (n=1500, seed 42)",
        "labels": "derived sif_label/rules, artifacts/corpus/test.jsonl",
        "aucs": aucs,
        "models": {k: {kk: vv for kk, vv in m.items() if not kk.startswith("_")}
                   for k, m in models.items()},
        "pairs": pairs,
        "ship_decision": ship,
        "note": "models/pairs use the FROZEN operating point for the finetune "
                "rows (the integration contract); threshold_diagnostics shows "
                "a-priori and post-hoc alternates measured on the same scores.",
    }
    (HERE / "compare1500.json").write_text(json.dumps(out, indent=1) + "\n")
    print("\nship decision:", json.dumps(ship, indent=1))
    print(f"wrote {HERE / 'compare1500.json'}")


if __name__ == "__main__":
    main()
