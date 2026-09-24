import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { t, type Lang } from "@/lib/phrasebook";
import { DensityView } from "@/views/density";
import { PatternsView } from "@/views/patterns";

type InsightMode = "locations" | "patterns";

export function InsightsView({
  lang,
  onIngested,
}: {
  lang: Lang;
  onIngested?: () => void;
}) {
  const [mode, setMode] = useState<InsightMode>("locations");

  return (
    <section aria-label={t(lang, "tabInsights")} className="space-y-6">
      <Tabs value={mode} onValueChange={(value) => setMode(value as InsightMode)}>
        <TabsList aria-label="Insight type" className="mb-5">
          <TabsTrigger value="locations">{t(lang, "locations")}</TabsTrigger>
          <TabsTrigger value="patterns">{t(lang, "recurringPatterns")}</TabsTrigger>
        </TabsList>
        <TabsContent value="locations">
          <DensityView lang={lang} onIngested={onIngested} />
        </TabsContent>
        <TabsContent value="patterns">
          <PatternsView lang={lang} />
        </TabsContent>
      </Tabs>
    </section>
  );
}
