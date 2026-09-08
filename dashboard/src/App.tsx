import { useCallback, useState } from "react";
import { LangToggle } from "@/components/lang-toggle";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { REPORTS } from "@/lib/mock";
import { t, type Lang } from "@/lib/phrasebook";
import { DensityView } from "@/views/density";
import { FeedView } from "@/views/feed";
import { PatternsView } from "@/views/patterns";
import { ReviewView } from "@/views/review";

export default function App() {
  const [lang, setLang] = useState<Lang>("en");
  const [overrides, setOverrides] = useState<
    { reportId: string; decision: "confirm" | "not_sif" }[]
  >([]);

  const onOverride = useCallback(
    (reportId: string, decision: "confirm" | "not_sif") =>
      setOverrides((cur) => [...cur, { reportId, decision }]),
    [],
  );

  const gated = REPORTS.filter((r) => r.prediction.gates.length > 0);

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-4">
          <span className="hazard-stripe h-8 w-12 shrink-0 rounded-sm" aria-hidden />
          <div className="min-w-0">
            <h1 className="truncate text-xl font-bold tracking-tight text-foreground">
              {t(lang, "appTitle")}
            </h1>
            <p className="font-mono text-xs text-muted-foreground">{t(lang, "appSub")}</p>
          </div>
          <div className="ml-auto">
            <LangToggle lang={lang} onChange={setLang} />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        <Tabs defaultValue="feed">
          <TabsList className="mb-6 h-11 bg-muted">
            <TabsTrigger value="feed" className="min-h-11 px-5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              {t(lang, "tabFeed")}
            </TabsTrigger>
            <TabsTrigger value="density" className="min-h-11 px-5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              {t(lang, "tabDensity")}
            </TabsTrigger>
            <TabsTrigger value="patterns" className="min-h-11 px-5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              {t(lang, "tabPatterns")}
            </TabsTrigger>
            <TabsTrigger value="review" className="min-h-11 px-5 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              {t(lang, "tabReview")}
              {overrides.length > 0 && (
                <span className="ml-2 rounded-full bg-primary px-1.5 font-mono text-xs text-primary-foreground">
                  {overrides.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="feed">
            <FeedView reports={REPORTS} lang={lang} onOverride={onOverride} />
          </TabsContent>
          <TabsContent value="density">
            <DensityView lang={lang} />
          </TabsContent>
          <TabsContent value="patterns">
            <PatternsView />
          </TabsContent>
          <TabsContent value="review">
            <ReviewView gatedReports={gated} lang={lang} />
          </TabsContent>
        </Tabs>
      </main>

      <footer className="border-t border-border">
        <p className="mx-auto max-w-7xl px-6 py-4 font-mono text-sm text-muted-foreground">
          {t(lang, "footer")}
        </p>
      </footer>
    </div>
  );
}
