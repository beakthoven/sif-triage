"""Barrier-failure gate family tests (D3 fix, 2026-09-25).

Gate-level (no server, no model): each of the seven barrier gates must fire on
explicit ABSENCE language adjacent to its control term or a targeted absence
sequence, must stay silent on the positive statement, and all seven must stay
silent on the benign probes. Triggered states are action="gray" — never
auto-cleared.

Run: .venv/bin/python tests/test_barrier_gates.py   (also works under pytest)
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.gates import gate_barrier_absence  # noqa: E402

BARRIER_NAMES = (
    "energy_isolation_absent",
    "gas_test_absent",
    "permit_absent",
    "fire_watch_absent",
    "standby_absent",
    "atmosphere_unmonitored",
    "fall_protection_absent",
)

# text -> gate names expected to fire
POSITIVE_ABSENCE: list[tuple[str, tuple[str, ...]]] = [
    ("LOTO not applied on the running pump.", ("energy_isolation_absent",)),
    ("Isolation was not verified before the valve was opened.",
     ("energy_isolation_absent",)),
    ("Lockout/tagout never applied during the filter change.",
     ("energy_isolation_absent",)),
    ("De-energisation not confirmed before work started on the panel.",
     ("energy_isolation_absent",)),
    ("The pump was worked on while energised; nobody confirmed the breaker was locked out before the flange was cracked.",
     ("energy_isolation_absent",)),
    ("The electrical isolation for the heat-tracing repair was never proved dead with a tester before work started.",
     ("energy_isolation_absent",)),
    ("No gas test was conducted before tank entry.", ("gas_test_absent",)),
    ("Gas detector absent at the manway.", ("gas_test_absent",)),
    ("Atmospheric testing was never performed inside the vessel.",
     ("gas_test_absent",)),
    ("Atmosphere was not tested before tank entry.", ("gas_test_absent",)),
    ("Atmosphere was not tested for gas before entry.",
     ("gas_test_absent",)),
    ("No gas reading taken before tank entry.", ("gas_test_absent",)),
    ("The atmosphere was unchecked before confined-space entry.",
     ("gas_test_absent",)),
    ("The atmosphere was unchecked during vessel entry.",
     ("gas_test_absent",)),
    ("No permit to work was raised for the hot job.",
     ("permit_absent",)),
    ("PTW not raised before opening the line.", ("permit_absent",)),
    ("Work permit never issued for the night shift.",
     ("permit_absent",)),
    ("Hot tapping on the produced water line began before the permit to work was signed by the area authority.",
     ("permit_absent",)),
    ("Rope access started before anyone confirmed the second anchorage.",
     ("fall_protection_absent",)),
    ("No full-body harness or fall-arrest device was available for the roof work.",
     ("fall_protection_absent",)),
    ("Fire watch absent during welding on the tank roof.",
     ("fire_watch_absent",)),
    ("The fire watch had left the area when sparks started.",
     ("fire_watch_absent",)),
    ("Fire watch gone home before the grind was finished.",
     ("fire_watch_absent",)),
    ("No standby man was posted at the vessel.", ("standby_absent",)),
    ("Hole watch missing during the entry.", ("standby_absent",)),
    ("Standby attendant never assigned for the confined-space job.",
     ("standby_absent",)),
    ("Nobody was posted as a lookout at the vessel.", ("standby_absent",)),
    ("No one was assigned as a spotter for the lift.", ("standby_absent",)),
    ("No sentinel was assigned to the entry team.", ("standby_absent",)),
    ("The entry continued with the standby post unattended.",
     ("standby_absent",)),
    ("The water bowser reversed; the banksman was unavailable.",
     ("standby_absent",)),
    ("Purging in progress while two men were inside the vessel.",
     ("atmosphere_unmonitored",)),
    ("Nitrogen purge underway during the cleaning.",
     ("atmosphere_unmonitored",)),
    ("No monitoring during vessel entry.", ("atmosphere_unmonitored",)),
]

# positive / negation-resolved statements that must NOT fire any barrier gate
POSITIVE_STATEMENTS: list[str] = [
    "LOTO applied and verified before work started.",
    "Isolations verified zero energy, locks and tags in place.",
    "Gas test conducted before entry; readings normal.",
    "Gas detector calibrated and used at the manway.",
    "Atmospheric testing performed and logged before entry.",
    "Permit to work raised and signed by the area authority.",
    "PTW raised with gas test results attached.",
    "Fire watch posted with extinguisher for the hot job.",
    "Standby man posted at the vessel for the whole entry.",
    "Hole watch in position and atmosphere monitored continuously.",
    "Atmosphere was monitored throughout the entry.",
    "A banksman was posted and in constant contact.",
    "A spotter was assigned and positioned at the lift area.",
    "A lookout was posted throughout the entry.",
    "The confined-space entry had a sentinel posted at the manway.",
    "The standby post was attended for the full job.",
    "Atmosphere checked and a gas reading taken before entry.",
    "Gas was tested before tank entry and the reading was logged.",
    "Nitrogen purge completed before the crew entered.",
    "The crew used the full-body harness and double lanyard, tied off to the certified anchorage before access.",
    "The lifeline and rope grab were inspected and secured before the rope-access task.",
    "Rope access began after the second anchorage was confirmed and the rope grab was fitted.",
    "The permit to work was signed before hot tapping commenced.",
    "Purge completed before entry; no entry was made during the purge.",
]

BENIGN_PROBES: list[str] = [
    "Housekeeping round completed across the well pad; work areas left tidy.",
    "Fire extinguisher inspection completed; all units within test date.",
    "Toolbox talk held on safety glasses and hand protection before the shift.",
    "Fire drill conducted at the processing plant; evacuation finished in 4 minutes.",
]


def fired(text: str) -> set[str]:
    return {n for n in BARRIER_NAMES if gate_barrier_absence(text, n).triggered}


def test_positive_absence_forms_fire():
    for text, expected in POSITIVE_ABSENCE:
        got = fired(text)
        assert got == set(expected), f"{text!r}: expected {set(expected)}, got {got}"


def test_positive_statements_do_not_fire():
    for text in POSITIVE_STATEMENTS:
        got = fired(text)
        assert not got, f"{text!r} must not fire barrier gates, got {got}"


def test_benign_probes_fire_zero_barrier_gates():
    for text in BENIGN_PROBES:
        got = fired(text)
        assert not got, f"benign probe fired {got}: {text!r}"


def test_driving_bypass_and_inspection_tag_families_remain_out_of_scope():
    for text in (
        "The crane crew used worn slings with no inspection tag.",
        "The driver exceeded the site speed limit and skipped a fatigue break.",
        "The panel technician bypassed the vibration trip.",
    ):
        assert not fired(text), f"documented out-of-scope text fired: {text!r}"


def test_triggered_states_are_gray():
    for text, _ in POSITIVE_ABSENCE:
        for n in BARRIER_NAMES:
            g = gate_barrier_absence(text, n)
            if g.triggered:
                assert g.action == "gray", f"{n} triggered with action={g.action!r}"


if __name__ == "__main__":
    failures = 0
    for fn in (test_positive_absence_forms_fire, test_positive_statements_do_not_fire,
               test_benign_probes_fire_zero_barrier_gates,
               test_driving_bypass_and_inspection_tag_families_remain_out_of_scope,
               test_triggered_states_are_gray):
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print("barrier-gate suite:", "PASS" if not failures else f"{failures} FAILURES")
    sys.exit(1 if failures else 0)
