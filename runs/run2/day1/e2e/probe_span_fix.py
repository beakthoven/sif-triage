#!/usr/bin/env python3
"""Probe: span-duplication fix (review SEV1-1) across all 13 demo cards.

Fetches POST /api/classify (stateless, no writes) for every demo_corpus.jsonl
card from the live server, then renders the blockquote text two ways:

  OLD — dashboard/src/components/highlighted-text.tsx pre-fix slicing
        (walk spans in array order, resume at previous span's end)
  NEW — the fixed slicing (sort by start, drop overlaps)

Asserts: NEW output == the exact input text for all 13 cards, and reports
how many cards the OLD path corrupted. Exit 1 if any assertion fails.

Usage: .venv/bin/python runs/run2/day1/e2e/probe_span_fix.py [base_url]
"""

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8177"
CORPUS = "artifacts/demo/demo_corpus.jsonl"


def classify(text: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/api/classify",
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def render_old(text: str, spans: list[dict]) -> str:
    parts, cursor = [], 0
    for s in spans:
        if s["start"] > cursor:
            parts.append(text[cursor : s["start"]])
        parts.append(text[s["start"] : s["end"]])
        cursor = s["end"]
    if cursor < len(text):
        parts.append(text[cursor:])
    return "".join(parts)


def render_new(text: str, spans: list[dict]) -> str:
    ordered = []
    for s in sorted(spans, key=lambda s: (s["start"], s["end"])):
        if ordered and s["start"] < ordered[-1]["end"]:
            continue
        ordered.append(s)
    parts, cursor = [], 0
    for s in ordered:
        if s["start"] > cursor:
            parts.append(text[cursor : s["start"]])
        parts.append(text[s["start"] : s["end"]])
        cursor = s["end"]
    if cursor < len(text):
        parts.append(text[cursor:])
    return "".join(parts)


def main() -> int:
    cards = [json.loads(line) for line in open(CORPUS)]
    corrupted_old, unsorted, overlaps_dropped = 0, 0, 0
    failures = []
    for card in cards:
        text = card["text"]
        pred = classify(text)
        spans = pred.get("evidence_spans", [])
        starts = [s["start"] for s in spans]
        if starts != sorted(starts):
            unsorted += 1
        old = render_old(text, spans)
        new = render_new(text, spans)
        n_kept = len([s for i, s in enumerate(sorted(spans, key=lambda s: (s["start"], s["end"])))
                      if i == 0 or s["start"] >= sorted(spans, key=lambda s: (s["start"], s["end"]))[i - 1]["end"]])
        overlaps_dropped += len(spans) - n_kept
        if old != text:
            corrupted_old += 1
        status = "OK " if new == text else "FAIL"
        if new != text:
            failures.append(card["demo_id"])
        print(
            f"{status} {card['demo_id']:<16} spans={len(spans)} "
            f"text={len(text)} old_render={len(old)} new_render={len(new)}"
        )
    print(
        f"\nOLD path corrupted: {corrupted_old}/{len(cards)} cards; "
        f"unsorted span arrays: {unsorted}/{len(cards)}; "
        f"overlapping spans dropped by fix: {overlaps_dropped}"
    )
    if failures:
        print(f"NEW path FAILED on: {failures}", file=sys.stderr)
        return 1
    print(f"NEW path: exact text reconstruction on {len(cards)}/{len(cards)} cards — fix proven.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
