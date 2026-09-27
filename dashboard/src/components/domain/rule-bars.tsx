/*
 * RuleBars — scores for the seven rules this model can assess. Out-of-scope
 * rules are disclosed in Data & limitations, not repeated on each report.
 */

import { t, type Lang } from "@/lib/phrasebook";
import type { RuleScore } from "@/lib/types";
import { cn } from "@/lib/utils";
import { dt } from "./domain-strings";
import { DomChip, DtLabel } from "./ui-bits";

export function RuleBars({
  rules,
  lang = "en",
  limit,
  className,
}: {
  rules?: RuleScore[] | null;
  lang?: Lang;
  /** Show only the top-N in-scope rules (compact result views). */
  limit?: number;
  className?: string;
}) {
  const sorted = [...(rules ?? [])]
    .filter((rule) => rule.in_scope)
    .sort((a, b) => b.prob - a.prob);
  const shown = limit != null ? sorted.slice(0, limit) : sorted;
  if (shown.length === 0) return null;
  return (
    <section className={cn("flex flex-col gap-3", className)}>
      <DtLabel>{t(lang, "ruleProbs")}</DtLabel>
      <ul className="flex flex-col gap-3">
        {shown.map((rule) =>
          rule.in_scope ? (
            <li key={rule.code} className="flex flex-col gap-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
                <span className="text-sm font-medium text-content-primary">{rule.name}</span>
                <span className="font-mono text-xs text-content-secondary">
                  {Math.round(Math.min(1, Math.max(0, rule.prob)) * 100)}%
                </span>
              </div>
              {rule.prob >= 0.5 && rule.cue_hit === false && (
                <span
                  className="w-fit rounded-sm bg-surface-sunken px-2 py-1 text-[11px] leading-4 text-content-secondary"
                  title={dt(lang, "ruleNoExplicitCueHint")}
                >
                  {dt(lang, "ruleNoExplicitCue")}
                </span>
              )}
              <div className="h-2 w-full overflow-hidden rounded-full bg-surface-sunken" role="presentation">
                <div
                  className="h-full rounded-full bg-verdict-uncertain-fill"
                  style={{ width: `${Math.min(100, Math.max(0, rule.prob)) * 100}%` }}
                />
              </div>
            </li>
          ) : (
            <li
              key={rule.code}
              className="flex flex-col gap-1 rounded-md border border-dashed border-border-default px-3 py-2"
            >
              <span className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm text-content-secondary">{rule.name}</span>
                <DomChip tone="neutral">{dt(lang, "ruleOutOfScope")}</DomChip>
              </span>
              <span className="text-xs text-content-secondary">{dt(lang, "ruleOutOfScopeHint")}</span>
            </li>
          ),
        )}
      </ul>
    </section>
  );
}
