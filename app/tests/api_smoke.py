"""API smoke test — runnable script, stdlib urllib only (no pytest).

Spawns uvicorn on :8177 (override with SIF_TEST_PORT when the demo server
owns :8177) against a throwaway DB, exercises the full flow:
health -> classify (span validity + determinism) -> ingest 5-row CSV ->
reports/density/rules/patterns/metrics -> review override round-trip ->
near-dup gate. Exit code 0 = pass.

Run: .venv/bin/python app/tests/api_smoke.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.schemas import (  # noqa: E402
    DensityRow,
    IngestResult,
    MetricsSummary,
    PatternRow,
    PredictionOut,
    StoredOverride,
    StoredReport,
)

PORT = int(os.environ.get("SIF_TEST_PORT", "8177"))  # override when the demo server owns :8177
BASE = f"http://127.0.0.1:{PORT}/api"

SAMPLE_REPORT = (
    "During well intervention at Baghjan field, a worker was grinding without "
    "a face shield near a live H2S flowline; LOTO was not applied on the pump "
    "and sparks were observed near the flange. Kick was later reported on the pit."
)

# final_audit_qa.md probe 1 — a NOVEL Baghjan-class well-control precursor
# (not in any corpus). The neural score sits below the flag threshold while
# the deterministic WC tag fires -> well-control watch gray, never auto-green.
WC_PROBE = (
    "During well servicing operations at well NHK-619, the crew observed mud "
    "gains of about three barrels at the active pit while tripping out. The "
    "well started flowing during connections. The driller shut in the BOP and "
    "the well was brought under control by bullheading kill-weight mud. "
    "No injury and no spill occurred."
)

CSV_5_ROWS = """narrative,site,activity,contractor
"Worker at height on scaffold without harness near derrick",Baghjan,maintenance,ONGC Services
"Confined space entry into tank without gas test or permit",Duliajan,tank cleaning,PetroServ
"Crane lifting operation with damaged sling over live equipment",Moran,lifting,ONGC Services
"LOTO not applied",Baghjan,maintenance,PetroServ
"Short note",Moran,driving,UNKNOWN
"""


def req(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def check(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"FAIL: {label}")
    print(f"  ok: {label}")


def main() -> int:
    tmp = tempfile.TemporaryDirectory(prefix="sif-smoke-")
    env = dict(os.environ, SIF_DB_PATH=str(Path(tmp.name) / "smoke.db"))
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=REPO_ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                status, health = req("GET", "/health")
                if status == 200:
                    break
            except urllib.error.URLError:
                time.sleep(0.2)
        else:
            raise AssertionError("server did not come up on :8177")

        print("[1] health")
        check(health["status"] == "ok", "health ok")
        check(health["classifier"] in ("MockClassifier", "RealOnnxClassifier"), "classifier named")

        print("[2] classify — span validity + determinism")
        status, pred_raw = req("POST", "/classify", {"text": SAMPLE_REPORT})
        check(status == 200, "classify 200")
        pred = PredictionOut(**pred_raw)
        check(0.0 <= pred.sif_score <= 1.0, "score in [0,1]")
        check(set(pred.rule_probs) == {
            "confined_space", "driving", "energy_isolation", "hot_work",
            "line_of_fire", "safe_mechanical_lifting", "working_at_height",
        }, "7 learnable rule probs present")
        check(all(SAMPLE_REPORT[s.start:s.end] == s.text for s in pred.evidence_spans),
              "every span satisfies text[start:end]==span.text")
        check(len(pred.evidence_spans) > 0, "anchors produced spans")
        check(pred.well_control is True, "well-control tag on kick/BOP language")
        check({g.name for g in pred.gate_states} == {
            "min_length", "negation", "language", "confidence", "drill", "near_dup",
            "long_input", "well_control_watch",
        }, "all 8 gates reported")
        _, pred2_raw = req("POST", "/classify", {"text": SAMPLE_REPORT})
        check(pred_raw == pred2_raw, "deterministic: same text -> same prediction")

        print("[3] gates fire on adversarial inputs")
        _, short_pred = req("POST", "/classify", {"text": "LOTO not applied"})
        gates = {g.name: g for g in PredictionOut(**short_pred).gate_states}
        check(not gates["min_length"].triggered and "codes path" in gates["min_length"].detail,
              "short-codes path saves 'LOTO not applied' from min-length")
        _, drill_pred = req("POST", "/classify", {"text": "Mock drill conducted for fire scenario at well pad, all safe."})
        check(PredictionOut(**drill_pred).gate_states[4].triggered, "drill filter fires")
        _, hindi_pred = req("POST", "/classify", {"text": "कर्मचारी बिना हार्नेस के ऊंचाई पर काम कर रहा था"})
        check(any(g.name == "language" and g.triggered for g in PredictionOut(**hindi_pred).gate_states),
              "language gate fires on non-ASCII text")
        # Well-control watch (audit probe 1 fix): WC tag fires but the score is
        # below the flag threshold -> gray watch state, never auto-green.
        _, wc_pred = req("POST", "/classify", {"text": WC_PROBE})
        wc = PredictionOut(**wc_pred)
        wcw = next(g for g in wc.gate_states if g.name == "well_control_watch")
        check(wc.well_control and wcw.triggered and wcw.action == "gray",
              f"well-control watch gray on novel WC text (score={wc.sif_score})")

        print("[4] ingest 5-row CSV (alias mapping: narrative -> text)")
        status, ing_raw = req("POST", "/ingest", {"csv": CSV_5_ROWS, "source": "smoke"})
        check(status == 200, "ingest 200")
        ing = IngestResult(**ing_raw)
        check(ing.received == 5 and ing.accepted == 5 and ing.rejected == 0, "5/5 rows accepted")
        check(len(ing.report_ids) == 5, "5 report ids returned")

        print("[4b] identical re-POST replays instead of double-ingesting")
        status, replay_raw = req("POST", "/ingest", {"csv": CSV_5_ROWS, "source": "smoke"})
        replay = IngestResult(**replay_raw)
        check(replay.idempotent_replay and replay.accepted == 5
              and replay.report_ids == ing.report_ids,
              "idempotent replay returns the original result")

        print("[5] stored views")
        _, reports_raw = req("GET", "/reports?limit=10")
        reports = [StoredReport(**r) for r in reports_raw]
        check(len(reports) == 5 and all(r.prediction for r in reports), "reports stored with predictions")
        short_stored = next(r for r in reports if r.report.text == "LOTO not applied")
        ml = next(g for g in short_stored.prediction.gate_states if g.name == "min_length")
        check(not ml.triggered, "stored short-code report not gated by min-length")
        _, density_raw = req("GET", "/density?by=site")
        density = [DensityRow(**d) for d in density_raw]
        check(sum(d.n_reports for d in density) == 5, "density covers all 5 reports")
        _, rules_raw = req("GET", "/rules")
        check(len(rules_raw) == 9, "9 IOGP rules listed")
        check(sum(1 for r in rules_raw if not r["in_scope"]) == 2,
              "PTW + Bypassing declared out-of-scope")
        _, patterns_raw = req("GET", "/patterns?min_n=1")
        patterns = [PatternRow(**p) for p in patterns_raw]
        check(all(0.0 <= p.ci_low <= p.sif_rate <= p.ci_high <= 1.0 for p in patterns),
              "pattern Wilson CIs bracket the rate")
        _, metrics_raw = req("GET", "/metrics/summary")
        metrics = MetricsSummary(**metrics_raw)
        check(metrics.n_reports == 5, "metrics count")

        print("[6] near-dup gate on re-pasted row")
        dup_text = CSV_5_ROWS.splitlines()[1].split('"')[1].replace("without harness", "without any harness")
        status, ing2_raw = req("POST", "/ingest", {"records": [{"text": dup_text, "site": "Baghjan"}]})
        ing2 = IngestResult(**ing2_raw)
        dup_report = StoredReport(**req("GET", f"/reports/{ing2.report_ids[0]}")[1])
        nd = next(g for g in dup_report.prediction.gate_states if g.name == "near_dup")
        check(nd.triggered, f"near-dup banner fired ({nd.detail})")

        print("[7] review override round-trip (-> future gold)")
        rid = ing.report_ids[0]
        stored_before = StoredReport(**req("GET", f"/reports/{rid}")[1])
        old = "sif_potential" if stored_before.prediction.sif_score >= 0.5 else "not_sif_potential"
        status, ov_raw = req("POST", "/review", {
            "report_id": rid, "field": "sif_label",
            "old_value": old,
            "new_value": "not_sif_potential" if old == "sif_potential" else "sif_potential",
            "labeler": "smoke_test", "rationale": "round-trip check",
        })
        check(status == 201, "override stored (201)")
        ov = StoredOverride(**ov_raw)
        _, queue_raw = req("GET", f"/review?report_id={rid}")
        queue = [StoredOverride(**o) for o in queue_raw]
        check(len(queue) == 1 and queue[0].id == ov.id and queue[0].source == "override",
              "override readable via GET /review")
        status, _ = req("POST", "/review", {"report_id": 99999, "field": "sif_label",
                                            "new_value": "not_sif_potential"})
        check(status == 404, "override on missing report -> 404")
        status, _ = req("POST", "/review", {"report_id": rid, "field": "garbage_field",
                                            "new_value": "x"})
        check(status == 422, "garbage override field rejected (422)")
        with urllib.request.urlopen(BASE + "/review/export", timeout=10) as resp:
            export_lines = resp.read().decode().strip().splitlines()
        check(len(export_lines) == 1 and json.loads(export_lines[0])["value"] == ov.new_value,
              "export emits latest-wins JSONL")

        print("[8] paste-persist round-trip (F4: overrides on live-paste cards)")
        _, health0 = req("GET", "/health")
        n0 = health0["n_reports"]
        status, plain = req("POST", "/classify", {"text": WC_PROBE})
        check(status == 200 and plain.get("report_id") is None,
              "default classify stays stateless (no report_id)")
        _, health1 = req("GET", "/health")
        check(health1["n_reports"] == n0, "stateless classify stores nothing")
        paste_text = ("Paste-persist probe: derrickhand spotted a hairline crack on the "
                      "crown sheave during morning checks at Workover Rig #7.")
        status, pasted = req("POST", "/classify?persist=1",
                             {"text": paste_text, "source": "live-paste"})
        check(status == 200 and isinstance(pasted.get("report_id"), int),
              "persist=1 returns a real server report id")
        rid = pasted["report_id"]
        status, stored = req("GET", f"/reports/{rid}")
        check(status == 200 and stored["report"]["text"] == paste_text
              and stored["report"]["source"] == "live-paste"
              and stored["prediction"] is not None,
              "pasted report + prediction retrievable by the returned id")
        status, _ = req("POST", "/review", {
            "report_id": rid, "field": "sif_label",
            "old_value": "LOW", "new_value": "sif_potential",
            "labeler": "smoke_test", "rationale": "paste override round-trip",
        })
        check(status == 201, "POST /review on a pasted report lands (201, not 404)")
        status, again = req("POST", "/classify?persist=1", {"text": paste_text})
        check(status == 200 and again.get("report_id") == rid,
              "identical re-paste dedups to the same stored row")
        _, health2 = req("GET", "/health")
        check(health2["n_reports"] == n0 + 1, "exactly one row stored across both pastes")

        print("\nSMOKE PASS")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=10)
        tmp.cleanup()


if __name__ == "__main__":
    sys.exit(main())
