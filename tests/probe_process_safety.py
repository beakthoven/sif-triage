"""Process-safety probe — the orchestrator's novel-text probe as a runnable eval.

Turns docs/discovery/60-orchestrator-novel-probe.md ("directional probe, n=18,
NOT a validated evaluation") into a proper runnable eval:

  * 62 hand-labelled scenarios (50 golden-set cases + 12 probe-only extras),
    stratified across (a) the 9 IOGP Life-Saving Rules and (b) the three
    strata the problem statement asks about:
      - procedural-barrier failures (the absent control is the precursor)
      - realised physical mechanisms (the event that nearly happened)
      - benign / administrative reports (must NOT be flagged)
  * recall per barrier type, two ways:
      - flag recall:   sif_score >= the classifier's current operating point,
        loaded dynamically through app.classifier.flag_threshold
      - routed recall: flagged OR any gray-action gate (well_control_watch,
        severity_watch, confidence band) — the full review-routing path
  * paraphrase verdict-stability: per group, score spread + verdict flips.

HONESTY BOUNDARY (do not strip): every label is EXPERT JUDGEMENT authored
this session, seeded from the categories of the orchestrator probe doc. It is
NOT the human gold set — the gold set remains the untouched final eval. The
probe doc's own "Required follow-up" (human-labelled, IOGP-stratified,
>=2 independent labelers) still applies to any number quoted externally.

COVERAGE IS ASSERTED, NOT CLAIMED: all 9 IOGP rules represented in the
barrier stratum, all three strata non-empty, >=60 scenarios total.

RUN:
  .venv/bin/python tests/probe_process_safety.py   # report + JSON artifact
  .venv/bin/pytest tests/probe_process_safety.py   # structural checks only

The pytest wrapper does NOT pass/fail on recall values — the honest current
finding is that procedural recall is LOW (the Phase-0 defect this workstream's
fixes target); a permanently-red eval would be noise and a green one would be
overclaiming. The JSON written to
artifacts/qa-evidence/probe_process_safety.json is the quotable artifact.

METHOD: the canonical single-text path (same as tests/golden_regression.py):
classifier.predict -> validate spans -> run_gates with an empty near-dup index
stub, i.e. the /api/classify route minus the index-dependent gate.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:  # package context (repo root importable)
    from tests.golden_regression import (
        ALL_RULES, CASES, PARAPHRASE_GROUPS, flag_threshold, load_classifier, observe,
    )
except ImportError:  # bare script run: tests/ itself is on sys.path
    from golden_regression import (
        ALL_RULES, CASES, PARAPHRASE_GROUPS, flag_threshold, load_classifier, observe,
    )

EVIDENCE_DIR = REPO_ROOT / "artifacts" / "qa-evidence"
REPORT_PATH = EVIDENCE_DIR / "probe_process_safety.json"

# Probe-only additions: round stratification out to n>=60. These do NOT join
# the golden stability baseline; same labelling discipline as CASES.
EXTRA_CASES: list[dict] = [
    {"id": "X1", "stratum": "barrier", "rule": "confined_space",
     "text": "A technician dropped through the sewer manhole at the EPS boundary "
             "to clear a blockage without a confined space entry permit or a gas meter."},
    {"id": "X2", "stratum": "barrier", "rule": "safe_mechanical_lifting",
     "text": "The mobile crane was positioned with its boom reaching across the "
             "overhead powerlines; no spotter was assigned for the lift."},
    {"id": "X3", "stratum": "barrier", "rule": "working_at_height",
     "text": "Rope access to the flare tip started before anyone confirmed the "
             "second anchorage; the rope grab was back at the tool crib."},
    {"id": "X4", "stratum": "barrier", "rule": "driving",
     "text": "The water bowser reversed into the loading bay without a banksman "
             "or reversing alarm; the spotter had been sent to another task."},
    {"id": "X5", "stratum": "mechanism", "rule": "line_of_fire",
     "text": "The scaffold inside the tank farm collapsed while two painters were "
             "planked on the third lift; both fell into the bund."},
    {"id": "X6", "stratum": "mechanism", "rule": "confined_space",
     "text": "An operator was engulfed to the waist in the powder silo when the "
             "bridged product released during the unloading attempt."},
    {"id": "X7", "stratum": "mechanism", "rule": "line_of_fire",
     "text": "The angle-grinder disc shattered and a fragment hit the fitter's "
             "face shield while he was dressing the weld on the skid."},
    {"id": "X8", "stratum": "mechanism", "rule": "energy_isolation",
     "text": "High-pressure steam escaped from the opened flange and scalded the "
             "technician's arm during the header blow-through."},
    {"id": "X9", "stratum": "benign", "rule": None,
     "text": "Canteen hygiene audit completed; kitchen deep-clean scheduled for the weekend."},
    {"id": "X10", "stratum": "benign", "rule": None,
     "text": "The air conditioner in the control room was serviced and the filters replaced."},
    {"id": "X11", "stratum": "benign", "rule": None,
     "text": "Radiation safety signage for the NDT campaign was verified at all four approaches."},
    {"id": "X12", "stratum": "benign", "rule": None,
     "text": "Gate pass audit correction: two visitors' induction dates were backfilled."},
]

ALL_SCENARIOS = CASES + EXTRA_CASES


def _rate(hits: int, n: int) -> float:
    return round(hits / n, 4) if n else 0.0


def run_eval(clf) -> dict:
    """Classify every scenario, measure, write the JSON artifact, return it."""
    thr = flag_threshold(clf)
    records: dict[str, dict] = {}
    for case in ALL_SCENARIOS:
        obs = observe(clf, case["text"])
        obs["id"] = case["id"]
        obs["stratum"] = case["stratum"]
        obs["rule"] = case["rule"]
        obs["text"] = case["text"]
        obs["flagged"] = obs["score"] >= thr
        obs["routed"] = obs["flagged"] or len(obs["gray"]) > 0
        records[case["id"]] = obs

    def rows_of(stratum: str) -> list[dict]:
        return [r for r in records.values() if r["stratum"] == stratum]

    summary: dict = {
        "meta": {
            "date": "2026-09-27",
            "classifier": type(clf).__name__,
            "model_version": clf.model_version,
            "flag_threshold": thr,
            "n_scenarios": len(records),
            "n_by_stratum": {name: len(rows_of(name))
                             for name in ("barrier", "mechanism", "benign", "paraphrase")},
            "label_provenance": (
                "expert judgement by the harness author this session, seeded from "
                "docs/discovery/60-orchestrator-novel-probe.md; NOT human gold and "
                "NOT externally quotable without the multi-labeler follow-up named "
                "in that doc"
            ),
            "gates_note": (
                "near-dup index stubbed empty; production gates otherwise; routed recall "
                "counts model flags OR gray-action gates (not model flags alone)"
            ),
        },
        "strata": {},
        "barrier_gate_false_gray_ids": [],
        "barrier_by_rule": {},
        "paraphrase_stability": {},
        "determinism": {},
        "records": records,
    }

    for name in ("barrier", "mechanism"):
        rows = rows_of(name)
        scores = [r["score"] for r in rows]
        summary["strata"][name] = {
            "n": len(rows),
            "flag_recall": _rate(sum(1 for r in rows if r["flagged"]), len(rows)),
            "routed_recall": _rate(sum(1 for r in rows if r["routed"]), len(rows)),
            "mean_score": round(statistics.mean(scores), 4),
            "median_score": round(statistics.median(scores), 4),
            "min_score": min(scores),
            "max_score": max(scores),
        }

    benign = rows_of("benign")
    barrier_gate_names = {
        "energy_isolation_absent", "gas_test_absent", "permit_absent",
        "fire_watch_absent", "standby_absent", "atmosphere_unmonitored",
        "fall_protection_absent",
    }
    summary["barrier_gate_false_gray_ids"] = sorted(
        r["id"] for r in benign if barrier_gate_names.intersection(r["gray"])
    )
    summary["strata"]["benign"] = {
        "n": len(benign),
        "false_flag_rate": _rate(sum(1 for r in benign if r["flagged"]), len(benign)),
        "false_gray_rate": _rate(
            sum(1 for r in benign if not r["flagged"] and r["gray"]), len(benign)),
        "mean_score": round(statistics.mean(r["score"] for r in benign), 4),
        "false_flag_ids": sorted(r["id"] for r in benign if r["flagged"]),
    }

    for rule in ALL_RULES:
        rows = [r for r in records.values()
                if r["stratum"] in ("barrier", "paraphrase") and r["rule"] == rule]
        if not rows:
            continue
        summary["barrier_by_rule"][rule] = {
            "n": len(rows),
            "flag_recall": _rate(sum(1 for r in rows if r["flagged"]), len(rows)),
            "routed_recall": _rate(sum(1 for r in rows if r["routed"]), len(rows)),
        }

    for group, ids in PARAPHRASE_GROUPS.items():
        rows = [records[i] for i in ids]
        verdict_counts: dict[str, int] = {}
        for r in rows:
            verdict_counts[r["band"]] = verdict_counts.get(r["band"], 0) + 1
        majority = max(verdict_counts, key=verdict_counts.get)
        summary["paraphrase_stability"][group] = {
            "n": len(rows),
            "scores": [r["score"] for r in rows],
            "mean": round(statistics.mean(r["score"] for r in rows), 4),
            "sd": round(statistics.pstdev([r["score"] for r in rows]), 4),
            "flagged": sum(1 for r in rows if r["flagged"]),
            "distinct_verdicts": len(verdict_counts),
            "majority_verdict": majority,
        }

    # determinism: re-observe every scenario once more, require exact equality
    nondeterministic = []
    for case in ALL_SCENARIOS:
        obs = observe(clf, case["text"])
        rec = records[case["id"]]
        if (obs["score"] != rec["score"] or obs["band"] != rec["band"]
                or obs["gray"] != rec["gray"]):
            nondeterministic.append(case["id"])
    summary["determinism"] = {
        "re_observed": len(ALL_SCENARIOS),
        "nondeterministic_ids": nondeterministic,
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    return summary


def print_report(s: dict) -> None:
    m = s["meta"]
    print(f"process-safety probe — {m['n_scenarios']} scenarios | {m['classifier']} | "
          f"flag threshold {m['flag_threshold']:.4f}")
    print("  labels: expert judgement (probe-doc seed), NOT human gold — "
          "see label_provenance in the JSON artifact")
    for name, row in s["strata"].items():
        if name == "benign":
            print(f"  {name:<10} n={row['n']:<3} false_flag_rate={row['false_flag_rate']} "
                  f"false_gray_rate={row['false_gray_rate']} mean={row['mean_score']} "
                  f"(false-flag ids: {row['false_flag_ids'] or 'none'})")
        else:
            print(f"  {name:<10} n={row['n']:<3} flag_recall={row['flag_recall']} "
                  f"routed_recall={row['routed_recall']} mean={row['mean_score']} "
                  f"range=[{row['min_score']}, {row['max_score']}]")
    print("  benign barrier-gate false-gray: "
          f"{len(s['barrier_gate_false_gray_ids'])}/16 "
          f"({s['barrier_gate_false_gray_ids'] or 'none'})")
    print("  barrier recall by IOGP rule (flag / routed):")
    for rule, row in s["barrier_by_rule"].items():
        print(f"    {rule:<26} {row['flag_recall']} / {row['routed_recall']} (n={row['n']})")
    print("  paraphrase verdict stability (flagged/n, sd, distinct verdicts):")
    for group, row in s["paraphrase_stability"].items():
        print(f"    {group:<28} {row['flagged']}/{row['n']} flagged, sd={row['sd']}, "
              f"verdicts={row['distinct_verdicts']}, majority={row['majority_verdict']}")
    det = s["determinism"]
    print("  determinism: " + (
        f"NON-DETERMINISTIC on {det['nondeterministic_ids']}"
        if det["nondeterministic_ids"]
        else "all scenarios reproduced identically"))


def structural_checks(s: dict) -> list[str]:
    """Structural invariants the pytest wrapper can assert without
    certifying model quality."""
    problems = []
    if s["meta"]["n_scenarios"] < 60:
        problems.append(f"n_scenarios={s['meta']['n_scenarios']} < 60")
    for stratum, minimum in (("barrier", 15), ("mechanism", 8), ("benign", 12)):
        n = s["strata"].get(stratum, {}).get("n", 0)
        if n < minimum:
            problems.append(f"stratum {stratum} has n={n} (< {minimum})")
    missing = [r for r in ALL_RULES if s["barrier_by_rule"].get(r, {}).get("n", 0) == 0]
    if missing:
        problems.append(f"IOGP rules with zero stratified scenarios: {missing}")
    if s["determinism"]["nondeterministic_ids"]:
        problems.append(
            f"non-deterministic scenarios: {s['determinism']['nondeterministic_ids']}")
    return problems


def test_probe_process_safety_eval_is_sound() -> None:
    """pytest wrapper: structural soundness only (n, stratification,
    determinism). Recall values are REPORTED to the JSON artifact, never
    asserted here — the model's procedural gap is a known disclosed defect,
    and a green bar here must never be read as model validation."""
    clf = load_classifier()
    problems = []
    if type(clf).__name__ == "MockClassifier":
        problems.append("no ONNX artifact loads — the probe ran against "
                        "MockClassifier, which cannot validate the model")
    report = run_eval(clf)
    print_report(report)
    problems.extend(structural_checks(report))
    assert not problems, "probe eval structurally unsound: " + "; ".join(problems)


if __name__ == "__main__":
    clf = load_classifier()
    if type(clf).__name__ == "MockClassifier":
        print("WARNING: running against MockClassifier (no ONNX artifact/tokenizer); "
              "this measures the stub, not the model.")
    print_report(run_eval(clf))
    sys.exit(0)
