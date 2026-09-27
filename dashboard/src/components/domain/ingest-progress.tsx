/*
 * IngestProgress — real progress for the bulk ingest beat.
 *
 * Fixes the money-beat defects: the bar is no longer paced fiction (width is
 * done/total, unknown-total renders an honest indeterminate bar with no fake
 * percentage), ETA comes from the caller's measured rate, cancel is real,
 * and the failure state no longer lies "live data unchanged" — the honest
 * copy says some rows may have been saved and to check the count first
 * (the server keeps ingesting after a client timeout).
 */

import type { Lang } from "@/lib/phrasebook";
import { t } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";
import { dt } from "./domain-strings";
import { DomButton } from "./ui-bits";

export type IngestStatus = "running" | "complete" | "failed";

export function IngestProgress({
  done,
  total,
  status,
  etaSeconds,
  onCancel,
  lang = "en",
  className,
}: {
  done: number;
  total?: number | null;
  status: IngestStatus;
  etaSeconds?: number | null;
  onCancel?: () => void;
  lang?: Lang;
  className?: string;
}) {
  const indeterminate = !(typeof total === "number" && total > 0);
  const pct = indeterminate ? null : Math.min(100, Math.max(0, (done / (total as number)) * 100));
  const rowsLine = indeterminate
    ? `${done} ${dt(lang, "rowsUnit")}`
    : `${done} / ${total} ${dt(lang, "rowsUnit")}`;
  const statusLabel =
    status === "complete"
      ? t(lang, "ingestedDone")
      : status === "failed"
        ? dt(lang, "ingestFailedShort")
        : t(lang, "ingesting");
  const etaLabel =
    status === "running" && etaSeconds != null && etaSeconds > 0
      ? dt(lang, "ingestEta", { s: Math.max(1, Math.round(etaSeconds)) })
      : null;
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("flex flex-col gap-1.5 rounded-md border border-border-subtle bg-surface-card px-3 py-2.5", className)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <span className="text-sm leading-5 font-medium text-content-primary">
          {statusLabel}
        </span>
        <span className="font-mono text-xs leading-4 text-content-secondary">{rowsLine}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-sunken">
        {pct === null ? (
          <div className="h-full w-1/3 rounded-full bg-action-primary animate-pulse" />
        ) : (
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={total as number}
            aria-valuenow={done}
            aria-label={rowsLine}
            className="h-full rounded-full bg-action-primary transition-[width] duration-200 ease-out"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <span className="font-mono text-xs leading-4 text-content-secondary">{etaLabel ?? ""}</span>
        {onCancel && status === "running" ? (
          <DomButton variant="ghost" size="sm" onClick={onCancel}>
            {dt(lang, "ingestCancel")}
          </DomButton>
        ) : null}
      </div>
      {status === "failed" ? (
        <p className="text-xs leading-4 text-status-danger">{dt(lang, "ingestFailedHonest")}</p>
      ) : null}
    </div>
  );
}