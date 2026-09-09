"""Self-check for the explanation layer — runnable script, no pytest.

Covers: template correctness (deterministic, contains score/rules/spans,
all spans exact substrings) — silent fallback when ollama is unreachable —
span validation (hallucinated span rejected, corrective retry recovers;
persistent garbage falls back to template) — cache round-trip through the
storage precomputed table — precompute-harness gates under the _NullStorage
stub never emit 'gate error' (final_audit F1/F3 regression) — endpoint
wiring (GET /reports/{id}/explanation, POST /classify?explain=1) with the
LLM disabled.

Run: .venv/bin/python app/tests/explain_check.py
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

os.environ["SIF_EXPLAIN_LLM"] = "0"  # endpoints must never wait on ollama here

from app.classifier import MockClassifier, validate_spans  # noqa: E402
from app.config import Settings  # noqa: E402
from app.explain import (  # noqa: E402
    build_explanation,
    explain_key,
    ollama_reword,
    render_template,
)
from app.schemas import ExplanationOut  # noqa: E402
from app.storage import SQLiteStorage  # noqa: E402

PORT = int(os.environ.get("SIF_TEST_PORT", "8179"))  # override when :8179 is taken
BASE = f"http://127.0.0.1:{PORT}/api"

SAMPLE = (
    "During well intervention at Baghjan field, a worker was grinding without "
    "a face shield near a live H2S flowline; LOTO was not applied on the pump "
    "and sparks were observed near the flange. Kick was later reported on the pit."
)


def check(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"FAIL: {label}")
    print(f"  ok: {label}")


def _pred(text: str):
    pred = MockClassifier().predict(text)
    pred.evidence_spans = validate_spans(text, pred.evidence_spans)
    return pred


def fake_transport(responses: list[dict | Exception]):
    calls: list[dict] = []

    def call(payload: dict) -> dict:
        calls.append(payload)
        item = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    return call, calls


def ok_response(explanation: str, spans: list[str]) -> dict:
    return {"message": {"content": json.dumps(
        {"explanation": explanation, "spans_quoted": spans})}}


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


def main() -> int:
    print("[1] template correctness")
    pred = _pred(SAMPLE)
    template, spans = render_template(pred, SAMPLE)
    template2, spans2 = render_template(pred, SAMPLE)
    check(template == template2 and spans == spans2, "deterministic: same pred -> same template")
    check(f"{pred.sif_score:.2f}" in template, "triage score present")
    check(all(s in template for s in spans), "every span quoted in the template")
    check(all(s in SAMPLE for s in spans), "every span is an exact substring of the report")
    implicated = [k for k, v in pred.rule_probs.items() if v >= 0.5]
    check(implicated, "mock anchors pushed at least one rule over threshold")
    check("Energy Isolation" in template and "Hot Work" in template,
          "rule display names rendered (anchors pushed energy_isolation + hot_work over threshold)")
    check(pred.well_control and "Well-control/barrier tag: raised." in template,
          "well-control line rendered")

    print("[2] fallback when ollama is stopped (connection refused)")
    t0 = time.perf_counter()
    out = build_explanation(pred, SAMPLE, None, use_llm=True,
                            url="http://127.0.0.1:9", timeout=2.0)
    dt = time.perf_counter() - t0
    check(out.source == "template" and out.reworded is None, "silent template fallback")
    check(out.template == template, "fallback template identical to render_template")
    check(dt < 5.0, f"fast failure ({dt:.2f}s, no stall)")

    print("[3] span validation + retry state machine")
    good = ok_response(f"The triage score is {pred.sif_score:.2f} with evidence "
                       f"\"LOTO\" and \"grinding\" noted.", ["LOTO", "grinding"])
    transport, calls = fake_transport([good])
    out3 = ollama_reword(SAMPLE, template, f"{pred.sif_score:.2f}", transport=transport)
    check(out3 is not None and len(calls) == 1, "clean output accepted on first try")
    check("think" in calls[0] and calls[0]["think"] is False and "format" in calls[0],
          "C10 contract on the wire: think:false + format schema")
    hallucinated = ok_response("Score 0.28.", ["nonexistent phrase"])
    transport, calls = fake_transport([hallucinated, good])
    out3 = ollama_reword(SAMPLE, template, f"{pred.sif_score:.2f}", transport=transport)
    check(out3 is not None and len(calls) == 2, "hallucinated span rejected, retry recovered")
    check("invalid" in calls[1]["messages"][-1]["content"].lower(),
          "retry appended the validation error")
    transport, calls = fake_transport([hallucinated, hallucinated])
    out3 = ollama_reword(SAMPLE, template, f"{pred.sif_score:.2f}", transport=transport)
    check(out3 is None and len(calls) == 2, "persistent bad spans -> None (template fallback)")
    transport, calls = fake_transport([OSError("boom")])
    check(ollama_reword(SAMPLE, template, "0.28", transport=transport) is None,
          "transport error -> None, never raises")
    meta = ok_response("The user wants me to rewrite the triage note carefully.", [])
    transport, _ = fake_transport([meta, meta])
    check(ollama_reword(SAMPLE, template, "0.28", transport=transport) is None,
          "chain-of-thought leak into the field rejected")
    wrong_score = ok_response("The triage score is 9.99, flagged for review.", [])
    transport, _ = fake_transport([wrong_score, wrong_score])
    check(ollama_reword(SAMPLE, template, "0.28", transport=transport) is None,
          "mutated triage score rejected")
    bad_quote = ok_response("Score 0.28. Evidence: \"LOTO\" and \"sparks flew\".", ["LOTO"])
    transport, _ = fake_transport([bad_quote, bad_quote])
    check(ollama_reword(SAMPLE, template, "0.28", transport=transport) is None,
          "in-prose quoted phrase not in the report rejected (spans_quoted valid)")

    print("[4] cache round-trip (storage precomputed table)")
    tmp = tempfile.TemporaryDirectory(prefix="sif-explain-")
    storage = SQLiteStorage(Path(tmp.name) / "t.db")
    key = explain_key(SAMPLE, pred.model_version)
    check(storage.load_precomputed(key) is None, "cache empty before first build")
    transport, calls = fake_transport([good])
    out4 = build_explanation(pred, SAMPLE, storage, use_llm=True, transport=transport)
    check(out4.source == "ollama" and not out4.cached, "first build: live ollama path")
    hit = storage.load_precomputed(key)
    check(hit is not None and hit["source"] == "ollama", "payload persisted under sha256 key")
    def boom_transport(_payload): raise OSError("ollama must not be called on a cache hit")
    out5 = build_explanation(pred, SAMPLE, storage, use_llm=True, transport=boom_transport)
    check(out5.cached and out5.source == "ollama" and out5.reworded == out4.reworded,
          "second build: served from cache, no LLM call")

    print("[4b] template-fallback TTL: fresh entry served, stale entry retried")
    key2 = explain_key("TTL probe report about LOTO at height", pred.model_version)
    pred_ttl = _pred("TTL probe report about LOTO at height")
    out_ttl = build_explanation(pred_ttl, "TTL probe report about LOTO at height",
                                storage, use_llm=True, url="http://127.0.0.1:9", timeout=1.0)
    check(out_ttl.source == "template", "llm down -> template fallback built")
    out_ttl2 = build_explanation(pred_ttl, "TTL probe report about LOTO at height",
                                 storage, use_llm=True, transport=boom_transport)
    check(out_ttl2.cached and out_ttl2.source == "template",
          "fresh template fallback served without retrying the LLM")
    hit2 = storage.load_precomputed(key2)
    hit2["created_epoch"] = 0.0  # force stale
    storage.save_precomputed(key2, hit2)
    good_ttl = ok_response(
        f"The triage score is {pred_ttl.sif_score:.2f} with \"LOTO\" noted.", ["LOTO"])
    transport3, calls3 = fake_transport([good_ttl])
    out_ttl3 = build_explanation(pred_ttl, "TTL probe report about LOTO at height",
                                 storage, use_llm=True, transport=transport3)
    check(len(calls3) == 1 and out_ttl3.source == "ollama" and not out_ttl3.cached,
          "stale template fallback retried the LLM and upgraded to ollama")
    storage.close()

    print("[4c] precompute harness: gates under the _NullStorage stub produce no gate errors")
    # Regression for final_audit F1/F3: the stub lacked nearest_base_batch /
    # nearest_session; run_gates degraded the AttributeError into a triggered
    # 'gate error' state and the string was baked into all 63 cached
    # explanations. The stub must now cover every Storage method gates call.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "sif_precompute", REPO_ROOT / "artifacts" / "explanations" / "precompute.py")
    precompute = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(precompute)
    res = precompute._gen_one({"id": "regression", "text": SAMPLE},
                              use_llm=False, timeout=1.0)
    check("error" not in res, f"_gen_one with stub gates did not raise (got {res.get('error')})")
    check("gate error" not in json.dumps(res["cache_payload"]),
          "no 'gate error' text in the precomputed payload (template path)")
    pred43 = precompute._predict(SAMPLE, Settings(), precompute._NULL_STORAGE)
    nd = next(g for g in pred43.gate_states if g.name == "near_dup")
    check(not nd.triggered and "index empty" in (nd.detail or ""),
          "near_dup gate degrades to 'index empty' under the stub, not an AttributeError")
    check(not any("gate error" in (g.detail or "") for g in pred43.gate_states),
          "no gate entered the error state under the stub")

    print("[5] endpoint wiring (uvicorn, SIF_EXPLAIN_LLM=0)")
    env = dict(os.environ, SIF_DB_PATH=str(Path(tmp.name) / "api.db"))
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=REPO_ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                status, _ = req("GET", "/health")
                if status == 200:
                    break
            except urllib.error.URLError:
                time.sleep(0.2)
        else:
            raise AssertionError("server did not come up")
        t0 = time.perf_counter()
        status, pred_raw = req("POST", "/classify?explain=1", {"text": SAMPLE})
        dt = time.perf_counter() - t0
        check(status == 200, "classify?explain=1 -> 200")
        expl = ExplanationOut(**pred_raw["explanation"])
        check(expl.template and expl.reworded is None and expl.source == "template",
              "explanation attached: template present, reworded null (llm disabled)")
        check(dt < 3.0, f"explain=1 stays fast with llm disabled ({dt*1000:.0f} ms)")
        status, plain = req("POST", "/classify", {"text": SAMPLE})
        check(status == 200 and plain["explanation"] is None,
              "plain classify untouched (explanation null)")
        status, ing = req("POST", "/ingest", {"records": [{"text": SAMPLE}]})
        rid = ing["report_ids"][0]
        status, e1 = req("GET", f"/reports/{rid}/explanation")
        check(status == 200 and e1["template"], "GET /reports/{id}/explanation -> 200")
        status, e2 = req("GET", f"/reports/{rid}/explanation")
        check(status == 200 and e2["cached"] is True, "second GET served from cache")
        status, _ = req("GET", "/reports/424242/explanation")
        check(status == 404, "missing report -> 404")
    finally:
        server.terminate()
        server.wait(timeout=10)
        tmp.cleanup()

    print("\nEXPLAIN CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
