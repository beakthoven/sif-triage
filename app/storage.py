"""Storage: protocol + stdlib-sqlite3 implementation (DECISION_LOG D5).

SQLite + numpy brute-force cosine ships; the Storage protocol keeps a Postgres
swap possible without touching routes. No ORM, no Alembic — fixed schema,
CREATE IF NOT EXISTS + schema_version row.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import numpy as np

from .schemas import OverrideIn, PredictionOut, ReportIn, StoredOverride, StoredReport

log = logging.getLogger(__name__)

CORPUS_NPY = "corpus_embeddings_fp16.npy"
CORPUS_IDS = "corpus_ids.jsonl"

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
CREATE TABLE IF NOT EXISTS precomputed (
    key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
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
    def nearest(self, vec: np.ndarray, k: int = 1, exclude_text: str | None = None) -> list[tuple[int | str, float]]: ...
    def nearest_base_batch(self, vecs: np.ndarray) -> list[tuple[int | str, float] | None]: ...
    def nearest_session(self, vec: np.ndarray) -> tuple[int, float] | None: ...
    def save_precomputed(self, key: str, payload: dict) -> None: ...
    def load_precomputed(self, key: str) -> dict | None: ...
    def count_reports(self) -> int: ...
    def count_overrides(self) -> int: ...
    def close(self) -> None: ...


class SQLiteStorage:
    def __init__(self, db_path: Path, corpus_index_dir: Path | None = None) -> None:
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
        # Precomputed MiniLM corpus index (training + synthetic rows) so the
        # near-dup banner catches verbatim training-row paste attacks
        # (ARCHITECTURE runtime; demo red-teamer attack (d)).
        self._base_ids: list[str] = []
        self._base_mat: np.ndarray | None = None
        # Session-row near-dup tier: preallocated fp32 buffer warmed once from
        # the embeddings table, then appended in place on add_embedding. The
        # old _index() full-scanned + np.stacked the whole table per query —
        # O(n^2) over a 5k-row bulk seed (D25).
        self._sess_loaded = False
        self._sess_ids: list[int] = []
        self._sess_mat: np.ndarray | None = None
        self._sess_n = 0
        if corpus_index_dir is not None:
            self._load_corpus_index(Path(corpus_index_dir))

    def _load_corpus_index(self, index_dir: Path) -> None:
        """Load corpus_embeddings_fp16.npy + corpus_ids.jsonl at startup.
        fp16 memmap is upcast to fp32 in RAM once (70,398 x 384 = ~108 MB,
        post-D24: training corpus minus the live-demo cards):
        fp16 matmul has no fast CPU path, so the fp32 copy is the query-side
        win. Absent files degrade silently to session-rows-only indexing."""
        npy, ids_file = index_dir / CORPUS_NPY, index_dir / CORPUS_IDS
        if not npy.exists() or not ids_file.exists():
            log.warning("corpus index not found under %s; near-dup covers session rows only", index_dir)
            return
        t0 = time.perf_counter()
        mat = np.load(npy, mmap_mode="r").astype(np.float32)
        base_ids = [json.loads(line)["id"] for line in ids_file.open(encoding="utf-8")]
        if mat.shape[0] != len(base_ids):
            raise ValueError(f"corpus index misaligned: {mat.shape[0]} vectors vs {len(base_ids)} ids")
        self._base_mat, self._base_ids = mat, base_ids
        log.info("corpus near-dup index loaded: %d x %d fp32 in %.2fs",
                 mat.shape[0], mat.shape[1], time.perf_counter() - t0)

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
            if self._sess_loaded:
                self._session_append(report_id, arr)

    def _session_append(self, report_id: int, arr: np.ndarray) -> None:
        # caller holds self._lock
        if self._sess_mat is None:
            self._sess_mat = np.zeros((4096, arr.shape[0]), dtype=np.float32)
        if self._sess_n == len(self._sess_mat):
            self._sess_mat = np.concatenate([self._sess_mat, np.zeros_like(self._sess_mat)])
        self._sess_mat[self._sess_n] = arr
        self._sess_ids.append(report_id)
        self._sess_n += 1

    def _session_index(self) -> tuple[list[int], np.ndarray]:
        # caller holds self._lock; warms the cache from the table once so a
        # restarted server still covers previously ingested rows.
        if not self._sess_loaded:
            rows = self._conn.execute(
                "SELECT report_id, vector FROM embeddings ORDER BY report_id"
            ).fetchall()
            for r in rows:
                self._session_append(int(r["report_id"]), np.frombuffer(r["vector"], dtype=np.float32))
            self._sess_loaded = True
        return self._sess_ids, (self._sess_mat[: self._sess_n] if self._sess_mat is not None
                                else np.zeros((0, 0), dtype=np.float32))

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
    # The query fans out over two tiers: the precomputed corpus index (fp32,
    # in RAM — one 70k x 384 matmul, ~10-25 ms) and session-ingested rows
    # (preallocated buffer warmed once from the table; O(1) amortized append).
    def nearest_base_batch(self, vecs: np.ndarray) -> list[tuple[int | str, float] | None]:
        """Top-1 corpus-tier hit per row for a (n, 384) batch — one matmul
        for the whole ingest chunk instead of one matvec per row (D25).
        None per row when no corpus index is loaded."""
        if self._base_mat is None:
            return [None] * len(vecs)
        mat = np.ascontiguousarray(np.asarray(vecs, dtype=np.float32))
        sims = self._base_mat @ mat.T  # L2-normalized both sides -> cosine
        top = np.argmax(sims, axis=0)
        return [(self._base_ids[int(i)], float(sims[int(i), j])) for j, i in enumerate(top)]

    def nearest_session(self, vec: np.ndarray) -> tuple[int, float] | None:
        """Top-1 session-tier hit for one vector (None when no session rows)."""
        v = np.asarray(vec, dtype=np.float32).ravel()
        with self._lock:
            ids, mat = self._session_index()
        if not ids:
            return None
        sims = mat @ v
        i = int(np.argmax(sims))
        return ids[i], float(sims[i])

    def nearest(self, vec: np.ndarray, k: int = 1, exclude_text: str | None = None) -> list[tuple[int | str, float]]:
        """Top-k cosine over corpus index (str corpus ids) + session rows (int
        report ids), merged. exclude_text filters only session rows — corpus
        rows are exactly what a verbatim training-row paste must match."""
        v = np.asarray(vec, dtype=np.float32).ravel()
        scored: list[tuple[int | str, float]] = []
        if self._base_mat is not None:
            sims = self._base_mat @ v  # L2-normalized both sides -> cosine
            take = min(len(sims), max(k, 8))
            top = np.argpartition(-sims, take - 1)[:take]
            scored.extend((self._base_ids[int(i)], float(sims[int(i)])) for i in top)
        with self._lock:
            ids, mat = self._session_index()
        if ids:
            sims = mat @ v
            scored.extend((ids[int(i)], float(sims[int(i)])) for i in np.argsort(-sims))
        scored.sort(key=lambda t: -t[1])
        out: list[tuple[int | str, float]] = []
        for rid, sim in scored:
            if exclude_text is not None and isinstance(rid, int):
                row = self._conn.execute("SELECT text FROM reports WHERE id = ?", (rid,)).fetchone()
                if row and row["text"] == exclude_text:
                    continue  # exact self-match, not a near-dup signal
            out.append((rid, sim))
            if len(out) >= k:
                break
        return out

    # -- precomputed payloads (e.g. pattern-mining stats) -------------------
    def save_precomputed(self, key: str, payload: dict) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO precomputed (key, payload, created_at)"
                " VALUES (?, ?, ?)",
                (key, json.dumps(payload), _utcnow()),
            )

    def load_precomputed(self, key: str) -> dict | None:
        row = self._conn.execute(
            "SELECT payload FROM precomputed WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row["payload"]) if row else None

    def count_reports(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0])

    def count_overrides(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM overrides").fetchone()[0])

    def close(self) -> None:
        self._conn.close()
