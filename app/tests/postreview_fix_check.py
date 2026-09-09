"""Post-review SEV1/SEV2 regression probe — runnable script, no pytest.

Proves each fix from runs/run2/day1/reviews/classifier_gates.md +
explain_embed.md against the REAL masked-v2 int8 artifact (no server, no
:8177 contact; the garbage-HTTP transport test binds 127.0.0.1:8196):

  1. SEV1-1 rule-head order: RULE_HEAD_ORDER == train.py RULES; welding text
     -> hot_work leads (not line_of_fire).
  2. SEV1-2 positional dead zone: stride 64 shrinks decisive-safe valleys
     (12 -> <=5, min score > 0.20; residual discount is inherent to CLS
     pooling — documented at RealOnnxClassifier.STRIDE). SEV2-6: a 200k-char
     paste is capped at 10k chars and scores in <5s, no 15.9s hang.
  3. SEV2-1 D27: int8 predict == per-window-solo max (delta 0.0; was 0.26).
  4. SEV2 spans: 13 demo cards + 20 corpus rows — every span a valid,
     meaningful phrase (>=3 chars, alphabetic, not stopword-only, no
     punctuation fragments); keyword-attribution fallback works (D2).
  5. SEV1 explain: ValueError / http.client.HTTPException / garbage-HTTP /
     timeout=-1 all fall back to template (return None), never raise.
  6. SEV2 explain score guard: "10.83"/"0.833" mutations rejected, a
     sentence-final "0.83." still accepted.
  7. SEV2-5: per-rule thresholds loaded from metrics.json into RULE_DISPLAY.
  8. SEV2-3 drill filter: the 3 FP classes clean; event drills still gray.

Run: .venv/bin/python app/tests/postreview_fix_check.py
"""
from __future__ import annotations

import http.client
import itertools
import json
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.classifier import (  # noqa: E402
    MAX_INPUT_CHARS,
    RULE_HEAD_ORDER,
    RealOnnxClassifier,
    _sigmoid,
)
from app.explain import _validate, ollama_reword  # noqa: E402
from app.gates import gate_drill, gate_long_input  # noqa: E402
from app.config import Settings  # noqa: E402
from app.schemas import RULE_DISPLAY  # noqa: E402

# Ship artifact (masked-v2 since the D21 retrain; masked-v1 = fallback).
MODEL_DIR = Path(os.environ.get(
    "SIF_MODEL_PATH", REPO_ROOT / "artifacts" / "models" / "masked-v2"))
if not MODEL_DIR.is_absolute():
    MODEL_DIR = REPO_ROOT / MODEL_DIR
TRAIN_PY = MODEL_DIR / "train.py"


def check(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"FAIL: {label}")
    print(f"  ok: {label}")


def train_py_rules() -> tuple[str, ...]:
    m = re.search(r"^RULES = \(([^)]*)\)", TRAIN_PY.read_text(), re.MULTILINE)
    assert m, "could not parse RULES from train.py"
    return tuple(re.findall(r'"([^"]+)"', m.group(1)))


def solo_window_max(clf: RealOnnxClassifier, text: str) -> float:
    enc = clf._tokenizer.encode(text[:MAX_INPUT_CHARS], add_special_tokens=False)
    probs = []
    for s, e in clf._windows(len(enc.ids)):
        ids, mask = clf._pad_rows([enc.ids[s:e]])
        sif_l, _, _ = clf._session.run(
            ["sif_logit", "rule_logits", "span_logits"],
            {"input_ids": ids, "attention_mask": mask})
        probs.append(float(_sigmoid(np.asarray(sif_l).reshape(-1).astype(np.float64)
                                    / clf.temperature)[0]))
    return max(probs)


def main() -> int:
    clf = RealOnnxClassifier(MODEL_DIR)
    print(f"model: {clf.model_version} quant={clf.quant} "
          f"supports_exact_batch={clf.supports_exact_batch} stride={clf.STRIDE}")

    print("[1] SEV1-1 rule-head order (zip == training order)")
    check(RULE_HEAD_ORDER == train_py_rules(),
          f"RULE_HEAD_ORDER == train.py RULES verbatim {train_py_rules()}")
    cases = {
        "hot_work": "Worker was grinding and welding near the diesel drum "
                    "storage, sparks flying everywhere, no fire watch posted.",
        "energy_isolation": "LOTO not applied before opening the pump; the motor "
                            "unexpectedly energized during maintenance, stored energy release.",
        "confined_space": "Worker entered the tank for vessel entry cleaning without a gas "
                          "test; two hours inside the vessel, no attendant at the manhole.",
        "working_at_height": "Worker on scaffold platform 9 meters up without a harness, "
                             "no fall arrest, ladder unsecured at the edge.",
        "line_of_fire": "Worker struck by a dropped pipe from the rack; hand caught between "
                        "the hammer union and the tong, pinch point crush.",
    }
    for expected, text in cases.items():
        top = max((p := clf.predict(text)).rule_probs, key=p.rule_probs.get)
        check(top == expected, f"{expected} text -> app top rule {top} p={p.rule_probs[top]:.3f}")
    print("      (pre-fix probe A: 6/6 scrambled, welding showed line_of_fire 0.9994)")

    print("[2] SEV1-2 positional scan + SEV2-6 input cap")
    check(clf.STRIDE == 64, "stride 96 -> 64")
    hazard = "Worker fell 6 meters from the scaffold without a harness and was taken to hospital."
    filler_ids = clf._tokenizer.encode(
        "Routine housekeeping walk completed around the yard checking hoses. " * 30,
        add_special_tokens=False).ids
    hz_ids = clf._tokenizer.encode(hazard, add_special_tokens=False).ids
    pad_after = filler_ids[:126]
    scores = []
    for n in range(0, 121, 8):
        text = clf._tokenizer.decode(list(filler_ids[:n]) + hz_ids + pad_after)
        scores.append(clf.predict(text).sif_score)
    valleys = sum(1 for s in scores if s < 0.4)
    print(f"      scan scores: {['%.2f' % s for s in scores]}")
    check(min(scores) > 0.20, f"worst-case score {min(scores):.3f} > 0.20 (was 0.13 at stride 96)")
    check(valleys <= 5, f"decisive-safe valleys (<0.4): {valleys} <= 5 (was 12 at stride 96)")
    print("      residual: mid-window hazards still score 0.25-0.70 (inherent to CLS "
          "pooling; most land in the 0.40-0.60 gray band -> review queue, not silent green)")
    big = "routine housekeeping walk around the yard checking hoses and valves " * 4000
    t0 = time.perf_counter()
    bp = clf.predict(big)
    dt = time.perf_counter() - t0
    check(dt < 5.0, f"200k-char paste capped: {dt:.2f}s < 5s (was 15.9s, 501 windows)")
    g = gate_long_input(big, Settings())
    check(g.triggered and g.action == "badge" and "capped" in g.detail,
          f"too-long badge (never gray): {g.detail[:80]}")
    _ = bp

    print("[3] SEV2-1 D27 int8 per-window sequential")
    check(not clf.supports_exact_batch, "int8 -> supports_exact_batch False")
    benign = "everything normal during the shift, housekeeping good, no issues observed. " * 10
    hot = "Worker fell 6 meters from scaffold without harness, taken to hospital. "
    for name, t in {"benign+hot": benign + hot, "hot+benign": hot + benign,
                    "hot@100": (" ".join(["ok"] * 100)) + " " + hot + (" ".join(["fine"] * 60))}.items():
        delta = abs(clf.predict(t).sif_score - solo_window_max(clf, t))
        check(delta < 1e-4,  # 4-decimal score rounding in PredictionOut
              f"{name}: predict == solo-window max (delta={delta:.2e}, was 0.26)")

    print("[4] SEV2 span quality: 13 demo cards + 20 corpus rows")
    texts = [json.loads(line)["text"] for line in
             (REPO_ROOT / "artifacts" / "demo" / "demo_corpus.jsonl").read_text().splitlines()]
    rows = []
    for line in itertools.islice(open(REPO_ROOT / "artifacts" / "corpus" / "test.jsonl"), 400):
        d = json.loads(line)
        rows.append(d.get("text") or d.get("masked_text") or "")
    texts += [r for r in rows if r][:20]
    n_empty = 0
    for t in texts:
        p = clf.predict(t)
        for s in p.evidence_spans:
            check(t[s.start:s.end] == s.text, f"span slice valid: {s.text!r}")
            check(len(s.text) >= 3 and re.search(r"[A-Za-z]", s.text),
                  f"span is a usable phrase, not a fragment: {s.text!r}")
            words = re.findall(r"[A-Za-z]+", s.text.lower())
            check(not all(w in ("the", "a", "an", "and", "of", "to", "in", "on") for w in words),
                  f"span not stopword-only: {s.text!r}")
        n_empty += not p.evidence_spans
        print(f"      score={p.sif_score:.3f} spans={[s.text for s in p.evidence_spans]}")
    print(f"      ({n_empty}/{len(texts)} texts with no span: honest empty — span head is "
          "sub-threshold in BOTH quants (max prob ~0.3, on punctuation), so the D2 "
          "keyword fallback is the live path; no spec keyword -> no highlight, never garbage)")
    weld = clf.predict(cases["hot_work"])
    check(any("weld" in s.text.lower() or "grind" in s.text.lower() for s in weld.evidence_spans),
          f"keyword fallback highlights mechanism phrase: {[s.text for s in weld.evidence_spans]}")

    print("[5] SEV1 explain: ollama_reword never raises")
    tmpl = "Triage score 0.83 — flagged for HSE review."
    for exc in (ValueError("Timeout value out of range"),
                http.client.BadStatusLine("\\x00\\x01garbage-not-http")):
        def boom(_p, exc=exc):
            raise exc
        check(ollama_reword("t", tmpl, "0.83", transport=boom) is None,
              f"transport {type(exc).__name__} -> None (template fallback)")
    check(ollama_reword("t", tmpl, "0.83", url="http://127.0.0.1:9", timeout=-1) is None,
          "timeout=-1 (SIF_EXPLAIN_TIMEOUT typo) -> None, was HTTP 500")
    srv = socket.socket()
    srv.bind(("127.0.0.1", 8196))
    srv.listen(1)
    srv.settimeout(5)
    def garbage():
        try:
            conn, _ = srv.accept()
            conn.sendall(b"\x00\x01garbage-not-http")
            conn.close()
        except OSError:
            pass
    threading.Thread(target=garbage, daemon=True).start()
    check(ollama_reword("t", tmpl, "0.83", url="http://127.0.0.1:8196", timeout=3) is None,
          "non-HTTP port squatter (BadStatusLine) -> None, was HTTP 500")
    srv.close()

    print("[6] SEV2 explain score guard (digit boundary)")
    def payload(expl: str) -> str:
        return json.dumps({"explanation": expl, "spans_quoted": []})
    check(_validate(payload("The triage score is 0.83, flagged."), "t", "0.83") is not None,
          "clean 0.83 accepted")
    check(_validate(payload("The triage score is 0.83."), "t", "0.83") is not None,
          "sentence-final '0.83.' accepted (period is not a digit)")
    for bad in ("The triage score is 10.83, flagged.", "The triage score is 0.833, flagged."):
        try:
            _validate(payload(bad), "t", "0.83")
            raise AssertionError(f"FAIL: mutated score accepted: {bad!r}")
        except ValueError:
            print(f"  ok: mutated score rejected: {bad!r}")

    print("[7] SEV2-5 per-rule thresholds from metrics.json")
    metrics = json.loads((MODEL_DIR / "metrics.json").read_text())
    for rule, thr in metrics["rules"].items():
        check(clf.rule_thresholds.get(rule) == thr["threshold"],
              f"{rule}: loaded {thr['threshold']}")
        check(RULE_DISPLAY[rule]["threshold"] == thr["threshold"],
              f"RULE_DISPLAY[{rule}] served at {thr['threshold']} (was hardcoded 0.5)")

    print("[8] SEV2-3 drill filter")
    clean = ["The drill was completed at 14:00 hrs, rig move next.",
             "Crew reminded to exercise caution near the rotary table.",
             "Planned test of the BOP this weekend per schedule.",
             "Drill pipe pressure test at 5000 psi, all holding steady.",
             "Drilling completed on well XYZ ahead of schedule.",
             "Rig floor hands performed drill line slip and cut."]
    gray = ["Mock drill conducted at GGS for fire response.",
            "Fire drill completed",
            "Evacuation mock drill at Baghjan camp area conducted on foggy morning.",
            "Simulated gas alarm during calibration check."]
    for t in clean:
        check(not gate_drill(t).triggered, f"clean: {t[:60]!r}")
    for t in gray:
        check(gate_drill(t).triggered, f"gray:  {t[:60]!r}")

    print("\nPOST-REVIEW FIX CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
