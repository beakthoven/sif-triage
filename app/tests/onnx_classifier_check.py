"""Runnable self-check for RealOnnxClassifier against the shipped trained
artifact (artifacts/models/masked-v1 — int8 default, fp32 fallback; D19/D20).
This checks the CONTRACT, not model quality. Exits 0 on pass.

Run: .venv/bin/python app/tests/onnx_classifier_check.py
     SIF_MODEL_QUANT=fp32 .venv/bin/python app/tests/onnx_classifier_check.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.classifier import (  # noqa: E402
    RULE_HEAD_ORDER,
    MockClassifier,
    RealOnnxClassifier,
    build_classifier,
)
from app.schemas import RULE_KEYS, PredictionOut  # noqa: E402

MODEL_DIR = REPO_ROOT / "artifacts" / "models" / "masked-v1"  # the ship artifact

SAMPLE = (
    "During well intervention at Baghjan field, a worker was grinding without "
    "a face shield near a live H2S flowline; LOTO was not applied on the pump "
    "and sparks were observed near the flange. Kick was later reported on the pit."
)


def check(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"FAIL: {label}")
    print(f"  ok: {label}")


def assert_valid(pred: PredictionOut, text: str) -> None:
    check(set(pred.rule_probs) == set(RULE_KEYS), "7 rule probs, exact keys")
    check(all(0.0 <= v <= 1.0 for v in pred.rule_probs.values()), "rule probs in [0,1]")
    check(0.0 <= pred.sif_score <= 1.0, "sif score in [0,1]")
    check(all(text[s.start:s.end] == s.text for s in pred.evidence_spans),
          "every span satisfies text[start:end]==span.text")
    check(len(pred.evidence_spans) <= 3, "top-3 spans cap")


def main() -> int:
    print("[1] factory resolution")
    clf = build_classifier(REPO_ROOT / "artifacts" / "models" / "no-such-dir", "mock-0.1.0")
    check(isinstance(clf, MockClassifier), "missing model dir -> MockClassifier fallback")
    clf = build_classifier(REPO_ROOT / "artifacts" / "models" / "masked-v1", "mock-0.1.0")
    check(isinstance(clf, RealOnnxClassifier), "masked-v1 ship artifact -> RealOnnxClassifier")

    print(f"[2] real load ({MODEL_DIR.relative_to(REPO_ROOT)})")
    clf = build_classifier(MODEL_DIR, "mock-0.1.0")
    check(isinstance(clf, RealOnnxClassifier), "masked-v1 dir -> RealOnnxClassifier")
    print(f"      quant={clf.quant} version={clf.model_version} T={clf.temperature}")

    print("[3] contract on sample report")
    pred = clf.predict(SAMPLE)
    assert_valid(pred, SAMPLE)
    check(pred.well_control is True, "well-control tag on kick language")
    check(pred.chunked is False, "short input not chunked")
    check(len(pred.evidence_spans) > 0, "spans non-empty (threshold or fallback)")
    check(pred.model_dump_json() == clf.predict(SAMPLE).model_dump_json(), "deterministic")

    print("[3b] classify_batch contract (D25)")
    batch_texts = [SAMPLE, "LOTO not applied", "x"]
    batch = clf.classify_batch(batch_texts, batch_size=2)
    check(len(batch) == 3, "one PredictionOut per input")
    for bp, bt in zip(batch, batch_texts):
        assert_valid(bp, bt)
    if clf.supports_exact_batch:
        check(batch[0].model_dump_json() == pred.model_dump_json(),
              "batch-exact quant: batch == single-row predict")
    else:
        # int8 per-tensor dynamic quantization shifts logits by batchmate
        # (measured Δ≈1-2, D25) — contract checked, score equality not asserted.
        print("      note: int8 quant — batch scores drift by batchmate (D25); equality not asserted")

    print("[3c] rule-head order == training order (post-review SEV1-1)")
    m = re.search(r"^RULES = \(([^)]*)\)", (MODEL_DIR / "train.py").read_text(), re.MULTILINE)
    train_rules = tuple(re.findall(r'"([^"]+)"', m.group(1)))
    check(RULE_HEAD_ORDER == train_rules,
          f"RULE_HEAD_ORDER == train.py RULES verbatim {train_rules}")
    weld = clf.predict("Worker was grinding and welding near the diesel drum "
                       "storage, sparks flying everywhere, no fire watch posted.")
    top = max(weld.rule_probs, key=weld.rule_probs.get)
    check(top == "hot_work",
          f"welding text -> hot_work leads (got {top}; pre-fix showed line_of_fire)")

    print("[4] chunked path — 1,500-word input (crash safety)")
    words = ("worker was grinding near the flange without face shield during lifting "
             "operations at height on scaffold near confined space entry").split()
    long_text = " ".join(words[i % len(words)] for i in range(1500))
    t0 = time.perf_counter()
    lp = clf.predict(long_text)
    dt = time.perf_counter() - t0
    check(lp.chunked is True, "chunked flag set on long input")
    assert_valid(lp, long_text)
    print(f"      1500-word end-to-end: {dt:.2f}s")

    print("[5] temperature hook")
    tmp = Path(tempfile.mkdtemp(prefix="sif-temp-"))
    try:
        shutil.copy2(MODEL_DIR / "sif_multitask_int8.onnx", tmp / "sif_multitask_int8.onnx")
        (tmp / "metrics.json").write_text(json.dumps({"temperature": 2.5}))
        hot = RealOnnxClassifier(tmp)
        check(hot.temperature == 2.5, "T read from metrics.json")
        hp = hot.predict(SAMPLE)
        check(abs(hp.sif_score - 0.5) <= abs(pred.sif_score - 0.5) + 1e-9,
              "T>1 pulls score toward 0.5")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("[6] edge inputs")
    for t in ["LOTO not applied", "कर्मचारी बिना हार्नेस के ऊंचाई पर काम कर रहा था", "x", "  "]:
        assert_valid(clf.predict(t), t)
    check(clf.dropped_spans == 0, f"no invalid spans dropped (dropped={clf.dropped_spans})")

    print("\nONNX CLASSIFIER CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
