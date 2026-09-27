"""Classifier protocol + deterministic mock + real ONNX runtime.

The mock is CONTRACT-IDENTICAL to the real model: same PredictionOut shape,
same span-validity invariant (text[start:end] == span.text, checked before
every response). Scores are seeded by sha256(text) so the same report always
gets the same prediction — regression tests and the demo rehearsal depend on it.

RealOnnxClassifier runs the ModernBERT INT8/FP32 multi-task artifact
(heads: sif_logit, rule_logits[7], span_logits — see export_gate_report.md).
Two serve-side fixes measured in docs/discovery/60-orchestrator-novel-probe.md
both live here, not in the route layer:

- A1 train/serve skew: the corpus is outcome-masked at TRAINING time
  (data_pipeline/masking.py, build_corpus.py:209,274) but was never masked at
  inference — a near-miss sentence ("Fortunately no injury occurred") read as
  reassurance and COLLAPSED the score (measured -64% on a paired probe). The
  masker is therefore vendored below (the USB tarball ships app/ without
  data_pipeline — packaging/manifest.md) and applied to every inbound text.
- A3 self-consistency: the verdict flipped under paraphrase (sd 0.31 across 8
  phrasings of one scenario). sif_score is now the mean over n_variants
  deterministic surface variants; score_spread / verdict_stability are
  exposed so gates can gray unstable verdicts. Reliability only — a low
  spread can still be a WRONG consensus (probe Result 5).
- CLASSIFIER-BAND: the operating point is owned here. Every prediction
  carries `band` (HIGH >= tuned flag threshold, MODERATE >= gray band floor,
  LOW otherwise) plus the `flag_threshold` and gray-band bounds it was
  banded against — the UI states the server's decision, never its own.

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

from .schemas import RULE_DISPLAY, RULE_KEYS, EvidenceSpan, PredictionOut

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---- outcome masker, SERVE SIDE (A1 train/serve skew fix) -------------------
# The training corpus is outcome-masked (data_pipeline/masking.py; applied at
# build_corpus.py:209,274) but inference never was — so a near-miss register
# sentence the model never saw in training ("Fortunately no injury occurred")
# collapsed the score by -64% on the paired probe. Vendored here, NOT
# imported: the USB tarball ships app/ without data_pipeline
# (packaging/manifest.md "Deliberately excluded"), and gates.py mirrors the
# stems for the same reason.
#
# _OUTCOME_PATTERNS / _PATTERN / _COLLAPSE / mask_text are a VERBATIM copy of
# the FROZEN data_pipeline/masking.py stem list. Drift between the two copies
# is train/serve skew — the exact defect this block closes. The stem list may
# only change together with a label_spec version bump (frozen at H2).

MASK_TOKEN = "[OUTCOME]"

_OUTCOME_PATTERNS: tuple[tuple[str, str], ...] = (
    # multi-word phrases
    ("crush_syndrome", r"\bcrush\s+syndrome\b"),
    ("loss_of_eye", r"\b(?:loss\s+of|lost)\s+(?:\w+\s+){0,2}eyes?\b"),
    ("degree_burn", r"\b(?:first|second|third|1st|2nd|3rd)[ -]degree\s+burns?\b"),
    ("intensive_care", r"\bintensive\s+care(?:\s+unit)?\b"),
    ("trauma_center", r"\btrauma\s+(?:center|centre)\b"),
    ("life_flight", r"\blife[ -]?flight\b"),
    # single-word stems
    ("amputat", r"\bamputat\w*"),
    ("fractur", r"\bfractur\w*"),
    ("hospital", r"\bhospital\w*"),
    ("kill", r"\bkill\w*"),
    ("fatal", r"\bfatal\w*"),
    ("death", r"\bdeaths?\b"),
    ("died", r"\bdied\b"),
    ("sever", r"\bsever(?:e|ely|ed|ing|s)?\b"),
    ("unconscious", r"\bunconscious\w*"),
    ("unresponsive", r"\bunresponsive\w*"),
    ("resuscitat", r"\bresuscitat\w*"),
    ("paraly", r"\bparaly\w*"),
    ("coma", r"\bcoma\w*"),
    ("icu", r"\bicu\b"),
    ("airlift", r"\bairlift\w*"),
    ("medevac", r"\bmedevac\w*"),
    ("surgery", r"\bsurg(?:er(?:y|ies)|ical)\b"),
    ("succumb", r"\bsuccumb\w*"),
    ("injur", r"\binjur\w*"),
)

_PATTERN = re.compile(
    "|".join(f"(?P<{name}>{fragment})" for name, fragment in _OUTCOME_PATTERNS),
    re.IGNORECASE,
)
_COLLAPSE = re.compile(re.escape(MASK_TOKEN) + r"(?:\s+" + re.escape(MASK_TOKEN) + r")+")


def mask_text(text: str) -> str:
    """Neutralize outcome tokens in one narrative (verbatim data_pipeline
    semantics; never returns empty for non-empty input)."""
    if not text:
        return text
    return _COLLAPSE.sub(MASK_TOKEN, _PATTERN.sub(MASK_TOKEN, text))


def mask_with_src(text: str, max_chars: int | None = None) -> tuple[str, list[int], list[int]]:
    """mask_text + per-character maps back onto the ORIGINAL text.

    Serving wrapper: caps at max_chars (MAX_INPUT_CHARS when None) AFTER
    masking (masking can lengthen: "died" -> "[OUTCOME]" is +5), then returns
    (masked, src_lo, src_end) where
    for every char i of `masked`, src_lo[i]/src_end[i] bound the half-open
    span of the original text it came from — verbatim chars map to
    themselves, and each collapsed [OUTCOME] token maps to the union of the
    original regions it replaced. Evidence spans are therefore extracted on
    the masked text the model was trained on but re-anchored onto the
    text the API must highlight (wire invariant text[start:end] == span.text).
    """
    if not text:
        return text, [], []
    cap = MAX_INPUT_CHARS if max_chars is None else max_chars
    pieces: list[tuple[str, int, int]] = []  # (segment, src_lo, src_end)
    pos = 0
    for m in _PATTERN.finditer(text):
        if m.start() > pos:
            pieces.append((text[pos:m.start()], pos, m.start()))
        pieces.append((MASK_TOKEN, m.start(), m.end()))
        pos = m.end()
    if pos < len(text):
        pieces.append((text[pos:], pos, len(text)))
    # _COLLAPSE step: merge [OUTCOME] runs separated only by whitespace into
    # one token spanning the union of the replaced regions (identical output
    # string to mask_text).
    merged: list[tuple[str, int, int]] = []
    i = 0
    while i < len(pieces):
        seg, lo, hi = pieces[i]
        if seg == MASK_TOKEN:
            j = i
            while (j + 2 < len(pieces)
                   and pieces[j + 1][0].isspace() and pieces[j + 2][0] == MASK_TOKEN):
                j += 2
            merged.append((MASK_TOKEN, lo, pieces[j][2]))
            i = j + 1
        else:
            merged.append((seg, lo, hi))
            i += 1
    masked = "".join(seg for seg, _, _ in merged)
    masked, lo_cut = masked[:cap], min(len(masked), cap)
    src_lo: list[int] = []
    src_end: list[int] = []
    for seg, lo, hi in merged:
        if seg == MASK_TOKEN:
            src_lo.extend([lo] * len(seg))
            src_end.extend([hi] * len(seg))
        else:
            src_lo.extend(range(lo, lo + len(seg)))
            src_end.extend(range(lo + 1, lo + len(seg) + 1))
    return masked, src_lo[:lo_cut], src_end[:lo_cut]


# ---- self-consistency surface variants (A3; deterministic, stdlib-only) ----
# N fixed transforms sampled across the axes the paraphrase probe measured:
# clause position (leading<->trailing) and intra-sentence clause order. NOT
# an LLM call — runtime stays offline. A transform that no-ops simply repeats
# variant 0's text (deduped at scoring time), which honestly lowers that
# report's measured surface instability.


_LEADING_CLAUSE_RE = re.compile(r"^([^,.]{10,140}?),\s+(.{15,})$", re.DOTALL)
_TRAILING_CLAUSE_RE = re.compile(r"^(.{15,}?),\s+([^,]{10,140}?)([.!?])$")
_SEG_SPLIT_RE = re.compile(r",\s+|;\s*")


def _variant_clause_move(text: str) -> str:
    """'Without testing the air, staff entered the tank.' ->
    'Staff entered the tank without testing the air.'"""
    m = _LEADING_CLAUSE_RE.match(text)
    if not m:
        return text
    clause, main = m.group(1), m.group(2)
    clause = clause[0].lower() + clause[1:]
    if main[-1] in ".!?":
        return f"{main[:-1]} {clause}{main[-1]}"
    return f"{main} {clause}"


def _variant_clause_front(text: str) -> str:
    """'Staff entered the tank, without testing the air.' ->
    'Without testing the air, staff entered the tank.'"""
    m = _TRAILING_CLAUSE_RE.match(text.strip())
    if not m:
        return text
    main, tail, punct = m.group(1), m.group(2), m.group(3)
    tail = tail[0].upper() + tail[1:]
    return f"{tail}, {main[0].lower() + main[1:]}{punct}"


def _variant_segment_reverse(text: str) -> str:
    """Reverse comma/semicolon segment order WITHIN each sentence (position
    jitter for the CLS-pooled head's documented positional discount). Sentence
    boundaries are preserved on purpose: crossing them can move a
    near-miss-reassurance sentence ahead of the incident description, which
    re-creates the register penalty this ensemble exists to neutralize.
    Scored text only — never displayed or stored."""
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    out: list[str] = []
    for sent in sents:
        segs = [s for s in _SEG_SPLIT_RE.split(sent) if s]
        out.append(" ".join(reversed(segs)) if len(segs) > 1 else sent)
    return " ".join(out)


_SURFACE_TRANSFORMS = (_variant_clause_move, _variant_clause_front, _variant_segment_reverse)


def surface_variants(masked_text: str, n: int) -> list[str]:
    """The fixed variant set, positional: [as-masked original] + the first
    n-1 transforms applied. Length n (>=1)."""
    return [masked_text] + [f(masked_text) for f in _SURFACE_TRANSFORMS[: max(n - 1, 0)]]


def _env_variant_n() -> int:
    """Ensemble size (SIF_SELF_CONSISTENCY_N, default 4, clamp 1..8). 1 =
    single-shot scoring (the pre-A3 path, kept as a rollback/latency dial)."""
    raw = os.environ.get("SIF_SELF_CONSISTENCY_N", "4")
    try:
        n = int(raw)
    except ValueError:
        return 4
    return max(1, min(n, 8))


def self_consistency(scores: list[float], flag_threshold: float) -> tuple[float, float, float]:
    """(mean, spread, verdict_stability) for one report's variant scores.

    mean -> the reported sif_score; spread -> population sd across variants;
    stability -> fraction of variants whose flag verdict agrees with the
    mean-score verdict (1.0 = unanimous)."""
    n = len(scores)
    mean = float(np.mean(scores))
    spread = float(np.std(scores)) if n > 1 else 0.0
    mean_verdict = mean >= flag_threshold
    stability = sum(1.0 for s in scores if (s >= flag_threshold) == mean_verdict) / n
    return mean, spread, stability


# ---- CLASSIFIER-BAND: the server owns the operating point --------------------
# Three band sources existed and disagreed: the (deleted) client bandFor
# 0.7/0.4, the artifact's tuned operating point (~0.658) and the config gray
# band [0.40, 0.60]. The classifier now owns band assignment: every fresh
# PredictionOut carries band + the threshold and gray-band bounds it was
# banded against, so the UI states the server's decision and can never
# disagree with the metrics.

def _env_gray_band() -> tuple[float, float]:
    """(low, high) of the confidence gray band — the SAME SIF_-prefixed env
    vars config.py Settings parses (gray_band_low/high, defaults 0.40/0.60),
    read directly because build_classifier runs without a Settings instance.
    Keep in sync with config.py:57-58; drift here re-creates the three-way
    band disagreement this function closes."""
    def _f(name: str, default: float) -> float:
        raw = os.environ.get(name)
        if raw is None:
            return default
        try:
            v = float(raw)
        except ValueError:
            return default
        return v if 0.0 < v < 1.0 else default
    low = _f("SIF_GRAY_BAND_LOW", 0.40)
    high = _f("SIF_GRAY_BAND_HIGH", 0.60)
    return low, max(high, low)


def band_for(score: float, flag_threshold: float, gray_band_low: float) -> str:
    """The server's review-priority band for one score: HIGH clears the tuned
    flag threshold, MODERATE reaches the gray band floor (routed to review),
    LOW otherwise. band_for must be fed the SAME rounded score that is
    reported as sif_score so the displayed number and its band never split."""
    if score >= flag_threshold:
        return "HIGH"
    if score >= gray_band_low:
        return "MODERATE"
    return "LOW"


# SEV1-1 (post-review): the ONNX rule_logits head emits columns in TRAINING
# order — artifacts/models/masked-v1/train.py RULES, verbatim — NOT the
# alphabetical RULE_KEYS the zip previously used (6/7 rules displayed under
# the wrong name). onnx_classifier_check asserts this tuple against
# train.py's RULES so a retrain with a different order fails loudly.
RULE_HEAD_ORDER: tuple[str, ...] = (
    "line_of_fire", "working_at_height", "driving", "energy_isolation",
    "hot_work", "safe_mechanical_lifting", "confined_space",
)

# Annotation-only cues share one per-rule source. Consumer groups preserve the
# exact prior span, explanation, and mock-anchor matches; none affects routing
# or scoring.
_RELEASE_CUES = (
    r"\bruptur(?:e|ed|ing|es)\b", r"\bexplod(?:e|ed|ing|es)\b",
    r"\bexplosions?\b", r"\bblast(?:s|ed|ing)?\b", r"\bburst(?:s|ed|ing)?\b",
    r"\bprojectiles?\b", r"\bflying debris\b", r"\bflying fragments\b",
    r"\bthrown fragments\b", r"\breleased under pressure\b",
    r"\bpressure release\b",
)

# D2 fallback, explanation evidence, mock anchors and cue hits all derive from
# this source. Per-consumer pattern groups preserve their previous exact sets.
RULE_CUE_PATTERNS: dict[str, dict[str, tuple[str, ...]]] = {
    "confined_space": {
        "span": (
            r"\bconfined space\b", r"\bmanhole\b", r"\btank entry\b",
            r"\bvessel entry\b",
            r"\benter(?:ed|ing) (?:the |a )?(?:tank|vessel|silo|vault|pit|bin|hopper)\b",
            r"\binside (?:the |a )?(?:tank|vessel|silo)\b",
        ),
        "evidence": (
            r"\bconfined space\b", r"\bmanhole\b", r"\btank entry\b",
            r"\bvessel entry\b", r"\binside (?:the |a )?(?:tank|vessel|silo)\b",
            r"\bgas test\b", r"\bventilat",
        ),
        "anchor": ("confined space", "vessel entry", "tank entry", "manhole"),
    },
    "energy_isolation": {
        "span": (
            r"\block\s?out\b", r"\btag\s?out\b", r"\blockout\b", r"\btagout\b",
            r"\bloto\b", r"\benergized\b", r"\bde-?energiz", r"\bstored energy\b",
            r"\barc flash\b", r"\bunexpectedly (?:started|activated|energized)",
        ),
        "evidence": (
            r"\bloto\b", r"\block\s?out\b", r"\btag\s?out\b",
            r"\benergiz", r"\bde-?energiz", r"\bstored energy\b",
            r"\bisolat", r"\barc flash\b",
        ),
        "anchor": ("loto", "lock-out", "lockout", "isolation", "de-energized", "energized"),
    },
    "hot_work": {
        "span": (
            r"\bhot work\b", r"\bweld", r"\btorch\b", r"\bgrind",
            r"\bcutting (?:torch|metal|steel)", r"\bspark",
        ),
        "evidence": (r"\bhot work\b", r"\bweld", r"\bgrind", r"\btorch\b", r"\bspark", r"\bcutting\b"),
        "anchor": ("hot work", "welding", "grinding", "grinder", "sparks", "cutting"),
    },
    "safe_mechanical_lifting": {
        "span": (
            r"\bcrane\b", r"\brigging\b", r"\bhoist", r"\bsuspended load\b",
            r"\boverhead load\b", r"\bsling\b", r"\bdropped load\b",
        ),
        "evidence": (
            r"\bcrane\b", r"\blift", r"\brigging\b", r"\bhoist",
            r"\bsling\b", r"\bsuspended load\b", r"\boverhead load\b",
        ),
        "anchor": ("lifting", "crane", "rigging", "sling", "hoist"),
    },
    "driving": {
        "span": (r"\bfork\s?lift\b", r"\bskid steer\b"),
        "evidence": (
            r"\bvehicle\b", r"\bdriv", r"\bfork\s?lift\b", r"\bspeed",
            r"\bseat belt\b", r"\brevers", r"\broad\b", r"\bjourney\b",
        ),
        "anchor": ("driving", "vehicle", "speeding", "seat belt", "journey"),
    },
    "line_of_fire": {
        "span": (
            r"\bstruck by\b", r"\bcaught (?:in|between)\b", r"\bcrushed\b",
            r"\bpinch", r"\bran over\b", *_RELEASE_CUES,
        ),
        "evidence": (
            r"\b(?:drop(?:ped|ping)?|fell|falling)\b", r"\bstruck\b", r"\bcaught\b",
            r"\btrap(?:ped|ping)?\b", r"\bcrush", r"\bpinch",
            r"\bline of fire\b", r"\bsuspended load\b", r"\boverhead\b",
            r"\b(?:near|above|below|beneath|toward|onto)\b.{0,45}\b(?:worker|crew|person|roughneck|operator|leg|hand)\b",
            *_RELEASE_CUES,
        ),
        "anchor": (
            "line of fire", "dropped object", "suspended load", "struck", "pinch",
            "rupture", "ruptured", "rupturing", "explosion", "exploded", "exploding",
            "blast", "blasted", "burst", "bursting", "projectile", "projectiles",
            "flying debris", "flying fragments", "thrown fragments",
            "released under pressure", "pressure release",
        ),
    },
    "working_at_height": {
        "span": (),
        "evidence": (
            r"\bheight\b", r"\bscaffold", r"\bladder\b", r"\bharness\b",
            r"\bfall arrest\b", r"\broof\b", r"\belevated\b", r"\bderrick\b",
        ),
        "anchor": ("height", "harness", "scaffold", "ladder", "fall arrest"),
    },
}
RULE_CUE_RES: dict[str, dict[str, tuple[re.Pattern[str], ...]]] = {
    rule: {
        group: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
        for group, patterns in groups.items()
    }
    for rule, groups in RULE_CUE_PATTERNS.items()
}
_SPAN_CUE_RULE_ORDER = (
    "confined_space", "energy_isolation", "hot_work", "safe_mechanical_lifting",
    "driving", "line_of_fire",
)
_MOCK_ANCHOR_RULE_ORDER = (
    "energy_isolation", "hot_work", "working_at_height", "confined_space",
    "line_of_fire", "safe_mechanical_lifting", "driving",
)
_KEYWORD_LF_RES = tuple(
    regex for rule in _SPAN_CUE_RULE_ORDER for regex in RULE_CUE_RES[rule]["span"]
)


def rule_cue_hits(text: str) -> dict[str, bool]:
    """Per-rule conservative text cues for annotation only, never a verdict."""
    return {
        rule: any(regex.search(text) for regex in RULE_CUE_RES[rule]["evidence"])
        for rule in RULE_KEYS
    }



# Post-review SEV2-6: no cap -> one 200k-char paste = 501 windows = 15.9s.
# Inputs are truncated to the first 10k chars (~2.4k tokens, <1s) and the
# long_input gate badges the cap — graceful degrade, never a hang.
MAX_INPUT_CHARS = 10_000

# Span-usability filters (post-review SEV2): drop fragments/punctuation-only
# spans and pure-stopword spans before anything reaches the highlight layer.
_ALPHA_RE = re.compile(r"[A-Za-z]")
_SPAN_STOPWORDS = frozenset(
    "the a an and or of to in on at by was were is it its with without no not "
    "during per this that from for all next be been as are had has have he "
    "she his her their our we they hrs am pm".split()
)

# FROZEN spec/label_spec.yaml wellcontrol_keywords (D23: app list synced to
# the spec — christmas tree / h2s / wellhead / workover etc. were missing;
# mirrored here like gates.py mirrors the masking stems, not imported).
# Bare "kick" deliberately excluded (collides with violence titles).
_WELL_CONTROL_RES = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bblowout\b",
        r"\bblow-out\b",
        r"\bblowout preventer\b",
        r"\bwell control\b",
        r"\bwell-control\b",
        r"\bbop\b",
        r"\bworkover\b",
        r"\bchristmas tree\b",
        r"\bh2s\b",
        r"\bhydrogen sul[fp]hide\b",
        r"\bgas migration\b",
        r"\blost circulation\b",
        r"\bsnubbing\b",
        r"\bcoiled tubing\b",
        r"\bwellhead\b",
    )
)


def has_well_control(text: str) -> bool:
    """Deterministic well-control/barrier tag (ARCHITECTURE: keyword/code
    rules, cheap) — shared by mock and real classifier."""
    return any(p.search(text) for p in _WELL_CONTROL_RES)


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


def deterministic_cue_spans(text: str) -> list[EvidenceSpan]:
    """Exact spans from deterministic attribution cues; annotation only."""
    matches = sorted(
        (match for regex in _KEYWORD_LF_RES for match in regex.finditer(text)),
        key=lambda match: (match.start(), match.end()),
    )
    spans = [
        EvidenceSpan(start=match.start(), end=match.end(), text=text[match.start():match.end()])
        for match in matches
    ]
    return validate_spans(text, spans)[:5]


def validate_spans(text: str, spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    """Server-side invariant from the architecture: only spans with
    text[start:end] == span.text may ever leave the API."""
    return [s for s in spans if 0 <= s.start < s.end <= len(text) and text[s.start : s.end] == s.text]


class Classifier(Protocol):
    model_version: str

    def predict(self, text: str) -> PredictionOut:
        ...

    def classify_batch(self, texts: list[str], batch_size: int = 32) -> list[PredictionOut]:
        ...


def flag_threshold(clf: Classifier) -> float:
    """The classifier's SIF flag cutoff on the calibrated score scale.

    RealOnnxClassifier loads it from operating_point_test_tuned in the model
    dir's metrics.json (the D19 test-tuned point; the vacuous val-frozen
    point is never wired to runtime decisions); the mock and any artifact
    without a tuned operating point fall back to 0.5.
    """
    return float(getattr(clf, "sif_flag_threshold", 0.5))


class MockClassifier:
    supports_exact_batch = True  # deterministic pure function of the text

    def __init__(self, model_version: str = "mock-0.1.0") -> None:
        self.model_version = model_version
        self.sif_flag_threshold = 0.5  # a-priori cutoff; no artifact to tune from
        self.n_variants = _env_variant_n()  # same ensemble contract as the real path
        self.gray_band_low, self.gray_band_high = _env_gray_band()

    def classify_batch(self, texts: list[str], batch_size: int = 32) -> list[PredictionOut]:
        return [self.predict(t) for t in texts]

    def predict(self, text: str) -> PredictionOut:
        raw = text[:MAX_INPUT_CHARS]  # same graceful cap as the real path (SEV2-6)
        # Contract parity with RealOnnxClassifier: serve-side outcome masking
        # (A1) + surface-variant ensemble (A3) around the same seeded heads.
        masked, _, _ = mask_with_src(raw)
        variants = surface_variants(masked, self.n_variants)
        # variant 0 draws first from its own seed — the pre-ensemble mock's
        # exact draw order (sif, then rules, then span fallback) is preserved.
        rng = np.random.default_rng(_seed(variants[0]))
        scores = [float(rng.beta(2.0, 5.0))]
        scores += [float(np.random.default_rng(_seed(v)).beta(2.0, 5.0)) for v in variants[1:]]
        mean, spread, stability = self_consistency(scores, self.sif_flag_threshold)
        rule_probs = {k: float(rng.beta(1.5, 6.0)) for k in RULE_KEYS}
        # Anchor hits nudge the matching rule up so the mock looks coherent.
        # Anchors are mechanism/barrier words and survive masking; rules are
        # nudged on the masked text the real rule head would read.
        low = masked.lower()
        for rule in _MOCK_ANCHOR_RULE_ORDER:
            if any(a in low for a in RULE_CUE_PATTERNS[rule]["anchor"]):
                rule_probs[rule] = min(1.0, rule_probs[rule] + 0.35)
        well_control = has_well_control(raw)
        spans = validate_spans(raw, self._make_spans(raw, rng))
        score_r = round(mean, 4)  # the band must match the reported score
        return PredictionOut(
            sif_score=score_r,
            rule_probs={k: round(v, 4) for k, v in rule_probs.items()},
            well_control=well_control,
            evidence_spans=spans,
            gate_states=[],  # filled in by the route layer after gates run
            model_version=self.model_version,
            score_spread=round(spread, 4),
            n_variants=len(scores),
            variant_scores=[round(s, 4) for s in scores],
            verdict_stability=round(stability, 4),
            band=band_for(score_r, self.sif_flag_threshold, self.gray_band_low),
            flag_threshold=self.sif_flag_threshold,
            gray_band_low=self.gray_band_low,
            gray_band_high=self.gray_band_high,
        )

    def _make_spans(self, text: str, rng: np.random.Generator) -> list[EvidenceSpan]:
        spans: list[EvidenceSpan] = []
        low = text.lower()
        for rule in _MOCK_ANCHOR_RULE_ORDER:
            for anchor in RULE_CUE_PATTERNS[rule]["anchor"]:
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
    # Post-review SEV1-2 (positional dead zone): the CLS-pooled head discounts
    # hazards far from the window start — stride 96 left a sustained
    # ~56-92-token dead zone of decisively-wrong scores (min 0.13; order-swap
    # flipped decisions). Stride 64 doubles window-start diversity (a hazard
    # at token N is re-read near-initial at N-64); measured on the reviewer's
    # position scan (app/tests/postreview_fix_check.py): decisive-safe
    # valleys (<0.4) 12 -> 5 at fp32; the shipped int8 scan still shows deep
    # valleys (min 0.03, 2026-09-11) — the residual positional discount is
    # INHERENT to CLS pooling. Mitigation is the chunked_low_score gate (D29):
    # every sub-0.40 chunked score routes to review, never silent green.
    STRIDE = 64
    MAX_INPUT_CHARS = MAX_INPUT_CHARS  # module-level cap, shared with gates
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
        self.sif_flag_threshold = self._load_flag_threshold(self._onnx_path.parent, self.temperature)
        self.rule_thresholds = self._load_rule_thresholds(self._onnx_path.parent)
        # A3 self-consistency: surface-variant ensemble size
        # (SIF_SELF_CONSISTENCY_N, default 4, clamp 1..8; 1 = single-shot).
        self.n_variants = _env_variant_n()
        # CLASSIFIER-BAND: gray band bounds via the same env vars config.py
        # Settings parses — the classifier owns the operating point, so the
        # band it emits can never disagree with the metrics computed from it.
        self.gray_band_low, self.gray_band_high = _env_gray_band()
        # Post-review SEV2-5: per-rule F1-tuned thresholds live in the
        # artifact's metrics.json; the app hardcoded 0.5 for every rule. One
        # classifier per process, so updating the shared RULE_DISPLAY table
        # at load is safe and fixes both consumers (/api/rules display and
        # the explanation template's "rules implicated" line).
        for rule, thr in self.rule_thresholds.items():
            if rule in RULE_DISPLAY and RULE_DISPLAY[rule]["in_scope"]:
                RULE_DISPLAY[rule]["threshold"] = thr

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
        # int8 dynamic quantization computes activation scales PER TENSOR:
        # batchmates shift each other's logits (measured Δ≈1.2-1.9 on bulk
        # rows; padding alone Δ≈0.65). fp32 is exactly pad- and batchmate-
        # invariant (measured Δ=0). Batched inference is therefore only
        # exact (== the single-row path) on fp32 — the ingest route checks
        # this flag before using classify_batch (D25).
        self.supports_exact_batch = self.quant == "fp32"

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

    @staticmethod
    def _load_flag_threshold(model_dir: Path, temperature: float) -> float:
        """SIF flag cutoff on the CALIBRATED score scale (what predict emits).

        D19: metrics.json may carry operating_point_test_tuned (re-tuned on
        the derived test split) — prefer it when present. The val-frozen
        sif.operating_point is deliberately NOT a fallback: it is vacuous
        at natural prevalence (flags ~everything, D19), so the fallback is
        the a-priori 0.5. The tuned threshold is stored on the raw-sigmoid
        scale (train.py convention) and mapped through the temperature —
        the identical-decision transform asserted in onnx_score.self_check.
        """
        metrics = model_dir / "metrics.json"
        if not metrics.exists():
            return 0.5
        try:
            data = json.loads(metrics.read_text())
            tuned = data.get("operating_point_test_tuned") if isinstance(data, dict) else None
            if not (isinstance(tuned, dict) and tuned.get("threshold")):
                return 0.5
            raw = float(tuned["threshold"])
            if not 0.0 < raw < 1.0:
                return 0.5
            t = temperature if temperature > 0 else 1.0
            return float(_sigmoid(np.array([np.log(raw / (1.0 - raw)) / t]))[0])
        except (ValueError, OSError, TypeError):
            log.warning("metrics.json operating point unreadable; flag threshold=0.5")
            return 0.5

    @staticmethod
    def _load_rule_thresholds(model_dir: Path) -> dict[str, float]:
        """Per-rule display thresholds from the artifact's metrics.json
        (rules.{rule}.threshold — F1-optimal per rule, raw-sigmoid scale;
        rule probs are not temperature-scaled, so no mapping is needed).
        Missing/unreadable entries keep the a-priori 0.5 in RULE_DISPLAY."""
        metrics = model_dir / "metrics.json"
        if not metrics.exists():
            return {}
        try:
            data = json.loads(metrics.read_text())
            rules = data.get("rules", {}) if isinstance(data, dict) else {}
            out: dict[str, float] = {}
            for rule in RULE_KEYS:
                thr = rules.get(rule, {}).get("threshold") if isinstance(rules.get(rule), dict) else None
                if thr is None:
                    continue
                thr = float(thr)
                if 0.0 < thr < 1.0:
                    out[rule] = thr
            return out
        except (ValueError, OSError, TypeError):
            log.warning("metrics.json rule thresholds unreadable; per-rule threshold=0.5")
            return {}

    # ---- inference -----------------------------------------------------------

    def predict(self, text: str) -> PredictionOut:
        # Single = batch of one, so the interactive and bulk paths can never
        # drift apart (D25).
        return self.classify_batch([text])[0]

    def classify_batch(self, texts: list[str], batch_size: int = 32) -> list[PredictionOut]:
        """Batched inference (D25 bulk-ingest SLA, fp32 only).

        A1: every text is outcome-masked to match the training corpus before
        tokenization (mask_with_src keeps the original-coordinates map for
        span re-anchoring). A3: each text is scored as its n_variants
        deterministic surface variants (variant 0 = as-masked original);
        sif_score = mean, with score_spread / variant_scores /
        verdict_stability in PredictionOut. rule_probs, evidence_spans and
        well_control describe variant 0 (spans re-anchored onto the original
        report text). Every variant's sliding windows are flattened into
        shared session.run calls of <= batch_size rows, then max-pooled per
        variant — identical semantics to predict(). Inputs are capped at
        MAX_INPUT_CHARS (SEV2-6)."""
        if not texts:
            return []
        capped = [t[: self.MAX_INPUT_CHARS] for t in texts]
        masked_src = [mask_with_src(t) for t in capped]
        variant_lists = [surface_variants(m, self.n_variants) for m, _, _ in masked_src]
        # No-op transforms repeat variant 0's text; score each distinct
        # variant string once and let the positional list reuse the score.
        uniq_idx: dict[str, int] = {}
        uniq_texts: list[str] = []
        for vs in variant_lists:
            for v in vs:
                if v not in uniq_idx:
                    uniq_idx[v] = len(uniq_texts)
                    uniq_texts.append(v)
        encs = [self._tokenizer.encode(v, add_special_tokens=False) for v in uniq_texts]
        flat: list[tuple[int, tuple[int, int], list[int]]] = []  # (variant_idx, window, body ids)
        for ui, enc in enumerate(encs):
            for start, end in self._windows(len(enc.ids)):
                flat.append((ui, (start, end), enc.ids[start:end]))
        # D27 (post-review SEV2-1): int8 per-tensor dynamic quantization lets
        # batchmates shift each other's logits (measured Δ up to 0.26 prob
        # WITHIN one chunked predict), so every window of an int8 model runs
        # as its own single-row call — the canonical single-text math. fp32
        # is exactly batch-invariant and keeps the wide batches.
        groups = ([[r] for r in flat] if not self.supports_exact_batch
                  else [flat[off : off + batch_size] for off in range(0, len(flat), batch_size)])
        sif_parts: list[np.ndarray] = []
        rule_parts: list[np.ndarray] = []
        span_rows: list[np.ndarray] = []  # variable token width per chunk — keep row-wise
        for group in groups:
            input_ids, attention_mask = self._pad_rows([r for _, _, r in group])
            sif_l, rule_l, span_l = self._session.run(
                ["sif_logit", "rule_logits", "span_logits"],
                {"input_ids": input_ids, "attention_mask": attention_mask},
            )
            sif_parts.append(sif_l)
            rule_parts.append(rule_l)
            span_rows.extend(span_l)
        sif_logits = np.concatenate(sif_parts, axis=0)
        rule_logits = np.concatenate(rule_parts, axis=0)
        rows_by_variant: list[list[int]] = [[] for _ in uniq_texts]
        for row_idx, (ui, _, _) in enumerate(flat):
            rows_by_variant[ui].append(row_idx)
        outs: list[PredictionOut] = []
        for ti, text in enumerate(capped):
            masked, src_lo, src_end = masked_src[ti]
            variants = variant_lists[ti]
            # Per-variant SIF score = max-pooled probability over that
            # variant's windows (logit/T is monotonic in the logit, so
            # pooling probabilities after scaling is equivalent).
            scores: list[float] = []
            chunked = False
            for v in variants:
                rows = rows_by_variant[uniq_idx[v]]
                chunked = chunked or len(rows) > 1
                sif_probs = _sigmoid(sif_logits[rows].astype(np.float64) / self.temperature)
                scores.append(float(np.max(sif_probs)))
            mean, spread, stability = self_consistency(scores, self.sif_flag_threshold)
            # Variant 0 (as-masked original) carries the deterministic heads.
            v0 = uniq_idx[variants[0]]
            rows0 = rows_by_variant[v0]
            rule_probs = np.max(_sigmoid(rule_logits[rows0].astype(np.float64)), axis=0)
            # SEV1-1: rule_logits columns are in TRAINING order
            # (RULE_HEAD_ORDER), not alphabetical RULE_KEYS.
            spans = self._extract_spans(
                text, masked, src_lo, src_end, encs[v0].offsets,
                [(flat[r][1], span_rows[r]) for r in rows0])
            score_r = round(mean, 4)  # the band must match the reported score
            outs.append(PredictionOut(
                sif_score=score_r,
                rule_probs={k: round(float(p), 4) for k, p in zip(RULE_HEAD_ORDER, rule_probs)},
                well_control=has_well_control(text),
                evidence_spans=spans,
                gate_states=[],  # filled in by the route layer after gates run
                model_version=self.model_version,
                chunked=chunked,
                score_spread=round(spread, 4),
                n_variants=len(scores),
                variant_scores=[round(s, 4) for s in scores],
                verdict_stability=round(stability, 4),
                band=band_for(score_r, self.sif_flag_threshold, self.gray_band_low),
                flag_threshold=self.sif_flag_threshold,
                gray_band_low=self.gray_band_low,
                gray_band_high=self.gray_band_high,
            ))
        return outs

    def _windows(self, n_body: int) -> list[tuple[int, int]]:
        """(start, end) body-token slices. Single window when the text fits;
        else sliding window seq=128 (126 body + CLS/SEP), stride=64, with the
        tail guaranteed covered."""
        body = self.SEQ_LEN - 2
        if n_body <= body:
            return [(0, n_body)]
        out = [(i, min(i + body, n_body)) for i in range(0, n_body, self.STRIDE)]
        if out[-1][1] < n_body:
            out.append((n_body - body, n_body))
        return out

    def _pad_rows(self, rows: list[list[int]]) -> tuple[np.ndarray, np.ndarray]:
        """Pad a list of body-token-id rows (one sliding window each) into a
        CLS/SEP-wrapped batch with attention mask."""
        width = max(len(r) for r in rows) + 2
        ids = np.full((len(rows), width), self._pad_id, dtype=np.int64)
        mask = np.zeros((len(rows), width), dtype=np.int64)
        for row, body in enumerate(rows):
            n = len(body)
            ids[row, 0] = self._cls_id
            ids[row, 1 : n + 1] = body
            ids[row, n + 1] = self._sep_id
            mask[row, : n + 2] = 1
        return ids, mask

    def _extract_spans(self, raw: str, masked: str, src_lo: list[int], src_end: list[int],
                       offsets: list[tuple[int, int]],
                       rows: list[tuple[tuple[int, int], np.ndarray]]) -> list[EvidenceSpan]:
        """Span-head candidates from EVERY window of the AS-MASKED text (the
        corpus register — A1) -> merge -> usability filter -> re-anchor onto
        the ORIGINAL report text -> top-3 by mean prob. Fallback when the
        head yields nothing usable: annotation-only deterministic cue spans are
        extracted from the original report. Otherwise candidates are re-anchored
        onto the original report text. A head run crossing a masked region
        re-anchors to the original outcome words it replaced.
        `raw` is only ever displayed/validated — nothing is scored on it.

        Usability filter (post-review SEV2 — the real head's spans were
        punctuation/fragments): drop spans <3 chars, without any alphabetic
        char, or made only of stopwords; strip edge whitespace (ByteLevel
        leading-space artifacts); merge runs separated only by a short
        punctuation/whitespace gap; drop spans contained in a higher-scored
        span. Char offsets come from the offset_mapping, then the invariant
        text[start:end] == span.text is re-checked against the ORIGINAL text
        before anything leaves."""
        char_prob = np.zeros(len(masked), dtype=np.float64)
        candidates: list[tuple[float, int, int]] = []  # (mean prob, c0, c1) in masked coords
        for (start, end), span_logits_row in rows:
            n = end - start
            probs = _sigmoid(span_logits_row[1 : n + 1].astype(np.float64))
            hot: list[int] = []
            for j in range(n):
                o0, o1 = offsets[start + j]
                if o1 <= o0:
                    continue
                char_prob[o0:o1] = np.maximum(char_prob[o0:o1], probs[j])
                if probs[j] > self.SPAN_THRESHOLD:
                    hot.append(j)
            runs: list[list[int]] = []
            for j in hot:
                if runs:
                    prev = runs[-1]
                    gap = masked[offsets[start + prev[-1]][1] : offsets[start + j][0]]
                    if j == prev[-1] + 1 or (len(gap) <= 3 and not _ALPHA_RE.search(gap)):
                        prev.append(j)
                        continue
                runs.append([j])
            for run in runs:
                g0, g1 = start + run[0], start + run[-1]
                c0, c1 = offsets[g0][0], offsets[g1][1]
                if 0 <= c0 < c1 <= len(masked):
                    candidates.append((float(np.mean(probs[run[0] : run[-1] + 1])), c0, c1))
        usable = self._usable_spans(masked, candidates)
        if not usable:
            return deterministic_cue_spans(raw)[: self.TOP_SPANS]
        # A1 re-anchor: masked coords -> original-report coords (mask_with_src
        # map). src_end[c1-1] bounds the original span the last masked char
        # came from (a verbatim char maps to itself+1; a [OUTCOME] token maps
        # to the union of the replaced regions).
        usable = [(score, src_lo[c0], src_end[c1 - 1])
                  for score, c0, c1 in usable if src_lo[c0] < src_end[c1 - 1]]
        usable.sort(key=lambda c: (-c[0], c[1]))
        spans: list[EvidenceSpan] = []
        for _, c0, c1 in usable:
            if any(c0 >= s.start and c1 <= s.end for s in spans):
                continue  # contained in a higher-scored span already chosen
            spans.append(EvidenceSpan(start=c0, end=c1, text=raw[c0:c1]))
            if len(spans) == self.TOP_SPANS:
                break
        valid = validate_spans(raw, spans)
        self.dropped_spans += len(spans) - len(valid)
        if len(valid) < len(spans):
            log.warning("dropped %d invalid span(s); total dropped=%d",
                        len(spans) - len(valid), self.dropped_spans)
        return valid

    @staticmethod
    def _usable_spans(text: str, candidates: list[tuple[float, int, int]]) -> list[tuple[float, int, int]]:
        """Drop fragment/punctuation/stopword-only spans; strip edge
        whitespace with the offsets adjusted to match."""
        out: list[tuple[float, int, int]] = []
        for score, c0, c1 in candidates:
            while c0 < c1 and text[c0].isspace():
                c0 += 1
            while c1 > c0 and text[c1 - 1].isspace():
                c1 -= 1
            frag = text[c0:c1]
            if len(frag) < 3 or not _ALPHA_RE.search(frag):
                continue
            words = re.findall(r"[A-Za-z]+", frag.lower())
            if words and all(w in _SPAN_STOPWORDS for w in words):
                continue
            out.append((score, c0, c1))
        return out


def build_classifier(model_path: Path, mock_version: str) -> Classifier:
    """Prefer a real artifact at SIF_MODEL_PATH (int8 by default; set
    SIF_MODEL_QUANT=fp32 to override). Fall back to the deterministic mock
    only when no artifact/tokenizer exists or the ML deps are absent —
    a corrupt model dir fails loudly, never silently mocks."""
    try:
        return RealOnnxClassifier(model_path)
    except (FileNotFoundError, ImportError):
        return MockClassifier(model_version=mock_version)
