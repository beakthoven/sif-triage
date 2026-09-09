"""Gold labeler-quality + error-analysis self-check (READ-ONLY on labels).

Recomputes every number quoted in runs/run2/day2/labeler_quality.md and
runs/run2/day2/error_analysis.md from the raw artifacts and asserts them
against the published gold_metrics_{all4,noC}.json / agreement_{all4,noC}.json.
Never writes anywhere near artifacts/gold/labels*/ — output is stdout plus
runs/run2/day2/_gold_analysis_dump.json (derived analysis, no human labels
modified; human labels are only ever read).

Run:  python3 runs/run2/day2/selfcheck_gold_analysis.py
Exit: 0 = all checks pass, 1 = mismatch (details on stdout).
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "gold"))
from export_labels import fleiss_kappa, kappa_matrix  # noqa: E402
from gold_common import LABELS, RULES  # noqa: E402

GOLD = REPO / "artifacts" / "gold"
THR = 0.7464005622345774  # D27 frozen operating point (p_raw), from masked-v2 metrics.json
Z = 1.96
RULE_MIN_SUPPORT = 50

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def wilson(k: int, n: int) -> tuple:
    if n == 0:
        return None, None, None
    p = k / n
    d = 1.0 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


# ------------------------------------------------------------- load inputs --
gold = load_jsonl(GOLD / "gold_items.jsonl")
gold_by_id = {r["gold_id"]: r for r in gold}
scores = {r["gold_id"]: r for r in load_jsonl(GOLD / "model_scores.jsonl")}
rule_thresholds = json.loads(
    (REPO / "artifacts/models/masked-v2/thresholds.json").read_text())["rule_thresholds"]

# Latest-wins dedup (mirrors export_labels.load_labels) + raw rows for timing.
raw_rows: dict[str, list[dict]] = {}
labels: dict[str, dict[str, dict]] = {}  # gold_id -> labeler -> latest rec
for lab in ("labeler_a", "labeler_b", "labeler_c", "labeler_d"):
    rows = load_jsonl(GOLD / "labels" / f"{lab}.jsonl")
    raw_rows[lab] = rows
    for r in rows:
        labels.setdefault(r["gold_id"], {})[lab] = r

print("== 1. per-labeler profiles ==")
profiles: dict[str, dict] = {}
for lab, rows in raw_rows.items():
    latest: dict[str, dict] = {}
    for r in rows:  # file order = ts order; last row wins
        latest[r["gold_id"]] = r
    dist = Counter(r["label"] for r in latest.values())
    # reading time: deltas between consecutive UNIQUE items, first-appearance
    # order (duplicate re-saves share timestamps and are not reading events)
    seen: set[str] = set()
    uts: list[datetime] = []
    for r in rows:
        if r["gold_id"] not in seen:
            seen.add(r["gold_id"])
            uts.append(datetime.fromisoformat(r["ts"]))
    deltas = [(uts[i + 1] - uts[i]).total_seconds() for i in range(len(uts) - 1)]
    in_sess = [d for d in deltas if d <= 600]  # drop session breaks
    assigned = {g["gold_id"] for g in gold
                if g["is_pilot"] or g["assignment"]["labeler"] == lab
                or g["assignment"].get("second_labeler") == lab}
    extra = sorted(set(latest) - assigned)
    n = len(latest)
    prof = {
        "rows": len(rows), "unique_items": n,
        "dup_resave_rows": len(rows) - n,
        "sif": dist.get("sif", 0), "non_sif": dist.get("non_sif", 0),
        "unsure": dist.get("unsure", 0),
        "sif_rate": dist.get("sif", 0) / n, "non_sif_rate": dist.get("non_sif", 0) / n,
        "unsure_rate": dist.get("unsure", 0) / n,
        "median_read_s": statistics.median(deltas) if deltas else None,
        "median_read_in_session_s": statistics.median(in_sess) if in_sess else None,
        "p90_read_s": sorted(deltas)[int(0.9 * (len(deltas) - 1))] if deltas else None,
        "assigned_items": len(assigned), "unassigned_items_labeled": len(extra),
        "first_ts": rows[0]["ts"], "last_ts": rows[-1]["ts"],
    }
    profiles[lab] = prof
    print(f"  {lab}: n={n} S/N/U={prof['sif']}/{prof['non_sif']}/{prof['unsure']} "
          f"({prof['sif_rate']:.0%}/{prof['non_sif_rate']:.0%}/{prof['unsure_rate']:.0%}) "
          f"median_read={prof['median_read_s']:.0f}s (in-session {prof['median_read_in_session_s']:.0f}s) "
          f"dup_resaves={prof['dup_resave_rows']} unassigned={len(extra)}")

check("labeler_c median reading time == 2s (protocol-violation evidence)",
      profiles["labeler_c"]["median_read_s"] == 2.0,
      f"got {profiles['labeler_c']['median_read_s']}s")
check("labelers a/b median reading time >= 10s",
      profiles["labeler_a"]["median_read_s"] >= 10 and profiles["labeler_b"]["median_read_s"] >= 10,
      f"a={profiles['labeler_a']['median_read_s']}s b={profiles['labeler_b']['median_read_s']}s")
check("labeler_c has batch duplicate re-save rows (same-ts bursts)",
      profiles["labeler_c"]["dup_resave_rows"] > 50,
      f"{profiles['labeler_c']['dup_resave_rows']} dup rows")
check("labeler_c label mix inverted vs peers (non_sif-majority)",
      profiles["labeler_c"]["non_sif_rate"] > 0.6 and
      all(profiles[l]["sif_rate"] > 0.5 for l in ("labeler_a", "labeler_b", "labeler_d")),
      f"c non_sif={profiles['labeler_c']['non_sif_rate']:.0%}")

print("\n== 2. pairwise agreement (items both labeled, latest label, 3-way exact) ==")
LABS = ("labeler_a", "labeler_b", "labeler_c", "labeler_d")
pairwise: dict[str, dict] = {}
for i, x in enumerate(LABS):
    for y in LABS[i + 1:]:
        both = [(labels[g][x]["label"], labels[g][y]["label"])
                for g in labels if x in labels[g] and y in labels[g]]
        agree = sum(1 for a, b in both if a == b)
        # binary S-vs-N view on pairs where neither said unsure
        sn = [(a, b) for a, b in both if "unsure" not in (a, b)]
        sn_agree = sum(1 for a, b in sn if a == b)
        pairwise[f"{x}|{y}"] = {
            "n": len(both), "agree": agree,
            "pct": 100 * agree / len(both) if both else None,
            "n_sn": len(sn), "pct_sn": 100 * sn_agree / len(sn) if sn else None,
        }
        print(f"  {x} vs {y}: n={len(both):3d} agree={100*agree/len(both):5.1f}%  "
              f"(S/N only: n={len(sn):3d}, {100*sn_agree/len(sn):5.1f}%)")

c_pairs = [pairwise[k]["pct"] for k in pairwise if "labeler_c" in k]
o_pairs = [pairwise[k]["pct"] for k in pairwise if "labeler_c" not in k]
check("labeler_c is the weakest link in every pair it touches",
      max(c_pairs) < min(o_pairs),
      f"C pairs {['%.1f' % p for p in c_pairs]} vs non-C {['%.1f' % p for p in o_pairs]}")

print("\n== 3. pilot (20 items x 4 raters) + kappa recomputation vs agreement JSONs ==")
pilot_ids = [g["gold_id"] for g in gold if g["is_pilot"]]
pilot_all4 = [[labels[g][lab]["label"] for lab in LABS if lab in labels[g]] for g in pilot_ids]
k_all4 = fleiss_kappa(kappa_matrix(pilot_all4))
pilot_noC = [[labels[g][lab]["label"] for lab in LABS if lab in labels[g] and lab != "labeler_c"]
             for g in pilot_ids]
k_noC = fleiss_kappa(kappa_matrix(pilot_noC))
raw4 = 100 * sum(1 for v in pilot_all4 if len(set(v)) == 1) / len(pilot_all4)
raw3 = 100 * sum(1 for v in pilot_noC if len(set(v)) == 1) / len(pilot_noC)
print(f"  pilot all4: kappa={k_all4:.4f} raw={raw4:.1f}% | noC: kappa={k_noC:.4f} raw={raw3:.1f}%")
c_pilot = Counter(labels[g]["labeler_c"]["label"] for g in pilot_ids if "labeler_c" in labels[g])
print(f"  labeler_c pilot labels: {dict(c_pilot)}")
ag_all4 = json.loads((GOLD / "agreement_all4.json").read_text())
ag_noC = json.loads((GOLD / "agreement_noC.json").read_text())
check("pilot kappa all4 matches agreement_all4.json",
      abs(k_all4 - ag_all4["subsets"]["n_raters_4"]["fleiss_kappa"]) < 1e-4,
      f"{k_all4:.4f} vs {ag_all4['subsets']['n_raters_4']['fleiss_kappa']}")
check("pilot kappa noC matches agreement_noC.json",
      abs(k_noC - ag_noC["subsets"]["n_raters_3"]["fleiss_kappa"]) < 1e-4,
      f"{k_noC:.4f} vs {ag_noC['subsets']['n_raters_3']['fleiss_kappa']}")
check("pilot raw agreement matches (35.0% all4 / 50.0% noC)",
      abs(raw4 - ag_all4["subsets"]["n_raters_4"]["raw_agreement_pct"]) < 0.01 and
      abs(raw3 - ag_noC["subsets"]["n_raters_3"]["raw_agreement_pct"]) < 0.01)

# double-labeled kappa (2-rater items)
dbl_all4 = [[v["label"] for v in labels[g].values()] for g in labels if len(labels[g]) == 2]
kd_all4 = fleiss_kappa(kappa_matrix(dbl_all4))
dbl_noC = [[v["label"] for k, v in labels[g].items() if k != "labeler_c"]
           for g in labels]
dbl_noC = [v for v in dbl_noC if len(v) == 2]
kd_noC = fleiss_kappa(kappa_matrix(dbl_noC))
print(f"  double-labeled: all4 n={len(dbl_all4)} kappa={kd_all4:.4f} | "
      f"noC n={len(dbl_noC)} kappa={kd_noC:.4f}")
check("double-labeled kappa matches both agreement JSONs",
      abs(kd_all4 - ag_all4["subsets"]["double_labeled"]["fleiss_kappa"]) < 1e-4 and
      abs(kd_noC - ag_noC["subsets"]["double_labeled"]["fleiss_kappa"]) < 1e-4,
      f"{kd_all4:.4f}/{kd_noC:.4f} vs {ag_all4['subsets']['double_labeled']['fleiss_kappa']}"
      f"/{ag_noC['subsets']['double_labeled']['fleiss_kappa']}")

# ------------------------------------------------- metrics re-derivation ----
def derive(labeler_set: set[str]) -> dict:
    """Mirror compute_gold_metrics.run on an arbitrary labeler subset."""
    cons: dict[str, dict] = {}
    adj = Counter()
    unlabeled = 0
    for item in gold:
        gid = item["gold_id"]
        labs = {k: v for k, v in labels.get(gid, {}).items() if k in labeler_set}
        if not labs:
            unlabeled += 1
            continue
        votes = {r["label"] for r in labs.values()}
        if len(votes) == 1:
            v = next(iter(votes))
            if v in ("sif", "non_sif"):
                cons[gid] = {
                    "truth": v, "stratum": item["source_stratum"],
                    "gold_rules": sorted({r for x in labs.values() for r in x.get("rules", [])}),
                }
                continue
            adj["unsure"] += 1
        else:
            adj["disagreement"] += 1
    strata: dict[str, dict] = {}
    for name in ("osha_2024_25", "asrs", "synthetic", "real_pooled"):
        gids = [g for g, c in cons.items()
                if c["stratum"] == name or (name == "real_pooled" and c["stratum"] != "synthetic")]
        tp = sum(1 for g in gids if cons[g]["truth"] == "sif" and scores[g]["p_raw"] >= THR)
        fp = sum(1 for g in gids if cons[g]["truth"] != "sif" and scores[g]["p_raw"] >= THR)
        fn = sum(1 for g in gids if cons[g]["truth"] == "sif" and scores[g]["p_raw"] < THR)
        tn = sum(1 for g in gids if cons[g]["truth"] != "sif" and scores[g]["p_raw"] < THR)
        r_est, r_lo, r_hi = wilson(tp, tp + fn)
        p_est, p_lo, p_hi = wilson(tp, tp + fp)
        f1 = (2 * p_est * r_est / (p_est + r_est)) if p_est and r_est else None
        strata[name] = {"n": len(gids), "n_pos": tp + fn, "tp": tp, "fp": fp, "fn": fn,
                        "tn": tn, "recall": (r_est, r_lo, r_hi), "precision": (p_est, p_lo, p_hi),
                        "f1": f1}
    # rules, real pooled
    real_gids = [g for g, c in cons.items() if c["stratum"] != "synthetic"]
    per_rule = {}
    for rule in RULES:
        thr = float(rule_thresholds[rule])
        tp = fp = fn = tn = 0
        for g in real_gids:
            gold_pos = cons[g]["truth"] == "sif" and rule in cons[g]["gold_rules"]
            pred = scores[g]["rule_probs"][rule] >= thr
            tp += gold_pos and pred
            fp += pred and not gold_pos
            fn += gold_pos and not pred
            tn += (not pred) and (not gold_pos)
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        f1 = (2 * prec * rec / (prec + rec)) if prec and rec else None
        per_rule[rule] = {"n_pos": tp + fn, "tp": tp, "fp": fp, "fn": fn,
                          "precision": prec, "recall": rec, "f1": f1,
                          "in_macro": tp + fn >= RULE_MIN_SUPPORT}
    macro = [r for r in RULES if per_rule[r]["in_macro"] and per_rule[r]["f1"] is not None]
    return {"consensus": cons, "n_consensus": len(cons), "n_adj": sum(adj.values()),
            "adj": dict(adj), "n_unlabeled": unlabeled, "strata": strata,
            "per_rule": per_rule,
            "macro_f1": sum(per_rule[r]["f1"] for r in macro) / len(macro) if macro else None,
            "macro_rules": macro}


def close(a, b, tol=1e-6) -> bool:
    if a is None or b is None:
        return a == b
    return abs(a - b) <= tol


def verify(derived: dict, ref_path: Path, tag: str) -> None:
    ref = json.loads(ref_path.read_text())
    g = ref["gold"]
    check(f"[{tag}] coverage counts (consensus/adjudication/unlabeled)",
          derived["n_consensus"] == g["n_consensus"] and
          derived["n_adj"] == g["n_adjudication"] and
          derived["n_unlabeled"] == g["n_unlabeled"],
          f"{derived['n_consensus']}/{derived['n_adj']}/{derived['n_unlabeled']} vs "
          f"{g['n_consensus']}/{g['n_adjudication']}/{g['n_unlabeled']}")
    for name in ("osha_2024_25", "asrs", "synthetic", "real_pooled"):
        d, r = derived["strata"][name], ref["strata"][name]
        c = r["confusion"]
        check(f"[{tag}] {name}: n/pos/confusion",
              d["n"] == r["n"] and d["n_pos"] == r["n_pos"] and
              (d["tp"], d["fp"], d["fn"], d["tn"]) == (c["tp"], c["fp"], c["fn"], c["tn"]),
              f"tp/fp/fn/tn {d['tp']}/{d['fp']}/{d['fn']}/{d['tn']} vs "
              f"{c['tp']}/{c['fp']}/{c['fn']}/{c['tn']}")
        check(f"[{tag}] {name}: recall+CI",
              close(d["recall"][0], r["recall"]["est"]) and
              (d["recall"][1] is None or close(d["recall"][1], r["recall"]["ci95"][0], 1e-9)) and
              (d["recall"][2] is None or close(d["recall"][2], r["recall"]["ci95"][1], 1e-9)))
        check(f"[{tag}] {name}: precision+CI",
              close(d["precision"][0], r["precision"]["est"]) and
              (d["precision"][1] is None or close(d["precision"][1], r["precision"]["ci95"][0], 1e-9)))
        check(f"[{tag}] {name}: F1", close(d["f1"], r["f1"]))
    for rule in RULES:
        d, r = derived["per_rule"][rule], ref["rules"]["per_rule"][rule]
        check(f"[{tag}] rule {rule}: n_pos/tp/fp/fn + F1",
              (d["n_pos"], d["tp"], d["fp"], d["fn"]) == (r["n_pos"], r["tp"], r["fp"], r["fn"])
              and close(d["f1"], r["f1"]) and d["in_macro"] == r["in_macro"],
              f"{d['n_pos']}/{d['tp']}/{d['fp']}/{d['fn']} f1={d['f1'] and round(d['f1'], 4)} "
              f"vs {r['n_pos']}/{r['tp']}/{r['fp']}/{r['fn']} f1={r['f1'] and round(r['f1'], 4)}")
    check(f"[{tag}] macro-F1 + macro rule set",
          close(derived["macro_f1"], ref["rules"]["macro_f1"]) and
          derived["macro_rules"] == ref["rules"]["macro_rules"],
          f"{derived['macro_f1'] and round(derived['macro_f1'], 4)} {derived['macro_rules']}")
    check(f"[{tag}] adjudication by-reason",
          derived["adj"] == ref["adjudication"]["by_reason"],
          f"{derived['adj']} vs {ref['adjudication']['by_reason']}")


print("\n== 4. gold metrics re-derivation vs published JSONs ==")
all4 = derive(set(LABS))
verify(all4, GOLD / "gold_metrics_all4.json", "all4")
noC = derive(set(LABS) - {"labeler_c"})
verify(noC, GOLD / "gold_metrics_noC.json", "noC")

# headline deltas all4 -> noC (the exclusion trade-off)
r4, r3 = all4["strata"]["real_pooled"], noC["strata"]["real_pooled"]
print(f"  real pooled: recall {r4['recall'][0]:.4f} -> {r3['recall'][0]:.4f} "
      f"(delta {(r3['recall'][0]-r4['recall'][0])*100:+.1f}pp), "
      f"precision {r4['precision'][0]:.4f} -> {r3['precision'][0]:.4f}, "
      f"coverage {all4['n_consensus']} -> {noC['n_consensus']} "
      f"({noC['n_unlabeled']} unlabeled without C)")
check("excluding C DROPS real-pooled recall (not flattery)",
      r3["recall"][0] < r4["recall"][0],
      f"{r4['recall'][0]:.4f} -> {r3['recall'][0]:.4f}")

print("\n== 5. error analysis on the all-4 consensus ==")
cons = all4["consensus"]
fp_ids = [g for g, c in cons.items()
          if c["truth"] == "non_sif" and scores[g]["p_raw"] >= THR]
fn_ids = [g for g, c in cons.items()
          if c["truth"] == "sif" and scores[g]["p_raw"] < THR]
fp_by = Counter(cons[g]["stratum"] for g in fp_ids)
fn_by = Counter(cons[g]["stratum"] for g in fn_ids)
print(f"  FP n={len(fp_ids)} {dict(fp_by)} | FN n={len(fn_ids)} {dict(fn_by)}")
check("FP/FN counts equal the published real+synthetic confusion",
      fp_by.get("osha_2024_25", 0) == 38 and fp_by.get("synthetic", 0) == 36 and
      fn_by.get("osha_2024_25", 0) == 23 and fn_by.get("asrs", 0) == 19 and
      fn_by.get("synthetic", 0) == 1,
      f"FP {dict(fp_by)} FN {dict(fn_by)}")

# ASRS: score distribution of the 19 FN (how badly missed?)
asrs_fn = sorted((scores[g]["p_raw"] for g in fn_ids if cons[g]["stratum"] == "asrs"))
asrs_all = [scores[g]["p_raw"] for g, c in cons.items() if c["stratum"] == "asrs"]
asrs_pos = [scores[g]["p_raw"] for g, c in cons.items()
            if c["stratum"] == "asrs" and c["truth"] == "sif"]
print(f"  ASRS: 19/19 positives below threshold; max p_raw={max(asrs_fn):.4f} "
      f"(thr {THR:.4f}); median {statistics.median(asrs_pos):.4f}; "
      f"all-stratum max {max(asrs_all):.4f}")
check("ASRS recall is exactly 0 and not a near-threshold artifact",
      max(asrs_fn) < 0.5 * THR, f"max FN p_raw={max(asrs_fn):.4f} vs thr {THR:.4f}")

# synthetic over-flagging
syn_flagged = [g for g, c in cons.items()
               if c["stratum"] == "synthetic" and scores[g]["p_raw"] >= THR]
syn_fp = [g for g in syn_flagged if cons[g]["truth"] == "non_sif"]
print(f"  synthetic: {len(syn_flagged)} flagged, {len(syn_fp)} of them FP "
      f"(P={13/49:.4f}); median FP p_raw={statistics.median(scores[g]['p_raw'] for g in syn_fp):.4f}")

print("\n== 6. label-provenance of the all-4 consensus + error sets ==")
solo_c = [g for g in cons if list(labels[g]) == ["labeler_c"]]
solo_abd = [g for g in cons if len(labels[g]) == 1 and "labeler_c" not in labels[g]]
osha_fp = [g for g in fp_ids if cons[g]["stratum"] == "osha_2024_25"]
osha_fp_solo_c = [g for g in osha_fp if list(labels[g]) == ["labeler_c"]]
osha_fn = [g for g in fn_ids if cons[g]["stratum"] == "osha_2024_25"]
osha_fn_solo_c = [g for g in osha_fn if list(labels[g]) == ["labeler_c"]]
agree_c = sum(1 for g in solo_c
              if (scores[g]["p_raw"] >= THR) == (cons[g]["truth"] == "sif"))
agree_abd = sum(1 for g in solo_abd
                if (scores[g]["p_raw"] >= THR) == (cons[g]["truth"] == "sif"))
print(f"  consensus items resting on C alone: {len(solo_c)}/{len(cons)} "
      f"({Counter(cons[g]['stratum'] for g in solo_c)})")
print(f"  OSHA FP provenance: {len(osha_fp_solo_c)}/{len(osha_fp)} are C-solo non_sif")
print(f"  OSHA FN provenance: {len(osha_fn_solo_c)}/{len(osha_fn)} are C-solo")
print(f"  model-vs-solo-label agreement: C {agree_c}/{len(solo_c)} "
      f"({100*agree_c/len(solo_c):.0f}%) vs A/B/D {agree_abd}/{len(solo_abd)} "
      f"({100*agree_abd/len(solo_abd):.0f}%)")
check("89 of 400 consensus items rest on labeler_c alone",
      len(solo_c) == 89 and len(cons) == 400)
check("37 of 38 OSHA FPs are C-solo labels (FP count is C-contaminated)",
      len(osha_fp_solo_c) == 37 and len(osha_fp) == 38)
check("0 of 23 OSHA FNs are C-solo (FN class is clean)",
      len(osha_fn_solo_c) == 0 and len(osha_fn) == 23)
check("model-vs-solo-label agreement: C 39/89 (44%) vs A/B/D 170/224 (76%)",
      (agree_c, agree_abd) == (39, 170))

# C vs the A/B/D majority on the calibration pilot
pilot_c_maj = sum(
    1 for gid in pilot_ids
    if labels[gid]["labeler_c"]["label"] ==
    Counter(labels[gid][f"labeler_{x}"]["label"] for x in "abd").most_common(1)[0][0])
print(f"  pilot: C matches the A/B/D majority on {pilot_c_maj}/20")
check("C matches A/B/D majority on only 12/20 pilot items", pilot_c_maj == 12)

# error-shape facts quoted in error_analysis.md
osha_fp_pmax_band = sum(1 for g in osha_fp if scores[g]["p_raw"] < 0.9)
osha_fn_near = [g for g in osha_fn if scores[g]["p_raw"] > 0.5]
syn_fp_ids = [g for g in fp_ids if cons[g]["stratum"] == "synthetic"]
syn_fp_solo_c = sum(1 for g in syn_fp_ids if list(labels[g]) == ["labeler_c"])
print(f"  OSHA FP with p in [thr,0.9): {osha_fp_pmax_band} (all FP are confident)")
print(f"  OSHA FN with p>0.5: {len(osha_fn_near)} "
      f"{[(g, round(scores[g]['p_raw'], 3)) for g in sorted(osha_fn_near)]}")
print(f"  synthetic FP provenance: {syn_fp_solo_c}/{len(syn_fp_ids)} C-solo "
      "(mixed -> genuine over-flagging)")
check("every OSHA FP sits at p>0.9 (confident errors, none near threshold)",
      osha_fp_pmax_band == 0)
check("5 OSHA FNs sit in the 0.5-0.65 near-threshold band",
      len(osha_fn_near) == 5)
check("synthetic FP provenance is mixed (only 11/36 C-solo)",
      syn_fp_solo_c == 11)

dump = {
    "profiles": profiles, "pairwise": pairwise,
    "c_solo": {"n": len(solo_c), "of": len(cons),
               "by_stratum": dict(Counter(cons[g]["stratum"] for g in solo_c)),
               "model_agree": agree_c, "abd_solo_model_agree": agree_abd,
               "n_abd_solo": len(solo_abd),
               "osha_fp_solo_c": len(osha_fp_solo_c), "osha_fn_solo_c": len(osha_fn_solo_c)},
    "pilot_c_matches_abd_majority": pilot_c_maj,
    "pilot": {"kappa_all4": round(k_all4, 4), "kappa_noC": round(k_noC, 4),
              "raw_all4": raw4, "raw_noC": raw3,
              "c_pilot_labels": dict(c_pilot)},
    "kappa_double": {"all4": round(kd_all4, 4), "noC": round(kd_noC, 4),
                     "n_all4": len(dbl_all4), "n_noC": len(dbl_noC)},
    "all4": {k: v for k, v in all4.items() if k != "consensus"},
    "noC": {k: v for k, v in noC.items() if k != "consensus"},
    "errors": {
        "fp_ids": sorted(fp_ids), "fn_ids": sorted(fn_ids),
        "fp_by_stratum": dict(fp_by), "fn_by_stratum": dict(fn_by),
        "asrs_fn_p_raw": [round(x, 4) for x in asrs_fn],
    },
}
out = REPO / "runs/run2/day2/_gold_analysis_dump.json"
out.write_text(json.dumps(dump, indent=1, default=str) + "\n")
print(f"\n  derived analysis dump -> {out.relative_to(REPO)} "
      "(derived data; human label FILES never written)")

print()
if FAILURES:
    print(f"SELF-CHECK FAILED: {FAILURES}")
    sys.exit(1)
print("SELF-CHECK PASS (all numbers in labeler_quality.md / error_analysis.md "
      "recomputed and verified against published JSONs)")
