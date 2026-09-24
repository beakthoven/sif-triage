import { useCallback, useEffect, useState } from "react";
import { LangToggle } from "@/components/lang-toggle";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getHealth, getOverrides, getReports, postReview } from "@/lib/api";
import { OVERRIDES, REPORTS } from "@/lib/mock";
import { t, type Lang } from "@/lib/phrasebook";
import type { HealthOut, OverrideOut, Report } from "@/lib/types";
import { FeedView } from "@/views/feed";
import { InsightsView } from "@/views/insights";
import { ReviewView } from "@/views/review";

type Workspace = "triage" | "insights" | "decision history";

export default function App() {
  const [lang, setLang] = useState<Lang>("en");
  const [workspace, setWorkspace] = useState<Workspace>("triage");
  // Mock data renders instantly; the live API swap lands when health + data
  // return (offline-demo doctrine: the UI never hard-fails).
  const [reports, setReports] = useState<Report[]>(REPORTS);
  const [overrides, setOverrides] = useState<OverrideOut[]>(OVERRIDES);
  const [health, setHealth] = useState<HealthOut | null>(null);
  const [sessionOverrides, setSessionOverrides] = useState(0);

  useEffect(() => {
    let cancel = false;
    (async () => {
      const [h, reps, ovs] = await Promise.all([
        getHealth(),
        getReports(),
        getOverrides(),
      ]);
      if (cancel) return;
      setHealth(h);
      setReports(reps);
      setOverrides(ovs);
    })();
    return () => {
      cancel = true;
    };
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const onOverride = useCallback(
    (reportId: number, decision: "confirm" | "not_sif") => {
      const newValue =
        decision === "confirm" ? "sif_potential" : "not_sif_potential";
      const current = reports.find((r) => r.id === reportId);
      setSessionOverrides((n) => n + 1);
      void (async () => {
        try {
          // Model proposes, HSE disposes — the POST is the real write.
          await postReview({
            report_id: reportId,
            field: "sif_label",
            old_value: current ? current.prediction.band : null,
            new_value: newValue,
          });
          setOverrides(await getOverrides());
        } catch {
          // Offline: record the decision locally so the queue still moves.
          setOverrides((cur) => [
            ...cur,
            {
              id: -(cur.length + 1),
              report_id: reportId,
              field: "sif_label",
              old_value: current ? current.prediction.band : null,
              new_value: newValue,
              labeler: "hse_reviewer",
              source: "override",
              ts: new Date().toISOString(),
            },
          ]);
        }
      })();
    },
    [reports],
  );

  // Only gray-action gates route to the review queue; badge gates
  // (near_dup, long_input) annotate the triage card in place.
  const reviewedReportIds = new Set(overrides.map((override) => override.report_id));
  const pendingDecisions = reports.filter(
    (report) =>
      !reviewedReportIds.has(report.id) &&
      report.prediction.gate_states.some((gate) => gate.triggered && gate.action !== "badge"),
  );

  // Live paste-classify: the persisted result (?persist=1, real server id) is
  // prepended to the queue; offline falls back to a negative-id LIVE row.
  // The server dedups exact repeat pastes and returns the same row id — drop
  // the stale copy so the queue never holds duplicate keys.
  const onClassified = useCallback((report: Report) => {
    setReports((cur) => [report, ...cur.filter((r) => r.id !== report.id)]);
  }, []);

  // B3: the density ingest beat changes server state — refetch the header
  // count + feed queue. Optimistic LIVE rows (negative ids) survive the swap.
  const refreshLive = useCallback(async () => {
    const [h, reps] = await Promise.all([getHealth(), getReports()]);
    setHealth(h);
    setReports((cur) => [...cur.filter((r) => r.id < 0), ...reps]);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="fixed top-3 left-3 z-50 -translate-y-20 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:translate-y-0"
      >
        {t(lang, "skipContent")}
      </a>
      <header className="border-b border-border bg-card/70">
        <div className="page-shell flex items-center gap-4 py-4">
          <div className="min-w-0">
            <h1 className="text-base font-semibold tracking-tight text-foreground sm:text-lg">
              <span className="sm:hidden">{t(lang, "appTitleShort")}</span>
              <span className="hidden sm:inline">{t(lang, "appTitle")}</span>
            </h1>
            <p className="hidden text-xs text-muted-foreground sm:block">
              {t(lang, "appSub")} · {t(lang, "hseOperations")}
            </p>
          </div>
          <div className="ml-auto flex items-center gap-3 sm:gap-5">
            <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <span
                className={health ? "status-dot bg-ok" : "status-dot bg-quiet"}
                aria-hidden
              />
              {health ? t(lang, "statusOnline") : t(lang, "statusOffline")}
              {health && (
                <span className="hidden text-muted-foreground/70 md:inline">
                  · {health.n_reports.toLocaleString("en-IN")} {t(lang, "reportsIndexed")}
                </span>
              )}
            </span>
            <LangToggle lang={lang} onChange={setLang} />
          </div>
        </div>
      </header>

      <main id="main-content" className="page-shell py-6 sm:py-8">
        <Tabs value={workspace} onValueChange={(value) => setWorkspace(value as Workspace)}>
          <TabsList
            variant="line"
            aria-label="Main workspace"
            className="mb-7 h-auto w-full justify-start gap-7 overflow-x-auto rounded-none border-b border-border p-0"
          >
            <TabsTrigger
              value="triage"
              className="min-h-11 flex-none rounded-none px-1 text-base text-muted-foreground transition-colors after:bottom-[-1px] after:h-[2px] hover:text-foreground data-[state=active]:font-semibold data-[state=active]:text-foreground"
            >
              {t(lang, "tabTriage")}
              {pendingDecisions.length > 0 && (
                <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-xs text-muted-foreground">
                  {pendingDecisions.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger
              value="insights"
              className="min-h-11 flex-none rounded-none px-1 text-base text-muted-foreground transition-colors after:bottom-[-1px] after:h-[2px] hover:text-foreground data-[state=active]:font-semibold data-[state=active]:text-foreground"
            >
              {t(lang, "tabInsights")}
            </TabsTrigger>
            <TabsTrigger
              value="decisions"
              className="min-h-11 flex-none rounded-none px-1 text-base text-muted-foreground transition-colors after:bottom-[-1px] after:h-[2px] hover:text-foreground data-[state=active]:font-semibold data-[state=active]:text-foreground"
            >
              {t(lang, "tabHistory")}
              {(sessionOverrides > 0 || overrides.length > 0) && (
                <span className="ml-1.5 font-mono text-sm font-normal text-muted-foreground">
                  {overrides.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="triage" forceMount className="data-[state=inactive]:hidden">
            <FeedView
              reports={reports}
              reviewedReportIds={reviewedReportIds}
              lang={lang}
              onOverride={onOverride}
              onClassified={onClassified}
            />
          </TabsContent>
          <TabsContent value="insights" forceMount className="data-[state=inactive]:hidden">
            <InsightsView lang={lang} onIngested={refreshLive} />
          </TabsContent>
          <TabsContent value="decisions" forceMount className="data-[state=inactive]:hidden">
            <ReviewView overrides={overrides} lang={lang} />
          </TabsContent>
        </Tabs>
      </main>

      <footer className="border-t border-border">
        <div className="page-shell flex flex-wrap items-center gap-3 py-4">
          <p className="text-sm text-muted-foreground">
            {t(lang, "footer")}
          </p>
          <span className="ml-auto inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
            <span className="status-dot bg-quiet" aria-hidden />
            {t(lang, "demoDisclosure")}
          </span>
        </div>
      </footer>
    </div>
  );
}
