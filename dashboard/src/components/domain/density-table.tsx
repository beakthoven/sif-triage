/*
 * DensityTable — the precursor-density ranking with the two REQUIRED honest
 * stats: a min-n guard and a Wilson 95% CI on the flagged rate.
 *
 * Fixes today's "ranks noise" defect: 173 of 341 entities had n = 1 and
 * ranked at "100 per 100" with no caveat. Rows below min-n are held out of
 * the ranking but never silently hidden — they appear in a disclosure.
 * The CI is computed for the rate (Wilson score interval) and labelled as
 * such, in per-100 units matching the flagged column.
 */

import { formatDisplayDate } from "@/lib/format";
import type { Lang } from "@/lib/phrasebook";
import { t } from "@/lib/phrasebook";
import type { DensityRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { wilson } from "./domain-logic";
import { dt } from "./domain-strings";
import { DtLabel } from "./ui-bits";

export function DensityTable({
  rows,
  by,
  dateRange,
  minN = 3,
  lang = "en",
  className,
}: {
  rows: DensityRow[];
  by: "site" | "activity" | "contractor";
  dateRange?: { from?: string | null; to?: string | null } | null;
  /** Minimum reports for a row to rank. Held-out rows stay visible in a
   *  disclosure below the table — transparent, never hidden. */
  minN?: number;
  lang?: Lang;
  className?: string;
}) {
  const facetLabel =
    by === "site" ? t(lang, "site") : by === "activity" ? dt(lang, "colActivity") : dt(lang, "colContractor");
  const ranked = rows.filter((r) => r.n_reports >= minN);
  const heldOut = rows.filter((r) => r.n_reports < minN);
  if (rows.length === 0) {
    return (
      <p className={cn("text-sm leading-5 text-content-secondary", className)}>
        {dt(lang, "densityNoRows")}
      </p>
    );
  }
  const rangeLabel =
    dateRange?.from && dateRange?.to
      ? `${formatDisplayDate(dateRange.from, lang)} – ${formatDisplayDate(dateRange.to, lang)}`
      : dateRange?.from
        ? formatDisplayDate(dateRange.from, lang)
        : dateRange?.to
          ? formatDisplayDate(dateRange.to, lang)
          : null;
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <DtLabel>{facetLabel}</DtLabel>
        <span className="font-mono text-xs leading-4 text-content-secondary">
          {rangeLabel ? `${rangeLabel} · ` : ""}
          {dt(lang, "densityCiHeader")} · min n = {minN}
        </span>
      </div>
      <div className="max-h-140 overflow-auto rounded-md border border-border-subtle">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">
            {facetLabel} — {t(lang, "densitySub")}
          </caption>
          <thead className="sticky top-0 z-10">
            <tr className="border-b border-border-default bg-surface-canvas">
              <th scope="col" className="h-12 px-4 text-sm font-semibold text-content-secondary">
                {t(lang, "rank")}
              </th>
              <th scope="col" className="h-12 px-4 text-sm font-semibold text-content-secondary">
                {facetLabel}
              </th>
              <th scope="col" className="h-12 px-4 text-right text-sm font-semibold text-content-secondary">
                {t(lang, "reports")}
              </th>
              <th scope="col" className="h-12 px-4 text-right text-sm font-semibold text-content-secondary">
                {t(lang, "flaggedPer100")}
              </th>
              <th scope="col" className="h-12 px-4 text-right text-sm font-semibold text-content-secondary">
                {dt(lang, "densityCiHeader")}
              </th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((row, i) => {
              const [lo, hi] = wilson(row.sif_rate, row.n_reports);
              return (
                <tr
                  key={row.key}
                  className={cn(
                    "border-b border-border-subtle bg-surface-card transition-colors duration-150 last:border-b-0 even:bg-surface-zebra hover:bg-surface-sunken",
                  )}
                >
                  <td className="h-12 px-4 font-mono text-sm text-content-secondary">
                    {i + 1}
                  </td>
                  <td className="h-12 px-4 text-sm text-content-primary">
                    {row.key}
                  </td>
                  <td className="h-12 px-4 text-right font-mono text-sm text-content-secondary">
                    {row.n_reports}
                  </td>
                  <td className="h-12 px-4 text-right font-mono text-sm text-content-primary">
                    {(row.sif_rate * 100).toFixed(1)}
                  </td>
                  <td className="h-12 px-4 text-right font-mono text-sm text-content-secondary">
                    {Math.round(lo * 100)}–{Math.round(hi * 100)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {heldOut.length > 0 ? (
        <details className="rounded-md border border-dashed border-border-subtle px-3 py-2">
          <summary className="cursor-pointer text-xs leading-4 text-content-secondary">
            {dt(lang, "densityHiddenCount", { c: heldOut.length })}
          </summary>
          <ul className="mt-1.5 flex list-disc flex-col gap-0.5 pl-4">
            {heldOut.map((row) => (
              <li key={row.key} className="text-xs leading-4 text-content-secondary">
                {row.key} — n = {row.n_reports} · {dt(lang, "densityNotRanked", { n: minN })}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}