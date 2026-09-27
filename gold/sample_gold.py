"""Gold set sampler — anti-circularity artifact for blind human labeling.

Composition (FROZEN spec/label_spec.yaml `gold:` + DECISION_LOG D7/D8):
  300 OSHA 2024-25  from artifacts/corpus/test.jsonl (temporal test pool also
                    used for operating-point tuning; not fully held out;
                    up to 150 oil-gas NAICS 211/213 rows — 364 available)
  100 ASRS          from artifacts/asrs/asrs-aviation-reports-train.jsonl,
                    SAME prescreen as data_pipeline/build_corpus.py (drop
                    high-energy Events_Anomaly rows, >=20 words, exact-dedup),
                    MINUS any ACN already used in corpus train.jsonl (leakage
                    guard: gold must never contain training rows)
  100 synthetic     RESERVED slots G0401-G0500; filled by re-running with
                    --synthetic-file once synthetic QA passes (D8: synthetic
                    stratum reported separately, never pooled)

Design: 500 items (400 emitted until synthetic fills), 150 double-labeled
(stratified 90 OSHA / 30 ASRS / 30 synthetic), 20-item calibration pilot
(same 20 for all labelers, drawn from double-flagged OSHA/ASRS so the pilot
set is stable when the synthetic stratum fills later). Assignments balanced
across 4 labelers; per-labeler queues shuffled with per-labeler seeds in
gold/labeler_app.py. Derived labels (sif_label, rules, naics, ...) are used
ONLY for stratification/enrichment statistics and are NEVER written to
gold_items.jsonl — labelers see masked_text + event_title, nothing else.

SIF-positive prevalence target >= 0.40 (proxy B_middle labels) for CI width;
the natural test-pool prevalence is ~0.64, so enrichment is achieved through
the oil-gas oversample alone (ratio recorded in the manifest).

Output:
  artifacts/gold/gold_items.jsonl     one row per emitted item
  artifacts/gold/sample_manifest.json full audit trail

Pure stdlib (masking.py imported for mask_text). Deterministic at seed 42.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data_pipeline"))

from gold_common import LABELER_IDS, RULES, SEED  # noqa: E402
from masking import mask_text  # noqa: E402

# ASRS high-energy prescreen — MUST stay identical to
# data_pipeline/build_corpus.py:ASRS_DROP_PREFIXES (parity asserted in
# self-check when pandas is available to import build_corpus).
ASRS_DROP_PREFIXES = (
    "Conflict",
    "Ground Event / Encounter",
    "Ground Excursion",
    "Ground Incursion",
    "Inflight Event / Encounter",
    "Flight Deck / Cabin / Aircraft Event Smoke / Fire / Fumes",
    "Flight Deck / Cabin / Aircraft Event Illness / Injury",
)

OIL_GAS_NAICS = ("211", "213")
N_OSHA, N_ASRS, N_SYNTH = 300, 100, 100
N_OIL_GAS_MAX = 150
PREVALENCE_TARGET = 0.40
DOUBLE_PER_STRATUM = {"osha_2024_25": 90, "asrs": 30, "synthetic": 30}
N_PILOT = 20
PILOT_PER_STRATUM = {"osha_2024_25": 15, "asrs": 5}  # no synthetic: pilot must
# be stable regardless of when the synthetic stratum fills.


def rng_for(*parts: object) -> random.Random:
    return random.Random(":".join(str(p) for p in parts))


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def osha_event_titles(csv_path: str) -> dict:
    """uid -> EventTitle, replicating build_corpus.load_osha's uid assignment
    (empty-narrative drop, stable sort by (ID, EventDate, UPA), occurrence
    suffix for the 5 reused report IDs)."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            text = norm_ws(r.get("Final Narrative") or "")
            if not text:
                continue
            rows.append(
                (
                    r["ID"],
                    datetime.strptime(r["EventDate"], "%m/%d/%Y"),
                    r.get("UPA") or "",
                    (r.get("EventTitle") or "").strip(),
                )
            )
    rows.sort(key=lambda t: (t[0], t[1], t[2]))  # stable like mergesort
    counts = Counter(r[0] for r in rows)
    occ: Counter[str] = Counter()
    titles = {}
    for rid, _date, _upa, title in rows:
        o = occ[rid]
        occ[rid] += 1
        uid = f"osha-{rid}" if counts[rid] == 1 else f"osha-{rid}-{chr(97 + o)}"
        titles[uid] = title
    return titles


def sample_osha(test_rows: list[dict], titles: dict, seed: int) -> tuple[list[dict], dict]:
    # Disclosure: this gold stratum is sampled from artifacts/corpus/test.jsonl,
    # the same temporal test split used to tune the operating point; it is not
    # a fully held-out evaluation. Do not re-sample without human re-adjudication.
    oil_gas = [r for r in test_rows if (r.get("naics") or "").startswith(OIL_GAS_NAICS)]
    rest = [r for r in test_rows if not (r.get("naics") or "").startswith(OIL_GAS_NAICS)]
    n_og = min(N_OIL_GAS_MAX, len(oil_gas))
    og_sel = rng_for(seed, "osha-oil-gas").sample(oil_gas, n_og)
    rest_sel = rng_for(seed, "osha-rest").sample(rest, N_OSHA - n_og)

    achieved = sum(r["sif_label"] for r in og_sel + rest_sel) / N_OSHA
    n_swapped = 0
    if achieved < PREVALENCE_TARGET:
        # Deterministic enrichment: swap sampled non-SIF rest rows for
        # unsampled SIF rest rows until the target is met.
        pool_ids = {r["id"] for r in rest_sel}
        spare_pos = [r for r in rest if r["sif_label"] and r["id"] not in pool_ids]
        swap_rng = rng_for(seed, "osha-enrich")
        swap_rng.shuffle(spare_pos)
        negs = [i for i, r in enumerate(rest_sel) if not r["sif_label"]]
        for i in negs:
            if achieved >= PREVALENCE_TARGET or not spare_pos:
                break
            rest_sel[i] = spare_pos.pop()
            n_swapped += 1
            achieved = sum(r["sif_label"] for r in og_sel + rest_sel) / N_OSHA

    items = []
    for i, r in enumerate(og_sel + rest_sel):
        items.append(
            {
                "gold_id": f"G{i + 1:04d}",
                "source_stratum": "osha_2024_25",
                "masked_text": r["masked_text"],
                # Titles are masked too: a few OIICS titles start with
                # "Injured by object..." (injur is a frozen outcome stem);
                # labelers must see zero unmasked outcome stems anywhere.
                "event_title": mask_text(titles.get(r["id"]) or "") or None,
                "_src_id": r["id"],
                "_sif_proxy": r["sif_label"],  # manifest stats only; stripped below
            }
        )
    stats = {
        "test_pool_rows": len(test_rows),
        "test_pool_natural_prevalence": round(
            sum(r["sif_label"] for r in test_rows) / len(test_rows), 4
        ),
        "oil_gas_available": len(oil_gas),
        "oil_gas_sampled": n_og,
        "oil_gas_sif_in_available": sum(r["sif_label"] for r in oil_gas),
        "oil_gas_sif_in_sample": sum(r["sif_label"] for r in og_sel),
        "achieved_prevalence_proxy": round(achieved, 4),
        "prevalence_target": PREVALENCE_TARGET,
        "enrichment_swaps": n_swapped,
        "event_title_missing": sum(1 for it in items if not it["event_title"]),
    }
    stats["enrichment_ratio"] = round(
        stats["achieved_prevalence_proxy"] / stats["test_pool_natural_prevalence"], 4
    )
    return items, stats


def sample_asrs(asrs_path: str, train_ids: set[str], seed: int) -> tuple[list[dict], dict]:
    """Same prescreen as build_corpus.load_asrs_negatives, plus the leakage
    guard: ACNs already emitted into corpus train.jsonl are excluded."""
    kept, seen = [], set()
    stats = Counter()
    with open(asrs_path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            stats["rows_read"] += 1
            anomaly = str(rec.get("Events_Anomaly") or "").strip()
            parts = [p.strip() for p in anomaly.split(";") if p.strip()]
            if any(any(e.startswith(p) for e in parts) for p in ASRS_DROP_PREFIXES):
                stats["dropped:high_energy_anomaly"] += 1
                continue
            text = norm_ws(
                " ".join(
                    p
                    for p in (
                        norm_ws(str(rec.get("Report 1_Narrative") or "")),
                        norm_ws(str(rec.get("Report 2_Narrative") or "")),
                    )
                    if p
                )
            )
            if len(text.split()) < 20:
                stats["dropped:short_narrative"] += 1
                continue
            if text in seen:
                stats["dropped:exact_dup"] += 1
                continue
            acn = str(rec.get("acn_num_ACN") or "").strip()
            if f"asrs-{acn}" in train_ids:
                stats["dropped:in_corpus_train"] += 1
                continue
            seen.add(text)
            synopsis = norm_ws(str(rec.get("Report 1.2_Synopsis") or ""))
            kept.append((acn, text, synopsis))
    stats["usable_pool"] = len(kept)
    sample = rng_for(seed, "asrs").sample(kept, N_ASRS)
    items = [
        {
            "gold_id": f"G{N_OSHA + 1 + i:04d}",
            "source_stratum": "asrs",
            "masked_text": mask_text(text),
            "event_title": mask_text(synopsis) if synopsis else None,
            "_src_id": f"asrs-{acn}",
            "_sif_proxy": 0,
        }
        for i, (acn, text, synopsis) in enumerate(sample)
    ]
    stats["sampled"] = len(items)
    stats["synopsis_missing"] = sum(1 for it in items if not it["event_title"])
    return items, stats


def sample_synthetic(path: str, seed: int) -> tuple[list[dict], dict]:
    # Disclosure: this sampler does not exclude synthetic rows used in training;
    # this stratum may overlap training and is not generalization evidence.
    rows = load_jsonl(path)
    sample = rng_for(seed, "synthetic").sample(rows, N_SYNTH)
    items = []
    for i, r in enumerate(sample):
        text = r.get("masked_text") or mask_text(norm_ws(r.get("text") or ""))
        items.append(
            {
                "gold_id": f"G{N_OSHA + N_ASRS + 1 + i:04d}",
                "source_stratum": "synthetic",
                "masked_text": text,
                "event_title": mask_text(r["event_title"]) if r.get("event_title") else None,
                "_src_id": r.get("id"),
                "_sif_proxy": r.get("sif_label"),
            }
        )
    return items, {"source_rows": len(rows), "sampled": len(items)}


def assign(items: list[dict], seed: int, synthetic_filled: bool) -> dict:
    """Double flags (stratified, stable id-subsets), pilot pick, and balanced
    primary/secondary labeler assignments. Mutates items."""
    by_stratum: dict[str, list[dict]] = {}
    for it in items:
        by_stratum.setdefault(it["source_stratum"], []).append(it)

    # Double flags: seeded pick per stratum; for a missing synthetic stratum
    # the 30 flags are reserved by id (G0401.. shuffled, first 30).
    for stratum, k in DOUBLE_PER_STRATUM.items():
        ids = [it["gold_id"] for it in by_stratum.get(stratum, [])]
        if not ids and stratum == "synthetic":
            ids = [f"G{N_OSHA + N_ASRS + 1 + i:04d}" for i in range(N_SYNTH)]
        flagged = set(ids)
        r = rng_for(seed, "double", stratum)
        shuffled = sorted(flagged)
        r.shuffle(shuffled)
        keep = set(shuffled[:k])
        for it in by_stratum.get(stratum, []):
            it["is_double"] = it["gold_id"] in keep
        if stratum == "synthetic":
            assign._synthetic_doubles = keep  # noqa: SLF001

    # Pilot: from double-flagged OSHA + ASRS (stable across synthetic fill).
    pilot_ids: list[str] = []
    for stratum, k in PILOT_PER_STRATUM.items():
        pool = sorted(it["gold_id"] for it in by_stratum[stratum] if it["is_double"])
        pilot_ids.extend(rng_for(seed, "pilot", stratum).sample(pool, k))
    pilot_set = set(pilot_ids)
    for it in items:
        it["is_pilot"] = it["gold_id"] in pilot_set

    # Primary: seeded shuffle of all emitted ids, round-robin.
    order = [it["gold_id"] for it in items]
    rng_for(seed, "assign-primary").shuffle(order)
    primary = {gid: LABELER_IDS[i % len(LABELER_IDS)] for i, gid in enumerate(order)}

    # Secondary for double-flagged: rotating pointer, skipping the primary.
    doubles = [it["gold_id"] for it in items if it["is_double"]]
    sec_rng = rng_for(seed, "assign-secondary")
    sec_rng.shuffle(doubles)
    secondary = {}
    sec_counts: Counter[str] = Counter()
    for gid in doubles:  # least-loaded eligible labeler, random tiebreak
        cand = sorted(
            (l for l in LABELER_IDS if l != primary[gid]),
            key=lambda l: (sec_counts[l], sec_rng.random()),
        )
        secondary[gid] = cand[0]
        sec_counts[cand[0]] += 1

    for it in items:
        it["assignment"] = {
            "labeler": primary[it["gold_id"]],
            "is_double": it["is_double"],
            "second_labeler": secondary.get(it["gold_id"]),
        }
        del it["is_double"]

    balance = {
        "primary": dict(Counter(primary.values())),
        "secondary": dict(Counter(secondary.values())),
    }
    assign._pilot_ids = pilot_ids  # noqa: SLF001
    assign._synthetic_filled = synthetic_filled  # noqa: SLF001
    return balance


def self_check(items: list[dict], manifest: dict, synthetic_filled: bool) -> list[str]:
    errs = []
    ids = [it["gold_id"] for it in items]
    if len(ids) != len(set(ids)):
        errs.append("duplicate gold_ids")
    expect_n = N_OSHA + N_ASRS + (N_SYNTH if synthetic_filled else 0)
    if len(items) != expect_n:
        errs.append(f"composition: {len(items)} != {expect_n}")
    by_stratum = Counter(it["source_stratum"] for it in items)
    if by_stratum.get("osha_2024_25") != N_OSHA or by_stratum.get("asrs") != N_ASRS:
        errs.append(f"stratum counts off: {by_stratum}")
    n_double = sum(it["assignment"]["is_double"] for it in items)
    n_double_design = n_double + (0 if synthetic_filled else DOUBLE_PER_STRATUM["synthetic"])
    if n_double_design != sum(DOUBLE_PER_STRATUM.values()):
        errs.append(f"double design off: {n_double_design}")
    per_stratum_double = Counter(
        it["source_stratum"] for it in items if it["assignment"]["is_double"]
    )
    for s, k in DOUBLE_PER_STRATUM.items():
        if s == "synthetic" and not synthetic_filled:
            continue
        if per_stratum_double.get(s, 0) != k:
            errs.append(f"double count {s}: {per_stratum_double.get(s, 0)} != {k}")
    prim = Counter(it["assignment"]["labeler"] for it in items)
    sec = Counter(
        it["assignment"]["second_labeler"] for it in items if it["assignment"]["second_labeler"]
    )
    for label, counts in (("primary", prim), ("secondary", sec)):
        if counts and max(counts.values()) - min(counts.values()) > 2:
            errs.append(f"{label} imbalance >2: {counts}")
    for it in items:
        a = it["assignment"]
        if a["second_labeler"] and a["second_labeler"] == a["labeler"]:
            errs.append(f"{it['gold_id']}: primary == secondary")
    pilots = [it for it in items if it["is_pilot"]]
    if len(pilots) != N_PILOT or not all(p["assignment"]["is_double"] for p in pilots):
        errs.append(f"pilot: n={len(pilots)}, all_double="
                    f"{all(p['assignment']['is_double'] for p in pilots)}")
    if any("_sif_proxy" in it or "_src_id" in it for it in items):
        errs.append("provenance/derived-label fields leaked into emitted rows")
    if any(not it["masked_text"] for it in items):
        errs.append("empty masked_text")
    try:
        from masking import mask_count  # noqa: PLC0415

        stem_leaks = [
            it["gold_id"] for it in items
            if mask_count(it["masked_text"]) or mask_count(it["event_title"] or "")
        ]
        if stem_leaks:
            errs.append(f"unmasked outcome stems in {len(stem_leaks)} rows: {stem_leaks[:5]}")
    except ImportError:
        errs.append("masking.py unavailable — stem-leak check skipped")
    if manifest["osha"]["achieved_prevalence_proxy"] < PREVALENCE_TARGET:
        errs.append("OSHA proxy prevalence below target")
    # Rule-set parity with oiics_maps (needs pandas; skip silently if absent).
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data_pipeline"))
        from oiics_maps import RULES as MAP_RULES  # noqa: PLC0415

        if tuple(MAP_RULES) != RULES:
            errs.append(f"RULES drifted from oiics_maps: {MAP_RULES}")
        import build_corpus  # noqa: PLC0415

        if tuple(build_corpus.ASRS_DROP_PREFIXES) != ASRS_DROP_PREFIXES:
            errs.append("ASRS_DROP_PREFIXES drifted from build_corpus")
    except ImportError:
        pass
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--test-file", default="artifacts/corpus/test.jsonl")
    ap.add_argument("--asrs-file", default="artifacts/asrs/asrs-aviation-reports-train.jsonl")
    ap.add_argument("--train-file", default="artifacts/corpus/train.jsonl")
    ap.add_argument("--csv", default="data/January2015toNovember2025.csv")
    ap.add_argument("--synthetic-file", default=None,
                    help="JSONL of QA-passed synthetic items; fills reserved slots G0401-G0500")
    ap.add_argument("--out", default="artifacts/gold/gold_items.jsonl")
    ap.add_argument("--manifest", default="artifacts/gold/sample_manifest.json")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    print("== load inputs ==", flush=True)
    test_rows = load_jsonl(args.test_file)
    titles = osha_event_titles(args.csv)
    train_ids = {r["id"] for r in load_jsonl(args.train_file)}
    print(f"  test pool {len(test_rows)} rows; train ids {len(train_ids)}")

    osha_items, osha_stats = sample_osha(test_rows, titles, args.seed)
    print(f"== OSHA == 300 sampled ({osha_stats['oil_gas_sampled']} oil-gas of "
          f"{osha_stats['oil_gas_available']}); proxy prevalence "
          f"{osha_stats['achieved_prevalence_proxy']:.4f} "
          f"(natural {osha_stats['test_pool_natural_prevalence']:.4f}, "
          f"ratio {osha_stats['enrichment_ratio']})", flush=True)

    asrs_items, asrs_stats = sample_asrs(args.asrs_file, train_ids, args.seed)
    print(f"== ASRS == pool {asrs_stats['usable_pool']} after prescreen + "
          f"train-overlap guard ({asrs_stats['dropped:in_corpus_train']} excluded); "
          f"sampled {asrs_stats['sampled']}", flush=True)

    items = osha_items + asrs_items
    synthetic_filled = False
    if args.synthetic_file:
        synth_items, synth_stats = sample_synthetic(args.synthetic_file, args.seed)
        items += synth_items
        synthetic_filled = True
        print(f"== SYNTHETIC == filled 100 reserved slots from {args.synthetic_file}", flush=True)
    else:
        synth_stats = {"status": "reserved",
                       "reserved_ids": [f"G{N_OSHA + N_ASRS + 1 + i:04d}" for i in range(N_SYNTH)]}
        print("== SYNTHETIC == 100 slots RESERVED (G0401-G0500); pass --synthetic-file after QA",
              flush=True)

    balance = assign(items, args.seed, synthetic_filled)

    manifest = {
        "seed": args.seed,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spec": "spec/label_spec.yaml gold: section (FROZEN v1.0.0); DECISION_LOG D7/D8",
        "inputs": {
            p: {"path": getattr(args, p.replace("-", "_"), None), "sha256": sha256_of(getattr(args, p.replace("-", "_")))}
            for p in ("test-file", "asrs-file", "train-file", "csv")
        } | ({"synthetic_file": {"path": args.synthetic_file,
                                 "sha256": sha256_of(args.synthetic_file)}}
             if args.synthetic_file else {}),
        "osha": osha_stats,
        "asrs": dict(asrs_stats),
        "synthetic": synth_stats,
        "double_design": DOUBLE_PER_STRATUM,
        "synthetic_double_ids_reserved": sorted(getattr(assign, "_synthetic_doubles", []))
        if not synthetic_filled else None,
        "pilot_ids": assign._pilot_ids,  # noqa: SLF001
        "labeler_balance": balance,
        "counts": dict(Counter(it["source_stratum"] for it in items)),
        "n_emitted": len(items),
        "n_judgments_emitted": len(items)
        + sum(it["assignment"]["is_double"] for it in items)
        + 2 * N_PILOT,  # pilot items get 4 labels, not 2
    }

    # Strip internal fields before writing.
    emitted = []
    for it in items:
        row = {
            "gold_id": it["gold_id"],
            "source_stratum": it["source_stratum"],
            "masked_text": it["masked_text"],
            "event_title": it["event_title"],
            "is_pilot": it["is_pilot"],
            "assignment": it["assignment"],
        }
        emitted.append(row)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for row in emitted:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(args.manifest, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"  wrote {out_path} ({len(emitted)} rows) + {args.manifest}", flush=True)

    print("== SELF-CHECK ==", flush=True)
    errs = self_check(emitted, manifest, synthetic_filled)
    if errs:
        for e in errs:
            print(f"  FAIL: {e}")
        return 1
    n_doubles = sum(r['assignment']['is_double'] for r in emitted)
    reserved_note = "" if synthetic_filled else " (+30 reserved synthetic = 150 design)"
    print(f"  composition {manifest['counts']}; doubles flagged {n_doubles} emitted{reserved_note}")
    print(f"  primary balance {balance['primary']}; secondary {balance['secondary']}")
    print(f"  pilot {N_PILOT} items (all double-flagged)")
    print("SELF-CHECK: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
