"""Pattern mining engine — the PS's "surfaces recurring precursor patterns"
requirement as real statistics (ARCHITECTURE.md pattern bullet;
fullstack-architect §3: lift-ranked co-occurrence on structured facets with
n + Wilson CIs, honest stats, no runtime LLM tagging).

Input : synthetic facet corpus — artifacts/synthetic/clean/*.jsonl +
        artifacts/synthetic/raw_v2/*.jsonl (site / activity / barrier facets +
        sif_potential label; the demo's OIL-analog data, ~9k rows).
Output: artifacts/patterns/patterns.json          — served by GET /api/patterns
        artifacts/patterns/demo_density_seed.json — site×activity density seed
        artifacts/patterns/patterns.db            — same payload in SQLite
        (Storage.precomputed, key="patterns")

Stats per cell: support n, SIF prevalence, lift vs corpus base rate,
Wilson 95% CI on the SIF rate. Pattern families ranked by lift with
min support n >= 10; barrier-failure modes ranked by n (top 50).

Run:        .venv/bin/python data_pipeline/pattern_mine.py
Self-check: .venv/bin/python data_pipeline/pattern_mine_selfcheck.py
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GLOBS = (
    "artifacts/synthetic/clean/*.jsonl",
    "artifacts/synthetic/raw_v2/*.jsonl",
)
OUT_DIR = REPO_ROOT / "artifacts" / "patterns"
MIN_SUPPORT = 10
BARRIER_MODES_TOP = 50

# ponytail: wilson() duplicates app.routes._wilson so the offline pipeline
# stays stdlib-only (no fastapi import). pattern_mine_selfcheck asserts both
# implementations agree on a grid — drift breaks the check.


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def load_rows(globs: tuple[str, ...] = DEFAULT_GLOBS) -> list[dict]:
    """Load the synthetic facet corpus, deduped by id (first wins)."""
    seen: set[str] = set()
    rows: list[dict] = []
    for pattern in globs:
        for path in sorted(glob.glob(str(REPO_ROOT / pattern))):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    row = json.loads(line)
                    if row["id"] in seen:
                        continue
                    seen.add(row["id"])
                    rows.append(row)
    return rows


def _rank(cells: list[dict]) -> list[dict]:
    cells.sort(key=lambda r: (-r["lift"], -r["n"]))
    return cells


def mine(rows: list[dict], min_support: int = MIN_SUPPORT) -> dict:
    """Compute the full patterns payload from corpus rows."""
    n_rows = len(rows)
    n_sif = sum(1 for r in rows if r.get("sif_potential") == 1)
    base_rate = n_sif / n_rows if n_rows else 0.0

    sx_a: dict[tuple[str, str], list[int]] = {}
    ax_b: dict[tuple[str, str], list[int]] = {}
    modes: dict[str, list[int]] = {}
    rules: dict[tuple, Counter] = {}

    def bump(groups: dict, key: tuple, sif: int, rule_list: list[str]) -> None:
        cell = groups.setdefault(key, [0, 0])
        cell[0] += 1
        cell[1] += sif
        rules.setdefault(key, Counter()).update(rule_list)

    for r in rows:
        sif = 1 if r.get("sif_potential") == 1 else 0
        rule_list = r.get("rules") or []
        site, activity = r.get("site"), r.get("activity")
        # "none"/"" is the generator's placeholder for negatives (no barrier
        # failed), not a failure mode — exclude from the barrier families.
        barrier = r.get("barrier") or None
        if barrier == "none":
            barrier = None
        if site and activity:
            bump(sx_a, ("site_x_activity", site, activity), sif, rule_list)
        if activity and barrier:
            bump(ax_b, ("activity_x_barrier", activity, barrier), sif, rule_list)
        if barrier:
            bump(modes, ("barrier", barrier), sif, rule_list)

    def stats(groups: dict, names: tuple[str, ...], min_n: int) -> list[dict]:
        out = []
        for key, (n, k) in groups.items():
            if n < min_n:
                continue
            rate = k / n
            lo, hi = wilson(rate, n)
            top_rule = rules[key].most_common(1)[0][0] if rules[key] else None
            row = dict(zip(names, key[1:]))
            row.update({
                "rule": top_rule,
                "n": n,
                "n_sif": k,
                "sif_rate": round(rate, 4),
                "lift": round(rate / base_rate, 3) if base_rate > 0 else 0.0,
                "ci_low": round(lo, 4),
                "ci_high": round(hi, 4),
            })
            out.append(row)
        return _rank(out)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": (
            "lift = cell SIF rate / corpus base rate; Wilson 95% CI (z=1.96) on "
            "the SIF rate; pattern families ranked by lift with min support "
            f"n>={min_support}; barrier modes ranked by n (top {BARRIER_MODES_TOP})."
        ),
        "corpus": {
            "globs": list(DEFAULT_GLOBS),
            "n_rows": n_rows,
            "n_sif": n_sif,
            "base_rate": round(base_rate, 4),
        },
        "min_support": min_support,
        "site_x_activity": stats(sx_a, ("site", "activity"), min_support),
        "activity_x_barrier": stats(ax_b, ("activity", "barrier"), min_support),
        "barrier_modes": sorted(
            stats(modes, ("barrier",), 1),
            key=lambda r: (-r["n"], -r["lift"]),
        )[:BARRIER_MODES_TOP],
    }


def density_seed(rows: list[dict]) -> dict:
    """site×activity aggregation (n, flagged rate) for the dashboard density
    view's bulk-ingest re-rank beat. Row order mirrors GET /api/density."""
    groups: dict[tuple[str, str], list[int]] = {}
    for r in rows:
        site, activity = r.get("site"), r.get("activity")
        if not (site and activity):
            continue
        cell = groups.setdefault((site, activity), [0, 0])
        cell[0] += 1
        cell[1] += 1 if r.get("sif_potential") == 1 else 0
    out = [
        {
            "site": site,
            "activity": activity,
            "n_reports": n,
            "n_flagged": k,
            "sif_rate": round(k / n, 4),
        }
        for (site, activity), (n, k) in groups.items()
    ]
    out.sort(key=lambda r: (-r["sif_rate"], -r["n_reports"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "grain": "site_x_activity",
        "source": {
            "globs": list(DEFAULT_GLOBS),
            "n_rows": len(rows),
            "flag": "sif_potential == 1",
        },
        "rows": out,
    }


def write_db(payload: dict, db_path: Path) -> None:
    """Persist the same payload into SQLite storage (precomputed table)."""
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from app.storage import SQLiteStorage

    storage = SQLiteStorage(db_path)
    try:
        storage.save_precomputed("patterns", payload)
    finally:
        storage.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--min-support", type=int, default=MIN_SUPPORT)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--db", type=Path, default=None,
                    help="also persist payload into this SQLite file "
                         "(default: <out-dir>/patterns.db; pass 'none' to skip)")
    args = ap.parse_args()

    rows = load_rows()
    payload = mine(rows, min_support=args.min_support)
    seed = density_seed(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    patterns_path = args.out_dir / "patterns.json"
    seed_path = args.out_dir / "demo_density_seed.json"
    patterns_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    seed_path.write_text(json.dumps(seed, indent=2), encoding="utf-8")

    db_path = args.db if args.db is not None else args.out_dir / "patterns.db"
    if str(db_path).lower() != "none":
        write_db(payload, db_path)

    c = payload["corpus"]
    print(f"corpus: {c['n_rows']} rows, {c['n_sif']} SIF, base_rate={c['base_rate']}")
    print(f"site_x_activity: {len(payload['site_x_activity'])} cells (n>={args.min_support})")
    print(f"activity_x_barrier: {len(payload['activity_x_barrier'])} cells (n>={args.min_support})")
    print(f"barrier_modes: {len(payload['barrier_modes'])}")
    print(f"density seed rows: {len(seed['rows'])}")
    print(f"wrote {patterns_path}")
    print(f"wrote {seed_path}")
    if str(db_path).lower() != "none":
        print(f"wrote {db_path} (precomputed['patterns'])")
    print("\ntop-10 site_x_activity by lift:")
    for r in payload["site_x_activity"][:10]:
        print(f"  lift={r['lift']:>5}  n={r['n']:>3}  rate={r['sif_rate']:.3f} "
              f"CI=[{r['ci_low']:.3f},{r['ci_high']:.3f}]  {r['rule'] or '':<26} "
              f"{r['site']} × {r['activity']}")
    print("\ntop-10 activity_x_barrier by lift:")
    for r in payload["activity_x_barrier"][:10]:
        print(f"  lift={r['lift']:>5}  n={r['n']:>3}  rate={r['sif_rate']:.3f} "
              f"CI=[{r['ci_low']:.3f},{r['ci_high']:.3f}]  {r['rule'] or '':<26} "
              f"{r['activity']} × {r['barrier']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
