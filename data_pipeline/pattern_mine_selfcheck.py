"""Self-check for the pattern mining engine + /api/patterns wiring.

Asserts:
  1. lift / rate / Wilson CI on a hand-verifiable 10-row corpus (exact numbers)
  2. wilson() parity with app.routes._wilson (drift guard — see ponytail note
     in pattern_mine.py)
  3. real synthetic corpus: pattern counts, min-support enforced, CIs in [0,1]
     and bracketing the rate, lift consistent with base rate, ranking order
  4. artifacts/patterns/patterns.json + demo_density_seed.json sane
  5. SQLite precomputed-table round-trip
  6. GET /api/patterns serves current live SQLite aggregation for both kinds

Run: .venv/bin/python data_pipeline/pattern_mine_selfcheck.py
Exit 0 = pass. Spawns uvicorn on :8187/:8188 (not the app's :8177).
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

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.routes import _wilson as routes_wilson  # noqa: E402
from app.storage import SQLiteStorage  # noqa: E402
from data_pipeline.pattern_mine import (  # noqa: E402
    MIN_SUPPORT,
    density_seed,
    load_rows,
    mine,
    wilson,
)

PATTERNS_JSON = REPO_ROOT / "artifacts" / "patterns" / "patterns.json"
SEED_JSON = REPO_ROOT / "artifacts" / "patterns" / "demo_density_seed.json"


def check(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"FAIL: {label}")
    print(f"  ok: {label}")


def req(port: int, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        f"http://127.0.0.1:{port}/api{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def serve(port: int, db_path: Path, patterns_file: str) -> subprocess.Popen:
    env = dict(os.environ, SIF_DB_PATH=str(db_path), SIF_PATTERNS_FILE=patterns_file)
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=REPO_ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        try:
            status, _ = req(port, "GET", "/health")
            if status == 200:
                return server
        except urllib.error.URLError:
            time.sleep(0.2)
    server.terminate()
    raise AssertionError(f"server did not come up on :{port}")


def main() -> int:
    print("[1] hand-verifiable example (10-row corpus, base rate 0.4)")
    hand = [
        {"id": f"h{i}", "site": "S" if i < 4 else "T", "activity": "A" if i < 4 else "B",
         "barrier": "b1", "rules": ["line_of_fire"],
         "sif_potential": 1 if i in (0, 1, 2, 4) else 0}
        for i in range(10)
    ]
    payload = mine(hand, min_support=1)
    check(payload["corpus"]["n_rows"] == 10 and payload["corpus"]["base_rate"] == 0.4,
          "base rate 4/10 = 0.4")
    cell = next(c for c in payload["site_x_activity"] if c["site"] == "S" and c["activity"] == "A")
    check(cell["n"] == 4 and cell["n_sif"] == 3, "cell support n=4, n_sif=3")
    check(cell["sif_rate"] == 0.75, "cell rate 3/4 = 0.75")
    check(cell["lift"] == 1.875, "lift 0.75/0.4 = 1.875")
    check(cell["ci_low"] == 0.3006 and cell["ci_high"] == 0.9544,
          "Wilson(0.75, 4) = [0.3006, 0.9544] (hand constants)")
    lo, hi = wilson(0.75, 4)
    check(abs(lo - 0.3006360524426366) < 1e-12 and abs(hi - 0.9544139373553637) < 1e-12,
          "wilson() matches full-precision constants")
    check(cell["rule"] == "line_of_fire", "dominant rule carried through")

    print("[2] wilson parity: data_pipeline.pattern_mine vs app.routes")
    for n in (1, 5, 10, 100):
        for k in range(n + 1):
            p = k / n
            check(wilson(p, n) == routes_wilson(p, n), f"parity p={p:.2f} n={n}")

    print("[3] labeled demo seed corpus (corpus mode)")
    rows = load_rows()
    check(len(rows) > 4_000, f"seed corpus loaded: {len(rows)} unique rows")
    n_sif = sum(1 for r in rows if r.get("sif_potential") == 1)
    base_rate = n_sif / len(rows)
    check(0.10 <= base_rate <= 0.35, f"seed precursor share {base_rate:.3f} in the ~20% band")
    payload = mine(rows)
    check(payload["corpus"]["n_sif"] == n_sif, "n_sif consistent with labels")
    sxa, axb = payload["site_x_activity"], payload["activity_x_barrier"]
    check(len(sxa) > 20 and len(axb) > 10, f"{len(sxa)} site×activity + {len(axb)} activity×barrier cells")
    check(len(payload["barrier_modes"]) > 0, "barrier modes present")
    check(all(c["n"] >= MIN_SUPPORT for c in sxa + axb), f"min support n>={MIN_SUPPORT} enforced")
    check(all(0.0 <= c["ci_low"] <= c["sif_rate"] + 1e-4 and
              c["sif_rate"] <= c["ci_high"] + 1e-4 <= 1.0 + 1e-4 for c in sxa + axb),
          "every CI in [0,1] and bracketing the rate")
    base = payload["corpus"]["base_rate"]
    check(all(abs(c["lift"] - c["sif_rate"] / base) < 0.002 for c in sxa + axb),
          "lift == rate / base rate (within rounding)")
    check(all(sxa[i]["lift"] >= sxa[i + 1]["lift"] for i in range(len(sxa) - 1)),
          "site×activity ranked by lift desc")
    check(all(axb[i]["lift"] >= axb[i + 1]["lift"] for i in range(len(axb) - 1)),
          "activity×barrier ranked by lift desc")
    check(all(c["barrier"] != "none" for c in axb + payload["barrier_modes"]),
          "generator placeholder barrier 'none' excluded")
    check(len({c["sif_rate"] for c in sxa}) > 1, "cell rates are not fully saturated")

    print("[4] SERVED artifacts on disk (live-DB mined by pattern_mine_live.py)")
    disk = json.loads(PATTERNS_JSON.read_text())
    check(disk["corpus"].get("source", "").startswith("live-db:"),
          f"patterns.json source = {disk['corpus'].get('source')}")
    check(len(disk["activity_x_barrier"]) == 0 and len(disk["barrier_modes"]) == 0,
          "served barrier families empty by construction (no barrier facet at ingest)")
    served = disk["site_x_activity"]
    check(len(served) > 20, f"{len(served)} served cells")
    thr = disk["corpus"]["threshold"]
    check(len({c["sif_rate"] for c in served}) > 1, "served cell rates are not fully saturated")
    check(all(0.0 <= c["ci_low"] <= c["sif_rate"] <= c["ci_high"] <= 1.0 for c in served),
          "served CIs bracket the rate")
    check(all(served[i]["lift"] >= served[i + 1]["lift"] for i in range(len(served) - 1)),
          "served ranked by lift desc")
    seed = json.loads(SEED_JSON.read_text())
    check(seed["grain"] == "site_x_activity" and len(seed["rows"]) > 20,
          "density seed has site×activity rows")
    check(sum(r["n_reports"] for r in seed["rows"]) == disk["corpus"]["n_rows"],
          "density seed covers every scored DB row")
    check(sum(r["n_flagged"] for r in seed["rows"]) == disk["corpus"]["n_flagged"],
          "density seed flagged count matches the served payload")
    regenerated = density_seed(rows)
    check(len(regenerated["rows"]) > 20, "corpus-mode density_seed() still works on the seed corpus")

    print("[5] SQLite precomputed-table round-trip")
    with tempfile.TemporaryDirectory(prefix="sif-pat-") as tmp:
        storage = SQLiteStorage(Path(tmp) / "t.db")
        storage.save_precomputed("patterns", payload)
        loaded = storage.load_precomputed("patterns")
        check(loaded == json.loads(json.dumps(payload)), "save/load round-trip identical")
        check(storage.load_precomputed("missing") is None, "missing key -> None")
        storage.close()

        print("[6] GET /api/patterns serves current live aggregation")
        server = serve(8187, Path(tmp) / "api.db", str(Path(tmp) / "ignored-patterns.json"))
        try:
            status, empty = req(8187, "GET", "/patterns")
            check(status == 200 and empty == [], "empty DB ignores configured pattern artifact")
            csv = ("narrative,site,activity\n"
                   '"Worker at height on scaffold without harness near derrick",Baghjan,maintenance\n'
                   '"Confined space entry into tank without gas test or permit",Duliajan,tank cleaning\n'
                   '"Crane lifting operation with damaged sling over live equipment",Moran,lifting\n')
            status, _ = req(8187, "POST", "/ingest", {"csv": csv, "source": "selfcheck"})
            check(status == 200, "live aggregation ingest 200")
            _, live = req(8187, "GET", "/patterns?min_n=1")
            check(len(live) == 3 and all(p["kind"] == "site_activity" for p in live),
                  "live site×activity aggregation covers current reports")
            check(all(0.0 <= p["ci_low"] <= p["sif_rate"] <= p["ci_high"] <= 1.0 for p in live),
                  "live CIs bracket the rate")
            _, barriers = req(8187, "GET", "/patterns?kind=activity_barrier&min_n=1&limit=100")
            check(isinstance(barriers, list) and all(p["kind"] == "activity_barrier" for p in barriers),
                  "live activity×barrier response uses the canonical shape")
        finally:
            server.terminate()
            server.wait(timeout=10)

    print("\nSELF-CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
