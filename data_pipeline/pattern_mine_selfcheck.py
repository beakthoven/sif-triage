"""Self-check for the pattern mining engine + /api/patterns wiring.

Asserts:
  1. lift / rate / Wilson CI on a hand-verifiable 10-row corpus (exact numbers)
  2. wilson() parity with app.routes._wilson (drift guard — see ponytail note
     in pattern_mine.py)
  3. real synthetic corpus: pattern counts, min-support enforced, CIs in [0,1]
     and bracketing the rate, lift consistent with base rate, ranking order
  4. artifacts/patterns/patterns.json + demo_density_seed.json sane
  5. SQLite precomputed-table round-trip
  6. GET /api/patterns serves the precomputed file (both kinds), and falls
     back to live DB aggregation when the file is absent

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

    print("[3] real synthetic corpus")
    rows = load_rows()
    check(len(rows) == 9027, "9027 unique rows (clean 6684 + raw_v2 2343, no id overlap)")
    payload = mine(rows)
    check(payload["corpus"]["n_sif"] == 6024 and payload["corpus"]["base_rate"] == 0.6673,
          "base rate 6024/9027 = 0.6673")
    sxa, axb = payload["site_x_activity"], payload["activity_x_barrier"]
    check(len(sxa) == 197, "197 site×activity cells at min support 10")
    check(len(axb) == 137, "137 activity×barrier cells at min support 10")
    check(len(payload["barrier_modes"]) == 50, "top-50 barrier modes")
    check(all(c["n"] >= MIN_SUPPORT for c in sxa + axb), "min support n>=10 enforced")
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
    check(any(c["rule"] == "line_of_fire" for c in axb), "line-of-fire patterns present")
    check(payload["barrier_modes"][0]["n"] >= payload["barrier_modes"][-1]["n"],
          "barrier modes ranked by n desc")

    print("[4] artifacts on disk")
    disk = json.loads(PATTERNS_JSON.read_text())
    check(len(disk["site_x_activity"]) == len(sxa) and len(disk["activity_x_barrier"]) == len(axb),
          "patterns.json matches in-memory counts")
    seed = json.loads(SEED_JSON.read_text())
    check(seed["grain"] == "site_x_activity" and len(seed["rows"]) == 4510,
          "density seed: 4510 site×activity rows")
    check(sum(r["n_reports"] for r in seed["rows"]) == 9027,
          "density seed covers the full corpus")
    check(sum(r["n_flagged"] for r in seed["rows"]) == 6024, "density seed flagged count")
    regenerated = density_seed(rows)
    check(len(regenerated["rows"]) == len(seed["rows"]), "density_seed() reproduces row count")

    print("[5] SQLite precomputed-table round-trip")
    with tempfile.TemporaryDirectory(prefix="sif-pat-") as tmp:
        storage = SQLiteStorage(Path(tmp) / "t.db")
        storage.save_precomputed("patterns", payload)
        loaded = storage.load_precomputed("patterns")
        check(loaded == json.loads(json.dumps(payload)), "save/load round-trip identical")
        check(storage.load_precomputed("missing") is None, "missing key -> None")
        storage.close()

        print("[6] GET /api/patterns serves the precomputed file")
        server = serve(8187, Path(tmp) / "api.db", str(PATTERNS_JSON))
        try:
            status, top = req(8187, "GET", "/patterns")
            check(status == 200 and len(top) == 20, "default limit 20 from file")
            check(all(p["kind"] == "site_activity" and p["site"] and p["activity"] for p in top),
                  "site_activity rows carry site + activity")
            check(all(p["n"] >= 2 for p in top), "min_n=2 default filter applied")
            check(all(top[i]["lift"] >= top[i + 1]["lift"] for i in range(len(top) - 1)),
                  "served ranked by lift desc")
            check(all(0.0 <= p["ci_low"] <= p["sif_rate"] <= p["ci_high"] <= 1.0 for p in top),
                  "served CIs bracket the rate")
            first = top[0]
            check(first["site"] == "Workover Rig #7" and first["activity"] == "derrick/mast climbing"
                  and first["n"] == 37 and first["lift"] == 1.499,
                  f"top pattern = {first['rule']} @ {first['site']} × {first['activity']} (n=37)")
            _, big = req(8187, "GET", "/patterns?min_n=30")
            check(0 < len(big) < 20 and all(p["n"] >= 30 for p in big), "min_n filter works over file")
            _, none_left = req(8187, "GET", "/patterns?min_n=100")
            check(none_left == [], "min_n=100 > max support 47 -> []")
            status, ab = req(8187, "GET", "/patterns?kind=activity_barrier&limit=100")
            check(status == 200 and len(ab) == 100, "activity_barrier kind served (limit=100)")
            check(all(p["barrier"] and p["site"] is None and p["kind"] == "activity_barrier" for p in ab),
                  "activity_barrier rows carry barrier, site null")
            check(any(p["rule"] == "line_of_fire" for p in ab), "line-of-fire in served barrier patterns")
            check(any("barricade" in p["barrier"] for p in ab),
                  "missing-barricade style pattern in served output")
        finally:
            server.terminate()
            server.wait(timeout=10)

        print("[7] fallback: file absent -> live DB aggregation")
        server = serve(8188, Path(tmp) / "api2.db", str(Path(tmp) / "no-such-file.json"))
        try:
            _, empty = req(8188, "GET", "/patterns")
            check(empty == [], "empty DB + no file -> []")
            csv = ("narrative,site,activity\n"
                   '"Worker at height on scaffold without harness near derrick",Baghjan,maintenance\n'
                   '"Confined space entry into tank without gas test or permit",Duliajan,tank cleaning\n'
                   '"Crane lifting operation with damaged sling over live equipment",Moran,lifting\n')
            status, _ = req(8188, "POST", "/ingest", {"csv": csv, "source": "selfcheck"})
            check(status == 200, "fallback ingest 200")
            _, live = req(8188, "GET", "/patterns?min_n=1")
            check(len(live) == 3 and all(p["kind"] == "site_activity" for p in live),
                  "fallback computes site×activity from DB reports")
            check(all(0.0 <= p["ci_low"] <= p["sif_rate"] <= p["ci_high"] <= 1.0 for p in live),
                  "fallback CIs bracket the rate")
            _, ab = req(8188, "GET", "/patterns?kind=activity_barrier")
            check(ab == [], "activity_barrier has no DB fallback (no barrier facet)")
        finally:
            server.terminate()
            server.wait(timeout=10)

    print("\nSELF-CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
