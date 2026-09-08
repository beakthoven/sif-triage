#!/usr/bin/env python3
"""Adversarial probes for app/classifier.py + app/gates.py (Day-1 evening review).

Every probe prints PROBE <name>: <evidence>. Run:
    .venv/bin/python runs/run2/day1/reviews/probes_classifier_gates.py

Uses the real masked-v1 int8 artifact directly (no server). Gates probed via
direct imports. Nothing here touches :8177 or the runtime DB.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.classifier import (  # noqa: E402
    Classifier,
    MockClassifier,
    RealOnnxClassifier,
    flag_threshold,
    validate_spans,
)
from app.config import Settings  # noqa: E402
from app.gates import (  # noqa: E402
    gate_drill,
    gate_language,
    gate_min_length,
    gate_negation,
)
from app.schemas import RULE_KEYS, EvidenceSpan  # noqa: E402

MODEL_DIR = Path("artifacts/models/masked-v1")
TRAIN_ORDER = (
    "line_of_fire", "working_at_height", "driving", "energy_isolation",
    "hot_work", "safe_mechanical_lifting", "confined_space",
)  # artifacts/models/masked-v1/train.py RULES, verbatim


def banner(t):
    print(f"\n{'=' * 74}\n## {t}\n{'=' * 74}")


# ---------------------------------------------------------------- A: rule order
def probe_rule_order(clf: RealOnnxClassifier):
    banner("A. rule_logits head order: training order vs app RULE_KEYS zip")
    print(f"TRAIN order (artifact train.py): {TRAIN_ORDER}")
    print(f"APP RULE_KEYS (schemas.py)     : {RULE_KEYS}")
    cases = {
        "hot_work": "Worker was grinding and welding near the diesel drum storage, "
                    "sparks flying everywhere, no fire watch posted.",
        "energy_isolation": "LOTO not applied before opening the pump; the motor "
                            "unexpectedly energized during maintenance, stored energy release.",
        "confined_space": "Worker entered the tank for vessel entry cleaning without a gas "
                          "test; two hours inside the vessel, no attendant at the manhole.",
        "working_at_height": "Worker on scaffold platform 9 meters up without a harness, "
                             "no fall arrest, ladder unsecured at the edge.",
        "driving": "Forklift reversed through the pedestrian walkway at speed; driver had "
                   "no seat belt, journey management plan not followed for the vehicle.",
        "line_of_fire": "Worker struck by a dropped pipe from the rack; hand caught between "
                        "the hammer union and the tong, pinch point crush.",
    }
    mismatches = 0
    for expected, text in cases.items():
        pred = clf.predict(text)
        # raw head outputs, indexed by TRAINING order
        enc = clf._tokenizer.encode(text, add_special_tokens=False)
        ids, mask = clf._pad_rows([enc.ids])
        _, rule_l, _ = clf._session.run(
            ["sif_logit", "rule_logits", "span_logits"],
            {"input_ids": ids, "attention_mask": mask})
        raw = 1 / (1 + np.exp(-rule_l[0].astype(np.float64)))
        train_top = TRAIN_ORDER[int(np.argmax(raw))]
        app_top = max(pred.rule_probs, key=pred.rule_probs.get)
        # what the app reports for the training-order top head:
        app_val_at_train_top = pred.rule_probs[train_top]
        raw_val_at_train_top = float(np.max(raw))
        consistent = abs(app_val_at_train_top - raw_val_at_train_top) < 5e-3
        print(f"\n  text expects rule={expected!r}")
        print(f"    raw head top (TRAIN order): {train_top} p={raw_val_at_train_top:.4f}")
        print(f"    app  top label            : {app_top} p={pred.rule_probs[app_top]:.4f}")
        print(f"    app value AT train-top key: {app_val_at_train_top:.4f} "
              f"(raw {raw_val_at_train_top:.4f}) -> {'CONSISTENT' if consistent else 'SCRAMBLED'}")
        if not consistent:
            mismatches += 1
    print(f"\n  RESULT: {mismatches}/6 cases where app label != raw head label "
          f"(safe_mechanical_lifting coincidentally shares index 5 in both orders)")


# ------------------------------------------------------- B: span offset mapping
def probe_offsets(clf: RealOnnxClassifier):
    banner("B. offset_mapping vs original text (emoji / NFD / CRLF / ZWJ)")
    tok = clf._tokenizer
    tricky = {
        "emoji-prefix": "👷🏽 Worker struck by dropped pipe at the rack.",
        "flag-emoji": "🇮🇳 crew reported a gas leak near the flare.",
        "zwj-emoji": "👨‍👩‍👧 visitor saw sparks during welding.",
        "NFD-e": "cafe\u0301 worker burned by steam line.",  # decomposed é
        "CRLF": "line one\r\nworker fell from ladder\r\nline three",
        "devanagari": "Worker राम Kumar slipped near the walkway.",
        "mixed": "A👷🏽B cafe\u0301 C\r\nD struck by load.",
    }
    for name, text in tricky.items():
        enc = tok.encode(text, add_special_tokens=False)
        bad = []
        prev_end = 0
        for tid, (o0, o1) in zip(enc.ids, enc.offsets):
            if o0 == o1:
                continue
            if not (0 <= o0 < o1 <= len(text)):
                bad.append((tid, o0, o1, "OUT OF BOUNDS"))
            if o0 < prev_end:
                bad.append((tid, o0, o1, "OVERLAP/non-monotonic"))
            prev_end = max(prev_end, o1)
        nfc = unicodedata.normalize("NFC", text)
        print(f"  {name}: len(text)={len(text)} len(NFC)={len(nfc)} tokens={len(enc.ids)} "
              f"max_off={max((o[1] for o in enc.offsets), default=0)} bad={bad[:3]}")
    # Real-model span probe: does the returned span still cover the anchor when
    # multi-byte chars precede it?
    print("\n  real-model spans after emoji prefix:")
    text = "👷🏽🇮🇳🚧 Worker struck by a dropped pipe, caught between rack and tong."
    pred = clf.predict(text)
    for s in pred.evidence_spans:
        print(f"    span=({s.start},{s.end}) text={s.text!r} "
              f"slice-ok={text[s.start:s.end] == s.text}")
    # validate_spans vacuity: real-classifier spans are BUILT as text[c0:c1],
    # so the invariant can never fail. Show the guard works only on alien spans.
    alien = [EvidenceSpan(start=0, end=5, text="ZZZZZ")]
    print(f"  validate_spans on foreign span {alien[0].text!r}: kept={len(validate_spans(text, alien))}")
    print("  but RealOnnxClassifier._extract_spans does "
          "EvidenceSpan(..., text=text[c0:c1]) -> invariant is vacuous by construction.")


# ------------------------------------------------------ C: threshold loading
def probe_threshold_loading():
    banner("C. metrics.json loading: missing / corrupt / both operating points")

    def load(dirpath: Path):
        t = RealOnnxClassifier._load_temperature(dirpath)
        thr = RealOnnxClassifier._load_flag_threshold(dirpath, t)
        return t, thr

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        print(f"  missing file          -> T={load(d)[0]}, thr={load(d)[1]}")
        (d / "metrics.json").write_text("{not json")
        print(f"  corrupt json          -> T={load(d)[0]}, thr={load(d)[1]}")
        (d / "metrics.json").write_text(json.dumps({
            "sif": {"operating_point": {"threshold": 6.58e-05}},  # vacuous val-frozen
            "temperature": 1.683972954750061,
            "operating_point_test_tuned": {"threshold": 0.821855},
        }))
        t, thr = load(d)
        print(f"  BOTH operating points -> T={t:.4f}, thr={thr:.6f} "
              f"(test_tuned wins; expect ~0.712581)")
        (d / "metrics.json").write_text(json.dumps({
            "sif": {"operating_point": {"threshold": 0.33}},
            "temperature": 1.683972954750061,
        }))
        t, thr = load(d)
        print(f"  only val-frozen point -> T={t:.4f}, thr={thr} (deliberately NOT used -> 0.5)")
        (d / "metrics.json").write_text(json.dumps({
            "operating_point_test_tuned": {"threshold": "0.821855"}, "temperature": 1.6839}))
        print(f"  threshold as string   -> thr={load(d)[1]:.6f}")
        (d / "metrics.json").write_text(json.dumps({
            "operating_point_test_tuned": {"threshold": 0.0}, "temperature": 1.6839}))
        print(f"  threshold=0.0 (falsy) -> thr={load(d)[1]}")
        (d / "metrics.json").write_text(json.dumps({
            "operating_point_test_tuned": {"threshold": 1.5}, "temperature": 1.6839}))
        print(f"  threshold=1.5 (>1)    -> thr={load(d)[1]}")
        (d / "metrics.json").write_text(json.dumps({
            "operating_point_test_tuned": {"threshold": 0.8}, "temperature": -2.0}))
        print(f"  negative temperature  -> T={load(d)[0]}, thr={load(d)[1]:.6f}")
    # math identity: flag iff sigmoid(raw_logit) >= raw_thr
    raw_thr, T = 0.821855, 1.683972954750061
    cal_thr = 1 / (1 + np.exp(-(np.log(raw_thr / (1 - raw_thr)) / T)))
    ok = True
    for L in np.linspace(-10, 10, 2001):
        a = (1 / (1 + np.exp(-L / T))) >= cal_thr
        b = (1 / (1 + np.exp(-L))) >= raw_thr
        if a != b:
            ok = False
            break
    print(f"  cal_thr={cal_thr:.6f} vs metrics.json threshold_calibrated=0.712581")
    print(f"  decision identity sigmoid(L/T)>=cal_thr <=> sigmoid(L)>=raw_thr over 2001 logits: {ok}")


# ---------------------------------------------------------------- D: chunking
def probe_chunking(clf: RealOnnxClassifier):
    banner("D. sliding windows: boundaries, max-pool, span window choice")
    for n in (0, 1, 126, 127, 128, 222, 223, 1000):
        w = clf._windows(n)
        print(f"  _windows({n}) -> {w if len(w) < 6 else str(w[:3])[:-1]}, ... x{len(w)}]")
    # keyword straddling the 126-token boundary: overlap is 30 tokens so any
    # <=30-token keyword is fully inside some window. Build filler + hazard.
    filler = ("routine housekeeping walk around the yard checking hoses and valves ")
    hazard = " worker struck by swinging crane load, taken for medical evaluation "
    base = filler * 20
    # token-align the hazard to start near token 124 (boundary at 126)
    enc = clf._tokenizer.encode(base, add_special_tokens=False)
    pre = clf._tokenizer.encode(base[: len(base) // 2], add_special_tokens=False)
    # find a char cut so hazard starts at token ~122
    cut = 0
    for c in range(0, len(base), 10):
        n = len(clf._tokenizer.encode(base[:c], add_special_tokens=False).ids)
        if n <= 122:
            cut = c
        else:
            break
    text_boundary = base[:cut] + hazard + filler * 10
    n_tok = len(clf._tokenizer.encode(text_boundary, add_special_tokens=False).ids)
    hz_char = text_boundary.index(hazard)
    hz_tok = sum(1 for o in clf._tokenizer.encode(text_boundary, add_special_tokens=False).offsets if o[0] < hz_char)
    pred_b = clf.predict(text_boundary)
    text_start = hazard + filler * 20
    pred_s = clf.predict(text_start)
    print(f"\n  hazard-straddle text: {n_tok} tokens, hazard starts ~token {hz_tok} "
          f"(window boundary at 126), windows={len(clf._windows(n_tok))}")
    print(f"    straddled hazard: score={pred_b.sif_score} spans={[s.text for s in pred_b.evidence_spans]}")
    print(f"    hazard-at-start : score={pred_s.sif_score} spans={[s.text for s in pred_s.evidence_spans]}")
    # conflicting windows: benign head + hot tail / hot head + benign tail
    benign = ("everything normal during the shift, housekeeping good, no issues observed. " * 8)
    hot = "worker fell 6 meters from scaffold without harness, taken to hospital. "
    for name, t in (("benign->hot", benign + hot), ("hot->benign", hot + benign)):
        p = clf.predict(t)
        n = len(clf._tokenizer.encode(t, add_special_tokens=False).ids)
        print(f"  {name}: tokens={n} windows={len(clf._windows(n))} "
              f"score={p.sif_score} chunked={p.chunked} spans={[s.text for s in p.evidence_spans]}")
    # int8 within-predict window batching (D27 gap): run windows together vs alone
    t = benign + hot
    enc = clf._tokenizer.encode(t, add_special_tokens=False)
    windows = clf._windows(len(enc.ids))
    ids, mask = clf._pad_rows([enc.ids[s:e] for s, e in windows])
    sl, _, _ = clf._session.run(["sif_logit", "rule_logits", "span_logits"],
                                {"input_ids": ids, "attention_mask": mask})
    together = 1 / (1 + np.exp(-sl.astype(np.float64) / clf.temperature))
    solo = []
    for s, e in windows:
        i1, m1 = clf._pad_rows([enc.ids[s:e]])
        l1, _, _ = clf._session.run(["sif_logit", "rule_logits", "span_logits"],
                                    {"input_ids": i1, "attention_mask": m1})
        solo.append(1 / (1 + np.exp(-l1[0].astype(np.float64) / clf.temperature)))
    print(f"\n  int8 window-batching: together={together.tolist()} solo={solo}")
    print(f"    max-pool together={float(np.max(together)):.6f} vs solo={float(np.max(solo)):.6f} "
          f"delta={abs(float(np.max(together)) - float(np.max(solo))):.2e}")
    # determinism
    p1 = clf.predict(t).sif_score
    p2 = clf.predict(t).sif_score
    print(f"  same input twice: {p1} vs {p2} -> {'DETERMINISTIC' if p1 == p2 else 'NONDET'}")
    # unbounded input: 200k chars
    big = filler * 4000
    n_big = len(clf._tokenizer.encode(big, add_special_tokens=False).ids)
    t0 = time.perf_counter()
    clf.predict(big)
    dt = time.perf_counter() - t0
    print(f"  200k-char paste: {n_big} tokens, {len(clf._windows(n_big))} windows, {dt:.2f}s "
          f"(no input length cap in ReportIn/ingest)")


# -------------------------------------------------------------------- E: gates
def probe_gates():
    banner("E. gates")
    cfg = Settings()

    print("-- drill filter (bare 'drill' must be excluded) --")
    drill_cases = [
        "Drill pipe pressure test at 5000 psi, all holding steady.",
        "Drill pipe pressure test was completed without anomalies.",
        "The drill was completed at 14:00 hrs, rig move next.",
        "Drilling completed on well XYZ ahead of schedule.",
        "Crew reminded to exercise caution near the rotary table.",
        "Planned test of the BOP this weekend per schedule.",
        "Mock drill conducted at GGS for fire response.",
        "Fire drill at noon, all mustered.",
        "Simulated gas alarm during calibration check.",
        "Rig floor hands performed drill line slip and cut.",
    ]
    for t in drill_cases:
        g = gate_drill(t)
        print(f"  [{'TRIG' if g.triggered else ' ok '}] {t!r} {('-> ' + g.detail) if g.triggered else ''}")

    print("-- min-length codes path --")
    len_cases = [
        "LOTO not applied",
        "loto applied",
        "LOTOS on pump 3",
        "LOTOS applied",
        "LOTOs verified",
        "H2S detected at wellhead",
        "N2 leak at manifold",
        "short text no code",
    ]
    for t in len_cases:
        g = gate_min_length(t, cfg)
        print(f"  [{'GRAY' if g.triggered else ' ok '}] len={len(t.strip()):2d} {t!r} {g.detail}")

    print("-- negation: punctuation / sentence-boundary collapse --")
    neg_cases = [
        "X-ray confirmed a fracture. No doubt about the diagnosis.",
        "No issues noted during rounds; hospital corridor slippery near ward.",
        "Employee had a fracture. No hospitalization was needed.",
        "Worker fell 2m. No injury occurred.",
        "Fracture of the drill bit reported. No other damage.",
        "no. injury",
        "Several cuts and bruises, not serious.",
        "Pipe severed hydraulic line. Not near personnel at the time.",
    ]
    for t in neg_cases:
        g = gate_negation(t)
        print(f"  [{'GRAY' if g.triggered else ' ok '}] {t!r} {('-> ' + g.detail) if g.triggered else ''}")

    print("-- language gate --")
    lang_cases = [
        "Worker राम Kumar slipped near the walkway at GGS.",
        "Near miss at rig 🚨 crew safe.",
        "пожар near the flare stack, extinguished quickly with foam.",
        "Normal English report about a dropped pipe at the rack.",
        "",
    ]
    for t in lang_cases:
        g = gate_language(t, cfg)
        print(f"  [{'GRAY' if g.triggered else ' ok '}] {t!r} {('-> ' + g.detail) if g.triggered else ''}")


# ------------------------------------------------------ F: protocol dead code
def probe_protocol():
    banner("F. Classifier protocol / dead nested def")
    print(f"  hasattr(Classifier, 'classify_batch'): {hasattr(Classifier, 'classify_batch')}")
    print(f"  hasattr(Classifier, 'predict'): {hasattr(Classifier, 'predict')}")
    nested = [c.co_name for c in flag_threshold.__code__.co_consts
              if hasattr(c, 'co_name')]
    print(f"  nested code objects inside flag_threshold: {nested} "
          f"(unreachable — defined after `return`)")
    m = MockClassifier()
    print(f"  Mock classify_batch works anyway (concrete class): {len(m.classify_batch(['a', 'b']))}")
    # does anything depend on Protocol having classify_batch? runtime only.
    print(f"  flag_threshold(MockClassifier()) = {flag_threshold(m)}")


# ------------------------------------------------------------- G: temperature
def probe_temperature(clf: RealOnnxClassifier):
    banner("G. temperature application consistency")
    print(f"  clf.temperature={clf.temperature}")
    print(f"  clf.sif_flag_threshold={clf.sif_flag_threshold:.6f} "
          f"(metrics.json says threshold_calibrated=0.712581)")
    metrics = json.loads((MODEL_DIR / "metrics.json").read_text())
    print(f"  metrics.json has keys: {sorted(metrics.keys())[:8]}...")
    print(f"  val-frozen sif.operating_point.threshold={metrics['sif']['operating_point']['threshold']:.3e} "
          f"(present in file but NOT used by _load_flag_threshold)")
    # rule thresholds tuned per-rule exist in artifact but app uses 0.5
    from app.schemas import RULE_DISPLAY
    print(f"  artifact rule thresholds: {metrics['rules']['line_of_fire']['threshold']}, "
          f"{metrics['rules']['driving']['threshold']}, ... (metrics.json 'rules'.*.threshold)")
    print(f"  app RULE_DISPLAY thresholds: { {k: v['threshold'] for k, v in RULE_DISPLAY.items() if v['in_scope']} }")
    # verify single application: grep-like check of source
    src = Path("app/classifier.py").read_text()
    print(f"  occurrences of 'self.temperature' in classifier.py: {src.count('self.temperature')}")
    # rule_probs are NOT temperature-scaled (line 365): tuned rule thresholds
    # were fit on raw-sigmoid scale -> consistent IF thresholds are raw-scale.
    print("  rule head: sigmoid(raw) with no /T — consistent with raw-scale tuned "
          "rule thresholds, but those thresholds are never loaded by the app.")


def main():
    print("Loading real model:", MODEL_DIR)
    clf = RealOnnxClassifier(MODEL_DIR)
    print("model_version:", clf.model_version, "| quant:", clf.quant,
          "| supports_exact_batch:", clf.supports_exact_batch)

    probe_rule_order(clf)
    probe_offsets(clf)
    probe_threshold_loading()
    probe_chunking(clf)
    probe_gates()
    probe_protocol()
    probe_temperature(clf)


if __name__ == "__main__":
    main()
