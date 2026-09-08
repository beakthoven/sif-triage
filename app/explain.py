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
import json
import logging
import os
import re
import time
import urllib.request
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from .schemas import RULE_DISPLAY, ExplanationOut, PredictionOut

log = logging.getLogger(__name__)

REVIEW_THRESHOLD = 0.5  # matches routes.FLAG_THRESHOLD

DEFAULT_OLLAMA_URL = os.environ.get("SIF_OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("SIF_OLLAMA_MODEL", "qwen3:4b")
DEFAULT_TIMEOUT_S = float(os.environ.get("SIF_EXPLAIN_TIMEOUT", "8"))
# Template-only cache entries (LLM down/slow at build time) are served this
# long before the LLM gets one upgrade retry.
FALLBACK_TTL_S = float(os.environ.get("SIF_EXPLAIN_FALLBACK_TTL", "300"))

REWORD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "spans_quoted": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["explanation", "spans_quoted"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """You turn structured triage notes into short plain-English paragraphs for an HSE review board.

Example input:
Triage score 0.83 — flagged for HSE review.
IOGP rules implicated: Hot Work (0.71), Energy Isolation (0.66).
Evidence phrases: "grinding", "LOTO".

Example output:
{"explanation": "This report is flagged for HSE review with a triage score of 0.83. The implicated IOGP rules are Hot Work (0.71) and Energy Isolation (0.66), supported by the evidence phrases \\"grinding\\" and \\"LOTO\\".", "spans_quoted": ["grinding", "LOTO"]}

Rules: keep every number exactly as given; quote evidence phrases verbatim; do not add facts, severities, or recommendations; never say the event was predicted or prevented; 2-3 sentences. Output JSON only."""

# ponytail: the user message carries the TEMPLATE only, not the report. With
# the report in-context qwen3:4b flips into analysis mode and burns the whole
# num_predict budget on planning inside the JSON string fields (measured
# twice, 2026-09-08); template-only + one-shot example yields clean rewrites.
_USER_TEMPLATE = "Triage note:\n{template}"


class RewordOut(BaseModel):
    explanation: str = Field(min_length=10, max_length=1500)
    spans_quoted: list[str] = Field(default_factory=list, max_length=10)


class SpanValidationError(ValueError):
    pass


def explain_key(text: str, model_version: str) -> str:
    digest = hashlib.sha256((text + "\x00" + model_version).encode("utf-8")).hexdigest()
    return f"explain:{digest}"


def render_template(pred: PredictionOut, text: str) -> tuple[str, list[str]]:
    """Deterministic human explanation from the prediction alone.

    Returns (template_text, spans_quoted). Same input -> same output; every
    quoted span is an exact substring of `text` by the span invariant.
    """
    flagged = pred.sif_score >= REVIEW_THRESHOLD
    lines = [
        f"Triage score {pred.sif_score:.2f} — "
        + ("flagged for HSE review." if flagged else "below the review threshold.")
    ]
    implicated = sorted(
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
    if implicated:
        shown = ", ".join(f"{RULE_DISPLAY[k]['display']} ({p:.2f})" for k, p in implicated)
        lines.append(f"IOGP rules implicated: {shown}.")
    else:
        lines.append("No IOGP rule crossed its display threshold.")
    if pred.well_control:
        lines.append("Well-control/barrier tag: raised.")
    span_texts = [s.text for s in pred.evidence_spans[:5] if s.text and s.text in text]
    if span_texts:
        quoted = ", ".join(f'"{s}"' for s in span_texts)
        lines.append(f"Evidence phrases: {quoted}.")
    else:
        lines.append("Evidence phrases: none extracted.")
    triggered = [g for g in pred.gate_states if g.triggered]
    if triggered:
        shown = "; ".join(f"{g.name} ({g.detail})" if g.detail else g.name for g in triggered)
        lines.append(f"Advisory gates: {shown}.")
    return "\n".join(lines), span_texts


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
    if score_str not in out.explanation:
        raise SpanValidationError(f"triage score {score_str} missing from the rewording")
    if _META_RE.search(out.explanation[:300]):
        raise SpanValidationError("reasoning/meta language in the explanation field")
    bad = [s for s in out.spans_quoted if not s or s not in text]
    if bad:
        raise SpanValidationError(f"spans not verbatim substrings of the report: {bad!r}")
    # Anything the paragraph puts in double quotes must be a verbatim report
    # substring too — observed live: an in-prose quoted date got mutated
    # ("22.05.2:2025") while spans_quoted stayed clean.
    bad_quotes = [q for q in re.findall(r'"([^"]+)"', out.explanation) if q not in text]
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
                KeyError, TypeError, OSError) as exc:
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
) -> ExplanationOut:
    """Template always; cached or live ollama rewording when it works.

    Cache semantics (precompute doctrine): an ollama-sourced entry is served
    verbatim forever. A template-only entry (LLM was down/slow at build time)
    is served for FALLBACK_TTL_S, then the LLM is retried once and the entry
    replaced — a recovered server upgrades stale fallbacks without a cache
    flush, while a down server costs at most one bounded stall per text per
    TTL window instead of 2x the timeout on every request.
    """
    template, template_spans = render_template(pred, text)
    key = explain_key(text, pred.model_version)

    if storage is not None:
        hit = storage.load_precomputed(key)
        if hit is not None:
            fresh = time.time() - float(hit.get("created_epoch", 0)) < FALLBACK_TTL_S
            if hit.get("source") == "ollama" or not use_llm or fresh:
                return ExplanationOut(**hit, cached=True)

    reworded: RewordOut | None = None
    if use_llm:
        reworded = ollama_reword(text, template, f"{pred.sif_score:.2f}",
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
