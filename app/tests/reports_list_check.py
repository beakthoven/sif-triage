"""Report-list API parity and text-annotation cache checks.
Run: .venv/bin/python -m app.tests.reports_list_check
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.classifier import MockClassifier, deterministic_cue_spans, rule_cue_hits
from app.config import Settings
from app.routes import _cached_cue_spans, _cached_rule_cues, _report_band, router
from app.schemas import PredictionOut, ReportIn, StoredReport
from app.storage import SQLiteStorage


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        storage = SQLiteStorage(Path(tmp) / "reports.db")
        classifier = MockClassifier()
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.state.storage = storage
        app.state.classifier = classifier
        app.state.cfg = Settings()
        try:
            text = "During maintenance the worker entered a confined space without a gas test."
            old = storage.add_report(ReportIn(text=text, date="2025-01-01", site="A"))
            latest = storage.add_report(ReportIn(text=text, date="2026-01-01", site="B"))
            pending = storage.add_report(ReportIn(text="Report awaiting scoring", date="2026-01-02"))
            long_text = "Worker fell from scaffold without a harness. " * 30
            long_id = storage.add_report(ReportIn(text=long_text, date="2026-01-03"))
            storage.add_prediction(old, PredictionOut(
                sif_score=0.25, rule_probs={}, well_control=False,
                evidence_spans=[], gate_states=[], model_version="test",
            ))
            storage.add_prediction(latest, PredictionOut(
                sif_score=0.75, rule_probs={}, well_control=False,
                evidence_spans=[], gate_states=[], model_version="test",
            ))
            storage.add_prediction(long_id, PredictionOut(
                sif_score=0.75, rule_probs={}, well_control=False,
                evidence_spans=[], gate_states=[], model_version="test",
            ))
            with TestClient(app) as client:
                _cached_rule_cues.cache_clear()
                _cached_cue_spans.cache_clear()
                query = "/api/reports?limit=2&offset=1"
                response = client.get(query)
                assert response.status_code == 200
                assert [row["id"] for row in response.json()] == [pending, latest]
                assert response.json()[0]["prediction"] is None
                assert client.get(query).json() == response.json()
                assert _cached_rule_cues.cache_info().hits >= 1
                assert _cached_cue_spans.cache_info().hits >= 1
                for report_id in (latest, old, long_id):
                    detail = client.get(f"/api/reports/{report_id}")
                    assert detail.status_code == 200
                    stored = StoredReport.model_validate(detail.json())
                    pred = stored.prediction
                    assert pred is not None
                    assert pred.rule_cue_hits == rule_cue_hits(stored.report.text)
                    assert pred.evidence_spans == deterministic_cue_spans(stored.report.text)
                    assert pred.band == ("LOW" if report_id == old else "HIGH")
                    assert all(stored.report.text[s.start:s.end] == s.text for s in pred.evidence_spans)
                assert client.get("/api/reports?date_from=2025-01-01&date_to=2025-01-01").json()[0]["id"] == old
                assert [r["id"] for r in client.get("/api/reports?date_from=2026-01-01&date_to=2026-01-02").json()] == [pending, latest]
                assert client.get("/api/reports?date_from=2026-01-04").json() == []
                assert client.get("/api/reports?date_from=2026-01-02&date_to=2026-01-01").status_code == 422
                all_rows = client.get("/api/reports?limit=4").json()
                assert [r["id"] for r in all_rows] == [long_id, pending, latest, old]
                assert all_rows[2] == client.get(f"/api/reports/{latest}").json()
                assert all_rows[3] == client.get(f"/api/reports/{old}").json()
                assert all_rows[0] == client.get(f"/api/reports/{long_id}").json()
                assert _cached_rule_cues.cache_info().currsize == 1
                assert _cached_cue_spans.cache_info().currsize == 1
                in_process = _report_band(storage.get_report(latest), classifier, app.state.cfg)
                in_process.prediction.rule_cue_hits.clear()
                in_process.prediction.evidence_spans.clear()
                fresh = _report_band(storage.get_report(latest), classifier, app.state.cfg)
                assert fresh.prediction.rule_cue_hits == rule_cue_hits(text)
                assert fresh.prediction.evidence_spans == deterministic_cue_spans(text)
                all_rows[2]["prediction"]["rule_cue_hits"].clear()
                assert client.get(f"/api/reports/{latest}").json()["prediction"]["rule_cue_hits"] == rule_cue_hits(text)
                assert client.get("/api/reports?limit=4").json()[2]["prediction"]["rule_cue_hits"] == rule_cue_hits(text)
                classifier.sif_flag_threshold = 0.8
                assert client.get(f"/api/reports/{latest}").json()["prediction"]["band"] == "MODERATE"
                assert client.get("/api/reports?limit=4").json()[2]["prediction"]["flag_threshold"] == 0.8
        finally:
            storage.close()
    print("reports_list_check: ALL PASS")


if __name__ == "__main__":
    main()
