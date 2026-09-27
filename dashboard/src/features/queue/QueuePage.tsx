/* QUEUE — the risk-ordered triage worklist (route feature).
 *
 * Fixes measured in Phase 0 (docs/discovery/50-visual-triage.md §10, §11.1,
 * §11.8, §11.10): the register is no longer capped at 200 — every row is
 * paged off GET /api/reports (offset batches, no client cap); default order
 * is sif_score desc, not id desc; search matches report BODY text ("LOTO"
 * now hits "LOTO not applied"); rows carry id / site / activity / contractor
 * / date / score + verdict word + flags; the ingestion-vs-event date is
 * labelled instead of silently conflated. Loading, error and empty states
 * are mandatory and there is no fabricated fallback data.
 *
 * Shell contract: mount <QueuePage lang onOpenReport? onSelectReport?/> in a
 * route. URL state: ?sort&q&band&rule&site&activity&from&to (see filters.ts). */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { FilePlus2, Search, X } from "lucide-react";
import {
  Button,
  buttonVariants,
  Card,
  DateRangePicker,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  Progress,
  Select,
  type DateRangeValue,
  type SelectOption,
} from "@/components/ui";
import { cn } from "@/lib/utils";
import { getHealth, getRules, useClusters } from "@/lib/api";
import { t as tShared, type Lang } from "@/lib/phrasebook";
import type { ClusterOut, HealthOut, RuleInfo } from "@/lib/types";
import { fetchQueueRows, type QueueRow } from "./api";
import {
  applyFilters,
  DEFAULT_FILTERS,
  distinctOptions,
  isFiltersActive,
  parseFilters,
  serializeFilters,
  type QueueFilters,
  type QueueSort,
} from "./filters";
import { QueueTable } from "./QueueTable";
import { queueCountLine, queuePartialLine, tq } from "./strings";
import type { SortingState } from "@tanstack/react-table";

export interface QueuePageProps {
  lang?: Lang;
  selectedId?: number | null;
  onSelectReport?: (id: number) => void;
  onOpenReport?: (id: number) => void;
  className?: string;
}

const fmt = (n: number) => n.toLocaleString("en-IN");

function sortingFor(sort: QueueSort): SortingState {
  switch (sort) {
    case "score-asc":
      return [{ id: "score", desc: false }];
    case "id-desc":
      return [{ id: "id", desc: true }];
    case "id-asc":
      return [{ id: "id", desc: false }];
    case "score-desc":
    default:
      return [{ id: "score", desc: true }];
  }
}

const dateToIso = (d: Date | undefined): string | null =>
  d
    ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
    : null;
const isoToDate = (iso: string | null): Date | undefined =>
  iso ? new Date(`${iso}T00:00:00`) : undefined;

export function QueuePage({
  lang = "en",
  selectedId = null,
  onSelectReport,
  onOpenReport,
  className,
}: QueuePageProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<QueueFilters>(() => parseFilters(location.search));
  const openReport = onOpenReport ?? ((id: number) => navigate(`/report/${id}`));
  const [health, setHealth] = useState<HealthOut | null>(null);
  const [rules, setRules] = useState<RuleInfo[]>([]);
  const [rows, setRows] = useState<QueueRow[] | null>(null);
  const [loaded, setLoaded] = useState(0);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [selection, setSelection] = useState<Set<number>>(new Set());
  const [clusters, setClusters] = useState<ClusterOut[]>([]);
  const [clustersError, setClustersError] = useState(false);
  const clustersQ = useClusters();

  useEffect(() => {
    if (clustersQ.data) {
      setClusters(clustersQ.data.clusters);
      setClustersError(false);
    } else if (clustersQ.isError) {
      setClusters([]);
      setClustersError(true);
    }
  }, [clustersQ.data, clustersQ.isError]);

  // Full-register load: health (indexed count) + rules (rule filter) + every
  // report row, batched by offset. Errors render an error state — nothing is
  // shown from a partial load.
  useEffect(() => {
    const ctl = new AbortController();
    let alive = true;
    setRows(null);
    setLoaded(0);
    setLoadErr(null);
    (async () => {
      try {
        const [h, rs] = await Promise.all([getHealth(), getRules()]);
        if (!alive) return;
        setHealth(h);
        setRules(rs);
        const all = await fetchQueueRows(ctl.signal, (n) => {
          if (alive) setLoaded(n);
        });
        if (!alive) return;
        setRows(all);
      } catch (err) {
        if (!alive || ctl.signal.aborted) return;
        setLoadErr(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      alive = false;
      ctl.abort();
    };
  }, [reloadKey]);

  useEffect(() => {
    const next = parseFilters(location.search);
    setFilters((current) => serializeFilters(current) === serializeFilters(next) ? current : next);
  }, [location.key, location.search]);

  useEffect(() => {
    const qs = serializeFilters(filters);
    if (qs === serializeFilters(parseFilters(location.search))) return;
    const url = window.location.href;
    const timer = window.setTimeout(() => {
      if (window.location.href === url) setSearchParams(qs, { replace: true });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [filters, location, setSearchParams]);

  const ruleThresholds = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of rules) if (r.in_scope) m.set(r.key, r.threshold ?? 0.5);
    return m;
  }, [rules]);

  const filteredRows = useMemo(
    () => (rows === null ? [] : applyFilters(rows, filters, ruleThresholds)),
    [rows, filters, ruleThresholds],
  );
  const visibleGroups = useMemo(() => {
    const groupedIds = new Set<number>();
    const groups: { cluster: ClusterOut; visibleRows: QueueRow[]; representative: QueueRow }[] = [];
    for (const cluster of clusters) {
      const memberIds = new Set(cluster.member_ids);
      const visibleRows = filteredRows
        .filter((row) => memberIds.has(row.id))
        .sort((a, b) => a.id - b.id);
      const availableRows = visibleRows.filter((row) => !groupedIds.has(row.id));
      if (availableRows.length < 2) continue;
      const group = { cluster, visibleRows: availableRows, representative: availableRows[0] };
      groups.push(group);
      for (const row of availableRows) groupedIds.add(row.id);
    }
    return {
      groups,
      collapsed: groups.reduce((total, group) => total + group.visibleRows.length - 1, 0),
    };
  }, [clusters, filteredRows]);

  const siteOptions = useMemo(
    () => (rows === null ? [] : distinctOptions(rows, (r) => r.site)),
    [rows],
  );
  const activityOptions = useMemo(
    () => (rows === null ? [] : distinctOptions(rows, (r) => r.activity)),
    [rows],
  );

  const patchFilters = useCallback((patch: Partial<QueueFilters>) => {
    setFilters((current) => ({ ...current, ...patch }));
  }, []);

  const toggleRow = useCallback((id: number) => {
    setSelection((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const allSelected =
    rows !== null &&
    filteredRows.length > 0 &&
    filteredRows.every((r) => selection.has(r.id));
  const someSelected = filteredRows.some((r) => selection.has(r.id));
  const toggleAll = useCallback(() => {
    setSelection((cur) => {
      if (allSelected) {
        const next = new Set(cur);
        for (const r of filteredRows) next.delete(r.id);
        return next;
      }
      return new Set([...cur, ...filteredRows.map((r) => r.id)]);
    });
  }, [allSelected, filteredRows]);

  const indexed = health?.n_reports ?? null;
  const loading = rows === null && loadErr === null;
  const filtersActive = isFiltersActive(filters);
  const compressionCaption = visibleGroups.groups.length > 0
    ? tq(lang, "compressionCaption", {
        groups: fmt(visibleGroups.groups.length),
        plural: lang === "en" && visibleGroups.groups.length !== 1 ? "s" : "",
        reports: fmt(visibleGroups.collapsed),
        reportsPlural: lang === "en" && visibleGroups.collapsed !== 1 ? "s" : "",
      })
    : null;

  const sortOptions: SelectOption[] = [
    { value: "score-desc", label: tq(lang, "sortScoreDesc") },
    { value: "score-asc", label: tq(lang, "sortScoreAsc") },
    { value: "id-desc", label: tq(lang, "sortIdDesc") },
    { value: "id-asc", label: tq(lang, "sortIdAsc") },
  ];
  const verdictOptions: SelectOption[] = [
    { value: "all", label: tq(lang, "verdictAll") },
    { value: "high", label: tq(lang, "verdictHigh") },
    { value: "moderate", label: tq(lang, "verdictModerate") },
    { value: "low", label: tq(lang, "verdictLow") },
    { value: "review", label: tShared(lang, "manualReview") },
  ];
  const ruleOptions: SelectOption[] = [
    { value: "", label: tq(lang, "ruleAll") },
    ...rules
      .filter((r) => r.in_scope)
      .map((r): SelectOption => ({ value: r.key, label: r.display })),
  ];
  const siteSelectOptions: SelectOption[] = [
    { value: "", label: tq(lang, "siteAll") },
    ...siteOptions.map((s): SelectOption => ({ value: s, label: s })),
  ];
  const activitySelectOptions: SelectOption[] = [
    { value: "", label: tq(lang, "activityAll") },
    ...activityOptions.map((a): SelectOption => ({ value: a, label: a })),
  ];

  const body = (() => {
    if (loading) {
      return (
        <div role="status" className="flex flex-col items-center gap-2 py-10">
          <div className="w-72">
            <Progress
              value={loaded}
              max={indexed ?? undefined}
              label={tq(lang, "loadingReports")}
              detail={
                indexed !== null
                  ? `${fmt(loaded)} / ${fmt(indexed)}`
                  : fmt(loaded)
              }
            />
          </div>
        </div>
      );
    }
    if (loadErr !== null) {
      return (
        <div className="space-y-3 text-center">
          <ErrorState
            title={tq(lang, "errorTitle")}
            description={tq(lang, "errorBody")}
          />
          <Button variant="secondary" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            {tq(lang, "retry")}
          </Button>
        </div>
      );
    }
    if (rows !== null && rows.length === 0) {
      return <EmptyState title={tShared(lang, "emptyQueue")} />;
    }
    if (filteredRows.length === 0) {
      return (
        <EmptyState
          title={filtersActive ? tShared(lang, "noMatchingReports") : tq(lang, "emptyNone")}
          action={
            filtersActive ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setFilters({ ...DEFAULT_FILTERS })}
              >
                {tq(lang, "clearFilters")}
              </Button>
            ) : undefined
          }
        />
      );
    }
    return (
      <QueueTable
        key={[filters.q, filters.verdict, filters.rule, filters.site, filters.activity, filters.from, filters.to, rows?.length ?? 0].join("\u0000")}
        rows={filteredRows}
        groups={visibleGroups.groups}
        sorting={sortingFor(filters.sort)}
        selection={selection}
        onToggleRow={toggleRow}
        onToggleAll={toggleAll}
        allSelected={allSelected}
        someSelected={someSelected}
        selectedId={selectedId}
        onSelectReport={onSelectReport ?? openReport}
        onOpenReport={openReport}
        lang={lang}
      />
    );
  })();

  return (
    <section className={cn("space-y-6", className)} aria-busy={loading}>
      <PageHeader
        eyebrow={tq(lang, "queueEyebrow")}
        title={tq(lang, "queueTitle")}
        description={tq(lang, "queueSub")}
        actions={
          <Link to="/ingest" className={buttonVariants({ variant: "primary", size: "md" })}>
            <FilePlus2 aria-hidden="true" />
            {tq(lang, "addReport")}
          </Link>
        }
      >
      </PageHeader>

      <Card density="compact" className="gap-4 overflow-hidden p-4 md:p-5">
        <div className="flex min-h-8 flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-3">
          <div>
            <p className="flex items-baseline gap-2 text-content-primary">
              <span className="font-mono text-base font-semibold tabular-nums">
                {loadErr !== null
                  ? queuePartialLine(lang, loaded)
                  : queueCountLine(lang, filteredRows.length, rows?.length ?? 0, indexed)}
              </span>
            </p>
            {compressionCaption && (
              <p className="mt-1 text-xs text-content-secondary">{compressionCaption}</p>
            )}
            {clustersError && (
              <p className="mt-1 text-xs text-content-muted">{tq(lang, "groupingUnavailable")}</p>
            )}
          </div>
          {filtersActive && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setFilters({ ...DEFAULT_FILTERS })}
            >
              {tq(lang, "clearFilters")}
            </Button>
          )}
        </div>
        <div className="space-y-2 rounded-lg border border-border-subtle bg-surface-sunken/45 p-2.5">
          <div className="grid gap-2 md:grid-cols-[minmax(260px,1fr)_220px_180px]">
            <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-content-secondary"
            />
            <Input
              type="search"
              size="sm"
              aria-label={tShared(lang, "searchReports")}
              placeholder={tShared(lang, "searchReports")}
              value={filters.q}
              onChange={(e) => patchFilters({ q: e.target.value })}
              className="pr-11 pl-9 [&::-webkit-search-cancel-button]:hidden"
            />
            {filters.q !== "" && (
              <button
                type="button"
                aria-label={tq(lang, "clearSearch")}
                onClick={() => patchFilters({ q: "" })}
                className="absolute top-1/2 right-0 grid size-11 -translate-y-1/2 place-items-center rounded-md text-content-secondary hover:text-content-primary"
              >
                <X aria-hidden="true" className="size-4" />
              </button>
            )}
          </div>

          <div>
            <Select
              size="sm"
              aria-label={tq(lang, "sortLabel")}
              options={sortOptions}
              value={filters.sort}
              onChange={(v) => patchFilters({ sort: v as QueueSort })}
            />
          </div>

          <div>
            <Select
              size="sm"
              aria-label={tq(lang, "verdictLabel")}
              options={verdictOptions}
              value={filters.verdict}
              onChange={(v) => patchFilters({ verdict: v as QueueFilters["verdict"] })}
            />
          </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <div title={tq(lang, "ruleHint")}>
            <Select
              size="sm"
              aria-label={tq(lang, "ruleLabel")}
              options={ruleOptions}
              value={filters.rule ?? ""}
              onChange={(v) => patchFilters({ rule: v === "" ? null : v })}
            />
          </div>

          <div>
            <Select
              size="sm"
              aria-label={tShared(lang, "site")}
              options={siteSelectOptions}
              value={filters.site ?? ""}
              onChange={(v) => patchFilters({ site: v === "" ? null : v })}
            />
          </div>

          <div>
            <Select
              size="sm"
              aria-label={tq(lang, "colActivity")}
              options={activitySelectOptions}
              value={filters.activity ?? ""}
              onChange={(v) => patchFilters({ activity: v === "" ? null : v })}
            />
          </div>

          <DateRangePicker
            lang={lang}
            emptyLabel={tq(lang, "allDates")}
            ariaLabel={tq(lang, "selectDateRange")}
            className="w-full min-w-0"
            value={
              filters.from || filters.to
                ? { from: isoToDate(filters.from), to: isoToDate(filters.to) }
                : undefined
            }
            onChange={(v: DateRangeValue | undefined) =>
              patchFilters({ from: dateToIso(v?.from), to: dateToIso(v?.to) })
            }
          />
          </div>
        </div>

        {selection.size > 0 && (
          <div
            role="status"
            className="flex items-center gap-3 rounded-md bg-action-secondary px-4 py-1"
          >
            <span className="font-mono text-xs text-content-secondary">
              {fmt(selection.size)} {tq(lang, "selectedLine")}
            </span>
            <Button variant="ghost" size="sm" onClick={() => setSelection(new Set())}>
              {tq(lang, "clearSelection")}
            </Button>
          </div>
        )}

        {body}

        <p className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-border-subtle pt-3 text-xs text-content-secondary">
          <span>{tq(lang, "ingestLegend")}</span>
          <span className="font-mono">{tq(lang, "kbdHint")}</span>
          {loadErr !== null && loaded > 0 && (
            <span className="font-mono">{queuePartialLine(lang, loaded)}</span>
          )}
        </p>
      </Card>
    </section>
  );
}

export default QueuePage;