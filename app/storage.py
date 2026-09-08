"""Storage: protocol + stdlib-sqlite3 implementation (DECISION_LOG D5).

SQLite + numpy brute-force cosine ships; the Storage protocol keeps a Postgres
swap possible without touching routes. No ORM, no Alembic — fixed schema,
CREATE IF NOT EXISTS + schema_version row.

Concurrency (SEV1-1 fix): a sqlite3 Connection is NOT thread-safe, even with
check_same_thread=False — concurrent statements on one connection interleave
and return each other's rows (silent wrong scores) or InterfaceError (500s).
Every self._conn access below, reads included, is serialized by self._lock
(an RLock, since the batched write path nests session-index appends).
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

from .ingest import text_hash
from .schemas import OverrideIn, PredictionOut, ReportIn, StoredOverride, StoredReport

log = logging.getLogger(__name__)

CORPUS_NPY = "corpus_embeddings_fp16.npy"
CORPUS_IDS = "corpus_ids.jsonl"

SCHEMA_VERSION = 2

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
-- v2 (SEV2-2): per-row content hashes for cross-request dedup, and per-payload
-- hashes for idempotent replay of an identical re-POST.
CREATE TABLE IF NOT EXISTS report_hashes (
    hash TEXT PRIMARY KEY,
    report_id INTEGER NOT NULL REFERENCES reports(id)
);
CREATE TABLE IF NOT EXISTS ingest_payloads (
    hash TEXT PRIMARY KEY,
    result TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage(Protocol):
    def add_report(self, report: ReportIn) -> int: ...
    def add_prediction(self, report_id: int, pred: PredictionOut) -> None: ...
    def add_embedding(self, report_id: int, vec: np.ndarray) -> None: ...
    def add_ingest_batch(
        self, items: list[tuple[ReportIn, PredictionOut, np.ndarray, str]]
    ) -> tuple[list[int], int]: ...
    def get_ingest_replay(self, payload_hash: str) -> dict | None: ...
    def record_ingest_payload(self, payload_hash: str, result: dict) -> None: ...
    def get_report(self, report_id: int) -> StoredReport | None: ...
    def list_reports(self, limit: int = 100, offset: int = 0) -> list[StoredReport]: ...
    def add_override(self, ov: OverrideIn) -> int: ...
    def list_overrides(self, report_id: int | None = None) -> list[StoredOverride]: ...
    def export_overrides(self) -> list[dict]: ...
    def density_aggregate(self, by: str, threshold: float) -> list[dict]: ...
    def metrics_aggregate(self, threshold: float) -> dict: ...
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
        self._lock = threading.RLock()  # serializes EVERY connection access (SEV1-1)
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
            version = int(self._conn.execute(
                "SELECT version FROM schema_meta WHERE id = 1"
            ).fetchone()[0])
            if version < 2:
                # v1 -> v2: backfill per-row content hashes for pre-existing
                # reports so cross-request dedup covers the pre-seeded corpus.
                rows = self._conn.execute("SELECT id, text FROM reports").fetchall()
                self._conn.executemany(
                    "INSERT OR IGNORE INTO report_hashes (hash, report_id) VALUES (?, ?)",
                    [(text_hash(r["text"]), int(r["id"])) for r in rows],
                )
                self._conn.execute("UPDATE schema_meta SET version = 2 WHERE id = 1")
                log.info("schema v1->v2: backfilled %d report content hashes", len(rows))
        # Metrics aggregate cache: invalidated by _writes_version on any
        # report/prediction write (SEV3-1 — /api/metrics/summary full-scan).
        self._writes_version = 0
        self._metrics_cache: tuple[int, float, dict] | None = None
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
            raise ValueError(
                f"corpus index misaligned: {mat.shape[0]} vectors vs {len(base_ids)} ids "
                f"under {index_dir}. Recovery: re-copy a matched {CORPUS_NPY} + "
                f"{CORPUS_IDS} pair, or DELETE BOTH files to boot in session-only "
                f"near-dup mode (degraded: verbatim-corpus banners off)."
            )
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
            self._writes_version += 1
            return int(cur.lastrowid)

    def add_prediction(self, report_id: int, pred: PredictionOut) -> None:
        with self._lock, self._conn:
            self._insert_prediction(report_id, pred)
            self._writes_version += 1

    def _insert_prediction(self, report_id: int, pred: PredictionOut) -> None:
        # caller holds self._lock inside a transaction
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
            self._writes_version += 1

    # -- transactional batch ingest (SEV2-3) -------------------------------
    def add_ingest_batch(
        self,
        items: list[tuple[ReportIn, PredictionOut, np.ndarray, str]],
    ) -> tuple[list[int], int]:
        """Write one ingest request's rows in a SINGLE transaction: all rows
        land or none do (a mid-batch failure rolls back — no silent partial
        commit). items = (report, prediction, embedding, text_hash) in
        request order. Per-row cross-request dedup: a row whose content hash
        already exists is skipped, not double-stored (SEV2-2).
        Returns (inserted report ids, skipped_duplicate count)."""
        ids: list[int] = []
        skipped = 0
        with self._lock, self._conn:
            for report, pred, vec, thash in items:
                if self._conn.execute(
                    "SELECT 1 FROM report_hashes WHERE hash = ?", (thash,)
                ).fetchone():
                    skipped += 1
                    continue
                cur = self._conn.execute(
                    "INSERT INTO reports (text, date, site, activity, contractor, source, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (report.text, report.date, report.site, report.activity,
                     report.contractor, report.source, _utcnow()),
                )
                rid = int(cur.lastrowid)
                self._conn.execute(
                    "INSERT INTO report_hashes (hash, report_id) VALUES (?, ?)",
                    (thash, rid),
                )
                self._insert_prediction(rid, pred)
                arr = np.ascontiguousarray(vec, dtype=np.float32)
                self._conn.execute(
                    "INSERT OR REPLACE INTO embeddings (report_id, vector) VALUES (?, ?)",
                    (rid, arr.tobytes()),
                )
                if self._sess_loaded:
                    self._session_append(rid, arr)
                ids.append(rid)
            self._writes_version += 1
        return ids, skipped

    # -- ingest payload idempotency (SEV2-2) --------------------------------
    def get_ingest_replay(self, payload_hash: str) -> dict | None:
        """Stored IngestResult for an identical previously-ingested payload."""
        with self._lock:
            row = self._conn.execute(
                "SELECT result FROM ingest_payloads WHERE hash = ?", (payload_hash,)
            ).fetchone()
        return json.loads(row["result"]) if row else None

    def record_ingest_payload(self, payload_hash: str, result: dict) -> None:
        """Remember an ingest payload's result so an identical re-POST replays
        it. Called only AFTER the batch committed (a failed ingest leaves no
        replay entry, so a retry re-runs cleanly; per-row dedup still prevents
        any double count in the gap)."""
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO ingest_payloads (hash, result, created_at)"
                " VALUES (?, ?, ?)",
                (payload_hash, json.dumps(result), _utcnow()),
            )

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
    # One LEFT JOIN fetches report + prediction together (SEV3-1: the old
    # per-row SELECT made every list endpoint N+1).
    _REPORT_SELECT = (
        "SELECT r.id, r.text, r.date, r.site, r.activity, r.contractor, r.source,"
        "       r.created_at, p.sif_score, p.rule_probs, p.well_control,"
        "       p.evidence_spans, p.gate_states, p.model_version"
        " FROM reports r LEFT JOIN predictions p ON p.report_id = r.id"
    )

    def _row_to_report(self, row: sqlite3.Row) -> StoredReport:
        pred = None
        if row["sif_score"] is not None:
            pred = PredictionOut(
                sif_score=row["sif_score"],
                rule_probs=json.loads(row["rule_probs"]),
                well_control=bool(row["well_control"]),
                evidence_spans=json.loads(row["evidence_spans"]),
                gate_states=json.loads(row["gate_states"]),
                model_version=row["model_version"],
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
        with self._lock:
            row = self._conn.execute(
                self._REPORT_SELECT + " WHERE r.id = ?", (report_id,)
            ).fetchone()
        return self._row_to_report(row) if row else None

    def list_reports(self, limit: int = 100, offset: int = 0) -> list[StoredReport]:
        with self._lock:
            rows = self._conn.execute(
                self._REPORT_SELECT + " ORDER BY r.id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_report(r) for r in rows]

    def list_overrides(self, report_id: int | None = None) -> list[StoredOverride]:
        with self._lock:
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

    # -- aggregate views (SEV3-1: computed in SQL / cached, no full scan) ----
    _DENSITY_FACETS = ("site", "activity", "contractor")

    def density_aggregate(self, by: str, threshold: float) -> list[dict]:
        """Precursor-density ranking computed in SQL — one GROUP BY over the
        join, no row materialization, no 100k cap. Rows without a prediction
        count as score 0.0 (same semantics as the old Python aggregation)."""
        if by not in self._DENSITY_FACETS:
            raise ValueError(f"unknown density facet: {by!r}")
        sql = (
            f"SELECT CASE WHEN r.{by} IS NULL OR r.{by} = '' THEN '(unspecified)'"
            f"       ELSE r.{by} END AS key,"
            "       COUNT(*) AS n_reports,"
            "       SUM(CASE WHEN p.sif_score >= ? THEN 1 ELSE 0 END) AS n_flagged,"
            "       AVG(COALESCE(p.sif_score, 0.0)) AS mean_score"
            " FROM reports r LEFT JOIN predictions p ON p.report_id = r.id"
            " GROUP BY key"
        )
        with self._lock:
            rows = self._conn.execute(sql, (threshold,)).fetchall()
        out = [
            {
                "key": r["key"],
                "n_reports": int(r["n_reports"]),
                "n_flagged": int(r["n_flagged"]),
                "sif_rate": round(int(r["n_flagged"]) / int(r["n_reports"]), 4),
                "mean_score": round(float(r["mean_score"]), 4),
            }
            for r in rows
        ]
        out.sort(key=lambda d: (-d["sif_rate"], -d["n_reports"]))
        return out

    def metrics_aggregate(self, threshold: float) -> dict:
        """n_reports / flag stats / gate-trigger counts over ALL predictions.
        Cached per (writes_version, threshold) — the gate_states JSON parse is
        the expensive part and is paid once per data change, not per request."""
        with self._lock:
            cache = self._metrics_cache
            if cache is not None and cache[0] == self._writes_version and cache[1] == threshold:
                return {**cache[2], "gate_trigger_counts": dict(cache[2]["gate_trigger_counts"])}
            n_reports = int(self._conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0])
            rows = self._conn.execute(
                "SELECT sif_score, gate_states FROM predictions"
            ).fetchall()
            scores: list[float] = []
            gate_counts: dict[str, int] = {}
            for r in rows:
                scores.append(float(r["sif_score"]))
                for g in json.loads(r["gate_states"]):
                    if g.get("triggered"):
                        gate_counts[g["name"]] = gate_counts.get(g["name"], 0) + 1
            n_flagged = sum(1 for sc in scores if sc >= threshold)
            result = {
                "n_reports": n_reports,
                "n_flagged": n_flagged,
                "flag_rate": round(n_flagged / len(scores), 4) if scores else 0.0,
                "mean_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
                "gate_trigger_counts": gate_counts,
            }
            self._metrics_cache = (self._writes_version, threshold, result)
            return {**result, "gate_trigger_counts": dict(gate_counts)}

    # -- future-gold export (SEV2-3) -----------------------------------------
    def export_overrides(self) -> list[dict]:
        """The override queue collapsed to future-gold JSONL rows (one dict
        per line when serialized).

        Semantics: latest-wins per (report_id, field) — the override with the
        highest id is the decision; exact duplicates (same report_id, field,
        old_value, new_value, labeler, source, rationale) collapse into it.
        Every superseded/collapsed row id is listed in 'supersedes' so the
        audit trail is recoverable from the table.

        Line schema:
          report_id   int            -- the ingested report
          field       str            -- 'sif_label' | 'rules' | 'notes'
          value       str            -- winning new_value (e.g. 'sif_potential')
          old_value   str | null     -- what the winning row replaced
          labeler     str
          source      str            -- 'override' | 'blind_gold'
          rationale   str | null
          decided_at  str            -- created_at of the winning row (UTC ISO)
          override_id int            -- winning overrides.id
          supersedes  list[int]      -- earlier overrides.ids on (report_id, field)
        """
        with self._lock:
            rows = self._conn.execute("SELECT * FROM overrides ORDER BY id").fetchall()
        winners: dict[tuple[int, str], dict] = {}
        for r in rows:
            key = (int(r["report_id"]), r["field"])
            sig = (r["old_value"], r["new_value"], r["labeler"], r["source"], r["rationale"])
            cur = winners.get(key)
            if cur is not None and cur["_sig"] == sig:
                # exact duplicate of the current winner: collapse
                cur["supersedes"].append(int(r["id"]))
                continue
            superseded = ([cur["override_id"], *cur["supersedes"]] if cur is not None else [])
            winners[key] = {
                "report_id": int(r["report_id"]),
                "field": r["field"],
                "value": r["new_value"],
                "old_value": r["old_value"],
                "labeler": r["labeler"],
                "source": r["source"],
                "rationale": r["rationale"],
                "decided_at": r["created_at"],
                "override_id": int(r["id"]),
                "supersedes": superseded,
                "_sig": sig,
            }
        out = []
        for w in sorted(winners.values(), key=lambda w: w["override_id"]):
            w = {k: v for k, v in w.items() if k != "_sig"}
            out.append(w)
        return out

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
                with self._lock:
                    row = self._conn.execute(
                        "SELECT text FROM reports WHERE id = ?", (rid,)
                    ).fetchone()
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
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM precomputed WHERE key = ?", (key,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def count_reports(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0])

    def count_overrides(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM overrides").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
