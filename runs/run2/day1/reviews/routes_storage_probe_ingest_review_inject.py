# Probes 3-5: partial failure honesty, duplicate re-ingest, override loop,
# injection surfaces. All against the throwaway DB on :8191.
import json, urllib.request, urllib.error

BASE = "http://127.0.0.1:8191"

def post(path, payload):
    req = urllib.request.Request(BASE+path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: body = e.read().decode()[:300]
        except Exception: body = ""
        return e.code, body

def get(path):
    with urllib.request.urlopen(BASE+path, timeout=60) as r:
        return json.loads(r.read())

print("== P3a: batch partial failure — row 3000 (0-based 2999) of 5050 invalid ==")
TEXT = "Probe row: unguarded rotating shaft on mud pump caught rag during rounds, near miss only."
rows = [{"text": f"{TEXT} (v{i})", "site": "p3"} for i in range(5050)]
rows[2999] = {"site": "p3"}  # no text at all
s, res = post("/api/ingest", {"records": rows, "source": "p3_partial"})
if isinstance(res, dict):
    res.pop("report_ids")
    print(f"  http={s} received={res['received']} accepted={res['accepted']} rejected={res['rejected']}")
    print(f"  errors[:3]={res['errors'][:3]}")
    assert res["received"] == 5050 and res["rejected"] == 1 and res["errors"][0]["row"] == 2999
    print("  counts HONEST; error row index correct (0-based)")
else:
    print(f"  http={s} body={res}")

print("== P3b: duplicate re-ingest of the same payload ==")
dup = [{"text": f"DupProbe: gas detector alarm at wellhead during wireline ops, evacuated and ventilated. (d{i})",
        "site": "dup-site", "activity": "wireline"} for i in range(50)]
m0 = get("/api/metrics/summary")
s1, r1 = post("/api/ingest", {"records": dup, "source": "dup_probe"})
r1.pop("report_ids")
s2, r2 = post("/api/ingest", {"records": dup, "source": "dup_probe"})
r2.pop("report_ids")
m1 = get("/api/metrics/summary")
print(f"  first : http={s1} {r1}")
print(f"  second: http={s2} {r2}")
print(f"  n_reports {m0['n_reports']} -> {m1['n_reports']} (delta={m1['n_reports']-m0['n_reports']}, expected 100 if double-counted)")
d = get("/api/density?by=site")
dup_row = [r for r in d if r["key"] == "dup-site"]
print(f"  density row for dup-site: {dup_row}")

print("== P4: override loop ==")
s, r = post("/api/review", {"report_id": 99999999, "field": "sif_label", "new_value": "not_sif_potential"})
print(f"  nonexistent report_id: http={s} {str(r)[:120]}")
s, r = post("/api/review", {"report_id": 1, "field": "sif_label", "new_value": "not_sif_potential", "rationale": "probe"})
print(f"  valid override: http={s} {str(r)[:160]}")
s, r = post("/api/review", {"report_id": 1, "field": "sif_label", "new_value": "not_sif_potential", "rationale": "probe"})
print(f"  exact duplicate override again: http={s} id={r.get('id') if isinstance(r, dict) else r}")
ovs = get("/api/review?report_id=1")
print(f"  overrides on report 1 now: {len(ovs)} (dedup: NONE)" if len(ovs) > 1 else f"  overrides on report 1: {len(ovs)}")
s, r = post("/api/review", {"report_id": 1, "field": "sif_label", "new_value": "sif_potential", "rationale": "changed my mind"})
print(f"  contradictory override (same field, opposite value): http={s} accepted={s==201}")
ovs = get("/api/review?report_id=1")
print(f"  report 1 override history: " + json.dumps([(o['field'], o['new_value']) for o in ovs]))
s, r = post("/api/review", {"report_id": 1, "field": "garbage_field'; DROP TABLE overrides;--", "new_value": "x"})
print(f"  arbitrary/garbage field value: http={s} (schema has NO enum on 'field')")
s, r = post("/api/review", {"report_id": 1, "field": "sif_label", "new_value": "maybe_sometimes" })
print(f"  free-text new_value (no label enum): http={s}")
s, r = post("/api/review", {"report_id": 1, "field": "sif_label", "new_value": "sif_potential", "source": "blind_gold"})
print(f"  blind_gold source accepted: http={s}")

print("== P5a: SQL injection in ingest fields ==")
s, r = post("/api/ingest", {"records": [{"text": "'); DROP TABLE reports;-- UNION SELECT * FROM overrides;--", "site": "x'; DROP TABLE reports;--"}], "source": "sqli_probe"})
h = get("/api/health")
print(f"  http={s}; health after: n_reports={h['n_reports']} (tables intact => parameterized)")

print("== P5b: CSV formula injection payloads stored verbatim ==")
s, r = post("/api/ingest", {"records": [
    {"text": "=cmd|'/c calc'!A1 plus enough words to clear the min length gate easily", "site": "=1+1"},
    {"text": "+SUM(1,2) formula-lead text with enough trailing words to pass the gate", "site": "@evil"},
    {"text": "-10-20 leading-minus text with plenty of words after to pass the gate", "site": "\t=HYPERLINK(\"http://x\")"},
], "source": "formula_probe"})
rid = r["report_ids"][0] if isinstance(r, dict) and r.get("report_ids") else None
got = get(f"/api/reports/{rid}") if rid else None
print(f"  http={s} stored text verbatim: {got['report']['text'][:40]!r} site: {got['report']['site']!r}" if got else f"  http={s}")
print("  (no CSV-export endpoint in app — risk lands on any downstream spreadsheet export)")

print("== P5c: records+csv both present ==")
s, r = post("/api/ingest", {"records": [{"text": "records path wins probe: valve left open on drain line during shift handover walkdown"}],
                            "csv": "text\ncsv path row that should be ignored, unguarded flange on the acid line",
                            "source": "both_probe"})
if isinstance(r, dict): r.pop("report_ids")
print(f"  http={s} {r} (csv silently ignored when records present)")

print("== P5d: column_mapping case sensitivity ==")
s, r = post("/api/ingest", {"records": [{"Narrative_Text": "case probe: sling parted during lift of pipe bundle onto catwalk deck"}],
                            "column_mapping": {"text": "narrative_text"}, "source": "case_probe"})
if isinstance(r, dict): r.pop("report_ids")
print(f"  mapping 'narrative_text' vs raw key 'Narrative_Text': http={s} {r}")
