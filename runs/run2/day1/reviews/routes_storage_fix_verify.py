"""Fix-verification probes for the SEV1/SEV2 wave on routes/storage/ingest.

Addresses runs/run2/day1/reviews/routes_storage.md findings:
  SEV1-1  shared-connection corruption     -> RLock serializes ALL conn access
  SEV2-1  index-misalignment boot-killer   -> actionable recovery in the message
  SEV2-2  duplicate re-ingest              -> content-hash dedup + payload replay
  SEV2-3  override queue integrity         -> write vocabulary + latest-wins export
  SEV2-4  non-transactional ingest batch   -> single-transaction batch + rollback
  SEV3-1  density/metrics full scan + N+1  -> SQL aggregate + cache

Usage:
  .venv/bin/python runs/run2/day1/reviews/routes_storage_fix_verify.py storage
  .venv/bin/python runs/run2/day1/reviews/routes_storage_fix_verify.py api 8192
  (api mode expects a server on that port seeded with >=1 report)
Exit code 0 = all checks green.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from app.ingest import text_hash  # noqa: E402
from app.schemas import (  # noqa: E402
    GateState,
    OverrideIn,
    PredictionOut,
    ReportIn,
)
from app.storage import SQLiteStorage  # noqa: E402


def check(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"FAIL: {label}")
    print(f"  ok: {label}")


def _pred(score: float = 0.9) -> PredictionOut:
    return PredictionOut(
        sif_score=score,
        rule_probs={"hot_work": score},
        well_control=False,
        evidence_spans=[],
        gate_states=[GateState(name="min_length", triggered=False)],
        model_version="probe",
    )


def _vec() -> np.ndarray:
    return np.zeros(384, dtype=np.float32)


def storage_mode() -> None:
    tmp = tempfile.TemporaryDirectory(prefix="sif-fix-verify-")
    db = Path(tmp.name) / "t.db"

    print("[S1] schema v1 -> v2 migration backfills content hashes")
    # build a v1-shaped DB by hand (schema minus the v2 tables)
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE schema_meta (id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL);
        INSERT INTO schema_meta VALUES (1, 1);
        CREATE TABLE reports (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL,
            date TEXT, site TEXT, activity TEXT, contractor TEXT,
            source TEXT NOT NULL DEFAULT 'api', created_at TEXT NOT NULL);
        INSERT INTO reports (text, created_at) VALUES ('legacy row one', '2026-01-01T00:00:00+00:00');
        INSERT INTO reports (text, created_at) VALUES ('legacy row two', '2026-01-01T00:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()
    st = SQLiteStorage(db)
    check(st.count_reports() == 2, "legacy rows visible after migration")
    ids, skipped = st.add_ingest_batch([
        (ReportIn(text="legacy row one"), _pred(), _vec(), text_hash("legacy row one")),
    ])
    check(ids == [] and skipped == 1, "pre-existing legacy row is deduped after backfill")
    st.close()

    print("[S2] transactional batch: forced mid-batch failure rolls back (SEV2-4)")
    st = SQLiteStorage(Path(tmp.name) / "t2.db")
    items = [
        (ReportIn(text=f"txn probe row {i} with enough words to matter"), _pred(), _vec(),
         text_hash(f"txn probe row {i} with enough words to matter"))
        for i in range(5)
    ]
    calls = {"n": 0}
    real = SQLiteStorage._insert_prediction

    def boom(self, rid, pred):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("injected mid-batch failure")
        return real(self, rid, pred)

    with mock.patch.object(SQLiteStorage, "_insert_prediction", boom):
        try:
            st.add_ingest_batch(items)
            raise SystemExit("FAIL: injected failure did not propagate")
        except RuntimeError:
            pass
    check(st.count_reports() == 0, "rollback: 0 rows after mid-batch failure")
    ids, skipped = st.add_ingest_batch(items)  # connection still usable
    check(len(ids) == 5 and skipped == 0, "clean retry after rollback stores all 5")
    st.close()

    print("[S3] cross-request per-row dedup (SEV2-2)")
    st = SQLiteStorage(Path(tmp.name) / "t3.db")
    ids1, _ = st.add_ingest_batch(items[:2])
    # second 'request': row 0 verbatim (whitespace-variant), row 1 dup, one new
    variant = "txn  probe   row 0\nwith enough words to matter"
    check(text_hash(variant) == text_hash(items[0][0].text),
          "whitespace-normalized hash matches the original")
    ids2, skipped2 = st.add_ingest_batch([
        (ReportIn(text=variant), _pred(), _vec(), text_hash(variant)),
        (items[1][0], _pred(), _vec(), items[1][3]),
        (ReportIn(text="brand new row about a dropped hammer near the derrick floor"),
         _pred(), _vec(), text_hash("brand new row about a dropped hammer near the derrick floor")),
    ])
    check(len(ids2) == 1 and skipped2 == 2, "2 dups skipped, 1 new stored")
    check(st.count_reports() == 3, "no double count in the store")
    st.close()

    print("[S4] override export: latest-wins + exact-dup collapse (SEV2-3)")
    st = SQLiteStorage(Path(tmp.name) / "t4.db")
    rid = st.add_report(ReportIn(text="override export probe row with enough words"))
    st.add_override(OverrideIn(report_id=rid, field="sif_label", new_value="not_sif_potential",
                               rationale="first"))
    st.add_override(OverrideIn(report_id=rid, field="sif_label", new_value="not_sif_potential",
                               rationale="first"))  # exact dup -> collapses
    st.add_override(OverrideIn(report_id=rid, field="sif_label", new_value="sif_potential",
                               rationale="changed my mind"))  # contradicts -> wins
    st.add_override(OverrideIn(report_id=rid, field="notes", new_value="called the rig",
                               source="blind_gold"))
    export = st.export_overrides()
    by_field = {r["field"]: r for r in export}
    check(len(export) == 2, "one export row per (report_id, field)")
    check(by_field["sif_label"]["value"] == "sif_potential", "latest distinct value wins")
    check(by_field["sif_label"]["override_id"] == 3, "winner is the latest row")
    check(sorted(by_field["sif_label"]["supersedes"]) == [1, 2],
          "superseded + collapsed ids recorded")
    check(by_field["notes"]["source"] == "blind_gold", "source column preserved")
    st.close()

    print("[S5] aggregates match brute force (SEV3-1)")
    st = SQLiteStorage(Path(tmp.name) / "t5.db")
    rng = np.random.default_rng(7)
    n = 500
    truth: dict[str, list[float]] = {}
    for i in range(n):
        site = f"site-{i % 17}" if i % 11 else None
        score = float(rng.random())
        st.add_ingest_batch([(ReportIn(text=f"agg probe row {i} enough words here", site=site),
                              _pred(score), _vec(), text_hash(f"agg probe row {i}"))])
        truth.setdefault(site or "(unspecified)", []).append(score)
    thr = 0.712581
    agg = {r["key"]: r for r in st.density_aggregate("site", thr)}
    check(set(agg) == set(truth), "density keys match")
    for k, scores in truth.items():
        row = agg[k]
        assert row["n_reports"] == len(scores)
        assert row["n_flagged"] == sum(1 for s in scores if s >= thr)
        assert abs(row["mean_score"] - round(sum(scores) / len(scores), 4)) < 1e-4
    check(True, "density n/flagged/mean exact vs brute force")
    m = st.metrics_aggregate(thr)
    all_scores = [s for ss in truth.values() for s in ss]
    check(m["n_reports"] == n and m["n_flagged"] == sum(1 for s in all_scores if s >= thr)
          and m["gate_trigger_counts"] == {}, "metrics aggregate matches brute force")
    st.close()

    print("[S6] actionable misalignment error (SEV2-1)")
    bad = Path(tmp.name) / "badindex"
    bad.mkdir()
    np.save(bad / "corpus_embeddings_fp16.npy", np.zeros((10, 384), dtype=np.float16))
    (bad / "corpus_ids.jsonl").write_text("".join(json.dumps({"id": i}) + "\n" for i in range(16)))
    try:
        SQLiteStorage(Path(tmp.name) / "t6.db", corpus_index_dir=bad)
        raise SystemExit("FAIL: misaligned index did not hard-fail")
    except ValueError as exc:
        msg = str(exc)
        check("10 vectors vs 16 ids" in msg, "still names the mismatch")
        check("DELETE BOTH" in msg and "session-only" in msg, "names the recovery path")

    print("\nSTORAGE-MODE PASS")


def api_mode(port: int) -> None:
    BASE = f"http://127.0.0.1:{port}/api"

    def post(path, payload):
        req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()[:300]

    def get(path):
        with urllib.request.urlopen(BASE + path, timeout=60) as r:
            return json.loads(r.read())

    print("[A1] duplicate re-ingest: replay + per-row dedup (SEV2-2)")
    nonce = f"{time.time():.6f}"  # probe payloads are unique per run so the
    # script itself is re-runnable against the same throwaway DB
    rows = [{"text": f"FixVerify[{nonce}]: gas alarm at wellhead during wireline ops, evacuated. (v{i})",
             "site": "fixverify-site", "activity": "wireline"} for i in range(8)]
    n0 = get("/metrics/summary")["n_reports"]
    s1, r1 = post("/ingest", {"records": rows, "source": "fixverify"})
    s2, r2 = post("/ingest", {"records": rows, "source": "fixverify"})
    check(s1 == 200 and r1["accepted"] == 8 and r1["skipped_duplicates"] == 0,
          f"first POST accepted 8 (got {r1.get('accepted')})")
    check(r2.get("idempotent_replay") is True and r2["report_ids"] == r1["report_ids"],
          "identical re-POST replays the original result")
    n1 = get("/metrics/summary")["n_reports"]
    check(n1 - n0 == 8, f"store grew by exactly 8 (delta={n1 - n0}), not 16")
    # different payload, overlapping rows -> per-row skip
    rows2 = rows[:4] + [{"text": f"FixVerify[{nonce}]: brand new text, sling parted during pipe lift",
                         "site": "fixverify-site"}]
    s3, r3 = post("/ingest", {"records": rows2, "source": "fixverify"})
    check(r3["accepted"] == 1 and r3["skipped_duplicates"] == 4 and not r3["idempotent_replay"],
          f"overlapping payload: 1 new + 4 skipped (got {r3})")
    n2 = get("/metrics/summary")["n_reports"]
    check(n2 - n1 == 1, "only the new row landed")

    print("[A2] within-batch dedup")
    dup_rows = [{"text": f"FixVerify within-batch dup[{nonce}]: unguarded shaft caught rag on mud pump"},
                {"text": f"FixVerify within-batch dup[{nonce}]:   unguarded shaft   caught rag on mud pump"},
                {"text": f"FixVerify within-batch unique[{nonce}]: dropped object near miss on deck"}]
    s, r = post("/ingest", {"records": dup_rows, "source": "fixverify"})
    check(r["accepted"] == 2 and r["skipped_duplicates"] == 1,
          f"whitespace-variant dup skipped within batch (got {r})")

    print("[A3] override vocabulary enforced (SEV2-3)")
    rid = r1["report_ids"][0]
    s, _ = post("/review", {"report_id": rid, "field": "garbage_field'; DROP TABLE overrides;--",
                                "new_value": "x"})
    check(s == 422, f"garbage field -> 422 (got {s})")
    s, _ = post("/review", {"report_id": rid, "field": "sif_label", "new_value": "maybe_sometimes"})
    check(s == 422, f"free-text sif_label value -> 422 (got {s})")
    s, _ = post("/review", {"report_id": rid, "field": "rules", "new_value": "hot_work,not_a_rule"})
    check(s == 422, f"unknown rule key -> 422 (got {s})")
    s, _ = post("/review", {"report_id": rid, "field": "rules", "new_value": "hot_work,line_of_fire"})
    check(s == 201, f"valid rules override -> 201 (got {s})")
    s, _ = post("/review", {"report_id": rid, "field": "sif_label", "new_value": "not_sif_potential"})
    check(s == 201, "valid sif_label override stored")
    s, _ = post("/review", {"report_id": rid, "field": "sif_label", "new_value": "not_sif_potential"})
    check(s == 201, "exact dup still recorded (history is append-only)")
    s, _ = post("/review", {"report_id": rid, "field": "sif_label", "new_value": "sif_potential",
                                "rationale": "reversed"})
    check(s == 201, "contradictory override recorded (latest wins at export)")
    with urllib.request.urlopen(BASE + "/review/export", timeout=30) as resp:
        lines = [json.loads(x) for x in resp.read().decode().strip().splitlines()]
    mine = [x for x in lines if x["report_id"] == rid and x["field"] == "sif_label"]
    check(len(mine) == 1 and mine[0]["value"] == "sif_potential" and len(mine[0]["supersedes"]) == 2,
          f"export: latest-wins with 2 superseded ids (got {mine})")

    print("[A4] validation-failure counts stay honest (P3a regression)")
    bad = [{"text": f"FixVerify P3a row {i}[{nonce}] enough words to pass validation"} for i in range(40)]
    bad[17] = {"site": "no-text"}
    s, r = post("/ingest", {"records": bad, "source": "fixverify_p3a"})
    check(s == 200 and r["received"] == 40 and r["accepted"] == 39 and r["rejected"] == 1
          and r["errors"][0]["row"] == 17, f"honest counts (got {r.get('received')}/"
          f"{r.get('accepted')}/{r.get('rejected')})")

    print("\nAPI-MODE PASS")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("storage", "api"):
        sys.exit("usage: routes_storage_fix_verify.py storage | api PORT")
    if sys.argv[1] == "storage":
        storage_mode()
    else:
        api_mode(int(sys.argv[2]))
