"""FastAPI entrypoint. Bare-metal run: `.venv/bin/python -m app.main`
(uvicorn + SQLite, no docker on the critical path — ARCHITECTURE runtime)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .classifier import MockClassifier, RealOnnxClassifier, build_classifier
from .config import REPO_ROOT, Settings
from .embedder import configure as configure_embedder
from .routes import router
from .schemas import HealthOut
from .storage import SQLiteStorage

DASHBOARD_DIST = REPO_ROOT / "dashboard" / "dist"


def create_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or Settings()
    configure_embedder(cfg.embed_model_dir)  # lazy MiniLM load, first embed pays it

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.storage = SQLiteStorage(cfg.db_path, cfg.embed_index_dir)
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

    app.include_router(router, prefix="/api")
    # Bare-metal demo spine: the prebuilt React dashboard is served by the
    # same process (ARCHITECTURE: uvicorn + static React + SQLite, no docker).
    # Mounted LAST so /api/* routes always win. Requires `npm run build` to
    # have produced dashboard/dist — run.sh checks for it at bring-up.
    if DASHBOARD_DIST.is_dir():
        app.mount("/", StaticFiles(directory=DASHBOARD_DIST, html=True), name="dashboard")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    cfg = Settings()
    uvicorn.run("app.main:app", host=cfg.host, port=cfg.port, reload=False)


if __name__ == "__main__":
    main()
