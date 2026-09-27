/* /analytics — the decision-grade analytics surface (redesign-plan §7.3):
 * time series FIRST, then density ranking with a mandatory adjustable min-n
 * guard, then pattern mining — every statistic showing n and a CI labelled as
 * the RATE's. Consumes the sanctioned @/components/ui primitives and the
 * @/components/domain DensityTable + PatternCard.
 *
 * Slice: dashboard/src/features/analytics/** (ANALYTICS). recharts is
 * lazy-loaded via dynamic import so it never lands in the initial chunk.
 * No fabricated data anywhere: offline → error state, never mock numbers. */

import { Suspense, lazy, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  CardHeader,
  Chip,
  DateRangePicker,
  EmptyState,
  ErrorState,
  PageHeader,
  Select,
  Skeleton,
  type DateRangeValue,
} from "@/components/ui";
import type { DensityRow, PatternOut } from "@/lib/types";
import type { Lang } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";
import { DensityTable } from "@/components/domain/density-table";
import { PatternCard } from "@/components/domain/pattern-card";
import {
  fetchAllReports,
  fetchDensity,
  fetchMetrics,
  fetchPatterns,
  type DensityWire,
  type MetricsWire,
  type PatternWire,
  type ReportSummary,
} from "./lib/api";
import {
  buildTrendBuckets,
  flagThreshold,
  formatThreshold,
  fmtPer100,
  hasServedFlagThreshold,
  setFlagThreshold,
  rankDensity,
  splitByMinN,
  toDensityStat,
  trendDelta,
  type Facet,
  type Granularity,
  type RankingMode,
} from "./lib/stats";
import { t } from "./phrases";

/* Lazy chart chunk — recharts resolves only inside these dynamic imports. */
const TimeSeriesChart = lazy(() =>
  import("./charts").then((m) => ({ default: m.TimeSeriesChart })),
);
const DensityChart = lazy(() =>
  import("./charts").then((m) => ({ default: m.DensityChart })),
);

const PATTERN_KINDS: { value: "site_activity" | "activity_barrier"; label: "siteXactivity" | "activityXbarrier" }[] = [
  { value: "site_activity", label: "siteXactivity" },
  { value: "activity_barrier", label: "activityXbarrier" },
];
const MIN_N_OPTIONS = [
  { value: "5", label: "n ≥ 5" },
  { value: "10", label: "n ≥ 10" },
  { value: "15", label: "n ≥ 15" },
  { value: "20", label: "n ≥ 20" },
  { value: "50", label: "n ≥ 50" },
];
const MIN_N_DEFAULT = 10;
const PATTERN_PREVIEW_LIMIT = 10;

function Segmented<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
  className,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn("inline-flex w-fit gap-1 rounded-md border border-border-subtle bg-surface-sunken p-1", className)}
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            "relative min-h-9 rounded-sm px-4 text-sm font-semibold whitespace-nowrap transition-colors duration-150 after:absolute after:inset-x-0 after:-inset-y-1 after:content-['']",
            o.value === value
              ? "bg-surface-card text-content-primary shadow-sm"
              : "text-content-secondary hover:text-content-primary",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function ChartLegend({ lang }: { lang: Lang }) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-content-secondary">
      <span className="inline-flex items-center gap-2">
        <span className="inline-block h-0.5 w-4 bg-verdict-high-fill" aria-hidden />
        {t(lang, "rateAxis")} · {t(lang, "ciOfFlagRate")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-xs bg-verdict-uncertain/40" aria-hidden />
        {t(lang, "reportsAxis")}
      </span>
    </div>
  );
}

function SectionCard({
  title,
  meta,
  actions,
  children,
}: {
  title: string;
  meta: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border-subtle bg-surface-card p-5 shadow-sm md:p-6">
      <CardHeader title={title} meta={meta} actions={actions} className="mb-5" />
      {children}
    </section>
  );
}

function ControlLabel({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label
      className="text-caption font-medium tracking-wide text-content-secondary uppercase"
      {...(htmlFor !== undefined ? { htmlFor } : {})}
    >
      {children}
    </label>
  );
}

export default function AnalyticsView({ lang }: { lang: Lang }) {
  /* ---- primary data (all-reports walk + metrics cross-check) ---- */
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [reloadKey, setReloadKey] = useState(0);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loadedProgress, setLoadedProgress] = useState(0);
  const [metrics, setMetrics] = useState<MetricsWire | null>(null);
  const [reportsTruncated, setReportsTruncated] = useState(false);
  const [thresholdVerified, setThresholdVerified] = useState(false);

  /* ---- server aggregates ---- */
  const [densityPhase, setDensityPhase] = useState<"loading" | "ready" | "error">("loading");
  const [densityRows, setDensityRows] = useState<DensityWire[]>([]);
  const [patternPhase, setPatternPhase] = useState<"loading" | "ready" | "error">("loading");
  const [patterns, setPatterns] = useState<PatternWire[]>([]);

  /* ---- controls ---- */
  const [granularity, setGranularity] = useState<Granularity>("month");
  const [range, setRange] = useState<{ from: string | null; to: string | null }>({
    from: null,
    to: null,
  });
  const [facet, setFacet] = useState<Facet>("site");
  const [minN, setMinN] = useState(MIN_N_DEFAULT);
  const [ranking, setRanking] = useState<RankingMode>("wilson");
  const [patternKind, setPatternKind] = useState<"site_activity" | "activity_barrier">(
    "site_activity",
  );
  const [patternMinN, setPatternMinN] = useState(MIN_N_DEFAULT);
  const [expandedPatternIds, setExpandedPatternIds] = useState<string[]>([]);
  const [showAllPatterns, setShowAllPatterns] = useState(false);
  const [activeView, setActiveView] = useState<"trend" | "density" | "patterns">("trend");

  useEffect(() => {
    let cancelled = false;
    setPhase("loading");
    setLoadedProgress(0);
    setMetrics(null);
    setReportsTruncated(false);
    setThresholdVerified(false);
    setFlagThreshold(null);
    (async () => {
      try {
        const m = await fetchMetrics().catch(() => null);
        if (cancelled) return;
        setMetrics(m);
        setThresholdVerified(hasServedFlagThreshold());
        const walk = await fetchAllReports((loaded) => {
          if (!cancelled) setLoadedProgress(loaded);
        });
        if (cancelled) return;
        setReports(walk.reports);
        setReportsTruncated(walk.truncated);
        setPhase("ready");
      } catch {
        if (!cancelled) setPhase("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  useEffect(() => {
    let cancelled = false;
    setDensityPhase("loading");
    fetchDensity(facet, range)
      .then((rows) => {
        if (!cancelled) {
          setDensityRows(rows);
          setDensityPhase("ready");
        }
      })
      .catch(() => {
        if (!cancelled) setDensityPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [facet, range, reloadKey]);

  useEffect(() => {
    let cancelled = false;
    setPatternPhase("loading");
    fetchPatterns(patternKind, patternMinN)
      .then((rows) => {
        if (!cancelled) {
          setPatterns(rows);
          setExpandedPatternIds([]);
          setShowAllPatterns(false);
          setPatternPhase("ready");
        }
      })
      .catch(() => {
        if (!cancelled) setPatternPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [patternKind, patternMinN, reloadKey]);

  /* ---- derived statistics ---- */
  const dated = useMemo(
    () =>
      reports
        .filter((r) => r.dateIso !== null)
        .map((r) => ({ dateIso: r.dateIso as string, flagged: r.flagged }))
        .sort((a, b) => a.dateIso.localeCompare(b.dateIso)),
    [reports],
  );
  const undated = reports.length - dated.length;
  const dateBounds = useMemo(
    () => (dated.length > 0 ? { min: dated[0].dateIso, max: dated[dated.length - 1].dateIso } : null),
    [dated],
  );
  const buckets = useMemo(
    () => buildTrendBuckets(dated, granularity, range),
    [dated, granularity, range],
  );
  const windowHasData = useMemo(() => buckets.some((b) => b.n > 0), [buckets]);
  const delta = useMemo(() => trendDelta(buckets, 4), [buckets]);
  const clientFlagged = useMemo(
    () => reports.filter((r) => r.score >= flagThreshold()).length,
    [reports],
  );
  const thresholdMismatch = metrics !== null && clientFlagged !== metrics.n_flagged;

  const densityStats = useMemo(() => densityRows.map(toDensityStat), [densityRows]);
  const rankedRows = useMemo(() => rankDensity(densityStats, ranking), [densityStats, ranking]);
  const guardSplit = useMemo(() => splitByMinN(rankedRows, minN), [rankedRows, minN]);
  const chartRows = useMemo(() => guardSplit.ranked, [guardSplit]);

  /** @/components/domain DensityTable wants lib/types DensityRow (with rank);
   * rank here is OUR client-side ranking order (Wilson LB or raw rate) — the
   * table renders rows in the order given. prev_rank is unused on this
   * surface (no Movement column); it mirrors rank to satisfy the type. */
  const tableRows: DensityRow[] = useMemo(
    () =>
      rankedRows.map((r, i) => ({
        key: r.key,
        n_reports: r.nReports,
        n_flagged: r.nFlagged,
        sif_rate: r.rate,
        mean_score: r.meanScore,
        rank: i + 1,
        prev_rank: i + 1,
      })),
    [rankedRows],
  );
  const patternRows: PatternOut[] = useMemo(
    () => patterns.map((p, i) => ({ id: `${patternKind}-${i + 1}`, kind: patternKind, ...p })),
    [patterns, patternKind],
  );
  const visiblePatternRows = showAllPatterns
    ? patternRows
    : patternRows.slice(0, PATTERN_PREVIEW_LIMIT);
  const allPatternsSaturated =
    patternRows.length > 0 && patternRows.every((p) => p.sif_rate >= 0.999);

  /* DateRangePicker bridge: ISO range ↔ DateRange. */
  const pickerValue: DateRangeValue = useMemo(
    () => ({
      from: range.from ? new Date(`${range.from}T00:00:00`) : undefined,
      to: range.to ? new Date(`${range.to}T00:00:00`) : undefined,
    }),
    [range],
  );

  const setPreset = (preset: "all" | "90" | "12m") => {
    if (!dateBounds) return;
    if (preset === "all") setRange({ from: null, to: null });
    else if (preset === "90") setRange({ from: isoDaysBefore(dateBounds.max, 90), to: dateBounds.max });
    else setRange({ from: isoDaysBefore(dateBounds.max, 365), to: dateBounds.max });
  };

  function isoDaysBefore(iso: string, days: number): string {
    const d = new Date(`${iso}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() - days);
    return d.toISOString().slice(0, 10);
  }

  if (phase === "error") {
    return (
      <section aria-label={t(lang, "analyticsTitle")} className="space-y-6">
        <PageHeader eyebrow={t(lang, "analyticsEyebrow")} title={t(lang, "analyticsTitle")} />
        <ErrorState
          title={t(lang, "dataUnavailable")}
          description={t(lang, "noFabricatedData")}
          className="max-w-xl"
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      </section>
    );
  }

  return (
    <section aria-label={t(lang, "analyticsTitle")} className="space-y-6">
      <PageHeader
        eyebrow={t(lang, "analyticsEyebrow")}
        title={t(lang, "analyticsTitle")}
        description={t(lang, "analyticsSub")}
      >
        <p className="text-sm text-content-secondary">
          <span className="font-medium text-content-primary">
            {phase === "ready"
              ? t(lang, "reportCoverage", { count: reports.length.toLocaleString("en-IN") })
              : t(lang, "loadedProgress", { loaded: loadedProgress.toLocaleString("en-IN") })}
          </span>
          {phase === "ready" && ` · ${t(lang, "thresholdSummary", { threshold: formatThreshold(flagThreshold()) })}`}
        </p>
        {phase === "ready" && reportsTruncated && (
          <p className="mt-1 text-xs text-content-secondary">{t(lang, "truncatedReports")}</p>
        )}
        {phase === "ready" && !thresholdVerified && (
          <p className="mt-1 text-xs text-content-secondary">{t(lang, "thresholdUnverified")}</p>
        )}
        {(undated > 0 || thresholdMismatch) && (
          <details className="max-w-3xl text-xs text-content-secondary">
            <summary className="w-fit cursor-pointer rounded-sm font-medium text-content-link">
              {t(lang, "dataNotes")}
            </summary>
            <div className="mt-2 space-y-1 border-l-2 border-border-default pl-3">
              {undated > 0 && <p>{t(lang, "undatedNote", { undated, total: reports.length })}</p>}
              {thresholdMismatch && metrics && (
                <p>
                  {t(lang, "thresholdMismatch", {
                    threshold: formatThreshold(flagThreshold()),
                    client: clientFlagged,
                    server: metrics.n_flagged,
                  })}
                </p>
              )}
            </div>
          </details>
        )}
      </PageHeader>

      <div
        role="tablist"
        aria-label={t(lang, "analyticsViews")}
        className="flex max-w-xl items-center gap-6 overflow-x-auto overflow-y-hidden border-b border-border-subtle"
      >
        {([
          ["trend", t(lang, "viewTrend")],
          ["density", t(lang, "viewHotspots")],
          ["patterns", t(lang, "viewPatterns")],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={activeView === value}
            onClick={() => setActiveView(value)}
            className={cn(
              "-mb-px min-h-11 shrink-0 border-b-2 px-1 text-sm font-semibold whitespace-nowrap transition-colors",
              activeView === value
                ? "border-action-primary text-content-primary"
                : "border-transparent text-content-secondary hover:text-content-primary",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* One focused analysis at a time keeps the page readable. */}
      {activeView === "trend" && (
      <SectionCard title={t(lang, "trendTitle")} meta={t(lang, "trendSub")}>
        <div className="mb-4 flex flex-wrap items-end gap-x-5 gap-y-3">
          <div className="flex flex-col gap-1">
            <ControlLabel>{t(lang, "period")}</ControlLabel>
            <Segmented<Granularity>
              ariaLabel={t(lang, "period")}
              value={granularity}
              onChange={setGranularity}
              options={[
                { value: "month", label: t(lang, "granularityMonth") },
                { value: "week", label: t(lang, "granularityWeek") },
              ]}
            />
          </div>
          <div className="flex flex-col gap-1">
            <ControlLabel>{t(lang, "window")}</ControlLabel>
            <Segmented<"all" | "90" | "12m">
              ariaLabel={t(lang, "window")}
              value={
                range.from === null && range.to === null
                  ? "all"
                  : range.from !== null &&
                      dateBounds !== null &&
                      range.from <= isoDaysBefore(dateBounds.max, 92)
                    ? "12m"
                    : "90"
              }
              onChange={setPreset}
              options={[
                { value: "all", label: t(lang, "allTime") },
                { value: "90", label: t(lang, "last90") },
                { value: "12m", label: t(lang, "last12m") },
              ]}
            />
          </div>
          <div className="flex flex-col gap-1">
            <ControlLabel>{t(lang, "customWindow")}</ControlLabel>
            <DateRangePicker
              lang={lang}
              emptyLabel={t(lang, "allDates")}
              ariaLabel={t(lang, "selectDateRange")}
              value={pickerValue}
              onChange={(value) => {
                if (!value) {
                  setRange({ from: null, to: null });
                  return;
                }
                const toIso = (d: Date) =>
                  new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
                setRange({
                  from: value.from ? toIso(value.from) : null,
                  to: value.to ? toIso(value.to) : null,
                });
              }}
            />
          </div>
        </div>
        {phase === "loading" ? (
          <Skeleton className="h-64 w-full" aria-hidden />
        ) : dated.length === 0 || !windowHasData ? (
          <EmptyState title={t(lang, "noDatedReports")} className="border-0 bg-transparent px-0 py-6" />
        ) : (
          <div className="space-y-3">
            {delta && (
              <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-body">
                <span className="font-medium text-content-primary">
                  {t(lang, "deltaLabel", {
                    k: 4,
                    unit: granularity === "week" ? t(lang, "unitWeek") : t(lang, "unitMonth"),
                  })}
                  :{" "}
                  <span className="font-mono">
                    {fmtPer100(delta.priorRate / 100)} → {fmtPer100(delta.recentRate / 100)}
                  </span>{" "}
                  {t(lang, "rateAxis")}{" "}
                  <span
                    className={cn(
                      "font-mono font-semibold",
                      delta.delta >= 0 ? "text-verdict-high" : "text-content-secondary",
                    )}
                  >
                    ({delta.delta >= 0 ? "+" : "−"}
                    {Math.abs(delta.delta).toFixed(1)})
                  </span>
                </span>
                <span className="font-mono text-caption text-content-secondary">
                  n {delta.priorN} → {delta.recentN} {t(lang, "reportsShort")}
                </span>
              </p>
            )}
            <Suspense
              fallback={
                <Skeleton className="h-72 w-full" aria-hidden />
              }
            >
              <TimeSeriesChart buckets={buckets} granularity={granularity} lang={lang} />
            </Suspense>
            <ChartLegend lang={lang} />
          </div>
        )}
      </SectionCard>
      )}

      {/* ---- 2. Density ranking with mandatory adjustable min-n guard ---- */}
      {activeView === "density" && (
      <SectionCard
        title={t(lang, "densityTitle")}
        meta={t(lang, "densitySub")}
        actions={
          <Segmented<Facet>
            ariaLabel={t(lang, "facet")}
            value={facet}
            onChange={setFacet}
            options={[
              { value: "site", label: t(lang, "facetSite") },
              { value: "activity", label: t(lang, "facetActivity") },
              { value: "contractor", label: t(lang, "facetContractor") },
            ]}
          />
        }
      >
        {densityPhase === "error" ? (
          <ErrorState
            title={t(lang, "densityTitle")}
            description={t(lang, "dataUnavailable")}
            onRetry={() => setReloadKey((k) => k + 1)}
            className="border-0 bg-transparent px-0 py-6"
          />
        ) : densityPhase === "loading" ? (
          <Skeleton className="h-64 w-full" aria-hidden />
        ) : (
          <div className="space-y-4">
            <Suspense fallback={<Skeleton className="h-80 w-full" aria-hidden />}>
              <DensityChart rows={chartRows} lang={lang} />
            </Suspense>
            <div className="flex flex-wrap items-end gap-x-5 gap-y-3">
              <div className="flex w-40 flex-col gap-1">
                <ControlLabel htmlFor="analytics-min-n">{t(lang, "minN")}</ControlLabel>
                <Select
                  id="analytics-min-n"
                  size="sm"
                  value={String(minN)}
                  onChange={(v) => setMinN(Number(v))}
                  options={MIN_N_OPTIONS}
                />
              </div>
              <div className="flex flex-col gap-1">
                <ControlLabel>{t(lang, "ranking")}</ControlLabel>
                <Segmented<RankingMode>
                  ariaLabel={t(lang, "ranking")}
                  value={ranking}
                  onChange={setRanking}
                  options={[
                    { value: "wilson", label: t(lang, "rankedByWilson") },
                    { value: "rate", label: t(lang, "rankedByRate") },
                  ]}
                />
              </div>
              <p className="max-w-md text-caption text-content-secondary">
                {t(lang, "rankedByHint")}
              </p>
            </div>
            {guardSplit.quarantined.length > 0 && (
              <Chip tone="uncertain">
                {t(lang, "quarantineNote", {
                  count: guardSplit.quarantined.length,
                  minN,
                })}
              </Chip>
            )}
            <DensityTable rows={tableRows} by={facet} dateRange={range} minN={minN} lang={lang} />
            <p className="text-caption text-content-secondary">{t(lang, "confidenceNote")}</p>
          </div>
        )}
      </SectionCard>
      )}

      {/* ---- 3. Recurring patterns with labelled rate CIs + provenance ---- */}
      {activeView === "patterns" && (
      <SectionCard title={t(lang, "patternsTitle")} meta={t(lang, "patternBlurb")}>
        <div className="mb-4 flex flex-wrap items-end gap-x-5 gap-y-3">
          <div className="flex flex-col gap-1">
            <ControlLabel>{t(lang, "patternKind")}</ControlLabel>
            <Segmented
              ariaLabel={t(lang, "patternKind")}
              value={patternKind}
              onChange={setPatternKind}
              options={PATTERN_KINDS.map((k) => ({ value: k.value, label: t(lang, k.label) }))}
            />
          </div>
          <div className="flex w-44 flex-col gap-1">
            <ControlLabel htmlFor="analytics-pattern-minn">{t(lang, "minCellN")}</ControlLabel>
            <Select
              id="analytics-pattern-minn"
              size="sm"
              value={String(patternMinN)}
              onChange={(v) => setPatternMinN(Number(v))}
              options={MIN_N_OPTIONS.filter((o) => o.value !== "15" && o.value !== "50")}
            />
          </div>
        </div>
        {patternPhase === "error" ? (
          <ErrorState
            title={t(lang, "patternsTitle")}
            description={t(lang, "dataUnavailable")}
            onRetry={() => setReloadKey((k) => k + 1)}
            className="border-0 bg-transparent px-0 py-6"
          />
        ) : patternPhase === "loading" ? (
          <Skeleton className="h-64 w-full" aria-hidden />
        ) : patternRows.length === 0 ? (
          <EmptyState title={t(lang, "patternsEmpty")} className="border-0 bg-transparent px-0 py-6" />
        ) : (
          <div className="space-y-3">
            <div className="space-y-1.5">
              {visiblePatternRows.map((p, i) => {
                const expanded = expandedPatternIds.includes(p.id);
                const pairLabel = p.site ?? p.barrier ?? "";
                const id = `pattern-detail-${p.id}`;
                return (
                  <article key={p.id} className="rounded-md border border-border-subtle bg-surface-card">
                    <button
                      type="button"
                      aria-expanded={expanded}
                      aria-controls={id}
                      onClick={() => setExpandedPatternIds((current) =>
                        expanded ? current.filter((item) => item !== p.id) : [...current, p.id],
                      )}
                      className="flex min-h-10 w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-md px-3 py-2 text-left text-label text-content-primary hover:bg-action-ghost-hover focus-visible:outline-none"
                    >
                      <span className="w-7 shrink-0 font-mono text-caption text-content-secondary">#{i + 1}</span>
                      <span className="font-medium">{p.activity}</span>
                      {pairLabel && <span className="text-content-secondary">× {pairLabel}</span>}
                      <span className="ml-auto font-mono text-caption text-content-secondary">
                        {t(lang, "patternCount", { n: p.n })}
                      </span>
                      <span className="font-mono text-caption font-medium text-content-primary">
                        {t(lang, "patternLift", { lift: p.lift.toFixed(2) })}
                      </span>
                    </button>
                    <div id={id} hidden={!expanded} className="border-t border-border-subtle p-2.5">
                      <PatternCard pattern={p} minN={MIN_N_DEFAULT} lang={lang} className="border-0 bg-transparent p-1" />
                    </div>
                  </article>
                );
              })}
            </div>
            {patternRows.length > PATTERN_PREVIEW_LIMIT && (
              <button
                type="button"
                aria-expanded={showAllPatterns}
                onClick={() => setShowAllPatterns((show) => !show)}
                className="rounded-sm px-2 py-1 text-label font-medium text-content-secondary underline hover:text-content-primary focus-visible:outline-none"
              >
                {t(
                  lang,
                  showAllPatterns ? "showTopPatternRows" : "showMorePatternRows",
                  { count: patternRows.length - PATTERN_PREVIEW_LIMIT },
                )}
              </button>
            )}
            <div className="space-y-1 rounded-md border border-border-subtle bg-surface-sunken px-4 py-3 text-caption text-content-secondary">
              <p>{t(lang, "patternProvenance")}</p>
              {allPatternsSaturated && (
                <p className="font-medium text-content-primary">{t(lang, "saturationNote")}</p>
              )}
            </div>
          </div>
        )}
      </SectionCard>
      )}
    </section>
  );
}