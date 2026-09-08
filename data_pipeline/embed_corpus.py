"""Embed the train corpus with vendored MiniLM -> fp16 memmap index.

Input : artifacts/corpus/train_final_v2.jsonl  (70,404 rows, field "text")
Output: artifacts/embeddings/corpus_embeddings_fp16.npy   (n, 384) float16, L2-normalized
        artifacts/embeddings/corpus_ids.jsonl             ({"id", "source"} per row, same order)
        artifacts/embeddings/corpus_index_meta.json       (model/dim/dtype/count/timing/sha256)

The runtime (app/storage.py) loads this .npy at startup so the near-dup index
INCLUDES the training corpus — a verbatim training-row paste attack is caught
(ARCHITECTURE runtime; demo red-teamer attack (d)).

Run: .venv/bin/python data_pipeline/embed_corpus.py
"""
from __future__ import annotations

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


def main() -> int:
    rows = []
    with open(CORPUS, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            rows.append({"id": r["id"], "source": r.get("source"), "text": r["text"]})
    n = len(rows)
    print(f"corpus rows: {n}")

    t0 = time.perf_counter()
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
    }
    META_PATH.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {NPY_PATH.name} ({NPY_PATH.stat().st_size / 1e6:.1f} MB), {IDS_PATH.name}, {META_PATH.name}")
    print(f"EMBED TIME: {elapsed:.1f}s for {n} rows = {n / elapsed:.0f} rows/s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
