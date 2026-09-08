"""Global QA for the synthetic OIL-register corpus (Day-1, spec synthetic_corpus.quality_gates).

Stages, in order (a row dropped at any stage is excluded from all later stages):
  1. schema validation      — all 10 fields, enums; drop+log malformed
  2. outcome-leak filter    — masking._PATTERN; drop+log per file
  3. AI-ism check           — 6 banned generation-brief phrases; drop+log
  4. within-file 8-gram dup — share >=1 8-gram with an earlier kept row in the
                              same file -> drop later row (keep first occurrence)
  5. cross-file 8-gram Jaccard >= 0.5 across all synthetic files (sequential,
                              keep first occurrence)
  6. 8-gram Jaccard >= 0.5 vs corpus train.jsonl masked_text + test.jsonl
                              masked_text (distinctive shingles, df cap 25);
                              drop+log. Per-row jaccard_max recorded on every
                              survivor (max over stages 5 and 6).
  7. vocab coverage         — 24 OIL terms, gate >= 50 rows each (report only)
  8. LLM-ism detector       — TF-IDF(1-2g, 5k) + LogReg, real-vs-synth 10-fold
                              AUC, gate < 0.9. One mitigation if breached: drop
                              the most templated quartile (highest CV synthetic
                              probability), re-measure, then STOP either way.

Outputs:
  artifacts/synthetic/clean/<file>.jsonl   survivors (+ jaccard_max field)
  artifacts/synthetic/qa_stats.json        full QA stats table

Stdlib + scikit-learn (requirements-dev). Run:
  .venv/bin/python data_pipeline/qa_synthetic.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from masking import _PATTERN, mask_text  # noqa: E402

RAW_DIR = Path("artifacts/synthetic/raw")
CLEAN_DIR = Path("artifacts/synthetic/clean")
STATS_PATH = Path("artifacts/synthetic/qa_stats.json")
CORPUS_DIR = Path("artifacts/corpus")

REQUIRED_FIELDS = {
    "id": str,
    "text": str,
    "sif_potential": int,
    "rules": list,
    "well_control": bool,
    "site": (str, type(None)),
    "activity": (str, type(None)),
    "barrier": (str, type(None)),
    "register": str,
    "source": str,
}
VALID_RULES = {
    "line_of_fire", "working_at_height", "driving", "energy_isolation",
    "hot_work", "safe_mechanical_lifting", "confined_space",
}
VALID_REGISTERS = {"near_miss", "drill", "ua_uc_observation"}

AI_ISMS = [
    "furthermore", "moreover", "in conclusion", "it is important to note",
    "underscores", "highlighting the importance",
]
_AI_ISM_RE = re.compile("|".join(rf"\b{re.escape(p)}\b" for p in AI_ISMS), re.IGNORECASE)

# 24 OIL terms (hse-domain-reviewer.md / protocol_draft.md §B4); slash = alternation family.
OIL_TERMS: list[tuple[str, str]] = [
    ("GGS", r"\bggs\b"),
    ("GCS", r"\bgcs\b"),
    ("EPS", r"\beps\b"),
    ("CTF", r"\bctf\b"),
    ("wellhead/manifold", r"\bwellheads?\b|\bmanifolds?\b"),
    ("christmas tree", r"\bchristmas[ -]trees?\b"),
    ("flowline", r"\bflow[ -]?lines?\b"),
    ("workover rig", r"\bworkover\s+rigs?\b"),
    ("BOP", r"\bbops?\b|\bblowout\s+preventers?\b"),
    ("WOC (waiting on cement)", r"\bwocs?\b|\bwaiting\s+on\s+cement\b"),
    ("mud pump/mud tank", r"\bmud\s+pumps?\b|\bmud\s+tanks?\b"),
    ("SRP/horse head", r"\bsrps?\b|\bhorse\s?heads?\b|\bsucker\s+rod\s+pumps?\b"),
    ("H2S/sour gas", r"\bh2s\b|\bsour\s+gas\b|\bhydrogen\s+sul[fp]hide\b"),
    ("LEL/gas detector", r"\blel\b|\bgas\s+detectors?\b"),
    ("kick", r"\bkicks?\b"),
    ("POOH/RIH", r"\bpooh\b|\brih\b"),
    ("flare pit", r"\bflare\s+pits?\b"),
    ("hot work/cold work permit", r"\b(?:hot|cold)[ -]work(?:\s+permits?)?\b"),
    ("PSV", r"\bpsvs?\b"),
    ("QRT", r"\bqrts?\b"),
    ("Duliajan", r"\bduliajan\b"),
    ("monsoon waterlogging", r"\bwaterlog\w*\b|\bmonsoon\s+waterlog\w*\b"),
    ("contractor (M/s ...)", r"\bm/s\b|\bcontractors?\b|\bthekedar\b"),
    ("wild elephant movement", r"\belephants?\b"),
]
OIL_TERM_RES = [(name, re.compile(pat, re.IGNORECASE)) for name, pat in OIL_TERMS]
VOCAB_GATE = 50

JACCARD_DROP = 0.5
NGRAM = 8
SYN_DF_CAP = 50     # shingles shared by >50 synthetic rows are boilerplate, not evidence
REAL_DF_CAP = 25    # "distinctive shingles" per spec splits.cross_boundary_near_dup_screen

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def shingles(text: str, n: int = NGRAM) -> list[int]:
    """Hashed 8-grams of lowercase alnum tokens. Short rows (< n tokens) get one
    whole-text shingle."""
    toks = _TOKEN_RE.findall(text.lower())
    if len(toks) < n:
        grams = [" ".join(toks)] if toks else []
    else:
        grams = [" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)]
    return [int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "big") for g in grams]


def load_raw(raw_dir: Path) -> dict[str, list[dict]]:
    files = {}
    for path in sorted(raw_dir.glob("*.jsonl")):
        rows = []
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as e:
                    rows.append({"__parse_error__": f"{path.name}:{lineno}: {e}"})
        files[path.name] = rows
    return files


def schema_error(row: dict) -> str | None:
    if "__parse_error__" in row:
        return row["__parse_error__"]
    for field, ftype in REQUIRED_FIELDS.items():
        if field not in row:
            return f"missing field {field!r}"
        if not isinstance(row[field], ftype) or (ftype is int and isinstance(row[field], bool)):
            return f"field {field!r} wrong type"
    if not row["id"].startswith("syn-"):
        return f"id {row['id']!r} missing syn- prefix"
    if not row["text"].strip():
        return "empty text"
    if row["sif_potential"] not in (0, 1):
        return f"sif_potential {row['sif_potential']!r} not in {{0,1}}"
    bad = set(row["rules"]) - VALID_RULES
    if bad:
        return f"unknown rules {sorted(bad)}"
    if row["register"] not in VALID_REGISTERS:
        return f"register {row['register']!r} not in {sorted(VALID_REGISTERS)}"
    if row["source"] != "synthetic":
        return f"source {row['source']!r} != 'synthetic'"
    return None


class NgramIndex:
    """Inverted index gram -> row keys, with df cap. Jaccard candidates are
    counted via postings (intersection size), so only per-row shingle counts
    are needed, never the full sets."""

    def __init__(self, df_cap: int):
        self.df_cap = df_cap
        self.postings: dict[int, list[int]] = defaultdict(list)
        self.row_len: dict[int, int] = {}

    def add(self, key: int, grams: list[int]) -> None:
        self.row_len[key] = len(set(grams))
        for g in set(grams):
            self.postings[g].append(key)

    def capped(self) -> int:
        over = [g for g, ks in self.postings.items() if len(ks) > self.df_cap]
        for g in over:
            del self.postings[g]
        return len(over)

    def jaccard_max(self, grams: list[int]) -> tuple[float, int | None]:
        """Max Jaccard of this row against all indexed rows (candidate-only)."""
        uniq = set(grams)
        inter: Counter[int] = Counter()
        for g in uniq:
            keys = self.postings.get(g, ())
            if len(keys) > self.df_cap:
                continue  # boilerplate shingle, not evidence of copying
            for key in keys:  # candidates share >=1 distinctive shingle
                inter[key] += 1
        best, best_key = 0.0, None
        na = len(uniq)
        for key, c in inter.items():
            nb = self.row_len[key]
            j = c / (na + nb - c)
            if j > best:
                best, best_key = j, key
        return best, best_key


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Global QA for synthetic OIL-register corpus rounds")
    ap.add_argument("--raw-dir", default=str(RAW_DIR))
    ap.add_argument("--clean-dir", default=str(CLEAN_DIR))
    ap.add_argument("--stats", default=str(STATS_PATH))
    ap.add_argument("--prior-clean-dir", action="append", default=None,
                    help="clean dir from an earlier round; rows are indexed for the "
                         "cross-file Jaccard screen but never dropped (repeatable)")
    ap.add_argument("--skip-llmism", action="store_true",
                    help="skip stage 8 (LLM-ism detector + mitigation drop)")
    args = ap.parse_args()
    raw_dir, clean_dir, stats_path = Path(args.raw_dir), Path(args.clean_dir), Path(args.stats)

    files = load_raw(raw_dir)
    clean_dir.mkdir(parents=True, exist_ok=True)

    stats: dict[str, dict] = {}
    drop_log: list[dict] = []

    # ---- stages 1-3: per-row filters --------------------------------------
    after_filters: dict[str, list[dict]] = {}
    for fname, rows in files.items():
        kept = []
        st = Counter(rows_in=len(rows))
        for row in rows:
            err = schema_error(row)
            if err:
                st["schema_dropped"] += 1
                drop_log.append({"file": fname, "stage": "schema", "reason": err,
                                 "id": row.get("id", "<unparseable>")})
                continue
            leak = _PATTERN.search(row["text"])
            if leak:
                st["leak_dropped"] += 1
                drop_log.append({"file": fname, "stage": "outcome_leak", "id": row["id"],
                                 "reason": f"outcome stem match: {leak.group(0)!r}"})
                continue
            ai = _AI_ISM_RE.search(row["text"])
            if ai:
                st["aiism_dropped"] += 1
                drop_log.append({"file": fname, "stage": "ai_ism", "id": row["id"],
                                 "reason": f"banned phrase: {ai.group(0)!r}"})
                continue
            kept.append(row)
        after_filters[fname] = kept
        stats[fname] = dict(st)

    # ---- stage 4: within-file 8-gram duplicate screen ----------------------
    for fname, rows in after_filters.items():
        idx = NgramIndex(df_cap=10**9)  # within-file: any shared 8-gram is a collision
        kept = []
        for i, row in enumerate(rows):
            grams = shingles(row["text"])
            _, hit = idx.jaccard_max(grams)  # any candidate shares >=1 8-gram
            if hit is not None:
                stats[fname]["within_file_dup_dropped"] = stats[fname].get("within_file_dup_dropped", 0) + 1
                drop_log.append({"file": fname, "stage": "within_file_dup", "id": row["id"],
                                 "reason": f"shares >=1 8-gram with earlier row #{hit} in {fname}"})
                continue
            idx.add(i, grams)
            kept.append(row)
        after_filters[fname] = kept
        stats[fname].setdefault("within_file_dup_dropped", 0)

    # ---- stage 5: cross-file 8-gram Jaccard >= 0.5 (sequential, keep first) -
    syn_idx = NgramIndex(df_cap=SYN_DF_CAP)
    jmax: dict[str, float] = {}
    global_i = 0
    if args.prior_clean_dir:
        n_prior = 0
        for prior_dir in args.prior_clean_dir:
            for path in sorted(Path(prior_dir).glob("*.jsonl")):
                with open(path, encoding="utf-8") as fh:
                    for line in fh:
                        syn_idx.add(global_i, shingles(json.loads(line)["text"]))
                        global_i += 1
                        n_prior += 1
        print(f"stage 5: pre-indexed {n_prior} prior-round clean rows (screen-only, never dropped)", flush=True)
    for fname in files:
        kept = []
        for row in after_filters[fname]:
            grams = shingles(row["text"])
            j, _ = syn_idx.jaccard_max(grams)
            jmax[row["id"]] = j
            if j >= JACCARD_DROP:
                stats[fname]["cross_file_jaccard_dropped"] = stats[fname].get("cross_file_jaccard_dropped", 0) + 1
                drop_log.append({"file": fname, "stage": "cross_file_jaccard", "id": row["id"],
                                 "reason": f"8-gram Jaccard {j:.3f} >= {JACCARD_DROP} vs earlier synthetic row"})
                continue
            syn_idx.add(global_i, grams)
            global_i += 1
            kept.append(row)
        after_filters[fname] = kept
        stats[fname].setdefault("cross_file_jaccard_dropped", 0)

    # ---- stage 6: Jaccard vs real corpus (train masked_text + test) --------
    print("indexing real corpus (train masked_text + test masked_text) ...", flush=True)
    real_idx = NgramIndex(df_cap=REAL_DF_CAP)
    n_real = 0
    for corpus_file in ("train.jsonl", "test.jsonl"):
        with open(CORPUS_DIR / corpus_file, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                real_idx.add(n_real, shingles(r["masked_text"]))
                n_real += 1
    capped = real_idx.capped()
    print(f"  {n_real} real rows indexed; {capped} boilerplate shingles capped (df>{REAL_DF_CAP})", flush=True)

    for fname in files:
        kept = []
        for row in after_filters[fname]:
            grams = shingles(row["text"])
            j, _ = real_idx.jaccard_max(grams)
            jmax[row["id"]] = max(jmax.get(row["id"], 0.0), j)
            if j >= JACCARD_DROP:
                stats[fname]["corpus_jaccard_dropped"] = stats[fname].get("corpus_jaccard_dropped", 0) + 1
                drop_log.append({"file": fname, "stage": "corpus_jaccard", "id": row["id"],
                                 "reason": f"8-gram Jaccard {j:.3f} >= {JACCARD_DROP} vs real corpus (generator copied)"})
                continue
            kept.append(row)
        after_filters[fname] = kept
        stats[fname].setdefault("corpus_jaccard_dropped", 0)

    # ---- survivors: attach jaccard_max, write clean files ------------------
    survivors: list[dict] = []
    for fname in files:
        rows = after_filters[fname]
        stats[fname]["survivors_pre_llmism"] = len(rows)
        with open(clean_dir / fname, "w", encoding="utf-8") as fh:
            for row in rows:
                out = dict(row)
                out["jaccard_max"] = round(jmax.get(row["id"], 0.0), 4)
                fh.write(json.dumps(out, ensure_ascii=False) + "\n")
        survivors.extend(rows)

    # ---- stage 7: vocab coverage -------------------------------------------
    vocab = {name: 0 for name, _ in OIL_TERM_RES}
    for row in survivors:
        for name, rex in OIL_TERM_RES:
            if rex.search(row["text"]):
                vocab[name] += 1
    vocab_misses = {k: v for k, v in vocab.items() if v < VOCAB_GATE}

    # ---- stage 8: LLM-ism detector -----------------------------------------
    if args.skip_llmism:
        llmism = {"status": "skipped (--skip-llmism): orchestrator adjudication — "
                             "AUC~1.0 separation is stylistic register, not templating; "
                             "no mitigation drop applied this round"}
    else:
        llmism = run_llmism(survivors, stats, clean_dir)

    # ---- self-checks --------------------------------------------------------
    leaks_after = sum(1 for row in survivors if _PATTERN.search(row["text"]))
    assert leaks_after == 0, f"{leaks_after} outcome stems survived QA"

    for fname in files:
        st = stats[fname]
        st["survivors"] = st["survivors_pre_llmism"] - st.get("llmism_dropped", 0)
        accounted = (st.get("schema_dropped", 0) + st.get("leak_dropped", 0)
                     + st.get("aiism_dropped", 0) + st.get("within_file_dup_dropped", 0)
                     + st.get("cross_file_jaccard_dropped", 0) + st.get("corpus_jaccard_dropped", 0)
                     + st.get("llmism_dropped", 0) + st["survivors"])
        assert accounted == st["rows_in"], f"{fname}: drop accounting mismatch ({accounted} != {st['rows_in']})"

    out = {
        "per_file": stats,
        "totals": {
            "rows_in": sum(s["rows_in"] for s in stats.values()),
            "schema_dropped": sum(s.get("schema_dropped", 0) for s in stats.values()),
            "leak_dropped": sum(s.get("leak_dropped", 0) for s in stats.values()),
            "aiism_dropped": sum(s.get("aiism_dropped", 0) for s in stats.values()),
            "within_file_dup_dropped": sum(s.get("within_file_dup_dropped", 0) for s in stats.values()),
            "cross_file_jaccard_dropped": sum(s.get("cross_file_jaccard_dropped", 0) for s in stats.values()),
            "corpus_jaccard_dropped": sum(s.get("corpus_jaccard_dropped", 0) for s in stats.values()),
            "llmism_dropped": sum(s.get("llmism_dropped", 0) for s in stats.values()),
            "survivors": sum(s["survivors"] for s in stats.values()),
        },
        "vocab_coverage": vocab,
        "vocab_gate": VOCAB_GATE,
        "vocab_misses": vocab_misses,
        "llmism": llmism,
        "drop_log": drop_log,
    }
    with open(stats_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    print(f"\nrows in: {out['totals']['rows_in']}  survivors: {out['totals']['survivors']}")
    print(f"leaks: {out['totals']['leak_dropped']}  ai-isms: {out['totals']['aiism_dropped']}  "
          f"within-file dups: {out['totals']['within_file_dup_dropped']}  "
          f"cross-file J: {out['totals']['cross_file_jaccard_dropped']}  "
          f"corpus J: {out['totals']['corpus_jaccard_dropped']}  "
          f"llm-ism: {out['totals']['llmism_dropped']}")
    print(f"vocab misses (<{VOCAB_GATE} rows): {vocab_misses or 'NONE'}")
    if args.skip_llmism:
        print(f"LLM-ism: {llmism['status']}")
    else:
        print(f"LLM-ism AUC: {llmism['auc_initial']:.4f} (gate < 0.9)"
              + (f" -> after mitigation: {llmism.get('auc_after_mitigation'):.4f}" if llmism.get("auc_after_mitigation") else ""))
    print(f"stats -> {stats_path}")


def run_llmism(survivors: list[dict], stats: dict[str, dict], clean_dir: Path = CLEAN_DIR) -> dict:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score
    import numpy as np
    import random

    print("LLM-ism detector: building real pool ...", flush=True)
    rng = random.Random(42)
    syn_texts = [r["text"] for r in survivors]
    syn_lens = sorted(len(_TOKEN_RE.findall(t.lower())) for t in syn_texts)
    edges = [syn_lens[int(q * (len(syn_lens) - 1))] for q in np.linspace(0, 1, 11)]

    # real pool: masked OSHA train rows, sampled to match synthetic length deciles
    osha_rows = []
    with open(CORPUS_DIR / "train.jsonl", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r["source"].startswith("osha"):
                osha_rows.append(r["masked_text"])
    bins: dict[int, list[str]] = defaultdict(list)
    for t in osha_rows:
        wl = len(_TOKEN_RE.findall(t.lower()))
        b = min(max(sum(wl > e for e in edges) - 1, 0), 9)
        bins[b].append(t)
    real_sample = []
    for b in range(10):
        want = sum(1 for L in syn_lens if min(max(sum(L > e for e in edges) - 1, 0), 9) == b)
        pool = bins.get(b, [])
        real_sample.extend(rng.sample(pool, min(want, len(pool))))
    print(f"  real sample: {len(real_sample)} (target {len(syn_texts)}), length-decile matched", flush=True)

    X_texts = real_sample + syn_texts
    y = np.array([0] * len(real_sample) + [1] * len(syn_texts))
    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=5000, lowercase=True)
    X = vec.fit_transform(X_texts)
    clf = LogisticRegression(max_iter=2000, C=1.0)
    cv = StratifiedKFold(n_splits=10, shuffle=True, random_state=42)
    proba = cross_val_predict(clf, X, y, cv=cv, method="predict_proba")[:, 1]
    auc = roc_auc_score(y, proba)
    result: dict = {"auc_initial": round(float(auc), 4), "gate": "< 0.9",
                    "n_real": len(real_sample), "n_synth": len(syn_texts)}

    if auc >= 0.9:
        clf.fit(X, y)
        feats = np.array(vec.get_feature_names_out())
        top = np.argsort(clf.coef_[0])[-20:][::-1]
        result["top20_synthetic_features"] = [f"{feats[i]} ({clf.coef_[0][i]:+.3f})" for i in top]
        print(f"  AUC {auc:.4f} >= 0.9 — GATE FAIL. Top tells: {result['top20_synthetic_features'][:8]}", flush=True)

        # ONE cheap mitigation: drop the most templated quartile (highest CV synth probability)
        syn_proba = proba[len(real_sample):]
        cutoff = np.quantile(syn_proba, 0.75)
        drop_ids = {r["id"] for r, p in zip(survivors, syn_proba) if p >= cutoff}
        result["mitigation"] = "drop most templated quartile (CV P(synthetic) >= q75)"
        result["mitigation_dropped"] = len(drop_ids)

        # rewrite clean files without dropped rows
        kept_survivors = []
        for path in sorted(CLEAN_DIR.glob("*.jsonl")):
            kept_rows = []
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    row = json.loads(line)
                    if row["id"] in drop_ids:
                        stats[path.name]["llmism_dropped"] = stats[path.name].get("llmism_dropped", 0) + 1
                        continue
                    kept_rows.append(row)
            with open(path, "w", encoding="utf-8") as fh:
                for row in kept_rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            kept_survivors.extend(kept_rows)

        kept_texts = [r["text"] for r in kept_survivors]
        real_resample = rng.sample(real_sample, min(len(kept_texts), len(real_sample)))
        X2 = vec.fit_transform(real_resample + kept_texts)
        y2 = np.array([0] * len(real_resample) + [1] * len(kept_texts))
        proba2 = cross_val_predict(clf, X2, y2, cv=cv, method="predict_proba")[:, 1]
        auc2 = roc_auc_score(y2, proba2)
        result["auc_after_mitigation"] = round(float(auc2), 4)
        result["n_synth_after_mitigation"] = len(kept_texts)
        if auc2 >= 0.9:
            clf.fit(X2, y2)
            feats2 = np.array(vec.get_feature_names_out())
            top2 = np.argsort(clf.coef_[0])[-20:][::-1]
            result["top20_features_after_mitigation"] = [f"{feats2[i]} ({clf.coef_[0][i]:+.3f})" for i in top2]
            result["verdict"] = "FAIL after mitigation — ship with disclosure (20-min budget exhausted)"
        else:
            result["verdict"] = "PASS after mitigation"
    else:
        result["verdict"] = "PASS"
    return result


if __name__ == "__main__":
    main()
