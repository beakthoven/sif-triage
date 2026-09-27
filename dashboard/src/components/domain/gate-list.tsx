/*
 * GateList — the advisory gates on a report, reviewer-facing.
 *
 * Fixes:
 *  - badge vs gray are visually distinct: gray rows carry a REVIEW chip + a
 *    sunken background + "routed to human review"; badge rows are plain
 *    informational rows. No two states share a look.
 *  - No debug internals: gate slugs are never rendered (human labels only),
 *    and the near-dup copy is the phrasebook's honest framing — the raw
 *    `cosine=1.000 with index row syn-cs-e-0188 (>= 0.91)` leak is gone for
 *    good. Any residual vector math in other details is stripped too.
 */

import type { Lang } from "@/lib/phrasebook";
import type { GateState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { dt, gateLabel } from "./domain-strings";
import { DomChip, DtLabel } from "./ui-bits";

export function GateList({
  gates,
  lang = "en",
  className,
}: {
  gates?: GateState[] | null;
  lang?: Lang;
  className?: string;
}) {
  const fired = (gates ?? []).filter((g) => g.triggered);
  if (fired.length === 0) return null;
  return (
    <section className={cn("flex flex-col gap-3", className)}>
      <DtLabel>{dt(lang, "gatesHeading")}</DtLabel>
      <ul className="flex flex-col gap-2">
        {fired.map((gate, i) => {
          const gray = gate.action === "gray";
          // The gate card shows the reviewer-facing label only. The report
          // evidence above is the place to inspect the actual wording;
          // detector internals and implementation explanations are omitted.
          const label = gateLabel(gate.name, lang);
          return (
            <li
              key={`${gate.name}-${i}`}
              className={cn(
                "flex flex-col gap-1 rounded-md border px-3 py-2",
                gray ? "border-verdict-uncertain/30 bg-verdict-uncertain-chip/60" : "border-border-subtle",
              )}
            >
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <DomChip tone={gray ? "uncertain" : "neutral"}>
                  {gray ? dt(lang, "wordReview") : dt(lang, "informational")}
                </DomChip>
                <span className="text-sm font-medium text-content-primary">{label}</span>
                {gray && (
                  <span className="text-xs text-content-secondary">{dt(lang, "gateRoutedToReview")}</span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}