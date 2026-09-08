#!/usr/bin/env python3
"""train.py — SIF multi-task ModernBERT training + export (Kaggle, wave 3).

Single-file training script for PS 26165. A Kaggle kernel execs this file
directly (see notebooks/kernel_runner.md). Module level imports are STDLIB
ONLY so `--dry-run` and the local self-check work on boxes without torch;
torch/transformers/numpy/sklearn/onnx/onnxruntime are lazy-imported inside
functions. training/model.py is FROZEN — imported, never modified.

Corpus contract (--corpus-dir must contain train/val/test.jsonl, 1 row/line):
  text field    : "masked_text" preferred when --config masked, else "text";
                  --config unmasked always reads "text". Fallbacks counted.
  SIF label     : "sif" | "sif_potential" | "sif_label" | "label" in {0,1}
  rule labels   : "rules" as (a) list of rule names (synthetic schema),
                  (b) dict {rule: 0/1}, or (c) list of 7 ints in RULES order.
                  Missing -> all-zero (counted).
  everything else (id, site, source, ...) is ignored.

Span weak supervision (D2, keyword anchors):
  Char spans = union of FROZEN keyword-LF regex matches (verbatim from
  spec/label_spec.yaml v1.0.0, sha256 db9462...2f51 — embedded below so the
  kernel needs no repo file) restricted to the rules the row is positive
  for. Char spans are aligned to tokens via the fast tokenizer's
  offset_mapping; overlapping tokens become B-/I- (first of a run = B).
  Drop policy, counted per split:
    no_anchor  — row has >=1 positive rule but its rules' LFs match nothing
                 (e.g. working_at_height is code-only, LF list empty by spec).
    misaligned — anchor chars covered by labeled tokens < 50% of anchor chars
                 (offsets absent/degenerate, or match lands on specials).
  Dropped rows contribute ZERO span loss (span_weight=0); sif/rule losses
  are unaffected. Negatives get all-O span labels (valid supervision).

Loss (ARCHITECTURE v2 / nlp-training-engineer):
  sif  : plain BCE (near-balanced binary).
  rules: per-rule BCEWithLogits(pos_weight = min(neg/pos, 10)). Item spec
         caps at 10 (nlp engineer suggested <=5; stream item overrides).
  span : token BCE, ignore_index=-100, per-row mean, weight 0.3.
  fp16 autocast + GradScaler (T4: fp16 tensor cores, no bf16), sdpa
  attention (frozen in model.py — FA2 impossible on sm_60/sm_75, D1),
  grad clip 1.0, AdamW + linear warmup.

Eval (per epoch, on val):
  SIF AUC + average precision + operating point = max recall s.t.
  precision >= 0.80 (threshold FROZEN on val, saved to thresholds.json);
  per-rule F1 at per-rule F1-optimal thresholds (rules with <50 val
  positives flagged low_support per spec macro-F1 note); span token-F1
  (binary, threshold 0.5, rows with anchors only); temperature scaling
  (single T, LBFGS on val sif logits). metrics.json rewritten each epoch
  plus metrics-ep{N}.json snapshots.

Export (GREEN recipe, runs/run2/day1/export_gate_report.md — D12/D13):
  wrapper returns tuple(sif, rules, span) -> torch.onnx.export(dynamo=True,
  opset_version=18) [legacy exporter BANNED — mis-traces ModernBERT] ->
  fp32 parity gate max|dlogit| <= 1e-4 BEFORE quantize -> strip
  graph.value_info (opset-18 annotation conflict (768)-vs-(1)) ->
  onnxruntime quantize_dynamic(QInt8) -> int8 decision-level parity
  (AUC drop <=0.005, recall@p0.8 drop <=0.01, agreement >=99.5%) ->
  latency benchmark seq128 batch 1/32. dynamo writes fp32 as graph +
  EXTERNAL .onnx.data — manifest hashes both; retrieval must fetch both.

Checkpoints: {out}/ckpt-ep{N}.pt each epoch (model+opt+sched+scaler+rng,
resume-safe via --resume). One config per kernel, <=45 min (F5: MCP kernels
have no Kaggle creds — artifacts retrieved post-completion via MCP).

Usage:
  python3 train.py --corpus-dir /kaggle/input/sif-corpus --config masked \
      --epochs 3 --batch 32 --seq 128 --lr 2e-5 --out /kaggle/working
  python3 train.py --dry-run --corpus-dir data/corpus   # no torch needed
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path

# --- FROZEN spec constants (spec/label_spec.yaml v1.0.0) --------------------
SPEC_VERSION = "1.0.0"
SPEC_SHA256 = "db94628372c076f0d37429cdfe81e3e9d301751d376b163a7fcbc399c73b2f51"

RULES = (
    "line_of_fire", "working_at_height", "driving", "energy_isolation",
    "hot_work", "safe_mechanical_lifting", "confined_space",
)

# keyword_lfs: verbatim from the frozen spec. Only rules with non-empty LF
# lists appear (working_at_height is code-only by spec -> never anchors).
KEYWORD_LFS = {
    "confined_space": [
        r"\bconfined space\b", r"\bmanhole\b", r"\btank entry\b",
        r"\bvessel entry\b",
        r"\benter(?:ed|ing) (?:the |a )?(?:tank|vessel|silo|vault|pit|bin|hopper)\b",
        r"\binside (?:the |a )?(?:tank|vessel|silo)\b",
    ],
    "energy_isolation": [
        r"\block\s?out\b", r"\btag\s?out\b", r"\blockout\b", r"\btagout\b",
        r"\benergized\b", r"\bde-?energiz", r"\bstored energy\b",
        r"\barc flash\b", r"\bunexpectedly (?:started|activated|energized)",
    ],
    "hot_work": [
        r"\bhot work\b", r"\bweld", r"\btorch\b", r"\bgrind",
        r"\bcutting (?:torch|metal|steel)", r"\bspark",
    ],
    "safe_mechanical_lifting": [
        r"\bcrane\b", r"\brigging\b", r"\bhoist", r"\bsuspended load\b",
        r"\boverhead load\b", r"\bsling\b", r"\bdropped load\b",
    ],
    "driving": [r"\bfork\s?lift\b", r"\bskid steer\b"],
    "line_of_fire": [
        r"\bstruck by\b", r"\bcaught (?:in|between)\b", r"\bcrushed\b",
        r"\bpinch", r"\bran over\b",
    ],
}

SPAN_LOSS_WEIGHT = 0.3
POS_WEIGHT_CAP = 10.0
PRECISION_FLOOR = 0.80
MIN_RULE_SUPPORT = 50          # spec: macro-F1 only over rules with >=50 positives
MISALIGN_COVERAGE = 0.5        # anchor-char coverage below this -> drop span loss
SEED = 42

FP32_PARITY_TOL = 1e-4         # D13 tier 1
INT8_AUC_DROP_MAX = 0.005      # D13 tier 2
INT8_RECALL_DROP_MAX = 0.01
INT8_AGREEMENT_MIN = 0.995

ONNX_FP32 = "sif_multitask_fp32.onnx"
ONNX_INT8 = "sif_multitask_int8.onnx"


# --- stdlib-only helpers (dry-run safe) --------------------------------------

def compile_lfs():
    return {rule: [re.compile(p, re.IGNORECASE) for p in pats]
            for rule, pats in KEYWORD_LFS.items()}


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{ln}: bad JSONL row: {e}") from e
    return rows


def normalize_row(row, config, stats):
    """Extract (text, sif, rules[7]) tolerating the concurrent writers'
    schemas (synthetic generator vs OSHA pipeline)."""
    if config == "masked":
        text = row.get("masked_text")
        if text is None:
            text = row.get("text", "")
            stats["masked_fallback_to_text"] += 1
    else:
        text = row.get("text") or row.get("masked_text") or ""
        if "text" not in row:
            stats["unmasked_fallback_to_masked"] += 1
    # BUGFIX (Day-1): final corpus schema uses "sif_label" (see
    # artifacts/corpus/*.jsonl); added to the fallback chain so the frozen
    # label contract accepts it. Docstring contract line updated to match.
    sif = row.get("sif", row.get("sif_potential",
                                 row.get("sif_label", row.get("label"))))
    if sif is None:
        raise ValueError(f"row {row.get('id', '?')}: no sif label")
    rules_raw = row.get("rules", [])
    rv = [0] * len(RULES)
    if isinstance(rules_raw, dict):
        for name, v in rules_raw.items():
            if name in RULES:
                rv[RULES.index(name)] = int(bool(v))
            else:
                stats["unknown_rule_name"] += 1
    elif isinstance(rules_raw, (list, tuple)):
        if len(rules_raw) == len(RULES) and all(
                isinstance(v, (int, float)) for v in rules_raw):
            rv = [int(bool(v)) for v in rules_raw]
        else:
            for name in rules_raw:
                if name in RULES:
                    rv[RULES.index(name)] = 1
                else:
                    stats["unknown_rule_name"] += 1
    elif rules_raw:
        stats["unparseable_rules_field"] += 1
    return str(text), int(bool(sif)), rv


def anchor_spans(text, rules_vec, lfs):
    """Union (merged) of char spans from the LFs of the row's positive rules."""
    spans = []
    for i, rule in enumerate(RULES):
        if not rules_vec[i] or rule not in lfs:
            continue
        for pat in lfs[rule]:
            spans.extend(m.span() for m in pat.finditer(text))
    if not spans:
        return []
    spans.sort()
    merged = [list(spans[0])]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def spans_to_bio(offsets, anchors):
    """Char anchors -> token BIO labels via offset_mapping.

    offsets: list of (start, end) per token; specials are (0, 0) or None.
    Returns (labels, status) with status in {"ok", "misaligned"}. A token is
    inside an anchor if its char interval overlaps the anchor by >=1 char.
    Misaligned = labeled tokens cover < MISALIGN_COVERAGE of anchor chars —
    the caller drops that row's span loss and counts the drop.
    """
    labels = ["O"] * len(offsets)
    anchor_chars = sum(e - s for s, e in anchors)
    covered = 0
    for s, e in anchors:
        for off in offsets:
            if not off:
                continue
            ts, te = off
            if ts == te:                    # special token (0,0)
                continue
            ov = min(te, e) - max(ts, s)
            if ov > 0:
                covered += ov
    inside = []
    for i, off in enumerate(offsets):
        hit = False
        if off:
            ts, te = off
            if ts != te:
                hit = any(min(te, e) - max(ts, s) > 0 for s, e in anchors)
        inside.append(hit)
    for i, hit in enumerate(inside):
        if hit:
            labels[i] = "I" if i > 0 and inside[i - 1] else "B"
    if anchor_chars == 0 or covered / anchor_chars < MISALIGN_COVERAGE:
        return labels, "misaligned"
    return labels, "ok"


def sha256_file(path, _buf=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(_buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def set_seed(seed=SEED):
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


# --- dry run (no torch) -------------------------------------------------------

def dry_run(args):
    lfs = compile_lfs()
    print(f"DRY RUN — train.py (spec v{SPEC_VERSION}, config={args.config})")
    print(f"  corpus-dir : {args.corpus_dir}")
    print(f"  out        : {args.out}")
    print(f"  epochs={args.epochs} batch={args.batch} seq={args.seq} "
          f"lr={args.lr} span_w={SPAN_LOSS_WEIGHT} pos_weight_cap={POS_WEIGHT_CAP}")
    plan_ok = True
    for split in ("train", "val", "test"):
        path = Path(args.corpus_dir) / f"{split}.jsonl"
        if not path.exists():
            print(f"  [{split}] MISSING: {path}")
            plan_ok = plan_ok and split == "test"   # test optional pre-export
            continue
        rows = load_jsonl(path)
        stats = {k: 0 for k in ("masked_fallback_to_text",
                                "unmasked_fallback_to_masked",
                                "unknown_rule_name", "unparseable_rules_field")}
        n_pos = 0
        rule_pos = [0] * len(RULES)
        n_anchor = 0
        n_words = 0
        for row in rows:
            text, sif, rv = normalize_row(row, args.config, stats)
            n_pos += sif
            for i, v in enumerate(rv):
                rule_pos[i] += v
            if rv and anchor_spans(text, rv, lfs):
                n_anchor += 1
            n_words += len(text.split())
        n = len(rows)
        print(f"  [{split}] rows={n} sif_pos={n_pos} "
              f"({100 * n_pos / max(n, 1):.1f}%) mean_words={n_words / max(n, 1):.0f}")
        for i, rule in enumerate(RULES):
            print(f"      {rule:26s} pos={rule_pos[i]:6d} "
                  f"({100 * rule_pos[i] / max(n, 1):5.2f}%)")
        print(f"      rows_with_anchors={n_anchor} "
              f"({100 * n_anchor / max(n, 1):.1f}%) "
              f"-> rest get no_anchor span-drop at tokenize time")
        noisy = {k: v for k, v in stats.items() if v}
        if noisy:
            print(f"      schema fallbacks/warnings: {noisy}")
    steps = 0
    train_path = Path(args.corpus_dir) / "train.jsonl"
    if train_path.exists():
        n = sum(1 for _ in open(train_path, "rb"))
        steps = args.epochs * -(-n // args.batch)
    print(f"  plan: ~{steps} optimizer steps; ckpt-ep1..{args.epochs}.pt; "
          f"metrics.json/epoch; then export {ONNX_FP32} (+ .onnx.data) + "
          f"{ONNX_INT8} + parity + latency + manifest.json")
    print(f"  torch import: DEFERRED (lazy) — dry-run never imports torch")
    print(f"DRY RUN {'OK' if plan_ok else 'INCOMPLETE (missing splits)'}")
    return 0 if plan_ok else 1


# --- dataset (torch lazy) ------------------------------------------------------

def build_features(rows, config, tokenizer, seq, lfs, stats):
    """Tokenize + derive span BIO labels. Mutates stats with drop counts."""
    feats = []
    for row in rows:
        text, sif, rv = normalize_row(row, config, stats)
        enc = tokenizer(text, truncation=True, max_length=seq,
                        return_offsets_mapping=True)
        anchors = anchor_spans(text, rv, lfs)
        if not anchors:
            span_labels = [0.0] * len(enc["input_ids"])
            weight = 0.0
            if any(rv):
                stats["span_drop_no_anchor"] += 1
            else:
                stats["span_negative_row"] += 1
        else:
            bio, status = spans_to_bio(enc["offset_mapping"], anchors)
            span_labels = [1.0 if t in ("B", "I") else 0.0 for t in bio]
            if status == "misaligned":
                weight = 0.0
                stats["span_drop_misaligned"] += 1
            else:
                weight = 1.0
        feats.append({
            "input_ids": enc["input_ids"],
            "attention_mask": enc["attention_mask"],
            "span_labels": span_labels,
            "span_weight": weight,
            "sif": float(sif),
            "rules": [float(v) for v in rv],
        })
    return feats


def make_collate(tokenizer):
    import torch

    def collate(feats):
        batch = tokenizer.pad(
            [{"input_ids": f["input_ids"],
              "attention_mask": f["attention_mask"]} for f in feats],
            padding=True, return_tensors="pt")
        maxlen = batch["input_ids"].shape[1]
        span = torch.full((len(feats), maxlen), -100.0)
        for i, f in enumerate(feats):
            n = min(len(f["span_labels"]), maxlen)
            span[i, :n] = torch.tensor(f["span_labels"][:n])
        batch["span_labels"] = span
        batch["span_weight"] = torch.tensor(
            [f["span_weight"] for f in feats])
        batch["sif"] = torch.tensor([f["sif"] for f in feats])
        batch["rules"] = torch.tensor([f["rules"] for f in feats])
        return batch

    return collate


# --- metrics (numpy/sklearn lazy) ----------------------------------------------

def safe_auc(y, p):
    from sklearn.metrics import roc_auc_score
    if len(set(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, p))


def operating_point(y, p):
    """Max recall subject to precision >= PRECISION_FLOOR; frozen threshold."""
    from sklearn.metrics import precision_recall_curve
    prec, rec, thr = precision_recall_curve(y, p)
    best = None
    for i in range(len(thr)):
        if prec[i + 1] >= PRECISION_FLOOR:
            if best is None or rec[i + 1] > best[1]:
                best = (float(thr[i]), float(rec[i + 1]), float(prec[i + 1]))
    if best is None:                        # floor unreachable
        i = max(range(len(thr)), key=lambda j: prec[j + 1] + rec[j + 1])
        return {"threshold": float(thr[i]), "recall": float(rec[i + 1]),
                "precision": float(prec[i + 1]), "floor_unreachable": True}
    return {"threshold": best[0], "recall": best[1], "precision": best[2],
            "floor_unreachable": False}


def tune_f1_threshold(y, p):
    best_t, best_f = 0.5, 0.0
    for t in [i / 100 for i in range(5, 96)]:
        pred = [1 if v >= t else 0 for v in p]
        tp = sum(1 for a, b in zip(pred, y) if a == 1 and b == 1)
        fp = sum(1 for a, b in zip(pred, y) if a == 1 and b == 0)
        fn = sum(1 for a, b in zip(pred, y) if a == 0 and b == 1)
        f = 2 * tp / max(2 * tp + fp + fn, 1e-9)
        if f > best_f:
            best_f, best_t = f, t
    return best_t, best_f


def evaluate_arrays(sif_logits, rule_logits, span_logits, val_feats):
    import numpy as np
    from sklearn.metrics import average_precision_score

    y_sif = [f["sif"] for f in val_feats]
    p_sif = 1 / (1 + np.exp(-np.asarray(sif_logits)))
    op = operating_point(y_sif, p_sif)
    out = {
        "sif": {
            "auc": safe_auc(y_sif, p_sif),
            "average_precision": float(average_precision_score(y_sif, p_sif)),
            "operating_point": op,
        },
        "rules": {},
        "span": {},
    }
    rule_logits = np.asarray(rule_logits)
    y_rules = np.asarray([f["rules"] for f in val_feats])
    macro_f1, macro_n = 0.0, 0
    for i, rule in enumerate(RULES):
        yr, pr = y_rules[:, i], 1 / (1 + np.exp(-rule_logits[:, i]))
        t, f1 = tune_f1_threshold(yr.tolist(), pr.tolist())
        support = int(yr.sum())
        out["rules"][rule] = {"f1": f1, "threshold": t, "support": support,
                              "low_support": support < MIN_RULE_SUPPORT}
        if support >= MIN_RULE_SUPPORT:
            macro_f1 += f1
            macro_n += 1
    out["rules_macro_f1_min_support"] = (
        macro_f1 / macro_n if macro_n else float("nan"))
    # span token-F1 vs weak anchors (binary @0.5, anchored rows only)
    tp = fp = fn = 0
    for f, logits in zip(val_feats, span_logits):
        if f["span_weight"] == 0.0:
            continue
        n = len(f["span_labels"])
        gold = f["span_labels"][:n]
        pred = (1 / (1 + np.exp(-logits[:n])) >= 0.5)
        for g, pr_ in zip(gold, pred):
            tp += bool(pr_) and g == 1.0
            fp += bool(pr_) and g == 0.0
            fn += (not pr_) and g == 1.0
    out["span"]["token_f1"] = 2 * tp / max(2 * tp + fp + fn, 1e-9)
    out["span"]["tp_fp_fn"] = [tp, fp, fn]
    return out


def fit_temperature(sif_logits, y_sif):
    import torch
    import torch.nn.functional as F

    x = torch.tensor(sif_logits, dtype=torch.float32)
    y = torch.tensor(y_sif, dtype=torch.float32)
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.05, max_iter=100)

    def closure():
        opt.zero_grad()
        loss = F.binary_cross_entropy_with_logits(
            x / log_t.exp().clamp(1e-2, 100.0), y)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.detach().exp().clamp(1e-2, 100.0))


# --- checkpoints ---------------------------------------------------------------

def save_ckpt(path, epoch, model, opt, sched, scaler, best, extra):
    import torch
    ckpt = {
        "epoch": epoch, "model": model.state_dict(),
        "optimizer": opt.state_dict(), "scheduler": sched.state_dict(),
        "scaler": scaler.state_dict(), "best": best,
        "rng": {"python": random.getstate()},
        "extra": extra,
    }
    try:
        import numpy as np
        ckpt["rng"]["numpy"] = np.random.get_state()
    except ImportError:
        pass
    ckpt["rng"]["torch"] = torch.get_rng_state()
    if torch.cuda.is_available():
        ckpt["rng"]["cuda"] = torch.cuda.get_rng_state_all()
    torch.save(ckpt, path)


def maybe_resume(out_dir, model, opt, sched, scaler):
    import torch
    ckpts = sorted(glob.glob(str(Path(out_dir) / "ckpt-ep*.pt")))
    if not ckpts:
        return 0, {}
    path = ckpts[-1]
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["model"])
    opt.load_state_dict(ckpt["optimizer"])
    sched.load_state_dict(ckpt["scheduler"])
    scaler.load_state_dict(ckpt["scaler"])
    random.setstate(ckpt["rng"]["python"])
    torch.set_rng_state(ckpt["rng"]["torch"])
    if "numpy" in ckpt["rng"]:
        import numpy as np
        np.random.set_state(ckpt["rng"]["numpy"])
    if "cuda" in ckpt["rng"] and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(ckpt["rng"]["cuda"])
    print(f"resumed from {path} (epoch {ckpt['epoch']} done)")
    return ckpt["epoch"], ckpt.get("extra", {})


# --- export (GREEN recipe) ------------------------------------------------------

def collect_logits(model, feats, collate, device, batch):
    import torch
    from torch.utils.data import DataLoader
    model.eval()
    sif, rules, span = [], [], []
    loader = DataLoader(feats, batch_size=batch, shuffle=False,
                        collate_fn=collate)
    with torch.no_grad():
        for b in loader:
            out = model(b["input_ids"].to(device),
                        b["attention_mask"].to(device))
            sif.extend(out["sif_logit"].float().cpu().tolist())
            rules.extend(out["rule_logits"].float().cpu().tolist())
            for i in range(len(b["input_ids"])):
                n = int(b["attention_mask"][i].sum())
                span.append(out["span_logits"][i, :n].float().cpu())
    return sif, rules, span


def export_and_gate(model, val_feats, collate, device, args, sif_op,
                    torch_sif_logits, y_sif):
    """fp32 ONNX + value_info strip + quantize_dynamic + two-tier parity +
    latency. Returns dict of gate results + artifact paths."""
    import numpy as np
    import torch
    import torch.nn as nn

    out_dir = Path(args.out)
    results = {"fp32_parity": {}, "int8_parity": {}, "latency_ms": {}}

    class TupleWrapper(nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, input_ids, attention_mask):
            o = self.m(input_ids=input_ids, attention_mask=attention_mask)
            return o["sif_logit"], o["rule_logits"], o["span_logits"]

    wrapper = TupleWrapper(model).eval().to(device)
    ids = torch.zeros(2, args.seq, dtype=torch.long, device=device)
    mask = torch.ones(2, args.seq, dtype=torch.long, device=device)
    fp32_path = out_dir / ONNX_FP32
    dyn = {"input_ids": {0: "batch", 1: "seq"},
           "attention_mask": {0: "batch", 1: "seq"},
           "sif_logit": {0: "batch"}, "rule_logits": {0: "batch"},
           "span_logits": {0: "batch", 1: "seq"}}
    torch.onnx.export(
        wrapper, (ids, mask), str(fp32_path), dynamo=True, opset_version=18,
        input_names=["input_ids", "attention_mask"],
        output_names=["sif_logit", "rule_logits", "span_logits"],
        dynamic_axes=dyn)
    print(f"exported fp32 ONNX (dynamo, opset 18): {fp32_path}")

    import onnx
    import onnxruntime as ort
    from onnxruntime.quantization import QuantType, quantize_dynamic

    # --- tier 1: fp32 parity BEFORE quantize (stage order is load-bearing)
    # BUGFIX (Day-1): collate pads span_logits to each batch's OWN max length,
    # so per-batch arrays cannot be np.concatenate'd (crashed with 87 vs 76 on
    # the masked run). Compare per batch and keep the running max per head.
    n_par = min(100, len(val_feats))
    par_feats = val_feats[:n_par]
    batches = [par_feats[i:i + 32] for i in range(0, n_par, 32)]
    sess = ort.InferenceSession(str(fp32_path),
                                providers=ort.get_available_providers())
    max_d = {"sif_logit": 0.0, "rule_logits": 0.0, "span_logits": 0.0}
    with torch.no_grad():
        for fb in batches:
            b = collate(fb)
            o = model(b["input_ids"].to(device), b["attention_mask"].to(device))
            r = sess.run(None, {"input_ids": b["input_ids"].numpy(),
                                "attention_mask": b["attention_mask"].numpy()})
            for k, v in zip(("sif_logit", "rule_logits", "span_logits"), r):
                d = float(np.abs(o[k].float().cpu().numpy() - v).max())
                max_d[k] = max(max_d[k], d)
    fp32_ok = True
    for k, d in max_d.items():
        results["fp32_parity"][k] = {"max_abs_dlogit": d,
                                     "pass": d <= FP32_PARITY_TOL}
        fp32_ok &= d <= FP32_PARITY_TOL
    print(f"fp32 parity: {results['fp32_parity']}")

    # --- value_info strip (opset-18 annotation conflict), keep external data
    m = onnx.load(str(fp32_path))
    del m.graph.value_info[:]
    onnx.save_model(m, str(fp32_path), save_as_external_data=True,
                    all_tensors_to_one_file=True,
                    location=ONNX_FP32 + ".data")
    int8_path = out_dir / ONNX_INT8
    quantize_dynamic(str(fp32_path), str(int8_path),
                     weight_type=QuantType.QInt8)
    print(f"quantized int8: {int8_path}")

    # --- tier 2: int8 decision-level parity on FULL val at frozen threshold
    i_out = {"sif_logit": []}
    sess8 = ort.InferenceSession(str(int8_path),
                                 providers=["CPUExecutionProvider"])
    for i in range(0, len(val_feats), 32):
        b = collate(val_feats[i:i + 32])
        r = sess8.run(None, {"input_ids": b["input_ids"].numpy(),
                             "attention_mask": b["attention_mask"].numpy()})
        i_out["sif_logit"].append(r[0])
    i_sif = np.concatenate(i_out["sif_logit"])
    t_sif = np.asarray(torch_sif_logits)
    thr = sif_op["threshold"]
    p_t = 1 / (1 + np.exp(-t_sif))
    p_i = 1 / (1 + np.exp(-i_sif))
    y = np.asarray(y_sif)
    agree = float(((p_t >= thr) == (p_i >= thr)).mean())
    auc_drop = safe_auc(y, p_t) - safe_auc(y, p_i)

    def recall_at(p):
        d = p >= thr
        return float((d & (y == 1)).sum() / max((y == 1).sum(), 1))

    rec_drop = recall_at(p_t) - recall_at(p_i)
    results["int8_parity"] = {
        "agreement": agree, "auc_drop": float(auc_drop),
        "recall_at_op_drop": float(rec_drop),
        "pass": (agree >= INT8_AGREEMENT_MIN
                 and auc_drop <= INT8_AUC_DROP_MAX
                 and rec_drop <= INT8_RECALL_DROP_MAX)}
    print(f"int8 parity: {results['int8_parity']}")

    # --- latency: seq128, batch 1 and 32, per artifact/provider
    for name, path, providers in (
            ("fp32", fp32_path, ort.get_available_providers()),
            ("int8", int8_path, ["CPUExecutionProvider"])):
        s = ort.InferenceSession(str(path), providers=providers)
        prov = s.get_providers()[0]
        for bs in (1, 32):
            inp = {"input_ids": np.random.randint(0, 30000, (bs, args.seq)),
                   "attention_mask": np.ones((bs, args.seq), dtype=np.int64)}
            inp = {k: v.astype(np.int64) for k, v in inp.items()}
            for _ in range(10):
                s.run(None, inp)
            iters = 50 if bs == 1 else 20
            t0 = time.perf_counter()
            for _ in range(iters):
                s.run(None, inp)
            dt = (time.perf_counter() - t0) / iters * 1000
            results["latency_ms"][f"{name}/{prov}/batch{bs}"] = round(dt, 2)
    print(f"latency: {results['latency_ms']}")
    results["pass"] = bool(fp32_ok and results["int8_parity"]["pass"])
    return results


# --- main -----------------------------------------------------------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--corpus-dir", required=True,
                   help="dir with train/val/test.jsonl")
    p.add_argument("--config", choices=("masked", "unmasked"),
                   default="masked")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--seq", type=int, default=128)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--out", default="/kaggle/working")
    p.add_argument("--resume", action="store_true",
                   help="resume from newest ckpt-ep*.pt in --out")
    p.add_argument("--max-rows", type=int, default=0,
                   help="cap rows per split (smoke tests)")
    p.add_argument("--skip-export", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="print execution plan; never imports torch")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.dry_run:
        return dry_run(args)

    import numpy as np
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoTokenizer, get_linear_schedule_with_warmup

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import BACKBONE, build_model            # FROZEN module

    set_seed()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        print("WARNING: no CUDA — CPU run (smoke only)")
    else:
        cap = torch.cuda.get_device_capability(0)
        print(f"device: {torch.cuda.get_device_name(0)} sm_{cap[0]}{cap[1]}")
        assert cap < (8, 0), "sdpa pinned for sm_60/75; re-review on newer arch"

    lfs = compile_lfs()
    tokenizer = AutoTokenizer.from_pretrained(BACKBONE)
    splits = {}
    stats = {}
    for split in ("train", "val"):
        rows = load_jsonl(Path(args.corpus_dir) / f"{split}.jsonl")
        if args.max_rows:
            rows = rows[: args.max_rows]
        st = {k: 0 for k in (
            "masked_fallback_to_text", "unmasked_fallback_to_masked",
            "unknown_rule_name", "unparseable_rules_field",
            "span_drop_no_anchor", "span_drop_misaligned",
            "span_negative_row")}
        t0 = time.time()
        splits[split] = build_features(rows, args.config, tokenizer,
                                       args.seq, lfs, st)
        stats[split] = st
        print(f"[{split}] {len(rows)} rows featurized in "
              f"{time.time() - t0:.1f}s; span drops: no_anchor="
              f"{st['span_drop_no_anchor']} misaligned="
              f"{st['span_drop_misaligned']}")

    train_feats, val_feats = splits["train"], splits["val"]

    # per-rule pos_weight, capped (item spec: cap 10)
    y_rules = np.asarray([f["rules"] for f in train_feats])
    pos = y_rules.sum(0)
    neg = len(train_feats) - pos
    pw = np.minimum(np.where(pos > 0, neg / np.maximum(pos, 1), 1.0),
                    POS_WEIGHT_CAP)
    pos_weight = torch.tensor(pw, dtype=torch.float32, device=device)
    print(f"rule pos_weight (cap {POS_WEIGHT_CAP}): "
          f"{dict(zip(RULES, pw.round(2).tolist()))}")

    model = build_model().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr,
                            weight_decay=0.01)
    collate = make_collate(tokenizer)
    loader = DataLoader(train_feats, batch_size=args.batch, shuffle=True,
                        collate_fn=collate, drop_last=False)
    total_steps = len(loader) * args.epochs
    sched = get_linear_schedule_with_warmup(
        opt, int(0.06 * total_steps), total_steps)
    use_amp = device == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    start_epoch, extra = (maybe_resume(out_dir, model, opt, sched, scaler)
                          if args.resume else (0, {}))
    history = extra.get("history", [])
    best_auc = extra.get("best_auc", -1.0)

    import torch.nn.functional as F
    rule_loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    metrics = sif_logits = y_sif = None
    for epoch in range(start_epoch + 1, args.epochs + 1):
        model.train()
        t0, run = time.time(), 0.0
        for step, b in enumerate(loader, 1):
            ids = b["input_ids"].to(device)
            am = b["attention_mask"].to(device)
            with torch.autocast("cuda", dtype=torch.float16, enabled=use_amp):
                o = model(ids, am)
                l_sif = F.binary_cross_entropy_with_logits(
                    o["sif_logit"], b["sif"].to(device))
                l_rule = rule_loss_fn(o["rule_logits"],
                                      b["rules"].to(device))
                sl = b["span_labels"].to(device)
                valid = (sl >= 0) & am.bool()
                tok = F.binary_cross_entropy_with_logits(
                    o["span_logits"], sl.clamp(min=0), reduction="none")
                per_row = (tok * valid).sum(1) / valid.sum(1).clamp(min=1)
                sw = b["span_weight"].to(device)
                l_span = (per_row * sw).sum() / sw.sum().clamp(min=1)
                loss = l_sif + l_rule + SPAN_LOSS_WEIGHT * l_span
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            opt.zero_grad(set_to_none=True)
            run += loss.item()
            if step % 100 == 0:
                print(f"  ep{epoch} step {step}/{len(loader)} "
                      f"loss {run / step:.4f}")

        sif_logits, rule_logits, span_logits = collect_logits(
            model, val_feats, collate, device, args.batch)
        y_sif = [f["sif"] for f in val_feats]
        metrics = evaluate_arrays(sif_logits, rule_logits, span_logits,
                                  val_feats)
        temp = fit_temperature(sif_logits, y_sif)
        metrics["temperature"] = temp
        metrics["epoch"] = epoch
        metrics["train_loss_mean"] = run / max(len(loader), 1)
        metrics["span_drops"] = {
            s: {k: stats[s][k] for k in ("span_drop_no_anchor",
                                         "span_drop_misaligned")}
            for s in stats}
        metrics["epoch_seconds"] = round(time.time() - t0, 1)
        history.append(metrics)
        (out_dir / f"metrics-ep{epoch}.json").write_text(
            json.dumps(metrics, indent=1))
        (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=1))
        print(f"[ep{epoch}] sif_auc={metrics['sif']['auc']:.4f} "
              f"op(r@p>={PRECISION_FLOOR})={metrics['sif']['operating_point']} "
              f"macroF1={metrics['rules_macro_f1_min_support']:.4f} "
              f"spanF1={metrics['span']['token_f1']:.4f} T={temp:.3f}")

        auc = metrics["sif"]["auc"]
        if auc == auc:                       # nan guard
            best_auc = max(best_auc, auc)
        save_ckpt(out_dir / f"ckpt-ep{epoch}.pt", epoch, model, opt, sched,
                  scaler, best_auc, {"history": history, "best_auc": best_auc})
        print(f"  checkpoint: {out_dir}/ckpt-ep{epoch}.pt")

    # --- final: freeze thresholds, export, gate, manifest
    if metrics is None:
        # BUGFIX (Day-1): --resume with every epoch already complete (the
        # export-retry path) used to crash on undefined metrics; recompute
        # the val eval so thresholds/export/gate can proceed.
        sif_logits, rule_logits, span_logits = collect_logits(
            model, val_feats, collate, device, args.batch)
        y_sif = [f["sif"] for f in val_feats]
        metrics = evaluate_arrays(sif_logits, rule_logits, span_logits,
                                  val_feats)
        metrics["temperature"] = fit_temperature(sif_logits, y_sif)
        metrics["epoch"] = start_epoch
        print(f"[resume] no epochs left; recomputed val eval "
              f"(auc={metrics['sif']['auc']:.4f})")
    sif_op = metrics["sif"]["operating_point"]
    thresholds = {
        "config": args.config, "spec_version": SPEC_VERSION,
        "spec_sha256": SPEC_SHA256,
        "sif_threshold": sif_op["threshold"],
        "sif_operating_point": sif_op,
        "temperature": metrics["temperature"],
        "rule_thresholds": {r: metrics["rules"][r]["threshold"]
                            for r in RULES},
        "rule_pos_weight": dict(zip(RULES, pw.tolist())),
    }
    (out_dir / "thresholds.json").write_text(json.dumps(thresholds, indent=1))

    gate = {"skipped": True}
    if not args.skip_export:
        gate = export_and_gate(model, val_feats, collate, device, args,
                               sif_op, sif_logits, y_sif)
        (out_dir / "export_gate.json").write_text(json.dumps(gate, indent=1))

    manifest = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": args.config, "spec_sha256": SPEC_SHA256,
        "backbone": BACKBONE, "seq": args.seq, "epochs": args.epochs,
        "export_gate_pass": gate.get("pass"),
        "files": {},
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["files"][path.name] = {
                "sha256": sha256_file(path), "bytes": path.stat().st_size}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"manifest: {out_dir}/manifest.json "
          f"({len(manifest['files'])} files, export_gate_pass="
          f"{manifest['export_gate_pass']})")
    return 0 if gate.get("skipped") or gate.get("pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
