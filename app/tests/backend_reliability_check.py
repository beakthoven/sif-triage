"""Isolated SQLite/API reliability checks.
Run: .venv/bin/python -m app.tests.backend_reliability_check
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.classifier import MockClassifier
from app.config import Settings
from app.routes import router
from app.schemas import GateState, OverrideIn, PatternRow, PredictionOut, ReportIn
from app.storage import SQLiteStorage


BARRIER_NAMES = {
    "energy_isolation_absent", "gas_test_absent", "permit_absent",
    "fall_protection_absent", "fire_watch_absent", "standby_absent",
    "atmosphere_unmonitored",
}


def prediction(score: float, gates: list[GateState] | None = None) -> PredictionOut:
    return PredictionOut(
        sif_score=score, rule_probs={}, well_control=False,
        evidence_spans=[], gate_states=gates or [], model_version="check",
    )


def client_for(storage: SQLiteStorage) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.storage = storage
    app.state.classifier = MockClassifier()
    app.state.classifier.sif_flag_threshold = 0.6
    app.state.cfg = Settings()
    return TestClient(app)


def check_legacy_reports(tmp: Path) -> None:
    storage = SQLiteStorage(tmp / "legacy.db")
    try:
        legacy = storage.add_report(ReportIn(text="Legacy report before ensemble migration"))
        zeros = storage.add_report(ReportIn(text="Stored prediction with zero spread and stability"))
        storage.add_prediction(legacy, prediction(0.7))
        storage.add_prediction(zeros, prediction(0.7).model_copy(update={
            "score_spread": 0.0, "n_variants": 4,
            "variant_scores": [0.0, 0.2, 0.6, 1.0], "verdict_stability": 0.0,
        }))
        with storage._lock, storage._conn:
            storage._conn.execute(
                "UPDATE predictions SET score_spread=NULL, n_variants=NULL,"
                " variant_scores=NULL, verdict_stability=NULL WHERE report_id=?", (legacy,),
            )
        with client_for(storage) as client:
            response = client.get("/api/reports")
            assert response.status_code == 200, response.text
            rows = {row["id"]: row for row in response.json()}
            for report_id in (legacy, zeros):
                detail = client.get(f"/api/reports/{report_id}")
                assert detail.status_code == 200, detail.text
                assert detail.json() == rows[report_id]
            pred = rows[legacy]["prediction"]
            assert (pred["score_spread"], pred["n_variants"], pred["variant_scores"],
                    pred["verdict_stability"]) == (0.0, 1, [], 1.0)
            pred = rows[zeros]["prediction"]
            assert (pred["score_spread"], pred["n_variants"], pred["variant_scores"],
                    pred["verdict_stability"]) == (0.0, 4, [0.0, 0.2, 0.6, 1.0], 0.0)
    finally:
        storage.close()


def check_actions(tmp: Path) -> None:
    storage = SQLiteStorage(tmp / "actions.db")
    try:
        report_id = storage.add_report(ReportIn(text="Action closure test report"))
        override_id = storage.add_override(OverrideIn(
            report_id=report_id, field="notes", new_value="Check control restoration",
        ))
        with client_for(storage) as client:
            response = client.post("/api/actions", json={
                "report_id": report_id, "override_id": override_id,
                "owner": " Shift lead ", "due_date": "2026-10-01",
            })
            assert response.status_code == 201, response.text
            action_id = response.json()["id"]
            url = f"/api/actions/{action_id}"
            response = client.patch(url, json={"status": "in_progress"})
            assert response.status_code == 200 and response.json()["due_date"] == "2026-10-01"
            response = client.patch(url, json={"due_date": None})
            assert response.status_code == 200 and response.json()["due_date"] is None
            assert storage._conn.execute(
                "SELECT due_date IS NULL FROM actions WHERE id=?", (action_id,),
            ).fetchone()[0] == 1
            response = client.patch(url, json={"due_date": "2026-10-02", "owner": " New owner "})
            assert response.status_code == 200 and response.json()["owner"] == "New owner"
            response = client.patch(url, json={"due_date": None, "owner": None, "status": None})
            assert response.status_code == 200 and response.json()["due_date"] is None
            assert response.json()["owner"] == "New owner" and response.json()["status"] == "in_progress"
            for body in ({}, {"owner": None}, {"status": None}, {"owner": " "},
                         {"due_date": ""}, {"due_date": "2026-02-30"}):
                assert client.patch(url, json=body).status_code == 422, body
            assert client.patch("/api/actions/99999", json={"due_date": None}).status_code == 404
            assert client.get("/api/actions").json()[0]["due_date"] is None
        assert not storage.update_action(action_id)
        assert storage.update_action(action_id, due_date="")
        assert storage.get_action(action_id)["due_date"] == ""
        assert storage.update_action(action_id, status="closed")
        assert storage.get_action(action_id)["due_date"] == ""
        assert storage.update_action(action_id, due_date=None)
        assert storage.get_action(action_id)["due_date"] is None
    finally:
        storage.close()


class CountingEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.vec = np.zeros(384, dtype=np.float32)
        self.vec[0] = 1.0

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        return np.stack([self.vec for _ in texts])


def check_classify_embedding(tmp: Path) -> None:
    storage = SQLiteStorage(tmp / "classify.db")
    embedder = CountingEmbedder()
    try:
        with client_for(storage) as client, patch("app.embedder.get_embedder", return_value=embedder):
            text = "During maintenance at Site X, LOTO was not applied to the pump."
            for count in (1, 2):
                response = client.post("/api/classify?persist=1", json={"text": text})
                assert response.status_code == 200, response.text
                pred = response.json()
                assert len(embedder.calls) == count and embedder.calls[-1] == [text]
                assert isinstance(pred["report_id"], int)
                assert any(g["name"] == "near_dup" and g["triggered"] for g in pred["gate_states"]) == (count == 2)
            assert storage.count_reports() == 1
            stored = client.get(f"/api/reports/{pred['report_id']}").json()
            assert stored["report"]["text"] == text and stored["prediction"] is not None
            vector = storage._conn.execute("SELECT vector FROM embeddings").fetchone()[0]
            assert np.array_equal(np.frombuffer(vector, dtype=np.float32), embedder.vec)
            response = client.post("/api/classify", json={"text": "Stateless new report with a pump"})
            assert response.status_code == 200 and response.json()["report_id"] is None
            assert len(embedder.calls) == 3 and storage.count_reports() == 1
            with patch.object(storage, "add_ingest_batch", side_effect=RuntimeError("write unavailable")):
                response = client.post("/api/classify?persist=1", json={"text": "Novel persistence failure report"})
                assert response.status_code == 200 and response.json()["report_id"] is None
                assert len(embedder.calls) == 4 and storage.count_reports() == 1
            with patch("app.routes.embed_texts", side_effect=RuntimeError("embedding unavailable")):
                response = client.post("/api/classify?persist=1", json={"text": "Novel embedding failure report"})
                assert response.status_code == 200 and response.json()["report_id"] is None
                assert storage.count_reports() == 1
            with patch("app.routes.embed_texts", side_effect=RuntimeError("embedding unavailable")), patch(
                "app.embedder.embed_text", side_effect=RuntimeError("embedding unavailable"),
            ):
                response = client.post("/api/classify?persist=1", json={"text": "Broken near duplicate embedding report"})
                assert response.status_code == 200 and response.json()["report_id"] is None
                assert any(g["name"] == "near_dup" and "gate error" in g["detail"]
                           for g in response.json()["gate_states"])
    finally:
        storage.close()


def check_patterns(tmp: Path) -> None:
    storage = SQLiteStorage(tmp / "patterns.db")
    stale = tmp / "stale.json"
    stale.write_text(json.dumps({"site_x_activity": [{
        "activity": "Stale activity", "site": "Stale site", "n": 100,
        "sif_rate": 1.0, "lift": 99, "ci_low": 0.9, "ci_high": 1.0,
    }], "activity_x_barrier": []}))
    try:
        storage.save_precomputed("patterns", json.loads(stale.read_text()))
        with client_for(storage) as client, patch.dict("os.environ", {"SIF_PATTERNS_FILE": str(stale)}):
            for kind in ("site_activity", "activity_barrier"):
                response = client.get(f"/api/patterns?kind={kind}&min_n=1")
                assert response.status_code == 200 and response.json() == []
            storage.add_report(ReportIn(text="Waiting for prediction", activity="Pending", site="Pending"))
            scores = [0.8, 0.7, 0.6, 0.2, 0.65, 0.1, 0.1, 0.1, 0.1, 0.1]
            report_ids = []
            for i, score in enumerate(scores):
                gates = [GateState(name="gas_test_absent", triggered=True)] if i < 4 else []
                if i == 0:
                    gates += [GateState(name=name, triggered=True) for name in sorted(BARRIER_NAMES)]
                    gates += [GateState(name="invented_absence", triggered=True),
                              GateState(name="severity_watch", triggered=True)]
                if i == 1:
                    gates += [GateState(name="energy_isolation_absent", triggered=True)]
                if i == 4:
                    gates += [GateState(name="fire_watch_absent", triggered=False),
                              GateState(name="permit_absent", triggered=True, detail="gate error: failed check")]
                report_id = storage.add_report(ReportIn(
                    text=f"Scored pattern report {i}", site="S" if i < 4 else "T",
                    activity="A" if i < 4 else "B",
                ))
                report_ids.append(report_id)
                storage.add_prediction(report_id, prediction(score, gates))
            with patch.object(storage, "list_reports", side_effect=AssertionError("patterns must aggregate in SQL")):
                response = client.get("/api/patterns?min_n=1")
                assert response.status_code == 200, response.text
                site_rows = response.json()
                assert sum(row["n"] for row in site_rows) == 10
                first = site_rows[0]
                assert (first["site"], first["activity"], first["n"], first["sif_rate"],
                        first["lift"], first["ci_low"], first["ci_high"]) == ("S", "A", 4, 0.75, 1.875, 0.3006, 0.9544)
                barrier_rows = client.get("/api/patterns?kind=activity_barrier&min_n=1").json()
                assert {row["barrier"] for row in barrier_rows} == BARRIER_NAMES
                assert all(row["site"] is None and row["rule"] is None and row["activity"] == "A"
                           for row in barrier_rows)
                gas = next(row for row in barrier_rows if row["barrier"] == "gas_test_absent")
                assert (gas["n"], gas["sif_rate"], gas["lift"]) == (4, 0.75, 1.875)
                assert next(row for row in barrier_rows if row["barrier"] == "energy_isolation_absent")["n"] == 2
                for row in site_rows + barrier_rows:
                    assert set(row) == set(PatternRow.model_fields)
                    assert 0.0 <= row["ci_low"] <= row["sif_rate"] <= row["ci_high"] <= 1.0
                assert len(client.get("/api/patterns?min_n=1&limit=1").json()) == 1
                assert client.get("/api/patterns?min_n=7").json() == []
                assert len(client.get("/api/patterns?kind=activity_barrier&min_n=2").json()) == 2
                assert client.get("/api/patterns?kind=made_up").status_code == 422
                client.app.state.classifier.sif_flag_threshold = 0.75
                changed = client.get("/api/patterns?min_n=1").json()[0]
                assert (changed["sif_rate"], changed["lift"]) == (0.25, 2.5)
                changed_gas = next(row for row in client.get(
                    "/api/patterns?kind=activity_barrier&min_n=1",
                ).json() if row["barrier"] == "gas_test_absent")
                assert (changed_gas["sif_rate"], changed_gas["lift"]) == (0.25, 2.5)
                client.app.state.classifier.sif_flag_threshold = 0.6
                storage.add_prediction(report_ids[0], prediction(0.1))
                changed = client.get("/api/patterns?min_n=1").json()[0]
                assert (changed["sif_rate"], changed["lift"]) == (0.5, 1.667)
                barrier_rows = client.get("/api/patterns?kind=activity_barrier&min_n=1").json()
                assert {row["barrier"] for row in barrier_rows} == {"gas_test_absent", "energy_isolation_absent"}
                new_id = storage.add_report(ReportIn(text="New live report", site="S", activity="A"))
                storage.add_prediction(new_id, prediction(0.8, [GateState(name="gas_test_absent", triggered=True)]))
                changed = client.get("/api/patterns?min_n=1").json()[0]
                assert (changed["n"], changed["sif_rate"], changed["lift"]) == (5, 0.6, 1.65)
                gas = next(row for row in client.get(
                    "/api/patterns?kind=activity_barrier&min_n=1",
                ).json() if row["barrier"] == "gas_test_absent")
                assert (gas["n"], gas["sif_rate"], gas["lift"]) == (4, 0.75, 2.062)
                client.app.state.classifier.sif_flag_threshold = 1.0
                assert all(row["sif_rate"] == row["lift"] == 0.0 for row in client.get(
                    "/api/patterns?kind=activity_barrier&min_n=1",
                ).json())
            storage.add_report(ReportIn(text="Unspecified facets null report"))
            null_id = storage.add_report(ReportIn(text="Unspecified facets empty report", activity="", site=""))
            storage.add_prediction(null_id, prediction(0.2))
            rows = client.get("/api/patterns?min_n=1").json()
            assert any(row["activity"] == row["site"] == "(unspecified)" and row["n"] == 1 for row in rows)
    finally:
        storage.close()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sif-backend-check-") as temp:
        tmp = Path(temp)
        for check in (check_legacy_reports, check_actions, check_classify_embedding, check_patterns):
            check(tmp)
            print(f"{check.__name__}: PASS")
    print("backend_reliability_check: ALL PASS")


if __name__ == "__main__":
    main()
