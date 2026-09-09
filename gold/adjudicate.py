"""Adjudication tool — final rulings on the gold disagreement/unsure queue.

Run (the morning AFTER labeling + export freeze):
    python3 gold/adjudicate.py --adjudicator junior --port 8010
    python3 gold/adjudicate.py --adjudicator senior --port 8011  # goes last: final

Protocol (spec/label_spec.yaml gold.labeling.adjudication "3rd labeler cites
frozen spec"; gold/RUBRIC.md):
  - adjudicators see ONLY masked_text + event_title + WHY the item is queued
    (disagreement / unsure). NEVER the individual votes, never the stratum,
    never model output — the served payload carries nothing else.
  - every ruling MUST carry a one-line justification citing the rubric; the
    app refuses to save without one.
  - rulings append to artifacts/gold/labels/adjudication.jsonl (one shared
    file). LATEST ruling per item wins: the junior adjudicator works the
    queue first, the senior adjudicator works it after, and the senior's
    ruling is final. Progress is per adjudicator; re-run to resume.
  - a ruling of U is a FINAL "cannot tell": the item stays out of the metrics
    but leaves the pending queue.

After the session, re-run gold/compute_gold_metrics.py — rulings are applied
automatically as superseding item-level overrides (pre-consensus), and the
metrics JSON records n_adjudicated. See gold/RUNBOOK_HUMANS.md.

Self-test: python3 gold/adjudicate.py --self-test  (throwaway ports + files)
Pure stdlib (http.server). Binds 127.0.0.1 only by default.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gold_common import LABELS, RULES, RULE_TITLES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE = ROOT / "artifacts" / "gold" / "adjudication_queue_all4.jsonl"
DEFAULT_RULINGS = ROOT / "artifacts" / "gold" / "labels" / "adjudication.jsonl"

SERVED_ITEM_KEYS = ("gold_id", "masked_text", "event_title", "reason")

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>SIF gold adjudication</title>
<style>
 body { font-family: system-ui, sans-serif; max-width: 860px; margin: 2em auto;
        padding: 0 1em; background: #f7f7f5; color: #1a1a1a; }
 #bar-wrap { background: #ddd; border-radius: 6px; height: 14px; margin: 1em 0; }
 #bar { background: #1d4ed8; height: 14px; border-radius: 6px; width: 0;
        transition: width .15s; }
 #reason-tag { display: inline-block; background: #fef3c7; border: 1px solid
               #d97706; color: #92400e; border-radius: 4px; padding: 1px 8px;
               font-size: .85em; margin-bottom: .5em; }
 #title { color: #555; font-size: .95em; margin-bottom: .4em; }
 #text { background: #fff; border: 1px solid #ddd; border-radius: 8px;
         padding: 1.2em; font-size: 1.15em; line-height: 1.55; white-space:
         pre-wrap; }
 #keys { margin: 1em 0; color: #444; }
 kbd { background: #eee; border: 1px solid #bbb; border-radius: 4px;
       padding: 1px 7px; font-family: inherit; }
 #ruling-form { display: none; background: #fff; border: 1px solid #ddd;
                border-radius: 8px; padding: 1em 1.2em; margin-top: 1em; }
 #ruling-form label { display: block; margin: .25em 0; }
 #just { width: 100%; margin-top: .5em; font: inherit; padding: .4em;
         box-sizing: border-box; }
 button { font: inherit; padding: .5em 1.2em; border-radius: 6px;
          border: 1px solid #999; cursor: pointer; }
 #save { background: #1d4ed8; color: #fff; border-color: #1d4ed8; }
 #status { color: #666; font-size: .9em; }
 #err { color: #b91c1c; font-size: .9em; min-height: 1.2em; }
 #picked { font-weight: bold; }
 h1 { font-size: 1.2em; }
</style></head><body>
<h1>SIF gold adjudication — __ADJUDICATOR__</h1>
<div id="bar-wrap"><div id="bar"></div></div>
<div id="status">loading…</div>
<div id="work" style="display:none">
  <div id="reason-tag"></div>
  <div id="title"></div>
  <div id="text"></div>
  <div id="keys">
    Rule <kbd>S</kbd> SIF-potential &nbsp; <kbd>N</kbd> non-SIF &nbsp;
    <kbd>U</kbd> unsure (final) &nbsp; <span style="color:#888">— every ruling
    needs a one-line justification citing the rubric</span>
  </div>
  <div id="ruling-form">
    <div>Ruling: <span id="picked"></span></div>
    <div id="rules-wrap"><b>Life-Saving Rules present</b> (SIF rulings; optional but encouraged)
      <div id="rules"></div>
    </div>
    Justification (required — cite gold/RUBRIC.md):
    <input id="just" type="text" autocomplete="off"
      placeholder="e.g. 'drill, not a real exposure -> N (rubric: edge cases)'">
    <div id="err"></div>
    <p><button id="save">Save ruling [Enter]</button></p>
  </div>
</div>
<div id="done" style="display:none">
  <h2>Queue adjudicated. Thank you!</h2>
  <p>Hand to the senior adjudicator if you are not last; otherwise tell the
  admin to re-run <code>gold/compute_gold_metrics.py</code>.</p>
</div>
<script>
let item = null, picked = null;
const RULES = __RULES_JSON__;
const LABEL_NAMES = {sif: 'SIF-potential', non_sif: 'non-SIF', unsure: 'unsure (final)'};

async function next() {
  const r = await fetch('/api/next');
  const d = await r.json();
  document.getElementById('bar').style.width = (100 * d.done / d.total) + '%';
  document.getElementById('status').textContent =
    d.done + ' / ' + d.total + ' ruled by you' +
    (d.ruled_by_others ? ' · ' + d.ruled_by_others + ' already ruled by others (you may still overrule — latest wins)' : '');
  if (!d.item) {
    document.getElementById('work').style.display = 'none';
    document.getElementById('done').style.display = 'block';
    return;
  }
  item = d.item; picked = null;
  document.getElementById('reason-tag').textContent =
    'queued for: ' + (d.item.reason === 'unsure' ? 'unsure vote' : 'disagreement');
  document.getElementById('title').textContent = d.item.event_title || '';
  document.getElementById('text').textContent = d.item.masked_text;
  document.getElementById('ruling-form').style.display = 'none';
  document.getElementById('just').value = '';
  document.getElementById('err').textContent = '';
  document.querySelectorAll('#rules input').forEach(cb => cb.checked = false);
  document.getElementById('work').style.display = 'block';
}

function pick(label) {
  picked = label;
  document.getElementById('picked').textContent = LABEL_NAMES[label];
  document.getElementById('rules-wrap').style.display = label === 'sif' ? 'block' : 'none';
  document.getElementById('ruling-form').style.display = 'block';
  document.getElementById('just').focus();
}

async function save() {
  if (!item || !picked) return;
  const just = document.getElementById('just').value.trim();
  if (!just) {
    document.getElementById('err').textContent =
      'justification is required — cite the rubric';
    return;
  }
  const rules = picked === 'sif'
    ? [...document.querySelectorAll('#rules input:checked')].map(cb => cb.value)
    : [];
  const r = await fetch('/api/rule', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({gold_id: item.gold_id, label: picked, rules,
                          justification: just})});
  if (!r.ok) {
    const d = await r.json();
    document.getElementById('err').textContent = d.error || 'save failed';
    return;
  }
  next();
}

document.addEventListener('keydown', e => {
  if (!item) return;
  if (e.target.id === 'just') {
    if (e.key === 'Enter') save();
    return;
  }
  const k = e.key.toLowerCase();
  if (k === 's') pick('sif');
  else if (k === 'n') pick('non_sif');
  else if (k === 'u') pick('unsure');
  else if (e.key === 'Enter' &&
           document.getElementById('ruling-form').style.display === 'block') save();
});
document.getElementById('save').onclick = save;

const rulesDiv = document.getElementById('rules');
for (const [val, title] of RULES) {
  const l = document.createElement('label');
  l.innerHTML = '<input type="checkbox" value="' + val + '"> ' + title;
  rulesDiv.appendChild(l);
}
next();
</script></body></html>"""


def load_queue(queue_path: Path) -> list[dict]:
    """The adjudication queue, stripped to blind-safe fields only: the raw
    rows carry the individual votes ('labels'), which adjudicators must NOT
    see. No stratum / model output exists in the queue by construction
    (compute_gold_metrics.py writes it blind)."""
    queue = []
    with open(queue_path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                queue.append({
                    "gold_id": row["gold_id"],
                    "masked_text": row["masked_text"],
                    "event_title": row.get("event_title"),
                    "reason": row["adjudication_reason"],
                })
    return queue


def load_rulings(rulings_path: Path) -> dict[str, dict]:
    """Latest-wins map gold_id -> ruling record (the file is append-only, so
    the last record for an item is the current ruling). This is the map
    compute_gold_metrics.py applies as the pre-consensus override."""
    rulings: dict[str, dict] = {}
    if rulings_path.exists():
        with open(rulings_path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    rulings[rec["gold_id"]] = rec
    return rulings


def _ruling_sets(rulings_file: Path, adjudicator: str) -> tuple[set[str], set[str]]:
    """(mine, anyone) gold_id sets from ALL ruling records — not the
    latest-wins map — so a senior overrule does not re-serve the item to the
    junior on resume."""
    mine: set[str] = set()
    anyone: set[str] = set()
    if rulings_file.exists():
        with open(rulings_file, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    anyone.add(rec["gold_id"])
                    if rec.get("adjudicator") == adjudicator:
                        mine.add(rec["gold_id"])
    return mine, anyone


def make_handler(queue, rulings_file, adjudicator):
    queue_ids = {it["gold_id"] for it in queue}

    class Handler(BaseHTTPRequestHandler):
        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                body = (
                    PAGE.replace("__ADJUDICATOR__", adjudicator).replace(
                        "__RULES_JSON__", json.dumps([[r, RULE_TITLES[r]] for r in RULES])
                    )
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/next":
                # re-read per request: two adjudicator instances share the file
                mine, anyone = _ruling_sets(rulings_file, adjudicator)
                done = sum(1 for it in queue if it["gold_id"] in mine)
                ruled_any = sum(1 for it in queue if it["gold_id"] in anyone)
                nxt = next((it for it in queue if it["gold_id"] not in mine), None)
                self._json({"done": done, "total": len(queue),
                            "ruled_by_others": ruled_any - done, "item": nxt})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            if self.path != "/api/rule":
                self._json({"error": "not found"}, 404)
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                gid, label = body["gold_id"], body["label"]
                rules = body.get("rules") or []
                justification = str(body.get("justification") or "").strip()[:500]
                assert gid in queue_ids, "gold_id not in the adjudication queue"
                assert label in LABELS, f"bad label {label!r}"
                assert set(rules) <= set(RULES), "unknown rule tag"
                assert justification, "justification is required (cite the rubric)"
                if label != "sif":
                    rules = []
                rec = {
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "gold_id": gid,
                    "label": label,
                    "rules": rules,
                    "justification": justification,
                    "adjudicator": adjudicator,
                }
                with open(rulings_file, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                mine, _ = _ruling_sets(rulings_file, adjudicator)
                done = sum(1 for it in queue if it["gold_id"] in mine)
                self._json({"ok": True, "done": done, "total": len(queue)})
            except (ValueError, KeyError, AssertionError) as e:
                self._json({"error": str(e)}, 400)

        def log_message(self, fmt, *args):  # keep console quiet
            pass

    return Handler


# --------------------------------------------------------------- self-test --
def self_test() -> int:
    """End-to-end on throwaway ports/files: serves a fake queue, drives two
    adjudicators over HTTP exactly as humans would, checks blindness,
    validation, progress, latest-wins, and resume."""
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    def api(port: int, path: str, body: dict | None = None):
        url = f"http://127.0.0.1:{port}{path}"
        if body is None:
            with urllib.request.urlopen(url, timeout=10) as r:
                return r.status, json.loads(r.read())
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    tmp = Path(tempfile.mkdtemp(prefix="adjudicate_selftest_"))
    servers = []
    try:
        queue_path = tmp / "queue.jsonl"
        fake = [
            {"gold_id": f"G9{i:03d}", "masked_text": f"Worker {i} was struck by "
             f"a suspended load near the crane and was [OUTCOME].",
             "event_title": f"Struck by event {i}",
             "adjudication_reason": "disagreement" if i % 2 else "unsure",
             "labels": {"labeler_a": {"label": "sif"}, "labeler_b": {"label": "non_sif"}},
             "source_stratum": "osha_2024_25", "p_raw": 0.9}
            for i in range(5)
        ]
        with open(queue_path, "w", encoding="utf-8") as fh:
            for row in fake:
                fh.write(json.dumps(row) + "\n")
        rulings_file = tmp / "labels" / "adjudication.jsonl"
        rulings_file.parent.mkdir(parents=True)
        queue = load_queue(queue_path)

        def serve(adj: str) -> int:
            srv = ThreadingHTTPServer(("127.0.0.1", 0),
                                      make_handler(queue, rulings_file, adj))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            servers.append(srv)
            return srv.server_address[1]

        print("== blindness: served payload carries no votes/stratum/model output ==")
        check("queue loader strips votes + provenance fields",
              all(set(it) == set(SERVED_ITEM_KEYS) for it in queue))
        p_junior = serve("junior")
        st, d = api(p_junior, "/api/next")
        item_json = json.dumps(d["item"])
        check("served item has exactly the blind-safe keys",
              st == 200 and set(d["item"]) == set(SERVED_ITEM_KEYS))
        check("no votes/stratum/model fields anywhere in the served item",
              all(t not in item_json for t in
                  ("labels", "labeler_", "stratum", "p_raw", "sif_logit",
                   "osha_2024_25")))
        with urllib.request.urlopen(f"http://127.0.0.1:{p_junior}/", timeout=10) as r:
            html = r.read().decode()
        check("served HTML has no provenance vocab",
              all(t not in html for t in ("labeler_", "stratum", "p_raw")))

        print("== validation ==")
        gid0 = queue[0]["gold_id"]
        st, r = api(p_junior, "/api/rule", {"gold_id": gid0, "label": "maybe",
                                            "rules": [], "justification": "x"})
        check("invalid label rejected (400)", st == 400, r.get("error", ""))
        st, r = api(p_junior, "/api/rule", {"gold_id": gid0, "label": "non_sif",
                                            "rules": [], "justification": "  "})
        check("empty justification rejected (400)", st == 400, r.get("error", ""))
        st, r = api(p_junior, "/api/rule", {"gold_id": "G0000", "label": "sif",
                                            "rules": [], "justification": "x"})
        check("gold_id outside the queue rejected (400)", st == 400, r.get("error", ""))
        st, r = api(p_junior, "/api/rule", {"gold_id": gid0, "label": "sif",
                                            "rules": ["underwater_basket_weaving"],
                                            "justification": "x"})
        check("unknown rule tag rejected (400)", st == 400, r.get("error", ""))

        print("== session: junior rules all 5, then senior overrules one ==")
        for i, it in enumerate(queue):
            label = ("sif", "non_sif", "unsure")[i % 3]
            rules = [RULES[0]] if label == "sif" else []
            st, r = api(p_junior, "/api/rule",
                        {"gold_id": it["gold_id"], "label": label, "rules": rules,
                         "justification": "self-test: rubric mechanism call"})
            assert st == 200, r
        check("junior ruled the full queue", r["done"] == len(queue),
              f"{r['done']}/{r['total']}")
        st, d = api(p_junior, "/api/next")
        check("junior: queue exhausted (item null)", d["item"] is None)
        rec0 = next(json.loads(l) for l in open(rulings_file)
                    if json.loads(l)["gold_id"] == gid0)
        check("non-sif ruling forced rules=[] (labeler_app invariant)",
              rec0["label"] == "sif" and rec0["rules"] == [RULES[0]]
              or rec0["label"] != "sif" and rec0["rules"] == [],
              f"{rec0['label']} rules={rec0['rules']}")

        p_senior = serve("senior")  # same queue, same rulings file
        st, d = api(p_senior, "/api/next")
        check("senior sees fresh progress on the shared queue (latest-wins design)",
              d["done"] == 0 and d["ruled_by_others"] == len(queue),
              f"done={d['done']} others={d['ruled_by_others']}")
        st, r = api(p_senior, "/api/rule",
                    {"gold_id": gid0, "label": "non_sif", "rules": [],
                     "justification": "senior final: negation real (rubric)"})
        check("senior overrule accepted", st == 200 and r["done"] == 1)
        check("latest-wins: senior ruling supersedes junior's",
              load_rulings(rulings_file)[gid0]["label"] == "non_sif")

        print("== resume: a fresh instance keeps per-adjudicator progress ==")
        p_junior2 = serve("junior")
        st, d = api(p_junior2, "/api/next")
        check("junior resume: still done, nothing re-served",
              d["done"] == len(queue) and d["item"] is None)
    finally:
        for srv in servers:
            srv.shutdown()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"\nSELF-TEST FAILED: {failures}")
        return 1
    print("\nSELF-TEST PASS (blindness, validation, 2-adjudicator latest-wins, resume)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--adjudicator", default="adjudicator",
                    help="name recorded on your rulings (e.g. junior / senior). "
                         "Progress is tracked per name; latest ruling per item wins.")
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE),
                    help="adjudication queue (default: the all4 queue, 100 items)")
    ap.add_argument("--rulings", default=str(DEFAULT_RULINGS),
                    help="append-only rulings file, shared across adjudicators")
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address; use 0.0.0.0 to allow teammates over LAN")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    queue = load_queue(Path(args.queue))
    rulings_file = Path(args.rulings)
    rulings_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        srv = ThreadingHTTPServer(
            (args.host, args.port), make_handler(queue, rulings_file, args.adjudicator)
        )
    except OSError as e:
        print(f"[{args.adjudicator}] ERROR: cannot bind {args.host}:{args.port} ({e}). "
              f"Another instance is probably already running on this port — "
              f"use it, or pick another port (8010+).", file=sys.stderr)
        return 2
    print(f"[{args.adjudicator}] {len(queue)} items in the adjudication queue. "
          f"Open http://{args.host}:{args.port}/  — Ctrl-C to stop; re-run to "
          f"resume. Rulings append to {rulings_file} (latest per item wins).")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
