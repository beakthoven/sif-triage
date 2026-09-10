import { useCallback, useEffect, useState } from "react";
import { LangToggle } from "@/components/lang-toggle";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getHealth, getOverrides, getReports, postReview } from "@/lib/api";
import { OVERRIDES, REPORTS } from "@/lib/mock";
import { t, type Lang } from "@/lib/phrasebook";
import type { HealthOut, OverrideOut, Report } from "@/lib/types";
import { DensityView } from "@/views/density";
import { FeedView } from "@/views/feed";
import { PatternsView } from "@/views/patterns";
import { ReviewView } from "@/views/review";

export default function App() {
  const [lang, setLang] = useState<Lang>("en");
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
  const gated = reports.filter((r) =>
    r.prediction.gate_states.some((g) => g.triggered && g.action !== "badge"),
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
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-[1100px] items-center gap-4 px-6 py-5">
          <div className="min-w-0">
            <h1 className="truncate text-xl font-semibold tracking-tight text-foreground">
              {t(lang, "appTitle")}
            </h1>
            <p className="text-sm text-muted-foreground">{t(lang, "appSub")}</p>
          </div>
          <div className="ml-auto flex items-center gap-6">
            <span className="inline-flex items-center gap-2 font-mono text-xs text-muted-foreground">
              <span
                className={health ? "status-dot bg-ok" : "status-dot bg-quiet"}
                aria-hidden
              />
              {health
                ? `LIVE · ${health.model_version} · ${health.n_reports} reports`
                : "Offline demo"}
            </span>
            <LangToggle lang={lang} onChange={setLang} />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1100px] px-6 py-8">
        <Tabs defaultValue="feed">
          <TabsList
            variant="line"
            className="mb-8 h-auto w-full justify-start gap-7 rounded-none border-b border-border p-0"
          >
            <TabsTrigger
              value="feed"
              className="min-h-11 flex-none rounded-none px-1 text-base text-muted-foreground transition-colors after:bottom-[-1px] after:h-[2px] hover:text-foreground data-[state=active]:font-semibold data-[state=active]:text-foreground"
            >
              {t(lang, "tabFeed")}
            </TabsTrigger>
            <TabsTrigger
              value="density"
              className="min-h-11 flex-none rounded-none px-1 text-base text-muted-foreground transition-colors after:bottom-[-1px] after:h-[2px] hover:text-foreground data-[state=active]:font-semibold data-[state=active]:text-foreground"
            >
              {t(lang, "tabDensity")}
            </TabsTrigger>
            <TabsTrigger
              value="patterns"
              className="min-h-11 flex-none rounded-none px-1 text-base text-muted-foreground transition-colors after:bottom-[-1px] after:h-[2px] hover:text-foreground data-[state=active]:font-semibold data-[state=active]:text-foreground"
            >
              {t(lang, "tabPatterns")}
            </TabsTrigger>
            <TabsTrigger
              value="review"
              className="min-h-11 flex-none rounded-none px-1 text-base text-muted-foreground transition-colors after:bottom-[-1px] after:h-[2px] hover:text-foreground data-[state=active]:font-semibold data-[state=active]:text-foreground"
            >
              {t(lang, "tabReview")}
              {sessionOverrides > 0 && (
                <span className="ml-1.5 font-mono text-sm font-normal text-muted-foreground">
                  ({sessionOverrides})
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="feed">
            <FeedView reports={reports} lang={lang} onOverride={onOverride} onClassified={onClassified} />
          </TabsContent>
          <TabsContent value="density">
            <DensityView lang={lang} onIngested={refreshLive} />
          </TabsContent>
          <TabsContent value="patterns">
            <PatternsView />
          </TabsContent>
          <TabsContent value="review">
            <ReviewView gatedReports={gated} overrides={overrides} lang={lang} />
          </TabsContent>
        </Tabs>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1100px] flex-wrap items-center gap-3 px-6 py-4">
          <p className="text-sm text-muted-foreground">
            {t(lang, "footer")}
          </p>
          {/* Provenance disclosure (audit C6): the seeded corpus is synthetic
              stand-in data — say so on-screen, not just in the deck. English-only
              by design: a data label, not UI chrome (keeps the QA'd phrasebook frozen). */}
          <span className="inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
            <span className="status-dot bg-quiet" aria-hidden />
            demo data: synthetic OIL-style corpus
          </span>
        </div>
      </footer>
    </div>
  );
}
