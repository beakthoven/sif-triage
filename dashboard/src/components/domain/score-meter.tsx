/*
 * ScoreMeter — the 0…1 triage score as a horizontal track, filled in the
 * band's fill shade, with the SERVER's operating point marked when known.
 * Decorative reinforcement only: the numeric score and the band word always
 * render next to it, so the meter is aria-hidden.
 */

import { cn } from "@/lib/utils";
import type { VerdictWord } from "./domain-types";

const FILL: Record<VerdictWord | "NONE", string> = {
  HIGH: "bg-verdict-high-fill",
  MODERATE: "bg-verdict-moderate-fill",
  LOW: "bg-verdict-low-fill",
  CLEAR: "bg-verdict-clear-fill",
  REVIEW: "bg-verdict-uncertain-fill",
  NONE: "bg-verdict-low-fill",
};

export function ScoreMeter({
  score,
  band,
  threshold,
  className,
}: {
  score: number;
  band: VerdictWord | null;
  threshold?: number | null;
  className?: string;
}) {
  const pct = Math.min(100, Math.max(0, score * 100));
  const tick = threshold != null ? Math.min(100, Math.max(0, threshold * 100)) : null;
  return (
    <div aria-hidden="true" className={cn("flex flex-col gap-1", className)}>
      <div className="relative h-3 w-full rounded-full bg-surface-sunken ring-1 ring-border-subtle ring-inset">
        <div
          className={cn("absolute inset-y-0 left-0 rounded-full transition-[width] duration-320 ease-standard", FILL[band ?? "NONE"])}
          style={{ width: `${pct}%` }}
        />
        {tick != null && (
          <div
            className="absolute -top-1 -bottom-1 w-0.5 -translate-x-1/2 rounded-full bg-content-primary"
            style={{ left: `${tick}%` }}
          />
        )}
      </div>
      <div className="relative flex justify-between font-mono text-xs text-content-secondary">
        <span>0</span>
        {tick != null && (
          <span className="absolute -translate-x-1/2 text-content-primary" style={{ left: `${tick}%` }}>
            {threshold}
          </span>
        )}
        <span>1</span>
      </div>
    </div>
  );
}
