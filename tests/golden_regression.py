"""Golden regression set — 50 cases, score bands + barrier-gate outcomes frozen.

WHY THIS EXISTS: the repo had no working regression gate (pytest collected 0
tests from the repo root; the orchestrator's probe doc had established that
the model's behaviour on novel text is the thing most likely to regress while
the fixes land). This suite freezes, case by case, exactly what the deployed
INT8 artifact + gate chain do today. A later fix that shifts a verdict band,
flips a barrier-gate outcome, or moves a score out of band shows up here as a
diff against tests/golden_baseline.json — that is the "our fixes did not
regress behaviour" proof.

WHAT IT ASSERTS (stability, NOT correctness):
  1. Determinism: every case classified twice must produce the identical
     rounded score, verdict band and gate sets (int8 is a pure function of
     the text on this chain).
  2. Baseline stability: score (tol 1e-3), review-priority band
     (HIGH >= 0.7 / MODERATE >= 0.4 / LOW, the dashboard's bandFor rule),
     well_control tag, and the triggered gray/badge gate sets must match
     tests/golden_baseline.json exactly.
It does NOT assert that procedural-barrier cases are actually flagged — the
measured finding (docs/discovery/60-orchestrator-novel-probe.md Result 2) is
that they largely are NOT; that gap is reported by
tests/probe_process_safety.py, not silently baked into a pass/fail here.

CASE PROVENANCE (honesty note): the 50 cases are authored this session,
seeded from the scenario categories of
docs/discovery/60-orchestrator-novel-probe.md (novel mechanism vs procedural
barrier vs benign; near-miss register; paraphrase instability). Labels are
expert judgement, NOT human gold. Several paraphrase cases intentionally
reproduce the doc's Result 3 instability conditions.

RUN:
  .venv/bin/python tests/golden_regression.py            # compare vs baseline
  .venv/bin/python tests/golden_regression.py --update   # (re)freeze baseline
  .venv/bin/pytest tests/golden_regression.py            # same via pytest
Baseline bootstrap: with no baseline file, the first run writes it and PASSES
with a loud "baseline created — re-run to verify" note; the second run is the
real comparison.

METHOD (mirrors the /api/classify single-text path): classifier.predict() ->
validate_spans (route invariant) -> run_gates() with an EMPTY near-dup index
(a stub storage; the index-dependent near_dup gate therefore reports the
stable "index empty" badge, and everything else — negation, language,
confidence, drill, long_input, well_control_watch, chunked_low_score,
severity_watch, and the barrier-failure family — is the production math).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.classifier import (  # noqa: E402
    Classifier,
    MockClassifier,
    band_for,
    build_classifier,
    flag_threshold,
    pseudo_embed,
    validate_spans,
)
from app.config import Settings  # noqa: E402
from app.gates import run_gates  # noqa: E402

DEFAULT_MODEL = REPO_ROOT / "artifacts" / "models" / "masked-v2" / "sif_multitask_int8.onnx"
BASELINE_PATH = Path(__file__).resolve().parent / "golden_baseline.json"

# Band rule: app.classifier.band_for with the SAME tuned operating point and
# gray-band floor the server uses — imported, not duplicated. The previous
# local 0.7/0.4 copy (the deleted client-side dashboard rule) drifted the
# moment the server started owning the band assignment.


# ---------------------------------------------------------------------------
# The 50 golden cases. stratum: barrier | mechanism | benign | paraphrase.
# `rule` tags the IOGP Life-Saving Rule a barrier case violates; the two
# rules the model declares out of scope (work_authorisation,
# bypassing_safety_controls) are deliberately present — the problem statement
# names them, and their detection gap must stay visible.
# ---------------------------------------------------------------------------
CASES: list[dict] = [
    # --- mechanism (8): physical events; the model's measured strong spot ---
    {"id": "M1", "stratum": "mechanism", "rule": "safe_mechanical_lifting",
     "text": "A 12 tonne spool was traversed over the crew standing in the pipe "
             "rack while the crane was in motion; nobody below cleared the area."},
    {"id": "M2", "stratum": "mechanism", "rule": "energy_isolation",
     "text": "The bleed valve on the pressurised gas header was opened while the "
             "line was believed de-pressurised; gas blew out onto the operators."},
    {"id": "M3", "stratum": "mechanism", "rule": "confined_space",
     "text": "Two men entered the separator vessel to clear the internals during "
             "the nitrogen purge without breathing apparatus."},
    {"id": "M4", "stratum": "mechanism", "rule": "working_at_height",
     "text": "A worker slipped from a 2 m step ladder on the rig floor and "
             "fractured his wrist; he was hospitalised the same evening."},
    {"id": "M5", "stratum": "mechanism", "rule": "line_of_fire",
     "text": "The pig receiver door swung open while the cradle was being lowered; "
             "the operator's arm was caught between the door and the saddle."},
    {"id": "M6", "stratum": "mechanism", "rule": "energy_isolation",
     "text": "An electrician contacted a live 415 V panel while racking out the "
             "breaker; arc flash burned his forearm."},
    {"id": "M7", "stratum": "mechanism", "rule": "line_of_fire",
     "text": "A pipe wrench fell from the derrick floor and struck the floorman "
             "on the shoulder during tripping."},
    {"id": "M8", "stratum": "mechanism", "rule": "energy_isolation",
     "text": "H2S gas released from the wellhead during the workover; the crew "
             "donned masks and mustered upwind."},

    # --- procedural barrier failures (18): one-plus per IOGP rule; the
    # --- measured weak spot (probe Result 2 — many are expected to sit
    # --- below the flag threshold; stability, not correctness, is asserted).
    {"id": "B1", "stratum": "barrier", "rule": "confined_space",
     "text": "Entry was made into the crude oil storage tank for cleaning without "
             "conducting a gas test; the isolations had not been verified and no "
             "standby man was posted."},
    {"id": "B2", "stratum": "barrier", "rule": "energy_isolation",
     "text": "The maintenance team replaced a valve on the running crude transfer "
             "pump without isolating the motor; lock-out tag-out was not applied."},
    {"id": "B3", "stratum": "barrier", "rule": "hot_work",
     "text": "Welding was carried out on the tank roof beside an open oily drain; "
             "the fire watch had left the area and no extinguisher was staged."},
    {"id": "B4", "stratum": "barrier", "rule": "safe_mechanical_lifting",
     "text": "The crane crew slung the 8 tonne manifold with worn webbing slings "
             "that had no valid inspection tag."},
    {"id": "B5", "stratum": "barrier", "rule": "working_at_height",
     "text": "Two fitters climbed the flare stack scaffold without fall-arrest "
             "harnesses because the anchorage points were not installed."},
    {"id": "B6", "stratum": "barrier", "rule": "driving",
     "text": "The light vehicle left the GGS for the airport run with the rear "
             "seat belts unlatched; the driver was exceeding the site limit."},
    {"id": "B7", "stratum": "barrier", "rule": "work_authorisation",
     "text": "Hot tapping on the produced water line began before the permit to "
             "work was signed by the area authority."},
    {"id": "B8", "stratum": "barrier", "rule": "bypassing_safety_controls",
     "text": "The panel technician bypassed the compressor vibration trip so the "
             "skid could keep running through the night shift."},
    {"id": "B9", "stratum": "barrier", "rule": "confined_space",
     "text": "The vessel was entered for cleaning purposes. Atmosphere was not "
             "tested and nobody checked the isolation state."},
    {"id": "B10", "stratum": "barrier", "rule": "energy_isolation",
     "text": "The pump was worked on while energised; nobody confirmed the breaker "
             "was locked out before the flange was cracked."},
    {"id": "B11", "stratum": "barrier", "rule": "hot_work",
     "text": "Grinding near the live flowline went ahead without a hot work "
             "permit; sparks fell close to the flange."},
    {"id": "B12", "stratum": "barrier", "rule": "line_of_fire",
     "text": "The winch operator dragged the tote tank across the walkway while "
             "the crew were still inside the marked exclusion line."},
    {"id": "B13", "stratum": "barrier", "rule": "safe_mechanical_lifting",
     "text": "The load was lifted over live equipment with no certified slinger "
             "directing the lift and the banksman unavailable."},
    {"id": "B14", "stratum": "barrier", "rule": "working_at_height",
     "text": "The AC-sheet roof access for the lighting upgrade was done without "
             "crawl boards or a rescue plan."},
    {"id": "B15", "stratum": "barrier", "rule": "driving",
     "text": "The crew driver continued the 400 km night journey despite dozing "
             "off twice; no fatigue break was recorded."},
    {"id": "B16", "stratum": "barrier", "rule": "work_authorisation",
     "text": "Scaffold modification continued three days after the work permit "
             "had expired; no extension was raised."},
    {"id": "B17", "stratum": "barrier", "rule": "bypassing_safety_controls",
     "text": "Operators silenced the H2S detector alarm at the manifold to stop "
             "the repeated nuisance trips."},
    {"id": "B18", "stratum": "barrier", "rule": "energy_isolation",
     "text": "The electrical isolation for the heat-tracing repair was never "
             "proved dead with a tester before work started."},

    # --- benign / administrative (12): measured strong spot (0 false flags
    # --- across the orchestrator's 16-case benign set).
    {"id": "G1", "stratum": "benign", "rule": None,
     "text": "Contractor name spelling corrected on the gate pass register after "
             "the audit comment."},
    {"id": "G2", "stratum": "benign", "rule": None,
     "text": "Toolbox talk held for the day shift reminding the crew about "
             "safety glasses."},
    {"id": "G3", "stratum": "benign", "rule": None,
     "text": "The pickup at base camp reported a dented bumper after the gravel "
             "road trip."},
    {"id": "G4", "stratum": "benign", "rule": None,
     "text": "Fire and safety training completed for 34 contract workers at the "
             "training centre."},
    {"id": "G5", "stratum": "benign", "rule": None,
     "text": "Housekeeping walkover of the laydown area found no open findings."},
    {"id": "G6", "stratum": "benign", "rule": None,
     "text": "Monthly extinguisher inspection completed on schedule; all tags "
             "current."},
    {"id": "G7", "stratum": "benign", "rule": None,
     "text": "Positive observation: the scaffolder wore his harness and "
             "double-lanyard correctly all shift."},
    {"id": "G8", "stratum": "benign", "rule": None,
     "text": "Fire drill completed at the GGS on Tuesday; muster recorded within "
             "four minutes."},
    {"id": "G9", "stratum": "benign", "rule": None,
     "text": "Safety meeting minutes circulated covering the revised journey "
             "management plan."},
    {"id": "G10", "stratum": "benign", "rule": None,
     "text": "JSA review for the pigging job signed by all participants before "
             "the pre-job."},
    {"id": "G11", "stratum": "benign", "rule": None,
     "text": "New PPE stock distributed; sizes recorded in the store register."},
    {"id": "G12", "stratum": "benign", "rule": None,
     "text": "Vehicle inspection completed for the crew bus before the morning "
             "run."},

    # --- paraphrase groups (12): same scenario, surface variants only.
    # --- Reproduces probe Result 3 (verdict flips under paraphrase); the
    # --- baseline freezes today's per-variant verdicts, so any fix that
    # --- changes the instability signature is visible.
    {"id": "P1", "stratum": "paraphrase", "rule": "confined_space",
     "text": "Entry was made into the crude oil storage tank for cleaning without "
             "a gas test; isolations were unverified and no standby man was posted."},
    {"id": "P2", "stratum": "paraphrase", "rule": "confined_space",
     "text": "A worker entered the crude oil tank to clean it without conducting "
             "a gas test or verifying the isolation."},
    {"id": "P3", "stratum": "paraphrase", "rule": "confined_space",
     "text": "Confined space entry into the storage tank was performed without "
             "atmospheric testing; the isolation status was unknown."},
    {"id": "P4", "stratum": "paraphrase", "rule": "confined_space",
     "text": "Cleaning crews went inside the crude storage tank even though "
             "nobody had tested the atmosphere."},
    {"id": "P5", "stratum": "paraphrase", "rule": "energy_isolation",
     "text": "The pump was still running when the maintenance team replaced the "
             "discharge valve; LOTO was not applied."},
    {"id": "P6", "stratum": "paraphrase", "rule": "energy_isolation",
     "text": "Valve replacement on the running pump went ahead with the motor "
             "never isolated or locked out."},
    {"id": "P7", "stratum": "paraphrase", "rule": "energy_isolation",
     "text": "The crew replaced the valve while the pump was energised; lock-out "
             "tag-out was skipped."},
    {"id": "P8", "stratum": "paraphrase", "rule": "energy_isolation",
     "text": "Without isolating the motor, the technician swapped the pump "
             "discharge valve during operation."},
    {"id": "P9", "stratum": "paraphrase", "rule": "line_of_fire",
     "text": "Fortunately no injury occurred, but the crew recognised the "
             "exposure when the fitting let go during the pressure test."},
    {"id": "P10", "stratum": "paraphrase", "rule": "line_of_fire",
     "text": "Nobody was hurt when the plug blew out of the test manifold; the "
             "area had been cleared beforehand."},
    {"id": "P11", "stratum": "paraphrase", "rule": "line_of_fire",
     "text": "The pressure test fitting failed and flew across the bay; luckily "
             "the test crew had already stepped behind the barrier."},
    {"id": "P12", "stratum": "paraphrase", "rule": "line_of_fire",
     "text": "A fitting let go during the pressure test with no one in the line "
             "of fire; the crew reviewed the anchorage after the event."},
]

PARAPHRASE_GROUPS: dict[str, tuple[str, ...]] = {
    "tank_entry_no_gas_test": ("P1", "P2", "P3", "P4"),
    "loto_omitted_running_pump": ("P5", "P6", "P7", "P8"),
    "near_miss_register": ("P9", "P10", "P11", "P12"),
}

# IOGP rules the barrier stratum must cover (9 = 7 learnable + 2 declared
# out-of-scope; out-of-scope rules are part of the PS ask, so they are
# measured, never skipped).
ALL_RULES = (
    "confined_space", "driving", "energy_isolation", "hot_work", "line_of_fire",
    "safe_mechanical_lifting", "working_at_height", "work_authorisation",
    "bypassing_safety_controls",
)


class _EmptyIndexStorage:
    """Stub storage for run_gates: no near-dup index rows, no session rows.
    near_dup therefore reports its stable 'index empty' badge; every other
    gate is index-free production code."""

    def nearest_base_batch(self, vecs):  # noqa: ANN001
        return [None] * len(vecs)

    def nearest_session(self, vec):  # noqa: ANN001
        return None


def load_classifier() -> Classifier:
    return build_classifier(DEFAULT_MODEL, "mock-0.1.0")


def observe(clf: Classifier, text: str) -> dict:
    """One observation on the canonical single-text path (classify route
    minus the near-dup index): predict -> validate spans -> run gates."""
    pred = clf.predict(text)
    pred.evidence_spans = validate_spans(text, pred.evidence_spans)
    assert all(text[span.start:span.end] == span.text for span in pred.evidence_spans), (
        "validate_spans must retain only spans matching text[start:end]"
    )
    cfg = Settings()
    gates = run_gates(
        text, pred.sif_score, _EmptyIndexStorage(), cfg,
        vec=pseudo_embed(text),
        well_control=pred.well_control,
        flag_thr=flag_threshold(clf),
        chunked=pred.chunked,
        verdict_stability=pred.verdict_stability,
        n_variants=pred.n_variants,
    )
    return {
        "score": pred.sif_score,
        "band": band_for(pred.sif_score, flag_threshold(clf), cfg.gray_band_low),
        "well_control": pred.well_control,
        "gray": sorted(g.name for g in gates if g.triggered and g.action == "gray"),
        "badge": sorted(g.name for g in gates if g.triggered and g.action == "badge"),
        "rule_probs": pred.rule_probs,
    }


def run_suite(clf: Classifier, update: bool = False) -> tuple[bool, str]:
    """Returns (ok, summary). Compares every case against the baseline and
    checks within-run determinism. Creates the baseline when absent."""
    thr = flag_threshold(clf)
    current: dict = {}
    problems: list[str] = []
    nondeterministic: list[str] = []

    for case in CASES:
        first = observe(clf, case["text"])
        second = observe(clf, case["text"])
        for key in ("score", "band", "well_control"):
            if first[key] != second[key]:
                nondeterministic.append(f"{case['id']}.{key} {first[key]!r} != {second[key]!r}")
        if first["gray"] != second["gray"] or first["badge"] != second["badge"]:
            nondeterministic.append(f"{case['id']} gate sets differ between runs")
        current[case["id"]] = {
            "score": first["score"], "band": first["band"],
            "well_control": first["well_control"],
            "gray": first["gray"], "badge": first["badge"],
        }

    if not BASELINE_PATH.exists():
        BASELINE_PATH.write_text(json.dumps({
            "note": "Frozen 2026-09-27 on masked-v2 int8 after barrier-gate expansion. "
                    "Labels are expert-judgement seeds from "
                    "docs/discovery/60-orchestrator-novel-probe.md, not human gold.",
            "model_version": clf.model_version,
            "classifier": type(clf).__name__,
            "flag_threshold": thr,
            "cases": current,
        }, indent=1, ensure_ascii=False))
        msg = (f"BASELINE CREATED at {BASELINE_PATH} ({len(CASES)} cases, "
               f"{clf.model_version}) — re-run to verify stability.")
        print(msg)
        return True, msg

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    was_real = baseline["classifier"] == "RealOnnxClassifier"
    if was_real and isinstance(clf, MockClassifier):
        problems.append(
            "baseline was frozen on the real ONNX artifact but no artifact/tokenizer "
            "loads now (MockClassifier) — the regression gate cannot protect anything "
            "in this state."
        )
    if baseline["classifier"] != type(clf).__name__ and not problems:
        problems.append(
            f"classifier changed: baseline {baseline['classifier']} vs now {type(clf).__name__}"
        )
    if baseline.get("model_version") != clf.model_version:
        print(f"NOTE: model_version changed: {baseline['model_version']} -> {clf.model_version} "
              "(intentional model updates must re-freeze with --update)")

    drifted = []
    for case in CASES:
        now = current[case["id"]]
        was = baseline["cases"].get(case["id"])
        if was is None:
            problems.append(f"{case['id']}: missing from baseline (add with --update)")
            continue
        if abs(now["score"] - was["score"]) > 1e-3:
            drifted.append(f"{case['id']} score {was['score']} -> {now['score']}")
        if now["band"] != was["band"]:
            drifted.append(f"{case['id']} band {was['band']} -> {now['band']}")
        if now["well_control"] != was["well_control"]:
            drifted.append(f"{case['id']} well_control {was['well_control']} -> {now['well_control']}")
        if now["gray"] != was["gray"]:
            drifted.append(f"{case['id']} gray gates {was['gray']} -> {now['gray']}")
        if now["badge"] != was["badge"]:
            drifted.append(f"{case['id']} badge gates {was['badge']} -> {now['badge']}")

    if nondeterministic:
        problems.append(f"{len(nondeterministic)} non-deterministic observation(s): "
                        + "; ".join(nondeterministic[:5]))
    if drifted:
        problems.append(f"{len(drifted)} golden drift(s) vs baseline: " + "; ".join(drifted))

    header = (f"golden regression: {len(CASES)} cases | classifier {clf.model_version} | "
              f"flag threshold {thr:.4f}")
    print(header)
    for case in CASES:
        cur = current[case["id"]]
        marks = "".join(
            f"{'G' if g in cur['gray'] else '.'}" for g in
            ("min_length", "negation", "language", "confidence", "drill",
             "long_input", "well_control_watch", "chunked_low_score", "severity_watch",
             "energy_isolation_absent", "gas_test_absent", "permit_absent",
             "fire_watch_absent", "standby_absent", "atmosphere_unmonitored",
             "verdict_stability", "fall_protection_absent"))
        print(f"  {case['id']:>4} {case['stratum']:<10} {case['rule'] or '-':<26} "
              f"score={cur['score']:.4f} {cur['band']:<8} gates[{marks}]")
    if problems:
        for p in problems:
            print("  FAIL:", p)
        return False, "; ".join(problems)
    print(f"  PASS: stable vs baseline ({BASELINE_PATH.name}) and deterministic within run")
    return True, "stable"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--update", action="store_true",
                    help="(re)freeze tests/golden_baseline.json from this run")
    args = ap.parse_args()

    clf = load_classifier()
    if isinstance(clf, MockClassifier):
        print(f"WARNING: no ONNX artifact at {DEFAULT_MODEL} — running against the "
              "deterministic MockClassifier. Freeze/update only with intent.")
    if args.update:
        BASELINE_PATH.unlink(missing_ok=True)
    ok, _ = run_suite(clf, update=args.update)
    return 0 if ok else 1


def test_golden_set_stable() -> None:
    """pytest wrapper for the golden comparison. PASS semantics:
    (a) baseline exists and every case matches it, or
    (b) the baseline was just created (bootstrap run) — the NEXT run is the
    real verification, so this never reads as behavioural approval."""
    clf = load_classifier()
    ok, summary = run_suite(clf)
    assert ok, "golden regression drifted: " + summary


if __name__ == "__main__":
    sys.exit(main())
