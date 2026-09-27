/*
 * EvidenceText — the report text with evidence spans highlighted.
 *
 * Fixes:
 *  - Legibility: spans are underlined + tinted + medium weight (today's
 *    #EFE9DC-on-white is invisible).
 *  - Freshly classified reports: spans render straight from the prediction
 *    object (server always returns evidence_spans); no reliance on the lazy
 *    explanation fetch, so highlights appear at the moment of classification.
 *  - Exact-substring only: every span is re-validated against the text before
 *    it may render (the server's own invariant, re-checked client-side);
 *    stale/mismatched offsets are dropped, never shown misaligned.
 */

import type { Lang } from "@/lib/phrasebook";
import type { EvidenceSpan } from "@/lib/types";
import { cn } from "@/lib/utils";
import { spanSegments } from "./domain-logic";
import { dt } from "./domain-strings";
import { DtLabel } from "./ui-bits";

export function EvidenceText({
  text,
  spans,
  lang = "en",
  className,
}: {
  text: string;
  spans?: EvidenceSpan[] | null;
  lang?: Lang;
  className?: string;
}) {
  const segments = spanSegments(text, spans ?? []);
  const hasSpans = spans != null && spans.length > 0 && segments.some((s) => s.isSpan);
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <DtLabel>{dt(lang, "evidenceLabel")}</DtLabel>
      <p className="border-l-2 border-border-strong pl-4 text-base leading-7 break-words whitespace-pre-wrap text-content-primary">
        {segments.map((seg, i) =>
          seg.isSpan ? (
            <mark key={i} className="span-highlight">
              {seg.text}
            </mark>
          ) : (
            <span key={i}>{seg.text}</span>
          ),
        )}
      </p>
      {/* Honest absence: the model returned zero spans, or none survived
          offset validation (a measured weakness — probe §Result 2). State it;
          never fabricate highlights. */}
      {spans != null && !hasSpans && (
        <p className="text-xs text-content-secondary">{dt(lang, "noEvidenceSpans")}</p>
      )}
    </div>
  );
}