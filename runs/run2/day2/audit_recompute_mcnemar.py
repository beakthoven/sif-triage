"""Final-audit independent recompute: baselines table + McNemar (6 models, Holm).

Does NOT reuse mcnemar_v2.py/mcnemar.py logic. Labels re-joined from
artifacts/corpus/test.jsonl; ft-v2-st predictions re-derived from the raw
full-test single-text scores (p_raw >= 0.7464005622345774), not trusted from
the optuned file's booleans (those are cross-checked separately).
"""
import json
from math import comb

from scipy.stats import chi2

# --- labels ---
labels = {}
with open("artifacts/corpus/test.jsonl") as f:
    for line in f:
        r = json.loads(line)
        labels[r["id"]] = int(r["sif_label"])

sample_ids = json.load(open("artifacts/baselines/zeroshot_sample_ids.json"))["ids"]
assert len(sample_ids) == 1500 and len(set(sample_ids)) == 1500
assert all(i in labels for i in sample_ids)
y = {i: labels[i] for i in sample_ids}
prev = sum(y.values()) / len(y)
print(f"sample n=1500 prevalence={prev:.4f}")

# --- predictions ---
def load_bool(path):
    d = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            d[r["id"]] = bool(r["sif_pred"])
    return d

preds = {
    "regex": load_bool("artifacts/baselines/regex_test1500.jsonl"),
    "tfidf": load_bool("artifacts/baselines/tfidf_test1500.jsonl"),
    "zeroshot": load_bool("artifacts/baselines/zeroshot_qwen3_8b_test1500.jsonl"),
    "ft-v1-b32": load_bool("artifacts/baselines/finetune_masked_test1500_optuned.jsonl"),
    "ft-v1-st": load_bool("artifacts/baselines/finetune_masked_test1500_optuned_singletext.jsonl"),
}
for name, d in preds.items():
    assert set(d.keys()) == set(sample_ids), f"{name} id mismatch: {len(d)}"

# ft-v2-st: derive independently from full-test raw scores
THR = 0.7464005622345774
ft_v2 = {}
with open("runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl") as f:
    for line in f:
        r = json.loads(line)
        if r["id"] in y:
            ft_v2[r["id"]] = r["p_raw"] >= THR
assert len(ft_v2) == 1500
preds["ft-v2-st"] = ft_v2

# cross-check published optuned file booleans vs derived
pub = load_bool("artifacts/baselines/finetune_masked_v2_test1500_optuned.jsonl")
mism = sum(1 for i in sample_ids if pub[i] != ft_v2[i])
print(f"ft-v2 published-boolean vs derived-from-raw-scores mismatches: {mism}")
# also verify sif_prob in published file is consistent with threshold
prob_mism = 0
with open("artifacts/baselines/finetune_masked_v2_test1500_optuned.jsonl") as f:
    for line in f:
        r = json.loads(line)
        if (r["sif_prob"] >= THR) != bool(r["sif_pred"]):
            prob_mism += 1
print(f"ft-v2 published sif_prob-vs-boolean mismatches: {prob_mism}")

# --- confusion / P / R / F1 ---
print("\n== confusion & metrics (recomputed) ==")
stats = {}
for name in ["regex", "tfidf", "zeroshot", "ft-v1-b32", "ft-v1-st", "ft-v2-st"]:
    p = preds[name]
    tp = sum(1 for i in sample_ids if p[i] and y[i] == 1)
    fp = sum(1 for i in sample_ids if p[i] and y[i] == 0)
    fn = sum(1 for i in sample_ids if not p[i] and y[i] == 1)
    tn = sum(1 for i in sample_ids if not p[i] and y[i] == 0)
    P = tp / (tp + fp); R = tp / (tp + fn); F1 = 2 * P * R / (P + R)
    acc = (tp + tn) / 1500
    stats[name] = (tp, fp, fn, tn, P, R, F1, acc)
    print(f"{name:10s} TP={tp:4d} FP={fp:4d} FN={fn:4d} TN={tn:4d} "
          f"P={P:.4f} R={R:.4f} F1={F1:.4f} acc={acc:.4f}")

# --- McNemar, all pairs, chi2 with continuity correction + exact binomial ---
def mcnemar(a, b):
    bb = sum(1 for i in sample_ids if (preds[a][i] == (y[i] == 1)) and (preds[b][i] != (y[i] == 1)))
    cc = sum(1 for i in sample_ids if (preds[a][i] != (y[i] == 1)) and (preds[b][i] == (y[i] == 1)))
    x2 = (abs(bb - cc) - 1) ** 2 / (bb + cc) if bb + cc else 0.0
    p_cc = float(chi2.sf(x2, 1))
    n = bb + cc
    k = min(bb, cc)
    p_exact = min(1.0, 2 * sum(comb(n, j) for j in range(0, k + 1)) / 2 ** n)
    return bb, cc, p_cc, p_exact

names = ["regex", "tfidf", "zeroshot", "ft-v1-b32", "ft-v1-st", "ft-v2-st"]
pairs = []
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        bb, cc, p_cc, p_exact = mcnemar(names[i], names[j])
        pairs.append({"a": names[i], "b": names[j], "b_disc": bb, "c_disc": cc,
                      "p_raw": p_cc, "p_exact": p_exact})

# Holm step-down over all 15 pairs
m = len(pairs)
order = sorted(range(m), key=lambda k: pairs[k]["p_raw"])
holm = [None] * m
running = 0.0
for rank, k in enumerate(order):
    val = min(1.0, (m - rank) * pairs[k]["p_raw"])
    running = max(running, val)  # enforce monotonicity (step-down)
    holm[k] = running
for k in range(m):
    pairs[k]["p_holm"] = holm[k]

print("\n== McNemar pairs (recomputed) ==")
for p in pairs:
    print(f"{p['a']:9s} vs {p['b']:9s} b={p['b_disc']:4d} c={p['c_disc']:4d} "
          f"p_cc={p['p_raw']:.6g} p_exact={p['p_exact']:.6g} p_holm={p['p_holm']:.6g}")

# key claims
zp = [p for p in pairs if {p['a'], p['b']} == {"zeroshot", "ft-v2-st"}][0]
print(f"\nCLAIM ft-v2>zeroshot p_holm=0.0018 -> recomputed {zp['p_holm']:.6f} (raw {zp['p_raw']:.6g}, exact {zp['p_exact']:.6g})")
