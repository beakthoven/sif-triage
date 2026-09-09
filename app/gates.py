"""Input gates — the engineered humility/quality checks (ARCHITECTURE runtime).

Every gate returns a GateState {name, triggered, detail, action} where action
is 'badge' (annotate only), 'gray' (route to review queue / gray UI card), or
'block' (reserved — no gate blocks today; gates are ADVISORY states attached to
PredictionOut.gate_states). Gates never block ingestion and never raise: a
broken gate degrades to a gray state inside run_gates.

Gate order is load-bearing: app/tests/api_smoke.py addresses drill by position.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import numpy as np

from .classifier import MAX_INPUT_CHARS
from .config import Settings
from .schemas import GateState

if TYPE_CHECKING:
    from .storage import Storage

# --- NegEx-style negation gate ------------------------------------------------
# A cue within ±_NEG_WINDOW tokens of an OUTCOME stem marks the report
# negated: "fell 4m. No injury occurred" must never be read as a fracture.
# Negated high-severity-looking reports are forced to gray review — never
# auto-green.
#
# Scope discipline (e2e B1, 2026-09-08 — the gate previously grayed the demo
# hero text on 'without'~'fire' / 'could'~'fire'):
#  - Anchors are OUTCOME stems ONLY. Mechanism/barrier words (fire, fell,
#    LOTO, fire watch) are never anchors: "grinding without fire watch" is an
#    absent-barrier SIGNAL to catch, not an outcome negation to route away.
#  - Counterfactual markers are the near-miss register itself (the corpus is
#    full of "could have been worse" / "almost" rows). They never TRIGGER the
#    gate, and a marker within the window SUPPRESSES the cue~anchor pair it
#    scopes ("no deaths — could have been worse" stays green-leaning).
_NEGATION_CUES = (
    "near miss", "did not", "was not", "were not",
    "didn't", "wasn't", "weren't", "prevented", "avoided",
    "without", "never", "none", "uninjured", "no", "not",
)
# Counterfactual / near-miss register — suppressors, never cues.
_COUNTERFACTUALS = (
    "could have", "would have", "might have", "narrowly", "almost",
    "nearly", "luckily", "fortunately",
)
_NEG_WINDOW = 5
_NEGATION_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in _NEGATION_CUES) + r")\b", re.IGNORECASE
)
_COUNTERFACTUAL_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in _COUNTERFACTUALS) + r")\b", re.IGNORECASE
)

# Outcome stems mirror label_spec.yaml masking stems (data_pipeline/masking.py
# _OUTCOME_PATTERNS — the FROZEN set, mirrored here, not imported) plus the
# plain outcome words harm/hurt/casualty/damage ("no one was hurt",
# "no damage"). Stem = token-prefix match, except "sever" which is token-exact
# to exclude "several" (same tradeoff as the frozen spec).
_OUTCOME_STEMS = (
    "amputat", "fractur", "hospital", "kill", "fatal", "death", "died",
    "unconscious", "unresponsive", "resuscitat", "paraly", "coma", "icu",
    "airlift", "medevac", "surg", "succumb", "injur",
    "harm", "hurt", "casualt", "damage",
)
_SEVER_TOKENS = {"sever", "severe", "severely", "severed", "severs", "severing"}

# --- Drill/simulation filter --------------------------------------------------
# Drills are not precursors (demo red-team SEV2-1). Post-review SEV2-3: the
# cues must read drill/exercise as an EVENT noun, not OIL-register usage —
# "the drill was completed" = the well finished drilling, "exercise caution"
# = boilerplate, "planned test of the BOP" = well-control maintenance; all
# three must stay clean. Bare "drill" still excluded ("drill pipe").
_DRILL_RE = re.compile(
    r"\b(mock drill|fire drill|evacuation drill|emergency drill|safety drill"
    r"|training drill|well[- ]control drill|bop drill|trip drill"
    r"|tabletop|simulated|simulation|rescue practice"
    r"|mock exercise|training exercise|emergency exercise|evacuation exercise"
    r"|training scenario"
    r"|(?:planned|scheduled)\s+(?:drill|exercise|simulation))\b",
    re.IGNORECASE,
)

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _is_anchor_token(tok: str) -> bool:
    if tok in _SEVER_TOKENS:
        return True
    return tok.startswith(_OUTCOME_STEMS)


def gate_min_length(text: str, cfg: Settings) -> GateState:
    """Min-length validator WITH short-codes exception path.

    'LOTO not applied' is 17 chars of pure SIF signal — a bare min-20-char
    validator would eat it (SEV2-2). A short report survives if it hits the
    short-code whitelist (incl. well-control codes BOP/H2S from label_spec) or
    shows all-caps acronym density (codes-heavy terse report).
    """
    stripped = text.strip()
    if len(stripped) >= cfg.min_text_length:
        return GateState(name="min_length", triggered=False, action="badge")
    upper = stripped.upper()
    hits = [c for c in cfg.short_codes if re.search(rf"\b{re.escape(c)}\b", upper)]
    tokens = _TOKEN_RE.findall(stripped)
    caps = [t for t in tokens if len(t) >= 2 and t.isupper()]
    density = len(caps) / len(tokens) if tokens else 0.0
    if hits or density >= 0.4:
        why = f"codes path: {', '.join(hits)}" if hits else f"acronym density {density:.2f}"
        return GateState(
            name="min_length",
            triggered=False,
            action="badge",
            detail=f"short report accepted via {why}",
        )
    return GateState(
        name="min_length",
        triggered=True,
        action="gray",
        detail=f"len={len(stripped)} < {cfg.min_text_length} and no short code",
    )


def _match_token_starts(rx: "re.Pattern[str]", text: str) -> list[int]:
    """char offset -> token index, so cue/suppressor phrase matches map to
    token positions."""
    starts: list[int] = []
    for m in rx.finditer(text):
        char_pos = m.start()
        tok_idx = sum(1 for tm in _TOKEN_RE.finditer(text) if tm.start() <= char_pos) - 1
        starts.append(max(tok_idx, 0))
    return starts


def gate_negation(text: str) -> GateState:
    """NegEx-style gate, outcome-scoped: a negation cue within ±5 tokens of an
    OUTCOME stem marks the report negated -> gray review.

    Mechanism/barrier words are never anchors, and counterfactual near-miss
    markers ("could have", "narrowly", "almost", ...) never trigger — a marker
    within the window suppresses the cue~anchor pair it scopes."""
    tokens = _TOKEN_RE.findall(text.lower())
    if not tokens:
        return GateState(name="negation", triggered=False, action="gray")
    cue_starts = _match_token_starts(_NEGATION_RE, text)
    if not cue_starts:
        return GateState(name="negation", triggered=False, action="gray")
    anchor_idx = [i for i, tok in enumerate(tokens) if _is_anchor_token(tok)]
    suppress_idx = _match_token_starts(_COUNTERFACTUAL_RE, text)
    pairs = [
        (c, a) for c in cue_starts for a in anchor_idx
        if abs(c - a) <= _NEG_WINDOW
        and not any(
            min(c, a) - _NEG_WINDOW <= s <= max(c, a) + _NEG_WINDOW
            for s in suppress_idx
        )
    ]
    if not pairs:
        return GateState(name="negation", triggered=False, action="gray")
    shown = ", ".join(f"'{tokens[c]}'~'{tokens[a]}'" for c, a in pairs[:3])
    return GateState(
        name="negation",
        triggered=True,
        action="gray",
        detail=f"negated outcome language (cue~outcome within {_NEG_WINDOW} tokens): {shown}",
    )


def gate_language(text: str, cfg: Settings) -> GateState:
    """Non-ASCII ratio or Devanagari block -> gray + language badge.
    Report text is never machine-translated live (adjudicated)."""
    if not text:
        return GateState(name="language", triggered=True, action="gray", detail="empty text")
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    ratio = non_ascii / len(text)
    devanagari = bool(_DEVANAGARI_RE.search(text))
    if ratio <= cfg.non_ascii_ratio and not devanagari:
        return GateState(name="language", triggered=False, action="badge")
    tag = "devanagari" if devanagari else "non-ascii"
    return GateState(
        name="language",
        triggered=True,
        action="gray",
        detail=f"language badge [{tag}]: non_ascii_ratio={ratio:.2f} (> {cfg.non_ascii_ratio})",
    )


def gate_confidence(score: float, cfg: Settings) -> GateState:
    """Confidence gray band [tau_lo, tau_hi] — triage score inside routes to review."""
    triggered = cfg.gray_band_low <= score <= cfg.gray_band_high
    return GateState(
        name="confidence",
        triggered=triggered,
        action="gray",
        detail=f"score {score:.3f} in gray band "
        f"[{cfg.gray_band_low}, {cfg.gray_band_high}]" if triggered else "",
    )


def gate_drill(text: str) -> GateState:
    """Drill/simulation filter — drills are not precursors (red-team #8):
    gray + drill badge, never auto-green."""
    hits = sorted({m.group(0).lower() for m in _DRILL_RE.finditer(text)})
    return GateState(
        name="drill",
        triggered=bool(hits),
        action="gray",
        detail=f"drill badge: {', '.join(hits)}" if hits else "",
    )


def gate_near_dup(text: str, storage: "Storage", cfg: Settings,
                  vec: "np.ndarray | None" = None,
                  base_hit: "tuple[int | str, float] | None" = None) -> GateState:
    """Near-duplicate banner over the MiniLM cosine index.

    The index = precomputed training+synthetic corpus (loaded from .npy at
    startup) + everything ingested this session, so a verbatim training-row
    paste is caught (demo red-teamer attack (d)). Exact verbatim re-pastes
    are NOT excluded — that is precisely the "memory, not generalization"
    attack the banner exists for. In the /ingest flow gates run before the
    row's own embedding is stored, so there is no self-match. Threshold is
    MEASURED from the MiniLM embedding curve
    (artifacts/embeddings/threshold_report.md).

    vec/base_hit let the bulk-ingest path pass the row's batch-computed
    embedding and chunk-level corpus-tier top-1 (D25); the merged top-1 over
    base+session tiers is identical to a full nearest() query."""
    if vec is None:
        from .embedder import embed_text  # local import: lazy-loads the model

        vec = embed_text(text)
    if base_hit is None:
        base_hit = storage.nearest_base_batch(np.asarray(vec, dtype=np.float32)[None, :])[0]
    session_hit = storage.nearest_session(vec)
    best: tuple[int | str, float] | None = base_hit
    if session_hit is not None and (best is None or session_hit[1] > best[1]):
        best = session_hit
    if best is not None and best[1] >= cfg.near_dup_threshold:
        rid, sim = best
        return GateState(
            name="near_dup",
            triggered=True,
            action="badge",
            detail=f"near-dup banner: cosine={sim:.3f} with index row {rid} "
            f"(>= {cfg.near_dup_threshold})",
        )
    detail = f"max cosine={best[1]:.3f}" if best is not None else "index empty"
    return GateState(name="near_dup", triggered=False, action="badge", detail=detail)


def gate_well_control_watch(well_control: bool, score: float, flag_thr: float) -> GateState:
    """Well-control watch (audit-fix wave, final_audit_qa.md probe 1): when the
    deterministic well-control/barrier tag fires but the calibrated SIF score
    sits BELOW the flag threshold, the neural model has missed a rare
    high-consequence class (novel Baghjan-class narratives score ~0.03 while
    the verbatim training cards score 0.9+). Automated screening defers:
    gray + routed to human review, never auto-greened. Silent when the score
    clears the threshold (the demo WC cards stay HIGH)."""
    triggered = well_control and score < flag_thr
    return GateState(
        name="well_control_watch",
        triggered=triggered,
        action="gray",
        detail=(
            f"well-control watch: barrier tag fired but triage score {score:.3f} "
            f"< flag threshold {flag_thr:.3f} — rare high-consequence domain, "
            "automated screening defers; routed to human review"
        ) if triggered else "",
    )


def gate_long_input(text: str, cfg: Settings) -> GateState:
    """Long-input info badge: >120 words -> 'chunked' (sliding-window max-pool
    applies, score is length-OOD). Informational badge, never gray. Inputs
    over the hard char cap are scored on their truncated prefix by the
    classifier (post-review SEV2-6) — the badge discloses the cap instead of
    hanging 15.9s on a 200k-char paste."""
    n = len(text.split())
    parts: list[str] = []
    if len(text) > MAX_INPUT_CHARS:
        parts.append(f"too long: input capped at first {MAX_INPUT_CHARS} "
                     f"chars ({len(text)} total)")
    if n > cfg.long_input_words:
        parts.append(f"chunked: {n} words > {cfg.long_input_words}; "
                     "sliding-window max-pool applies (length-OOD)")
    if not parts:
        return GateState(name="long_input", triggered=False, action="badge")
    return GateState(name="long_input", triggered=True, action="badge",
                     detail="; ".join(parts))


def run_gates(text: str, score: float, storage: "Storage", cfg: Settings,
              vec: "np.ndarray | None" = None,
              base_hit: "tuple[int | str, float] | None" = None,
              well_control: bool = False,
              flag_thr: float = 0.5) -> list[GateState]:
    # vec/base_hit (optional) are the bulk-ingest path's batch-computed
    # embedding + corpus-tier top-1 (D25); None = compute per row (the
    # /classify path, unchanged). well_control is the classifier's
    # deterministic barrier tag; flag_thr is its calibrated flag threshold
    # (flag_threshold(clf)) — both feed the well-control watch gate.
    # Order is load-bearing (smoke test addresses drill by index 4);
    # well_control_watch is appended LAST so existing positions hold.
    specs = (
        ("min_length", lambda: gate_min_length(text, cfg)),
        ("negation", lambda: gate_negation(text)),
        ("language", lambda: gate_language(text, cfg)),
        ("confidence", lambda: gate_confidence(score, cfg)),
        ("drill", lambda: gate_drill(text)),
        ("near_dup", lambda: gate_near_dup(text, storage, cfg, vec=vec, base_hit=base_hit)),
        ("long_input", lambda: gate_long_input(text, cfg)),
        ("well_control_watch", lambda: gate_well_control_watch(well_control, score, flag_thr)),
    )
    states: list[GateState] = []
    for name, fn in specs:
        try:
            states.append(fn())
        except Exception as exc:  # a broken gate must never 500 the request
            states.append(
                GateState(
                    name=name,
                    triggered=True,
                    action="gray",
                    detail=f"gate error: {type(exc).__name__}: {exc}",
                )
            )
    return states
