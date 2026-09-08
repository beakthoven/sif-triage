"""MiniLM embedding runtime for the near-dup index (ARCHITECTURE runtime gate).

Model: sentence-transformers/all-MiniLM-L6-v2, vendored ONNX at
artifacts/embeddings/minilm/ (no torch; onnxruntime + tokenizers only).
Pooling matches the model card EXACTLY: masked MEAN pooling over
last_hidden_state (1_Pooling/config.json: pooling_mode_mean_tokens=true,
pooling_mode_cls_token=false), then L2 normalize. Inputs truncate at 256
word pieces (model-card default). Vendored 1_Pooling/config.json is the
provenance record.

Pooling verification: this pipeline reproduces the official sbert.net
quickstart similarity matrix for all-MiniLM-L6-v2
("The weather is lovely today." / "It's so sunny outside!" /
"He drove to the stadium." -> 0.6660 / 0.1046 / 0.1411) within 5e-3;
see app/tests/near_dup_embed_check.py.

onnxruntime/tokenizers import lazily; when the vendored model is absent the
module degrades to the deterministic hashed pseudo-embedding (same 384-dim
contract) with a loud warning, so the API still boots bare.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = REPO_ROOT / "artifacts" / "embeddings" / "minilm"

EMBED_DIM = 384
MAX_TOKENS = 256  # model-card truncation for all-MiniLM-L6-v2

# Official quickstart anchor (sbert.net/docs/quickstart.html) — the known-good
# reference this ONNX pipeline is verified against.
_QUICKSTART_SENTENCES = (
    "The weather is lovely today.",
    "It's so sunny outside!",
    "He drove to the stadium.",
)
_QUICKSTART_SIMS = ((0, 1, 0.6660), (0, 2, 0.1046), (1, 2, 0.1411))
QUICKSTART_TOLERANCE = 5e-3


class MiniLMEmbedder:
    """all-MiniLM-L6-v2 via vendored ONNX; mean-pool + L2 normalize."""

    def __init__(self, model_dir: Path) -> None:
        model_dir = Path(model_dir)
        onnx_path = model_dir / "model.onnx"
        tok_path = model_dir / "tokenizer.json"
        if not onnx_path.exists() or not tok_path.exists():
            raise FileNotFoundError(f"MiniLM artifacts missing under {model_dir}")

        import onnxruntime as ort  # lazy by design
        from tokenizers import Tokenizer  # noqa: F401 — lazy by design

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 8  # measured optimum on this box (see classifier)
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(str(onnx_path), opts, providers=["CPUExecutionProvider"])
        self._tokenizer = Tokenizer.from_file(str(tok_path))
        self._tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self._lock = threading.Lock()  # ORT session + padding state are not thread-safe

    def embed(self, texts: list[str]) -> np.ndarray:
        """Batch-embed -> (n, 384) fp32 L2-normalized rows."""
        if not texts:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)
        with self._lock:
            self._tokenizer.no_padding()
            encs = self._tokenizer.encode_batch(texts, add_special_tokens=True)
            width = max(len(e.ids) for e in encs)
            ids = np.zeros((len(encs), width), dtype=np.int64)
            mask = np.zeros((len(encs), width), dtype=np.int64)
            for i, e in enumerate(encs):
                ids[i, : len(e.ids)] = e.ids
                mask[i, : len(e.attention_mask)] = e.attention_mask
            type_ids = np.zeros_like(ids)
            hidden = self._session.run(
                ["last_hidden_state"],
                {"input_ids": ids, "attention_mask": mask, "token_type_ids": type_ids},
            )[0].astype(np.float32)
        mask_f = mask.astype(np.float32)[..., None]
        pooled = (hidden * mask_f).sum(axis=1) / np.maximum(mask_f.sum(axis=1), 1e-9)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return pooled / np.maximum(norms, 1e-12)


class HashedEmbedder:
    """Fallback: deterministic hashed n-gram embedding (ex-pseudo_embed).
    Keeps the API alive when the MiniLM artifact is absent; near-dup behaves
    like the old stub. Never used when the vendored model is present."""

    def __init__(self) -> None:
        from .classifier import pseudo_embed

        self._fn = pseudo_embed

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)
        return np.stack([self._fn(t, EMBED_DIM) for t in texts])


_singleton = None
_singleton_lock = threading.Lock()
_model_dir_override: Path | None = None


def configure(model_dir: Path) -> None:
    """Point the lazy singleton at a model dir (called once at app startup)."""
    global _model_dir_override, _singleton
    with _singleton_lock:
        _model_dir_override = Path(model_dir)
        _singleton = None  # force reload under the new dir


def get_embedder():
    """Lazy singleton: MiniLM when vendored, hashed fallback otherwise."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                model_dir = _model_dir_override or DEFAULT_MODEL_DIR
                try:
                    _singleton = MiniLMEmbedder(model_dir)
                    log.info("MiniLM embedder loaded from %s", model_dir)
                except (FileNotFoundError, ImportError) as exc:
                    log.warning("MiniLM unavailable (%s); falling back to hashed pseudo-embedding", exc)
                    _singleton = HashedEmbedder()
    return _singleton


def embed_texts(texts: list[str], batch_size: int = 256) -> np.ndarray:
    """Embed a list of texts -> (n, 384) fp32 L2-normalized."""
    enc = get_embedder()
    if len(texts) <= batch_size:
        return enc.embed(texts)
    out = [enc.embed(texts[i : i + batch_size]) for i in range(0, len(texts), batch_size)]
    return np.concatenate(out, axis=0)


def embed_text(text: str) -> np.ndarray:
    return get_embedder().embed([text])[0]


def verify_pooling(tolerance: float = QUICKSTART_TOLERANCE) -> dict:
    """Reproduce the official quickstart similarity matrix; returns per-pair
    measured vs reference deltas. Raises AssertionError beyond tolerance."""
    emb = embed_texts(list(_QUICKSTART_SENTENCES))
    rows = []
    worst = 0.0
    for i, j, ref in _QUICKSTART_SIMS:
        got = float(emb[i] @ emb[j])
        delta = abs(got - ref)
        worst = max(worst, delta)
        rows.append({"pair": (i, j), "reference": ref, "measured": round(got, 6), "abs_delta": round(delta, 6)})
    assert worst <= tolerance, f"pooling verification FAILED: worst |delta|={worst:.5f} > {tolerance} ({rows})"
    return {"pairs": rows, "worst_abs_delta": round(worst, 6), "tolerance": tolerance}
