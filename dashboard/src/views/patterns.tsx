import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { PATTERNS } from "@/lib/mock";

/** Patterns: top-5 plain-sentence pattern cards with n + Wilson CI.
 *  No sankey, no chart lib — one sentence, one count, honest stats. */
export function PatternsView() {
  return (
    <div className="space-y-3">
      <p className="text-muted-foreground">
        Lift-ranked activity × location × barrier co-occurrence on structured
        facets. Wilson 95% CI on the flag-rate lift — no LLM tagging.
      </p>
      {PATTERNS.map((p, i) => (
        <Card key={p.id} className="border-border">
          <CardHeader className="flex flex-row flex-wrap items-center gap-3 pb-2">
            <span className="hazard-stripe-dense inline-block h-4 w-8 shrink-0 self-center rounded-sm" aria-hidden />
            <h3 className="text-lg leading-snug font-semibold text-foreground">
              {p.sentence}
            </h3>
            <span className="ml-auto shrink-0 font-mono text-sm text-muted-foreground">
              #{i + 1}
            </span>
          </CardHeader>
          <CardContent className="flex-row flex-wrap items-baseline gap-x-6 gap-y-1 font-mono text-sm">
            <span className="text-foreground">
              <span className="text-xl font-bold text-primary">{p.n}</span> reports /{" "}
              {p.window_days} days
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
