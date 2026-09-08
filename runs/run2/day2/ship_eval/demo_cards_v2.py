"""13 demo cards through masked-v2 (and masked-v1 for a like-for-like column),
in-process, mirroring the app's predict semantics WITHOUT importing the app
classifier (it is being edited by another agent — the SEV1-1 rule-order fix):

  * windowing: 126 body tokens, stride 96 (RealOnnxClassifier._windows)
  * each window its own single-row session.run (D27 canonical; also the
    SEV2-1 fix direction — no int8 window-batching)
  * max-pool calibrated sif probs and raw-sigmoid rule probs across windows,
    spans from the argmax window (span comparison is a separate item)
  * rule names zipped in TRAINING ORDER (train.py:87 — the TRUE order; the
    app's alphabetical RULE_KEYS zip is the SEV1-1 bug, being fixed in
    parallel). Per-rule thresholds from each model's thresholds.json.

Gates are evaluated with the app's pure gate functions (app/gates.py —
deterministic, no model state) + has_well_control (app/classifier.py,
D23-synced keyword list). near-dup is NOT evaluated here (needs the live
storage index; v1 record: every synthetic card fires it by design, D24).

Writes demo_cards_v2.json + prints the expected-behavior table.
Run: .venv/bin/python runs/run2/day2/ship_eval/demo_cards_v2.py
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "runs/run2/day1/real_model_integration"))
sys.path.insert(0, str(REPO))

from onnx_score import RULES, sigmoid  # noqa: E402

from app.classifier import has_well_control  # noqa: E402
from app.config import Settings  # noqa: E402
from app.gates import (gate_confidence, gate_drill, gate_language,  # noqa: E402
                       gate_long_input, gate_min_length, gate_negation)

HERE = Path(__file__).resolve().parent
SEQ_LEN = 128
STRIDE = 96

BANDS = ((0.7, "HIGH"), (0.4, "MODERATE"), (0.0, "LOW"))

EXPECTED = {  # from demo_corpus.jsonl expected blocks (abridged to checkables)
    "contrast-red":   {"band": "HIGH", "flag": True,  "rule": "line_of_fire", "wc": False},
    "contrast-green": {"band": "LOW",  "flag": False, "rule": None, "wc": False},
    "gray-negation":  {"band": "GRAY", "flag": None,  "rule": None, "wc": False, "gate": "negation"},
    "gray-drill":     {"band": "GRAY", "flag": False, "rule": None, "wc": False, "gate": "drill"},
    "wc-baghjan-1":   {"band": "HIGH", "flag": True,  "rule": "confined_space", "wc": True},
    "wc-baghjan-2":   {"band": "HIGH", "flag": True,  "rule": "energy_isolation", "wc": True},
    "wc-baghjan-3":   {"band": "HIGH", "flag": True,  "rule": "hot_work", "wc": True},
    "hinglish":       {"band": "GRAY", "flag": None,  "rule": None, "wc": None, "gate": "language"},
    "verbatim-osha":  {"band": "HIGH", "flag": True,  "rule": "line_of_fire", "wc": False},
    "long-report":    {"band": "HIGH", "flag": True,  "rule": "line_of_fire", "wc": False, "gate": "long_input"},
    "mega-report":    {"band": "HIGH", "flag": True,  "rule": "ALL7", "wc": True},
    "codes-only":     {"band": "GRAY", "flag": None,  "rule": None, "wc": False, "gate": "codes_accept"},
    "first-aid-green": {"band": "LOW", "flag": False, "rule": None, "wc": False},
}


def windows(n_body):
    body = SEQ_LEN - 2
    if n_body <= body:
        return [(0, n_body)]
    out = [(i, min(i + body, n_body)) for i in range(0, n_body, STRIDE)]
    if out[-1][1] < n_body:
        out.append((n_body - body, n_body))
    return out


class CardScorer:
    """Per-window single-row scoring for one model dir (int8)."""

    def __init__(self, model_dir):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.dir = Path(model_dir)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 8
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(self.dir / "sif_multitask_int8.onnx"), opts,
            providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(self.dir / "tokenizer" / "tokenizer.json"))
        t = json.loads((self.dir / "thresholds.json").read_text())
        m = json.loads((self.dir / "metrics.json").read_text())
        self.temperature = float(t["temperature"])
        self.rule_thresholds = t["rule_thresholds"]
        self.op_raw = float(m["operating_point_test_tuned"]["threshold"])
        self.op_cal = float(m["operating_point_test_tuned"]["threshold_calibrated"])

    def predict(self, text):
        enc = self.tok.encode(text, add_special_tokens=False)
        cls = self.tok.token_to_id("[CLS]")
        sep = self.tok.token_to_id("[SEP]")
        wins = windows(len(enc.ids))
        sif_cal, rule_p = [], []
        for s, e in wins:
            body = enc.ids[s:e]
            ids = np.array([[cls, *body, sep]], dtype=np.int64)
            mask = np.ones_like(ids)
            z, rl = self.session.run(
                ["sif_logit", "rule_logits"],
                {"input_ids": ids, "attention_mask": mask})
            sif_cal.append(float(sigmoid(z[0] / self.temperature)))
            rule_p.append(sigmoid(rl[0]))
        sif_score = max(sif_cal)
        rule_probs = {r: float(p) for r, p in zip(RULES, np.max(np.stack(rule_p), axis=0))}
        # decision identical on raw or cal scale (monotonic map); use cal display
        return {
            "p_cal": sif_score,
            "flag": bool(sif_score >= self.op_cal),
            "rule_probs": rule_probs,
            "rules_fired": [r for r in RULES
                            if rule_probs[r] >= self.rule_thresholds[r]],
            "chunked": len(wins) > 1,
            "n_windows": len(wins),
        }


def band_of(score, gray):
    if gray:
        return "GRAY"
    for lo, name in BANDS:
        if score >= lo:
            return name
    return "LOW"


def run_gates(text, score, cfg):
    """The app gate order minus near-dup (needs the live index; D24 note)."""
    states = {}
    for g in (gate_min_length(text, cfg), gate_negation(text),
              gate_language(text, cfg), gate_confidence(score, cfg),
              gate_drill(text), gate_long_input(text, cfg)):
        states[g.name] = {"triggered": g.triggered, "action": g.action,
                          "detail": g.detail}
    return states


def verdict(card_id, exp, res, gates, wc):
    probs = []
    gray = any(g["triggered"] and g["action"] == "gray" for g in gates.values())
    band = band_of(res["p_cal"], gray)
    if exp.get("gate") == "codes_accept":
        ml = gates["min_length"]
        if ml["triggered"] or "codes path" not in (ml["detail"] or ""):
            probs.append(f"codes path not taken ({ml['detail']!r})")
    elif exp.get("gate") and not gates.get(exp["gate"], {}).get("triggered"):
        probs.append(f"expected gate {exp['gate']} did not fire")
    if exp["band"] != "GRAY" and band != exp["band"]:
        probs.append(f"band {band} != {exp['band']}")
    if exp.get("flag") is not None and res["flag"] != exp["flag"]:
        probs.append(f"flag {res['flag']} != {exp['flag']}")
    top_rule = max(res["rule_probs"], key=res["rule_probs"].get)
    if exp.get("rule") == "ALL7":
        if len(res["rules_fired"]) < 7:
            probs.append(f"only {len(res['rules_fired'])}/7 rules fired "
                         f"{sorted(set(RULES) - set(res['rules_fired']))}")
    elif exp.get("rule") and top_rule != exp["rule"]:
        probs.append(f"top rule {top_rule} != expected {exp['rule']}")
    if exp.get("wc") is not None and wc != exp["wc"]:
        probs.append(f"wc {wc} != {exp['wc']}")
    return ("PASS" if not probs else "DEVIATION"), probs, band, top_rule


def main():
    cfg = Settings()
    cards = [json.loads(l) for l in (REPO / "artifacts/demo/demo_corpus.jsonl").open()]
    scorers = {name: CardScorer(REPO / f"artifacts/models/{name}")
               for name in ("masked-v1", "masked-v2")}
    out = {}
    for name, sc in scorers.items():
        rows = []
        for c in cards:
            res = sc.predict(c["text"])
            wc = has_well_control(c["text"])
            gates = run_gates(c["text"], res["p_cal"], cfg)
            v, probs, band, top_rule = verdict(c["demo_id"], EXPECTED[c["demo_id"]],
                                               res, gates, wc)
            rows.append({
                "card": c["demo_id"], "p_cal": round(res["p_cal"], 4),
                "flag": res["flag"], "band": band,
                "top_rule": top_rule,
                "top_rule_p": round(res["rule_probs"][top_rule], 4),
                "rules_fired": res["rules_fired"],
                "wc": wc, "chunked": res["chunked"],
                "gates": {k: g for k, g in gates.items() if g["triggered"]},
                "verdict": v, "problems": probs,
            })
        out[name] = {"op_raw": sc.op_raw, "op_cal": sc.op_cal,
                     "temperature": sc.temperature, "rows": rows}
    (HERE / "demo_cards_v2.json").write_text(json.dumps(out, indent=1) + "\n")

    for name in ("masked-v1", "masked-v2"):
        o = out[name]
        print(f"\n=== {name} (op_cal {o['op_cal']:.4f}, T {o['temperature']:.3f}) ===")
        print(f"{'card':<15} {'score':>6} {'band':<9} {'flag':<5} {'wc':<5} "
              f"{'top rule (p)':<28} {'gates':<22} verdict")
        for r in o["rows"]:
            gs = ",".join(g for g in r["gates"] if g != "near_dup") or "-"
            print(f"{r['card']:<15} {r['p_cal']:>6.3f} {r['band']:<9} "
                  f"{str(r['flag']):<5} {str(r['wc']):<5} "
                  f"{r['top_rule'] + ' (' + format(r['top_rule_p'], '.2f') + ')':<28} "
                  f"{gs:<22} {r['verdict']}"
                  + (f"  <- {'; '.join(r['problems'])}" if r["problems"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
