"""Near-dup embedding index + banner scenario check — runnable, no pytest.

Verifies the REAL MiniLM index end to end:
  1. pooling matches the official sentence-transformers quickstart matrix
     (mean-pool + L2 norm exact, worst |delta| <= 5e-3)
  2. corpus index loads from .npy and a VERBATIM train row scores cosine ~1.0
     -> banner fires (the "memory, not generalization" attack)
  3. a ONE-WORD-CHANGED twin still scores >= measured threshold -> banner fires
  4. an UNRELATED report scores below threshold -> no banner
  5. ingest-time embedding round-trips through SQLite and is found by nearest()

Run: .venv/bin/python app/tests/near_dup_embed_check.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.config import Settings  # noqa: E402
from app.embedder import embed_text, verify_pooling  # noqa: E402
from app.gates import gate_near_dup  # noqa: E402
from app.schemas import ReportIn  # noqa: E402
from app.storage import SQLiteStorage  # noqa: E402

CORPUS = REPO_ROOT / "artifacts" / "corpus" / "train_final_v2.jsonl"
INDEX_DIR = REPO_ROOT / "artifacts" / "embeddings"


def check(cond: bool, label: str) -> None:
    if not cond:
        raise AssertionError(f"FAIL: {label}")
    print(f"  ok: {label}")


def main() -> int:
    cfg = Settings()
    tau = cfg.near_dup_threshold
    print(f"threshold: {tau} (artifacts/embeddings/threshold_report.md)")

    print("[1] pooling verification vs official quickstart sims")
    v = verify_pooling()
    check(v["worst_abs_delta"] <= 5e-3, f"mean-pool matches reference (worst |d|={v['worst_abs_delta']})")

    rows = []
    with open(CORPUS, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i > 5000:  # a slice is enough for scenario texts
                break
            rows.append(json.loads(line))
    train_row = rows[1234]["text"]
    check(len(train_row) >= 20, "sampled train row is non-trivial")

    tmp = tempfile.TemporaryDirectory(prefix="sif-neardup-")
    storage = SQLiteStorage(Path(tmp.name) / "t.db", corpus_index_dir=INDEX_DIR)
    try:
        check(storage._base_mat is not None and len(storage._base_ids) > 60_000,
              f"corpus index loaded ({len(storage._base_ids)} rows)")

        print("[2] verbatim train row -> cosine ~1.0 -> banner")
        rid, sim = storage.nearest(embed_text(train_row), k=1)[0]
        check(sim >= 0.999, f"verbatim cosine {sim:.4f} >= 0.999 (row {rid})")
        gate = gate_near_dup(train_row, storage, cfg)
        check(gate.triggered, f"banner fired ({gate.detail})")

        print("[3] one-word-changed twin -> banner")
        words = train_row.split(" ")
        swapped = False
        for i, w in enumerate(words):
            if w.lower().strip(".,;") in {"worker", "employee", "man", "crew"}:
                words[i] = w.lower().strip(".,;") and "technician" or "technician"
                swapped = True
                break
        if not swapped:
            words.insert(min(5, len(words) - 1), "also")
        twin = " ".join(words)
        rid, sim = storage.nearest(embed_text(twin), k=1)[0]
        gate = gate_near_dup(twin, storage, cfg)
        check(gate.triggered and sim >= tau, f"twin cosine {sim:.4f} >= {tau} -> banner ({gate.detail})")

        print("[4] unrelated report -> no banner")
        unrelated = ("Quarterly financial results exceeded analyst expectations as revenue "
                     "grew across all segments and the board declared an interim dividend.")
        gate = gate_near_dup(unrelated, storage, cfg)
        sim = storage.nearest(embed_text(unrelated), k=1)[0][1]
        check(not gate.triggered and sim < tau, f"unrelated cosine {sim:.4f} < {tau} -> no banner ({gate.detail})")

        print("[5] ingest embedding round-trip through SQLite")
        report = ReportIn(text=unrelated, source="check")
        rid_int = storage.add_report(report)
        storage.add_embedding(rid_int, embed_text(report.text))
        hits = storage.nearest(embed_text(unrelated), k=1)
        check(hits[0][0] == rid_int and hits[0][1] >= 0.999,
              f"session row found verbatim (report #{hits[0][0]}, cosine {hits[0][1]:.4f})")
    finally:
        storage.close()
        tmp.cleanup()

    print("\nNEAR-DUP CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
