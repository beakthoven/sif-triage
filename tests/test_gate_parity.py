"""Gate-parity guard (Workstream S/B0): tests/adversarial_suite.py's GATE_ORDER
must never drift from run_gates' dispatch table. The suite now DERIVES
GATE_ORDER from run_gates itself; this module re-derives the names
INDEPENDENTLY (fresh call, own fakes — deliberately NOT importing the suite's
helper, so a broken derivation cannot vouch for itself) and fails if the two
ever diverge.

Run: .venv/bin/python tests/test_gate_parity.py
     (or: pytest tests/test_gate_parity.py)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.config import Settings  # noqa: E402
from app.gates import gate_verdict_stability, run_gates  # noqa: E402

import tests.adversarial_suite as adv  # noqa: E402


class _EmptyIndex:
    """Storage stand-in with an empty near-dup index (both tiers miss)."""

    def nearest_base_batch(self, _vecs):
        return [(None, 0.0)]

    def nearest_session(self, _vec):
        return None


def run_gates_names() -> list[str]:
    # vec/base_hit dummies keep gate_near_dup off the embedder; any gate that
    # still raises is caught inside run_gates and keeps its spec name, so the
    # returned names are exactly the dispatch table.
    states = run_gates(
        "gate parity probe", 0.5, _EmptyIndex(), Settings(),
        vec=[0.0], base_hit=(None, 0.0),
    )
    return [s.name for s in states]


def test_gate_order_matches_run_gates() -> None:
    assert list(adv.GATE_ORDER) == run_gates_names(), (
        f"adversarial suite GATE_ORDER {list(adv.GATE_ORDER)} != "
        f"run_gates dispatch {run_gates_names()}"
    )


def test_verdict_stability_threshold_and_order() -> None:
    assert not gate_verdict_stability(0.50, 1).triggered
    assert not gate_verdict_stability(0.75, 4).triggered
    unstable = gate_verdict_stability(0.50, 4)
    assert unstable.triggered and unstable.action == "gray"
    assert "2 of 4 variants disagree (stability 0.50)" in unstable.detail
    assert run_gates_names()[-2:] == ["verdict_stability", "fall_protection_absent"]


def test_fall_protection_gate_parity_and_behavior() -> None:
    states = run_gates(
        "No harness was available for the roof work.", 0.2, _EmptyIndex(), Settings(),
        vec=[0.0], base_hit=(None, 0.0),
    )
    state = next(s for s in states if s.name == "fall_protection_absent")
    assert state.triggered and state.action == "gray"
    assert "fall protection control" in state.detail
    clean = run_gates(
        "Harness anchored and lifeline secured before access.", 0.2,
        _EmptyIndex(), Settings(), vec=[0.0], base_hit=(None, 0.0),
    )
    assert not next(s for s in clean if s.name == "fall_protection_absent").triggered


def test_suite_expects_only_real_gates() -> None:
    names = set(run_gates_names())
    src = Path(adv.__file__).read_text(encoding="utf-8")
    referenced = set(re.findall(r'g\["([a-z_]+)"\]', src))
    missing = referenced - names
    assert not missing, (
        f"suite expectations reference unknown gates: {sorted(missing)}"
    )


def test_gate_order_is_derived_not_hand_kept() -> None:
    src = Path(adv.__file__).read_text(encoding="utf-8")
    assert not re.search(r"GATE_ORDER\s*=\s*[\[(]", src), (
        "GATE_ORDER must be derived from run_gates, not a hand-kept list"
    )


if __name__ == "__main__":
    test_gate_order_matches_run_gates()
    test_verdict_stability_threshold_and_order()
    test_fall_protection_gate_parity_and_behavior()
    test_suite_expects_only_real_gates()
    test_gate_order_is_derived_not_hand_kept()
    names = run_gates_names()
    print(f"GATE PARITY PASS — suite GATE_ORDER == run_gates dispatch "
          f"({len(names)} gates: {', '.join(names)})")
