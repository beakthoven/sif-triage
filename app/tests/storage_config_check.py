"""Storage-config wave check: the actions (CAPA) table CRUD and the
boot-time gate_states backfill contract. Run:
    .venv/bin/python -m app.tests.storage_config_check"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from app.gates import gate_verdict_stability
from app.main import GATE_SCHEMA_VERSION, _backfill_gate_states
from app.schemas import GateState, OverrideIn, PredictionOut, ReportIn
from app.storage import SCHEMA_VERSION, SQLiteStorage


def _mkstorage(tmp: Path) -> SQLiteStorage:
    tmp.mkdir(parents=True, exist_ok=True)
    return SQLiteStorage(tmp / "t.db")


def _seed_prediction(st: SQLiteStorage, text: str, gates: list[GateState],
                     stability: float = 1.0, n_variants: int = 1) -> int:
    rid = st.add_report(ReportIn(text=text, date="2021-06-15"))
    st.add_prediction(rid, PredictionOut(
        sif_score=0.42, rule_probs={}, well_control=False,
        evidence_spans=[], gate_states=gates, model_version="test",
        verdict_stability=stability, n_variants=n_variants,
    ))
    return rid


# a minimal v1-era snapshot: the classic gates, nothing appended after
_OLD_GATES = [
    GateState(name="min_length", triggered=False),
    GateState(name="negation", triggered=False),
    GateState(name="language", triggered=False),
    GateState(name="confidence", triggered=False),
    GateState(name="drill", triggered=False),
    GateState(name="near_dup", triggered=False),
    GateState(name="long_input", triggered=False),
]


def test_actions_table_and_crud(tmp: Path) -> None:
    st = _mkstorage(tmp / "a")
    ver = st._conn.execute("SELECT version FROM schema_meta WHERE id = 1").fetchone()[0]
    assert ver == SCHEMA_VERSION, (ver, SCHEMA_VERSION)
    ddl = st._conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='actions'").fetchone()[0]
    for col in ("id", "report_id", "override_id", "owner", "due_date", "status",
                "created_at", "updated_at"):
        assert col in ddl, (col, ddl)
    assert "UNIQUE" in ddl, ddl  # one CAPA row per decision, CapaStore semantics

    rid = st.add_report(ReportIn(text="rig floor hand crushed toe" * 3))
    ov_id = st.add_override(_override(rid))
    aid = st.add_action(rid, ov_id, "ravi.sharma", "2026-10-15", "open")
    got = st.get_action(aid)
    assert got == {
        "id": aid, "report_id": rid, "override_id": ov_id, "owner": "ravi.sharma",
        "due_date": "2026-10-15", "status": "open",
        "created_at": got["created_at"], "updated_at": got["updated_at"],
    }, got
    assert st.get_action_by_override(ov_id)["id"] == aid

    rid2 = st.add_report(ReportIn(text="frac tank vent corroded" * 3))
    ov2 = st.add_override(_override(rid2))
    st.add_action(rid2, ov2, "priya.das", None, "in_progress")
    assert [a["report_id"] for a in st.list_actions()] == [rid, rid2]
    assert [a["owner"] for a in st.list_actions(report_id=rid2)] == ["priya.das"]
    assert [a["owner"] for a in st.list_actions(override_id=ov2)] == ["priya.das"]

    before = st.get_action(aid)["updated_at"]
    assert st.update_action(aid, status="closed") is True
    up = st.get_action(aid)
    assert up["status"] == "closed" and up["owner"] == "ravi.sharma"  # partial update
    assert up["updated_at"] >= before
    assert st.update_action(aid, due_date="") is True and st.get_action(aid)["due_date"] == ""
    assert st.update_action(99999, status="closed") is False
    assert st.update_action(aid) is False  # no fields -> no-op, False

    # UNIQUE override_id: a second CAPA on the same decision must fail loudly
    try:
        st.add_action(rid, ov_id, "someone.else", None, "open")
        raise AssertionError("duplicate override_id accepted")
    except sqlite3.IntegrityError:
        pass
    # foreign_keys=ON: dangling report/override ids must fail loudly
    try:
        st.add_action(999999, ov_id, "x", None, "open")
        raise AssertionError("dangling report_id accepted")
    except sqlite3.IntegrityError:
        pass

    assert st.delete_action(aid) is True and st.get_action(aid) is None
    assert st.delete_action(aid) is False
    st.close()


def _override(rid: int) -> OverrideIn:
    return OverrideIn(report_id=rid, field="sif_label", new_value="not_sif_potential")


def test_gate_backfill_rewrite(tmp: Path) -> None:
    st = _mkstorage(tmp / "b")
    rid = _seed_prediction(st, "worker fell from unguarded height, no harness fitted", _OLD_GATES,
                           stability=0.5, n_variants=4)
    writes_before = st._writes_version

    def mapper(existing, text, score, well_control, stability, n_variants):
        assert stability == 0.5 and n_variants == 4
        names = {g["name"] for g in existing}
        out = list(existing)
        if "severity_watch" not in names:
            out.append({"name": "severity_watch", "triggered": True, "detail": "probe",
                        "action": "gray"})
        if "energy_isolation_absent" not in names:
            out.append({"name": "energy_isolation_absent", "triggered": False,
                        "detail": "", "action": "badge"})
        if "verdict_stability" not in names:
            gate = gate_verdict_stability(stability, n_variants)
            out.append(gate.model_dump())
        return out

    n = st.rewrite_gate_states(mapper)
    assert n == 1, n
    stored = st._conn.execute(
        "SELECT gate_states FROM predictions WHERE report_id = ?", (rid,)).fetchone()[0]
    gates = json.loads(stored)
    names = [g["name"] for g in gates]
    assert names[:7] == [g.name for g in _OLD_GATES], names  # originals keep positions
    assert names[7:] == ["severity_watch", "energy_isolation_absent", "verdict_stability"], names
    assert st._writes_version == writes_before + 1  # metrics cache invalidated

    # idempotent: second pass changes nothing
    assert st.rewrite_gate_states(mapper) == 0

    # a corrupt snapshot is skipped, not fatal
    st._conn.execute("UPDATE predictions SET gate_states = 'not-json' WHERE report_id = ?", (rid,))
    assert st.rewrite_gate_states(lambda e, t, s, w, stability, n_variants: e) == 0
    st.close()


def test_version_three_backfill(tmp: Path) -> None:
    st = _mkstorage(tmp / "v3")
    text = "Worker climbed the scaffold without a harness."
    rid = _seed_prediction(st, text, _OLD_GATES)
    st.save_precomputed("gate_schema_version", {"version": 3})
    assert GATE_SCHEMA_VERSION > 3
    _backfill_gate_states(st, 0.5)
    gates = st.get_report(rid).prediction.gate_states
    assert [g.name for g in gates[:7]] == [g.name for g in _OLD_GATES]
    fall = [g for g in gates if g.name == "fall_protection_absent"]
    assert len(fall) == 1 and fall[0].triggered and fall[0].action == "gray"
    assert st.load_precomputed("gate_schema_version") == {"version": GATE_SCHEMA_VERSION}
    _backfill_gate_states(st, 0.5)
    assert st.get_report(rid).prediction.gate_states == gates
    st.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        test_actions_table_and_crud(tmp / "a")
        test_gate_backfill_rewrite(tmp / "b")
        test_version_three_backfill(tmp / "c")
    print("storage_config_check: ALL PASS")


if __name__ == "__main__":
    main()