#!/usr/bin/env python3
"""De-saturate the demo database (Workstream B1).

The current demo DB (artifacts/demo/demo_pre.db, 5056 rows) was seeded from
the training corpus, so the classifier scores its own training data: live
flag_rate 0.7095, median score 0.958, 59.7% near-dup banner rate — triage
value destroyed and patterns.json saturated (all 197 site×activity cells at
sif_rate 1.0, one identical lift 1.499).

This builder replaces the corpus-derived rows with a NOVEL, NEGATIVE-DOMINANT
seed written register-style (short operational English: observations,
housekeeping, inspections, toolbox talks, training records, admin), mixed to
approximately domain-realistic composition (~20% genuine SIF precursor
reports, 80% routine/negative register). None of the texts appear verbatim
in the training corpus (see artifacts/demo/SEED_PROVENANCE.md for the
construction method and its honest limitations — including that the
generator LLM that produced the synthetic corpus is not recorded anywhere in
this repo: a reproducibility gap).

A small deliberately-memorised subset (~80 rows lifted verbatim from the
training corpus) is kept so the near-dup "memory, not generalisation" banner
feature still demonstrates — that is a genuine asset of the system.

Outputs:
  artifacts/demo/demo_pre_v2.db   (new seed; live demo_pre.db is NOT touched
                                   from here — promotion is a separate step)
Usage:
  .venv/bin/python scripts/data_pipeline/build_demo_seed_v2.py [--out PATH]
  .venv/bin/python scripts/data_pipeline/build_demo_seed_v2.py --count-only
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DATA_PIPELINE = REPO / "data_pipeline"
if str(DATA_PIPELINE) not in sys.path:
    sys.path.insert(0, str(DATA_PIPELINE))

from load_data import create_db, normalize  # noqa: E402
from seed_corpora import seed_corpora  # noqa: E402
from demo_seed import MEMORIZED  # noqa: E402

from seed_v2.corpus import build_corpus  # noqa: E402

ART_DEMO = REPO / "artifacts" / "demo"
DEFAULT_OUT = ART_DEMO / "demo_pre_v2.db"
CATEGORIES = ("injury", "nearmiss", "unsafe", "environment", "housekeeping")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=20260930)
    ap.add_argument("--count-only", action="store_true")
    args = ap.parse_args()

    rows = build_corpus(args.seed)
    sizes = Counter(c for _, c, _, _ in rows)
    print(
        "corpus composition: "
        + ", ".join(f"{k}={sizes.get(k, 0)}" for k in CATEGORIES)
        + f" total={len(rows)}"
    )
    if args.count_only:
        return 0

    out = args.out if args.out.is_absolute() else REPO / args.out
    if out.exists():
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    create_db(str(out))

    rng = random.Random(args.seed)
    now = datetime(2026, 9, 28, 9, 30, 0)
    conn = sqlite3.connect(str(out))
    cur = conn.cursor()

    # 1) novel register-style rows
    for i, (text, cat, area, act) in enumerate(rows):
        report_no = f"V2-{2026000 + i}"
        when = now - timedelta(
            days=rng.randint(0, 120),
            hours=rng.randint(6, 18),
            minutes=rng.randint(0, 59),
        )
        cur.execute(
            "INSERT INTO reports "
            "(report_no, report_date, category, text, normalized_text, area, activity) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                report_no,
                when.date().isoformat(),
                cat,
                text,
                normalize(text),
                area,
                act,
            ),
        )

    # 2) deliberately memorised subset, pulled from the live demo DB
    lookup = {
        r[0]: r for r in conn.execute(
            "SELECT report_no, report_date, category, text, normalized_text, "
            "area, activity FROM reports"
        )
    }
    memorised = 0
    for report_no, category in MEMORIZED:
        src = lookup.get(report_no)
        if src is None or src[2] != category:
            continue
        when = now - timedelta(
            days=rng.randint(30, 150),
            hours=rng.randint(6, 18),
            minutes=rng.randint(0, 59),
        )
        cur.execute(
            "INSERT INTO reports "
            "(report_no, report_date, category, text, normalized_text, area, activity) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                f"{report_no}-M",
                when.date().isoformat(),
                category,
                src[3],
                src[4],
                src[5],
                src[6],
            ),
        )
        memorised += 1
    print(f"memorised rows inserted: {memorised}/{len(MEMORIZED)}")

    # 3) patterns live off the reports table (with overridden counts backfilled)
    seed_corpora(str(out))
    cur.execute(
        "UPDATE reports SET overridden_by='demo_seed_v2' WHERE overridden_by IS NULL"
    )
    conn.commit()
    n_reports = cur.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    n_overridden = cur.execute(
        "SELECT COUNT(*) FROM reports WHERE overridden_by IS NOT NULL"
    ).fetchone()[0]
    print(f"total rows: {n_reports}; overridden flag: {n_overridden}")
    conn.close()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
