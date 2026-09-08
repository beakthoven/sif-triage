"""Dry-run simulator for the blind labeling session — ops validation, NOT real labels.

Spins up 4 labeler_app instances and drives each through a labeling session
over HTTP exactly as a human would (GET /api/next -> POST /api/label), then
runs the adversarial ops cases and the export path. Prints PASS/FAIL per
check; exits non-zero if any check fails.

Phases:
  1. leakage scan   served payload keys + HTML/JSON grepped for provenance
  2. session        4 labelers x ~40 items via the real HTTP flow
  3. adversarial    mid-session restart/resume, duplicate submission,
                    invalid payloads, port already in use
  4. doubles top-up make some double items get their 2nd label (n=2 kappa subset)
  5. export         run export_labels.py, verify merged + agreement outputs

Usage:
    python3 gold/simulate_labeling.py            # full dry run (LEAVES label files)
    python3 gold/simulate_labeling.py --reset    # delete all simulated output, verify clean
    python3 gold/simulate_labeling.py --self-test  # alias for a quick end-to-end run

Labels are content-heuristic + deterministic noise so agreement numbers are
realistic (kappa > 0), but they are throwaway: run --reset before humans start.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gold_common import LABELER_IDS, RULES  # noqa: E402
from labeler_app import load_queue  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "artifacts/gold/gold_items.jsonl"
LABELS_DIR = ROOT / "artifacts/gold/labels"
MERGED = ROOT / "artifacts/gold/labels_merged.jsonl"
AGREEMENT = ROOT / "artifacts/gold/agreement.json"

SERVED_ITEM_KEYS = {"gold_id", "masked_text", "event_title", "is_pilot"}
# Provenance VOCABULARY that must never appear anywhere in a served payload:
# field names, stratum values, and labeler ids. Unambiguous (never report prose).
PROVENANCE_VOCAB = ("source_stratum", "osha_2024_25", "second_labeler", "is_double",
                    "naics", "oiics") + LABELER_IDS
# Generic English words worth eyeballing when they appear INSIDE narrative text
# (report content, not provenance — e.g. "altitude assignment", "synthetic shoe").
CONTENT_WATCH = ("stratum", "synthetic", "osha", "asrs", "assignment")
# gold_ids (G0xxx) are served BY DESIGN (opaque, needed to save a label).

SIF_HINTS = ("fell", "fall", "crush", "struck", "caught", "suspended", "ladder",
             "scaffold", "roof", "crane", "electric", "volt", "fire", "explod",
             "burn", "amput", "fracture", "dropped", "pinch", "deglov", "steam",
             "confined", "manhole", "reversing", "backed", "rollover", "forklift",
             "hoist", "rigging", "uncontrolled", "separation", "runway")
RULE_HINTS = {
    "line_of_fire": ("struck", "caught", "pinch", "crush", "dropped", "rolled"),
    "working_at_height": ("ladder", "scaffold", "roof", "fell from", "fall from",
                          "platform", "height"),
    "driving": ("reversing", "backed", "forklift", "truck", "vehicle", "rollover"),
    "energy_isolation": ("electric", "volt", "energized", "lockout", "breaker",
                         "pressure", "arc"),
    "hot_work": ("weld", "grind", "solder", "torch", "sparks", "flame"),
    "safe_mechanical_lifting": ("crane", "hoist", "rigging", "suspended", "sling",
                                "boom", "load"),
    "confined_space": ("confined", "tank", "manhole", "vessel", "pit", "silo"),
}

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


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


def sim_label(gold_id: str, labeler: str, text: str) -> dict:
    """Deterministic content heuristic + per-labeler noise (realistic agreement)."""
    low = text.lower()
    sif = any(h in low for h in SIF_HINTS)
    noise = int.from_bytes(
        hashlib.sha256(f"{gold_id}:{labeler}".encode()).digest()[:4]) % 100
    if noise < 7:                       # ~7% unsure
        label = "unsure"
    elif noise < 15:                    # ~8% flip
        label = "non_sif" if sif else "sif"
    else:
        label = "sif" if sif else "non_sif"
    rules = []
    if label == "sif":
        rules = [r for r in RULES if any(h in low for h in RULE_HINTS[r])][:2]
    return {"gold_id": gold_id, "label": label, "rules": rules,
            "reason": "simulated dry-run" if label == "sif" else ""}


def wait_ready(port: int, timeout: float = 15.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            api(port, "/api/next")
            return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.2)
    return False


def start_server(labeler: str, port: int) -> subprocess.Popen:
    log = open(f"/tmp/sif_sim_{labeler}.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "gold/labeler_app.py", "--labeler", labeler,
         "--port", str(port)],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    return proc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--items", type=int, default=40,
                    help="items per labeler in the main session phase")
    ap.add_argument("--ports", type=int, nargs=4, default=[8011, 8012, 8013, 8014])
    ap.add_argument("--reset", action="store_true",
                    help="delete simulated labels + export outputs and verify clean")
    ap.add_argument("--self-test", action="store_true", help="same as a default run")
    ap.add_argument("--force", action="store_true",
                    help="run even if label files already exist (DANGER: mixes with human labels)")
    args = ap.parse_args()

    if args.reset:
        return reset()

    if LABELS_DIR.exists() and any(LABELS_DIR.glob("labeler_*.jsonl")) and not args.force:
        print(f"REFUSING: {LABELS_DIR} already contains label files — are these human "
              f"labels? Use --reset to clear simulated output, or --force if you are sure.")
        return 2

    # ---------------- Phase 1: leakage scan ----------------
    print("\n== Phase 1: leakage scan (static, full queue payloads) ==")
    queues = {lab: load_queue(str(GOLD), lab, 42) for lab in LABELER_IDS}
    key_ok = all(set(it) == SERVED_ITEM_KEYS for q in queues.values() for it in q)
    check("served item payload keys == {gold_id, masked_text, event_title, is_pilot}", key_ok)

    meta_leaks = [(t, lab, it["gold_id"]) for lab, q in queues.items() for it in q
                  for t in PROVENANCE_VOCAB if t in json.dumps(it).lower()]
    content_hits = sorted({(t, it["gold_id"]) for lab, q in queues.items() for it in q
                           for t in CONTENT_WATCH
                           if t in (it["masked_text"] + " " + (it["event_title"] or "")).lower()})
    check("zero provenance vocab (fields/strata/labeler ids) in served payloads",
          not meta_leaks, f"meta leaks: {meta_leaks[:5]}")
    # Content-level words inside narratives are report text, not provenance.
    print(f"  [info] content-word hits inside narrative text (benign, reviewed): "
          f"{content_hits}")

    pilot_sets = {lab: [it["gold_id"] for it in q[:20]] for lab, q in queues.items()}
    pilot_ok = all(all(it["is_pilot"] for it in q[:20]) for q in queues.values()) and \
        len({tuple(sorted(s)) for s in pilot_sets.values()}) == 1
    check("first 20 served items are the SAME pilot set for all 4 labelers", pilot_ok,
          f"pilot n={len(pilot_sets['labeler_a'])}")
    orders_differ = len({tuple(s) for s in pilot_sets.values()}) > 1 or \
        len({tuple(it["gold_id"] for it in q) for q in queues.values()}) > 1
    check("queue order differs per labeler (per-labeler shuffle)", orders_differ)
    q_sizes = {lab: len(q) for lab, q in queues.items()}
    check("queue sizes 165-180 per labeler (20 pilot + ~125 primary + ~30 secondary, "
          "pilot overlaps deduped; total 690 judgments)",
          all(165 <= n <= 180 for n in q_sizes.values()) and sum(q_sizes.values()) == 690,
          str(q_sizes))

    # ---------------- servers up ----------------
    print("\n== Starting 4 labeler servers ==")
    procs: dict[str, subprocess.Popen] = {}
    ports = dict(zip(LABELER_IDS, args.ports))
    try:
        for lab, port in ports.items():
            procs[lab] = start_server(lab, port)
        up = {lab: wait_ready(p) for lab, p in ports.items()}
        check("all 4 servers respond", all(up.values()), str(up))

        # live wire-format leakage check (HTML + first JSON payload per labeler)
        for lab, port in ports.items():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r:
                html = r.read().decode().lower()
            # the labeler's own id in the page <h1> is by design, not provenance
            html_hits = [t for t in PROVENANCE_VOCAB if t in html and t != lab]
            st, nxt = api(port, "/api/next")
            json_hits = [t for t in PROVENANCE_VOCAB
                         if t in json.dumps(nxt["item"]).lower()]
            if lab == "labeler_a":
                check("served HTML has zero provenance vocab", not html_hits, str(html_hits))
                check("served JSON item has exactly the blind-safe keys",
                      set(nxt["item"]) == SERVED_ITEM_KEYS, str(sorted(nxt["item"])))
            check(f"no provenance vocab in HTML/JSON ({lab})",
                  not html_hits and not json_hits)

        # ---------------- Phase 2: labeling session ----------------
        print(f"\n== Phase 2: session — 4 labelers x {args.items} items via HTTP ==")
        for lab, port in ports.items():
            n = 0
            while n < args.items:
                st, nxt = api(port, "/api/next")
                assert st == 200 and nxt["item"], f"{lab}: queue exhausted"
                it = nxt["item"]
                st, resp = api(port, "/api/label",
                               sim_label(it["gold_id"], lab, it["masked_text"]))
                assert st == 200, f"{lab}: save failed: {resp}"
                n += 1
            check(f"{lab} labeled {args.items} items (done={resp['done']}/{resp['total']})",
                  resp["done"] == args.items)

        # ---------------- Phase 3: adversarial ops ----------------
        print("\n== Phase 3: adversarial ops cases ==")

        # (a) mid-session restart -> resume
        procs["labeler_a"].send_signal(signal.SIGINT)
        procs["labeler_a"].wait(timeout=10)
        procs["labeler_a"] = start_server("labeler_a", ports["labeler_a"])
        resumed = wait_ready(ports["labeler_a"])
        st, nxt = api(ports["labeler_a"], "/api/next")
        expected_next = queues["labeler_a"][args.items]["gold_id"]
        check("restart mid-session: server back up", resumed)
        check("resume: done count survives restart", nxt["done"] == args.items,
              f"done={nxt['done']}")
        check("resume: next item is the first unlabeled one",
              nxt["item"]["gold_id"] == expected_next, nxt["item"]["gold_id"])

        # (b) duplicate submission -> append-only keeps both; export keeps latest
        dup_gid = nxt["item"]["gold_id"]
        st1, _ = api(ports["labeler_a"], "/api/label",
                     {"gold_id": dup_gid, "label": "unsure", "rules": [], "reason": "first"})
        st2, _ = api(ports["labeler_a"], "/api/label",
                     {"gold_id": dup_gid, "label": "non_sif", "rules": [], "reason": "second"})
        lines = [json.loads(l) for l in
                 open(LABELS_DIR / "labeler_a.jsonl") if json.loads(l)["gold_id"] == dup_gid]
        check("duplicate submission accepted+appended (append-only contract)",
              st1 == 200 and st2 == 200 and len(lines) == 2,
              f"{len(lines)} records for {dup_gid}")

        # (c) invalid payloads
        st, r = api(ports["labeler_b"], "/api/label",
                    {"gold_id": queues["labeler_b"][args.items]["gold_id"],
                     "label": "maybe", "rules": []})
        check("invalid label value rejected (400)", st == 400, r.get("error", ""))
        foreign = next(it["gold_id"] for it in queues["labeler_c"]
                       if it["gold_id"] not in {x["gold_id"] for x in queues["labeler_b"]})
        st, r = api(ports["labeler_b"], "/api/label",
                    {"gold_id": foreign, "label": "sif", "rules": []})
        check("gold_id outside labeler's queue rejected (400)", st == 400, r.get("error", ""))
        st, r = api(ports["labeler_b"], "/api/label",
                    {"gold_id": queues["labeler_b"][args.items]["gold_id"],
                     "label": "sif", "rules": ["underwater_basket_weaving"]})
        check("unknown rule tag rejected (400)", st == 400, r.get("error", ""))

        # (d) port already in use
        dup = subprocess.run([sys.executable, "gold/labeler_app.py", "--labeler", "c",
                              "--port", str(ports["labeler_c"])],
                             cwd=ROOT, capture_output=True, text=True, timeout=30)
        check("second instance on same port exits non-zero with clear message",
              dup.returncode == 2 and "already running" in dup.stderr,
              f"rc={dup.returncode}: {dup.stderr.strip().splitlines()[-1] if dup.stderr else ''}")

        # ---------------- Phase 4: doubles top-up ----------------
        print("\n== Phase 4: top up doubles so the n=2 kappa subset is non-empty ==")
        gold = {json.loads(l)["gold_id"]: json.loads(l) for l in open(GOLD)}
        have: dict[str, set[str]] = {}
        for f in LABELS_DIR.glob("labeler_*.jsonl"):
            for l in open(f):
                rec = json.loads(l)
                have.setdefault(rec["gold_id"], set()).add(f.stem)
        topped = 0
        for gid, it in gold.items():
            a = it["assignment"]
            if not (a["is_double"] and not it["is_pilot"]):
                continue
            want = {a["labeler"], a["second_labeler"]}
            missing = want - have.get(gid, set())
            if len(missing) == 1:
                lab = missing.pop()
                st, _ = api(ports[lab], "/api/label",
                            sim_label(gid, lab, it["masked_text"]))
                assert st == 200, f"top-up failed for {gid} on {lab}"
                topped += 1
        check("double items topped up to 2 raters", topped > 0, f"{topped} second labels")

        # ---------------- Phase 5: export ----------------
        print("\n== Phase 5: export ==")
        exp = subprocess.run([sys.executable, "gold/export_labels.py"],
                             cwd=ROOT, capture_output=True, text=True, timeout=300)
        print("  " + exp.stdout.replace("\n", "\n  ").rstrip())
        check("export_labels.py exits 0", exp.returncode == 0, exp.stderr.strip()[-200:])
        merged = [json.loads(l) for l in open(MERGED)]
        check("labels_merged.jsonl rows == labeled distinct items", len(merged) > 0,
              f"{len(merged)} rows")
        agree = json.loads(AGREEMENT.read_text())
        dbl = agree["subsets"].get("double_labeled", {})
        pil = agree["subsets"].get("n_raters_4", {})
        check("Fleiss' kappa computed on double-labeled subset (n=2)",
              dbl.get("items", 0) > 0 and dbl.get("fleiss_kappa") is not None,
              f"{dbl.get('items')} items, kappa={dbl.get('fleiss_kappa')} "
              f"± {dbl.get('bootstrap_se')}, raw={dbl.get('raw_agreement_pct')}%")
        check("pilot subset computed (n=4)", pil.get("items") == 20
              and pil.get("fleiss_kappa") is not None,
              f"{pil.get('items')} items, kappa={pil.get('fleiss_kappa')}")
        dup_row = next(r for r in merged if r["gold_id"] == dup_gid)
        check("export keeps LATEST record on duplicate (non_sif wins over unsure)",
              dup_row["labels"]["labeler_a"]["label"] == "non_sif",
              str(dup_row["labels"]["labeler_a"]["label"]))
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
        for p in procs.values():
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()

    print("\n== SUMMARY ==")
    fails = [c for c in CHECKS if not c[1]]
    print(f"{len(CHECKS) - len(fails)}/{len(CHECKS)} checks PASS")
    if fails:
        for name, _, detail in fails:
            print(f"  FAIL: {name} — {detail}")
        print("\nNOTE: simulated label files were LEFT in artifacts/gold/labels/ — "
              "run --reset before humans start.")
        return 1
    print("NOTE: simulated label files were LEFT in artifacts/gold/labels/ — "
          "run --reset before humans start.")
    return 0


def reset() -> int:
    print("== RESET: removing all simulated labeling output ==")
    if LABELS_DIR.exists():
        shutil.rmtree(LABELS_DIR)
        print(f"  deleted {LABELS_DIR}/")
    for f in (MERGED, AGREEMENT):
        if f.exists():
            f.unlink()
            print(f"  deleted {f}")
    ok = (not LABELS_DIR.exists() or not any(LABELS_DIR.iterdir())) \
        and not MERGED.exists() and not AGREEMENT.exists()
    print(f"  verify: labels dir absent/empty, merged+agreement absent -> "
          f"{'CLEAN' if ok else 'NOT CLEAN'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
