"""A5 storage-hardening check: busy_timeout pragma, secondary indexes,
bounded write retry under an externally-held lock, and date-range filters.
Run: .venv/bin/python -m app.tests.a5_storage_check"""
from __future__ import annotations

import logging
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

from app.schemas import ReportIn
from app.storage import SCHEMA_VERSION, SQLiteStorage


def _mkstorage(tmp: Path, busy_ms: int = 5000) -> SQLiteStorage:
    tmp.mkdir(parents=True, exist_ok=True)
    return SQLiteStorage(tmp / "t.db", busy_timeout_ms=busy_ms)


def test_busy_timeout_pragma(tmp: Path) -> None:
    st = _mkstorage(tmp)
    val = st._conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert val == 5000, f"busy_timeout={val}, expected 5000"
    st2 = SQLiteStorage(tmp / "t2.db", busy_timeout_ms=1234)
    assert st2._conn.execute("PRAGMA busy_timeout").fetchone()[0] == 1234
    st.close(); st2.close()


def test_indexes_and_schema_version(tmp: Path) -> None:
    st = _mkstorage(tmp)
    ver = st._conn.execute("SELECT version FROM schema_meta WHERE id = 1").fetchone()[0]
    assert ver == SCHEMA_VERSION, f"schema version {ver}, expected {SCHEMA_VERSION}"
    names = {r[0] for r in st._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")}
    expected = {
        "idx_overrides_report_id", "idx_reports_date",
        "idx_reports_site", "idx_reports_activity", "idx_reports_contractor",
        "idx_actions_report_id",
    }
    assert names == expected, f"indexes {names} != {expected}"
    # planner actually uses them
    plan = " ".join(str(r[-1]) for r in st._conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM overrides WHERE report_id = 5"))
    assert "idx_overrides_report_id" in plan, plan
    plan = " ".join(str(r[-1]) for r in st._conn.execute(
        "EXPLAIN QUERY PLAN SELECT r.id FROM reports r WHERE r.date >= '2020-01-01'"))
    assert "idx_reports_date" in plan, plan
    st.close()


def test_write_retry_under_external_lock(tmp: Path) -> None:
    st = _mkstorage(tmp, busy_ms=250)
    conn2 = sqlite3.connect(str(tmp / "t.db"))
    conn2.execute("BEGIN IMMEDIATE")  # hold the write lock
    conn2.execute("INSERT INTO reports (text, source, created_at) VALUES ('x', 'api', 'now')")

    records: list[logging.LogRecord] = []

    class _Cap(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logging.getLogger("app.storage").addHandler(_Cap())

    result: list[int] = []

    def writer() -> None:
        result.append(st.add_report(ReportIn(text="retry probe row" * 3, date="2021-03-04")))

    th = threading.Thread(target=writer)
    th.start()
    time.sleep(0.4)          # let attempt 1 time out against the held lock
    conn2.rollback()         # release -> the retry should win
    th.join(timeout=10)
    assert result, "write did not land after lock release (retry failed)"
    assert any("retrying" in r.getMessage() for r in records), records
    conn2.close()

    # bounded failure: lock held for good -> OperationalError, not a hang
    conn3 = sqlite3.connect(str(tmp / "t.db"))
    conn3.execute("BEGIN IMMEDIATE")
    t0 = time.perf_counter()
    try:
        st.add_report(ReportIn(text="blocked forever row" * 3))
        raise AssertionError("expected OperationalError under permanently held lock")
    except sqlite3.OperationalError as exc:
        assert "lock" in str(exc).lower(), str(exc)
    elapsed = time.perf_counter() - t0
    assert 0.6 < elapsed < 5.0, f"bounded retry took {elapsed:.2f}s (expected ~1s)"
    conn3.close()
    st.close()


def test_date_filters(tmp: Path) -> None:
    st = _mkstorage(tmp)
    rid_a = st.add_report(ReportIn(text="frac tank vent line corroded" * 3, date="2020-05-01", site="SiteA"))
    rid_b = st.add_report(ReportIn(text="rig floor hand crushed toe" * 3, date="2021-06-15", site="SiteB"))
    assert st.count_reports() == 2
    got = st.list_reports(date_from="2021-01-01", date_to="2021-12-31")
    assert [r.id for r in got] == [rid_b], got
    got = st.list_reports(date_from="2020-05-01")  # open-ended lower bound
    assert sorted(r.id for r in got) == sorted([rid_a, rid_b])
    assert st.list_reports(date_to="2020-05-01")[0].id == rid_a
    agg = {r["key"]: r["n_reports"] for r in st.density_aggregate("site", 0.5, date_from="2021-01-01")}
    assert agg == {"SiteB": 1}, agg
    agg_all = {r["key"]: r["n_reports"] for r in st.density_aggregate("site", 0.5)}
    assert agg_all == {"SiteA": 1, "SiteB": 1}, agg_all
    try:
        st.list_reports(date_from="05/2020")
        raise AssertionError("bad date format accepted")
    except ValueError:
        pass
    st.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        test_busy_timeout_pragma(tmp / "a")
        test_indexes_and_schema_version(tmp / "b")
        test_write_retry_under_external_lock(tmp / "c")
        test_date_filters(tmp / "d")
    print("a5_storage_check: ALL PASS")


if __name__ == "__main__":
    main()