"""Outcome-mask: token-level outcome neutralization (label-spec component B, D6).

Replaces outcome/severity tokens in incident narratives with a neutral
placeholder ([OUTCOME]) WITHOUT removing clauses. Applied to positives AND
negatives (96.8% of low-energy negative rows are hospitalized — masking only
positives would teach "outcome words = SIF").

Why token neutralization and not clause-stripping: clause-stripping measured
to empty 19.1% of rows (KNOWLEDGE_BASE §2); neutralization preserves length
and empties 0%.

The stem list below is FROZEN — it lands verbatim in label_spec.yaml at the
H2 freeze. Any change is a label_spec version bump: leak rate is word-list
dependent (measured swing 70.4% vs 76.4%).

Stdlib only.

Self-check (runs unit assertions + 5k-row measurement on the real OSHA CSV):
    python3 data_pipeline/masking.py [csv_path]
"""

from __future__ import annotations

import csv
import random
import re
import sys

MASK_TOKEN = "[OUTCOME]"

# FROZEN outcome stem list (25 entries). Multi-word phrases come first so the
# alternation takes the longest/most-specific match. Fragments match
# case-insensitively; trailing \w* makes a stem cover its inflections.
#
# Inclusion rule: a stem masks outcome/severity/disposition signal (what
# happened to the person, how bad, where they were taken), never mechanism
# signal (struck by / caught in / fell / pinned / crushed between all
# survive). Known trade-offs, accepted and documented:
#   - "sever" fragment covers severe/severely/severed but NOT "several"
#     (explicit alternation, not a bare prefix).
#   - "injur" masks injured/injury everywhere, including "no injury occurred"
#     -> "no [OUTCOME] occurred" (negation survives; acceptable).
#   - "coma"/"airlift" can rare-hit proper nouns (e.g. Comal County) — judged
#     rarer than the leak they close.
#   - "burn" alone is NOT masked (mechanism-relevant for Hot Work); only
#     degree-qualified burns are severity leaks.
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

STEM_NAMES: tuple[str, ...] = tuple(name for name, _ in _OUTCOME_PATTERNS)

_PATTERN = re.compile(
    "|".join(f"(?P<{name}>{fragment})" for name, fragment in _OUTCOME_PATTERNS),
    re.IGNORECASE,
)
_COLLAPSE = re.compile(re.escape(MASK_TOKEN) + r"(?:\s+" + re.escape(MASK_TOKEN) + r")+")


def mask_text(text: str) -> str:
    """Neutralize outcome tokens in one narrative. Never returns empty for
    non-empty input: tokens are replaced in place, clauses are never removed."""
    if not text:
        return text
    return _COLLAPSE.sub(MASK_TOKEN, _PATTERN.sub(MASK_TOKEN, text))


def mask_count(text: str) -> int:
    """How many outcome matches the masker would make (pre-collapse)."""
    return len(_PATTERN.findall(text)) if text else 0


def _self_check(csv_path: str, sample_n: int = 5000) -> None:
    # --- unit assertions ---
    assert mask_text("Employee amputated two fingers.") == f"Employee {MASK_TOKEN} two fingers."
    assert mask_text("He died at the hospital.") == f"He {MASK_TOKEN} at the {MASK_TOKEN}."
    assert mask_text("second-degree burns to the leg") == f"{MASK_TOKEN} to the leg"
    assert mask_text("third degree burn") == MASK_TOKEN
    assert "several employees were present" == mask_text("several employees were present"), "sever != several"
    assert mask_text("Severe laceration, severely bleeding") == f"{MASK_TOKEN} laceration, {MASK_TOKEN} bleeding"
    assert mask_text("loss of his left eye") == MASK_TOKEN
    assert mask_text("crush syndrome observed") == f"{MASK_TOKEN} observed"
    assert mask_text("no injury occurred") == f"no {MASK_TOKEN} occurred"
    assert mask_text("kept overnight in intensive care") == f"kept overnight in {MASK_TOKEN}"
    # mechanism words must survive untouched
    mech = "struck by a forklift, caught in the auger, fell 12 feet, pinned between, crushed between rollers"
    assert mask_text(mech) == mech
    assert mask_text("") == ""
    assert mask_text("plain text with no leaks") == "plain text with no leaks"
    print(f"unit assertions: PASS ({len(_OUTCOME_PATTERNS)} stems)")

    # --- 5k-row measurement on the real OSHA CSV ---
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = [r["Final Narrative"] for r in csv.DictReader(fh)]
    sample = random.Random(42).sample(rows, sample_n)

    empty = masked_rows = tokens_masked = 0
    len_ratios = []
    for raw in sample:
        masked = mask_text(raw)
        if not masked.strip():
            empty += 1
        n = mask_count(raw)
        if n:
            masked_rows += 1
            tokens_masked += n
        len_ratios.append(len(masked) / max(len(raw), 1))

    len_ratios.sort()
    median_ratio = len_ratios[len(len_ratios) // 2]
    print(f"rows sampled:            {len(sample)}")
    print(f"empty after masking:     {empty} ({100 * empty / len(sample):.2f}%)  [gate: must be 0]")
    print(f"rows with >=1 mask hit:  {masked_rows} ({100 * masked_rows / len(sample):.1f}%)")
    print(f"total tokens masked:     {tokens_masked} (mean {tokens_masked / len(sample):.2f}/row)")
    print(f"median len preserved:    {median_ratio:.3f}")
    assert empty == 0, "masking must produce 0% empty rows"
    print("SELF-CHECK: PASS")


if __name__ == "__main__":
    _self_check(sys.argv[1] if len(sys.argv) > 1 else "data/January2015toNovember2025.csv")
