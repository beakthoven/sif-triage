"""Input gates — the 6 engineered humility/quality checks.

Every gate returns a GateState; triggered=True means "route to review queue /
show gray state in UI", never "silently drop". Gates never block ingestion —
they annotate.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .config import Settings
from .schemas import GateState

if TYPE_CHECKING:
    from .storage import Storage

_NEGATION_CUES = (
    "no ", "not ", "never", "without", "none ", "didn't", "did not",
    "wasn't", "was not", "weren't", "were not", "uninjured", "avoided",
)

_DRILL_KEYWORDS = (
    "drill", "mock drill", "tabletop", "simulation", "simulated",
    "exercise", "fire drill", "mock exercise", "training scenario",
)

_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def gate_min_length(text: str, cfg: Settings) -> GateState:
    """Min-length validator WITH short-codes exception path.

    'LOTO not applied' is 17 chars of pure SIF signal — a bare min-20-char
    validator would eat it (SEV1 register #7). A short report survives if it
    contains a known short code.
    """
    if len(text.strip()) >= cfg.min_text_length:
        return GateState(name="min_length", triggered=False)
    upper = text.upper()
    hits = [c for c in cfg.short_codes if c in upper]
    if hits:
        return GateState(
            name="min_length",
            triggered=False,
            detail=f"short report accepted via codes path: {', '.join(hits)}",
        )
    return GateState(
        name="min_length",
        triggered=True,
        detail=f"len={len(text.strip())} < {cfg.min_text_length} and no short code",
    )


def gate_negation(text: str) -> GateState:
    """NegEx-style stub: flag negation cues so a human checks that a 'no injury /
    no permit' statement isn't being read as its opposite."""
    low = text.lower()
    hits = [c.strip() for c in _NEGATION_CUES if c in low]
    return GateState(
        name="negation",
        triggered=bool(hits),
        detail=f"negation cues: {', '.join(sorted(set(hits)))}" if hits else "",
    )


def gate_language(text: str) -> GateState:
    """ASCII-ratio language stub. Report text is never machine-translated live;
    non-English input goes gray for the reviewer."""
    if not text:
        return GateState(name="language", triggered=True, detail="empty text")
    ascii_ratio = sum(1 for ch in text if ord(ch) < 128) / len(text)
    triggered = ascii_ratio < 0.85
    return GateState(
        name="language",
        triggered=triggered,
        detail=f"ascii_ratio={ascii_ratio:.2f}" if triggered else "",
    )


def gate_confidence(score: float, cfg: Settings) -> GateState:
    """Confidence gray band — triage score inside the band routes to review."""
    triggered = cfg.gray_band_low <= score <= cfg.gray_band_high
    return GateState(
        name="confidence",
        triggered=triggered,
        detail=f"score {score:.3f} in gray band "
        f"[{cfg.gray_band_low}, {cfg.gray_band_high}]" if triggered else "",
    )


def gate_drill(text: str) -> GateState:
    """Drill/simulation filter — drills are not precursors (demo red-team SEV1 #6)."""
    low = text.lower()
    hits = [k for k in _DRILL_KEYWORDS if k in low]
    return GateState(
        name="drill",
        triggered=bool(hits),
        detail=f"drill keywords: {', '.join(sorted(set(hits)))}" if hits else "",
    )


def gate_near_dup(text: str, storage: "Storage", cfg: Settings) -> GateState:
    """Near-duplicate banner hook over the stored-embedding cosine index.

    The index includes everything ever ingested, so re-pasted training rows
    surface here. Stub embeddings are hashed n-gram vectors; threshold to be
    re-derived from the measured MiniLM curve (see config).
    """
    from .classifier import pseudo_embed  # local import: storage<->classifier cycle

    vec = pseudo_embed(text, cfg.embed_dim)
    nearest = storage.nearest(vec, k=1, exclude_text=text)
    if nearest and nearest[0][1] >= cfg.near_dup_threshold:
        rid, sim = nearest[0]
        return GateState(
            name="near_dup",
            triggered=True,
            detail=f"cosine={sim:.3f} with report #{rid} (>= {cfg.near_dup_threshold})",
        )
    detail = f"max cosine={nearest[0][1]:.3f}" if nearest else "index empty"
    return GateState(name="near_dup", triggered=False, detail=detail)


def run_gates(text: str, score: float, storage: "Storage", cfg: Settings) -> list[GateState]:
    return [
        gate_min_length(text, cfg),
        gate_negation(text),
        gate_language(text),
        gate_confidence(score, cfg),
        gate_drill(text),
        gate_near_dup(text, storage, cfg),
    ]
