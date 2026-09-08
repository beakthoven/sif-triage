"""Demo-card re-verification under the D19 test-tuned operating point.

Scores the 13 demo cards (artifacts/demo/demo_corpus.jsonl) through the SHIP
path — app.classifier.RealOnnxClassifier, int8, sliding-window max-pool —
runs the deterministic text gates, and checks two SEPARATE things:

  A. Threshold-induced flips (the D19 ask): the re-tune moves ONLY the flag
     cutoff (0.5 a-priori -> tuned calibrated). Bands are derived from the
     score (dashboard bandFor: 0.7/0.4) and cannot move. The only decisions
     that can flip are cards scoring inside [min(old,new), max(old,new)).
     PASS = no card score in that zone AND the app's flag_threshold equals
     the tuned value.

  B. Expectation audit (informational): effective band (score band, or GRAY
     when a gray-action gate fires) and flag vs each card's `expected`
     annotation. Known PRE-EXISTING mismatches, none caused by the re-tune:
       - first-aid-green: D21 — the model genuinely scores the first-aid row
         0.964 HIGH (masked-v2 retrain in flight).
       - long-report: negation gate fires on 'no'~'damage' — the demo pack's
         own selfcheck (artifacts/demo/selfcheck_demo_pack.py) is RED on the
         same check before this work; gate-stem scope issue, not threshold.
       - codes-only: mock-era annotation expects the score to land in the
         [0.40,0.60] gray band; the real model scores 0.115 (LOW). The card's
         asserted behavior (codes-path acceptance) passes in the demo pack
         selfcheck; only the band annotation is stale.

near_dup is NOT run (embedding index is another agent's D24 rebuild);
verbatim-osha's banner expectation is annotated, not asserted.

Reads the tuned threshold from runs/run2/day1/operating_point/operating_point.json.
Run: .venv/bin/python runs/run2/day1/operating_point/check_demo_cards.py
Exit 0 = no threshold-induced flips and no UNDOCUMENTED expectation mismatches.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from app.classifier import RealOnnxClassifier, flag_threshold  # noqa: E402
from app.config import Settings  # noqa: E402
from app.gates import (  # noqa: E402
    gate_confidence,
    gate_drill,
    gate_language,
    gate_long_input,
    gate_min_length,
    gate_negation,
)

HERE = Path(__file__).resolve().parent
CARDS_PATH = REPO / "artifacts/demo/demo_corpus.jsonl"
OP_PATH = HERE / "operating_point.json"
OLD_THRESHOLD = 0.5  # a-priori cutoff the app used before the D19 re-tune
PRE_EXISTING = {
    "first-aid-green": "D21: high first-aid score is model behavior, masked-v2 retrain in flight",
    "long-report": "pre-existing: negation gate 'no'~'damage' (demo-pack selfcheck RED pre-tune)",
    "codes-only": "pre-existing: mock-era gray-band annotation vs real score 0.115 < 0.40",
}


def band_for(score: float) -> str:
    return "HIGH" if score >= 0.7 else "MODERATE" if score >= 0.4 else "LOW"


def main() -> int:
    op = json.loads(OP_PATH.read_text())
    thr_cal = op["masked"]["operating_point_test_tuned"]["threshold_calibrated"]
    cards = [json.loads(l) for l in CARDS_PATH.open(encoding="utf-8")]
    assert len(cards) == 13, f"{len(cards)} cards != 13"

    cfg = Settings()
    clf = RealOnnxClassifier(REPO / "artifacts/models/masked-v1")
    runtime_thr = flag_threshold(clf)
    assert abs(runtime_thr - thr_cal) < 1e-9, (
        f"app flag_threshold {runtime_thr} != tuned {thr_cal} — "
        "metrics.json not updated or wiring broken")

    flip_zone = (min(OLD_THRESHOLD, thr_cal), max(OLD_THRESHOLD, thr_cal))
    rows = []
    threshold_flips = []
    undocumented = []
    for card in cards:
        text = card["text"]
        exp = card["expected"]
        pred = clf.predict(text)
        score = pred.sif_score
        gates = [
            gate_min_length(text, cfg),
            gate_negation(text),
            gate_language(text, cfg),
            gate_confidence(score, cfg),
            gate_drill(text),
            gate_long_input(text, cfg),
        ]
        gray_gates = [g.name for g in gates if g.triggered and g.action == "gray"]
        effective = "GRAY" if gray_gates else band_for(score)
        exp_band = exp["band"].replace("-with-banner", "")  # banner is D24's
        flag_new = score >= thr_cal
        flag_old = score >= OLD_THRESHOLD
        if flag_new != flag_old:
            threshold_flips.append(card["demo_id"])
        band_ok = effective == exp_band
        exp_flag = exp.get("sif_flag")
        flag_ok = exp_flag is None or flag_new == exp_flag
        if not (band_ok and flag_ok) and card["demo_id"] not in PRE_EXISTING:
            undocumented.append(card["demo_id"])
        rows.append({
            "demo_id": card["demo_id"],
            "score": score,
            "score_band": band_for(score),
            "gray_gates": gray_gates,
            "effective_band": effective,
            "expected_band": exp["band"],
            "band_ok": band_ok,
            "flag@0.5": flag_old,
            "flag@tuned": flag_new,
            "expected_flag": exp_flag,
            "expectation_match": band_ok and flag_ok,
            "pre_existing": PRE_EXISTING.get(card["demo_id"], "") if not (band_ok and flag_ok) else "",
        })

    print(f"tuned calibrated threshold: {thr_cal:.6f} "
          f"(raw {op['masked']['operating_point_test_tuned']['threshold']:.6g}); "
          f"app flag_threshold agrees: {runtime_thr:.6f}")
    print(f"threshold-induced flip zone: [{flip_zone[0]:.6f}, {flip_zone[1]:.6f})")
    print(f"\n{'card':<16} {'score':>6} {'band':>9} {'gray-gates':<18} "
          f"{'expected':>16} {'f@0.5':>5} {'f@new':>5} {'exp':>5}  verdict")
    for r in rows:
        if r["demo_id"] in threshold_flips:
            verdict = "THRESHOLD-FLIP"
        elif r["expectation_match"]:
            verdict = "OK"
        else:
            verdict = f"pre-existing ({r['pre_existing'].split(':')[0]})"
        print(f"{r['demo_id']:<16} {r['score']:>6.4f} {r['effective_band']:>9} "
              f"{','.join(r['gray_gates']) or '-':<18} {r['expected_band']:>16} "
              f"{str(r['flag@0.5']):>5} {str(r['flag@tuned']):>5} "
              f"{str(r['expected_flag']):>5}  {verdict}")

    out = {"threshold_calibrated": thr_cal,
           "threshold_raw": op["masked"]["operating_point_test_tuned"]["threshold"],
           "old_threshold": OLD_THRESHOLD,
           "flip_zone": list(flip_zone),
           "cards": rows,
           "threshold_flips": threshold_flips,
           "undocumented_mismatches": undocumented}
    (HERE / "demo_cards_optuned.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"\nwrote {HERE / 'demo_cards_optuned.json'}")
    if threshold_flips or undocumented:
        print(f"FAIL: threshold flips={threshold_flips} undocumented={undocumented}")
        return 1
    print("PASS: zero threshold-induced flips; all expectation mismatches are "
          "documented pre-existing issues (D21 / demo-pack gate scope / stale mock-era annotation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
