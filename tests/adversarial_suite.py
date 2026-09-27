"""Adversarial suite — 18 hostile inputs vs the input gates + API contract.

Runnable stdlib script (urllib only, no pytest). Spawns uvicorn on :8177
(override with SIF_TEST_PORT when the demo server owns :8177) against a
throwaway DB, seeds the near-dup index with a training row and a
synthetic row, then fires all 15 adversarial inputs from
runs/run2/phase1-architecture/demo-red-teamer.md (§B.3 #1-10 + the 5 new
attacks) plus 2 B1 regressions (2026-09-08 e2e: the negation gate grayed the
demo hero text on 'without'~'fire' / 'could'~'fire') plus the final-audit
probe (novel well-control narrative -> watch-gate gray) at /api/classify and
asserts each produces the expected gate state / no crash / valid schema.
Exit code 0 = pass.

Run: .venv/bin/python tests/adversarial_suite.py
     SIF_MODEL_PATH=artifacts/models/masked-v2/sif_multitask_int8.onnx SIF_TEST_PORT=8238 .venv/bin/python tests/adversarial_suite.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.config import Settings  # noqa: E402
from app.gates import run_gates  # noqa: E402
from app.schemas import PredictionOut  # noqa: E402

PORT = int(os.environ.get("SIF_TEST_PORT", "8177"))  # override when the demo server owns :8177
BASE = f"http://127.0.0.1:{PORT}/api"

# Near-dup index seeds: one OSHA-train-style row, one synthetic-corpus-style
# row. The runtime index must include both (ARCHITECTURE: "near-dup index
# INCLUDES the synthetic corpus") so verbatim re-pastes surface the banner.
SEED_TRAIN = (
    "Employee was struck by a falling pipe wrench while working on the rig "
    "floor and sustained a fractured wrist requiring hospitalization."
)
SEED_SYNTH = (
    "During pigging operations at the GGS, a technician opened the receiver "
    "door before full depressurization; the door swung and narrowly missed "
    "his face."
)

LONG_REPORT = (
    "Crew continued routine maintenance on the separator unit during the "
    "morning shift. " * 160  # 1920 words — the §B.3 #5 length-OOD case
)

# B1 regression fixtures (2026-09-08 e2e): the old NegEx fired on negation
# cues near ANY mechanism term, graying the demo hero text via
# 'without'~'fire', 'without'~'fell', 'could'~'fire'. "Without fire watch" is
# an absent-barrier SIGNAL; "could have been" is the near-miss register.
HERO_WELD = (
    "During hot work at the well pad, a worker was grinding near live "
    "flowline without fire watch; sparks fell near the flange. Could have "
    "been a major fire."
)

# final_audit_qa.md probe 1 — a NOVEL Baghjan-class well-control precursor,
# verbatim the auditor's text (not in any corpus). The neural model scored it
# 0.033 LOW while the deterministic WC tag fired: a judge pasting their own
# well-control narrative would see green next to demo cards at 0.9+. The
# well-control watch gate routes this class to human review instead.
WC_PROBE = (
    "During well servicing operations at well NHK-619, the crew observed mud "
    "gains of about three barrels at the active pit while tripping out. The "
    "well started flowing during connections. The driller shut in the BOP and "
    "the well was brought under control by bullheading kill-weight mud. "
    "No injury and no spill occurred."
)

# (id, label, text, expectation fn(gates: dict[str, GateState-like], pred) -> None)
# Every case also gets the universal checks: HTTP 200, PredictionOut schema
# parses, spans satisfy text[start:end]==span.text, no gate errored to gray.
CASES: list[dict] = [
    {
        "id": 1, "src": "B.3-1", "label": "negated fall ('No injury occurred')",
        "text": "Worker fell 4m from scaffold. No injury occurred.",
        "expect": lambda g, p: _req(
            g["negation"].triggered and g["negation"].action == "gray",
            "negation gate forces gray review"),
    },
    {
        "id": 2, "src": "B.3-2", "label": "sarcasm (gray or clean LOW)",
        "text": "Fantastic, another leak nobody reported for two shifts, "
                "truly outstanding vigilance at the site.",
        # The ensemble mean may sit in the confidence band or be a clean LOW;
        # a false HIGH is the only unacceptable outcome.
        "expect": lambda g, p: _req(
            (g["confidence"].triggered and g["confidence"].action == "gray")
            or (p.sif_score < 0.40
                and not any(gs.triggered and gs.action == "gray" for gs in g.values())),
            f"sarcasm -> confidence gray or clean LOW; score={p.sif_score}"),
    },
    {
        "id": 3, "src": "B.3-3", "label": "romanized Hinglish (known PARTIAL — no crash)",
        "text": "Worker height par kaam kar raha tha bina harness ke, "
                "achanak gir gaya par kuch nahi hua, sab theek hai.",
        # ASCII Hinglish legitimately slips the ASCII-ratio language gate;
        # red-teamer PARTIAL is handled by precomputed translation, not a gate.
        "expect": lambda g, p: _req(
            not g["language"].triggered,
            "language gate not fooled either way (documented PARTIAL)"),
    },
    {
        "id": 4, "src": "B.3-4", "label": "'Forklift incident.' (18 chars)",
        "text": "Forklift incident.",
        "expect": lambda g, p: _req(
            g["min_length"].triggered and g["min_length"].action == "gray",
            "min-length gray: too short to assess"),
    },
    {
        "id": 5, "src": "B.3-5", "label": "2000-word report (length-OOD)",
        "text": LONG_REPORT,
        "expect": lambda g, p: (
            _req(g["long_input"].triggered and g["long_input"].action == "badge",
                 "long-input 'chunked' badge fires"),
            _req("chunked" in g["long_input"].detail, "badge says 'chunked'"),
            _req(g["long_input"].action != "gray", "long input is a badge, never gray"),
        ),
    },
    {
        "id": 6, "src": "B.3-6", "label": "Deepwater Horizon narrative",
        "text": "Deepwater Horizon Macondo well: crew could not kill the well "
                "after the blowout; the BOP failed to shear the pipe and the "
                "rig was lost.",
        "expect": lambda g, p: (
            _req(g["negation"].triggered and g["negation"].action == "gray",
                 "negation gray on 'could not kill the well'"),
            _req(p.well_control, "well-control tag on blowout/BOP language"),
        ),
    },
    {
        "id": 7, "src": "B.3-7", "label": "all-9-rules report (no gray expected)",
        "text": "PTW closed and verified; bypassed alarm restored; harness "
                "anchored at height; LOTO applied and verified; hot work with "
                "fire watch; crane lift with certified rigging; confined space "
                "entry with gas test; forklift route segregated; seat belts "
                "worn on the journey.",
        # Dense hazard vocabulary with controls explicitly present and no event.
        # Confidence or stability gray is acceptable; absence gates must stay silent.
        "expect": lambda g, p: _req(
            (not any(gs.triggered and gs.action == "gray" for name, gs in g.items()
                     if name != "verdict_stability"))
            if IS_MOCK else
            (p.sif_score < 0.6581
             and not any(gs.triggered and gs.action == "gray"
                         and gs.name not in ("confidence", "verdict_stability")
                         for gs in g.values())),
            f"clean full-rules report: no flag, no unexpected gray (score={p.sif_score})"),
    },
    {
        "id": 8, "src": "B.3-8", "label": "'Fire drill completed' (5th gate)",
        "text": "Fire drill completed",
        "expect": lambda g, p: _req(
            g["drill"].triggered and g["drill"].action == "gray",
            "drill filter forces gray, never auto-green"),
    },
    {
        "id": 9, "src": "B.3-9", "label": "verbatim training row re-paste",
        "text": SEED_TRAIN,
        "expect": lambda g, p: _req(
            g["near_dup"].triggered and g["near_dup"].action == "badge",
            f"near-dup banner fires ({g['near_dup'].detail})"),
    },
    {
        "id": 10, "src": "B.3-10", "label": "garbage symbols",
        "text": "?!?! ..,,;; ??",
        "expect": lambda g, p: _req(
            g["min_length"].triggered and g["min_length"].action == "gray",
            "garbage -> min-length gray"),
    },
    {
        "id": 11, "src": "new-a", "label": "Baghjan blowout narrative",
        "text": "Baghjan well blowout during workover: gas migration observed, "
                "BOP pulled before cement set, WOC only 12 hours, H2S released "
                "at the wellhead.",
        "expect": lambda g, p: _req(
            p.well_control, "well-control tag on Baghjan-class language"),
    },
    {
        "id": 12, "src": "new-b", "label": "Assamese script (unsupported language)",
        "text": "শ্রমিকজনে হাৰ্নেছ নপিন্ধাকৈ উচ্চতাত কাম কৰি আছিল আৰু হঠাৎ গ্যাচ ওলাবলৈ আৰম্ভ কৰিলে।",
        "expect": lambda g, p: _req(
            g["language"].triggered and g["language"].action == "gray",
            f"language gray+badge on non-ASCII ({g['language'].detail})"),
    },
    {
        "id": 13, "src": "new-c", "label": "codes-only 'LOTO not applied' (16 chars)",
        "text": "LOTO not applied",
        "expect": lambda g, p: (
            _req(not g["min_length"].triggered,
                 "min-length must NOT eat a codes-heavy terse report"),
            _req("codes path" in g["min_length"].detail,
                 f"accepted via codes path ({g['min_length'].detail})"),
            _req(not g["negation"].triggered,
                 "negation must NOT gray an absent-barrier code report (B1)"),
            # EI >= 0.35 is the mock's keyword-anchor nudge; the real model
            # reads a bare 16-char code as low-confidence (D22, rule bars
            # are probabilities, never "the rule").
            _req(not IS_MOCK or p.rule_probs["energy_isolation"] >= 0.35,
                 "energy-isolation keyword tag attached (mock anchor behavior)"),
        ),
    },
    {
        "id": 14, "src": "new-d", "label": "synthetic training row verbatim",
        "text": SEED_SYNTH,
        "expect": lambda g, p: _req(
            g["near_dup"].triggered and g["near_dup"].action == "badge",
            f"near-dup banner fires on synthetic row ({g['near_dup'].detail})"),
    },
    {
        "id": 15, "src": "new-e", "label": "first-aid non-SIF (stability may route)",
        "text": "Worker received first aid for a small superficial cut on the "
                "finger while opening a toolbox; cleaned, dressed, and "
                "returned to normal duties.",
        "expect": lambda g, p: (
            _req(p.sif_score < 0.5, f"green triage (score={p.sif_score})"),
            _req(not any(gs.triggered and gs.action == "gray"
                         for name, gs in g.items() if name != "verdict_stability"),
                 "no content-based gray gate on a clean first-aid case"),
        ),
    },
    {
        "id": 16, "src": "B1-fix", "label": "hero weld report (absent barrier + counterfactual)",
        # The 90-second demo's opening paste. 'without fire watch' = missing
        # barrier (the SIGNAL), 'could have been a major fire' = near-miss
        # register. Neither is an outcome negation — the card must score.
        "text": HERO_WELD,
        "expect": lambda g, p: (
            _req(not g["negation"].triggered,
                 f"'without fire watch'/'could have been' must NOT gray "
                 f"({g['negation'].detail})"),
            # 2026-09-26: the barrier gate family (the D3 fix) made 'without
            # fire watch' a DETECTED absent-barrier signal — graying here is
            # the product working, not a negation false positive (the B1
            # comment above says exactly this). Contract now: the card still
            # scores, and the ONLY gray is the true barrier, never negation.
            _req(g["fire_watch_absent"].triggered
                 and g["fire_watch_absent"].action == "gray",
                 f"'without fire watch' must route via fire_watch_absent "
                 f"({g['fire_watch_absent'].detail})"),
            _req(all(not (gs.triggered and gs.action == "gray")
                     for name, gs in g.items()
                     if name not in ("fire_watch_absent", "verdict_stability")),
                 "no gray gate other than the true fire_watch_absent barrier or a genuine stability concern"),
            # hot_work-on-top is the mock's anchor ranking; the real model's
            # dominant bar is Line of Fire here — accepted per D22 (the UI
            # narrates the probability bar, never "the rule"). The real-model
            # contract: a dominant bar renders.
            _req((p.rule_probs["hot_work"] == max(p.rule_probs.values()))
                 if IS_MOCK else max(p.rule_probs.values()) >= 0.5,
                 "hot_work leads (mock) / a dominant rule bar renders (real)"),
        ),
    },
    {
        "id": 17, "src": "B1-fix", "label": "absence of exposure ('no one was in the area')",
        # Near-miss absence-of-exposure: GREEN-leaning, gray is for genuine
        # ambiguity. Asserts the negation gate only — the mock score here
        # (0.52) sits inside the confidence gray band by sha256 seed, an
        # orthogonal intended behavior.
        "text": "no one was in the area when the pipe fell",
        "expect": lambda g, p: _req(
            not g["negation"].triggered,
            f"absence-of-exposure must NOT gray via negation ({g['negation'].detail})"),
    },
    {
        "id": 18, "src": "audit-P1", "label": "novel well-control precursor (judge's own Baghjan paste)",
        # The neural model misses novel WC narratives (masked-v2: 0.033); the
        # deterministic tag + watch gate are the safety net — gray review,
        # never a confident LOW. Threshold: mock 0.5, masked-v2 0.6581 (the
        # hardcoded tuned op, same convention as case 7).
        "text": WC_PROBE,
        "expect": lambda g, p: (
            _req(p.well_control, "well-control tag fires on novel WC narrative"),
            _req(p.sif_score < (0.5 if IS_MOCK else 0.6581),
                 f"neural score below flag threshold as diagnosed (score={p.sif_score})"),
            _req(g["well_control_watch"].triggered
                 and g["well_control_watch"].action == "gray",
                 "well-control watch routes the novel WC paste to human review (gray)"),
        ),
    },
]

def discover_gate_names() -> list[str]:
    """Gate names lifted from run_gates' own dispatch — never a hand-kept
    list (a 9-entry hand list drifted from the 10-gate run_gates and failed
    every case; tests/test_gate_parity.py now re-checks this independently).
    vec/base_hit are dummies so gate_near_dup never lazy-imports the
    embedder; a gate that still raises is caught inside run_gates and keeps
    its spec name, so the returned names are exactly the dispatch table."""
    class _EmptyIndex:
        def nearest_session(self, _vec): return None

    states = run_gates(
        "gate discovery probe", 0.5, _EmptyIndex(), Settings(),
        vec=[0.0], base_hit=(None, 0.0),
    )
    return [s.name for s in states]


GATE_ORDER = discover_gate_names()

# Set from /api/health in main(). Three expectations below were tuned to the
# mock's sha256-seeded Beta scores; the real model disposes of those inputs
# differently and D22 accepts rule-probability drift (narrate the probability
# bar, never "the rule"). Mock keeps the strict assertions; the real model
# gets the honest behavioral contract (demo_verification §5).
IS_MOCK = True

failures: list[str] = []


def _req(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(label)


def req(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class _Gate:
    """Light attribute view over a gate dict for readable expectations."""

    def __init__(self, d: dict) -> None:
        self.name = d["name"]
        self.triggered = bool(d["triggered"])
        self.action = d.get("action", "badge")
        self.detail = d.get("detail", "")


def run_case(case: dict) -> tuple[str, dict[str, _Gate] | None, str]:
    """Returns (verdict, gates, note). verdict in PASS/FAIL."""
    status, raw = req("POST", "/classify", {"text": case["text"]})
    if status != 200:
        return "FAIL", None, f"HTTP {status}: {raw}"
    try:
        pred = PredictionOut(**raw)
    except Exception as exc:
        return "FAIL", None, f"schema invalid: {exc}"
    gates = {g.name: _Gate(g.model_dump()) for g in pred.gate_states}
    try:
        if set(gates) != set(GATE_ORDER):
            raise AssertionError(f"gate set mismatch: {sorted(gates)}")
        for g in gates.values():
            if g.detail.startswith("gate error:"):
                raise AssertionError(f"{g.name} crashed: {g.detail}")
        for s in pred.evidence_spans:
            if case["text"][s.start:s.end] != s.text:
                raise AssertionError(f"span invariant violated: {s}")
        case["expect"](gates, pred)
    except AssertionError as exc:
        return "FAIL", gates, str(exc)
    return "PASS", gates, ""


def print_table(results: list[tuple[dict, str, dict[str, _Gate] | None, str]]) -> None:
    print("\n=== GATE TABLE (input x gate x outcome) ===")
    header = f"{'#':>2} {'case':<44} | " + " ".join(f"{g[:11]:>11}" for g in GATE_ORDER)
    print(header)
    print("-" * len(header))
    for case, verdict, gates, note in results:
        cells = []
        for name in GATE_ORDER:
            if gates is None:
                cells.append(f"{'?':>11}")
            else:
                g = gates[name]
                mark = g.action.upper() if g.triggered else "-"
                cells.append(f"{mark:>11}")
        print(f"{case['id']:>2} {case['label'][:44]:<44} | " + " ".join(cells))
        if verdict == "FAIL":
            print(f"   ^^ FAIL: {note}")


def main() -> int:
    tmp = tempfile.TemporaryDirectory(prefix="sif-adv-")
    env = dict(os.environ, SIF_DB_PATH=str(Path(tmp.name) / "adv.db"))
    model = REPO_ROOT / "artifacts" / "models" / "masked-v2" / "sif_multitask_int8.onnx"
    if model.is_file():
        env.setdefault("SIF_MODEL_PATH", str(model))
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=REPO_ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        health: dict = {}
        for _ in range(50):
            try:
                status, health = req("GET", "/health")
                if status == 200:
                    break
            except urllib.error.URLError:
                time.sleep(0.2)
        else:
            raise AssertionError(f"server did not come up on :{PORT}")

        global IS_MOCK
        IS_MOCK = health.get("classifier") == "MockClassifier"
        print(f"classifier under test: {health.get('classifier')} ({health.get('model_version')})")

        # Seed the near-dup index (training + synthetic corpus population).
        status, ing = req("POST", "/ingest", {
            "records": [{"text": SEED_TRAIN}, {"text": SEED_SYNTH}],
            "source": "adv_seed",
        })
        if status != 200 or ing.get("accepted") != 2:
            raise AssertionError(f"seed ingest failed: {status} {ing}")
        print("seeded near-dup index: 1 train-style + 1 synthetic-style row")

        results: list[tuple[dict, str, dict[str, _Gate] | None, str]] = []
        for case in CASES:
            verdict, gates, note = run_case(case)
            results.append((case, verdict, gates, note))
            print(f"  [{verdict}] #{case['id']:>2} {case['src']:<6} {case['label']}"
                  + (f" — {note}" if note else ""))
            if verdict == "FAIL":
                failures.append(f"#{case['id']} {case['label']}: {note}")

        # Empty text is a schema-level rejection (422 -> 'rejection toast'),
        # the other half of §B.3-10. It must not 500.
        status, body = req("POST", "/classify", {"text": ""})
        if status == 422:
            print("  [PASS] #10b B.3-10 empty text -> 422 rejection (schema-valid)")
        else:
            failures.append(f"#10b empty text: expected 422, got {status}: {body}")
            print(f"  [FAIL] #10b empty text: expected 422, got {status}")

        print_table(results)
        if failures:
            print(f"\nADVERSARIAL SUITE FAIL — {len(failures)} failure(s)")
            return 1
        print(f"\nADVERSARIAL SUITE PASS — {len(CASES)}/{len(CASES)} routed correctly, no crashes, schema valid")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=10)
        tmp.cleanup()


if __name__ == "__main__":
    sys.exit(main())
