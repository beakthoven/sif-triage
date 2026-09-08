"""Embed the train corpus with vendored MiniLM -> fp16 memmap index.

Input : artifacts/corpus/train_final_v2.jsonl  (70,404 rows, field "text")
Output: artifacts/embeddings/corpus_embeddings_fp16.npy   (n, 384) float16, L2-normalized
        artifacts/embeddings/corpus_ids.jsonl             ({"id", "source"} per row, same order)
        artifacts/embeddings/corpus_index_meta.json       (model/dim/dtype/count/timing/sha256)

The runtime (app/storage.py) loads this .npy at startup so the near-dup index
INCLUDES the training corpus — a verbatim training-row paste attack is caught
(ARCHITECTURE runtime; demo red-teamer attack (d)).

--exclude-ids PATH [...] drops corpus rows whose id is listed in PATH (DECISION_LOG
D24: the live-demo cards play "the user's own reports", so their training-index
rows must not banner). Each PATH is a .jsonl (row "id", or "provenance.id" for
demo_corpus-style rows) or a plain-text file of one id per line (# comments ok).

Run: .venv/bin/python data_pipeline/embed_corpus.py [--exclude-ids artifacts/demo/demo_corpus.jsonl]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.embedder import DEFAULT_MODEL_DIR, EMBED_DIM, embed_texts  # noqa: E402

CORPUS = REPO_ROOT / "artifacts" / "corpus" / "train_final_v2.jsonl"
OUT_DIR = REPO_ROOT / "artifacts" / "embeddings"
NPY_PATH = OUT_DIR / "corpus_embeddings_fp16.npy"
IDS_PATH = OUT_DIR / "corpus_ids.jsonl"
META_PATH = OUT_DIR / "corpus_index_meta.json"
BATCH = 256


def load_exclude_ids(paths: list[str]) -> set[str]:
    ids: set[str] = set()
    for p in paths:
        path = Path(p)
        for line in path.open(encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if path.suffix == ".jsonl":
                r = json.loads(line)
                rid = r.get("id") or (r.get("provenance") or {}).get("id")
                if rid:
                    ids.add(rid)
            else:
                ids.add(line)
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exclude-ids", nargs="*", default=[], metavar="PATH",
                        help="files listing corpus ids to drop from the index (D24)")
    args = parser.parse_args()
    exclude = load_exclude_ids(args.exclude_ids)

    rows = []
    with open(CORPUS, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            rows.append({"id": r["id"], "source": r.get("source"), "text": r["text"]})
    n_total = len(rows)
    excluded_count = 0
    if exclude:
        absent = sorted(exclude - {r["id"] for r in rows})
        rows = [r for r in rows if r["id"] not in exclude]
        excluded_count = n_total - len(rows)
        # ids given but absent from the corpus are no-ops, not errors (e.g.
        # demo cards that were written, never corpus rows).
        print(f"exclude-ids: {len(exclude)} given, {excluded_count} matched corpus rows and dropped"
              + (f", {len(absent)} not in corpus (no-op): {absent}" if absent else ""))
    n = len(rows)
    print(f"corpus rows: {n}" + (f" (excluded {excluded_count} of {n_total})" if exclude else ""))

    t0 = time.perf_counter()
    if NPY_PATH.exists():
        # A stale .npy from a different row set would silently corrupt: r+
        # reuses old bytes and the resume probe sees them as written rows.
        hdr_shape = np.load(NPY_PATH, mmap_mode="r").shape
        if hdr_shape != (n, EMBED_DIM):
            sys.exit(f"{NPY_PATH} holds shape {hdr_shape}, expected {(n, EMBED_DIM)} "
                     f"for this row set — move it aside (e.g. corpus_index_full_backup.npy) and rerun")
    # r+ when resuming (w+ would truncate rows already written).
    mm = np.lib.format.open_memmap(NPY_PATH, mode="r+" if NPY_PATH.exists() else "w+",
                                   dtype=np.float16, shape=(n, EMBED_DIM))
    resume_at = 0
    if META_PATH.exists() and not IDS_PATH.exists():
        META_PATH.unlink()  # stale meta from an interrupted run; recompute
    if not IDS_PATH.exists():
        # Resume support: unwritten memmap rows are zeros; restart at the
        # first zero row rounded down to a batch boundary.
        probe = np.load(NPY_PATH, mmap_mode="r")
        for s in range(0, n, 2000):
            block = probe[s : s + 2000].astype(np.float32)
            zeros = np.where(~block.any(axis=1))[0]
            if len(zeros):
                resume_at = (s + int(zeros[0])) // BATCH * BATCH
                break
        else:
            resume_at = n
        if resume_at:
            print(f"resuming at row {resume_at} ({resume_at / n * 100:.1f}% already written)")
    for start in range(resume_at, n, BATCH):
        batch = rows[start : start + BATCH]
        emb = embed_texts([r["text"] for r in batch], batch_size=BATCH)
        mm[start : start + len(batch)] = emb.astype(np.float16)
        done = min(start + BATCH, n)
        if done % (BATCH * 20) < BATCH or done == n:
            el = time.perf_counter() - t0
            print(f"  {done}/{n}  ({done / el:.0f} rows/s, {el:.1f}s elapsed)", flush=True)
    mm.flush()
    elapsed = time.perf_counter() - t0

    with open(IDS_PATH, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({"id": r["id"], "source": r["source"]}, ensure_ascii=False) + "\n")

    # --- self-check ---------------------------------------------------------
    arr = np.load(NPY_PATH, mmap_mode="r")
    assert arr.shape == (n, EMBED_DIM), f"shape {arr.shape} != {(n, EMBED_DIM)}"
    norms = np.linalg.norm(arr[:2000].astype(np.float32), axis=1)
    assert np.all(np.abs(norms - 1.0) < 2e-3), f"norm drift: {norms.min():.5f}..{norms.max():.5f}"
    rng = np.random.default_rng(42)
    spot = sorted(rng.integers(0, n, size=8).tolist())
    re_emb = embed_texts([rows[i]["text"] for i in spot])
    for k, i in enumerate(spot):
        cos = float(np.dot(arr[i].astype(np.float32), re_emb[k]))
        assert cos > 0.999, f"fp16 round-trip cosine {cos:.6f} on row {i}"
    print(f"self-check ok: shape={arr.shape}, norms~1 (±2e-3), fp16 round-trip cosine > 0.999 on 8 spot rows")
    if exclude:
        written = {json.loads(l)["id"] for l in IDS_PATH.open(encoding="utf-8")}
        leaked = exclude & written
        assert not leaked, f"excluded ids still in index: {sorted(leaked)}"
        print(f"self-check ok: 0 of {len(exclude)} excluded ids present in {IDS_PATH.name}")

    meta = {
        "model": "sentence-transformers/all-MiniLM-L6-v2 (vendored ONNX)",
        "model_dir": str(DEFAULT_MODEL_DIR.relative_to(REPO_ROOT)),
        "model_onnx_sha256": hashlib.sha256((DEFAULT_MODEL_DIR / "model.onnx").read_bytes()).hexdigest(),
        "pooling": "masked mean over last_hidden_state + L2 normalize (1_Pooling/config.json)",
        "truncation_word_pieces": 256,
        "corpus": str(CORPUS.relative_to(REPO_ROOT)),
        "n_rows": n,
        "dim": EMBED_DIM,
        "dtype": "float16",
        "embed_seconds": round(elapsed, 2),
        "rows_per_second": round(n / elapsed, 1),
        "excluded_demo_cards": bool(exclude),
        "excluded_demo_cards_count": excluded_count,
    }
    if exclude:
        meta["excluded_ids_files"] = [
            str(p) if not (rp := Path(p).resolve()).is_relative_to(REPO_ROOT)
            else str(rp.relative_to(REPO_ROOT))
            for p in args.exclude_ids
        ]
    META_PATH.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {NPY_PATH.name} ({NPY_PATH.stat().st_size / 1e6:.1f} MB), {IDS_PATH.name}, {META_PATH.name}")
    print(f"EMBED TIME: {elapsed:.1f}s for {n} rows = {n / elapsed:.0f} rows/s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
