import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { getPatterns, ruleDisplayName } from "@/lib/api";
import { PATTERNS } from "@/lib/mock";
import type { PatternKind, PatternOut } from "@/lib/types";
import { cn } from "@/lib/utils";

const KIND_TABS: { kind: PatternKind; label: string; blurb: string }[] = [
  {
    kind: "site_activity",
    label: "Site × Activity",
    blurb:
      "Lift-ranked activity × site co-occurrence on structured facets. Wilson 95% CI on the flag rate — no LLM tagging.",
  },
  {
    kind: "activity_barrier",
    label: "Activity × Barrier",
    blurb:
      "Lift-ranked activity × failed-barrier co-occurrence from the mined corpus. The dominant IOGP rule tags each cell.",
  },
];

/** Patterns: lift-ranked co-occurrence cards with n + Wilson CI (GET
 *  /api/patterns?kind=). No sankey, no chart lib — one sentence, one count,
 *  honest stats. Structured facets only — no LLM tagging. */
export function PatternsView() {
  const [kind, setKind] = useState<PatternKind>("site_activity");
  const [patterns, setPatterns] = useState<PatternOut[]>(
    PATTERNS.filter((p) => p.kind === "site_activity"),
  );

  useEffect(() => {
    let cancel = false;
    getPatterns(kind).then((rows) => {
      if (!cancel) setPatterns(rows);
    });
    return () => {
      cancel = true;
    };
  }, [kind]);

  const tab = KIND_TABS.find((k) => k.kind === kind) ?? KIND_TABS[0];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="pattern kind">
        {KIND_TABS.map((k) => (
          <button
            key={k.kind}
            type="button"
            role="tab"
            aria-selected={k.kind === kind}
            onClick={() => setKind(k.kind)}
            className={cn(
              "min-h-11 rounded-md border px-4 font-mono text-sm font-semibold transition-colors",
              k.kind === kind
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
          >
            {k.label}
          </button>
        ))}
      </div>
      <p className="text-muted-foreground">{tab.blurb}</p>
      {patterns.length === 0 && (
        <p className="font-mono text-sm text-muted-foreground">
          No patterns yet — ingest more reports (min n=2 per cell).
        </p>
      )}
      <div className="space-y-3">
        {patterns.map((p, i) => (
          <Card key={p.id} className="border-border">
            <CardHeader className="flex flex-row flex-wrap items-center gap-3 pb-2">
              <span className="hazard-stripe-dense inline-block h-4 w-8 shrink-0 self-center rounded-sm" aria-hidden />
              <h3 className="text-lg leading-snug font-semibold text-foreground">
                {p.activity} × {p.site ?? p.barrier}
              </h3>
              {p.rule && (
                <span className="rounded-sm border border-primary/60 bg-primary/10 px-1.5 py-0.5 font-mono text-xs font-semibold text-primary">
                  {ruleDisplayName(p.rule)}
                </span>
              )}
              <span className="ml-auto shrink-0 font-mono text-sm text-muted-foreground">
                #{i + 1}
              </span>
            </CardHeader>
            <CardContent className="flex-row flex-wrap items-baseline gap-x-6 gap-y-1 font-mono text-sm">
              <span className="text-foreground">
                <span className="text-xl font-bold text-primary">{p.n}</span> reports
              </span>
              <span className="text-muted-foreground">
                flagged <span className="text-foreground">{(p.sif_rate * 100).toFixed(0)}</span>
                <span className="ml-1">per 100</span>
              </span>
              <span className="text-muted-foreground">
                lift <span className="text-foreground">{p.lift.toFixed(1)}×</span>
              </span>
              <span className="text-muted-foreground">
                95% CI [{p.ci_low.toFixed(2)}, {p.ci_high.toFixed(2)}]
              </span>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
