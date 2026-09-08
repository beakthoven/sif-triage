"""Admin export: merge per-labeler files, compute human-vs-human agreement.

Reads artifacts/gold/labels/labeler_*.jsonl (append-only, timestamped),
keeps the LATEST record per (labeler, gold_id), and writes:

  artifacts/gold/labels_merged.jsonl   one row per gold_id with all labels
  artifacts/gold/agreement.json        Fleiss' kappa + bootstrap SE

Fleiss' kappa is implemented from scratch (stdlib) over the 3 label
categories {sif, non_sif, unsure}. Human-vs-human only (SEV2-3: model-vs-
human kappa is not validity). Items are grouped by rater count: the
double-labeled subset (n=2 raters/item) carries the spec'd kappa; the
calibration pilot (n=4 raters/item) is reported separately.

Self-test (hand-computed):  python3 gold/export_labels.py --self-test
Merge:                      python3 gold/export_labels.py
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gold_common import LABELS, SEED  # noqa: E402

BOOTSTRAP_N = 1000


def fleiss_kappa(counts: list[list[int]]) -> float:
    """counts[i][j] = number of raters assigning item i to category j.
    Every item must have the same total rater count n >= 2."""
    n_items = len(counts)
    n_raters = sum(counts[0])
    assert n_items > 0 and n_raters >= 2
    assert all(sum(c) == n_raters for c in counts)
    k = len(counts[0])
    p_i = [(sum(x * x for x in c) - n_raters) / (n_raters * (n_raters - 1)) for c in counts]
    p_bar = sum(p_i) / n_items
    p_j = [sum(c[j] for c in counts) / (n_items * n_raters) for j in range(k)]
    p_e = sum(p * p for p in p_j)
    if math.isclose(p_e, 1.0):
        return float("nan")  # degenerate: a category has all ratings
    return (p_bar - p_e) / (1.0 - p_e)


def kappa_matrix(item_labels: list[list[str]]) -> list[list[int]]:
    """item_labels[i] = list of category labels for item i (fixed length)."""
    idx = {c: j for j, c in enumerate(LABELS)}
    return [[Counter(labs).get(c, 0) for c in LABELS] for labs in item_labels]


def bootstrap_se(item_labels: list[list[str]], n_boot: int, seed: int) -> float:
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        sample = [item_labels[rng.randrange(len(item_labels))] for _ in item_labels]
        k = fleiss_kappa(kappa_matrix(sample))
        if not math.isnan(k):
            vals.append(k)
    if len(vals) < 2:
        return float("nan")
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def self_test() -> int:
    # Hand-computed: 3 raters, 4 items, 2 categories.
    # P = [1, 1, 1/3, 1/3] -> P_bar = 2/3; p = (0.5, 0.5) -> P_e = 0.5
    # kappa = (2/3 - 1/2) / (1 - 1/2) = 1/3
    m = [[3, 0], [0, 3], [2, 1], [1, 2]]
    got = fleiss_kappa(m)
    assert abs(got - 1 / 3) < 1e-12, f"hand example: {got} != 1/3"

    # Perfect agreement -> kappa == 1 regardless of marginals.
    got = fleiss_kappa([[2, 0], [0, 2], [2, 0], [0, 2]])
    assert got == 1.0, f"perfect agreement: {got}"

    # Same but one split item: P_bar = 0.8, P_e = 0.5 -> kappa = 0.6.
    got = fleiss_kappa([[2, 0], [0, 2], [2, 0], [0, 2], [1, 1]])
    assert abs(got - 0.6) < 1e-12, f"mixed: {got}"

    # 2-rater case: two agreed + two split -> P_bar = 0.5, P_e = 0.5 -> 0.
    got = fleiss_kappa([[2, 0], [0, 2], [1, 1], [1, 1]])
    assert abs(got) < 1e-12, f"chance agreement: {got}"

    # kappa_matrix wiring: label names map to the right columns.
    mats = kappa_matrix([["sif", "sif"], ["non_sif", "unsure"]])
    assert mats == [[2, 0, 0], [0, 1, 1]], mats

    print("kappa self-test: PASS (hand example kappa=1/3, perfect=1, chance=0)")
    return 0


def load_labels(labels_dir: Path) -> dict[str, dict[str, dict]]:
    """gold_id -> labeler -> latest record."""
    per_item: dict[str, dict[str, dict]] = {}
    for path in sorted(labels_dir.glob("labeler_*.jsonl")):
        labeler = path.stem
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                per_item.setdefault(rec["gold_id"], {})[labeler] = rec
    return per_item


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gold", default="artifacts/gold/gold_items.jsonl")
    ap.add_argument("--labels-dir", default="artifacts/gold/labels")
    ap.add_argument("--out", default="artifacts/gold/labels_merged.jsonl")
    ap.add_argument("--agreement", default="artifacts/gold/agreement.json")
    ap.add_argument("--bootstrap", type=int, default=BOOTSTRAP_N)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    gold = {}
    with open(args.gold, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                gold[r["gold_id"]] = r

    per_item = load_labels(Path(args.labels_dir))
    merged = []
    for gid in sorted(per_item):
        labs = per_item[gid]
        g = gold.get(gid, {})
        votes = [r["label"] for r in labs.values()]
        merged.append(
            {
                "gold_id": gid,
                "source_stratum": g.get("source_stratum"),
                "is_pilot": g.get("is_pilot"),
                "is_double": g.get("assignment", {}).get("is_double"),
                "n_labels": len(labs),
                "agree": len(set(votes)) == 1,
                "labels": {
                    lab: {
                        "label": r["label"],
                        "rules": r["rules"],
                        "reason": r["reason"],
                        "ts": r["ts"],
                    }
                    for lab, r in sorted(labs.items())
                },
            }
        )

    with open(args.out, "w", encoding="utf-8") as fh:
        for row in merged:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Agreement, grouped by rater count (Fleiss needs fixed n per item).
    by_n: dict[int, list[list[str]]] = {}
    for gid, labs in per_item.items():
        if len(labs) >= 2:
            by_n.setdefault(len(labs), []).append([r["label"] for r in labs.values()])

    agreement = {"categories": list(LABELS), "subsets": {}}
    for n, item_labels in sorted(by_n.items()):
        k = fleiss_kappa(kappa_matrix(item_labels))
        se = bootstrap_se(item_labels, args.bootstrap, args.seed)
        n_agree = sum(1 for labs in item_labels if len(set(labs)) == 1)
        subset = "double_labeled" if n == 2 else f"n_raters_{n}"
        agreement["subsets"][subset] = {
            "items": len(item_labels),
            "raters_per_item": n,
            "fleiss_kappa": None if math.isnan(k) else round(k, 4),
            "bootstrap_se": None if math.isnan(se) else round(se, 4),
            "bootstrap_reps": args.bootstrap,
            "raw_agreement_pct": round(100 * n_agree / len(item_labels), 2),
            "note": "calibration pilot subset" if n > 2 else
                    "spec'd kappa subset (gold.labeling.agreement)",
        }
        print(f"  n={n} raters: {len(item_labels)} items, "
              f"kappa={agreement['subsets'][subset]['fleiss_kappa']} "
              f"± {agreement['subsets'][subset]['bootstrap_se']} (SE), "
              f"raw agreement {agreement['subsets'][subset]['raw_agreement_pct']}%")

    with open(args.agreement, "w", encoding="utf-8") as fh:
        json.dump(agreement, fh, indent=2)
    print(f"wrote {args.out} ({len(merged)} items) + {args.agreement}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
