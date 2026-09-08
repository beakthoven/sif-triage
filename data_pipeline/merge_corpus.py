"""Merge QA-passing synthetic rows into the training corpus (Day-1 critical path).

artifacts/corpus/train_final.jsonl = artifacts/corpus/train.jsonl
                                     + ALL rows in artifacts/synthetic/clean/*.jsonl
Synthetic goes to TRAIN ONLY — val/test are never touched.

Schema: every output row has exactly the 15 corpus keys
(id, text, masked_text, sif_label, rules, primary_rule, well_control, site,
 activity, barrier, source, employer, event_date, naics, oiics_event).
Synthetic rows gain employer/event_date/naics/oiics_event = null and a
masked_text built by RUNNING the masker on their text (assert 0 changes —
generators were outcome-banned and QA already dropped every stem match).
Synthetic `register` and `jaccard_max` are NOT carried into the merged corpus
(kept in clean/*.jsonl; documented in the Day-1 report).

primary_rule for synthetic rows: spec primary_tie_order applied to the row's
rules list (keyword-match order is a real-corpus concept; tie order is the
spec's deterministic fallback).

Shuffle: seed 42.

SPEC DEVIATIONS (documented, flagged for orchestrator adjudication):
  - Frozen train_mix_ratios (55/15/15/10/5) assumed 9,000 synthetic; we merge
    ALL QA survivors and compute the ACTUAL ratios instead of down-sampling.
  - The spec line target_train_prevalence: 0.40 is internally inconsistent
    with the frozen ratios (they imply ~65% prevalence). We proceed with
    all-survivors and report the actual prevalence for adjudication.

Self-checks:
  - row count == train.jsonl + survivors
  - no synthetic id in val/test
  - zero outcome-stem matches in clean synthetic
  - quota table primary-rule counts sum to tagged positives

Run: .venv/bin/python data_pipeline/merge_corpus.py
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from masking import _PATTERN, mask_text  # noqa: E402

CORPUS = Path("artifacts/corpus")
CLEAN = Path("artifacts/synthetic/clean")
OUT = CORPUS / "train_final.jsonl"

KEYS15 = ["id", "text", "masked_text", "sif_label", "rules", "primary_rule",
          "well_control", "site", "activity", "barrier", "source",
          "employer", "event_date", "naics", "oiics_event"]

# spec/label_spec.yaml primary_tie_order (rare-first)
TIE_ORDER = ["confined_space", "energy_isolation", "safe_mechanical_lifting",
             "hot_work", "driving", "working_at_height", "line_of_fire"]

# spec frozen positive_quotas_9000
QUOTAS = {"line_of_fire": 231, "working_at_height": 535, "hot_work": 586,
          "safe_mechanical_lifting": 677, "driving": 900,
          "energy_isolation": 1351, "confined_space": 1720}
QUOTA_NEGATIVES = 3000


def primary_rule(rules: list[str]) -> str | None:
    for r in TIE_ORDER:
        if r in rules:
            return r
    return None


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Merge QA-passing synthetic rounds into the training corpus")
    ap.add_argument("--base", default=str(CORPUS / "train.jsonl"),
                    help="base corpus JSONL (train.jsonl for round 1, train_final.jsonl for top-ups)")
    ap.add_argument("--clean-dir", default=str(CLEAN))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--summary", default=str(CORPUS / "train_final_merge_summary.json"))
    args = ap.parse_args()

    with open(args.base, encoding="utf-8") as fh:
        train_rows = [json.loads(line) for line in fh]

    survivors: list[dict] = []
    for path in sorted(Path(args.clean_dir).glob("*.jsonl")):
        with open(path, encoding="utf-8") as fh:
            survivors.extend(json.loads(line) for line in fh)

    # ---- self-check: zero outcome stems in clean synthetic ------------------
    stem_hits = [r["id"] for r in survivors if _PATTERN.search(r["text"])]
    assert not stem_hits, f"outcome stems survived QA: {stem_hits[:5]}"

    # ---- convert synthetic rows to the 15-key corpus schema -----------------
    mask_changes = 0
    syn_out = []
    for r in survivors:
        masked = mask_text(r["text"])
        if masked != r["text"]:
            mask_changes += 1
        syn_out.append({
            "id": r["id"],
            "text": r["text"],
            "masked_text": masked,
            "sif_label": r["sif_potential"],
            "rules": r["rules"],
            "primary_rule": primary_rule(r["rules"]),
            "well_control": r["well_control"],
            "site": r["site"],
            "activity": r["activity"],
            "barrier": r["barrier"],
            "source": "synthetic_positive" if r["sif_potential"] == 1 else "synthetic_negative",
            "employer": None,
            "event_date": None,
            "naics": None,
            "oiics_event": None,
        })
    assert mask_changes == 0, f"masker changed {mask_changes} synthetic rows"

    for row in train_rows:
        assert sorted(row.keys()) == sorted(KEYS15), f"unexpected corpus schema in {row['id']}"

    merged = train_rows + syn_out
    random.Random(42).shuffle(merged)
    assert len(merged) == len(train_rows) + len(syn_out)

    # ---- self-check: no synthetic id anywhere in val/test -------------------
    for split in ("val", "test"):
        with open(CORPUS / f"{split}.jsonl", encoding="utf-8") as fh:
            bad = [json.loads(l)["id"] for l in fh if l.startswith('{"id": "syn-') or '"syn-' in l[:30]]
        assert not bad, f"synthetic ids leaked into {split}: {bad[:5]}"

    with open(args.out, "w", encoding="utf-8") as fh:
        for row in merged:
            fh.write(json.dumps({k: row[k] for k in KEYS15}, ensure_ascii=False) + "\n")

    # ---- actual mix ratios + prevalence -------------------------------------
    n = len(merged)
    by_source = Counter(r["source"] for r in merged)
    ratios = {k: round(v / n, 4) for k, v in sorted(by_source.items())}
    prevalence = sum(r["sif_label"] for r in merged) / n

    # ---- per-rule synthetic counts vs frozen quotas -------------------------
    pos = [r for r in syn_out if r["sif_label"] == 1]
    neg = [r for r in syn_out if r["sif_label"] == 0]
    primary_counts = Counter(r["primary_rule"] for r in pos)
    containment_counts = Counter()
    for r in pos:
        for rule in r["rules"]:
            containment_counts[rule] += 1
    assert sum(v for k, v in primary_counts.items() if k is not None) == sum(1 for r in pos if r["rules"]), \
        "quota table does not sum to tagged positives"

    quota_table = {}
    for rule, q in QUOTAS.items():
        actual = primary_counts.get(rule, 0)
        quota_table[rule] = {
            "quota_9000": q,
            "actual_primary": actual,
            "actual_containment": containment_counts.get(rule, 0),
            "shortfall_pct": round(100 * (q - actual) / q, 1),
        }
    quota_table["_negatives"] = {
        "quota_9000": QUOTA_NEGATIVES, "actual_primary": len(neg),
        "actual_containment": len(neg),
        "shortfall_pct": round(100 * (QUOTA_NEGATIVES - len(neg)) / QUOTA_NEGATIVES, 1),
    }

    syn_pos = by_source.get("synthetic_positive", 0)
    syn_neg = by_source.get("synthetic_negative", 0)
    syn_share = syn_pos + syn_neg
    summary = {
        "train_rows_in": len(train_rows),
        "synthetic_survivors": len(syn_out),
        "train_final_rows": n,
        "actual_mix_ratios": ratios,
        "frozen_mix_ratios": {"osha_positive": 0.55, "osha_low_energy_negative": 0.15,
                              "asrs_negative": 0.15, "synthetic_positive": 0.10,
                              "synthetic_negative": 0.05},
        "actual_train_prevalence": round(prevalence, 4),
        "spec_target_train_prevalence": 0.40,
        "frozen_ratios_implied_prevalence": "0.55+0.10 = 0.65 — inconsistent with 0.40; flagged for adjudication",
        "synthetic_share_of_train": round(syn_share / n, 4),
        "synthetic_pos_within_synthetic": round(syn_pos / max(syn_share, 1), 4),
        "quota_table": quota_table,
        "untagged_positives": sum(1 for r in pos if not r["rules"]),
        "tagged_negatives": sum(1 for r in neg if r["rules"]),
        "masker_changes_on_synthetic": mask_changes,
    }
    with open(args.summary, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"{args.out}: {n} rows = {len(train_rows)} base + {len(syn_out)} synthetic")
    print(f"mix ratios: {ratios}")
    print(f"prevalence: {prevalence:.4f} (spec target 0.40; frozen ratios imply ~0.65 — DEVIATION, adjudicate)")
    print(f"masker changes on synthetic: {mask_changes}")
    print("quota table (primary rule | quota -> actual, shortfall%):")
    for rule, t in quota_table.items():
        print(f"  {rule:26s} {t['quota_9000']:5d} -> {t['actual_primary']:5d}  ({t['shortfall_pct']:+.1f}%)")
    print(f"summary -> {args.summary}")


if __name__ == "__main__":
    main()
