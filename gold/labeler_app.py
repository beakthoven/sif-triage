"""Blind labeling tool — serves one masked report at a time, keyboard-driven.

Run one instance PER LABELER (separate terminal + port), e.g.:
    python3 gold/labeler_app.py --labeler a --port 8001
    python3 gold/labeler_app.py --labeler b --port 8002
    python3 gold/labeler_app.py --labeler c --port 8003
    python3 gold/labeler_app.py --labeler d --port 8004

Blind protocol (spec/label_spec.yaml gold.labeling):
  - labelers see ONLY masked_text + event_title. The item payload sent to the
    browser contains nothing else: no source stratum, no ids beyond the
    opaque gold_id, no derived labels, no model output, no provenance.
  - queue order is shuffled per labeler (per-labeler seed); the 20-item
    calibration pilot is served first, identical for all labelers.
  - labels autosave append-only to artifacts/gold/labels/<labeler>.jsonl.
    There is NO endpoint that reads any label file: labelers cannot see each
    other's labels (or their own history) through this app.
  - re-running the app resumes at the first unlabeled item (reads the
    labeler's own file to skip completed items).

Keys: [S] SIF-potential · [N] non-SIF · [U] unsure · [Enter] save (SIF form).
Pure stdlib (http.server). Binds 127.0.0.1 only.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gold_common import LABELS, RULES, RULE_TITLES, SEED  # noqa: E402

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>SIF gold labeling</title>
<style>
 body { font-family: system-ui, sans-serif; max-width: 860px; margin: 2em auto;
        padding: 0 1em; background: #f7f7f5; color: #1a1a1a; }
 #bar-wrap { background: #ddd; border-radius: 6px; height: 14px; margin: 1em 0; }
 #bar { background: #b45309; height: 14px; border-radius: 6px; width: 0;
        transition: width .15s; }
 #title { color: #555; font-size: .95em; margin-bottom: .4em; }
 #text { background: #fff; border: 1px solid #ddd; border-radius: 8px;
         padding: 1.2em; font-size: 1.15em; line-height: 1.55; white-space:
         pre-wrap; }
 #keys { margin: 1em 0; color: #444; }
 kbd { background: #eee; border: 1px solid #bbb; border-radius: 4px;
       padding: 1px 7px; font-family: inherit; }
 #sif-form { display: none; background: #fff; border: 1px solid #ddd;
             border-radius: 8px; padding: 1em 1.2em; margin-top: 1em; }
 #sif-form label { display: block; margin: .25em 0; }
 #reason { width: 100%; margin-top: .5em; font: inherit; padding: .4em;
           box-sizing: border-box; }
 button { font: inherit; padding: .5em 1.2em; border-radius: 6px;
          border: 1px solid #999; cursor: pointer; }
 #save { background: #b45309; color: #fff; border-color: #b45309; }
 #status { color: #666; font-size: .9em; }
 h1 { font-size: 1.2em; }
</style></head><body>
<h1>SIF-potential gold labeling — __LABELER__</h1>
<div id="bar-wrap"><div id="bar"></div></div>
<div id="status">loading…</div>
<div id="work" style="display:none">
  <div id="title"></div>
  <div id="text"></div>
  <div id="keys">
    <kbd>S</kbd> SIF-potential &nbsp; <kbd>N</kbd> non-SIF &nbsp;
    <kbd>U</kbd> unsure &nbsp; <span style="color:#888">(one judgment per report;
    no going back)</span>
  </div>
  <div id="sif-form">
    <b>SIF-potential.</b> Which Life-Saving Rules apply? (optional but encouraged)
    <div id="rules"></div>
    Reason (optional): <input id="reason" type="text" autocomplete="off"
      placeholder="one short phrase, e.g. 'suspended load over worker'">
    <p><button id="save">Save SIF label [Enter]</button></p>
  </div>
</div>
<div id="done" style="display:none"><h2>All items labeled. Thank you!</h2></div>
<script>
let item = null, picked = null;
const RULES = __RULES_JSON__;

async function next() {
  const r = await fetch('/api/next');
  const d = await r.json();
  document.getElementById('bar').style.width = (100 * d.done / d.total) + '%';
  document.getElementById('status').textContent =
    d.done + ' / ' + d.total + ' labeled';
  if (!d.item) {
    document.getElementById('work').style.display = 'none';
    document.getElementById('done').style.display = 'block';
    return;
  }
  item = d.item; picked = null;
  document.getElementById('title').textContent =
    d.item.is_pilot ? '[calibration pilot] ' + (d.item.event_title || '')
                    : (d.item.event_title || '');
  document.getElementById('text').textContent = d.item.masked_text;
  document.getElementById('sif-form').style.display = 'none';
  document.getElementById('reason').value = '';
  document.querySelectorAll('#rules input').forEach(cb => cb.checked = false);
  document.getElementById('work').style.display = 'block';
}

async function save(label) {
  const rules = label === 'sif'
    ? [...document.querySelectorAll('#rules input:checked')].map(cb => cb.value)
    : [];
  const reason = label === 'sif'
    ? document.getElementById('reason').value.trim() : '';
  await fetch('/api/label', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({gold_id: item.gold_id, label, rules, reason})});
  next();
}

document.addEventListener('keydown', e => {
  if (!item) return;
  if (e.target.id === 'reason') {
    if (e.key === 'Enter') save('sif');
    return;
  }
  const k = e.key.toLowerCase();
  if (k === 's') { document.getElementById('sif-form').style.display = 'block'; }
  else if (k === 'n') save('non_sif');
  else if (k === 'u') save('unsure');
  else if (e.key === 'Enter' &&
           document.getElementById('sif-form').style.display === 'block') save('sif');
});
document.getElementById('save').onclick = () => save('sif');

const rulesDiv = document.getElementById('rules');
for (const [val, title] of RULES) {
  const l = document.createElement('label');
  l.innerHTML = '<input type="checkbox" value="' + val + '"> ' + title;
  rulesDiv.appendChild(l);
}
next();
</script></body></html>"""


def load_queue(gold_path: str, labeler: str, seed: int) -> list[dict]:
    """Pilot items first (same 20 for every labeler), then the labeler's
    assigned items (primary + secondary), each block shuffled with a
    per-labeler seed. Only blind-safe fields are kept."""
    items = []
    with open(gold_path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                items.append(json.loads(line))
    mine = [
        it for it in items
        if it["is_pilot"]
        or it["assignment"]["labeler"] == labeler
        or it["assignment"].get("second_labeler") == labeler
    ]
    pilot = [it for it in mine if it["is_pilot"]]
    rest = [it for it in mine if not it["is_pilot"]]
    random.Random(f"{seed}:order:{labeler}:pilot").shuffle(pilot)
    random.Random(f"{seed}:order:{labeler}:main").shuffle(rest)
    return [
        {
            "gold_id": it["gold_id"],
            "masked_text": it["masked_text"],
            "event_title": it["event_title"],
            "is_pilot": it["is_pilot"],
        }
        for it in pilot + rest
    ]


def make_handler(queue, labels_file, labeler):
    labeled_ids: set[str] = set()
    if labels_file.exists():
        with open(labels_file, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    labeled_ids.add(json.loads(line)["gold_id"])

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
                    PAGE.replace("__LABELER__", labeler).replace(
                        "__RULES_JSON__", json.dumps([[r, RULE_TITLES[r]] for r in RULES])
                    )
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/next":
                nxt = next((it for it in queue if it["gold_id"] not in labeled_ids), None)
                done = sum(1 for it in queue if it["gold_id"] in labeled_ids)
                self._json({"done": done, "total": len(queue), "item": nxt})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            if self.path != "/api/label":
                self._json({"error": "not found"}, 404)
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                gid, label = body["gold_id"], body["label"]
                rules = body.get("rules") or []
                reason = str(body.get("reason") or "")[:500]
                valid_ids = {it["gold_id"] for it in queue}
                assert gid in valid_ids, "gold_id not in this labeler's queue"
                assert label in LABELS, f"bad label {label!r}"
                assert set(rules) <= set(RULES), "unknown rule tag"
                if label != "sif":
                    rules = []
                rec = {
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "gold_id": gid,
                    "label": label,
                    "rules": rules,
                    "reason": reason,
                }
                with open(labels_file, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                labeled_ids.add(gid)
                done = sum(1 for it in queue if it["gold_id"] in labeled_ids)
                self._json({"ok": True, "done": done, "total": len(queue)})
            except (ValueError, KeyError, AssertionError) as e:
                self._json({"error": str(e)}, 400)

        def log_message(self, fmt, *args):  # keep console quiet
            pass

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--labeler", required=True,
                    help="a, b, c, d (or labeler_a …) — one instance per labeler")
    ap.add_argument("--gold", default="artifacts/gold/gold_items.jsonl")
    ap.add_argument("--labels-dir", default="artifacts/gold/labels")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    labeler = args.labeler if args.labeler.startswith("labeler_") else f"labeler_{args.labeler}"
    queue = load_queue(args.gold, labeler, args.seed)
    labels_dir = Path(args.labels_dir)
    labels_dir.mkdir(parents=True, exist_ok=True)
    labels_file = labels_dir / f"{labeler}.jsonl"

    try:
        srv = ThreadingHTTPServer(
            ("127.0.0.1", args.port), make_handler(queue, labels_file, labeler)
        )
    except OSError as e:
        print(f"[{labeler}] ERROR: cannot bind 127.0.0.1:{args.port} ({e}). "
              f"Another instance is probably already running on this port — "
              f"use it, or stop it first (gold/start_labeling.sh --stop).",
              file=sys.stderr)
        return 2
    print(f"[{labeler}] {len(queue)} items queued (pilot first). "
          f"Open http://127.0.0.1:{args.port}/  — Ctrl-C to stop; "
          f"re-run to resume. Labels append to {labels_file}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
