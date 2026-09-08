"""Classifier protocol + deterministic mock + real ONNX runtime.

The mock is CONTRACT-IDENTICAL to the real model: same PredictionOut shape,
same span-validity invariant (text[start:end] == span.text, checked before
every response). Scores are seeded by sha256(text) so the same report always
gets the same prediction — regression tests and the demo rehearsal depend on it.

RealOnnxClassifier runs the ModernBERT INT8/FP32 multi-task artifact
(heads: sif_logit, rule_logits[7], span_logits — see export_gate_report.md).
onnxruntime/tokenizers are imported lazily so the API still boots with zero
ML deps when no artifact is present (falls back to the mock).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Protocol

import numpy as np

from .schemas import RULE_KEYS, EvidenceSpan, PredictionOut

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Keyword anchors the mock uses to place evidence spans. Mirrors the weak-
# supervision anchors the real span head is trained from (DECISION_LOG D2).
_SPAN_ANCHORS: dict[str, tuple[str, ...]] = {
    "energy_isolation": ("loto", "lock-out", "lockout", "isolation", "de-energized", "energized"),
    "hot_work": ("hot work", "welding", "grinding", "grinder", "sparks", "cutting"),
    "working_at_height": ("height", "harness", "scaffold", "ladder", "fall arrest"),
    "confined_space": ("confined space", "vessel entry", "tank entry", "manhole"),
    "line_of_fire": ("line of fire", "dropped object", "suspended load", "struck", "pinch"),
    "safe_mechanical_lifting": ("lifting", "crane", "rigging", "sling", "hoist"),
    "driving": ("driving", "vehicle", "speeding", "seat belt", "journey"),
}

_WELL_CONTROL_KEYWORDS = (
    "kick", "bop", "blowout", "well control", "loss of circulation",
    "gain in pit", "pit gain", "shut in", "kill the well", "gas influx",
)


def has_well_control(text: str) -> bool:
    """Deterministic well-control/barrier tag (ARCHITECTURE: keyword/code
    rules, cheap) — shared by mock and real classifier."""
    low = text.lower()
    return any(k in low for k in _WELL_CONTROL_KEYWORDS)


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def pseudo_embed(text: str, dim: int = 384) -> np.ndarray:
    """Deterministic hashed word/char-n-gram embedding (L2-normalized).

    Fallback for the real MiniLM embedder (app/embedder.py HashedEmbedder),
    used only when the vendored MiniLM ONNX is absent. The production
    near-dup path embeds with all-MiniLM-L6-v2.
    """
    vec = np.zeros(dim, dtype=np.float32)
    low = text.lower()
    tokens = re.findall(r"[a-z0-9]+", low)
    feats = list(tokens)
    for tok in tokens:
        feats.extend(tok[i : i + 3] for i in range(max(0, len(tok) - 2)))
    for feat in feats:
        h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if h[4] & 1 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


def validate_spans(text: str, spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    """Server-side invariant from the architecture: only spans with
    text[start:end] == span.text may ever leave the API."""
    return [s for s in spans if 0 <= s.start < s.end <= len(text) and text[s.start : s.end] == s.text]


class Classifier(Protocol):
    model_version: str

    def predict(self, text: str) -> PredictionOut:
        ...


class MockClassifier:
    def __init__(self, model_version: str = "mock-0.1.0") -> None:
        self.model_version = model_version

    def predict(self, text: str) -> PredictionOut:
        rng = np.random.default_rng(_seed(text))
        # Beta(2,5) skews low — realistic triage distribution (~20% flag rate).
        sif_score = float(rng.beta(2.0, 5.0))
        rule_probs = {k: float(rng.beta(1.5, 6.0)) for k in RULE_KEYS}
        # Anchor hits nudge the matching rule up so the mock looks coherent.
        low = text.lower()
        for rule, anchors in _SPAN_ANCHORS.items():
            if any(a in low for a in anchors):
                rule_probs[rule] = min(1.0, rule_probs[rule] + 0.35)
        well_control = has_well_control(text)
        spans = validate_spans(text, self._make_spans(text, rng))
        return PredictionOut(
            sif_score=round(sif_score, 4),
            rule_probs={k: round(v, 4) for k, v in rule_probs.items()},
            well_control=well_control,
            evidence_spans=spans,
            gate_states=[],  # filled in by the route layer after gates run
            model_version=self.model_version,
        )

    def _make_spans(self, text: str, rng: np.random.Generator) -> list[EvidenceSpan]:
        spans: list[EvidenceSpan] = []
        low = text.lower()
        for anchors in _SPAN_ANCHORS.values():
            for anchor in anchors:
                i = low.find(anchor)
                if i >= 0:
                    spans.append(EvidenceSpan(start=i, end=i + len(anchor), text=text[i : i + len(anchor)]))
                    break
        if not spans and text.strip():
            # No anchor: take a deterministic word-window substring.
            words = list(re.finditer(r"\S+", text))
            if words:
                i = int(rng.integers(0, len(words)))
                m = words[i]
                spans.append(EvidenceSpan(start=m.start(), end=m.end(), text=text[m.start() : m.end()]))
        return spans[:5]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


class RealOnnxClassifier:
    """ModernBERT multi-task ONNX artifact (sif / 7-rule / token-span heads).

    Loads only when a real .onnx exists. model_path may be the .onnx file or
    a directory holding the artifacts; quant preference comes from
    SIF_MODEL_QUANT ("int8" default, "fp32" to override). onnxruntime and
    tokenizers are imported lazily so the API runs with zero ML deps until
    the artifact drops in.
    """

    SEQ_LEN = 128            # verified p99=112 tokens on corpus (ARCHITECTURE)
    STRIDE = 96              # sliding-window stride for long inputs
    SPAN_THRESHOLD = 0.5     # token-prob cutoff for evidence spans
    TOP_SPANS = 3
    # Ordered candidates per quant preference; first hit wins, then falls
    # back to the other precision — a real model of either kind beats mock.
    _INT8_NAMES = ("sif_multitask_int8.onnx", "model_int8.onnx")
    _FP32_NAMES = ("sif_multitask_fp32.onnx", "model_fp32.onnx")

    def __init__(self, model_path: Path, tokenizer_path: Path | None = None,
                 quant: str | None = None) -> None:
        self.model_path = Path(model_path)
        self._onnx_path = self._resolve_onnx(self.model_path, quant or os.environ.get("SIF_MODEL_QUANT", "int8"))
        self.quant = "int8" if "int8" in self._onnx_path.name else "fp32"
        self._tokenizer_path = self._resolve_tokenizer(self._onnx_path.parent, tokenizer_path)
        self.temperature = self._load_temperature(self._onnx_path.parent)

        import onnxruntime as ort  # lazy by design
        from tokenizers import Tokenizer  # noqa: F401 — lazy by design

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 8  # measured optimum; 16 is worse (HT contention)
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(
            str(self._onnx_path), opts, providers=["CPUExecutionProvider"])
        self._tokenizer = Tokenizer.from_file(str(self._tokenizer_path))
        self._cls_id = self._tokenizer.token_to_id("[CLS]")
        self._sep_id = self._tokenizer.token_to_id("[SEP]")
        self._pad_id = self._tokenizer.token_to_id("[PAD]")
        self.model_version = f"onnx:{self._onnx_path.parent.name}/{self._onnx_path.name}"
        self.dropped_spans = 0

    # ---- artifact resolution -------------------------------------------------

    @classmethod
    def _resolve_onnx(cls, model_path: Path, quant: str) -> Path:
        if model_path.is_file():
            if model_path.suffix == ".onnx":
                return model_path
            raise FileNotFoundError(f"not an ONNX file: {model_path}")
        if model_path.is_dir():
            first, second = (cls._INT8_NAMES, cls._FP32_NAMES) if quant != "fp32" else (cls._FP32_NAMES, cls._INT8_NAMES)
            for name in first + second + ("model.onnx",):
                cand = model_path / name
                if cand.exists():
                    return cand
            candidates = sorted(p for p in model_path.glob("*.onnx")
                                if not p.name.endswith(".onnx.data"))
            if candidates:
                return candidates[0]
        raise FileNotFoundError(f"ONNX artifact not found: {model_path}")

    @staticmethod
    def _resolve_tokenizer(model_dir: Path, tokenizer_path: Path | None) -> Path:
        candidates = [
            tokenizer_path,
            Path(os.environ["SIF_TOKENIZER_PATH"]) if os.environ.get("SIF_TOKENIZER_PATH") else None,
            model_dir / "tokenizer.json",
            model_dir / "tokenizer" / "tokenizer.json",
            REPO_ROOT / "artifacts" / "models" / "tokenizer" / "tokenizer.json",
        ]
        for cand in candidates:
            if cand is not None:
                cand = Path(cand)
                if cand.is_dir():
                    cand = cand / "tokenizer.json"
                if cand.exists():
                    return cand
        raise FileNotFoundError(
            "tokenizer.json not found (checked model dir, SIF_TOKENIZER_PATH, "
            "artifacts/models/tokenizer)")

    @staticmethod
    def _load_temperature(model_dir: Path) -> float:
        """Temperature-scaling hook: read T from metrics.json next to the
        model when present (calibration lands with the trained artifact),
        else 1.0 (identity)."""
        metrics = model_dir / "metrics.json"
        if not metrics.exists():
            return 1.0
        try:
            data = json.loads(metrics.read_text())
            cal = data.get("calibration", {}) if isinstance(data, dict) else {}
            t = data.get("temperature") or data.get("sif_temperature") or cal.get("temperature")
            t = float(t) if t else 1.0
            return t if t > 0 else 1.0
        except (ValueError, OSError, TypeError):
            log.warning("metrics.json unreadable; temperature=1.0")
            return 1.0

    # ---- inference -----------------------------------------------------------

    def predict(self, text: str) -> PredictionOut:
        enc = self._tokenizer.encode(text, add_special_tokens=False)
        body_ids = enc.ids
        offsets = enc.offsets
        windows = self._windows(len(body_ids))
        input_ids, attention_mask = self._batch(body_ids, windows)
        sif_logits, rule_logits, span_logits = self._session.run(
            ["sif_logit", "rule_logits", "span_logits"],
            {"input_ids": input_ids, "attention_mask": attention_mask},
        )
        # Max-pool per-head scores across windows (logit / T is monotonic in
        # the logit, so pooling probabilities after scaling is equivalent).
        sif_probs = _sigmoid(sif_logits.astype(np.float64) / self.temperature)
        sif_score = float(np.max(sif_probs))
        rule_probs = np.max(_sigmoid(rule_logits.astype(np.float64)), axis=0)
        best = int(np.argmax(sif_probs))
        spans = self._extract_spans(text, offsets, windows[best], span_logits[best])
        return PredictionOut(
            sif_score=round(sif_score, 4),
            rule_probs={k: round(float(p), 4) for k, p in zip(RULE_KEYS, rule_probs)},
            well_control=has_well_control(text),
            evidence_spans=spans,
            gate_states=[],  # filled in by the route layer after gates run
            model_version=self.model_version,
            chunked=len(windows) > 1,
        )

    def _windows(self, n_body: int) -> list[tuple[int, int]]:
        """(start, end) body-token slices. Single window when the text fits;
        else sliding window seq=128 (126 body + CLS/SEP), stride=96, with the
        tail guaranteed covered."""
        body = self.SEQ_LEN - 2
        if n_body <= body:
            return [(0, n_body)]
        out = [(i, min(i + body, n_body)) for i in range(0, n_body, self.STRIDE)]
        if out[-1][1] < n_body:
            out.append((n_body - body, n_body))
        return out

    def _batch(self, body_ids: list[int], windows: list[tuple[int, int]]) -> tuple[np.ndarray, np.ndarray]:
        width = max(end - start for start, end in windows) + 2
        ids = np.full((len(windows), width), self._pad_id, dtype=np.int64)
        mask = np.zeros((len(windows), width), dtype=np.int64)
        for row, (start, end) in enumerate(windows):
            n = end - start
            ids[row, 0] = self._cls_id
            ids[row, 1 : n + 1] = body_ids[start:end]
            ids[row, n + 1] = self._sep_id
            mask[row, : n + 2] = 1
        return ids, mask

    def _extract_spans(self, text: str, offsets: list[tuple[int, int]],
                       window: tuple[int, int], span_logits_row: np.ndarray) -> list[EvidenceSpan]:
        """Token probs above threshold -> merge contiguous -> char offsets via
        offset_mapping -> validate text[start:end] == span text exactly
        (invalid dropped + counted) -> top-3. Fallback when nothing crosses
        the threshold (weak span head): top-scoring tokens, i.e. the
        keyword-attribution highlighting fallback from ARCHITECTURE."""
        start, end = window
        n = end - start
        probs = _sigmoid(span_logits_row[1 : n + 1].astype(np.float64))
        hot = [j for j in range(n) if probs[j] > self.SPAN_THRESHOLD
               and offsets[start + j][1] > offsets[start + j][0]]
        runs: list[list[int]] = []
        for j in hot:
            if runs and j == runs[-1][-1] + 1:
                runs[-1].append(j)
            else:
                runs.append([j])
        candidates: list[tuple[float, int, int]] = []  # (score, char_start, char_end)
        for run in runs:
            g0, g1 = start + run[0], start + run[-1]
            c0, c1 = offsets[g0][0], offsets[g1][1]
            if 0 <= c0 < c1 <= len(text):
                candidates.append((float(np.mean(probs[run[0] : run[-1] + 1])), c0, c1))
        if not candidates and n > 0:
            ranked = sorted(
                (j for j in range(n) if offsets[start + j][1] > offsets[start + j][0]),
                key=lambda j: float(probs[j]), reverse=True)
            for j in ranked[: self.TOP_SPANS]:
                c0, c1 = offsets[start + j]
                if 0 <= c0 < c1 <= len(text):
                    candidates.append((float(probs[j]), c0, c1))
        candidates.sort(key=lambda c: (-c[0], c[1]))
        seen: set[tuple[int, int]] = set()
        spans: list[EvidenceSpan] = []
        for _, c0, c1 in candidates:
            if (c0, c1) in seen:
                continue
            seen.add((c0, c1))
            spans.append(EvidenceSpan(start=c0, end=c1, text=text[c0:c1]))
            if len(spans) == self.TOP_SPANS:
                break
        valid = validate_spans(text, spans)
        self.dropped_spans += len(spans) - len(valid)
        if len(valid) < len(spans):
            log.warning("dropped %d invalid span(s); total dropped=%d",
                        len(spans) - len(valid), self.dropped_spans)
        return valid


def build_classifier(model_path: Path, mock_version: str) -> Classifier:
    """Prefer a real artifact at SIF_MODEL_PATH (int8 by default; set
    SIF_MODEL_QUANT=fp32 to override). Fall back to the deterministic mock
    only when no artifact/tokenizer exists or the ML deps are absent —
    a corrupt model dir fails loudly, never silently mocks."""
    try:
        return RealOnnxClassifier(model_path)
    except (FileNotFoundError, ImportError):
        return MockClassifier(model_version=mock_version)
