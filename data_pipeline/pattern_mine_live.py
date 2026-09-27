"""Mine precursor patterns from the LIVE demo database (workstream B1).

Replaces the saturated artifacts/patterns/patterns.json (all 197 cells at
sif_rate=1.0 with one identical lift 1.499, mined from the deleted balanced
synthetic corpus — numbers could never move because app/routes.py serves the
precomputed file BEFORE the live DB aggregation).

Semantics mirror the app/routes.py live fallback exactly: flag = calibrated
score >= threshold; baseline = overall flag rate over scored rows; per
site×activity cell: n, n_flagged, sif_rate, lift = cell rate / baseline,
Wilson 95% CI. activity_x_barrier / barrier_modes are emitted EMPTY on
purpose: ingested reports carry no barrier facet (app.ingest.map_columns
drops it), so a barrier-family payload would be static seed statistics
dressed up as live ones — exactly the saturation defect B1 removes.

Outputs (both served artifacts):
  artifacts/patterns/patterns.json          — GET /api/patterns payload
  artifacts/patterns/demo_density_seed.json — site×activity density seed

NOTE: this file is a SNAPSHOT of the DB at generation time. Re-run this
script after a demo ingest to refresh it — or delete patterns.json entirely,
which makes routes.py fall back to computing the same stats from the live DB
per request (numbers then move during ingest without any pipeline step).

Run:  .venv/bin/python data_pipeline/pattern_mine_live.py [--db PATH] [--threshold X]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from data_pipeline.pattern_mine import wilson  # the self-check-guarded copy

DEFAULT_DB = REPO_ROOT / "artifacts" / "demo" / "demo_pre.db"
OUT_DIR = REPO_ROOT / "artifacts" / "patterns"
DEFAULT_MODEL_DIR = REPO_ROOT / "artifacts" / "models" / "masked-v2"


def calibrated_threshold(model_dir: Path) -> float:
    """The masked-v2 flag threshold on the calibrated score scale — the same
    mapping RealOnnxClassifier._load_flag_threshold performs (D19: prefer
    operating_point_test_tuned.threshold mapped through the temperature)."""
    metrics = model_dir / "metrics.json"
    data = json.loads(metrics.read_text(encoding="utf-8"))
    tuned = data.get("operating_point_test_tuned") or {}
    raw = float(tuned["threshold"])
    temp = float(data.get("temperature") or 1.0)
    import math

    return float(1.0 / (1.0 + pow(2.718281828459045, -math.log(raw / (1 - raw)) / temp)))


def mine_db(db_path: Path, threshold: float, min_support: int = 1) -> dict:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT r.site, r.activity, p.sif_score FROM reports r"
        " JOIN predictions p ON p.report_id = r.id"
    ).fetchall()
    con.close()
    scored = [r["sif_score"] for r in rows]
    baseline = sum(1 for s in scored if s >= threshold) / len(scored) if scored else 0.0

    cells: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        key = (r["activity"] or "(unspecified)", r["site"] or "(unspecified)")
        cells.setdefault(key, []).append(r["sif_score"])
    out = []
    for (activity, site), scores in cells.items():
        n = len(scores)
        if n < min_support:
            continue
        k = sum(1 for s in scores if s >= threshold)
        rate = k / n
        lo, hi = wilson(rate, n)
        out.append({
            "rule": None, "n": n, "n_sif": k,
            "sif_rate": round(rate, 4),
            "lift": round(rate / baseline, 3) if baseline > 0 else 0.0,
            "ci_low": round(lo, 4), "ci_high": round(hi, 4),
            "activity": activity, "site": site,
        })
    out.sort(key=lambda r: (-r["lift"], -r["n"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": (
            "lift = cell flag rate / live-DB baseline flag rate; Wilson 95% CI "
            "(z=1.96); mined from the live demo DB reports JOIN predictions "
            "(flag = calibrated sif_score >= threshold); site×activity only — "
            "ingested reports carry no barrier facet, so the barrier families "
            "are empty by construction (see module docstring)."
        ),
        "corpus": {
            "source": f"live-db:{db_path.name}",
            "n_rows": len(rows),
            "n_flagged": sum(1 for s in scored if s >= threshold),
            "baseline_flag_rate": round(baseline, 4),
            "threshold": round(threshold, 6),
        },
        "min_support": min_support,
        "site_x_activity": out,
        "activity_x_barrier": [],
        "barrier_modes": [],
    }


def density_seed_from_db(db_path: Path, threshold: float) -> dict:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT r.site, r.activity, p.sif_score FROM reports r"
        " JOIN predictions p ON p.report_id = r.id"
    ).fetchall()
    con.close()
    groups: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        key = (r["activity"] or "(unspecified)", r["site"] or "(unspecified)")
        groups.setdefault(key, []).append(r["sif_score"])
    out = [
        {
            "site": site, "activity": activity,
            "n_reports": len(scores),
            "n_flagged": sum(1 for s in scores if s >= threshold),
            "sif_rate": round(sum(1 for s in scores if s >= threshold) / len(scores), 4),
        }
        for (activity, site), scores in groups.items()
    ]
    out.sort(key=lambda r: (-r["sif_rate"], -r["n_reports"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "grain": "site_x_activity",
        "source": {
            "db": str(db_path.relative_to(REPO_ROOT)),
            "n_rows": len(rows),
            "flag": f"sif_score >= {threshold:.4f} (calibrated op point)",
        },
        "rows": out,
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--threshold", type=float, default=None,
                    help="flag threshold; default = masked-v2 calibrated op point")
    ap.add_argument("--min-support", type=int, default=1)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    thr = args.threshold if args.threshold is not None else calibrated_threshold(DEFAULT_MODEL_DIR)
    payload = mine_db(args.db, thr, args.min_support)
    seed = density_seed_from_db(args.db, thr)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "patterns.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (args.out_dir / "demo_density_seed.json").write_text(json.dumps(seed, indent=2), encoding="utf-8")

    c = payload["corpus"]
    cells = payload["site_x_activity"]
    rates = sorted({cell["sif_rate"] for cell in cells})
    print(f"db: {args.db} — {c['n_rows']} scored rows, flag_rate={c['baseline_flag_rate']} (thr={c['threshold']})")
    print(f"site_x_activity cells: {len(cells)} | distinct sif_rates: {len(rates)}"
          f" {rates[:6]}{'...' if len(rates) > 6 else ''}")
    print(f"top-5 cells by lift:")
    for r in cells[:5]:
        print(f"  lift={r['lift']:>5}  n={r['n']:>4}  rate={r['sif_rate']:.3f} "
              f"CI=[{r['ci_low']:.3f},{r['ci_high']:.3f}]  {r['site']} × {r['activity']}")
    print(f"wrote {args.out_dir / 'patterns.json'}")
    print(f"wrote {args.out_dir / 'demo_density_seed.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())