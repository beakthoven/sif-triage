#!/usr/bin/env python3
"""Follow-up probes: hazard position scan, multi-window int8 batch-vs-solo,
live-server end-to-end rule-label check."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from app.classifier import RealOnnxClassifier  # noqa: E402

clf = RealOnnxClassifier(Path("artifacts/models/masked-v1"))

print("## P1. hazard position scan (same sentence, filler prefix of N tokens)")
hazard = "Worker fell 6 meters from the scaffold without a harness and was taken to hospital."
filler_sentence = "Routine housekeeping walk completed around the yard checking hoses. "
# build filler prefixes tokenized to exact lengths
tok = clf._tokenizer
filler = filler_sentence * 30
filler_ids = tok.encode(filler, add_special_tokens=False).ids
hz_ids = tok.encode(hazard, add_special_tokens=False).ids
pad_after = filler_ids[:126]


def ids_to_text_score(prefix_ids):
    ids = list(prefix_ids) + hz_ids + pad_after
    text = tok.decode(ids)
    p = clf.predict(text)
    return p.sif_score


thr = clf.sif_flag_threshold
print(f"flag threshold = {thr:.4f}")
flips = []
for n in range(0, 121, 4):
    s = ids_to_text_score(filler_ids[:n])
    bar = "#" * int(s * 40)
    flag = "FLAG" if s >= thr else "    "
    print(f"  pos={n:3d} tok  score={s:.4f} {flag} {bar}")
    flips.append((n, s, s >= thr))
states = [f for _, _, f in flips]
print(f"  flips along position: {sum(1 for a, b in zip(states, states[1:]) if a != b)}")

print("\n## P2. multi-window int8: windows batched (predict) vs solo, same text")
benign = ("everything normal during the shift, housekeeping good, no issues observed. " * 10)
hot = "Worker fell 6 meters from scaffold without harness, taken to hospital. "
texts = {
    "benign+hot (hot in w2)": benign + hot,
    "hot+benign (hot in w1)": hot + benign,
    "hot at tok~100": (" ".join(["ok"] * 100)) + " " + hot + (" ".join(["fine"] * 60)),
}
for name, t in texts.items():
    enc = tok.encode(t, add_special_tokens=False)
    windows = clf._windows(len(enc.ids))
    p = clf.predict(t)
    # solo per-window
    solo_probs = []
    for s0, e0 in windows:
        i1, m1 = clf._pad_rows([enc.ids[s0:e0]])
        l1, _, _ = clf._session.run(["sif_logit", "rule_logits", "span_logits"],
                                    {"input_ids": i1, "attention_mask": m1})
        solo_probs.append(float(1 / (1 + np.exp(-l1[0].astype(np.float64) / clf.temperature))))
    solo_max = max(solo_probs)
    print(f"  {name}: tokens={len(enc.ids)} windows={len(windows)}")
    print(f"    predict() score={p.sif_score}  solo-window max={solo_max:.4f}  "
          f"delta={abs(p.sif_score - solo_max):.4f}")
    print(f"    solo per-window probs={['%.3f' % x for x in solo_probs]}")

print("\n## P3. live server :8177 end-to-end (rule label scramble through the API)")
body = json.dumps({"text": "Worker was grinding and welding near the diesel drum "
                           "storage, sparks flying everywhere, no fire watch posted."}).encode()
req = urllib.request.Request("http://127.0.0.1:8177/api/classify", data=body,
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read())
    rp = out["rule_probs"]
    top = max(rp, key=rp.get)
    print(f"  model_version={out['model_version']}")
    print(f"  top rule shown by API: {top} p={rp[top]:.4f}  (text is unambiguously hot_work)")
    print(f"  full rule_probs={ {k: round(v, 3) for k, v in rp.items()} }")
except Exception as e:
    print(f"  live server probe skipped: {e}")
