"""Stream D corpus builder: OSHA + ASRS -> artifacts/corpus/{train,val,test}.jsonl.

Implements spec/label_spec.yaml (FROZEN v1.0.0):
  1. load OSHA CSV, whitespace-normalize narratives, exact-dedup pre-split
  2. labels via data_pipeline/oiics_maps.py (era-conditional B_middle sif_label,
     7-rule multi-hot, primary_rule, well_control) — imported, not modified
  3. ASRS negatives: HF elihoole/asrs-aviation-reports train shard, high-energy
     Events_Anomaly rows prescreened OUT, narratives masked with masking.py
  4. OSHA low-energy negative pool (v1 42x/7xx, v2 43x/7xx; amputated excluded),
     ALL OSHA narratives masked (positives and negatives)
  5. temporal hard split (train <= 2023-12-31, test 2024-01-01..2025-11-30),
     within-train employer-grouped val holdout (~10%, group-disjoint),
     cross-boundary 8-gram Jaccard screen (drop test J>=0.5, report J>=0.3)
  6. JSONL schema per row:
     {id, text, masked_text, sif_label, rules, primary_rule, well_control,
      site, activity, barrier, source, employer, event_date, naics, oiics_event}
  7. splits.json leakage audit
  8. console self-check + runs/run2/day1/data_pipeline_report.md

Train mix (frozen ratios, real components only — synthetic slots merge later):
  osha_positive 0.55 : osha_low_energy_negative 0.15 : asrs_negative 0.15
  (synthetic_positive 0.10 + synthetic_negative 0.05 reserved).

stdlib + pandas + numpy only. Deterministic (seed 42).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from masking import mask_text  # noqa: E402
from oiics_maps import RULES, label_frame  # noqa: E402

SEED = 42
TRAIN_END = pd.Timestamp("2023-12-31")
TEST_START = pd.Timestamp("2024-01-01")
TEST_END = pd.Timestamp("2025-11-30")

# Frozen train-mix ratios (real components; synthetic 0.15 reserved for later).
MIX = {"osha_positive": 0.55, "osha_low_energy_negative": 0.15, "asrs_negative": 0.15}
REAL_MIX_TOTAL = sum(MIX.values())  # 0.85

VAL_FRAC_OF_TRAIN = 0.10  # ~10% of real train rows, employer-group-disjoint

SHINGLE_N = 8
J_DROP = 0.5
J_REPORT = 0.3
MAX_DF = 256  # boilerplate shingles (df > MAX_DF train rows) are not indexed

# ASRS high-energy Events_Anomaly prescreen. Semantics verified by 200-row
# spot-check (seed 42, 2026-09-08; see report §ASRS). Events_Anomaly is a
# SEMICOLON-separated LIST of anomalies; each element is category + subcategory
# SPACE-joined, e.g. 'Aircraft Equipment Problem Critical; Conflict Airborne
# Conflict; Ground Excursion Runway'. A report is dropped if ANY element's
# category indicates high kinetic/potential energy or person harm; kept
# categories are procedural/deviation/equipment/ATC only.
ASRS_DROP_PREFIXES = (
    "Conflict",                    # NMAC (1555), Airborne Conflict (743), Ground Conflict (991)
    "Ground Event / Encounter",    # loss of control, ground strike, gear up, jet blast, FOD... (~867)
    "Ground Excursion",            # runway/taxiway/ramp excursion (87)
    "Ground Incursion",            # runway/taxiway incursion (11)
    "Inflight Event / Encounter",  # wake vortex, CFTT/CFIT, weather/turbulence, loss of control... (~963)
    "Flight Deck / Cabin / Aircraft Event Smoke / Fire / Fumes",  # thermal event, hot-work class (255)
    "Flight Deck / Cabin / Aircraft Event Illness / Injury",      # person-harm outcome rows (224)
)

EMPLOYER_NORM_RE = re.compile(r"[^a-z0-9 ]+")


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def norm_employer(s: str) -> str:
    s = EMPLOYER_NORM_RE.sub(" ", str(s).lower())
    return re.sub(r"\s+", " ", s).strip()


def shingles(text: str, n: int = SHINGLE_N) -> set[int]:
    toks = text.lower().split()
    if len(toks) < n:
        return set()
    return {
        int.from_bytes(hashlib.blake2b(" ".join(toks[i : i + n]).encode(), digest_size=8).digest(), "little")
        for i in range(len(toks) - n + 1)
    }


def load_osha(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype=str)
    df["text"] = df["Final Narrative"].fillna("").map(norm_ws)
    df = df[df["text"] != ""].copy()
    labeled = label_frame(df)  # adds era, oiics_prefix, sif, rules, primary_rule, well_control
    # 5 OSHA report IDs are reused for 2 distinct incidents each (data quirk,
    # verified 2026-09-08: same ID, different narrative/Event). Disambiguate
    # with a deterministic occurrence suffix.
    labeled = labeled.sort_values(["ID", "EventDate", "UPA"], kind="mergesort")
    id_counts = labeled["ID"].map(labeled["ID"].value_counts())
    occ = labeled.groupby("ID").cumcount()
    labeled["uid"] = [
        f"osha-{i}" if c == 1 else f"osha-{i}-{chr(97 + o)}"
        for i, c, o in zip(labeled["ID"], id_counts, occ)
    ]
    return labeled


def exact_dedup(labeled: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Pre-split exact dedup on normalized narrative; keeper = earliest
    (EventDate, ID). Reports within-train / within-test / cross-boundary excess."""
    d = labeled.sort_values(["EventDate", "ID"], kind="mergesort")
    dup = d["text"].duplicated(keep="first")
    keep = d[~dup].copy()
    era_of_text = d[~dup].set_index("text")["era"]
    dropped = d[dup].copy()
    dropped["keeper_era"] = dropped["text"].map(era_of_text)
    stats = {
        "excess_total": int(len(dropped)),
        "within_train": int(((dropped["era"] == "v1") & (dropped["keeper_era"] == "v1")).sum()),
        "within_test": int(((dropped["era"] == "v2") & (dropped["keeper_era"] == "v2")).sum()),
        "cross_boundary": int((dropped["era"] != dropped["keeper_era"]).sum()),
    }
    return keep, stats


def boundary_screen(train_df: pd.DataFrame, test_df: pd.DataFrame) -> tuple[pd.Series, dict]:
    """8-gram Jaccard screen of test narratives vs train-era narratives.
    Distinctive-shingle inverted index (df<=MAX_DF) as sorted numpy arrays.
    Returns (test_max_jaccard Series, stats)."""
    tr_shingle_sets = [shingles(t) for t in train_df["text"]]
    tr_sizes = np.array([len(s) for s in tr_shingle_sets], dtype=np.int64)
    hashes = np.concatenate([np.fromiter(s, dtype=np.uint64) if s else np.empty(0, np.uint64) for s in tr_shingle_sets])
    rowids = np.concatenate([np.full(len(s), i, dtype=np.int64) for i, s in enumerate(tr_shingle_sets)])
    order = np.argsort(hashes, kind="mergesort")
    hashes, rowids = hashes[order], rowids[order]

    # posting-list lengths (df) per unique shingle
    uniq, start_idx, counts = np.unique(hashes, return_index=True, return_counts=True)
    lo = np.searchsorted(hashes, uniq)
    df_of = dict(zip(uniq.tolist(), counts.tolist()))

    max_j = pd.Series(0.0, index=test_df.index)
    n_no_shingles = 0
    for idx, text in zip(test_df.index, test_df["text"]):
        s = shingles(text)
        if not s:
            n_no_shingles += 1
            continue
        inter: Counter[int] = Counter()
        for h in s:
            dfh = df_of.get(h, 0)
            if dfh == 0 or dfh > MAX_DF:
                continue
            a = np.searchsorted(hashes, h)
            for rid in rowids[a : a + dfh]:
                inter[int(rid)] += 1
        best = 0.0
        st = len(s)
        for rid, c in inter.items():
            union = st + tr_sizes[rid] - c
            if union > 0:
                best = max(best, c / union)
        max_j[idx] = best
    stats = {
        "test_rows_screened": int(len(test_df)),
        "test_rows_no_shingles(<8 tokens)": n_no_shingles,
        f"dropped_J>={J_DROP}": int((max_j >= J_DROP).sum()),
        f"flagged_J>={J_REPORT}": int((max_j >= J_REPORT).sum()),
        "train_shingle_postings": int(len(hashes)),
        "train_unique_shingles": int(len(uniq)),
        "boilerplate_shingles_excluded": int((counts > MAX_DF).sum()),
    }
    return max_j, stats


def employer_grouped_val(osha_sel: pd.DataFrame, target_n: int, seed: int) -> tuple[pd.Index, pd.Index]:
    """Split selected OSHA rows into (train_idx, val_idx) by normalized-employer
    groups; val groups accumulated until >= target_n rows. Group-disjoint."""
    groups = {}
    for emp, sub in osha_sel.groupby(osha_sel["employer_norm"]):
        groups[emp] = sub.index.to_numpy()
    keys = list(groups)
    random.Random(seed).shuffle(keys)
    val_idx, n = [], 0
    for k in keys:
        if n >= target_n:
            break
        val_idx.extend(groups[k].tolist())
        n += len(groups[k])
    val_set = set(val_idx)
    train_idx = osha_sel.index.difference(pd.Index(sorted(val_set)))
    return train_idx, pd.Index(val_idx)


def osha_row(r: pd.Series, source: str) -> dict:
    return {
        "id": r["uid"],
        "text": r["text"],
        "masked_text": mask_text(r["text"]),
        "sif_label": int(r["sif"]),
        "rules": [rule for rule in RULES if rule in r["rules"]],
        "primary_rule": r["primary_rule"] if pd.notna(r["primary_rule"]) else None,
        "well_control": bool(r["well_control"]),
        "site": None, "activity": None, "barrier": None,
        "source": source,
        "employer": r["Employer"] if pd.notna(r["Employer"]) else None,
        "event_date": r["EventDate"].strftime("%Y-%m-%d"),
        "naics": r["Primary NAICS"] if pd.notna(r["Primary NAICS"]) else None,
        "oiics_event": str(r["Event"]).strip() if pd.notna(r["Event"]) else None,
    }


def asrs_row(rec: dict, masked: str) -> dict:
    acn = rec.get("acn_num_ACN")
    date = str(rec.get("Time_Date") or "").strip() or None  # format YYYYMM
    if date and re.fullmatch(r"\d{6}", date):
        date = f"{date[:4]}-{date[4:6]}-01"
    else:
        date = None
    return {
        "id": f"asrs-{acn}",
        "text": rec["_text"],
        "masked_text": masked,
        "sif_label": 0,
        "rules": [],
        "primary_rule": None,
        "well_control": False,
        "site": None, "activity": None, "barrier": None,
        "source": "asrs_negative",
        "employer": None,
        "event_date": date,
        "naics": None,
        "oiics_event": None,
    }


def load_asrs_negatives(path: str, n_needed: int, seed: int) -> tuple[list[dict], dict]:
    kept, seen = [], set()
    stats = Counter()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            stats["rows_read"] += 1
            anomaly = str(rec.get("Events_Anomaly") or "").strip()
            parts = [p.strip() for p in anomaly.split(";") if p.strip()]
            hits = [p for p in ASRS_DROP_PREFIXES if any(e.startswith(p) for e in parts)]
            if hits:
                stats[f"dropped:{hits[0]}"] += 1
                continue
            parts = [norm_ws(str(rec.get(f) or "")) for f in ("Report 1_Narrative", "Report 2_Narrative")]
            text = norm_ws(" ".join(p for p in parts if p))
            if len(text.split()) < 20:  # stub narratives carry no register signal
                stats["dropped:short_narrative"] += 1
                continue
            if text in seen:
                stats["dropped:exact_dup"] += 1
                continue
            seen.add(text)
            rec["_text"] = text
            kept.append(rec)
    stats["usable_after_screen"] = len(kept)
    rng = random.Random(seed)
    sample = rng.sample(kept, min(n_needed, len(kept)))
    rows = [asrs_row(r, mask_text(r["_text"])) for r in sample]
    for r in sample:
        del r["_text"]
    stats["emitted"] = len(rows)
    return rows, dict(stats)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def prevalence(rows: list[dict]) -> float:
    return sum(r["sif_label"] for r in rows) / max(len(rows), 1)


def rule_dist(rows: list[dict]) -> dict:
    n = max(len(rows), 1)
    return {rule: round(sum(rule in r["rules"] for r in rows) / n * 100, 2) for rule in RULES}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/January2015toNovember2025.csv")
    ap.add_argument("--asrs", default="artifacts/asrs/asrs-aviation-reports-train.jsonl")
    ap.add_argument("--outdir", default="artifacts/corpus")
    ap.add_argument("--splits-json", default="artifacts/corpus/splits.json")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    print("== load + label OSHA ==", flush=True)
    labeled = load_osha(args.csv)
    print(f"  rows loaded (non-empty narrative): {len(labeled)}")

    print("== exact dedup pre-split ==", flush=True)
    dedup, dedup_stats = exact_dedup(labeled)
    print(f"  {dedup_stats}; kept {len(dedup)}")

    train_era = dedup[dedup["EventDate"] <= TRAIN_END].copy()
    test_era = dedup[(dedup["EventDate"] >= TEST_START) & (dedup["EventDate"] <= TEST_END)].copy()
    print(f"  train-era {len(train_era)}  test-era {len(test_era)}")

    print("== cross-boundary 8-gram Jaccard screen ==", flush=True)
    max_j, screen_stats = boundary_screen(train_era, test_era)
    test_kept = test_era[max_j < J_DROP].copy()
    print(f"  {screen_stats}")

    print("== pools ==", flush=True)
    pos_pool = train_era[train_era["sif"]].copy()
    le_mask = train_era["oiics_prefix"].eq("42") | train_era["oiics_prefix"].str.startswith("7")
    neg_pool = train_era[le_mask].copy()
    amp = neg_pool["Amputation"].fillna("0").astype(float) > 0
    neg_pool = neg_pool[~amp].copy()
    print(f"  osha positives (v1): {len(pos_pool)}")
    print(f"  low-energy pool (v1 42x/7xx): {int(le_mask.sum())}, amputated excluded: {int(amp.sum())}, usable: {len(neg_pool)}")

    # size from binding pool: use ALL usable low-energy negatives
    n_neg = len(neg_pool)
    n_pos = int(round(n_neg * MIX["osha_positive"] / MIX["osha_low_energy_negative"]))
    n_asrs = int(round(n_neg * MIX["asrs_negative"] / MIX["osha_low_energy_negative"]))
    n_pos = min(n_pos, len(pos_pool))
    print(f"  mix sizing: neg={n_neg} pos={n_pos} asrs={n_asrs}")

    pos_sel = pos_pool.sample(n=n_pos, random_state=args.seed)
    osha_sel = pd.concat([pos_sel, neg_pool])
    osha_sel["employer_norm"] = osha_sel["Employer"].map(norm_employer)

    n_real_train = n_pos + n_neg + n_asrs
    val_target = int(round(VAL_FRAC_OF_TRAIN * n_real_train))
    tr_idx, val_idx = employer_grouped_val(osha_sel, val_target, args.seed)
    print(f"  val holdout: target={val_target} got={len(val_idx)} ({len(val_idx)/n_real_train*100:.1f}% of real train)")

    print("== ASRS negatives ==", flush=True)
    asrs_rows, asrs_stats = load_asrs_negatives(args.asrs, n_asrs, args.seed)
    print(f"  {asrs_stats}")

    print("== emit JSONL ==", flush=True)
    osha_tr = osha_sel.loc[tr_idx]
    osha_va = osha_sel.loc[val_idx]
    train_rows = [osha_row(r, "osha_positive" if r["sif"] else "osha_low_energy_negative")
                  for _, r in osha_tr.iterrows()]
    train_rows += asrs_rows
    rng.shuffle(train_rows)
    val_rows = [osha_row(r, "osha_positive" if r["sif"] else "osha_low_energy_negative")
                for _, r in osha_va.iterrows()]
    rng.shuffle(val_rows)
    test_rows = [osha_row(r, "osha") for _, r in test_kept.iterrows()]

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    write_jsonl(outdir / "train.jsonl", train_rows)
    write_jsonl(outdir / "val.jsonl", val_rows)
    write_jsonl(outdir / "test.jsonl", test_rows)
    print(f"  train={len(train_rows)} val={len(val_rows)} test={len(test_rows)}")

    # ---- leakage audit -------------------------------------------------------
    tr_emp = set(osha_tr["employer_norm"]) - {""}
    va_emp = set(osha_va["employer_norm"]) - {""}
    te_emp_norm = test_kept["Employer"].map(norm_employer)
    test_overlap = float((te_emp_norm.isin(tr_emp)).mean())
    trainval_overlap = len(tr_emp & va_emp)

    # projected final mix with frozen synthetic quota (9000 = 6000 pos / 3000 neg)
    n_syn_pos, n_syn_neg = 6000, 3000
    proj_train = len(train_rows) + n_syn_pos + n_syn_neg
    proj_prev = (sum(r["sif_label"] for r in train_rows) + n_syn_pos) / proj_train

    splits = {
        "seed": args.seed,
        "policy": "temporal_hard; employer-grouped val within train only; 8-gram Jaccard boundary screen",
        "dedup_pre_split": dedup_stats,
        "counts": {
            "osha_labeled_after_dedup": len(dedup),
            "train_era_rows": len(train_era), "test_era_rows": len(test_era),
            "test_after_boundary_screen": len(test_kept),
            "train": len(train_rows), "val": len(val_rows), "test": len(test_rows),
            "train_by_source": dict(Counter(r["source"] for r in train_rows)),
            "val_by_source": dict(Counter(r["source"] for r in val_rows)),
        },
        "boundary_screen": screen_stats,
        "employer_leakage": {
            "train_val_shared_employers": trainval_overlap,
            "test_rows_with_employer_in_train_pct": round(test_overlap * 100, 2),
            "note": "cross-era employer overlap accepted per D10; normalized=lower+strip punctuation (lower bound)",
        },
        "asrs": asrs_stats,
        "asrs_drop_prefixes": list(ASRS_DROP_PREFIXES),
        "prevalence": {
            "train_real_only": round(prevalence(train_rows), 4),
            "val": round(prevalence(val_rows), 4),
            "test_natural": round(prevalence(test_rows), 4),
            "projected_final_train_with_synthetic_9000": round(proj_prev, 4),
            "spec_target_train_prevalence": 0.40,
            "spec_note": "frozen mix ratios 0.55/0.15/0.15/0.10/0.05 imply 0.65 prevalence; "
                         "spec target 0.40 is NOT consistent with the frozen ratios — flagged",
        },
        "rule_distribution_pct": {
            "train": rule_dist(train_rows), "val": rule_dist(val_rows), "test": rule_dist(test_rows),
        },
        "synthetic_slots": {"planned_pos": n_syn_pos, "planned_neg": n_syn_neg,
                            "synthetic_share_of_final": round((n_syn_pos + n_syn_neg) / proj_train, 4)},
    }
    with open(args.splits_json, "w", encoding="utf-8") as fh:
        json.dump(splits, fh, indent=2)
    print(f"  wrote {args.splits_json}")

    # ---- self-check: re-read and validate emitted JSONL ----------------------
    print("== SELF-CHECK ==", flush=True)
    required = {"id", "text", "masked_text", "sif_label", "rules", "primary_rule",
                "well_control", "site", "activity", "barrier", "source",
                "employer", "event_date", "naics", "oiics_event"}
    ok = True
    for name in ("train", "val", "test"):
        rows = [json.loads(l) for l in open(outdir / f"{name}.jsonl", encoding="utf-8")]
        for r in rows:
            assert set(r) == required, f"{name}: bad schema keys {set(r) ^ required}"
            assert isinstance(r["sif_label"], int) and r["sif_label"] in (0, 1)
            assert isinstance(r["rules"], list) and set(r["rules"]) <= set(RULES)
            assert r["text"] and r["masked_text"]
            assert r["site"] is None and r["activity"] is None and r["barrier"] is None
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids)), f"{name}: duplicate ids"
        print(f"  {name}: n={len(rows)} prevalence={prevalence(rows)*100:.2f}% rules={rule_dist(rows)}")
    # no row may contain an unmasked outcome stem in masked_text
    from masking import mask_count
    leaks = 0
    for name in ("train", "val", "test"):
        for l in open(outdir / f"{name}.jsonl", encoding="utf-8"):
            leaks += mask_count(json.loads(l)["masked_text"]) > 0
    print(f"  masked_text rows still matching outcome stems: {leaks} (expect 0)")
    ok &= leaks == 0
    # train/val employer disjointness + id disjointness across splits
    all_ids = []
    for name in ("train", "val", "test"):
        all_ids += [json.loads(l)["id"] for l in open(outdir / f"{name}.jsonl", encoding="utf-8")]
    assert len(all_ids) == len(set(all_ids)), "id collision across splits"
    print(f"  train/val shared normalized employers: {trainval_overlap} (expect 0)")
    ok &= trainval_overlap == 0
    print(f"  test rows with employer present in train: {test_overlap*100:.2f}% (accepted residual, ~42% expected)")
    print(f"  projected final train prevalence (with 9000 synthetic): {proj_prev*100:.2f}%")
    print("SELF-CHECK:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
