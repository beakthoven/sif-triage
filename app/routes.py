"""API routes. REST only, no websockets (fullstack-architect §3).

All endpoints live under /api except /api/health (registered in main.py).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from .classifier import Classifier, flag_threshold, validate_spans
from .config import REPO_ROOT, Settings
from .embedder import embed_texts
from .explain import build_explanation
from .gates import run_gates
from .ingest import parse_records, text_hash, validate_rows
from .schemas import (
    RULE_DISPLAY,
    DensityRow,
    ExplanationOut,
    IngestRequest,
    IngestResult,
    MetricsSummary,
    OverrideWrite,
    PatternRow,
    PredictionOut,
    ReportIn,
    RuleInfo,
    StoredOverride,
    StoredReport,
)
from .storage import Storage

router = APIRouter()

FLAG_THRESHOLD = 0.5  # fallback only — classifier.flag_threshold (D19 tuned
# operating point from the artifact's metrics.json) wins whenever present

# /ingest classification batch (D25): windows across rows share session.run
# calls of this width — the measured sweet spot for the int8 artifact here.
INGEST_BATCH = 32


def _cfg(req: Request) -> Settings:
    return req.app.state.cfg


def _storage(req: Request) -> Storage:
    return req.app.state.storage


def _classifier(req: Request) -> Classifier:
    return req.app.state.classifier


def _predict_with_gates(storage: Storage, clf: Classifier, cfg: Settings, text: str) -> PredictionOut:
    pred = clf.predict(text)
    # Span invariant re-checked against the canonical text at the boundary.
    pred.evidence_spans = validate_spans(text, pred.evidence_spans)
    pred.gate_states = run_gates(text, pred.sif_score, storage, cfg)
    return pred


def _wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


@router.post("/classify", response_model=PredictionOut)
def classify(
    body: ReportIn,
    req: Request,
    explain: bool = Query(default=False),
    llm: bool = Query(default=True),
) -> PredictionOut:
    """Stateless single-report classification (no store — use /ingest to persist).
    ?explain=1 attaches a human explanation: the deterministic template is
    always present; the optional ollama rewording is null whenever the LLM is
    unavailable (async-safe — every call is bounded by the 8 s timeout and
    falls back silently). ?llm=0 pins the template only — the live-paste demo
    path: a novel text is never in the reword cache, and a cold reword would
    stall the card for up to 2x the timeout on CPU."""
    cfg = _cfg(req)
    clf = _classifier(req)
    pred = _predict_with_gates(_storage(req), clf, cfg, body.text)
    if explain:
        pred.explanation = build_explanation(
            pred, body.text, _storage(req),
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


@router.post("/ingest", response_model=IngestResult)
def ingest(body: IngestRequest, req: Request) -> IngestResult:
    cfg, storage, clf = _cfg(req), _storage(req), _classifier(req)
    # Idempotent replay: byte-identical re-POST of an already-ingested payload
    # returns the original result untouched (no double count — SEV2-2).
    payload_hash = _payload_hash(body)
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
    skipped_duplicates = 0
    for r in reports:
        th = text_hash(r.text)
        if th in seen:
            skipped_duplicates += 1
            continue
        seen.add(th)
        unique.append((r, th))
    # Phase 1 — classify + embed + gates, NO writes (D25 bulk path: inline
    # single-everything measured 5.33/s vs the >=30/s SLA; classify is batched
    # only when the loaded quant is batch-exact — int8's per-tensor dynamic
    # quantization shifts logits by batchmate, so per-row keeps stored scores
    # identical to the interactive path; embeddings are batch-computed once
    # per chunk and reused for the near-dup gate AND storage; the corpus-tier
    # nearest is one matmul per chunk).
    # Behavior note (SEV2-3 fix): the old flow interleaved writes per row so
    # the near-dup gate also saw earlier rows of the SAME request. Phase-1
    # gates now see committed rows only; exact duplicates within the batch
    # are skipped above instead of bannered. Rows stay in request order.
    prepared: list[tuple[ReportIn, PredictionOut, np.ndarray, str]] = []
    for off in range(0, len(unique), INGEST_BATCH):
        chunk = unique[off : off + INGEST_BATCH]
        texts = [r.text for r, _ in chunk]
        if getattr(clf, "supports_exact_batch", False):
            preds = clf.classify_batch(texts, batch_size=INGEST_BATCH)
        else:
            preds = [clf.predict(t) for t in texts]
        vecs = embed_texts(texts)
        base_hits = storage.nearest_base_batch(vecs)
        for (report, th), pred, vec, base_hit in zip(chunk, preds, vecs, base_hits):
            pred.evidence_spans = validate_spans(report.text, pred.evidence_spans)
            pred.gate_states = run_gates(report.text, pred.sif_score, storage, cfg,
                                         vec=vec, base_hit=base_hit)
            prepared.append((report, pred, vec, th))
    # Phase 2 — ONE transaction: every row lands or none do. A failure here
    # rolls the whole batch back and the client gets an honest error instead
    # of a silent partial commit it cannot distinguish from "nothing stored".
    try:
        ids, skipped_duplicates_db = storage.add_ingest_batch(prepared)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"ingest failed and was rolled back; nothing stored: "
            f"{type(exc).__name__}: {exc}",
        ) from exc
    skipped_duplicates += skipped_duplicates_db
    result = IngestResult(
        received=len(raw_rows),
        accepted=len(ids),
        rejected=len(errors),
        report_ids=ids,
        errors=errors,
        skipped_duplicates=skipped_duplicates,
    )
    # Record the replay entry only after success (a failed ingest leaves no
    # entry, so a retry re-runs cleanly; per-row dedup covers the gap).
    storage.record_ingest_payload(payload_hash, result.model_dump())
    return result


@router.get("/reports", response_model=list[StoredReport])
def list_reports(
    req: Request,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[StoredReport]:
    return _storage(req).list_reports(limit=limit, offset=offset)


@router.get("/reports/{report_id}", response_model=StoredReport)
def get_report(report_id: int, req: Request) -> StoredReport:
    stored = _storage(req).get_report(report_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"report {report_id} not found")
    return stored


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
) -> list[DensityRow]:
    """Precursor-density ranking by structured facet — the PS-core view.
    Computed as a single SQL GROUP BY (SEV3-1: the old path materialized
    every row + one extra query per row, ~170ms at 5k rows and silently
    capped at the latest 100k)."""
    thr = flag_threshold(_classifier(req))
    return [DensityRow(**row) for row in _storage(req).density_aggregate(by, thr)]


@router.get("/rules", response_model=list[RuleInfo])
def rules() -> list[RuleInfo]:
    """All 9 IOGP rules; out-of-scope ones are declared, never faked."""
    return [RuleInfo(key=k, **meta) for k, meta in RULE_DISPLAY.items()]


PATTERNS_FILE_DEFAULT = REPO_ROOT / "artifacts" / "patterns" / "patterns.json"


def _patterns_file() -> Path:
    return Path(os.environ.get("SIF_PATTERNS_FILE", str(PATTERNS_FILE_DEFAULT)))


def _precomputed_patterns(kind: str) -> list[PatternRow] | None:
    """Precomputed lift-ranked patterns mined from the synthetic facet corpus
    (data_pipeline/pattern_mine.py). None when the file is absent — the caller
    then falls back to live DB aggregation. Read per request; the file is
    ~50 KB so re-parsing is noise at demo QPS (precompute doctrine)."""
    path = _patterns_file()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    cells = data["site_x_activity"] if kind == "site_activity" else data["activity_x_barrier"]
    return [
        PatternRow(
            kind=kind,
            activity=c["activity"],
            site=c.get("site"),
            barrier=c.get("barrier"),
            rule=c.get("rule"),
            n=c["n"],
            sif_rate=c["sif_rate"],
            lift=c["lift"],
            ci_low=c["ci_low"],
            ci_high=c["ci_high"],
        )
        for c in cells
    ]


@router.get("/patterns", response_model=list[PatternRow])
def patterns(
    req: Request,
    min_n: int = Query(default=2, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    kind: str = Query(default="site_activity", pattern="^(site_activity|activity_barrier)$"),
) -> list[PatternRow]:
    """Lift-ranked precursor-pattern co-occurrence with n + Wilson CIs.
    Serves the precomputed synthetic-corpus stats (artifacts/patterns/
    patterns.json) when present; falls back to live DB aggregation
    (site×activity only — ingested reports carry no barrier facet) when the
    file is absent, so the override-queue demo path still answers.
    Structured facets only — no runtime LLM tagging (adjudicated)."""
    pre = _precomputed_patterns(kind)
    if pre is not None:
        return [r for r in pre if r.n >= min_n][:limit]
    if kind == "activity_barrier":
        return []
    stored = _storage(req).list_reports(limit=100_000)
    scored = [(s, s.prediction.sif_score) for s in stored if s.prediction]
    if not scored:
        return []
    thr = flag_threshold(_classifier(req))
    baseline = sum(1 for _, sc in scored if sc >= thr) / len(scored)
    cells: dict[tuple[str, str], list[float]] = {}
    for s, sc in scored:
        key = (s.report.activity or "(unspecified)", s.report.site or "(unspecified)")
        cells.setdefault(key, []).append(sc)
    rows: list[PatternRow] = []
    for (activity, site), scores in cells.items():
        n = len(scores)
        if n < min_n:
            continue
        rate = sum(1 for s in scores if s >= thr) / n
        lift = rate / baseline if baseline > 0 else 0.0
        lo, hi = _wilson(rate, n)
        rows.append(PatternRow(
            activity=activity, site=site, n=n,
            sif_rate=round(rate, 4), lift=round(lift, 3),
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
    """Future-gold export, one JSON object per line (application/x-ndjson).
    Latest-wins per (report_id, field) with exact-duplicate collapse; line
    schema is documented on storage.export_overrides (SEV2-3)."""
    rows = _storage(req).export_overrides()
    body = "".join(json.dumps(r, ensure_ascii=True) + "\n" for r in rows)
    return PlainTextResponse(body, media_type="application/x-ndjson")


@router.get("/metrics/summary", response_model=MetricsSummary)
def metrics_summary(req: Request) -> MetricsSummary:
    storage, clf = _storage(req), _classifier(req)
    # SQL/cached aggregate over ALL rows (SEV3-1: the old path materialized
    # 100k StoredReport objects per call and silently dropped rows beyond it).
    agg = storage.metrics_aggregate(flag_threshold(clf))
    return MetricsSummary(
        **agg,
        n_overrides=storage.count_overrides(),
        model_version=clf.model_version,
        classifier=type(clf).__name__,
    )
