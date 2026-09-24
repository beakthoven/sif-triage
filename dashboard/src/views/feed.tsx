import { Search } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { BandBadge } from "@/components/band-badge";
import { GrayStateCard, SentinelGateLegend } from "@/components/gray-state-card";
import { PasteClassify } from "@/components/paste-classify";
import { TriageCard } from "@/components/triage-card";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { classify } from "@/lib/api";
import { t, type Lang } from "@/lib/phrasebook";
import {
  inferredSite,
  reportActivityLabel,
  reportSiteLabel,
} from "@/lib/report-display";
import type { Report } from "@/lib/types";
import { cn } from "@/lib/utils";

type QueueFilter = "decision" | "priority" | "reviewed" | "informational" | "all";

/** Feed: paste-classify box + report queue + triage card with evidence
 *  highlights. Gray-action gates (min_length/negation/language/confidence/
 *  drill/well_control_watch) swap the card for Sentinel gray-state cards;
 *  badge-action gates (near_dup, long_input) annotate the triage card itself.
 *
 *  The paste box is the demo's opening beat: POST /api/classify?persist=1
 *  stores the report server-side and returns the real row id — the pasted
 *  card joins the queue as a genuine feed row, so the override buttons POST
 *  /review against a persisted report (audit F4: negative-id placeholder
 *  rows 404'd). Offline (or an old server without persist), the row falls
 *  back to a negative-id optimistic placeholder and overrides land in the
 *  local log; the box shows the offline note — the UI never crashes. */
export function FeedView({
  reports,
  reviewedReportIds,
  lang,
  onOverride,
  onClassified,
}: {
  reports: Report[];
  reviewedReportIds: Set<number>;
  lang: Lang;
  onOverride: (reportId: number, decision: "confirm" | "not_sif") => void;
  onClassified: (report: Report) => void;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [classifying, setClassifying] = useState(false);
  const [offlineNote, setOfflineNote] = useState(false);
  const [filter, setFilter] = useState<QueueFilter>("decision");
  const [query, setQuery] = useState("");
  const busyRef = useRef(false);
  const nextLocalId = useRef(-1);

  const grayGates = (report: Report) =>
    report.prediction.gate_states.filter((gate) => gate.triggered && gate.action !== "badge");
  const isDuplicate = (report: Report) =>
    report.prediction.gate_states.some((gate) => gate.name === "near_dup" && gate.triggered);
  const isReviewed = (report: Report) => reviewedReportIds.has(report.id);

  const filteredReports = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return reports.filter((report) => {
      const matchesQuery =
        !needle ||
        `${report.site} ${report.activity} ${report.text}`.toLocaleLowerCase().includes(needle);
      const matchesFilter =
        filter === "all" ||
        (filter === "priority" &&
          report.prediction.band !== "LOW" &&
          grayGates(report).length === 0 &&
          !isReviewed(report)) ||
        (filter === "decision" && grayGates(report).length > 0 && !isReviewed(report)) ||
        (filter === "reviewed" && isReviewed(report)) ||
        (filter === "informational" &&
          report.prediction.band === "LOW" &&
          grayGates(report).length === 0 &&
          !isReviewed(report));
      return matchesQuery && matchesFilter;
    });
  }, [filter, query, reports, reviewedReportIds]);

  const selected =
    filteredReports.find((report) => report.id === selectedId) ?? filteredReports[0] ?? null;

  async function submitPaste() {
    const value = pasteText.trim();
    if (!value || busyRef.current) return;
    busyRef.current = true;
    setClassifying(true);
    setOfflineNote(false);
    try {
      const prediction = await classify(value, { explain: true });
      // The server persists the paste (persist=1) and returns the real row
      // id; offline fallback keeps the negative-id optimistic convention.
      const serverId = prediction.report_id ?? null;
      setOfflineNote(prediction.model_version === "offline" || serverId === null);
      const id =
        serverId ??
        Math.min(nextLocalId.current, 0, ...reports.map((r) => r.id)) - 1;
      if (serverId === null) nextLocalId.current = id;
      const report: Report = {
        id,
        text: value,
        site: inferredSite(value) ?? "",
        activity: "",
        contractor: null,
        reported_at: new Date().toISOString().slice(0, 10),
        prediction,
      };
      onClassified(report);
      setFilter(
        prediction.gate_states.some((gate) => gate.triggered && gate.action !== "badge")
          ? "decision"
          : prediction.band === "LOW"
            ? "informational"
            : "priority",
      );
      setQuery("");
      setSelectedId(report.id);
    } finally {
      busyRef.current = false;
      setClassifying(false);
    }
  }

  const triggered = selected ? grayGates(selected) : [];
  const filters: { value: QueueFilter; label: string; count: number }[] = [
    {
      value: "decision",
      label: t(lang, "filterReview"),
      count: reports.filter(
        (report) => grayGates(report).length > 0 && !isReviewed(report),
      ).length,
    },
    {
      value: "priority",
      label: t(lang, "filterPriority"),
      count: reports.filter(
        (report) =>
          report.prediction.band !== "LOW" &&
          grayGates(report).length === 0 &&
          !isReviewed(report),
      ).length,
    },
    {
      value: "reviewed",
      label: t(lang, "filterReviewed"),
      count: reports.filter(isReviewed).length,
    },
    {
      value: "informational",
      label: t(lang, "filterInformational"),
      count: reports.filter(
        (report) =>
          report.prediction.band === "LOW" &&
          grayGates(report).length === 0 &&
          !isReviewed(report),
      ).length,
    },
    { value: "all", label: t(lang, "filterAll"), count: reports.length },
  ];

  return (
    <section aria-label={t(lang, "tabTriage")} className="space-y-6">
      <PasteClassify
        lang={lang}
        text={pasteText}
        busy={classifying}
        offline={offlineNote}
        onTextChange={setPasteText}
        onSubmit={submitPaste}
      />

      {reports.length === 0 ? (
        <Card className="border-border">
          <CardContent className="px-5 py-8 text-center text-muted-foreground">
            {t(lang, "emptyQueue")}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(300px,0.8fr)_minmax(0,1.7fr)]">
          <Card className="gap-0 border-border py-0 lg:sticky lg:top-5">
            <CardContent className="gap-0 px-0 py-0">
              <div className="space-y-3 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-foreground">{t(lang, "reportQueue")}</p>
                  <span className="font-mono text-xs text-muted-foreground">
                    {filteredReports.length}/{reports.length}
                  </span>
                </div>
                <label className="relative block">
                  <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
                  <span className="sr-only">{t(lang, "searchReports")}</span>
                  <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={t(lang, "searchReports")}
                    className="h-10 w-full rounded-md border border-input bg-background pr-3 pl-9 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
                  />
                </label>
                <div className="flex flex-wrap gap-1.5" aria-label={t(lang, "queueFilters")}>
                  {filters.map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => setFilter(item.value)}
                      aria-pressed={filter === item.value}
                      className={cn(
                        "rounded-full px-2.5 py-1.5 text-xs font-medium transition-colors",
                        filter === item.value
                          ? "bg-foreground text-background"
                          : "bg-muted text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {item.label} <span className="font-mono opacity-70">{item.count}</span>
                    </button>
                  ))}
                </div>
                {filter === "priority" && (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {t(lang, "priorityGuidance")}
                  </p>
                )}
              </div>
              <Separator />
              {filteredReports.length === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-muted-foreground">
                  {t(lang, "noMatchingReports")}
                </p>
              ) : (
                <ul className="max-h-[22rem] overflow-y-auto lg:max-h-[calc(100vh-16rem)]">
                {filteredReports.map((r) => {
                  const gated = grayGates(r).length > 0;
                  const dup = isDuplicate(r);
                  const reviewed = isReviewed(r);
                  const activity = reportActivityLabel(r);
                  const live = r.id < 0;
                  const active = r.id === selected?.id;
                  return (
                    <li key={r.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(r.id)}
                        aria-current={active}
                        className={cn(
                          "flex min-h-11 w-full items-center gap-3 px-4 py-2.5 text-left transition-colors",
                          active ? "bg-muted" : "hover:bg-muted/50",
                        )}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-foreground">
                            {reportSiteLabel(r)}
                          </span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {activity ? `${activity} · ` : ""}
                            {r.reported_at}
                          </span>
                        </span>
                        {live && (
                          <span
                            className="inline-flex items-center gap-1.5 font-mono text-xs font-medium text-foreground"
                            title={t(lang, "pastedNow")}
                          >
                            <span className="status-dot bg-foreground" aria-hidden />
                            {t(lang, "liveChip")}
                          </span>
                        )}
                        {dup && !gated && (
                          <span
                            className="inline-flex items-center gap-1.5 font-mono text-xs font-medium text-verdict"
                            title={t(lang, "possibleDuplicate")}
                          >
                            <span className="status-dot bg-verdict" aria-hidden />
                            {t(lang, "filterDuplicate")}
                          </span>
                        )}
                        {reviewed ? (
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ok">
                            <span className="status-dot bg-ok" aria-hidden />
                            {t(lang, "filterReviewed")}
                          </span>
                        ) : gated ? (
                          <span
                            className="inline-flex items-center gap-1.5 font-mono text-xs text-quiet"
                            title={t(lang, "filterReview")}
                          >
                            <span className="status-dot bg-quiet" aria-hidden />
                            {t(lang, "gateShort")}
                          </span>
                        ) : (
                          <BandBadge band={r.prediction.band} lang={lang} />
                        )}
                      </button>
                      <Separator />
                    </li>
                  );
                })}
              </ul>
              )}
            </CardContent>
          </Card>

          <div className="space-y-4">
            {classifying ? (
              <Card className="border-border py-0" aria-busy="true" aria-label={t(lang, "pasteBusy")}>
                <CardContent className="space-y-3 px-6 py-6">
                  <div className="h-6 w-1/3 animate-pulse rounded-sm bg-muted" />
                  <div className="h-4 w-full animate-pulse rounded-sm bg-muted" />
                  <div className="h-4 w-5/6 animate-pulse rounded-sm bg-muted" />
                  <div className="h-4 w-2/3 animate-pulse rounded-sm bg-muted" />
                  <p className="font-mono text-xs text-muted-foreground">
                    {t(lang, "pasteBusy")}
                  </p>
                </CardContent>
              </Card>
            ) : !selected ? null : triggered.length > 0 ? (
              triggered.map((g) => (
                <GrayStateCard
                  key={`${selected.id}-${g.name}`}
                  report={selected}
                  gate={g}
                  lang={lang}
                  reviewed={isReviewed(selected)}
                  onOverride={onOverride}
                />
              ))
            ) : (
              <TriageCard
                report={selected}
                lang={lang}
                reviewed={isReviewed(selected)}
                onOverride={onOverride}
              />
            )}
          </div>
        </div>
      )}

      <details className="rounded-lg border border-border bg-card px-5 py-4">
        <summary className="cursor-pointer text-sm font-medium text-foreground">
          {t(lang, "queueHelp")}
        </summary>
        <div className="mt-4">
          <SentinelGateLegend lang={lang} />
        </div>
      </details>
    </section>
  );
}
