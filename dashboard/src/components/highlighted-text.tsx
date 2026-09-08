import type { EvidenceSpan } from "@/lib/types";
import { Fragment } from "react";

/** Renders canonical report text with amber evidence-span highlights.
 *  UI only slices at server-validated char offsets — never computes them. */
export function HighlightedText({
  text,
  spans,
}: {
  text: string;
  spans: EvidenceSpan[];
}) {
  const parts: { key: number; node: string; hit: boolean }[] = [];
  let cursor = 0;
  spans.forEach((s, i) => {
    if (s.start > cursor) parts.push({ key: i * 2, node: text.slice(cursor, s.start), hit: false });
    parts.push({ key: i * 2 + 1, node: text.slice(s.start, s.end), hit: true });
    cursor = s.end;
  });
  if (cursor < text.length) parts.push({ key: -1, node: text.slice(cursor), hit: false });

  return (
    <blockquote className="border-l-2 border-border pl-4 text-lg leading-relaxed text-foreground/90">
      {parts.map((p) =>
        p.hit ? (
          <mark key={p.key} className="span-highlight">
            {p.node}
          </mark>
        ) : (
          <Fragment key={p.key}>{p.node}</Fragment>
        ),
      )}
    </blockquote>
  );
}
