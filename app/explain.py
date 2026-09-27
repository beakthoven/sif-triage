"""Explanation layer: deterministic template first, optional Ollama rewording.

The TEMPLATE is the contract floor — built only from the prediction and the
canonical report text, so it is always correct and needs zero dependencies.
The OPTIONAL qwen3:4b rewording follows the verified C10 invocation contract
(DECISION_LOG D4 + local-llm-ops-engineer.md):

    POST /api/chat {"messages": [...], "stream": false, "think": false,
                    "format": <JSON-SCHEMA>,
                    "options": {"temperature": 0, "num_predict": 400}}

The `format` schema on EVERY call is what suppresses thinking — `/no_think`
and bare `think:false` are both verified broken. Validation layers: pydantic
schema -> triage score preserved verbatim -> no chain-of-thought/meta leak
into the field -> spans_quoted AND every in-prose "quoted phrase" are exact
case-sensitive substrings of the report -> one corrective retry with the
error appended -> silent template fallback.

Results are cached in the storage `precomputed` table under
sha256(text + model_version) so the demo never depends on a live LLM call.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import logging
import os
import re
import time
import urllib.request
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from .classifier import RULE_CUE_RES
from .schemas import RULE_DISPLAY, ExplanationOut, PredictionOut

log = logging.getLogger(__name__)

REVIEW_THRESHOLD = 0.5  # fallback when the classifier carries no tuned
# operating point (matches routes.FLAG_THRESHOLD; the D19 test-tuned point
# from the artifact's metrics.json is preferred whenever present)

DEFAULT_OLLAMA_URL = os.environ.get("SIF_OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("SIF_OLLAMA_MODEL", "qwen3:4b")
DEFAULT_TIMEOUT_S = float(os.environ.get("SIF_EXPLAIN_TIMEOUT", "8"))
# Template-only cache entries (LLM down/slow at build time) are served this
# long before the LLM gets one upgrade retry.
FALLBACK_TTL_S = float(os.environ.get("SIF_EXPLAIN_FALLBACK_TTL", "300"))
EXPLANATION_VERSION = "v5-serious-event"

# Explanation cues share the classifier's consolidated per-rule table. The
# well-control phrases remain separate: they are not one of the seven rules.
_RULE_EVIDENCE_RES = {
    rule: groups["evidence"] for rule, groups in RULE_CUE_RES.items()
}
_WELL_CONTROL_EVIDENCE_RES = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"\bwell control\b", r"\bblowout\b", r"\bbop\b", r"\bwellhead\b",
    r"\bh2s\b", r"\bgas migration\b", r"\blost circulation\b",
    r"\bworkover\b", r"\bcoiled tubing\b",
))

REWORD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "spans_quoted": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["explanation", "spans_quoted"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """Rewrite the supplied HSE report note as one or two short sentences for a field safety officer.

Focus on the actual worksite situation and any named safeguard that was missing. Use direct language, not model terminology. Keep every cited report phrase verbatim. Include the supplied triage score exactly as shown, but do not add thresholds, percentages, rule rankings, gate names, similarity values, or internal matching details. Do not add facts, severity, causation, or recommendations not present in the note. Never say an event was predicted or prevented. Return JSON only in the requested schema. If the note says the report is unclear, preserve that uncertainty.

Example:
Input: The report describes people exposed to a suspended load. Missing: a standby person. Report text: “the load passed over the crew”. Sent to a reviewer.
Output: {\"explanation\": \"A suspended load passed over the crew, and no standby person was recorded.\", \"spans_quoted\": [\"the load passed over the crew\"]}"""

_USER_TEMPLATE = "HSE report note:\\n{template}"


class RewordOut(BaseModel):
    explanation: str = Field(min_length=10, max_length=1500)
    spans_quoted: list[str] = Field(default_factory=list, max_length=10)


class SpanValidationError(ValueError):
    pass


def explain_key(text: str, model_version: str, threshold: float = REVIEW_THRESHOLD) -> str:
    # Threshold is part of the key: a re-tuned operating point changes the
    # "flagged / below the review threshold" wording, so cached entries from
    # the old threshold must not be served against the new one.
    digest = hashlib.sha256(
        (
            text
            + "\x00"
            + model_version
            + "\x00"
            + repr(threshold)
            + "\x00"
            + EXPLANATION_VERSION
        ).encode("utf-8")
    ).hexdigest()
    return f"explain:{digest}"


def _context_phrase(text: str, start: int, end: int, max_chars: int = 180) -> str:
    """Return an exact sentence/clause around a cue, bounded for readability."""
    left = max(text.rfind(".", 0, start), text.rfind(";", 0, start), text.rfind("\n", 0, start)) + 1
    stops = [pos for pos in (text.find(".", end), text.find(";", end), text.find("\n", end)) if pos >= 0]
    right = min(stops) + 1 if stops else len(text)
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if right - left <= max_chars:
        return text[left:right]

    left = max(left, start - max_chars // 2)
    right = min(right, end + max_chars // 2)
    while left > 0 and left < start and not text[left - 1].isspace():
        left += 1
    while right < len(text) and right > end and not text[right].isspace():
        right -= 1
    return text[left:right].strip()


def evidence_phrases(pred: PredictionOut, text: str, limit: int = 3) -> list[str]:
    """Exact source phrases: model spans first, then rule-aware cue context."""
    phrases = list(dict.fromkeys(
        span.text.strip()
        for span in pred.evidence_spans
        if span.text.strip() and span.text in text
    ))
    if len(phrases) >= limit:
        return phrases[:limit]

    ranked_rules = sorted(
        (
            (key, prob)
            for key, prob in pred.rule_probs.items()
            if key in RULE_DISPLAY and RULE_DISPLAY[key]["in_scope"]
        ),
        key=lambda item: (-item[1], item[0]),
    )
    regex_groups = [
        _RULE_EVIDENCE_RES[key]
        for key, _ in ranked_rules
        if key in _RULE_EVIDENCE_RES
    ]
    if pred.well_control:
        regex_groups.append(_WELL_CONTROL_EVIDENCE_RES)

    for regexes in regex_groups:
        match = next((match for regex in regexes if (match := regex.search(text))), None)
        if match is None:
            continue
        phrase = _context_phrase(text, match.start(), match.end())
        if phrase and phrase in text and phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) >= limit:
            break
    return phrases[:limit]


# Plain-language meanings: describe the exposure, not the classifier's
# ontology. Numeric probabilities live in the adjacent rule bars.
_RULE_MEANING: dict[str, str] = {
    "line_of_fire": "a person was exposed to a moving or released object",
    "energy_isolation": "work involved equipment that may still be energised",
    "hot_work": "hot work was carried out near flammable material",
    "confined_space": "someone entered or worked inside a confined space",
    "working_at_height": "work was carried out at height, with a fall risk",
    "safe_mechanical_lifting": "a load was lifted over or near people",
    "driving": "the report describes a driving or vehicle hazard",
}

_BARRIER_MEANING: dict[str, str] = {
    "energy_isolation_absent": "lock-out/tag-out or isolation",
    "gas_test_absent": "a gas test before entry",
    "permit_absent": "a permit to work",
    "fire_watch_absent": "a fire watch",
    "standby_absent": "a standby person",
    "atmosphere_unmonitored": "atmosphere monitoring",
    "fall_protection_absent": "fall protection or a harness",
}


def _implicated_rules(pred: PredictionOut) -> list[tuple[str, float]]:
    return sorted(
        (
            (key, prob)
            for key, prob in pred.rule_probs.items()
            if key in RULE_DISPLAY
            and RULE_DISPLAY[key]["in_scope"]
            and RULE_DISPLAY[key]["threshold"] is not None
            and prob >= float(RULE_DISPLAY[key]["threshold"])
        ),
        key=lambda kv: (-kv[1], kv[0]),
    )


def _triggered_barriers(pred: PredictionOut) -> list[str]:
    return [
        g.name
        for g in pred.gate_states
        if g.triggered and g.name in _BARRIER_MEANING
    ]


def _needs_review(pred: PredictionOut) -> bool:
    return any(g.triggered and g.action in {"gray", "block"} for g in pred.gate_states)


def render_template(pred: PredictionOut, text: str,
                    threshold: float = REVIEW_THRESHOLD) -> tuple[str, list[str]]:
    """Short, officer-first explanation: what happened and what needs review.

    The score, band, threshold, and rule probabilities are already visible in
    neighboring UI components; repeating them here obscures the actual exposure.
    Returns (plain-language summary, the exact report phrase it cites).
    """
    cited = evidence_phrases(pred, text, limit=1)
    quote = f' Report text: “{cited[0]}”' if cited else ""
    rules = _implicated_rules(pred)
    barriers = _triggered_barriers(pred)
    uncertain_from = getattr(pred, "gray_band_low", None)
    uncertain_from = uncertain_from if isinstance(uncertain_from, float) else 0.40

    if barriers:
        missing = ", ".join(_BARRIER_MEANING[b] for b in barriers)
        lines = [f"Missing: {missing}.{quote}", "Sent to a reviewer."]
        if pred.well_control:
            lines.append("Well-control equipment is involved.")
    elif pred.well_control:
        lines = [f"The report involves well-control equipment; a person should review it.{quote}"]
    elif pred.sif_score >= threshold:
        lines = [f"This report describes a serious event; a person should review it.{quote}"]
    elif pred.sif_score >= uncertain_from:
        lines = [f"The report is unclear; a person should check it.{quote}"]
    elif _needs_review(pred):
        lines = [f"The report needs a review before it is closed.{quote}"]
    else:
        lines = [f"No clear high-energy exposure or missing safeguard was identified.{quote}"]
    return "\n".join(lines), cited


def _http_transport(url: str, timeout: float) -> Callable[[dict], dict]:
    def call(payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url.rstrip("/") + "/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    return call


# Chain-of-thought leaking into the explanation field passes JSON/schema
# validation — catch it semantically (observed live on qwen3:4b: the field
# opened with "The user wants me to rewrite...").
_META_RE = re.compile(
    r"\b(the user|i need to|i should|let me|my task|the instruction|"
    r"the rules|i will|step by step|first, i)\b",
    re.IGNORECASE,
)


def _validate(content: str, text: str, score_str: str) -> RewordOut:
    out = RewordOut(**json.loads(content))
    # Post-review SEV2: a bare substring check let mutated scores through
    # ("10.83" and "0.833" both contain "0.83"; a rule prob formatting to the
    # same 2-decimal string masked a missing triage score). Digit-boundary
    # anchored: preceded by no digit/dot, followed by no digit — a trailing
    # sentence period after the score stays legal, "10.83"/"0.833" do not.
    if not re.search(rf"(?<![\d.]){re.escape(score_str)}(?!\d)", out.explanation):
        raise SpanValidationError(f"triage score {score_str} missing from the rewording")
    if _META_RE.search(out.explanation[:300]):
        raise SpanValidationError("reasoning/meta language in the explanation field")
    bad = [s for s in out.spans_quoted if not s or s not in text]
    if bad:
        raise SpanValidationError(f"spans not verbatim substrings of the report: {bad!r}")
    # Anything the paragraph puts in double quotes (straight or curly) must
    # be a verbatim report substring too — observed live: an in-prose quoted
    # date got mutated ("22.05.2:2025") while spans_quoted stayed clean.
    quoted = re.findall(r'"([^"]+)"', out.explanation)
    quoted += re.findall(r"“([^”]+)”", out.explanation)
    bad_quotes = [q for q in quoted if q not in text]
    if bad_quotes:
        raise SpanValidationError(f"quoted phrases not verbatim in the report: {bad_quotes!r}")
    return out


def ollama_reword(
    text: str,
    template: str,
    score_str: str,
    *,
    url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT_S,
    transport: Callable[[dict], dict] | None = None,
) -> RewordOut | None:
    """One optional rewording attempt: call -> validate -> 1 retry -> None.

    Never raises; any failure returns None so the caller falls back to the
    template silently. `transport` is injectable for tests (defaults to the
    real /api/chat POST with the C10 contract on every call). `score_str` is
    the exact triage-score token the rewording must preserve.
    """
    transport = transport or _http_transport(url, timeout)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(template=template)},
    ]
    for attempt in range(2):
        try:
            resp = transport(
                {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "format": REWORD_SCHEMA,
                    "options": {"temperature": 0, "num_predict": 300},
                }
            )
            content = resp["message"]["content"]
            return _validate(content, text, score_str)
        except (ValidationError, SpanValidationError, json.JSONDecodeError,
                KeyError, TypeError, OSError, ValueError,
                http.client.HTTPException) as exc:
            # Post-review SEV1: ValueError (e.g. SIF_EXPLAIN_TIMEOUT=-1 ->
            # urlopen "Timeout value out of range") and HTTPException (a
            # non-HTTP port squatter -> BadStatusLine) escaped this tuple and
            # 500'd ?explain=1 instead of falling back to the template.
            err = f"{type(exc).__name__}: {exc}"
            log.info("reword attempt %d failed (%s)", attempt + 1, err)
            messages = messages + [
                {"role": "user", "content": f"The previous output was invalid ({err}). Return corrected JSON only."}
            ]
    return None


def cache_payload(out: ExplanationOut) -> dict:
    """Payload written to the precomputed table (shared by build_explanation
    and the precompute harness). created_epoch drives the fallback TTL."""
    return out.model_dump(exclude={"cached"}) | {"created_epoch": time.time()}


def build_explanation(
    pred: PredictionOut,
    text: str,
    storage: Any = None,
    *,
    use_llm: bool = True,
    url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT_S,
    transport: Callable[[dict], dict] | None = None,
    threshold: float | None = None,
) -> ExplanationOut:
    """Template always; cached or live ollama rewording when it works.

    `threshold` is the SIF flag cutoff for the flagged/not-flagged wording —
    callers pass the classifier's tuned operating point (D19); None falls
    back to the a-priori REVIEW_THRESHOLD. The threshold is part of the
    cache key, so a re-tune never serves stale flag wording.

    Cache semantics (precompute doctrine): an ollama-sourced entry is served
    verbatim forever. A template-only entry (LLM was down/slow at build time)
    is served for FALLBACK_TTL_S, then the LLM is retried once and the entry
    replaced — a recovered server upgrades stale fallbacks without a cache
    flush, while a down server costs at most one bounded stall per text per
    TTL window instead of 2x the timeout on every request.
    """
    thr = REVIEW_THRESHOLD if threshold is None else float(threshold)
    template, template_spans = render_template(pred, text, threshold=thr)
    key = explain_key(text, pred.model_version, thr)

    if storage is not None:
        hit = storage.load_precomputed(key)
        if hit is not None:
            fresh = time.time() - float(hit.get("created_epoch", 0)) < FALLBACK_TTL_S
            if hit.get("source") == "ollama" or not use_llm or fresh:
                return ExplanationOut(**hit, cached=True)

    reworded: RewordOut | None = None
    if use_llm:
        reworded = ollama_reword(text, template, f"{pred.sif_score:.3f}",
                                 url=url, model=model,
                                 timeout=timeout, transport=transport)

    out = ExplanationOut(
        template=template,
        reworded=reworded.explanation if reworded else None,
        spans_quoted=list(dict.fromkeys(reworded.spans_quoted)) if reworded else template_spans,
        source="ollama" if reworded else "template",
        cached=False,
        model_version=pred.model_version,
    )
    if storage is not None:
        storage.save_precomputed(key, cache_payload(out))
    return out
