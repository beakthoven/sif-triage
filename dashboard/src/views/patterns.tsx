import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { getPatterns } from "@/lib/api";
import { PATTERNS } from "@/lib/mock";
import type { PatternOut } from "@/lib/types";

/** Patterns: lift-ranked activity × site cards with n + Wilson CI (GET
 *  /api/patterns). No sankey, no chart lib — one sentence, one count, honest
 *  stats. Structured facets only — no LLM tagging. */
export function PatternsView() {
  const [patterns, setPatterns] = useState<PatternOut[]>(PATTERNS);

  useEffect(() => {
    let cancel = false;
    getPatterns().then((rows) => {
      if (!cancel) setPatterns(rows);
    });
    return () => {
      cancel = true;
    };
  }, []);

  return (
    <div className="space-y-3">
      <p className="text-muted-foreground">
        Lift-ranked activity × site co-occurrence on structured facets. Wilson
        95% CI on the SIF-rate lift — no LLM tagging.
      </p>
      {patterns.length === 0 && (
        <p className="font-mono text-sm text-muted-foreground">
          No patterns yet — ingest more reports (min n=2 per activity × site cell).
        </p>
      )}
      {patterns.map((p, i) => (
        <Card key={p.id} className="border-border">
          <CardHeader className="flex flex-row flex-wrap items-center gap-3 pb-2">
            <span className="hazard-stripe-dense inline-block h-4 w-8 shrink-0 self-center rounded-sm" aria-hidden />
            <h3 className="text-lg leading-snug font-semibold text-foreground">
              {p.activity} × {p.site}
            </h3>
            <span className="ml-auto shrink-0 font-mono text-sm text-muted-foreground">
              #{i + 1}
            </span>
          </CardHeader>
          <CardContent className="flex-row flex-wrap items-baseline gap-x-6 gap-y-1 font-mono text-sm">
            <span className="text-foreground">
              <span className="text-xl font-bold text-primary">{p.n}</span> reports
            </span>
            <span className="text-muted-foreground">
              SIF rate <span className="text-foreground">{(p.sif_rate * 100).toFixed(0)}</span>
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
  );
}
