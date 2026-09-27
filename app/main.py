"""FastAPI entrypoint. Bare-metal run: `.venv/bin/python -m app.main`
(uvicorn + SQLite, no docker on the critical path — ARCHITECTURE runtime).

Observability (A5, backend-stack-decision §4): JSON logs via structlog's
stdlib ProcessorFormatter — every existing logging.getLogger call site emits
JSON with no per-module edit — and Prometheus RED metrics (Rate, Errors,
Duration) exported at /metrics. OpenTelemetry was rejected there: no
collector/backend infrastructure in an air-gapped demo."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from .classifier import MockClassifier, RealOnnxClassifier, build_classifier, flag_threshold
from .config import REPO_ROOT, Settings
from .embedder import configure as configure_embedder
from .gates import (
    gate_barrier_absence,
    gate_chunked_low_score,
    gate_severity_watch,
    gate_verdict_stability,
    gate_well_control_watch,
)
from .routes import router
from .schemas import HealthOut
from .storage import SQLiteStorage

log = logging.getLogger(__name__)

DASHBOARD_DIST = REPO_ROOT / "dashboard" / "dist"

# -- Prometheus RED metrics -------------------------------------------------
# Rate = http_requests_total; Errors = the same counter's status labels
# (incl. 'exception' for unhandled crashes); Duration = histogram. Labels use
# the route TEMPLATE, never the raw path, to bound cardinality. Module level:
# create_app() may be called repeatedly (tests) without re-registering.
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", "HTTP requests processed", ["method", "route", "status"]
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


def _observe(scope: Scope, status: str, start: float) -> None:
    method = scope.get("method", "-")
    route = getattr(scope.get("route"), "path", "unmatched")
    HTTP_REQUESTS_TOTAL.labels(method=method, route=route, status=status).inc()
    HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(
        time.perf_counter() - start
    )


class RedMetricsMiddleware:
    """Pure-ASGI RED middleware. Duration is observed at response-start
    (headers), so slow body streaming is not measured; unhandled exceptions
    reaching this layer are labelled status='exception' — the outermost
    ServerErrorMiddleware is outside us and still returns the 500."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                _observe(scope, str(message["status"]), start)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            _observe(scope, "exception", start)
            raise


class SpaStaticFiles(StaticFiles):
    """StaticFiles with the hash-router fallback: a GET that matches no real
    file under dist/ serves index.html instead of Starlette's raw 404, so a
    reviewer typing /queue (no #) still lands in the React shell. /api and
    /assets stay loud 404s: unmatched /api paths keep their JSON error (an
    HTML shell answering an API call hides breakage), and a missing hashed
    asset must not masquerade as a 200 HTML page. Only 404 is intercepted —
    405/401 propagate unchanged."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            full = scope.get("path", "")
            reserved = full == "/api" or full.startswith(("/api/", "/assets/"))
            if exc.status_code != 404 or reserved:
                raise
            return await self._deep_link_fallback(full, scope)

    async def _deep_link_fallback(self, full_path: str, scope: Scope) -> Response:
        """Path deep links (/report/4534) otherwise bounce off the hash
        router: the shell loads, but HashRouter only reads the hash, sees no
        route, and lands on the default queue. Injecting a one-line bootstrap
        that rewrites the path into the hash BEFORE the app mounts makes both
        link styles work: /report/4534 becomes /#/report/4534.

        index.html is re-read per request, never cached: it carries hashed
        asset filenames that change on every build, and a cached copy served
        404s for every asset until the process restarts (seen 2026-09-26)."""
        index = Path(self.directory) / "index.html"
        try:
            raw = index.read_text(encoding="utf-8")
        except OSError:
            return await super().get_response("index.html", scope)
        boot = (
            "<script>/* deep-link shim: path -> hash before the router"
            " mounts */(function(){var p=location.pathname;"
            "if(p&&p!=='/'&&location.hash.indexOf('#/')!==0){"
            "location.replace('/#'+p+location.search);}})();</script>"
        )
        if "<head>" in raw and "deep-link shim" not in raw:
            raw = raw.replace("<head>", "<head>" + boot, 1)
        # no-cache: the shell references hashed assets that change per build.
        return Response(
            content=raw,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )


def configure_logging() -> None:
    """Route ALL stdlib logging (app modules, uvicorn access/error) through
    structlog's JSON renderer. The shared processor chain runs both for
    structlog-API loggers and as foreign_pre_chain for stdlib records, so a
    plain `logging.getLogger(__name__)` anywhere emits JSON unchanged."""
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared,
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # uvicorn installs its own handlers + propagate=False at startup; strip
    # them so access/error logs flow through root and render as JSON too.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True


configure_logging()


# -- stored gate_states schema backfill --------------------------------------
# Predictions persisted before the current gate registry carry short
# snapshots: run_gates (app/gates.py) appends newer gates so original indexes
# hold. Older rows lack these appended states, so /metrics/summary and stored
# report routing must be refreshed from the row's saved prediction fields.
# The recomputed gates use the stored text, score, control tag and ensemble
# statistics — no model call or embedding (near_dup and original entries are
# left exactly as stored) — so a one-shot boot backfill is safe and ~1 s over the 5k-row
# demo DB. The version marker lives in the precomputed table, not schema_meta:
# this is the gate registry's schema, not the database's.
GATE_SCHEMA_VERSION = 4
_GATE_SCHEMA_KEY = "gate_schema_version"


def _recompute_gate_states(existing: list[dict], text: str, score: float,
                           well_control: bool, flag_thr: float,
                           verdict_stability: float | None,
                           n_variants: int | None) -> list[dict]:
    """Append every run_gates entry missing from an old snapshot, in the same
    canonical order run_gates emits. `chunked` is not persisted (storage
    rebuilds stored predictions with the schema default False), so
    chunked_low_score is computed with False — identical to what the row was
    stored with. Legacy NULL ensemble fields mean a stable single-shot row."""
    computed = {
        "well_control_watch": gate_well_control_watch(well_control, score, flag_thr),
        "chunked_low_score": gate_chunked_low_score(False, score),
        "severity_watch": gate_severity_watch(text, score, flag_thr),
        "energy_isolation_absent": gate_barrier_absence(text, "energy_isolation_absent"),
        "gas_test_absent": gate_barrier_absence(text, "gas_test_absent"),
        "permit_absent": gate_barrier_absence(text, "permit_absent"),
        "fire_watch_absent": gate_barrier_absence(text, "fire_watch_absent"),
        "standby_absent": gate_barrier_absence(text, "standby_absent"),
        "atmosphere_unmonitored": gate_barrier_absence(text, "atmosphere_unmonitored"),
        "fall_protection_absent": gate_barrier_absence(text, "fall_protection_absent"),
        "verdict_stability": gate_verdict_stability(
            verdict_stability if verdict_stability is not None else 1.0,
            n_variants if n_variants is not None else 1,
        ),
    }
    names = {g.get("name") for g in existing}
    out = list(existing)
    out.extend(g.model_dump() for name, g in computed.items() if name not in names)
    return out


def _backfill_gate_states(storage: SQLiteStorage, flag_thr: float) -> None:
    try:
        stored = storage.load_precomputed(_GATE_SCHEMA_KEY)
        version = int(stored.get("version", 0)) if isinstance(stored, dict) else 0
    except Exception:
        log.warning("stored gate_states marker is invalid; backfill will run", exc_info=True)
        version = 0
    if version >= GATE_SCHEMA_VERSION:
        return
    try:
        n = storage.rewrite_gate_states(
            lambda existing, text, score, wc, stability, n_variants: _recompute_gate_states(
                existing, text, score, wc, flag_thr, stability, n_variants)
        )
    except Exception:
        # The transaction rolled back; the marker stays unset so the next
        # boot retries. Never block bring-up on a backfill.
        log.exception("stored gate_states backfill failed; snapshots left unchanged")
        return
    storage.save_precomputed(_GATE_SCHEMA_KEY, {"version": GATE_SCHEMA_VERSION})
    log.info("stored gate_states backfilled to schema v%d (%d rows changed)",
             GATE_SCHEMA_VERSION, n)


def create_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or Settings()
    configure_embedder(cfg.embed_model_dir)  # lazy MiniLM load, first embed pays it

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.storage = SQLiteStorage(
            cfg.db_path, cfg.embed_index_dir, busy_timeout_ms=cfg.db_busy_timeout_ms
        )
        _backfill_gate_states(app.state.storage, flag_threshold(app.state.classifier))
        yield
        app.state.storage.close()

    app = FastAPI(
        title="SIF-Precursor Detection Engine",
        version=cfg.api_version,
        description="Triage + extraction for high-energy precursor reports "
        "(SIH 2026 PS 26165, OIL India). Triage score — never prediction accuracy.",
        lifespan=lifespan,
    )
    app.state.cfg = cfg
    app.state.classifier = build_classifier(cfg.model_path, cfg.model_version)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RedMetricsMiddleware)

    @app.get("/api/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(
            status="ok",
            api_version=cfg.api_version,
            model_version=app.state.classifier.model_version,
            classifier=type(app.state.classifier).__name__,
            n_reports=app.state.storage.count_reports(),
            n_overrides=app.state.storage.count_overrides(),
        )

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

    app.include_router(router, prefix="/api")
    # Bare-metal demo spine: the prebuilt React dashboard is served by the
    # same process (ARCHITECTURE: uvicorn + static React + SQLite, no docker).
    # Mounted LAST so /api/* routes always win; SpaStaticFiles adds the
    # hash-router fallback for /queue-style deep links. Requires `npm run
    # build` to have produced dashboard/dist — run.sh checks for it at bring-up.
    if DASHBOARD_DIST.is_dir():
        app.mount("/", SpaStaticFiles(directory=DASHBOARD_DIST, html=True), name="dashboard")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    cfg = Settings()
    # log_config=None: keep OUR structlog JSON handler authoritative instead
    # of letting uvicorn reinstall its text handlers. The app OBJECT is passed
    # (not the "app.main:app" string) — re-importing the module would run its
    # module-level Prometheus collectors twice into the default registry and
    # crash startup with DuplicateTimeseries.
    uvicorn.run(app, host=cfg.host, port=cfg.port, reload=False, log_config=None)


if __name__ == "__main__":
    main()