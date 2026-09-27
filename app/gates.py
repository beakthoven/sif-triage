"""Input gates — the engineered humility/quality checks (ARCHITECTURE runtime).

Every gate returns a GateState {name, triggered, detail, action} where action
is 'badge' (annotate only), 'gray' (route to review queue / gray UI card), or
'block' (reserved — no gate blocks today; gates are ADVISORY states attached to
PredictionOut.gate_states). Gates never block ingestion and never raise: a
broken gate degrades to a gray state inside run_gates.

Gate order is load-bearing: app/tests/api_smoke.py addresses drill by position.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
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

# --- Severity watch (register-shift safety net) ------------------------------
# The ship model (masked-v2) is trained on OSHA/synthetic narrative register;
# terse out-of-register phrasing of a genuine high-severity event can score
# ~0.01 while OSHA-register phrasing of the SAME event scores 0.99 (measured
# 2026-09-11 on a live-pasted blast report: 0.006 vs 0.993). When outcome or
# high-energy mechanism language is present UNNEGATED but the calibrated score
# sits below the flag threshold, the model may have missed the event — defer
# to human review, never auto-green. Negation-scoped anchors ("no injuries",
# counterfactual-suppressed "could have") do not count. Measured corpus impact
# 2026-09-11: 49/4557 rows (1.1%) newly gray, none of them auto-cleared today.
_SEVERITY_MECH_TOKENS = {
    "blast", "explosion", "explode", "exploded", "burst",
    "collapse", "collapsed", "electrocuted", "electrocution",
    "engulfed", "crushed",
}

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


def _is_severity_anchor_token(tok: str) -> bool:
    if tok in _SEVERITY_MECH_TOKENS:
        return True
    return _is_anchor_token(tok)


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


def _match_token_starts(rx: "re.Pattern[str]", text: str,
                        tok_starts: "list[int] | None" = None) -> list[int]:
    """char offset -> token index, so cue/suppressor phrase matches map to
    token positions. The token-start table is built once per call (O(n)) and
    each match is placed by binary search — the previous per-match full token
    rescan was O(matches x tokens) and measured 30.9s at 100k chars
    (2026-09-25, /tmp/gates_timing.py)."""
    if tok_starts is None:
        tok_starts = [tm.start() for tm in _TOKEN_RE.finditer(text)]
    return [max(bisect_right(tok_starts, m.start()) - 1, 0)
            for m in rx.finditer(text)]


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
    # Bisect over the ascending cue/anchor/suppressor index lists: the naive
    # cue x anchor cross product (with a linear suppressor scan per pair) was
    # a second quadratic trap on long cue-dense pastes.
    pairs: list[tuple[int, int]] = []
    for c in cue_starts:
        for a in anchor_idx[bisect_left(anchor_idx, c - _NEG_WINDOW):
                            bisect_right(anchor_idx, c + _NEG_WINDOW)]:
            lo = min(c, a) - _NEG_WINDOW
            hi = max(c, a) + _NEG_WINDOW
            s = bisect_left(suppress_idx, lo)
            if s < len(suppress_idx) and suppress_idx[s] <= hi:
                continue
            pairs.append((c, a))
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


def gate_chunked_low_score(chunked: bool, score: float) -> GateState:
    """Chunked-input humility gate (T-6h adjudication of the v2 positional
    finding in runs/run2/day2/latency_v2_final.md §5): on multi-window inputs
    the CLS-pooled head can discount mid-text hazards (measured valleys to
    0.03 on synthetic probes). A chunked report scoring below the confidence
    band may be a silent false negative — route to review (gray) instead of
    auto-greening. Badge-only behavior for chunked + confident scores."""
    triggered = chunked and score < 0.40
    return GateState(
        name="chunked_low_score",
        triggered=triggered,
        action="gray",
        detail=(
            f"chunked input scored {score:.3f} below the 0.40 confidence band — "
            "long-report scoring can discount mid-text hazards; routed to "
            "human review"
        ) if triggered else "",
    )


def gate_severity_watch(text: str, score: float, flag_thr: float) -> GateState:
    """Severity watch (register-shift safety net): outcome or high-energy
    mechanism language present UNNEGATED, but the calibrated score sits below
    the flag threshold — the register-bound model may have missed a real
    high-severity event. Gray + routed to human review, never auto-green.
    Negation-scoped anchors (cue within ±5 tokens, counterfactual-suppressed)
    do not count — those are the negation gate's territory."""
    tokens = _TOKEN_RE.findall(text.lower())
    if not tokens or score >= flag_thr:
        return GateState(name="severity_watch", triggered=False, action="gray")
    anchor_idx = [i for i, tok in enumerate(tokens) if _is_severity_anchor_token(tok)]
    if not anchor_idx:
        return GateState(name="severity_watch", triggered=False, action="gray")
    cue_starts = _match_token_starts(_NEGATION_RE, text)
    suppress_idx = _match_token_starts(_COUNTERFACTUAL_RE, text)

    def negated(a: int) -> bool:
        for c in cue_starts[bisect_left(cue_starts, a - _NEG_WINDOW):
                            bisect_right(cue_starts, a + _NEG_WINDOW)]:
            s = bisect_left(suppress_idx, min(c, a) - _NEG_WINDOW)
            if not (s < len(suppress_idx)
                    and suppress_idx[s] <= max(c, a) + _NEG_WINDOW):
                return True
        return False

    live = [a for a in anchor_idx if not negated(a)]
    if not live:
        return GateState(name="severity_watch", triggered=False, action="gray")
    shown = ", ".join(f"'{tokens[a]}'" for a in live[:3])
    return GateState(
        name="severity_watch",
        triggered=True,
        action="gray",
        detail=(
            f"severity watch: unnegated outcome/high-energy language ({shown}) "
            f"but triage score {score:.3f} < flag threshold {flag_thr:.3f} — "
            "model may have missed a high-severity event (register shift); "
            "routed to human review"
        ),
    )


# --- Barrier-failure gate family (D3 fix) --------------------------------------
# The ship model detects physical MECHANISM, not barrier state: OIICS training
# labels encode what happened to an injured person, never the absent control
# (docs/discovery/60-orchestrator-novel-probe.md Result 2 — no gas test 0.29,
# no LOTO 0.28, fire watch gone 0.13, all below the 0.658 flag threshold, 3/6
# novel precursors missed). The problem statement explicitly asks for barrier
# failures / IOGP Life-Saving-Rule violations, so this family generalises the
# well-control-watch idea — a deterministic barrier signal the neural model
# can miss, forced to gray review, never auto-greened — into text-only gates
# for specific barrier types.
#
# Firing rule: an explicit ABSENCE cue token within +/- _BARRIER_WINDOW tokens
# of the barrier's control term, or a narrowly scoped direct absence sequence.
# Positive statements ("LOTO applied and verified", "gas test conducted,
# readings normal") carry no adjacent absence cue and never fire. Every triggered
# state is action="gray" — routed to review, never auto-cleared.
#
# Scope boundary: no trip/bypass gate because bypass language needs equipment
# state and time scope to distinguish an active defeat from a restored/tested
# bypass. Inspection-tag-removal mentions need equipment state to distinguish
# active defeat from authorized removal. Driving violations (speeding, fatigue,
# phone use) are affirmative behaviors, not negated missing controls; a reliable
# gate needs driver-behavior context to avoid flagging policy or training text.
#
# Known ceiling (ponytail: token-window keyword matching, no syntactic parse):
# absence idioms near a control term can gray a positive report ("isolated
# without exception", "no isolation breach"), and double negatives fire
# ("LOTO was not omitted"). Every error direction is toward review, never
# toward auto-green — the safe side for an advisory gate.
_BARRIER_WINDOW = 3

_ABSENCE_CUE_RE = re.compile(
    r"\b(?:no\s+one\s+was\s+assigned|nobody\s+was\s+posted\s+as|"
    r"the\s+atmosphere\s+was\s+unchecked|was\s+not\s+tested\s+for|"
    r"no\s+one|nobody|not|no|none|without|absent|never|omitted|missed|"
    r"skipped|missing|left|gone|withdrew|unverified|untested|unchecked|"
    r"unconfirmed|unattended|unavailable|unlatched|failed|forgotten|"
    r"lacked|lacking)\b",
    re.IGNORECASE,
)

# Deliberately not generalized into this token-window table: trip/bypass and
# inspection-tag-removal mentions need equipment state and time scope to
# distinguish active defeats from restored/tested or authorized removal.
# Driving-violation mentions are affirmative behaviors, not absence cues; a
# reliable gate needs driver-behavior context to avoid flagging policy/training.
_BARRIER_CONTROLS: dict[str, "re.Pattern[str]"] = {
    "energy_isolation_absent": re.compile(
        r"\b(?:loto|lock[\s/-]?out(?:[\s/-]?tag[\s/-]?out)?|tag[\s/-]?out"
        r"|isolation(?:s)?|isolat(?:e|ed|es|ing)|de-?energi[sz]\w*"
        r"|energi[sz]\w*|prov(?:e|ed|ing)\s+dead|test(?:ed|ing)?\s+dead"
        r"|absence\s+of\s+voltage|zero[\s-]+voltage)\b",
        re.IGNORECASE,
    ),
    "gas_test_absent": re.compile(
        r"\b(?:gas test\w*|gas detect\w*|atmospher\w* test\w*|air test\w*"
        r"|o2 test\w*|oxygen test\w*|gas reading\w*|tested for gas"
        r"|gas reading taken|atmospher\w*\s+was\s+not\s+tested|"
        r"atmospher\w*\s+was\s+unchecked|atmospher\w*\s+unchecked)\b",
        re.IGNORECASE,
    ),
    "permit_absent": re.compile(
        r"\b(?:permit to (?:work|enter)|work permit|ptw|entry permit"
        r"|hot[\s-]?work permit|confined space permit|cold work permit"
        r"|permit system)\b",
        re.IGNORECASE,
    ),
    "fall_protection_absent": re.compile(
        r"\b(?:anchor(?:age)?(?:\s+point)?s?|full[\s-]?body harness(?:es)?"
        r"|harness(?:es)?|double[\s-]?lanyards?|lanyards?"
        r"|rope grabs?|fall[\s-]?arrest(?:\s+devices?)?|lifelines?"
        r"|tied[\s-]?off|tie[\s-]?off)\b",
        re.IGNORECASE,
    ),
    "fire_watch_absent": re.compile(
        r"\bfire ?watch(?:er|ers|ing|man|men)?\b",
        re.IGNORECASE,
    ),
    "standby_absent": re.compile(
        r"\b(?:stand ?by|attendant|hole watch(?:es)?|bottle watch|safety watch|"
        r"banksman|spotter|lookout|sentinel|unattended)\b",
        re.IGNORECASE,
    ),
    "atmosphere_unmonitored": re.compile(
        r"\b(?:monitor\w*|purg\w*|sweep\w*)\b", re.IGNORECASE,
    ),
}

# atmosphere_unmonitored also fires on an inert purge DURING work ("purging in
# progress" while entry is under way) — the absent control there is a
# breathable, monitored atmosphere itself. Suppressors cover purges that are
# over or that had not started ("purge completed", "purge before entry",
# "no nitrogen purge"); an ongoing inert purge is a hard hazard and staying
# silent on it would be the dangerous direction.
_BARRIER_DIRECT: dict[str, "re.Pattern[str]"] = {
    "atmosphere_unmonitored": re.compile(
        r"\b(?:(?:nitrogen|n2|inert)\s+(?:gas\s+)?(?:purg\w*|sweep\w*)"
        r"|(?:purg\w*|sweep\w*)\b.{0,24}?\b(?:in[\s-]?progress|ongoing|underway))\b",
        re.IGNORECASE,
    ),
    "permit_absent": re.compile(
        r"\b(?:began|started|commenced|proceeded|carried\s+out)\b"
        r".{0,48}?\bbefore\b.{0,24}?\b(?:permit\s+to\s+work|ptw)\b"
        r".{0,24}?\b(?:signed|approved|authori[sz]ed|issued)\b",
        re.IGNORECASE,
    ),
    "fall_protection_absent": re.compile(
        r"\b(?:started|began|commenced|proceeded)\b.{0,48}?\bbefore\b"
        r".{0,24}?\b(?:anyone|anybody|someone)\s+confirmed\b"
        r".{0,24}?\b(?:anchor(?:age)?(?:\s+point)?|tie[\s-]?off)\b",
        re.IGNORECASE,
    ),
}
_BARRIER_DIRECT_SUPPRESS_RE = re.compile(
    r"\b(?:complet\w*|finish\w*|stopp\w*|halt\w*|abort\w*|cancel\w*|suspend\w*"
    r"|before|prior|preced\w*)\b",
    re.IGNORECASE,
)


def gate_barrier_absence(text: str, name: str) -> GateState:
    """One barrier-failure gate (D3 fix): fires on a nearby explicit ABSENCE cue
    or a targeted direct absence sequence. The atmosphere gate also detects an
    inert purge in progress. Shared engine; never auto-cleared (action="gray")."""
    tok_starts = [tm.start() for tm in _TOKEN_RE.finditer(text)]
    if not tok_starts:
        return GateState(name=name, triggered=False, action="gray")
    # Measure multiword cues from their final token: "no one" is the absence
    # phrase, so its distance to "spotter" is one token shorter than from "no".
    cue_idx = sorted({
        max(bisect_right(tok_starts, m.end() - 1) - 1, 0)
        for m in _ABSENCE_CUE_RE.finditer(text)
    })
    pairs: list[tuple[int, str]] = []
    direct = _BARRIER_DIRECT.get(name)
    if direct is not None:
        suppress_spans = [
            (max(bisect_right(tok_starts, m.start()) - 1, 0),
             max(bisect_right(tok_starts, m.end() - 1) - 1, 0))
            for m in _BARRIER_DIRECT_SUPPRESS_RE.finditer(text)
        ]
        for m in direct.finditer(text):
            i0 = max(bisect_right(tok_starts, m.start()) - 1, 0)
            i1 = max(bisect_right(tok_starts, m.end() - 1) - 1, 0)
            if name == "atmosphere_unmonitored":
                if any(s <= i1 + _BARRIER_WINDOW and e >= i0 - _BARRIER_WINDOW
                       for (s, e) in suppress_spans):
                    continue  # "purge completed", "purge before entry"
                if any(i0 - 2 <= c < i0 for c in cue_idx):
                    continue  # "no nitrogen purge" — the cue negates the purge
            pairs.append((i0, m.group(0).lower()))
    if cue_idx:
        spans: list[tuple[int, int, str]] = []
        for m in _BARRIER_CONTROLS[name].finditer(text):
            i0 = max(bisect_right(tok_starts, m.start()) - 1, 0)
            i1 = max(bisect_right(tok_starts, m.end() - 1) - 1, 0)
            spans.append((i0, i1, m.group(0).lower()))
        # cue x control-span scan via two-pointer merge over the ascending
        # spans (same quadratic-trap avoidance as gate_negation); spans expire
        # permanently once their last token falls behind the cue window
        si = 0
        active: list[tuple[int, int, str]] = []
        for c in cue_idx:
            while si < len(spans) and spans[si][0] <= c + _BARRIER_WINDOW:
                active.append(spans[si])
                si += 1
            active = [sp for sp in active if sp[1] >= c - _BARRIER_WINDOW]
            pairs.extend((c, phrase) for (_, _, phrase) in active)
    if not pairs:
        return GateState(name=name, triggered=False, action="gray")
    tokens = _TOKEN_RE.findall(text.lower())
    shown = ", ".join(f"'{tokens[c]}'~'{phrase}'" for c, phrase in pairs[:3])
    label = name.removesuffix("_absent").replace("_", " ")
    return GateState(
        name=name,
        triggered=True,
        action="gray",
        detail=f"barrier failure: absence or direct violation signal for "
        f"{label} control ({shown}) — routed to human review, never auto-cleared",
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


def gate_verdict_stability(stability: float, n_variants: int) -> GateState:
    """Route an ensemble verdict to review when fewer than 75% of scored
    surface variants agree with the ensemble verdict. Reliability routing only:
    this gate never changes the score or operating point."""
    triggered = n_variants >= 2 and stability < 0.75
    if not triggered:
        return GateState(name="verdict_stability", triggered=False, action="gray")
    disagree = n_variants - round(stability * n_variants)
    return GateState(
        name="verdict_stability",
        triggered=True,
        action="gray",
        detail=(f"verdict flips on rephrasing: {disagree} of {n_variants} variants "
                f"disagree (stability {stability:.2f}) — routed to human review"),
    )


def run_gates(text: str, score: float, storage: "Storage", cfg: Settings,
              vec: "np.ndarray | None" = None,
              base_hit: "tuple[int | str, float] | None" = None,
              well_control: bool = False,
              flag_thr: float = 0.5,
              chunked: bool = False,
              verdict_stability: float = 1.0,
              n_variants: int = 1) -> list[GateState]:
    # vec/base_hit (optional) are the bulk-ingest path's batch-computed
    # embedding + corpus-tier top-1 (D25); None = compute per row (the
    # /classify path, unchanged). well_control is the classifier's
    # deterministic barrier tag; flag_thr is its calibrated flag threshold
    # (flag_threshold(clf)) — both feed the well-control watch gate.
    # chunked feeds the chunked-low-score humility gate; stability and variant
    # count feed the final ensemble reliability gate.
    # Order is load-bearing (smoke test addresses drill by index 4);
    # newer general gates, barrier-failure gates and verdict_stability are
    # appended LAST so existing positions hold.
    # NOTE for the api_smoke owner: app/tests/api_smoke.py asserts the exact
    # gate-name set and must track additions here.
    specs = (
        ("min_length", lambda: gate_min_length(text, cfg)),
        ("negation", lambda: gate_negation(text)),
        ("language", lambda: gate_language(text, cfg)),
        ("confidence", lambda: gate_confidence(score, cfg)),
        ("drill", lambda: gate_drill(text)),
        ("near_dup", lambda: gate_near_dup(text, storage, cfg, vec=vec, base_hit=base_hit)),
        ("long_input", lambda: gate_long_input(text, cfg)),
        ("well_control_watch", lambda: gate_well_control_watch(well_control, score, flag_thr)),
        ("chunked_low_score", lambda: gate_chunked_low_score(chunked, score)),
        ("severity_watch", lambda: gate_severity_watch(text, score, flag_thr)),
        ("energy_isolation_absent",
         lambda: gate_barrier_absence(text, "energy_isolation_absent")),
        ("gas_test_absent", lambda: gate_barrier_absence(text, "gas_test_absent")),
        ("permit_absent", lambda: gate_barrier_absence(text, "permit_absent")),
        ("fire_watch_absent", lambda: gate_barrier_absence(text, "fire_watch_absent")),
        ("standby_absent", lambda: gate_barrier_absence(text, "standby_absent")),
        ("atmosphere_unmonitored",
         lambda: gate_barrier_absence(text, "atmosphere_unmonitored")),
        ("verdict_stability",
         lambda: gate_verdict_stability(verdict_stability, n_variants)),
        ("fall_protection_absent",
         lambda: gate_barrier_absence(text, "fall_protection_absent")),
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
