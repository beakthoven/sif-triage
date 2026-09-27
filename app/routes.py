"""API routes. REST only, no websockets (fullstack-architect §3).

All endpoints live under /api except /api/health (registered in main.py).
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
import uuid
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .classifier import (
    Classifier,
    band_for,
    deterministic_cue_spans,
    flag_threshold,
    rule_cue_hits,
    validate_spans,
)
from .config import REPO_ROOT, Settings
from .embedder import embed_texts
from .explain import build_explanation
from .gates import run_gates
from .ingest import parse_records, text_hash, validate_rows
from .report_metadata import extract_site
from .schemas import (
    RULE_DISPLAY,
    ActionCreate,
    ActionOut,
    ActionPatch,
    DensityRow,
    EvidenceSpan,
    ExplanationOut,
    IngestError,
    IngestRequest,
    IngestResult,
    MetricsSummary,
    OverrideWrite,
    PatternRow,
    PredictionOut,
    ClustersOut,
    ReportIn,
    RuleInfo,
    StoredOverride,
    StoredReport,
)
from .storage import Storage

log = logging.getLogger(__name__)

router = APIRouter()

FLAG_THRESHOLD = 0.5  # fallback only — classifier.flag_threshold (D19 tuned
# operating point from the artifact's metrics.json) wins whenever present

# /ingest classification batch (D25): windows across rows share session.run
# calls of this width — the measured sweet spot for the int8 artifact here.
INGEST_BATCH = 32

# Rows above this run POST /ingest as a background job (202 + job id to poll)
# instead of synchronously. Grounded in the MEASURED bulk rate of ~7.3 rows/s
# (68.9 s for the 500-row money beat — docs/discovery/24-be-api.md): 100 rows
# bounds the synchronous worst case near ~14 s, well inside the dashboard's
# 90 s client budget, while 500 rows (~69-81 s measured) is exactly the
# payload that previously made the UI declare 'Ingest failed — live data
# unchanged' over a batch the server had in fact fully stored (SEV-1).
INGEST_SYNC_MAX_ROWS = 100


def _cfg(req: Request) -> Settings:
    return req.app.state.cfg


def _storage(req: Request) -> Storage:
    return req.app.state.storage


def _classifier(req: Request) -> Classifier:
    return req.app.state.classifier


def _predict_with_gates(storage: Storage, clf: Classifier, cfg: Settings, text: str,
                        vec: np.ndarray | None = None) -> PredictionOut:
    pred = clf.predict(text)
    pred.rule_cue_hits = rule_cue_hits(text)
    # Span invariant re-checked against the canonical text at the boundary.
    pred.evidence_spans = validate_spans(text, pred.evidence_spans)
    pred.gate_states = run_gates(text, pred.sif_score, storage, cfg,
                                 vec=vec, well_control=pred.well_control,
                                 flag_thr=flag_threshold(clf),
                                 chunked=getattr(pred, "chunked", False),
                                 verdict_stability=pred.verdict_stability,
                                 n_variants=pred.n_variants)
    return pred


def _wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _date_filter(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        if len(value) != 10:
            raise ValueError
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return value
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{name} must be a valid YYYY-MM-DD date") from exc


def _checked_date_range(date_from: str | None, date_to: str | None) -> tuple[str | None, str | None]:
    start = _date_filter(date_from, "date_from")
    end = _date_filter(date_to, "date_to")
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    return start, end


# Cache only short narratives; immutable values keep each response independent.
@lru_cache(maxsize=8192)
def _cached_rule_cues(text: str) -> tuple[tuple[str, bool], ...]:
    return tuple(rule_cue_hits(text).items())


@lru_cache(maxsize=8192)
def _cached_cue_spans(text: str) -> tuple[tuple[int, int, str], ...]:
    return tuple((span.start, span.end, span.text) for span in deterministic_cue_spans(text))


def _report_band(stored: StoredReport, clf: Classifier, cfg: Settings) -> StoredReport:
    """Reconstitute stored display fields without re-scoring the report."""
    pred = stored.prediction
    if pred is None:
        return stored
    text = stored.report.text
    cached = len(text) <= 1000
    threshold = flag_threshold(clf)
    gray_low = float(getattr(clf, "gray_band_low", cfg.gray_band_low))
    gray_high = float(getattr(clf, "gray_band_high", cfg.gray_band_high))
    updates = {
        "band": band_for(pred.sif_score, threshold, gray_low),
        "flag_threshold": threshold,
        "gray_band_low": gray_low,
        "gray_band_high": gray_high,
        "rule_cue_hits": dict(_cached_rule_cues(text)) if cached else rule_cue_hits(text),
    }
    if not pred.evidence_spans:
        updates["evidence_spans"] = (
            [EvidenceSpan(start=start, end=end, text=value)
             for start, end, value in _cached_cue_spans(text)]
            if cached else validate_spans(text, deterministic_cue_spans(text))
        )
    prediction = pred.model_copy(update=updates)
    return stored.model_copy(update={"prediction": prediction})


@router.post("/classify", response_model=PredictionOut)
def classify(
    body: ReportIn,
    req: Request,
    explain: bool = Query(default=False),
    llm: bool = Query(default=True),
    persist: bool = Query(default=False),
) -> PredictionOut:
    """Single-report classification. Stateless by default; ?persist=1 stores
    the report + prediction (same single-transaction write path as /ingest)
    and returns the real report id in `report_id`, so the dashboard's
    live-paste row can attach overrides via POST /review instead of 404-ing
    on an optimistic placeholder id (final_audit_rehearsal F4). A paste whose
    text is already stored reuses the existing row (content-hash dedup).
    ?explain=1 attaches a human explanation: the deterministic template is
    always present; optional Ollama rewording may make two bounded attempts
    (SIF_EXPLAIN_TIMEOUT each, default 8 s), so fallback can take up to 16 s.
    ?llm=0 pins the template only — the live-paste demo path: a novel text is
    never in the reword cache and does not wait for either attempt."""
    cfg = _cfg(req)
    clf = _classifier(req)
    storage = _storage(req)
    vec = None
    if persist:
        try:
            vec = embed_texts([body.text])[0]
        except Exception:
            log.exception("classify embedding failed; returning stateless prediction")
    pred = _predict_with_gates(storage, clf, cfg, body.text, vec=vec)
    if persist and vec is not None:
        try:
            if not body.site:
                body = body.model_copy(update={"site": extract_site(body.text)})
            th = text_hash(body.text)
            ids, _skipped = storage.add_ingest_batch([(body, pred, vec, th)])
            pred.report_id = ids[0] if ids else storage.get_report_id_by_hash(th)
        except Exception:
            # Persistence must never kill the paste beat: degrade to the old
            # stateless response (report_id stays None, the UI marks the row
            # offline and override falls back to the local log).
            log.exception("classify persist failed; returning stateless prediction")
    if explain:
        pred.explanation = build_explanation(
            pred, body.text, storage,
            use_llm=cfg.explain_llm and llm, url=cfg.ollama_url,
            model=cfg.ollama_model, timeout=cfg.explain_timeout_s,
            threshold=flag_threshold(clf),
        )
    return pred


def _payload_hash(body: IngestRequest) -> str:
    """Canonical hash of the ingest payload for cross-request idempotency
    (SEV2-2): an identical re-POST replays the stored result instead of
    double-ingesting. Key order inside individual records still matters —
    'identical' means byte-canonical, which is exactly the retry case."""
    canon = json.dumps(
        {"records": body.records, "csv": body.csv,
         "column_mapping": body.column_mapping, "source": body.source},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --- bulk ingest jobs ---------------------------------------------------------
# In-process job registry (single uvicorn worker): larger payloads are polled
# for truthful progress and can cancel before the atomic write transaction.
# Registry state is guarded by _INGEST_JOBS_LOCK; ingest rows remain durable
# in SQLite and payload-hash replay makes re-POST safe after a server restart.


class IngestJobAccepted(BaseModel):
    """202 body of a bulk POST /api/ingest. received / total / rejected are
    already final at this point (validation + dedup ran synchronously)."""

    job_id: str
    status: Literal["queued"] = "queued"
    poll: str
    received: int
    total: int
    rejected: int


class IngestJobStatus(BaseModel):
    """Poll body for GET /api/ingest/{job_id}.

    status: queued -> running -> done | error.
    total   rows queued for classify+store (post-validation, post-dedup).
    done    rows classified so far (phase 1); done==total still precedes the
            single write transaction — 'accepted' is only known at done.
    accepted / rejected / skipped_duplicates / report_ids: the honest final
            outcome, populated when status=done.
    detail  non-null on error; an error can follow a committed batch if only
            its payload replay record failed to save.
    """

    job_id: str
    status: Literal["queued", "running", "done", "error", "cancelled"] = "queued"
    received: int = 0
    total: int = 0
    done: int = 0
    accepted: int = 0
    rejected: int = 0
    skipped_duplicates: int = 0
    errors: list[IngestError] = Field(default_factory=list)
    report_ids: list[int] | None = None
    detail: str | None = None


_INGEST_JOBS: dict[str, dict[str, Any]] = {}
_INGEST_JOBS_LOCK = threading.Lock()
_INGEST_JOB_TTL_S = 3600.0  # finished jobs evicted lazily on the next bulk POST


def _register_ingest_job(job_id: str, initial: dict[str, Any]) -> None:
    now = time.monotonic()
    with _INGEST_JOBS_LOCK:
        for jid, job in list(_INGEST_JOBS.items()):
            if job["status"] in ("done", "error", "cancelled") and now - job["ts"] > _INGEST_JOB_TTL_S:
                del _INGEST_JOBS[jid]
        _INGEST_JOBS[job_id] = initial


def _set_ingest_job(job_id: str, **fields: Any) -> None:
    with _INGEST_JOBS_LOCK:
        job = _INGEST_JOBS.get(job_id)
        if job is not None:
            job.update(fields)


def _start_ingest_job(job_id: str) -> bool:
    with _INGEST_JOBS_LOCK:
        job = _INGEST_JOBS.get(job_id)
        if job is None or job.get("cancel_requested"):
            return False
        job["status"] = "running"
        return True


def _ingest_cancelled(job_id: str) -> bool:
    with _INGEST_JOBS_LOCK:
        job = _INGEST_JOBS.get(job_id)
        return job is None or job.get("cancel_requested", False)


def _begin_ingest_commit(job_id: str) -> bool:
    with _INGEST_JOBS_LOCK:
        job = _INGEST_JOBS.get(job_id)
        if job is None or job.get("cancel_requested"):
            return False
        job["committing"] = True
        return True


def _ingest_job_snapshot(job_id: str) -> dict[str, Any] | None:
    """Copy under the lock so json serialization never iterates a list a job
    thread is appending to."""
    with _INGEST_JOBS_LOCK:
        job = _INGEST_JOBS.get(job_id)
        if job is None:
            return None
        snap = {k: (list(v) if k in ("errors", "report_ids") and v is not None else v)
                for k, v in job.items()}
        snap.pop("ts", None)
        return snap


def _ingest_rollback_detail(exc: Exception) -> str:
    return (f"ingest batch failed and was rolled back; nothing stored: "
            f"{type(exc).__name__}: {exc}")


def _ingest_replay_detail(exc: Exception) -> str:
    return (f"ingest batch committed successfully, but saving its replay record failed; "
            f"reports are stored and retry may return a deduplicated result: "
            f"{type(exc).__name__}: {exc}")


class _IngestCancelled(Exception):
    pass


def _mark_ingest_cancelled(job_id: str) -> None:
    _set_ingest_job(job_id, status="cancelled", report_ids=[], ts=time.monotonic())


def _classify_and_store(
    cfg: Settings,
    storage: Storage,
    clf: Classifier,
    unique: list[tuple[ReportIn, str]],
    errors: list[IngestError],
    received: int,
    skipped_within: int,
    progress: Callable[[int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    before_commit: Callable[[], bool] | None = None,
) -> IngestResult:
    """Phase 1 (classify + embed + gates, NO writes) + Phase 2 (one write
    transaction) — shared verbatim by the synchronous path and the bulk job.
    `progress(done)` fires once per classified chunk when given (bulk job
    progress only). Raises the raw storage exception on rollback; call sites
    turn it into the response shape."""
    # Phase 1. MEASURED on this box (docs/discovery/24-be-api.md): ~7.3 rows/s
    # end-to-end for the 500-row money beat (68.9 s). int8 forces
    # per-row solo runs (supports_exact_batch False — per-tensor dynamic
    # quantization shifts logits by batchmate, so per-row keeps stored scores
    # identical to the interactive path); embeddings are batch-computed once
    # per chunk and reused for the near-dup gate AND storage; the corpus-tier
    # nearest is one matmul per chunk. Behavior note (SEV2-3 fix): phase-1
    # gates see committed rows only — exact duplicates within the batch were
    # skipped before this function; rows stay in request order.
    prepared: list[tuple[ReportIn, PredictionOut, np.ndarray, str]] = []
    done = 0
    for off in range(0, len(unique), INGEST_BATCH):
        if cancelled is not None and cancelled():
            raise _IngestCancelled
        chunk = unique[off : off + INGEST_BATCH]
        texts = [r.text for r, _ in chunk]
        if getattr(clf, "supports_exact_batch", False):
            preds = clf.classify_batch(texts, batch_size=INGEST_BATCH)
        else:
            preds = [clf.predict(t) for t in texts]
        vecs = embed_texts(texts)
        base_hits = storage.nearest_base_batch(vecs)
        for (report, th), pred, vec, base_hit in zip(chunk, preds, vecs, base_hits):
            if cancelled is not None and cancelled():
                raise _IngestCancelled
            pred.evidence_spans = validate_spans(report.text, pred.evidence_spans)
            pred.gate_states = run_gates(report.text, pred.sif_score, storage, cfg,
                                         vec=vec, base_hit=base_hit,
                                         well_control=pred.well_control,
                                         flag_thr=flag_threshold(clf),
                                         chunked=getattr(pred, "chunked", False),
                                         verdict_stability=pred.verdict_stability,
                                         n_variants=pred.n_variants)
            prepared.append((report, pred, vec, th))
        done += len(chunk)
        if progress is not None:
            progress(done)
        if cancelled is not None and cancelled():
            raise _IngestCancelled
    # Phase 2 — ONE transaction: every row lands or none do. A failure here
    # rolls the whole batch back and the client gets an honest error instead
    # of a silent partial commit it cannot distinguish from "nothing stored".
    if before_commit is not None and not before_commit():
        raise _IngestCancelled
    ids, skipped_duplicates_db = storage.add_ingest_batch(prepared)
    return IngestResult(
        received=received,
        accepted=len(ids),
        rejected=len(errors),
        report_ids=ids,
        errors=errors,
        skipped_duplicates=skipped_within + skipped_duplicates_db,
    )


def _run_ingest_job(
    job_id: str,
    cfg: Settings,
    storage: Storage,
    clf: Classifier,
    payload_hash: str,
    unique: list[tuple[ReportIn, str]],
    errors: list[IngestError],
    received: int,
    skipped_within: int,
) -> None:
    if not _start_ingest_job(job_id):
        _set_ingest_job(job_id, status="cancelled", ts=time.monotonic())
        return

    def progress(done: int) -> None:
        _set_ingest_job(job_id, done=done)

    try:
        result = _classify_and_store(cfg, storage, clf, unique, errors, received,
                                     skipped_within, progress=progress,
                                     cancelled=lambda: _ingest_cancelled(job_id),
                                     before_commit=lambda: _begin_ingest_commit(job_id))
        # Record the replay entry only after the batch commits; simultaneous
        # identical requests can both miss the lookup and race through storage.
        try:
            storage.record_ingest_payload(payload_hash, result.model_dump())
        except Exception as exc:
            log.exception("bulk ingest job %s committed but replay record failed", job_id)
            _set_ingest_job(job_id, status="error", detail=_ingest_replay_detail(exc),
                            done=len(unique), accepted=result.accepted, rejected=result.rejected,
                            skipped_duplicates=result.skipped_duplicates,
                            report_ids=result.report_ids, errors=[e.model_dump() for e in result.errors],
                            ts=time.monotonic())
            return
    except _IngestCancelled:
        _mark_ingest_cancelled(job_id)
    except Exception as exc:
        log.exception("bulk ingest job %s failed before commit", job_id)
        _set_ingest_job(job_id, status="error", detail=_ingest_rollback_detail(exc),
                        accepted=0, skipped_duplicates=0, report_ids=[],
                        ts=time.monotonic())
    else:
        _set_ingest_job(job_id, status="done", done=len(unique),
                        accepted=result.accepted, rejected=result.rejected,
                        skipped_duplicates=result.skipped_duplicates,
                        errors=[e.model_dump() for e in result.errors],
                        report_ids=result.report_ids, ts=time.monotonic())


@router.post(
    "/ingest",
    response_model=None,
    responses={
        200: {"model": IngestResult, "description": "Synchronous ingest result"},
        202: {"model": IngestJobAccepted, "description": "Bulk ingest job accepted"},
    },
)
def ingest(
    body: IngestRequest, req: Request, background_tasks: BackgroundTasks,
) -> IngestResult | IngestJobAccepted:
    """Ingest raw records or a CSV: validate -> dedup -> classify + embed +
    gates -> one write transaction. Two response shapes (both same-origin, no
    CORS involved):

    - 200 IngestResult — payloads up to INGEST_SYNC_MAX_ROWS (and ALL
      idempotent replays) complete synchronously, exactly as before.
    - 202 IngestJobAccepted — larger payloads return a job id immediately;
      poll GET /api/ingest/{job_id} for progress (done/total) and the final
      outcome. Without this the dashboard's 90 s client timeout fired while
      the server kept persisting, so the UI reported 'Ingest failed — live
      data unchanged' over an actually-stored batch (SEV-1).

    An identical re-POST of a finished payload replays the stored result
    (idempotent_replay=True, SEV2-2); that replay is instant, so it always
    comes back synchronously even for bulk payloads."""
    cfg, storage, clf = _cfg(req), _storage(req), _classifier(req)
    # Idempotent replay: byte-identical re-POST of an already-ingested payload
    # returns the original result untouched (no double count — SEV2-2).
    payload_hash = _payload_hash(body)
    # Without a reservation/unique in-progress claim, concurrent identical
    # requests can both miss this lookup; row hashes still prevent duplicates.
    replay = storage.get_ingest_replay(payload_hash)
    if replay is not None:
        return IngestResult(**{**replay, "idempotent_replay": True})
    try:
        raw_rows = parse_records(body.records, body.csv)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    reports, errors = validate_rows(raw_rows, source=body.source, column_mapping=body.column_mapping)
    # Within-batch dedup on the normalized-text content hash (keep the first
    # occurrence); cross-request row dedup happens at write time in storage.
    seen: set[str] = set()
    unique: list[tuple[ReportIn, str]] = []
    skipped_within = 0
    for r in reports:
        th = text_hash(r.text)
        if th in seen:
            skipped_within += 1
            continue
        seen.add(th)
        unique.append((r, th))

    received = len(raw_rows)
    if len(unique) > INGEST_SYNC_MAX_ROWS:
        job_id = uuid.uuid4().hex
        _register_ingest_job(job_id, {
            "job_id": job_id, "status": "queued", "received": received,
            "total": len(unique),
            "done": 0, "accepted": 0, "rejected": len(errors),
            "skipped_duplicates": 0,
            "errors": [e.model_dump() for e in errors],
            "report_ids": None, "detail": None, "ts": time.monotonic(),
        })
        background_tasks.add_task(
            _run_ingest_job, job_id, cfg, storage, clf, payload_hash,
            unique, errors, received, skipped_within,
        )
        return JSONResponse(
            status_code=202,
            content=IngestJobAccepted(
                job_id=job_id, poll=f"/api/ingest/{job_id}",
                received=received, total=len(unique), rejected=len(errors),
            ).model_dump(),
        )
    try:
        result = _classify_and_store(cfg, storage, clf, unique, errors, received, skipped_within)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_ingest_rollback_detail(exc)) from exc
    # The batch already committed; a replay-record error must not claim rollback.
    try:
        storage.record_ingest_payload(payload_hash, result.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_ingest_replay_detail(exc)) from exc
    return result


@router.delete("/ingest/{job_id}", response_model=IngestJobStatus)
def cancel_ingest_job(job_id: str) -> IngestJobStatus:
    with _INGEST_JOBS_LOCK:
        job = _INGEST_JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"unknown ingest job {job_id}")
        if job["status"] in ("done", "error", "cancelled"):
            raise HTTPException(status_code=409, detail=f"ingest job is already {job['status']}")
        if job.get("committing"):
            raise HTTPException(status_code=409, detail="ingest job is committing and cannot be cancelled")
        job["cancel_requested"] = True
        if job["status"] == "queued":
            job["status"] = "cancelled"
            job["ts"] = time.monotonic()
    snap = _ingest_job_snapshot(job_id)
    return IngestJobStatus(**snap)


@router.get("/ingest/{job_id}", response_model=IngestJobStatus)
def ingest_job_status(job_id: str) -> IngestJobStatus:
    """Poll a bulk ingest job (see POST /api/ingest for when a 202 + job id is
    returned). 404 means: unknown id, finished job evicted after
    _INGEST_JOB_TTL_S, or the server restarted (registry is in-memory) — in
    every case re-POSTing the payload is safe: the payload-hash replay either
    replays the stored result or re-runs cleanly."""
    snap = _ingest_job_snapshot(job_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"unknown ingest job {job_id}")
    return IngestJobStatus(**snap)


@router.get("/clusters", response_model=ClustersOut)
def duplicate_clusters(
    req: Request,
    min_cos: float | None = Query(default=None),
) -> ClustersOut:
    """Presentation compression using star semantics (members never chain).

    Defaults to cfg.near_dup_threshold, the near-duplicate gate's own cutoff.
    This view only compresses presentation; it never changes routing, scores,
    or gates.
    """
    cfg = _cfg(req)
    threshold = cfg.near_dup_threshold if min_cos is None else min_cos
    if not 0.5 <= threshold < 1.0:
        raise HTTPException(status_code=422, detail="min_cos must be in [0.5, 1.0)")
    result = _storage(req).duplicate_clusters(threshold)
    return ClustersOut(threshold=threshold, **result)


@router.get("/reports", response_model=list[StoredReport])
def list_reports(
    req: Request,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> list[StoredReport]:
    start, end = _checked_date_range(date_from, date_to)
    cfg, clf = _cfg(req), _classifier(req)
    rows = _storage(req).list_reports(limit=limit, offset=offset, date_from=start, date_to=end)
    return [_report_band(row, clf, cfg) for row in rows]


@router.get("/reports/{report_id}", response_model=StoredReport)
def get_report(report_id: int, req: Request) -> StoredReport:
    stored = _storage(req).get_report(report_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"report {report_id} not found")
    return _report_band(stored, _classifier(req), _cfg(req))


@router.get("/reports/{report_id}/explanation", response_model=ExplanationOut)
def report_explanation(report_id: int, req: Request) -> ExplanationOut:
    """Human explanation for a stored prediction. Template is deterministic and
    always present; the ollama rewording (when enabled) is cached in the
    precomputed table under sha256(text + model_version + threshold)."""
    cfg, storage = _cfg(req), _storage(req)
    stored = storage.get_report(report_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"report {report_id} not found")
    if stored.prediction is None:
        raise HTTPException(status_code=409, detail=f"report {report_id} has no prediction")
    stored = _report_band(stored, _classifier(req), cfg)
    return build_explanation(
        stored.prediction, stored.report.text, storage,
        use_llm=cfg.explain_llm, url=cfg.ollama_url,
        model=cfg.ollama_model, timeout=cfg.explain_timeout_s,
        threshold=flag_threshold(_classifier(req)),
    )


@router.get("/density", response_model=list[DensityRow])
def density(
    req: Request,
    by: str = Query(default="site", pattern="^(site|activity|contractor)$"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
) -> list[DensityRow]:
    """Precursor-density ranking by structured facet — the PS-core view.
    Computed as a single SQL GROUP BY (SEV3-1: the old path materialized
    every row + one extra query per row, ~170ms at 5k rows and silently
    capped at the latest 100k)."""
    start, end = _checked_date_range(date_from, date_to)
    thr = flag_threshold(_classifier(req))
    return [DensityRow(**row) for row in _storage(req).density_aggregate(
        by, thr, date_from=start, date_to=end)]


@router.get("/rules", response_model=list[RuleInfo])
def rules() -> list[RuleInfo]:
    """All 9 IOGP rules; out-of-scope ones are declared, never faked."""
    return [RuleInfo(key=k, **meta) for k, meta in RULE_DISPLAY.items()]


@router.get("/patterns", response_model=list[PatternRow])
def patterns(
    req: Request,
    min_n: int = Query(default=2, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    kind: str = Query(default="site_activity", pattern="^(site_activity|activity_barrier)$"),
) -> list[PatternRow]:
    """Live SQLite co-occurrence at the current classifier threshold.

    Barrier cells use triggered canonical barrier-absence gates, not inferred
    labels. Lift uses all scored reports as its baseline; CIs describe the
    cell's flag rate, not lift. No rule tag is inferred from gate names.
    """
    cells = _storage(req).patterns_aggregate(kind, flag_threshold(_classifier(req)), min_n)
    rows: list[PatternRow] = []
    for cell in cells:
        n = cell["n"]
        rate = cell["n_flagged"] / n
        baseline = cell["baseline"]
        lo, hi = _wilson(rate, n)
        rows.append(PatternRow(
            kind=kind, activity=cell["activity"], site=cell["site"], barrier=cell["barrier"],
            n=n, sif_rate=round(rate, 4),
            lift=round(rate / baseline, 3) if baseline > 0 else 0.0,
            ci_low=round(lo, 4), ci_high=round(hi, 4),
        ))
    rows.sort(key=lambda r: (-r.lift, -r.n))
    return rows[:limit]


@router.post("/review", response_model=StoredOverride, status_code=201)
def create_override(body: OverrideWrite, req: Request) -> StoredOverride:
    """HSE override -> stored as future gold. 'Model proposes, HSE disposes.'
    Field + value vocabulary are validated (OverrideWrite, SEV2-3); history is
    append-only — GET /review/export collapses to latest-wins per
    (report_id, field) for the gold lineage."""
    storage = _storage(req)
    if storage.get_report(body.report_id) is None:
        raise HTTPException(status_code=404, detail=f"report {body.report_id} not found")
    ov_id = storage.add_override(body)
    return next(o for o in storage.list_overrides(body.report_id) if o.id == ov_id)


@router.get("/review", response_model=list[StoredOverride])
def list_overrides(req: Request, report_id: int | None = Query(default=None)) -> list[StoredOverride]:
    """The override queue — exported downstream as future gold labels
    (source column separates 'override' from 'blind_gold'; eval joins blind_gold only)."""
    return _storage(req).list_overrides(report_id)


@router.get("/review/export")
def export_overrides(req: Request) -> PlainTextResponse:
    """Future-gold export — application/x-ndjson, one JSON object per line.
    Same-origin for the dashboard (served by this same process), so a plain
    fetch().then(r => r.text()) reads it — no CORS involved; an empty queue
    is a valid empty body (zero lines). Latest-wins per (report_id, field)
    with exact-duplicate collapse (SEV2-3). Line schema, keys in order:
      report_id   int        -- the ingested report
      field       str        -- 'sif_label' | 'rules' | 'notes'
      value       str        -- winning new_value (e.g. 'sif_potential')
      old_value   str | null -- what the winning row replaced
      labeler     str
      source      str        -- 'override' | 'blind_gold'
      rationale   str | null
      decided_at  str        -- created_at of the winning row (UTC ISO)
      override_id int        -- winning overrides.id
      supersedes  list[int]  -- earlier override ids the winner replaced
    Full semantics on storage.export_overrides."""
    rows = _storage(req).export_overrides()
    body = "".join(json.dumps(r, ensure_ascii=True) + "\n" for r in rows)
    return PlainTextResponse(body, media_type="application/x-ndjson")


@router.get("/actions", response_model=list[ActionOut])
def list_actions(
    req: Request,
    report_id: int | None = Query(default=None, ge=1),
) -> list[ActionOut]:
    return [ActionOut(**row) for row in _storage(req).list_actions(report_id=report_id)]


@router.post("/actions", response_model=ActionOut, status_code=201)
def create_action(body: ActionCreate, req: Request) -> ActionOut:
    storage = _storage(req)
    if storage.get_report(body.report_id) is None:
        raise HTTPException(status_code=404, detail=f"report {body.report_id} not found")
    override = next((item for item in storage.list_overrides(body.report_id)
                     if item.id == body.override_id), None)
    if override is None:
        raise HTTPException(status_code=404, detail="override not found for report")
    owner = body.owner.strip()
    if not owner:
        raise HTTPException(status_code=422, detail="owner must not be blank")
    if storage.get_action_by_override(body.override_id) is not None:
        raise HTTPException(status_code=409, detail="an action already exists for this decision")
    try:
        action_id = storage.add_action(
            body.report_id, body.override_id, owner, body.due_date, body.status
        )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=409, detail="an action already exists for this decision") from exc
        raise
    result = storage.get_action(action_id)
    if result is None:
        raise HTTPException(status_code=500, detail="created action could not be read")
    return ActionOut(**result)


@router.patch("/actions/{action_id}", response_model=ActionOut)
def patch_action(action_id: int, body: ActionPatch, req: Request) -> ActionOut:
    storage = _storage(req)
    if storage.get_action(action_id) is None:
        raise HTTPException(status_code=404, detail=f"action {action_id} not found")
    changes = {key: value for key, value in body.model_dump(exclude_unset=True).items()
               if value is not None or key == "due_date"}
    if not changes:
        raise HTTPException(status_code=422, detail="at least one action field is required")
    if "owner" in changes:
        changes["owner"] = changes["owner"].strip()
        if not changes["owner"]:
            raise HTTPException(status_code=422, detail="owner must not be blank")
    if not storage.update_action(action_id, **changes):
        raise HTTPException(status_code=404, detail=f"action {action_id} not found")
    result = storage.get_action(action_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"action {action_id} not found")
    return ActionOut(**result)


@router.delete("/actions/{action_id}", status_code=204)
def delete_action(action_id: int, req: Request) -> None:
    if not _storage(req).delete_action(action_id):
        raise HTTPException(status_code=404, detail=f"action {action_id} not found")


def _calibration_block(clf: Classifier) -> dict[str, Any]:
    model_path = getattr(clf, "_onnx_path", None)
    metrics_path = Path(model_path).parent / "metrics.json" if model_path else REPO_ROOT / "artifacts/models/masked-v2/metrics.json"
    empty = {"ece": None, "brier": None, "calibration_n": None, "calibration_split": None}
    try:
        calibration = json.loads(metrics_path.read_text(encoding="utf-8"))["calibration"]
        test = calibration["test"]
        ece = float(test["ece_p_cal"])
        brier = float(test["brier_p_cal"])
        n = int(test["n"])
        if not math.isfinite(ece) or not math.isfinite(brier) or n < 0:
            raise ValueError("invalid calibration values")
        return {
            "ece": ece,
            "brier": brier,
            "calibration_n": n,
            "calibration_split": "test",
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("calibration metrics unavailable at %s (%s: %s)",
                    metrics_path, type(exc).__name__, exc)
        return empty


@router.get("/metrics/summary", response_model=MetricsSummary)
def metrics_summary(req: Request) -> MetricsSummary:
    """Live report KPIs and artifact-held calibration summary."""
    storage, clf = _storage(req), _classifier(req)
    agg = storage.metrics_aggregate(flag_threshold(clf))
    return MetricsSummary(
        **agg,
        n_overrides=storage.count_overrides(),
        model_version=clf.model_version,
        classifier=type(clf).__name__,
        **_calibration_block(clf),
        flag_threshold=flag_threshold(clf),
        gray_band_low=getattr(clf, "gray_band_low", None),
        gray_band_high=getattr(clf, "gray_band_high", None),
    )
