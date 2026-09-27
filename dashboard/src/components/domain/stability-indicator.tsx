/*
 * StabilityIndicator — NEW. Makes the paraphrase instability (the probe's
 * most serious finding) visible, honest signal instead of a hidden failure.
 *
 * High spread → an "unstable wording" chip in the REVIEW tone, and (via
 * effectiveWord, used by VerdictCard) the report's word routes to REVIEW.
 * Spread/n/flip figures are the self-consistency fix's own output (A3);
 * when the runtime scored a single variant the caller omits the indicator.
 */

import type { Lang } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";
import { UNSTABLE_SPREAD_DEFAULT } from "./domain-logic";
import { dt } from "./domain-strings";
import type { Stability } from "./domain-types";
import { DomChip } from "./ui-bits";

export function StabilityIndicator({
  spread,
  nVariants,
  verdictFlips,
  highSpreadAbove = UNSTABLE_SPREAD_DEFAULT,
  lang = "en",
  className,
}: Stability & {
  /** Spread above which wording is described as "unstable" in this indicator. */
  highSpreadAbove?: number;
  lang?: Lang;
  className?: string;
}) {
  const unstable = spread > highSpreadAbove;
  return (
    <span
      className={cn("inline-flex flex-wrap items-center gap-x-2 gap-y-1", className)}
      title={unstable ? dt(lang, "unstableHint") : undefined}
    >
      {unstable ? (
        <DomChip tone="uncertain">{dt(lang, "unstableWording")}</DomChip>
      ) : (
        <DomChip tone="neutral">{dt(lang, "stableWording")}</DomChip>
      )}
      <span className="font-mono text-xs leading-4 text-content-secondary">
        {dt(lang, "scoreSpread")} {spread.toFixed(2)} · {nVariants} {dt(lang, "variantsScored")}
        {typeof verdictFlips === "number" && verdictFlips > 0
          ? ` · ${verdictFlips} ${dt(lang, "verdictFlipsLabel")}`
          : ""}
      </span>
    </span>
  );
}