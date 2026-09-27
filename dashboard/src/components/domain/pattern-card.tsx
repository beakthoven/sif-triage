/*
 * PatternCard — one lift-ranked co-occurrence cell with honest stats.
 *
 * Fixes the statistical mislabel: the published CI belongs to the RATE and is
 * now labelled "95% CI of the rate"; lift is labelled "lift — no CI published
 * for lift" (the server ships a rate CI only; claiming a lift CI would be
 * fabrication). Small-n cells carry a "low n — read with caution" chip.
 */

import type { Lang } from "@/lib/phrasebook";
import { t } from "@/lib/phrasebook";
import type { PatternOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { dt } from "./domain-strings";
import { DomChip } from "./ui-bits";

export function PatternCard({
  pattern,
  minN = 5,
  lang = "en",
  className,
}: {
  pattern: PatternOut;
  /** Below this n the card shows a read-with-caution chip. */
  minN?: number;
  lang?: Lang;
  className?: string;
}) {
  const pairLabel = pattern.site ?? pattern.barrier ?? "";
  const ruleLabel = pattern.rule ? pattern.rule.replace(/[_-]+/g, " ") : null;
  const pct = (v: number) => `${Math.round(Math.min(1, Math.max(0, v)) * 100)}%`;
  return (
    <article
      className={cn(
        "flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-card px-4 py-3",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="text-sm leading-5 font-semibold text-content-primary">
          {pattern.activity}
        </span>
        {pairLabel ? (
          <span className="text-sm leading-5 text-content-secondary">{pairLabel}</span>
        ) : null}
        <DomChip tone="neutral">
          {pattern.kind === "activity_barrier" ? t(lang, "activityBarrier") : t(lang, "siteActivity")}
        </DomChip>
      </div>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
        <span className="font-mono text-xs leading-4 text-content-secondary">n = {pattern.n}</span>
        <span className="font-mono text-xs leading-4 text-content-primary">
          {dt(lang, "patternRate")} {pct(pattern.sif_rate)}
          {" · "}
          {dt(lang, "patternRateCi")} [{pct(pattern.ci_low)}–{pct(pattern.ci_high)}]
        </span>
        <span className="font-mono text-xs leading-4 text-content-secondary">
          {dt(lang, "patternLiftLabel")} {pattern.lift.toFixed(2)} — {dt(lang, "patternLiftNoCi")}
        </span>
        {ruleLabel ? (
          <DomChip tone="neutral" title={pattern.rule ?? undefined}>
            {ruleLabel}
          </DomChip>
        ) : null}
        {pattern.n < minN ? <DomChip tone="uncertain">{dt(lang, "patternLowN")}</DomChip> : null}
      </div>
    </article>
  );
}