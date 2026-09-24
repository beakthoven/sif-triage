import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { getPatterns, ruleDisplayName } from "@/lib/api";
import { PATTERNS } from "@/lib/mock";
import { t, type Lang } from "@/lib/phrasebook";
import type { PatternKind, PatternOut } from "@/lib/types";
import { cn } from "@/lib/utils";

const KINDS: PatternKind[] = ["site_activity", "activity_barrier"];

/** Patterns: lift-ranked co-occurrence rows with n + Wilson CI (GET
 *  /api/patterns?kind=). No sankey, no chart lib — one sentence, one count,
 *  honest stats. Structured facets only — no LLM tagging. */
export function PatternsView({ lang }: { lang: Lang }) {
  const [kind, setKind] = useState<PatternKind>("site_activity");
  const [patterns, setPatterns] = useState<PatternOut[]>(
    PATTERNS.filter((p) => p.kind === "site_activity"),
  );
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let cancel = false;
    getPatterns(kind).then((rows) => {
      if (!cancel) setPatterns(rows);
    });
    return () => {
      cancel = true;
    };
  }, [kind]);

  const blurb =
    kind === "site_activity"
      ? t(lang, "patternSiteBlurb")
      : t(lang, "patternBarrierBlurb");

  return (
    <div className="space-y-4">
      <div
        className="flex flex-wrap items-center gap-6 border-b border-border"
        role="tablist"
        aria-label="pattern kind"
      >
        {KINDS.map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={item === kind}
            onClick={() => setKind(item)}
            className={cn(
              "-mb-px min-h-11 border-b-2 px-1 text-sm font-medium transition-colors",
              item === kind
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t(lang, item === "site_activity" ? "siteActivity" : "activityBarrier")}
          </button>
        ))}
      </div>
      <p className="max-w-3xl text-muted-foreground">{blurb}</p>
      {patterns.length === 0 && (
        <p className="font-mono text-sm text-muted-foreground">
          {t(lang, "noPatterns")}
        </p>
      )}
      {patterns.length > 0 && (
        <Card className="gap-0 border-border py-0">
          <ul>
            {(showAll ? patterns : patterns.slice(0, 10)).map((p, i) => (
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
                <div className="mt-1.5 flex flex-wrap items-baseline gap-x-5 gap-y-1 pl-11 text-sm text-muted-foreground">
                  <span>
                    <span className="font-mono text-base font-semibold text-foreground">{p.n}</span>{" "}
                    {t(lang, "reportsReviewed")}
                  </span>
                  <span>
                    <span className="font-mono text-foreground">{(p.sif_rate * 100).toFixed(0)}</span>{" "}
                    {t(lang, "flaggedPer100")}
                  </span>
                </div>
                <details className="mt-2 pl-11 text-xs text-muted-foreground">
                  <summary className="cursor-pointer font-medium">
                    {t(lang, "statisticalDetail")}
                  </summary>
                  <p className="mt-1 font-mono">
                    lift {p.lift.toFixed(1)}× · 95% CI [{p.ci_low.toFixed(2)}, {p.ci_high.toFixed(2)}]
                  </p>
                </details>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {patterns.length > 10 && (
        <button
          type="button"
          onClick={() => setShowAll((value) => !value)}
          className="min-h-10 text-sm font-medium text-foreground underline-offset-4 hover:underline"
        >
          {showAll
            ? t(lang, "showTop10")
            : `${t(lang, "showAllPatterns")} (${patterns.length})`}
        </button>
      )}
    </div>
  );
}
