"""Runnable self-checks for the real-model integration:

1. SPAN SUBSTRING VALIDITY: 20 real reports through the ship path
   (RealOnnxClassifier.predict, masked-v1 int8). Every evidence span must
   satisfy text[start:end] == span.text exactly (the ARCHITECTURE render
   invariant), and the classifier's internal drop counter must stay 0.
2. MODEL-DIR PREFERENCE: a model dir resolves to int8 by default, to fp32
   with SIF_MODEL_QUANT=fp32, and an explicit .onnx file path is honored.

Exits non-zero on any failure.
"""
import json
import os
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from app.classifier import RealOnnxClassifier  # noqa: E402


def check_dir_preference():
    d = REPO / "artifacts/models/masked-v1"
    c = RealOnnxClassifier(d)
    assert c.quant == "int8" and c.model_path.is_dir(), c.model_version
    os.environ["SIF_MODEL_QUANT"] = "fp32"
    try:
        c2 = RealOnnxClassifier(d)
        assert c2.quant == "fp32", c2.model_version
    finally:
        del os.environ["SIF_MODEL_QUANT"]
    c3 = RealOnnxClassifier(d / "sif_multitask_fp32.onnx")
    assert c3.quant == "fp32", c3.model_version
    print("self-check 2 OK: dir -> int8 default; SIF_MODEL_QUANT=fp32 and "
          "explicit .onnx path -> fp32")


def check_spans(n=20, seed=11):
    rows = [json.loads(l) for l in (REPO / "artifacts/corpus/test.jsonl").open()]
    sample = random.Random(seed).sample(rows, n)
    c = RealOnnxClassifier(REPO / "artifacts/models/masked-v1")
    total, with_spans, probs = 0, 0, []
    for r in sample:
        text = r["masked_text"]
        pred = c.predict(text)
        probs.append(pred.sif_score)
        with_spans += bool(pred.evidence_spans)
        for s in pred.evidence_spans:
            total += 1
            assert 0 <= s.start < s.end <= len(text), (s, len(text))
            assert text[s.start:s.end] == s.text, (s, text[s.start:s.end])
    assert c.dropped_spans == 0, f"{c.dropped_spans} invalid spans dropped"
    print(f"self-check 1 OK: {n} reports -> {total} spans, all exact "
          f"substrings; {with_spans}/{n} reports highlighted; "
          f"dropped=0; sif_score range [{min(probs):.4f}, {max(probs):.4f}]")


if __name__ == "__main__":
    check_spans()
    check_dir_preference()
    print("ALL SELF-CHECKS PASS")
