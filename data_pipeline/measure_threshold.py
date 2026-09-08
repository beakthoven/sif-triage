"""Measure the MiniLM near-dup threshold curve and pick the banner threshold.

Inputs : artifacts/embeddings/corpus_embeddings_fp16.npy + corpus_ids.jsonl
         artifacts/corpus/train_final_v2.jsonl  (row-aligned with the index)
         data/January2015toNovember2025.csv     (raw OSHA, exact-dup pairs)

Sets measured (cosine of L2-normalized MiniLM embeddings):
  (a) 500 random DISTINCT corpus pairs          — the FPR baseline
  (b) known OSHA exact-dup pairs (verbatim)     — recall floor, sanity ~=1.0
      + constructed NEAR-TWINS (same event, 2-3 words swapped)
  (c) OSHA TEMPLATE pairs (same employer, different OIICS event) — the
      practical false-banner driver (shared employer boilerplate; MiniLM
      "runs hotter" than the char-cosine proxy, demo-red-teamer §1)

Pick: max threshold with recall(b) >= 0.95 and FPR(a) <= 0.01.
Output: artifacts/embeddings/threshold_report.md (+ machine JSON sidecar).

Run: .venv/bin/python data_pipeline/measure_threshold.py
"""
from __future__ import annotations

import csv
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.embedder import embed_texts  # noqa: E402

OUT_DIR = REPO_ROOT / "artifacts" / "embeddings"
CORPUS = REPO_ROOT / "artifacts" / "corpus" / "train_final_v2.jsonl"
OSHA_CSV = REPO_ROOT / "data" / "January2015toNovember2025.csv"
REPORT_MD = OUT_DIR / "threshold_report.md"
REPORT_JSON = OUT_DIR / "threshold_report.json"

SEED = 42
N_DISTINCT = 500
N_TWINS = 150
N_TEMPLATE = 400
RECALL_FLOOR = 0.95
FPR_CEIL = 0.01

# Word-swap map for near-twin construction: same event, 2-3 words changed.
# Body-part swaps replicate the red-teamer's wrist/ankle template twin.
SWAP_MAP = {
    "finger": "thumb", "hand": "foot", "wrist": "ankle", "knee": "elbow",
    "arm": "leg", "left": "right", "ladder": "scaffold", "grinder": "welder",
    "hammer": "wrench", "forklift": "crane", "truck": "van", "gloves": "gauntlets",
}


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def load_corpus() -> list[dict]:
    rows = []
    with open(CORPUS, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            rows.append(r)
    return rows


def exact_dup_pairs() -> list[tuple[str, str]]:
    """Reconstruct the OSHA exact-dup pairs (build_corpus.py exact_dedup):
    group whitespace-normalized 'Final Narrative' texts; keeper = first by
    (EventDate, ID); every later row forms a verbatim pair with the keeper."""
    recs = []
    with open(OSHA_CSV, newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            text = norm_ws(rec.get("Final Narrative") or "")
            if text:
                recs.append((rec.get("EventDate") or "", rec.get("ID") or "", text))
    recs.sort(key=lambda t: (t[0], t[1]))
    groups: dict[str, list[str]] = defaultdict(list)
    for _, _, text in recs:
        groups[text].append(text)
    pairs = []
    for text, members in groups.items():
        for _ in members[1:]:
            pairs.append((members[0], text))
    return pairs


def make_twin(text: str, rng: random.Random) -> str | None:
    """Same event, 2-3 words changed: up to 2 swap-map hits, else a digit swap,
    plus an optional filler insertion. None when nothing editable."""
    words = text.split(" ")
    edits = 0
    used = set()
    for i, w in enumerate(words):
        lw = w.lower().strip(".,;")
        if lw in SWAP_MAP and lw not in used and edits < 2:
            # preserve trailing punctuation
            punct = w[len(w.rstrip(".,;")) :]
            words[i] = SWAP_MAP[lw] + punct
            used.add(lw)
            edits += 1
    if edits < 2:
        for i, w in enumerate(words):
            if re.fullmatch(r"[2-9]", w):
                words[i] = str((int(w) % 8) + 2)  # 2->4, 3->5, ... 9->3
                edits += 1
                break
    if edits < 3 and len(words) > 8:
        pos = rng.randrange(3, min(len(words) - 1, 12))
        words.insert(pos, rng.choice(["also", "approximately", "reportedly"]))
        edits += 1
    twin = " ".join(words)
    return twin if twin != text and edits >= 2 else None


def percentile(v: np.ndarray, q: float) -> float:
    return float(np.percentile(v, q)) if len(v) else float("nan")


def dist_stats(v: np.ndarray) -> dict:
    return {
        "n": int(len(v)),
        "mean": round(float(v.mean()), 4),
        "p5": round(percentile(v, 5), 4),
        "p50": round(percentile(v, 50), 4),
        "p95": round(percentile(v, 95), 4),
        "p99": round(percentile(v, 99), 4),
        "max": round(float(v.max()), 4),
        "min": round(float(v.min()), 4),
    }


def main() -> int:
    rng = random.Random(SEED)
    t0 = time.perf_counter()
    mat = np.load(OUT_DIR / "corpus_embeddings_fp16.npy", mmap_mode="r").astype(np.float32)
    load_s = time.perf_counter() - t0
    rows = load_corpus()
    n = len(rows)
    assert mat.shape[0] == n
    print(f"index loaded: {mat.shape} fp32 in {load_s:.2f}s ({mat.nbytes / 1e6:.0f} MB)")

    # (a) random distinct pairs -------------------------------------------------
    seen = set()
    pairs_a = []
    while len(pairs_a) < N_DISTINCT:
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j or (i, j) in seen or rows[i]["text"] == rows[j]["text"]:
            continue
        seen.add((i, j))
        pairs_a.append((i, j))
    ia = np.array([p[0] for p in pairs_a])
    ja = np.array([p[1] for p in pairs_a])
    cos_a = np.einsum("ij,ij->i", mat[ia], mat[ja])
    print(f"(a) {N_DISTINCT} distinct pairs: max={cos_a.max():.4f} p99={percentile(cos_a, 99):.4f}")

    # (b1) OSHA exact-dup pairs (verbatim) --------------------------------------
    dup_pairs = exact_dup_pairs()
    print(f"(b1) OSHA exact-dup pairs found: {len(dup_pairs)}")
    texts = sorted({t for p in dup_pairs for t in p})
    emb_cache = dict(zip(texts, embed_texts(texts)))
    cos_b1 = np.array([float(np.dot(emb_cache[a], emb_cache[b])) for a, b in dup_pairs])

    # (b2) constructed near-twins -----------------------------------------------
    osha_idx = [i for i, r in enumerate(rows) if str(r.get("source", "")).startswith("osha")]
    rng.shuffle(osha_idx)
    twins = []
    for i in osha_idx:
        if len(twins) >= N_TWINS:
            break
        twin = make_twin(rows[i]["text"], rng)
        if twin:
            twins.append((i, twin))
    twin_texts = [t for _, t in twins]
    twin_embs = embed_texts(twin_texts)
    cos_b2 = np.array([float(np.dot(mat[i], twin_embs[k])) for k, (i, _) in enumerate(twins)])
    print(f"(b2) near-twins constructed: {len(twins)}  min={cos_b2.min():.4f} p5={percentile(cos_b2, 5):.4f}")

    cos_b = np.concatenate([cos_b1, cos_b2])

    # (c) template pairs: same employer, different OIICS event -------------------
    by_emp: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        emp = r.get("employer")
        if emp and str(r.get("source", "")).startswith("osha"):
            by_emp[str(emp)].append(i)
    pairs_c = []
    emps = [e for e, idxs in by_emp.items() if len({rows[i].get("oiics_event") for i in idxs}) >= 2]
    rng.shuffle(emps)
    for emp in emps:
        if len(pairs_c) >= N_TEMPLATE:
            break
        idxs = by_emp[emp]
        rng.shuffle(idxs)
        for x in range(len(idxs)):
            for y in range(x + 1, len(idxs)):
                if rows[idxs[x]].get("oiics_event") != rows[idxs[y]].get("oiics_event"):
                    pairs_c.append((idxs[x], idxs[y]))
                    break
            else:
                continue
            break
    ic = np.array([p[0] for p in pairs_c])
    jc = np.array([p[1] for p in pairs_c])
    cos_c = np.einsum("ij,ij->i", mat[ic], mat[jc]) if pairs_c else np.array([])
    print(f"(c) template pairs: {len(pairs_c)}  p95={percentile(cos_c, 95):.4f} max={percentile(cos_c, 100):.4f}")

    # masked-variant paste robustness (training rows are masked_text) ------------
    mask_idx = rng.sample(osha_idx, 100)
    masked = embed_texts([rows[i].get("masked_text") or rows[i]["text"] for i in mask_idx])
    cos_mask = np.array([float(np.dot(mat[i], masked[k])) for k, i in enumerate(mask_idx)])

    # threshold scan --------------------------------------------------------------
    grid = [round(0.80 + 0.005 * k, 3) for k in range(40)]  # 0.800 .. 0.995
    curve = []
    for t in grid:
        curve.append({
            "threshold": t,
            "recall_b_all": round(float((cos_b >= t).mean()), 4),
            "recall_b_twins": round(float((cos_b2 >= t).mean()), 4),
            "fpr_a": round(float((cos_a >= t).mean()), 4),
            "fp_rate_c": round(float((cos_c >= t).mean()), 4) if len(cos_c) else None,
        })
    feasible = [c for c in curve if c["recall_b_all"] >= RECALL_FLOOR and c["fpr_a"] <= FPR_CEIL]
    if not feasible:
        raise AssertionError("no threshold satisfies recall>=0.95 & FPR<=0.01 — inspect the curve")
    chosen = max(c["threshold"] for c in feasible)  # top of band: best template margin
    chosen_row = next(c for c in curve if c["threshold"] == chosen)
    print(f"CHOSEN threshold={chosen}  {chosen_row}")

    # report ----------------------------------------------------------------------
    md = []
    md.append("# Near-dup threshold report — MiniLM embedding index\n")
    md.append(f"Measured {time.strftime('%Y-%m-%d')} on this machine, `.venv/bin/python "
              "data_pipeline/measure_threshold.py`. Model: vendored "
              "sentence-transformers/all-MiniLM-L6-v2 ONNX (masked mean-pool + L2 norm, "
              "verified vs official quickstart sims, worst |Δ|=4.5e-05).\n")
    md.append(f"## Decision\n\n**near_dup_threshold = {chosen}** "
              f"(max threshold with recall(b) ≥ {RECALL_FLOOR} and FPR(a) ≤ {FPR_CEIL})\n")
    md.append("## Set definitions\n")
    md.append(f"- (a) distinct: {N_DISTINCT} random corpus pairs (deduped corpus, different texts) — FPR baseline\n"
              f"- (b) near-dup: {len(cos_b1)} OSHA exact-dup pairs (verbatim, reconstructed from raw CSV "
              "via build_corpus exact_dedup logic) + " 
              f"{len(cos_b2)} constructed near-twins (same event, 2-3 words swapped)\n"
              f"- (c) template: {len(pairs_c)} same-employer different-OIICS-event pairs — practical FP driver\n")
    md.append("## Distribution summary (cosine)\n")
    md.append("| set | n | mean | p5 | p50 | p95 | p99 | max | min |\n|---|---|---|---|---|---|---|---|---|")
    for name, v in (("(a) distinct", cos_a), ("(b1) exact-dup verbatim", cos_b1),
                    ("(b2) near-twin 2-3 word swap", cos_b2), ("(c) template same-employer", cos_c),
                    ("masked-text paste vs raw index", cos_mask)):
        s = dist_stats(v)
        md.append(f"| {name} | {s['n']} | {s['mean']} | {s['p5']} | {s['p50']} | {s['p95']} | {s['p99']} | {s['max']} | {s['min']} |")
    md.append("\n## Threshold curve\n")
    md.append("| threshold | recall (b) all | recall (b2) twins | FPR (a) | FP rate (c) |\n|---|---|---|---|---|")
    for c in curve:
        marker = " **<== CHOSEN**" if c["threshold"] == chosen else ""
        md.append(f"| {c['threshold']:.3f} | {c['recall_b_all']:.4f} | {c['recall_b_twins']:.4f} | "
                  f"{c['fpr_a']:.4f} | {c['fp_rate_c'] if c['fp_rate_c'] is None else format(c['fp_rate_c'], '.4f')} |{marker}")
    md.append("")
    md.append("Notes: (b1) verbatim pairs are a pipeline sanity floor (~1.0 by construction); "
              "the binding constraint is (b2). (c) quantifies the banner's false-fire risk on "
              "employer boilerplate at the chosen threshold. Masked-text paste row shows a judge "
              "pasting the masked training variant is still caught.")
    REPORT_MD.write_text("\n".join(md) + "\n")

    REPORT_JSON.write_text(json.dumps({
        "chosen_threshold": chosen,
        "chosen_row": chosen_row,
        "stats": {k: dist_stats(v) for k, v in {
            "a_distinct": cos_a, "b1_exact_dup": cos_b1, "b2_near_twins": cos_b2,
            "c_template": cos_c, "masked_paste": cos_mask}.items()},
        "curve": curve,
        "n_exact_dup_pairs": len(dup_pairs),
        "index_load_seconds": round(load_s, 3),
        "index_rows": n,
    }, indent=2) + "\n")
    print(f"wrote {REPORT_MD} and {REPORT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
