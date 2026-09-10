import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
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

/** Patterns: lift-ranked co-occurrence rows with n + Wilson CI (GET
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
      <div
        className="flex flex-wrap items-center gap-6 border-b border-border"
        role="tablist"
        aria-label="pattern kind"
      >
        {KIND_TABS.map((k) => (
          <button
            key={k.kind}
            type="button"
            role="tab"
            aria-selected={k.kind === kind}
            onClick={() => setKind(k.kind)}
            className={cn(
              "-mb-px min-h-11 border-b-2 px-1 text-sm font-medium transition-colors",
              k.kind === kind
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
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
      {patterns.length > 0 && (
        <Card className="gap-0 border-border py-0">
          <ul>
            {patterns.map((p, i) => (
              <li
                key={p.id}
                className="border-b border-border px-5 py-4 last:border-b-0"
              >
                <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <span className="w-7 shrink-0 font-mono text-sm text-muted-foreground">
                    #{i + 1}
                  </span>
                  <h3 className="text-base font-semibold text-foreground">
                    {p.activity} × {p.site ?? p.barrier}
                  </h3>
                  {p.rule && (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                      <span className="status-dot bg-foreground/60" aria-hidden />
                      {ruleDisplayName(p.rule)}
                    </span>
                  )}
                </div>
                <div className="mt-1.5 flex flex-wrap items-baseline gap-x-6 gap-y-1 pl-11 font-mono text-sm text-muted-foreground">
                  <span>
                    <span className="text-base font-semibold text-foreground">{p.n}</span>{" "}
                    reports
                  </span>
                  <span>
                    flagged <span className="text-foreground">{(p.sif_rate * 100).toFixed(0)}</span>{" "}
                    per 100
                  </span>
                  <span>
                    lift <span className="text-foreground">{p.lift.toFixed(1)}×</span>
                  </span>
                  <span>
                    95% CI [{p.ci_low.toFixed(2)}, {p.ci_high.toFixed(2)}]
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
