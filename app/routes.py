"""API routes. REST only, no websockets (fullstack-architect §3).

All endpoints live under /api except /api/health (registered in main.py).
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from .classifier import Classifier, validate_spans
from .config import REPO_ROOT, Settings
from .embedder import embed_text
from .explain import build_explanation
from .gates import run_gates
from .ingest import parse_records, validate_rows
from .schemas import (
    RULE_DISPLAY,
    DensityRow,
    ExplanationOut,
    IngestRequest,
    IngestResult,
    MetricsSummary,
    OverrideIn,
    PatternRow,
    PredictionOut,
    ReportIn,
    RuleInfo,
    StoredOverride,
    StoredReport,
)
from .storage import Storage

router = APIRouter()

FLAG_THRESHOLD = 0.5  # triage flag cutoff for density/pattern aggregates


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
def classify(body: ReportIn, req: Request, explain: bool = Query(default=False)) -> PredictionOut:
    """Stateless single-report classification (no store — use /ingest to persist).
    ?explain=1 attaches a human explanation: the deterministic template is
    always present; the optional ollama rewording is null whenever the LLM is
    unavailable (async-safe — every call is bounded by the 8 s timeout and
    falls back silently)."""
    cfg = _cfg(req)
    pred = _predict_with_gates(_storage(req), _classifier(req), cfg, body.text)
    if explain:
        pred.explanation = build_explanation(
            pred, body.text, _storage(req),
            use_llm=cfg.explain_llm, url=cfg.ollama_url,
            model=cfg.ollama_model, timeout=cfg.explain_timeout_s,
        )
    return pred


@router.post("/ingest", response_model=IngestResult)
def ingest(body: IngestRequest, req: Request) -> IngestResult:
    cfg, storage, clf = _cfg(req), _storage(req), _classifier(req)
    try:
        raw_rows = parse_records(body.records, body.csv)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    reports, errors = validate_rows(raw_rows, source=body.source, column_mapping=body.column_mapping)
    ids: list[int] = []
    # ponytail: classify inline per row. Fine for the mock and for demo-scale
    # batches; the real ONNX path needs the batch-worker queue (fullstack
    # architect SEV finding: single-text calls can't hit the bulk SLA).
    for report in reports:
        pred = _predict_with_gates(storage, clf, cfg, report.text)
        rid = storage.add_report(report)
        storage.add_prediction(rid, pred)
        storage.add_embedding(rid, embed_text(report.text))
        ids.append(rid)
    return IngestResult(
        received=len(raw_rows),
        accepted=len(ids),
        rejected=len(errors),
        report_ids=ids,
        errors=errors,
    )


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
    precomputed table under sha256(text + model_version)."""
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
    )


@router.get("/density", response_model=list[DensityRow])
def density(
    req: Request,
    by: str = Query(default="site", pattern="^(site|activity|contractor)$"),
) -> list[DensityRow]:
    """Precursor-density ranking by structured facet — the PS-core view."""
    groups: dict[str, list[float]] = {}
    for stored in _storage(req).list_reports(limit=100_000):
        key = getattr(stored.report, by) or "(unspecified)"
        groups.setdefault(key, []).append(
            stored.prediction.sif_score if stored.prediction else 0.0
        )
    rows = [
        DensityRow(
            key=k,
            n_reports=len(scores),
            n_flagged=sum(1 for s in scores if s >= FLAG_THRESHOLD),
            sif_rate=round(sum(1 for s in scores if s >= FLAG_THRESHOLD) / len(scores), 4),
            mean_score=round(sum(scores) / len(scores), 4),
        )
        for k, scores in groups.items()
    ]
    rows.sort(key=lambda r: (-r.sif_rate, -r.n_reports))
    return rows


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
    baseline = sum(1 for _, sc in scored if sc >= FLAG_THRESHOLD) / len(scored)
    cells: dict[tuple[str, str], list[float]] = {}
    for s, sc in scored:
        key = (s.report.activity or "(unspecified)", s.report.site or "(unspecified)")
        cells.setdefault(key, []).append(sc)
    rows: list[PatternRow] = []
    for (activity, site), scores in cells.items():
        n = len(scores)
        if n < min_n:
            continue
        rate = sum(1 for s in scores if s >= FLAG_THRESHOLD) / n
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
def create_override(body: OverrideIn, req: Request) -> StoredOverride:
    """HSE override -> stored as future gold. 'Model proposes, HSE disposes.'"""
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


@router.get("/metrics/summary", response_model=MetricsSummary)
def metrics_summary(req: Request) -> MetricsSummary:
    storage, clf = _storage(req), _classifier(req)
    stored = storage.list_reports(limit=100_000)
    scores = [s.prediction.sif_score for s in stored if s.prediction]
    gate_counts: dict[str, int] = {}
    for s in stored:
        if s.prediction:
            for g in s.prediction.gate_states:
                if g.triggered:
                    gate_counts[g.name] = gate_counts.get(g.name, 0) + 1
    n_flagged = sum(1 for sc in scores if sc >= FLAG_THRESHOLD)
    return MetricsSummary(
        n_reports=len(stored),
        n_flagged=n_flagged,
        flag_rate=round(n_flagged / len(scores), 4) if scores else 0.0,
        mean_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
        n_overrides=storage.count_overrides(),
        gate_trigger_counts=gate_counts,
        model_version=clf.model_version,
        classifier=type(clf).__name__,
    )
