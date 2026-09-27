#!/usr/bin/env python3
"""Generate and write the negative-dominant register-style demo DB (v2).

Replaces the source DB referenced by artifacts/demo/run_metrics.json
(70.9% false-flag rate on the demo DB, 0% on training set).

Reproduce with:
    python scripts/data_pipeline/seed_v2/build_demo_seed_v2.py --write
    python scripts/data_pipeline/seed_v2/build_demo_seed_v2.py --verify
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

DEFAULT_DB = os.path.join(ROOT, "data", "incident_register_demo_v2.db")
PROVENANCE = os.path.join(ROOT, "artifacts", "demo", "SEED_PROVENANCE.md")


def rows(seed: int = 20260930):
    from corpus import build_corpus  # local import so --help works offline
    return build_corpus(seed)


def write_db(path: str, seed: int) -> None:
    data = rows(seed)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS incident_register")
    cur.execute(
        """
        CREATE TABLE incident_register (
            id INTEGER PRIMARY KEY,
            incident_description TEXT NOT NULL,
            incident_type TEXT NOT NULL,
            area_of_incident TEXT NOT NULL,
            activity_at_time TEXT NOT NULL
        )
        """
    )
    cur.executemany(
        "INSERT INTO incident_register "
        "(incident_description, incident_type, area_of_incident, activity_at_time) "
        "VALUES (?, ?, ?, ?)",
        data,
    )
    conn.commit()
    conn.close()
    print(f"wrote {path}: {len(data)} rows")
    print(f"category mix: {dict(Counter(c for _, c, _, _ in data))}")


def verify(path: str) -> dict:
    """Dedup check: no exact-text collision with data/*.json or demo_seed.py."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT incident_description FROM incident_register")
    db_texts = [r[0] for r in cur.fetchall()]
    conn.close()

    # training-corpus texts
    train_texts: set[str] = set()
    data_dir = os.path.join(ROOT, "data")
    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(data_dir, fname), encoding="utf-8") as fh:
            payload = json.load(fh)
        for rec in payload if isinstance(payload, list) else payload.get("records", []):
            for key in ("incident_description", "description", "text", "report"):
                v = rec.get(key) if isinstance(rec, dict) else None
                if isinstance(v, str):
                    train_texts.add(v.strip())

    # demo_seed.py TEMPLATES
    seed_py = os.path.join(ROOT, "scripts", "demo_seed.py")
    seed_texts: set[str] = set()
    if os.path.exists(seed_py):
        with open(seed_py, encoding="utf-8") as fh:
            src = fh.read()
        # crude but effective: strings inside TEMPLATES block
        import ast
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Constant,)) and isinstance(node.value, str):
                seed_texts.add(node.value.strip())

    exact_db = {t.strip() for t in db_texts}
    dup_train = exact_db & train_texts
    dup_seed = exact_db & seed_texts
    result = {
        "db_rows": len(db_texts),
        "unique_texts": len(exact_db),
        "collisions_with_training_data": sorted(dup_train),
        "collisions_with_demo_seed": sorted(dup_seed),
        "pass": not dup_train and not dup_seed,
    }
    print(json.dumps(result, indent=2)[:4000])
    if not result["pass"]:
        print("FAIL: exact-text collisions with existing corpus", file=sys.stderr)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write the DB")
    ap.add_argument("--verify", action="store_true", help="dedup check only")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--seed", type=int, default=20260930)
    args = ap.parse_args()
    if args.write:
        write_db(args.db, args.seed)
    if args.verify or not args.write:
        verify(args.db)


if __name__ == "__main__":
    main()
