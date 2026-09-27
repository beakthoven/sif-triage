"""Gold metrics pipeline — one-command consensus evaluation.

Input : artifacts/gold/gold_items.jsonl and a merged labels export
Output: single-text int8 scores plus metrics/queue (paths configurable by CLI)
Default model: artifacts/models/masked-v2/ (int8 ONNX and metrics.json).

The historical gold snapshot used calibrated threshold 0.658108 (raw
0.746401). The current serving operating point is calibrated 0.5647 (raw
0.605638), tuned for the runtime N=4 ensemble. This evaluator scores one
masked text at a time, so a run at the current threshold is a single-text
proxy, not an N=4 serving-path evaluation. The dated snapshot
artifacts/gold/gold_metrics_current_point_20260926.md documents that limitation
and the gold-sample overlap with operating-point tuning.

Protocol: the threshold is applied once to p_raw; per-stratum metrics and a
real-only pooled headline are reported, synthetic is kept separate, and
Wilson 95% CIs are reported for precision/recall. Disagreements and unsure
labels remain excluded pending adjudication. Human agreement is human-vs-human
only; rulings supersede split votes before consensus and never enter kappa.

Run:        .venv/bin/python gold/compute_gold_metrics.py
Self-check: .venv/bin/python gold/compute_gold_metrics.py --self-check
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "runs" / "run2" / "day1" / "real_model_integration"))

from gold_common import LABELS, RULES, SEED  # noqa: E402
from adjudicate import load_rulings  # noqa: E402
from export_labels import BOOTSTRAP_N, bootstrap_se, fleiss_kappa, kappa_matrix  # noqa: E402
from onnx_score import RULES as MODEL_RULES  # noqa: E402
from onnx_score import Scorer, sigmoid  # noqa: E402

assert tuple(RULES) == tuple(MODEL_RULES), "rule order drifted from model head"

Z = 1.96
PRECISION_FLOOR = 0.80
RECALL_CI_WIDTH_LIMIT = 0.12
RULE_MIN_SUPPORT = 50
STRATA = ("osha_2024_25", "asrs", "synthetic")
REAL_STRATA = ("osha_2024_25", "asrs")

CONSENSUS_POLICY = (
    "unanimous label across the item's raters; any disagreement or any "
    "'unsure' (including a single-rater unsure) -> adjudication queue, excluded "
    "from metrics until adjudicated; rule tags on consensus-sif items = union "
    "of rater tags"
)


# ---------------------------------------------------------------- statistics --
def wilson(k: int, n: int, z: float = Z) -> tuple[float | None, float | None, float | None]:
    """Wilson score interval. Returns (est, lo, hi); (None, None, None) at n=0."""
    if n == 0:
        return None, None, None
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def ci_dict(k: int, n: int) -> dict:
    est, lo, hi = wilson(k, n)
    return {
        "est": est,
        "ci95": None if lo is None else [lo, hi],
        "width": None if lo is None else hi - lo,
        "n": n,
    }


# ------------------------------------------------------------------- loading --
def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_operating_point(model_dir: Path) -> dict:
    """The D27 frozen operating point. thresholds.json's sif_threshold is the
    VACUOUS val-frozen point (D19) and is deliberately never read here."""
    mp = model_dir / "metrics.json"
    metrics = json.loads(mp.read_text())
    op = metrics.get("operating_point_test_tuned")
    if not isinstance(op, dict) or not op.get("threshold"):
        raise SystemExit(
            f"ERROR: {mp} has no operating_point_test_tuned — the D19/D27 "
            "test-tuned operating point is required (val-frozen point is "
            "vacuous, D19). Refusing to guess a threshold.")
    return {
        "threshold_raw": float(op["threshold"]),
        "threshold_calibrated": float(op.get("threshold_calibrated", 0.0)),
        "source": f"{model_dir}/metrics.json operating_point_test_tuned",
        "selection": op.get("selection", "max recall subject to precision >= 0.80"),
        "temperature": float(metrics["temperature"]),
    }


def model_fingerprint(model_dir: Path, op: dict) -> dict:
    onnx_name = "sif_multitask_int8.onnx"
    manifest_path = model_dir / "manifest.json"
    sha = "unknown"
    spec_sha = "unknown"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        sha = manifest.get("files", {}).get(onnx_name, {}).get("sha256", "unknown")
        spec_sha = manifest.get("spec_sha256", "unknown")
    return {
        "model_dir": str(model_dir.relative_to(REPO) if model_dir.is_relative_to(REPO) else model_dir),
        "onnx": onnx_name,
        "onnx_sha256_12": sha[:12],
        "spec_sha256_12": spec_sha[:12],
        "quant": "int8",
        "scoring": "onnx_score.Scorer, single-text batch=1 (D27 ship path)",
        "threshold_raw": op["threshold_raw"],
    }


def fp_key(fp: dict) -> str:
    return json.dumps(fp, sort_keys=True)


# ------------------------------------------------------------------- scoring --
def score_gold(gold: list[dict], scores_path: Path, model_dir: Path,
               op: dict, threads: int, rescore: bool) -> dict[str, dict]:
    """Score every gold item single-text int8 (D27). Idempotent: a cache row
    with a matching model fingerprint is reused; only missing/stale rows are
    scored. Returns gold_id -> score row."""
    fp = model_fingerprint(model_dir, op)
    key = fp_key(fp)
    cache: dict[str, dict] = {}
    if scores_path.exists() and not rescore:
        for row in load_jsonl(scores_path):
            if row.get("fingerprint") == key:
                cache[row["gold_id"]] = row
    want = {r["gold_id"] for r in gold}
    missing = [r for r in gold if r["gold_id"] not in cache]
    if not missing and set(cache) >= want:
        print(f"scores: cache hit — {len(cache)}/{len(want)} rows "
              f"(fingerprint {fp['onnx_sha256_12']}, thr {op['threshold_raw']})")
        return {gid: cache[gid] for gid in sorted(want)}

    scorer = Scorer(model_dir, quant="int8", threads=threads)
    print(f"scores: scoring {len(missing)} of {len(gold)} gold items "
          f"single-text int8 (D27 ship path, threads={threads}) ...")
    t0 = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for i, item in enumerate(missing):
        z, rule_logits = scorer.logits([item["masked_text"]], batch=1)
        rule_probs = sigmoid(rule_logits[0])
        cache[item["gold_id"]] = {
            "gold_id": item["gold_id"],
            "sif_logit": float(z[0]),
            "p_raw": float(sigmoid(z[0])),
            "p_cal": float(sigmoid(z[0] / scorer.temperature)),
            "rule_probs": {r: float(p) for r, p in zip(RULES, rule_probs)},
            "fingerprint": key,
            "scored_at": t0,
        }
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(missing)}", flush=True)
    rows = [cache[gid] for gid in sorted(want)]
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    with open(scores_path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    print(f"scores: wrote {scores_path} ({len(rows)} rows)")
    return {r["gold_id"]: r for r in rows}


# ------------------------------------------------------- consensus + metrics --
def consensus_votes(labs: dict) -> tuple[str | None, str | None]:
    """labs: labeler -> {label, rules, ...}. Returns (truth, adjudication_reason)."""
    votes = {r["label"] for r in labs.values()}
    if len(votes) == 1:
        v = next(iter(votes))
        if v in ("sif", "non_sif"):
            return v, None
        return None, "unsure"
    return None, "disagreement"


def metrics_block(truths: list[str], preds: list[bool]) -> dict:
    tp = sum(1 for t, p in zip(truths, preds) if t == "sif" and p)
    fp = sum(1 for t, p in zip(truths, preds) if t != "sif" and p)
    fn = sum(1 for t, p in zip(truths, preds) if t == "sif" and not p)
    tn = sum(1 for t, p in zip(truths, preds) if t != "sif" and not p)
    n = tp + fp + fn + tn
    n_pos = tp + fn
    recall = ci_dict(tp, n_pos)
    precision = ci_dict(tp, tp + fp)
    pe, re_ = precision["est"], recall["est"]
    f1 = (2 * pe * re_ / (pe + re_)) if pe and re_ and (pe + re_) else None
    return {
        "n": n,
        "n_pos": n_pos,
        "prevalence": n_pos / n if n else None,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "flag_rate": (tp + fp) / n if n else None,
    }


def rules_metrics(items: list[dict], scores: dict[str, dict],
                  rule_thresholds: dict) -> dict:
    """Per-rule one-vs-rest over the stratum's consensus items. Gold rule
    positive = consensus-sif item whose (union) human tags include the rule."""
    per_rule = {}
    for rule in RULES:
        tp = fp = fn = tn = 0
        thr = float(rule_thresholds[rule])
        for it in items:
            gold_pos = it["truth"] == "sif" and rule in it["gold_rules"]
            pred_pos = scores[it["gold_id"]]["rule_probs"][rule] >= thr
            if gold_pos and pred_pos:
                tp += 1
            elif pred_pos and not gold_pos:
                fp += 1
            elif gold_pos and not pred_pos:
                fn += 1
            else:
                tn += 1
        n_pos = tp + fn
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / n_pos if n_pos else None
        f1 = (2 * prec * rec / (prec + rec)) if prec and rec and (prec + rec) else None
        per_rule[rule] = {
            "n_pos": n_pos, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": prec, "recall": rec, "f1": f1,
            "threshold": thr, "in_macro": n_pos >= RULE_MIN_SUPPORT,
        }
    in_macro = [r for r in RULES if per_rule[r]["in_macro"]]
    others = [r for r in RULES if not per_rule[r]["in_macro"]]
    macro_f1s = [per_rule[r]["f1"] for r in in_macro if per_rule[r]["f1"] is not None]
    other = {"members": others}
    if others:
        tp = sum(per_rule[r]["tp"] for r in others)
        fp = sum(per_rule[r]["fp"] for r in others)
        fn = sum(per_rule[r]["fn"] for r in others)
        tn = sum(per_rule[r]["tn"] for r in others)
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        f1 = (2 * prec * rec / (prec + rec)) if prec and rec and (prec + rec) else None
        other.update({
            "n_pos": tp + fn, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": prec, "recall": rec, "f1": f1,
            "disclosure": (
                f"rules with <{RULE_MIN_SUPPORT} gold positives merged into "
                "'Other' (spec cs_ei_support_weakness: macro-F1 only over "
                f"rules with >={RULE_MIN_SUPPORT} gold positives)"),
        })
    return {
        "min_support": RULE_MIN_SUPPORT,
        "stratum": "real_pooled",
        "per_rule": per_rule,
        "macro_rules": in_macro,
        "macro_f1": sum(macro_f1s) / len(macro_f1s) if macro_f1s else None,
        "other": other,
    }


# ----------------------------------------------------------------- agreement --
def agreement_from_merged(merged: list[dict], seed: int) -> dict:
    """Fleiss' kappa grouped by rater count — mirrors export_labels.py exactly
    (functions imported from it); human-vs-human only."""
    by_n: dict[int, list[list[str]]] = {}
    for row in merged:
        labs = row["labels"]
        if len(labs) >= 2:
            by_n.setdefault(len(labs), []).append([v["label"] for v in labs.values()])
    out = {"categories": list(LABELS), "human_vs_human_only": True, "subsets": {}}
    for n, item_labels in sorted(by_n.items()):
        k = fleiss_kappa(kappa_matrix(item_labels))
        se = bootstrap_se(item_labels, BOOTSTRAP_N, seed)
        n_agree = sum(1 for labs in item_labels if len(set(labs)) == 1)
        subset = "double_labeled" if n == 2 else f"n_raters_{n}"
        out["subsets"][subset] = {
            "items": len(item_labels),
            "raters_per_item": n,
            "fleiss_kappa": None if math.isnan(k) else round(k, 4),
            "bootstrap_se": None if math.isnan(se) else round(se, 4),
            "raw_agreement_pct": round(100 * n_agree / len(item_labels), 2),
            "note": "calibration pilot subset" if n > 2 else
                    "spec'd kappa subset (gold.labeling.agreement)",
        }
    return out


def cross_check_agreement(agreement: dict, agreement_path: Path, flags: list) -> dict:
    """Sanity: our recomputed kappa must match export_labels.py's output."""
    if not agreement_path.exists():
        return {"agreement_json": None, "match": None}
    ref = json.loads(agreement_path.read_text())
    # kappa is deterministic -> near-exact match required; bootstrap_se is a
    # Monte Carlo estimate whose resamples depend on item ORDER (export scans
    # rater files, we scan the merged file), so it gets an MC-noise tolerance.
    tolerances = {"fleiss_kappa": 1e-4, "bootstrap_se": 0.01, "items": 0}
    mismatches = []
    for subset, vals in agreement["subsets"].items():
        r = ref.get("subsets", {}).get(subset, {})
        for field, tol in tolerances.items():
            a, b = vals.get(field), r.get(field)
            if a is None or b is None:
                if a != b:
                    mismatches.append((subset, field, a, b))
            elif isinstance(a, float) and abs(a - b) > tol:
                mismatches.append((subset, field, a, b))
            elif field == "items" and a != b:
                mismatches.append((subset, field, a, b))
    if mismatches:
        flags.append({
            "id": "AGREEMENT_MISMATCH", "severity": "SEV2",
            "detail": f"kappa recomputation != {agreement_path}: {mismatches}",
        })
    return {"agreement_json": str(agreement_path), "match": not mismatches}


# ------------------------------------------------------------------ markdown --
def f3(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}"


def fci(d: dict) -> str:
    if d["est"] is None:
        return "—"
    return f"{d['est']:.3f} [{d['ci95'][0]:.3f}, {d['ci95'][1]:.3f}] (n={d['n']})"


def render_md(result: dict) -> str:
    md = []
    fp = result["model"]
    md.append(f"# Gold metrics — consensus eval ({fp['model_dir']}, single-text int8)")
    md.append("")
    md.append("**Evaluation limitations:** This evaluates single-text int8 scores, "
              "not the current serving N=4 ensemble; the ensemble's calibrated "
              "threshold is converted to its raw-score equivalent and applied to "
              "single-text scores. OSHA gold items were sampled from the same "
              "`artifacts/corpus/test.jsonl` temporal test split used to tune the "
              "operating point, so this is not a fully held-out evaluation. "
              "Synthetic items are not excluded from training data and may "
              "overlap training; their metrics are not generalization evidence.")
    md.append("")
    op = result["operating_point"]
    md.append(f"- Model: `{fp['model_dir']}` int8 (`{fp['onnx']}` sha "
              f"{fp['onnx_sha256_12']}…), scored {fp['scoring']}")
    md.append(f"- Operating point: p_raw ≥ **{op['threshold_raw']}** "
              f"(calibrated-scale {op['threshold_calibrated']:.6f}) — {op['source']}; "
              f"{op['selection']}; **applied once** to gold, no re-tuning")
    md.append(f"- Generated: {result['generated_at']} by `gold/compute_gold_metrics.py`")
    g = result["gold"]
    md.append(f"- Gold truth: {g['consensus_policy']}")
    md.append(f"- Coverage: {g['n_consensus']} consensus / {g['n_items']} items; "
              f"{g['n_adjudication']} pending adjudication, {g['n_unlabeled']} unlabeled"
              + (f"; **{g['n_adjudicated']} adjudicated** (rulings applied as "
                 f"superseding overrides), {g['n_adjudicated_unsure']} ruled "
                 f"final-unsure (excluded)" if g["n_adjudicated"]
                 or g["n_adjudicated_unsure"] else ""))
    md.append("")
    md.append("## Per-stratum results")
    md.append("")
    md.append("| stratum | n | positives | prevalence | recall [95% CI] | "
              "precision [95% CI] | F1 | TP/FP/FN/TN |")
    md.append("|---|---|---|---|---|---|---|---|")
    order = [("**real pooled (headline)**", "real_pooled"),
             ("osha_2024_25", "osha_2024_25"), ("asrs", "asrs"),
             ("synthetic *(separate, never pooled)*", "synthetic")]
    for label, key in order:
        s = result["strata"][key]
        c = s["confusion"]
        md.append(
            f"| {label} | {s['n']} | {s['n_pos']} | {f3(s['prevalence'])} | "
            f"{fci(s['recall'])} | {fci(s['precision'])} | {f3(s['f1'])} | "
            f"{c['tp']}/{c['fp']}/{c['fn']}/{c['tn']} |")
    md.append("")
    md.append("*F1 carries no CI (ratio of two binomial estimates); recall CI "
              "is over positives, precision CI over flagged — Wilson z=1.96.*")
    md.append("")
    md.append("## Flags")
    md.append("")
    if result["flags"]:
        for fl in result["flags"]:
            md.append(f"- **{fl['id']}** ({fl['severity']}): {fl['detail']}")
    else:
        md.append("- none")
    md.append("")
    r = result["rules"]
    md.append(f"## Rules — macro-F1 over rules with ≥{r['min_support']} gold "
              f"positives (real pooled stratum)")
    md.append("")
    md.append("| rule | gold pos | TP/FP/FN | precision | recall | F1 | in macro |")
    md.append("|---|---|---|---|---|---|---|")
    for rule in RULES:
        pr = r["per_rule"][rule]
        md.append(f"| {rule} | {pr['n_pos']} | {pr['tp']}/{pr['fp']}/{pr['fn']} | "
                  f"{f3(pr['precision'])} | {f3(pr['recall'])} | {f3(pr['f1'])} | "
                  f"{'yes' if pr['in_macro'] else 'no → Other'} |")
    if r["other"]["members"]:
        o = r["other"]
        md.append(f"| **Other** ({', '.join(o['members'])}) | {o['n_pos']} | "
                  f"{o['tp']}/{o['fp']}/{o['fn']} | {f3(o['precision'])} | "
                  f"{f3(o['recall'])} | {f3(o['f1'])} | merged, disclosed |")
    md.append("")
    md.append(f"**Rules macro-F1 ({len(r['macro_rules'])} rules "
              f"{r['macro_rules']}): {f3(r['macro_f1'])}**")
    md.append("")
    ag = result["agreement"]
    md.append("## Human agreement (human-vs-human only)")
    md.append("")
    md.append("| subset | items | raters/item | Fleiss κ | bootstrap SE | raw agreement |")
    md.append("|---|---|---|---|---|---|")
    for name, s in ag["subsets"].items():
        md.append(f"| {name} | {s['items']} | {s['raters_per_item']} | "
                  f"{s['fleiss_kappa']} | ±{s['bootstrap_se']} | {s['raw_agreement_pct']}% |")
    md.append("")
    adj = result["adjudication"]
    md.append("## Adjudication")
    md.append("")
    ru = adj["rulings"]
    if ru["n_applied"]:
        md.append(f"- **{ru['n_applied']} rulings applied** from `{ru['path']}` "
                  f"(by label: "
                  + ", ".join(f"{k}={v}" for k, v in sorted(ru["by_label"].items()))
                  + ") — each ruling superseded the item's split votes "
                  "(pre-consensus override; latest ruling wins; rulings never "
                  "enter kappa, which stays human-vs-human).")
        if ru["stale_ids_ignored"]:
            md.append(f"- WARNING: {len(ru['stale_ids_ignored'])} ruling(s) reference "
                      f"ids outside the gold set and were ignored: "
                      f"{ru['stale_ids_ignored'][:5]}")
    if adj["n"]:
        md.append(f"- {adj['n']} items still need a ruling → `{adj['path']}` (by reason: "
                  + ", ".join(f"{k}={v}" for k, v in sorted(adj["by_reason"].items())) + ")")
        md.append("- Queue is blind: no stratum, no model output. Rule on it with "
                  "`gold/adjudicate.py` (see gold/RUNBOOK_HUMANS.md), then re-run "
                  "this script — rulings apply automatically (score cache makes "
                  "the re-run seconds).")
    else:
        md.append("- Pending queue is empty — every disagreement/unsure has a final ruling.")
    md.append("")
    md.append("## Provenance")
    md.append("")
    md.append(f"- Model fingerprint: `{json.dumps(fp, sort_keys=True)}`")
    md.append(f"- Score cache: `{result['artifacts']['scores']}` "
              f"({g['n_scored']} rows, idempotent)")
    md.append(f"- Metrics JSON: `{result['artifacts']['metrics_json']}`")
    md.append("- Synthetic stratum reported separately above, never pooled into "
              "the headline (spec gold.reporting).")
    md.append("")
    return "\n".join(md)


# ------------------------------------------------------------------ pipeline --
def run(args: argparse.Namespace) -> int:
    gold_path = Path(args.gold)
    merged_path = Path(args.merged)
    labels_dir = Path(args.labels_dir)
    scores_path = Path(args.scores)
    agreement_path = Path(args.agreement)
    model_dir = Path(args.model_dir)

    gold = load_jsonl(gold_path)
    op = load_operating_point(model_dir)
    if args.threshold_calibrated is not None:
        if not 0.0 < args.threshold_calibrated < 1.0:
            raise SystemExit("ERROR: --threshold-calibrated must be between 0 and 1")
        logit = math.log(args.threshold_calibrated / (1.0 - args.threshold_calibrated))
        op["threshold_calibrated"] = args.threshold_calibrated
        op["threshold_raw"] = sigmoid(logit * op["temperature"])
        op["source"] = "--threshold-calibrated override"
        op["selection"] = "externally supplied calibrated operating point"

    # Step 1: score all gold items (idempotent cache).
    scores = score_gold(gold, scores_path, model_dir, op, args.threads, args.rescore)

    # Auto-export when the merge is missing but label files exist.
    if not merged_path.exists():
        if labels_dir.exists() and any(labels_dir.glob("labeler_*.jsonl")):
            print(f"labels: {merged_path} missing — running export_labels.py")
            proc = subprocess.run(
                [sys.executable, str(HERE / "export_labels.py"),
                 "--gold", str(gold_path), "--labels-dir", str(labels_dir),
                 "--out", str(merged_path), "--agreement", str(agreement_path)],
                capture_output=True, text=True)
            if proc.returncode != 0:
                print(proc.stdout)
                print(proc.stderr, file=sys.stderr)
                return 2
            print("  " + proc.stdout.replace("\n", "\n  ").rstrip())
        else:
            print(f"labels: {merged_path} not found and no label files in "
                  f"{labels_dir} — score cache written; run again after "
                  "labeling + export_labels.py for metrics.")
            return 2

    merged = load_jsonl(merged_path)
    merged_by_id = {r["gold_id"]: r for r in merged}
    gold_by_id = {r["gold_id"]: r for r in gold}

    # Step 2: frozen threshold applied ONCE (decisions only; no re-tuning).
    thr = op["threshold_raw"]
    for gid, row in scores.items():
        row["pred_sif"] = row["p_raw"] >= thr

    # Step 3: adjudication rulings (pre-consensus overrides), then consensus,
    # strata, adjudication queue.
    rulings_path = Path(args.rulings)
    rulings = load_rulings(rulings_path) if rulings_path.exists() else {}
    if rulings:
        print(f"adjudication: applying {len(rulings)} ruling(s) from "
              f"{rulings_path} as superseding item-level overrides (latest wins)")
    items_by_stratum: dict[str, list[dict]] = {s: [] for s in STRATA}
    adjudication: list[dict] = []
    unlabeled: list[str] = []
    adjudicated_unsure: list[str] = []
    n_adjudicated = 0
    ruling_by_label: dict[str, int] = {}
    stale_rulings = sorted(set(rulings) - {r["gold_id"] for r in gold})
    orphans = sorted(set(merged_by_id) - set(gold_by_id))
    for item in gold:
        gid = item["gold_id"]
        stratum = item["source_stratum"]
        ruling = rulings.get(gid)
        if ruling is not None:
            # The ruling REPLACES the item's split votes (not a 5th rater):
            # the item is unanimous-by-ruling. A final 'unsure' ruling keeps
            # the item out of metrics but clears it from the pending queue.
            ruling_by_label[ruling["label"]] = ruling_by_label.get(ruling["label"], 0) + 1
            if ruling["label"] == "unsure":
                adjudicated_unsure.append(gid)
                continue
            n_adjudicated += 1
            items_by_stratum[stratum].append({
                "gold_id": gid, "truth": ruling["label"],
                "gold_rules": sorted(ruling.get("rules") or []),
            })
            continue
        rec = merged_by_id.get(gid)
        if rec is None:
            unlabeled.append(gid)
            continue
        truth, adj_reason = consensus_votes(rec["labels"])
        if adj_reason is not None:
            adjudication.append({
                "gold_id": gid,
                "masked_text": item["masked_text"],
                "event_title": item.get("event_title"),
                "adjudication_reason": adj_reason,
                "labels": rec["labels"],
            })
            continue
        gold_rules = sorted({r for v in rec["labels"].values() for r in v.get("rules", [])})
        items_by_stratum[stratum].append({
            "gold_id": gid, "truth": truth, "gold_rules": gold_rules,
        })

    flags: list[dict] = []
    strata: dict[str, dict] = {}
    for name in STRATA:
        items = items_by_stratum[name]
        strata[name] = metrics_block(
            [it["truth"] for it in items],
            [scores[it["gold_id"]]["pred_sif"] for it in items])
    real_items = [it for name in REAL_STRATA for it in items_by_stratum[name]]
    strata["real_pooled"] = metrics_block(
        [it["truth"] for it in real_items],
        [scores[it["gold_id"]]["pred_sif"] for it in real_items])

    headline = strata["real_pooled"]
    if headline["precision"]["est"] is not None and \
            headline["precision"]["est"] < PRECISION_FLOOR - 1e-12:
        flags.append({
            "id": "PRECISION_FLOOR_FAIL", "severity": "SEV1",
            "detail": (f"real-pooled precision {headline['precision']['est']:.4f} "
                       f"< {PRECISION_FLOOR} — the operating-point claim fails on gold"),
        })
    rw = headline["recall"]["width"]
    if rw is not None and rw > RECALL_CI_WIDTH_LIMIT:
        flags.append({
            "id": "RECALL_CI_TOO_WIDE", "severity": "SEV2",
            "detail": (f"real-pooled recall CI width {rw:.3f} > {RECALL_CI_WIDTH_LIMIT} "
                       "— headline is underpowered (spec wants ≤0.12)"),
        })
    if unlabeled:
        flags.append({
            "id": "INCOMPLETE_LABELING", "severity": "SEV2",
            "detail": f"{len(unlabeled)} of {len(gold)} gold items have no label",
        })
    if adjudication:
        flags.append({
            "id": "ADJUDICATION_PENDING", "severity": "SEV3",
            "detail": (f"{len(adjudication)} items excluded pending adjudication; "
                       "metrics shift when rulings land"),
        })

    # Step 4: rules macro-F1 (>=50 positives; others -> Other).
    tcfg = json.loads((model_dir / "thresholds.json").read_text())
    rules = rules_metrics(real_items, scores, tcfg["rule_thresholds"])

    # Step 5: human-vs-human kappa (from export_labels functions) + cross-check.
    agreement = agreement_from_merged(merged, args.seed)
    agreement["cross_check"] = cross_check_agreement(agreement, agreement_path, flags)

    # Adjudication queue (BLIND: no stratum, no model output).
    adj_path = Path(args.adjudication_out)
    adj_path.parent.mkdir(parents=True, exist_ok=True)
    with open(adj_path, "w", encoding="utf-8") as fh:
        for row in adjudication:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    by_reason: dict[str, int] = {}
    for row in adjudication:
        by_reason[row["adjudication_reason"]] = by_reason.get(row["adjudication_reason"], 0) + 1

    # Step 6: final table JSON + markdown.
    n_consensus = sum(len(v) for v in items_by_stratum.values())
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model_fingerprint(model_dir, op),
        "operating_point": {
            "threshold_raw": op["threshold_raw"],
            "threshold_calibrated": op["threshold_calibrated"],
            "source": op["source"],
            "selection": op["selection"],
            "applied": "once, frozen; decisions on p_raw >= threshold_raw; no re-tuning on gold",
        },
        "gold": {
            "n_items": len(gold),
            "n_scored": len(scores),
            "n_merged_rows": len(merged),
            "n_consensus": n_consensus,
            "n_adjudicated": n_adjudicated,
            "n_adjudicated_unsure": len(adjudicated_unsure),
            "n_adjudication": len(adjudication),
            "n_unlabeled": len(unlabeled),
            "unlabeled_ids": unlabeled,
            "orphan_label_ids": orphans,
            "consensus_policy": CONSENSUS_POLICY,
        },
        "strata": strata,
        "headline_stratum": "real_pooled",
        "flags": flags,
        "rules": rules,
        "agreement": agreement,
        "adjudication": {
            "n": len(adjudication),
            "by_reason": by_reason,
            "path": str(adj_path),
            "blind": "no stratum, no model output in the queue",
            "rulings": {
                "path": str(rulings_path) if rulings else None,
                "n_applied": n_adjudicated + len(adjudicated_unsure),
                "by_label": ruling_by_label,
                "stale_ids_ignored": stale_rulings,
                "policy": ("latest ruling per item wins; a ruling SUPERSEDES the "
                           "item's split votes (item-level override, not a 5th "
                           "rater; never enters kappa); a final 'unsure' ruling "
                           "keeps the item excluded but clears the pending queue"),
            },
        },
        "artifacts": {
            "scores": str(scores_path),
            "metrics_json": str(args.out_json),
            "metrics_md": str(args.out_md),
            "adjudication_queue": str(adj_path),
        },
    }
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=1) + "\n")
    out_md = Path(args.out_md)
    out_md.write_text(render_md(result))
    print(f"wrote {out_json}\nwrote {out_md}\nwrote {adj_path} "
          f"({len(adjudication)} items)")

    for name, key in [("real pooled (HEADLINE)", "real_pooled")] + [(s, s) for s in STRATA]:
        s = strata[key]
        print(f"  {name:26s} n={s['n']:3d} pos={s['n_pos']:3d} "
              f"P={f3(s['precision']['est'])} R={f3(s['recall']['est'])} "
              f"F1={f3(s['f1'])}")
    for fl in flags:
        print(f"  FLAG {fl['severity']} {fl['id']}: {fl['detail']}")
    return 0


# ---------------------------------------------------------------- self-check --
def self_check(args: argparse.Namespace) -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    print("== unit: Wilson CIs vs the corrected eval table (eval-metrics-engineer.md 1a) ==")
    _, lo, hi = wilson(51, 60)
    check("recall 0.85 @60 positives -> [0.739, 0.919]",
          abs(lo - 0.739) < 5e-4 and abs(hi - 0.919) < 5e-4, f"[{lo:.4f}, {hi:.4f}]")
    _, lo, hi = wilson(85, 100)
    check("recall 0.85 @100 positives -> [0.767, 0.907]",
          abs(lo - 0.767) < 5e-4 and abs(hi - 0.907) < 5e-4, f"[{lo:.4f}, {hi:.4f}]")
    est, lo, hi = wilson(0, 0)
    check("n=0 -> Nones", est is None and lo is None and hi is None)

    print("== unit: confusion/P/R/F1 on a constructed case ==")
    truths = ["sif"] * 5 + ["non_sif"] * 5
    preds = [True] * 4 + [False] + [True] * 2 + [False] * 3  # tp4 fn1 fp2 tn3
    m = metrics_block(truths, preds)
    check("tp/fp/fn/tn = 4/2/1/3", m["confusion"] == {"tp": 4, "fp": 2, "fn": 1, "tn": 3})
    check("precision=4/6, recall=4/5, F1=8/11",
          abs(m["precision"]["est"] - 4 / 6) < 1e-12 and
          abs(m["recall"]["est"] - 4 / 5) < 1e-12 and
          abs(m["f1"] - 8 / 11) < 1e-12, f"F1={m['f1']:.6f}")
    check("precision CI n = flagged (6), recall CI n = positives (5)",
          m["precision"]["n"] == 6 and m["recall"]["n"] == 5)

    print("== e2e: simulated labels in a temp dir (real artifacts untouched) ==")
    artifacts_gold = REPO / "artifacts" / "gold"
    before = {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
              for p in artifacts_gold.glob("*") if p.is_file()}
    labels_before = (artifacts_gold / "labels").exists()

    from gold_common import LABELER_IDS
    from simulate_labeling import sim_label

    tmp = Path(tempfile.mkdtemp(prefix="gold_metrics_selfcheck_"))
    try:
        gold = load_jsonl(REPO / "artifacts" / "gold" / "gold_items.jsonl")
        labels_dir = tmp / "labels"
        labels_dir.mkdir()
        ts = "2026-09-08T00:00:00+00:00"
        files: dict[str, list[dict]] = {lab: [] for lab in LABELER_IDS}
        for it in gold:
            a = it["assignment"]
            if it["is_pilot"]:
                raters = LABELER_IDS
            elif a["is_double"]:
                raters = (a["labeler"], a["second_labeler"])
            else:
                raters = (a["labeler"],)
            for lab in raters:
                rec = sim_label(it["gold_id"], lab, it["masked_text"])
                if rec["label"] != "sif":
                    rec["rules"] = []  # labeler_app invariant
                rec["ts"] = ts
                files[lab].append(rec)
        for lab, recs in files.items():
            with open(labels_dir / f"{lab}.jsonl", "w", encoding="utf-8") as fh:
                for rec in recs:
                    fh.write(json.dumps(rec) + "\n")

        argv = [
            "--gold", str(REPO / "artifacts" / "gold" / "gold_items.jsonl"),
            "--labels-dir", str(labels_dir),
            "--merged", str(tmp / "labels_merged.jsonl"),
            "--agreement", str(tmp / "agreement.json"),
            "--scores", str(tmp / "model_scores.jsonl"),
            "--out-json", str(tmp / "gold_metrics.json"),
            "--out-md", str(tmp / "gold_metrics.md"),
            "--adjudication-out", str(tmp / "adjudication_queue.jsonl"),
            "--rulings", str(tmp / "labels" / "adjudication.jsonl"),
        ]
        # Fast path: reuse the real score cache when it exists (same
        # fingerprint -> cache hit); otherwise this scores 500 items fresh.
        real_cache = artifacts_gold / "model_scores.jsonl"
        if real_cache.exists():
            shutil.copy(real_cache, tmp / "model_scores.jsonl")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc1 = main(argv)
        print("  " + buf.getvalue().replace("\n", "\n  ").rstrip())
        check("pipeline exits 0 on simulated labels", rc1 == 0)

        result = json.loads((tmp / "gold_metrics.json").read_text())
        g = result["gold"]
        check("all 500 items scored", g["n_scored"] == 500, str(g["n_scored"]))
        check("consensus + adjudication + unlabeled == 500",
              g["n_consensus"] + g["n_adjudication"] + g["n_unlabeled"] == 500,
              f"{g['n_consensus']}+{g['n_adjudication']}+{g['n_unlabeled']}")
        check("sim noise produced a non-empty adjudication queue",
              g["n_adjudication"] > 0, f"{g['n_adjudication']} items, {result['adjudication']['by_reason']}")
        strata = result["strata"]
        check("synthetic stratum separate; real pooled excludes it",
              strata["real_pooled"]["n"] ==
              strata["osha_2024_25"]["n"] + strata["asrs"]["n"] and
              strata["synthetic"]["n"] > 0,
              f"real={strata['real_pooled']['n']} synth={strata['synthetic']['n']}")
        dbl = result["agreement"]["subsets"].get("double_labeled", {})
        check("kappa computed on the double-labeled subset",
              dbl.get("items", 0) > 0 and dbl.get("fleiss_kappa") is not None,
              f"{dbl.get('items')} items, kappa={dbl.get('fleiss_kappa')}")
        check("kappa cross-check vs export_labels.py agreement.json matches",
              result["agreement"]["cross_check"]["match"] is True)
        for rule, pr in result["rules"]["per_rule"].items():
            if pr["in_macro"] != (pr["n_pos"] >= RULE_MIN_SUPPORT):
                check(f"in_macro consistency ({rule})", False)
                break
        else:
            check("in_macro == (n_pos >= 50) for every rule; Other bucket consistent",
                  set(result["rules"]["other"]["members"]) ==
                  {r for r in RULES if not result["rules"]["per_rule"][r]["in_macro"]},
                  f"macro={result['rules']['macro_rules']}")
        adj_rows = load_jsonl(tmp / "adjudication_queue.jsonl")
        check("adjudication queue is blind (no stratum, no model output)",
              all("source_stratum" not in json.dumps(r) and "p_raw" not in json.dumps(r)
                  and "sif_logit" not in json.dumps(r) for r in adj_rows),
              f"{len(adj_rows)} rows")
        md = (tmp / "gold_metrics.md").read_text()
        check("markdown has headline table, flags, rules, kappa, provenance",
              all(s in md for s in ("real pooled (headline)", "## Flags",
                                    "macro-F1", "Fleiss", "Provenance")))

        print("== e2e: idempotency (second run reuses the score cache) ==")
        cache_bytes = (tmp / "model_scores.jsonl").read_bytes()
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            rc2 = main(argv)
        check("second run exits 0 and reports cache hit",
              rc2 == 0 and "cache hit" in buf2.getvalue())
        check("score cache bytes unchanged on re-run",
              (tmp / "model_scores.jsonl").read_bytes() == cache_bytes)

        print("== e2e: adjudication rulings applied as superseding overrides ==")
        rulings_file = tmp / "labels" / "adjudication.jsonl"
        with open(rulings_file, "w", encoding="utf-8") as fh:
            for row in adj_rows:
                rec = sim_label(row["gold_id"], "adjudicator_senior", row["masked_text"])
                fh.write(json.dumps({
                    "ts": ts, "gold_id": row["gold_id"], "label": rec["label"],
                    "rules": rec["rules"] if rec["label"] == "sif" else [],
                    "justification": "self-check ruling (rubric: judge the mechanism)",
                    "adjudicator": "senior"}) + "\n")
        buf3 = io.StringIO()
        with contextlib.redirect_stdout(buf3):
            rc3 = main(argv)
        check("re-run with rulings file exits 0", rc3 == 0)
        r3 = json.loads((tmp / "gold_metrics.json").read_text())
        g3 = r3["gold"]
        ruled = {json.loads(l)["gold_id"]: json.loads(l)
                 for l in rulings_file.read_text().splitlines()}
        n_unsure_ruled = sum(1 for v in ruled.values() if v["label"] == "unsure")
        check("every queued item ruled -> pending queue empty, ADJUDICATION_PENDING clears",
              g3["n_adjudication"] == 0 and
              not load_jsonl(tmp / "adjudication_queue.jsonl") and
              not any(f["id"] == "ADJUDICATION_PENDING" for f in r3["flags"]))
        check("n_adjudicated provenance recorded (final-unsure counted separately)",
              g3["n_adjudicated"] == len(ruled) - n_unsure_ruled and
              g3["n_adjudicated_unsure"] == n_unsure_ruled,
              f"{g3['n_adjudicated']} applied, {n_unsure_ruled} final-unsure")
        check("adjudicated items enter metrics: consensus grows by exactly the ruled sif/non_sif count",
              g3["n_consensus"] == g["n_consensus"] + g3["n_adjudicated"],
              f"{g['n_consensus']} -> {g3['n_consensus']}")
        check("invariant: consensus + pending + unlabeled + final-unsure == 500",
              g3["n_consensus"] + g3["n_adjudication"] + g3["n_unlabeled"]
              + g3["n_adjudicated_unsure"] == 500)
        stratum_of = {it["gold_id"]: it["source_stratum"] for it in gold}
        real_add = sum(1 for v in ruled.values()
                       if v["label"] != "unsure" and stratum_of[v["gold_id"]] in REAL_STRATA)
        check("real-pooled stratum grows by exactly the ruled real items",
              r3["strata"]["real_pooled"]["n"] == strata["real_pooled"]["n"] + real_add,
              f"{strata['real_pooled']['n']} -> {r3['strata']['real_pooled']['n']} (+{real_add})")
        check("rulings block: n_applied + policy + path recorded",
              r3["adjudication"]["rulings"]["n_applied"] == len(ruled) and
              r3["adjudication"]["rulings"]["path"] == str(rulings_file) and
              "supersede" in r3["adjudication"]["rulings"]["policy"].lower())
        check("kappa untouched by rulings (human-vs-human only)",
              r3["agreement"]["subsets"] == result["agreement"]["subsets"])
        check("markdown reports the applied rulings",
              "rulings applied" in (tmp / "gold_metrics.md").read_text())

        print("== e2e: backward compat (no rulings file = original behavior) ==")
        rulings_file.unlink()
        buf4 = io.StringIO()
        with contextlib.redirect_stdout(buf4):
            rc4 = main(argv)
        g4 = json.loads((tmp / "gold_metrics.json").read_text())["gold"]
        check("rulings file removed -> original numbers + ADJUDICATION_PENDING return",
              rc4 == 0 and g4["n_consensus"] == g["n_consensus"] and
              g4["n_adjudication"] == g["n_adjudication"] and
              g4["n_adjudicated"] == 0 and g4["n_adjudicated_unsure"] == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    after = {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
             for p in artifacts_gold.glob("*") if p.is_file()}
    check("artifacts/gold untouched by the self-check",
          before == after and (artifacts_gold / "labels").exists() == labels_before,
          f"{sorted(after)}")

    if failures:
        print(f"\nSELF-CHECK FAILED: {failures}")
        return 1
    print("\nSELF-CHECK PASS (Wilson units + full e2e on simulated labels in temp dir)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gold", default=str(REPO / "artifacts" / "gold" / "gold_items.jsonl"))
    ap.add_argument("--labels-dir", default=str(REPO / "artifacts" / "gold" / "labels"))
    ap.add_argument("--merged", default=str(REPO / "artifacts" / "gold" / "labels_merged.jsonl"))
    ap.add_argument("--agreement", default=str(REPO / "artifacts" / "gold" / "agreement.json"))
    ap.add_argument("--model-dir", default=str(REPO / "artifacts" / "models" / "masked-v2"))
    ap.add_argument("--scores", default=str(REPO / "artifacts" / "gold" / "model_scores.jsonl"))
    ap.add_argument("--out-json", default=str(REPO / "artifacts" / "gold" / "gold_metrics.json"))
    ap.add_argument("--out-md", default=str(REPO / "artifacts" / "gold" / "gold_metrics.md"))
    ap.add_argument("--adjudication-out",
                    default=str(REPO / "artifacts" / "gold" / "adjudication_queue.jsonl"))
    ap.add_argument("--rulings",
                    default=str(REPO / "artifacts" / "gold" / "labels" / "adjudication.jsonl"),
                    help="adjudication rulings (gold/adjudicate.py output); applied as "
                         "pre-consensus superseding overrides. Absent file = no overrides.")
    ap.add_argument("--threads", type=int, default=4,
                    help="ONNX threads (default 4 — the demo server shares this box)")
    ap.add_argument("--threshold-calibrated", type=float, default=None,
                    help="apply an explicit threshold on the calibrated score scale")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--rescore", action="store_true", help="ignore the score cache")
    ap.add_argument("--self-check", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_check:
        return self_check(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
