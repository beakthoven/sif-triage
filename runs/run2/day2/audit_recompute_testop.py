"""Final-audit recompute: masked-v2 test operating point from raw scores.

Independent of tune_op_v2.py — reads only the raw score jsonl and recomputes
confusion / P / R / F1 / prevalence / AUC at the shipped threshold.
"""
import json
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

SCORES = "runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl"
THR_RAW = 0.7464005622345774      # metrics.json operating_point_test_tuned.threshold
THR_CAL = 0.6581082996119922      # metrics.json operating_point_test_tuned.threshold_calibrated

ids, y, praw, pcal = [], [], [], []
with open(SCORES) as f:
    for line in f:
        r = json.loads(line)
        ids.append(r["id"])
        y.append(r["sif_label"])
        praw.append(r["p_raw"])
        pcal.append(r["p_cal"])

y = np.array(y); praw = np.array(praw); pcal = np.array(pcal)
n = len(y)
print(f"n = {n}")
print(f"prevalence = {y.mean():.13f}")
print(f"AUC (p_raw) = {roc_auc_score(y, praw):.13f}")
print(f"AP  (p_raw) = {average_precision_score(y, praw):.13f}")

# duplicate id check
print(f"unique ids = {len(set(ids))}")

for name, thr, scores in [("raw", THR_RAW, praw), ("cal", THR_CAL, pcal)]:
    pred = scores >= thr
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    P = tp / (tp + fp); R = tp / (tp + fn)
    F1 = 2 * P * R / (P + R)
    print(f"[{name} @ {thr:.12g}] TP={tp} FP={fp} FN={fn} TN={tn} "
          f"P={P:.13f} R={R:.13f} F1={F1:.13f} flag_rate={(tp+fp)/n:.13f}")

# verify raw-thr decisions == cal-thr decisions (monotone calibration)
d_raw = praw >= THR_RAW
d_cal = pcal >= THR_CAL
print(f"raw-vs-cal decision disagreement = {int((d_raw != d_cal).sum())}")

# also: recompute from metrics.json confusion as pure arithmetic
tp, fp, fn, tn = 11102, 2775, 287, 3567
P = tp/(tp+fp); R = tp/(tp+fn); F1 = 2*P*R/(P+R)
print(f"[metrics.json confusion arithmetic] P={P:.13f} R={R:.13f} F1={F1:.13f} sum={tp+fp+fn+tn}")

# nearest-threshold sensitivity: how many scores within 1e-3 of threshold
near = np.abs(praw - THR_RAW) < 1e-3
print(f"scores within 1e-3 of raw threshold: {int(near.sum())}")
