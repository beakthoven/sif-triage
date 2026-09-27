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

import contextlib
import json
import logging
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol, TypeVar

import numpy as np

from .ingest import text_hash
from .schemas import OverrideIn, PredictionOut, ReportIn, StoredOverride, StoredReport

try:
    from threadpoolctl import threadpool_limits as _threadpool_limits
except ImportError:  # bare runtime envs without the dep degrade to unfixed timing
    _threadpool_limits = None


def _blas_single_thread():
    """Pin BLAS to 1 thread around the near-dup matmuls.

    These matmuls stream a 108 MB fp32 index — memory-bound, so threads buy
    nothing (2.9 ms either way) — but OpenBLAS's multithreaded gemm/gemv
    leaves its worker threads spinning, and the NEXT onnxruntime intra-op run
    then starves (measured: predict 21 ms -> 77-97 ms after one near-dup
    matmul; full /classify ship path 127 -> 28 ms with limits=1, identical
    results; runs/run2/day2/latency_v2_final.md)."""
    if _threadpool_limits is None:
        return contextlib.nullcontext()
    return _threadpool_limits(limits=1, user_api="blas")

log = logging.getLogger(__name__)

CORPUS_NPY = "corpus_embeddings_fp16.npy"
CORPUS_IDS = "corpus_ids.jsonl"

SCHEMA_VERSION = 5

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
    created_at TEXT NOT NULL,
    -- v5: self-consistency ensemble fields (NULL on legacy single-shot rows)
    score_spread REAL,
    n_variants INTEGER,
    variant_scores TEXT,
    verdict_stability REAL
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
-- v3 (A5): first secondary indexes. Zero existed before — every /review
-- lookup and facet GROUP BY was a full scan (backend-stack-decision §2).
-- overrides.report_id backs list_overrides(report_id); reports.date is the
-- time dimension (604 distinct values) backing date-range filters; the facet
-- columns back /density's GROUP BY keys. IF NOT EXISTS keeps the
-- unconditional executescript at boot idempotent on existing databases.
CREATE INDEX IF NOT EXISTS idx_overrides_report_id ON overrides(report_id);
CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(date);
CREATE INDEX IF NOT EXISTS idx_reports_site ON reports(site);
CREATE INDEX IF NOT EXISTS idx_reports_activity ON reports(activity);
CREATE INDEX IF NOT EXISTS idx_reports_contractor ON reports(contractor);
-- v4 (CAPA): action-closure rows attached to review decisions. The DECISIONS
-- surface kept owner/due/status in localStorage only (dashboard/src/features/
-- decisions/data.ts CAPA_KEY) — wiped on reinstall and invisible to any other
-- reviewer. One row per decision: UNIQUE override_id matches the UI's
-- CapaStore, which is keyed by override id. status vocabulary is the UI's
-- (open | in_progress | closed) but is NOT enforced here — storage stays
-- lenient like override reads; the route layer validates (OverrideWrite
-- pattern in app/schemas.py).
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id),
    override_id INTEGER NOT NULL UNIQUE REFERENCES overrides(id),
    owner TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actions_report_id ON actions(report_id);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


T = TypeVar("T")


def _is_locked_error(exc: sqlite3.OperationalError) -> bool:
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date_bound(value: str) -> str:
    """reports.date is ISO text (YYYY-MM-DD), so lexicographic compare IS
    date compare. Reject anything else loudly instead of silently filtering
    on a wrong lexicographic range."""
    if not _DATE_RE.match(value):
        raise ValueError(f"date filter must be YYYY-MM-DD, got {value!r}")
    return value


_UNSET = object()


class Storage(Protocol):
    def add_report(self, report: ReportIn) -> int: ...
    def add_prediction(self, report_id: int, pred: PredictionOut) -> None: ...
    def add_embedding(self, report_id: int, vec: np.ndarray) -> None: ...
    def add_ingest_batch(
        self, items: list[tuple[ReportIn, PredictionOut, np.ndarray, str]]
    ) -> tuple[list[int], int]: ...
    def get_ingest_replay(self, payload_hash: str) -> dict | None: ...
    def record_ingest_payload(self, payload_hash: str, result: dict) -> None: ...
    def get_report_id_by_hash(self, thash: str) -> int | None: ...
    def get_report(self, report_id: int) -> StoredReport | None: ...
    def list_reports(self, limit: int = 100, offset: int = 0,
                     date_from: str | None = None, date_to: str | None = None) -> list[StoredReport]: ...
    def add_override(self, ov: OverrideIn) -> int: ...
    def list_overrides(self, report_id: int | None = None) -> list[StoredOverride]: ...
    def export_overrides(self) -> list[dict]: ...
    def density_aggregate(self, by: str, threshold: float,
                          date_from: str | None = None, date_to: str | None = None) -> list[dict]: ...
    def patterns_aggregate(self, kind: str, threshold: float, min_n: int = 2) -> list[dict]: ...
    def metrics_aggregate(self, threshold: float) -> dict: ...
    def nearest(self, vec: np.ndarray, k: int = 1, exclude_text: str | None = None) -> list[tuple[int | str, float]]: ...
    def nearest_base_batch(self, vecs: np.ndarray) -> list[tuple[int | str, float] | None]: ...
    def nearest_session(self, vec: np.ndarray) -> tuple[int, float] | None: ...
    def duplicate_clusters(self, min_cos: float) -> dict: ...
    def save_precomputed(self, key: str, payload: dict) -> None: ...
    def load_precomputed(self, key: str) -> dict | None: ...
    def count_reports(self) -> int: ...
    def count_overrides(self) -> int: ...
    def add_action(self, report_id: int, override_id: int, owner: str,
                   due_date: str | None, status: str = "open") -> int: ...
    def get_action(self, action_id: int) -> dict | None: ...
    def get_action_by_override(self, override_id: int) -> dict | None: ...
    def list_actions(self, report_id: int | None = None,
                     override_id: int | None = None) -> list[dict]: ...
    def update_action(self, action_id: int, *, owner: str | None = None,
                      due_date: str | None | object = _UNSET, status: str | None = None) -> bool: ...
    def delete_action(self, action_id: int) -> bool: ...
    def rewrite_gate_states(
        self, mapper: Callable[[list[dict], str, float, bool, float | None, int | None], list[dict]]
    ) -> int: ...
    def close(self) -> None: ...


class SQLiteStorage:
    def __init__(
        self,
        db_path: Path,
        corpus_index_dir: Path | None = None,
        busy_timeout_ms: int = 5000,
    ) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.RLock()  # serializes EVERY connection access (SEV1-1)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        # A5: explicit busy_timeout. Python's sqlite3 already installs an
        # implicit 5 s busy handler — that undeclared default is exactly the
        # measured "5 s block then HTTP 500" under a held external write lock.
        # Declared + tunable here; _write() adds the bounded retry for the
        # WAL snapshot-upgrade SQLITE_BUSY that ignores busy_timeout.
        self._conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
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
            if version < 3:
                # v2 -> v3: secondary indexes (created by the unconditional
                # _SCHEMA executescript above, IF NOT EXISTS). No backfill.
                self._conn.execute("UPDATE schema_meta SET version = 3 WHERE id = 1")
                log.info("schema v%d->v%d: secondary indexes applied", version, SCHEMA_VERSION)
            if version < 4:
                # v3 -> v4: the actions (CAPA) table (created by the
                # unconditional _SCHEMA executescript above). No backfill:
                # existing decisions gain action rows only when a reviewer
                # saves CAPA fields on them — the localStorage store this
                # replaces is per-browser and not migratable.
                self._conn.execute("UPDATE schema_meta SET version = 4 WHERE id = 1")
                log.info("schema v%d->v%d: actions (CAPA) table applied",
                         version, SCHEMA_VERSION)
            if version < 5:
                # v4 -> v5: self-consistency ensemble fields on predictions.
                # ALTER TABLE per column, guarded, because CREATE TABLE IF NOT
                # EXISTS cannot extend a table that already exists. No backfill:
                # legacy rows keep NULL (scored single-shot before the ensemble
                # landed) — they are re-scored by re-seeding, never silently
                # rewritten.
                have = {r[1] for r in self._conn.execute(
                    "PRAGMA table_info(predictions)")}
                for col in ("score_spread REAL", "n_variants INTEGER",
                            "variant_scores TEXT", "verdict_stability REAL"):
                    name = col.split()[0]
                    if name not in have:
                        self._conn.execute(
                            f"ALTER TABLE predictions ADD COLUMN {col}")
                self._conn.execute("UPDATE schema_meta SET version = 5 WHERE id = 1")
                log.info("schema v%d->v%d: ensemble columns applied",
                         version, SCHEMA_VERSION)
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
    # Every write runs through _write(): one lock + transaction wrapper with
    # a bounded retry. busy_timeout paces each lock acquisition, but SQLite
    # raises SQLITE_BUSY *immediately* (ignoring busy_timeout) on the WAL
    # snapshot-upgrade path — deferred BEGIN that first reads, then writes,
    # while another writer committed — and after a busy_timeout expiry under
    # a still-held external lock. The retry covers both; worst-case write
    # block is bounded at _WRITE_ATTEMPTS x busy_timeout + backoff.
    _WRITE_ATTEMPTS = 3
    _WRITE_BACKOFF_S = 0.1

    def _write(self, fn: Callable[[], T]) -> T:
        for attempt in range(1, self._WRITE_ATTEMPTS + 1):
            try:
                with self._lock, self._conn:
                    return fn()
            except sqlite3.OperationalError as exc:
                if attempt == self._WRITE_ATTEMPTS or not _is_locked_error(exc):
                    raise
                log.warning("sqlite write blocked, retrying (%d/%d): %s",
                            attempt, self._WRITE_ATTEMPTS, exc)
                time.sleep(self._WRITE_BACKOFF_S * attempt)

    def add_report(self, report: ReportIn) -> int:
        def _txn() -> int:
            cur = self._conn.execute(
                "INSERT INTO reports (text, date, site, activity, contractor, source, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (report.text, report.date, report.site, report.activity,
                 report.contractor, report.source, _utcnow()),
            )
            self._writes_version += 1
            return int(cur.lastrowid)
        return self._write(_txn)

    def add_prediction(self, report_id: int, pred: PredictionOut) -> None:
        def _txn() -> None:
            self._insert_prediction(report_id, pred)
            self._writes_version += 1
        self._write(_txn)

    def _insert_prediction(self, report_id: int, pred: PredictionOut) -> None:
        # caller holds self._lock inside a transaction
        self._conn.execute(
            "INSERT OR REPLACE INTO predictions"
            " (report_id, sif_score, rule_probs, well_control, evidence_spans,"
            "  gate_states, model_version, created_at,"
            "  score_spread, n_variants, variant_scores, verdict_stability)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                report_id,
                pred.sif_score,
                json.dumps(pred.rule_probs),
                int(pred.well_control),
                json.dumps([s.model_dump() for s in pred.evidence_spans]),
                json.dumps([g.model_dump() for g in pred.gate_states]),
                pred.model_version,
                _utcnow(),
                pred.score_spread,
                pred.n_variants,
                (json.dumps(pred.variant_scores)
                 if pred.variant_scores is not None else None),
                pred.verdict_stability,
            ),
        )

    def add_embedding(self, report_id: int, vec: np.ndarray) -> None:
        arr = np.ascontiguousarray(vec, dtype=np.float32)

        def _txn() -> None:
            self._conn.execute(
                "INSERT OR REPLACE INTO embeddings (report_id, vector) VALUES (?, ?)",
                (report_id, arr.tobytes()),
            )
            self._writes_version += 1

        with self._lock:
            self._write(_txn)
            if self._sess_loaded:
                self._session_append(report_id, arr)

    # -- transactional batch ingest (SEV2-3) -------------------------------
    def add_ingest_batch(
        self,
        items: list[tuple[ReportIn, PredictionOut, np.ndarray, str]],
    ) -> tuple[list[int], int]:
        """Write one ingest request's rows in a SINGLE transaction: all rows
        land or none do (a mid-batch failure rolls back — no silent partial
        commit). items = (report, prediction, embedding, text_hash) in
        request order. Per-row cross-request dedup: a row whose content hash
        already exists is skipped, not double-stored (SEV2-2). Retried on
        lock contention via _write.
        Returns (inserted report ids, skipped_duplicate count)."""
        staged: list[tuple[int, np.ndarray]] = []

        def _txn() -> tuple[list[int], int]:
            staged.clear()
            ids: list[int] = []
            skipped = 0
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
                    staged.append((rid, arr))
                ids.append(rid)
            self._writes_version += 1
            return ids, skipped

        with self._lock:
            result = self._write(_txn)
            for rid, arr in staged:
                self._session_append(rid, arr)
            return result

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
        def _txn() -> None:
            self._conn.execute(
                "INSERT OR REPLACE INTO ingest_payloads (hash, result, created_at)"
                " VALUES (?, ?, ?)",
                (payload_hash, json.dumps(result), _utcnow()),
            )
        self._write(_txn)

    def get_report_id_by_hash(self, thash: str) -> int | None:
        """Report id for a normalized-text content hash (report_hashes), or
        None. Used by the persist=1 classify path when the pasted text is
        already stored — the response then points at the existing row instead
        of writing a duplicate."""
        with self._lock:
            row = self._conn.execute(
                "SELECT report_id FROM report_hashes WHERE hash = ?", (thash,)
            ).fetchone()
        return int(row["report_id"]) if row else None

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

    def duplicate_clusters(self, min_cos: float) -> dict:
        """Build sparse, deterministic star clusters from stored embeddings."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT report_id, vector FROM embeddings ORDER BY report_id"
            ).fetchall()
            reviewed = {
                int(row[0]) for row in self._conn.execute(
                    "SELECT DISTINCT report_id FROM overrides"
                ).fetchall()
            }

        decoded = []
        for row in rows:
            raw = row["vector"]
            if len(raw) % np.dtype(np.float32).itemsize:
                decoded.append((int(row["report_id"]), None))
            else:
                decoded.append((int(row["report_id"]), np.frombuffer(raw, dtype=np.float32)))
        if not decoded:
            return {"n_scored": 0, "n_skipped": 0, "dim": 0, "n_clusters": 0,
                    "n_members": 0, "clusters": []}
        dims: dict[int, int] = {}
        for _, vec in decoded:
            if vec is not None:
                dims[vec.size] = dims.get(vec.size, 0) + 1
        if not dims:
            return {"n_scored": 0, "n_skipped": len(decoded), "dim": 0,
                    "n_clusters": 0, "n_members": 0, "clusters": []}
        dim = max(dims, key=lambda size: (dims[size], -size))
        items = [(rid, vec) for rid, vec in decoded if vec is not None and vec.size == dim]
        n_skipped = len(decoded) - len(items)
        ids = [rid for rid, _ in items]
        mat = np.stack([vec for _, vec in items]).astype(np.float32, copy=False)
        norms = np.linalg.norm(mat, axis=1)
        normalized = np.divide(mat, norms[:, None], out=np.zeros_like(mat),
                               where=norms[:, None] != 0)
        neighbors: list[dict[int, float]] = [dict() for _ in ids]
        block_size = 1024
        with _blas_single_thread():
            for start in range(0, len(ids), block_size):
                sims = normalized[start:start + block_size] @ normalized.T
                for local, row_sims in enumerate(sims):
                    i = start + local
                    for j in np.flatnonzero(row_sims >= min_cos):
                        if int(j) != i:
                            neighbors[i][int(j)] = float(row_sims[j])

        groups_by_exemplar: dict[int, list[int]] = {}
        exemplars: set[int] = set()
        for i in range(len(ids)):
            match = next((j for j in sorted(neighbors[i])
                          if j < i and j in exemplars), None)
            if match is None:
                groups_by_exemplar[i] = [i]
                exemplars.add(i)
            else:
                groups_by_exemplar[match].append(i)

        groups: list[dict] = []
        for members in groups_by_exemplar.values():
            if len(members) < 2:
                continue
            member_ids = [ids[j] for j in members]
            pair_cos = [float(normalized[left] @ normalized[right])
                        for offset, left in enumerate(members)
                        for right in members[offset + 1:]]
            reviewed_ids = [member_id for member_id in member_ids if member_id in reviewed]
            groups.append({
                "exemplar_id": min(reviewed_ids) if reviewed_ids else member_ids[0],
                "member_ids": member_ids,
                "n": len(member_ids),
                "reviewed_member_ids": reviewed_ids,
                "max_cos": max(pair_cos),
            })

        return {
            "n_scored": len(items), "n_skipped": n_skipped, "dim": dim,
            "n_clusters": len(groups),
            "n_members": sum(group["n"] for group in groups),
            "clusters": groups,
        }

    def add_override(self, ov: OverrideIn) -> int:
        def _txn() -> int:
            cur = self._conn.execute(
                "INSERT INTO overrides"
                " (report_id, field, old_value, new_value, labeler, source, rationale, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ov.report_id, ov.field, ov.old_value, ov.new_value,
                 ov.labeler, ov.source, ov.rationale, _utcnow()),
            )
            return int(cur.lastrowid)
        return self._write(_txn)

    # -- reads -----------------------------------------------------------
    # One LEFT JOIN fetches report + prediction together (SEV3-1: the old
    # per-row SELECT made every list endpoint N+1).
    _REPORT_SELECT = (
        "SELECT r.id, r.text, r.date, r.site, r.activity, r.contractor, r.source,"
        "       r.created_at, p.sif_score, p.rule_probs, p.well_control,"
        "       p.evidence_spans, p.gate_states, p.model_version,"
        "       p.score_spread, p.n_variants, p.variant_scores, p.verdict_stability"
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
                score_spread=(row["score_spread"] if row["score_spread"] is not None else 0.0),
                n_variants=(row["n_variants"] if row["n_variants"] is not None else 1),
                variant_scores=(json.loads(row["variant_scores"])
                                if row["variant_scores"] else []),
                verdict_stability=(row["verdict_stability"]
                                   if row["verdict_stability"] is not None else 1.0),
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

    def list_reports(self, limit: int = 100, offset: int = 0,
                     date_from: str | None = None, date_to: str | None = None) -> list[StoredReport]:
        """date_from/date_to bound the (ISO-text) reports.date range,
        inclusive on both ends — the /reports time-slice filter (A5)."""
        clauses: list[str] = []
        params: list[str] = []
        if date_from is not None:
            clauses.append("r.date >= ?")
            params.append(_date_bound(date_from))
        if date_to is not None:
            clauses.append("r.date <= ?")
            params.append(_date_bound(date_to))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                self._REPORT_SELECT + where + " ORDER BY r.id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
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

    def density_aggregate(self, by: str, threshold: float,
                          date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        """Precursor-density ranking computed in SQL — one GROUP BY over the
        join, no row materialization, no 100k cap. Rows without a prediction
        count as score 0.0 (same semantics as the old Python aggregation).
        date_from/date_to bound the (ISO-text) reports.date range, inclusive
        on both ends — the time-window slice for the PS time view (A5)."""
        if by not in self._DENSITY_FACETS:
            raise ValueError(f"unknown density facet: {by!r}")
        sql = (
            f"SELECT CASE WHEN r.{by} IS NULL OR r.{by} = '' THEN '(unspecified)'"
            f"       ELSE r.{by} END AS key,"
            "       COUNT(*) AS n_reports,"
            "       SUM(CASE WHEN p.sif_score >= ? THEN 1 ELSE 0 END) AS n_flagged,"
            "       AVG(COALESCE(p.sif_score, 0.0)) AS mean_score"
            " FROM reports r LEFT JOIN predictions p ON p.report_id = r.id"
        )
        # Parameter order follows the SQL text: threshold ? appears first
        # (inside the SELECT), then any date bounds in the WHERE clause.
        params: list[float | str] = [threshold]
        clauses: list[str] = []
        if date_from is not None:
            clauses.append("r.date >= ?")
            params.append(_date_bound(date_from))
        if date_to is not None:
            clauses.append("r.date <= ?")
            params.append(_date_bound(date_to))
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " GROUP BY key"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
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

    _BARRIER_GATES = (
        "energy_isolation_absent", "gas_test_absent", "permit_absent",
        "fall_protection_absent", "fire_watch_absent", "standby_absent",
        "atmosphere_unmonitored",
    )

    def patterns_aggregate(self, kind: str, threshold: float, min_n: int = 2) -> list[dict]:
        """Aggregate scored report cells and the all-scored baseline in one query."""
        if kind not in ("site_activity", "activity_barrier"):
            raise ValueError(f"unknown pattern kind: {kind!r}")
        sql = (
            "WITH scored AS ("
            " SELECT r.id AS report_id,"
            "        COALESCE(NULLIF(r.activity, ''), '(unspecified)') AS activity,"
            "        COALESCE(NULLIF(r.site, ''), '(unspecified)') AS site,"
            "        p.gate_states, CASE WHEN p.sif_score >= ? THEN 1 ELSE 0 END AS flagged"
            " FROM reports r JOIN predictions p ON p.report_id = r.id"
            "), baseline AS (SELECT AVG(flagged) AS baseline FROM scored)"
        )
        params: list[float | str | int] = [threshold]
        if kind == "site_activity":
            sql += (
                " SELECT activity, site, NULL AS barrier, COUNT(*) AS n,"
                "        SUM(flagged) AS n_flagged, baseline.baseline"
                " FROM scored CROSS JOIN baseline GROUP BY activity, site HAVING COUNT(*) >= ?"
                " ORDER BY activity, site"
            )
        else:
            names = ", ".join("?" for _ in self._BARRIER_GATES)
            sql += (
                ", barrier_reports AS ("
                " SELECT DISTINCT s.report_id, s.activity, s.flagged,"
                "        json_extract(g.value, '$.name') AS barrier"
                " FROM scored s, json_each(s.gate_states) g"
                " WHERE json_extract(g.value, '$.triggered') = 1"
                f" AND json_extract(g.value, '$.name') IN ({names})"
                " AND COALESCE(json_extract(g.value, '$.detail'), '') NOT LIKE 'gate error:%'"
                ") SELECT activity, NULL AS site, barrier, COUNT(*) AS n,"
                "         SUM(flagged) AS n_flagged, baseline.baseline"
                " FROM barrier_reports CROSS JOIN baseline GROUP BY activity, barrier"
                " HAVING COUNT(*) >= ? ORDER BY activity, barrier"
            )
            params.extend(self._BARRIER_GATES)
        params.append(min_n)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

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
        with _blas_single_thread():
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
        with _blas_single_thread():
            sims = mat @ v
            i = int(np.argmax(sims))
        return ids[i], float(sims[i])

    def nearest(self, vec: np.ndarray, k: int = 1, exclude_text: str | None = None) -> list[tuple[int | str, float]]:
        """Top-k cosine over corpus index (str corpus ids) + session rows (int
        report ids), merged. exclude_text filters only session rows — corpus
        rows are exactly what a verbatim training-row paste must match."""
        v = np.asarray(vec, dtype=np.float32).ravel()
        scored: list[tuple[int | str, float]] = []
        with _blas_single_thread():
            if self._base_mat is not None:
                sims = self._base_mat @ v  # L2-normalized both sides -> cosine
                take = min(len(sims), max(k, 8))
                top = np.argpartition(-sims, take - 1)[:take]
                scored.extend((self._base_ids[int(i)], float(sims[int(i)])) for i in top)
        with self._lock:
            ids, mat = self._session_index()
        if ids:
            with _blas_single_thread():
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
        def _txn() -> None:
            self._conn.execute(
                "INSERT OR REPLACE INTO precomputed (key, payload, created_at)"
                " VALUES (?, ?, ?)",
                (key, json.dumps(payload), _utcnow()),
            )
        self._write(_txn)

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

    # -- CAPA actions (v4; DECISIONS surface) -------------------------------
    def _action_row(self, row: sqlite3.Row) -> dict:
        return {
            "id": int(row["id"]),
            "report_id": int(row["report_id"]),
            "override_id": int(row["override_id"]),
            "owner": row["owner"],
            "due_date": row["due_date"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def add_action(self, report_id: int, override_id: int, owner: str,
                   due_date: str | None, status: str = "open") -> int:
        """Insert one CAPA action. Raises sqlite3.IntegrityError when the
        decision already has an action (UNIQUE override_id) or the report/
        override ids dangle (foreign_keys=ON) — the route layer chooses
        between upsert and a 4xx."""
        def _txn() -> int:
            now = _utcnow()
            cur = self._conn.execute(
                "INSERT INTO actions"
                " (report_id, override_id, owner, due_date, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (report_id, override_id, owner, due_date, status, now, now),
            )
            return int(cur.lastrowid)
        return self._write(_txn)

    def get_action(self, action_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM actions WHERE id = ?", (action_id,)
            ).fetchone()
        return self._action_row(row) if row else None

    def get_action_by_override(self, override_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM actions WHERE override_id = ?", (override_id,)
            ).fetchone()
        return self._action_row(row) if row else None

    def list_actions(self, report_id: int | None = None,
                     override_id: int | None = None) -> list[dict]:
        sql = "SELECT * FROM actions"
        clauses: list[str] = []
        params: list[int] = []
        if report_id is not None:
            clauses.append("report_id = ?")
            params.append(report_id)
        if override_id is not None:
            clauses.append("override_id = ?")
            params.append(override_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._action_row(r) for r in rows]

    def update_action(self, action_id: int, *, owner: str | None = None,
                      due_date: str | None | object = _UNSET, status: str | None = None) -> bool:
        """Omitted fields stay unchanged; due_date=None clears to SQL NULL.
        Direct due_date="" retains the legacy empty string. False means no
        such id or nothing to change."""
        sets: list[str] = []
        params: list[str | int | None] = []
        for col, val in (("owner", owner), ("status", status)):
            if val is not None:
                sets.append(f"{col} = ?")
                params.append(val)
        if due_date is not _UNSET:
            sets.append("due_date = ?")
            params.append(due_date)
        if not sets:
            return False
        sets.append("updated_at = ?")
        params.append(_utcnow())
        params.append(action_id)

        def _txn() -> bool:
            cur = self._conn.execute(
                f"UPDATE actions SET {', '.join(sets)} WHERE id = ?", params
            )
            return cur.rowcount > 0
        return self._write(_txn)

    def delete_action(self, action_id: int) -> bool:
        def _txn() -> bool:
            cur = self._conn.execute("DELETE FROM actions WHERE id = ?", (action_id,))
            return cur.rowcount > 0
        return self._write(_txn)

    # -- boot-time gate-schema backfill -------------------------------------
    def rewrite_gate_states(
        self, mapper: Callable[[list[dict], str, float, bool, float | None, int | None], list[dict]]
    ) -> int:
        """Rebuild every stored prediction's gate_states through `mapper`, in
        ONE transaction. mapper receives the existing snapshot, report text,
        score, well-control tag, and stored ensemble stability/count. Rows whose
        mapper output equals the stored list are skipped; a mapper exception
        keeps that row unchanged (a corrupt snapshot never aborts the boot).
        Bumps the metrics-cache version so /metrics/summary recomputes counts."""
        def _txn() -> int:
            rows = self._conn.execute(
                "SELECT p.report_id, p.gate_states, p.sif_score, p.well_control, r.text,"
                "       p.verdict_stability, p.n_variants"
                " FROM predictions p JOIN reports r ON r.id = p.report_id"
            ).fetchall()
            updated = 0
            for row in rows:
                try:
                    existing = json.loads(row["gate_states"])
                    new = mapper(existing, row["text"], float(row["sif_score"]),
                                 bool(row["well_control"]), row["verdict_stability"],
                                 row["n_variants"])
                except Exception:
                    log.exception("gate backfill skipped report %s", row["report_id"])
                    continue
                if new == existing:
                    continue
                self._conn.execute(
                    "UPDATE predictions SET gate_states = ? WHERE report_id = ?",
                    (json.dumps(new), row["report_id"]),
                )
                updated += 1
            self._writes_version += 1
            return updated
        return self._write(_txn)

    def close(self) -> None:
        with self._lock:
            self._conn.close()
