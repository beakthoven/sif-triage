"""Storage: protocol + stdlib-sqlite3 implementation (DECISION_LOG D5).

SQLite + numpy brute-force cosine ships; the Storage protocol keeps a Postgres
swap possible without touching routes. No ORM, no Alembic — fixed schema,
CREATE IF NOT EXISTS + schema_version row.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import numpy as np

from .schemas import OverrideIn, PredictionOut, ReportIn, StoredOverride, StoredReport

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    date TEXT,
    site TEXT,
    activity TEXT,
    contractor TEXT,
    source TEXT NOT NULL DEFAULT 'api',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
    report_id INTEGER PRIMARY KEY REFERENCES reports(id),
    sif_score REAL NOT NULL,
    rule_probs TEXT NOT NULL,
    well_control INTEGER NOT NULL,
    evidence_spans TEXT NOT NULL,
    gate_states TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id),
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    labeler TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'override',
    rationale TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS embeddings (
    report_id INTEGER PRIMARY KEY REFERENCES reports(id),
    vector BLOB NOT NULL
);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage(Protocol):
    def add_report(self, report: ReportIn) -> int: ...
    def add_prediction(self, report_id: int, pred: PredictionOut) -> None: ...
    def add_embedding(self, report_id: int, vec: np.ndarray) -> None: ...
    def get_report(self, report_id: int) -> StoredReport | None: ...
    def list_reports(self, limit: int = 100, offset: int = 0) -> list[StoredReport]: ...
    def add_override(self, ov: OverrideIn) -> int: ...
    def list_overrides(self, report_id: int | None = None) -> list[StoredOverride]: ...
    def nearest(self, vec: np.ndarray, k: int = 1, exclude_text: str | None = None) -> list[tuple[int, float]]: ...
    def count_reports(self) -> int: ...
    def count_overrides(self) -> int: ...
    def close(self) -> None: ...


class SQLiteStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.Lock()  # SQLite single-writer
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_meta (id, version) VALUES (1, ?)",
                (SCHEMA_VERSION,),
            )

    # -- writes ----------------------------------------------------------
    def add_report(self, report: ReportIn) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO reports (text, date, site, activity, contractor, source, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (report.text, report.date, report.site, report.activity,
                 report.contractor, report.source, _utcnow()),
            )
            return int(cur.lastrowid)

    def add_prediction(self, report_id: int, pred: PredictionOut) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO predictions"
                " (report_id, sif_score, rule_probs, well_control, evidence_spans,"
                "  gate_states, model_version, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report_id,
                    pred.sif_score,
                    json.dumps(pred.rule_probs),
                    int(pred.well_control),
                    json.dumps([s.model_dump() for s in pred.evidence_spans]),
                    json.dumps([g.model_dump() for g in pred.gate_states]),
                    pred.model_version,
                    _utcnow(),
                ),
            )

    def add_embedding(self, report_id: int, vec: np.ndarray) -> None:
        arr = np.ascontiguousarray(vec, dtype=np.float32)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO embeddings (report_id, vector) VALUES (?, ?)",
                (report_id, arr.tobytes()),
            )

    def add_override(self, ov: OverrideIn) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO overrides"
                " (report_id, field, old_value, new_value, labeler, source, rationale, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ov.report_id, ov.field, ov.old_value, ov.new_value,
                 ov.labeler, ov.source, ov.rationale, _utcnow()),
            )
            return int(cur.lastrowid)

    # -- reads -----------------------------------------------------------
    def _row_to_report(self, row: sqlite3.Row) -> StoredReport:
        pred = None
        prow = self._conn.execute(
            "SELECT * FROM predictions WHERE report_id = ?", (row["id"],)
        ).fetchone()
        if prow is not None:
            pred = PredictionOut(
                sif_score=prow["sif_score"],
                rule_probs=json.loads(prow["rule_probs"]),
                well_control=bool(prow["well_control"]),
                evidence_spans=json.loads(prow["evidence_spans"]),
                gate_states=json.loads(prow["gate_states"]),
                model_version=prow["model_version"],
            )
        return StoredReport(
            id=row["id"],
            report=ReportIn(
                text=row["text"], date=row["date"], site=row["site"],
                activity=row["activity"], contractor=row["contractor"],
                source=row["source"],
            ),
            prediction=pred,
            created_at=row["created_at"],
        )

    def get_report(self, report_id: int) -> StoredReport | None:
        row = self._conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return self._row_to_report(row) if row else None

    def list_reports(self, limit: int = 100, offset: int = 0) -> list[StoredReport]:
        rows = self._conn.execute(
            "SELECT * FROM reports ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [self._row_to_report(r) for r in rows]

    def list_overrides(self, report_id: int | None = None) -> list[StoredOverride]:
        if report_id is None:
            rows = self._conn.execute("SELECT * FROM overrides ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM overrides WHERE report_id = ? ORDER BY id", (report_id,)
            ).fetchall()
        return [
            StoredOverride(
                id=r["id"], report_id=r["report_id"], field=r["field"],
                old_value=r["old_value"], new_value=r["new_value"],
                labeler=r["labeler"], source=r["source"], rationale=r["rationale"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # -- near-dup index ----------------------------------------------------
    # ponytail: full table scan + rebuild per query; exact and fine for the demo
    # corpus (n<=~10k). Upgrade path: invalidate-on-write cache, then memmap
    # index once the 110k-row synthetic corpus joins the index.
    def _index(self) -> tuple[list[int], np.ndarray]:
        rows = self._conn.execute(
            "SELECT report_id, vector FROM embeddings ORDER BY report_id"
        ).fetchall()
        if not rows:
            return [], np.zeros((0, 0), dtype=np.float32)
        ids = [r["report_id"] for r in rows]
        mat = np.stack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])
        return ids, mat

    def nearest(self, vec: np.ndarray, k: int = 1, exclude_text: str | None = None) -> list[tuple[int, float]]:
        ids, mat = self._index()
        if not ids:
            return []
        v = np.asarray(vec, dtype=np.float32)
        sims = mat @ v  # both sides L2-normalized -> cosine
        order = np.argsort(-sims)
        out: list[tuple[int, float]] = []
        for i in order:
            rid = ids[int(i)]
            if exclude_text is not None:
                row = self._conn.execute("SELECT text FROM reports WHERE id = ?", (rid,)).fetchone()
                if row and row["text"] == exclude_text:
                    continue  # exact self-match, not a near-dup signal
            out.append((rid, float(sims[int(i)])))
            if len(out) >= k:
                break
        return out

    def count_reports(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0])

    def count_overrides(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM overrides").fetchone()[0])

    def close(self) -> None:
        self._conn.close()
