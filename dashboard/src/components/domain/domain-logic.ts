/*
 * Pure domain logic for the explainability primitives. NO imports at all —
 * this file must stay runnable directly under `node domain-selfcheck.ts`
 * (Node type-stripping requires erasable syntax only, which is all we use).
 */

import type { Stability, VerdictWord } from "./domain-types";

/** Spread above which the report card describes wording as unstable. The
 *  queue's instability badge uses the server's agreement fraction separately;
 *  this spread cutoff remains a UI presentation heuristic. */
export const UNSTABLE_SPREAD_DEFAULT = 0.15;

/** Wilson score interval (95%, z = 1.96) for a binomial proportion. Used by
 *  DensityTable (and available to PatternCard callers) so no small-n rate is
 *  ever shown without its interval. Returns [lo, hi] clamped to [0, 1];
 *  n <= 0 returns the maximally uninformative [0, 1]. */
export function wilson(p: number, n: number, z: number = 1.96): [number, number] {
  if (!Number.isFinite(p) || !Number.isFinite(n) || n <= 0) return [0, 1];
  const phat = Math.min(1, Math.max(0, p));
  const denom = 1 + (z * z) / n;
  const centre = phat + (z * z) / (2 * n);
  const margin = z * Math.sqrt((phat * (1 - phat) + (z * z) / (4 * n)) / n);
  return [Math.max(0, (centre - margin) / denom), Math.min(1, (centre + margin) / denom)];
}

export interface RawSpan {
  start: number;
  end: number;
  text: string;
}

export interface SpanSegment {
  text: string;
  isSpan: boolean;
}

/** Keep only spans that satisfy the server invariant text[start:end] === text
 *  (defends the render against stale offsets on freshly classified reports),
 *  sort by position, and merge true overlaps so <mark> elements never nest.
 *  Adjacent (touching but non-overlapping) spans stay separate. */
export function mergeSpans(text: string, spans: readonly RawSpan[]): RawSpan[] {
  const valid = spans.filter(
    (s) =>
      Number.isInteger(s.start) &&
      Number.isInteger(s.end) &&
      s.start >= 0 &&
      s.end > s.start &&
      s.end <= text.length &&
      text.slice(s.start, s.end) === s.text,
  );
  const sorted = [...valid].sort((a, b) => a.start - b.start || a.end - b.end);
  const merged: RawSpan[] = [];
  for (const s of sorted) {
    const last = merged[merged.length - 1];
    if (last && s.start < last.end) {
      if (s.end > last.end) {
        last.end = s.end;
        last.text = text.slice(last.start, last.end);
      }
    } else {
      merged.push({ start: s.start, end: s.end, text: s.text });
    }
  }
  return merged;
}

/** Split text into plain/highlighted segments for rendering. */
export function spanSegments(text: string, spans: readonly RawSpan[]): SpanSegment[] {
  const segments: SpanSegment[] = [];
  let cursor = 0;
  for (const s of mergeSpans(text, spans)) {
    if (s.start > cursor) segments.push({ text: text.slice(cursor, s.start), isSpan: false });
    segments.push({ text: text.slice(s.start, s.end), isSpan: true });
    cursor = s.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), isSpan: false });
  return segments;
}

/** Strip raw vector math and index-row identifiers from reviewer-facing copy.
 *  The honest framing ("matches a training record") survives; the cosine
 *  numbers, similarity values and training-row ids do not. */
export function stripVectorMath(s: string): string {
  if (!s) return s;
  return s
    .replace(
      /cosine\s*=\s*[\d.]+(?:\s+with\s+index\s+row\s+\S+)?(?:\s*\(?\s*>=?\s*[\d.]+\s*\))?/gi,
      "",
    )
    .replace(/max\s+cosine\s*=\s*[\d.]+/gi, "")
    .replace(/index\s+row\s+\S+/gi, "")
    .replace(/\(\s*\)/g, "")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([,.;:)])/g, "$1")
    .replace(/^[,;:\s]+|[,;:\s]+$/g, "")
    .trim();
}

/** The word the verdict chip shows. Unstable wording routes a would-be-clear
 *  report to REVIEW (the honest "our biggest weakness made visible" rule);
 *  HIGH/MODERATE already route, so their word stands. */
export function effectiveWord(
  band: VerdictWord,
  stability?: Stability | null,
  highSpreadAbove: number = UNSTABLE_SPREAD_DEFAULT,
): VerdictWord {
  const unstable = !!stability && stability.spread > highSpreadAbove;
  return unstable && (band === "LOW" || band === "CLEAR") ? "REVIEW" : band;
}