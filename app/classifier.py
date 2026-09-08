"""Classifier protocol + deterministic mock + real-ONNX stub.

The mock is CONTRACT-IDENTICAL to the real model: same PredictionOut shape,
same span-validity invariant (text[start:end] == span.text, checked before
every response). Scores are seeded by sha256(text) so the same report always
gets the same prediction — regression tests and the demo rehearsal depend on it.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Protocol

import numpy as np

from .schemas import RULE_KEYS, EvidenceSpan, PredictionOut

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


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def pseudo_embed(text: str, dim: int = 384) -> np.ndarray:
    """Deterministic hashed word/char-n-gram embedding (L2-normalized).

    Stub for MiniLM: no model download, and near-identical texts genuinely
    score high cosine — enough for the near-dup gate hook to be exercised.
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
        well_control = any(k in low for k in _WELL_CONTROL_KEYWORDS)
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


class RealOnnxClassifier:
    """Stub for the ModernBERT INT8 multi-task ONNX artifact.

    Loads only when model.onnx exists (torch.onnx.export + quantize_dynamic,
    hand-rolled per DECISION_LOG D12). onnxruntime is imported lazily so the
    API runs with zero ML deps until the artifact drops in.
    """

    def __init__(self, model_path: Path) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"ONNX artifact not found: {self.model_path}")
        import onnxruntime as ort  # noqa: F401 — lazy by design; absent locally

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 8  # measured optimum; 16 is worse (HT contention)
        self._session = ort.InferenceSession(str(self.model_path), opts)
        self.model_version = f"onnx:{self.model_path.name}"

    def predict(self, text: str) -> PredictionOut:
        raise NotImplementedError(
            "RealOnnxClassifier.predict lands with the Day-2 export-gate kernel "
            "(heads: sif_logits, rule_logits, span_logits; char offsets computed "
            "server-side against canonical text)."
        )


def build_classifier(model_path: Path, mock_version: str) -> Classifier:
    try:
        return RealOnnxClassifier(model_path)
    except FileNotFoundError:
        return MockClassifier(model_version=mock_version)
