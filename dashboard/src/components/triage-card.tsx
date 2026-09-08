import { CircleCheck, CircleX, Zap } from "lucide-react";
import { BandBadge } from "@/components/band-badge";
import { HighlightedText } from "@/components/highlighted-text";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { t, type Lang } from "@/lib/phrasebook";
import type { Report } from "@/lib/types";

/**
 * THE triage card (money shot). Amber "review priority" band — never red,
 * never "detected", score labeled "triage score" and shown as a band,
 * per D14 / UX SEV1-1. Equal-weight Confirm / Not-SIF override buttons;
 * footer: "model proposes, HSE disposes".
 */
export function TriageCard({
  report,
  lang,
  onOverride,
}: {
  report: Report;
  lang: Lang;
  onOverride?: (reportId: string, decision: "confirm" | "not_sif") => void;
}) {
  const p = report.prediction;
  const inScope = p.rules.filter((r) => r.in_scope);
  const oos = p.rules.filter((r) => !r.in_scope);
  const top = inScope[0];
  const second = inScope[1];

  return (
    <Card className="overflow-hidden border-border py-0">
      {/* Signature hazard-tape header */}
      <div className="hazard-stripe flex items-center justify-between gap-3 px-4 py-2.5">
        <BandBadge band={p.band} className="shadow-sm" />
        <span className="rounded-sm bg-background/90 px-2 py-1 font-mono text-sm font-medium text-primary">
          {t(lang, "flaggedFor")}
        </span>
      </div>

      <CardContent className="space-y-4 px-5 pt-4">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 font-mono text-sm text-muted-foreground">
          <span>
            Band <span className="font-semibold text-foreground">{p.band}</span>
          </span>
          <span aria-label={t(lang, "triageScore")}>
            {t(lang, "triageScore")}{" "}
            <span className="font-semibold text-foreground">{p.triage_score.toFixed(2)}</span>
          </span>
          <span>{p.latency_ms}ms</span>
          <span className="ml-auto">
            {report.site} · {report.activity}
          </span>
        </div>

        {top && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
              <Zap className="size-4 text-primary" aria-hidden />
              Rule: {top.name}{" "}
              <span className="font-mono text-primary">{top.prob.toFixed(2)}</span>
            </span>
            {second && (
              <span className="text-sm text-muted-foreground">
                (2nd: {second.name} {second.prob.toFixed(2)})
              </span>
            )}
            {p.well_control_tag && (
              <span className="rounded-sm border border-primary/60 bg-primary/10 px-2 py-0.5 font-mono text-xs font-semibold text-primary">
                WELL-CONTROL / BARRIER TAG
              </span>
            )}
          </div>
        )}
        {oos.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Declared out-of-scope (never scored): {oos.map((r) => r.name).join(" · ")}
          </p>
        )}

        <HighlightedText text={report.text} spans={p.spans} />

        {p.explanation && (
          <p className="text-sm text-muted-foreground">{p.explanation}</p>
        )}
      </CardContent>

      <CardFooter className="flex flex-wrap items-center gap-3 border-t border-border px-5 py-4 [.border-t]:pt-4">
        <div className="flex gap-3">
          <Button
            size="lg"
            onClick={() => onOverride?.(report.id, "confirm")}
            className="min-h-11 bg-primary font-semibold text-primary-foreground hover:bg-primary/90"
          >
            <CircleCheck aria-hidden />
            {t(lang, "confirm")}
          </Button>
          <Button
            size="lg"
            variant="outline"
            onClick={() => onOverride?.(report.id, "not_sif")}
            className="min-h-11"
          >
            <CircleX aria-hidden />
            {t(lang, "notSif")}
          </Button>
        </div>
        <p className="ml-auto font-mono text-xs text-muted-foreground">
          {t(lang, "footer")}
        </p>
      </CardFooter>
    </Card>
  );
}
