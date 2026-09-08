import { ChevronDown, ChevronUp, CircleCheck, CircleX, Copy, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { BandBadge } from "@/components/band-badge";
import { HighlightedText } from "@/components/highlighted-text";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { getExplanation } from "@/lib/api";
import { t, type Lang } from "@/lib/phrasebook";
import type { ExplanationOut, Report } from "@/lib/types";

/**
 * THE triage card (money shot). Amber "review priority" band — never red,
 * never "detected", score labeled "triage score" and shown as a band,
 * per D14 / UX SEV1-1. Equal-weight Confirm / Not-SIF override buttons;
 * footer: "model proposes, HSE disposes".
 *
 * D22: the top-3 in-scope rule probabilities render as bars — never a
 * single asserted rule. The header chip says "Flagged for HSE review" on
 * HIGH/MODERATE and "no action needed" on LOW (review SEV2-4/SEV2-5).
 *
 * Badge gates annotate here instead of routing to the gray queue:
 * near_dup -> amber-striped "memory, not generalization" banner;
 * chunked / long_input -> CHUNKED badge. The explanation expander fetches
 * GET /api/reports/{id}/explanation lazily — async with a skeleton, the
 * card never blocks on it; template always renders, the ollama rewording
 * is shown when (and only when) the API produced one.
 */
export function TriageCard({
  report,
  lang,
  onOverride,
}: {
  report: Report;
  lang: Lang;
  onOverride?: (reportId: number, decision: "confirm" | "not_sif") => void;
}) {
  const p = report.prediction;
  const inScope = p.rules.filter((r) => r.in_scope);
  const oos = p.rules.filter((r) => !r.in_scope);
  const nearDup = p.gate_states.find((g) => g.name === "near_dup" && g.triggered);
  const longInput = p.gate_states.find((g) => g.name === "long_input" && g.triggered);
  const chunked = p.chunked || longInput !== undefined;

  return (
    <Card className="overflow-hidden border-border py-0">
      {/* Signature hazard-tape header */}
      <div className="hazard-stripe flex items-center justify-between gap-3 px-4 py-2.5">
        <BandBadge band={p.band} className="shadow-sm" />
        <span className="rounded-sm bg-background/90 px-2 py-1 font-mono text-sm font-medium text-primary">
          {p.band === "LOW" ? t(lang, "noAction") : t(lang, "flaggedFor")}
        </span>
      </div>

      {/* Near-dup banner: badge gate, amber-striped, never gray. */}
      {nearDup && (
        <div className="hazard-stripe-dense flex items-center gap-3 px-4 py-2">
          <span className="flex items-center gap-2 rounded-sm bg-background/90 px-2 py-1 text-sm font-medium text-primary">
            <Copy className="size-4 shrink-0" aria-hidden />
            {t(lang, "nearDupBanner")}
          </span>
          {nearDup.detail && (
            <span className="hidden rounded-sm bg-background/90 px-2 py-1 font-mono text-xs text-muted-foreground lg:inline">
              {nearDup.detail}
            </span>
          )}
        </div>
      )}

      <CardContent className="space-y-4 px-5 pt-4">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 font-mono text-sm text-muted-foreground">
          <span>
            Band <span className="font-semibold text-foreground">{p.band}</span>
          </span>
          <span aria-label={t(lang, "triageScore")}>
            {t(lang, "triageScore")}{" "}
            <span className="font-semibold text-foreground">{p.sif_score.toFixed(2)}</span>
          </span>
          {p.latency_ms > 0 && <span>{p.latency_ms}ms</span>}
          {chunked && (
            <span
              className="rounded-sm border border-primary/60 bg-primary/10 px-1.5 py-0.5 text-xs font-semibold text-primary"
              title={longInput?.detail}
            >
              {t(lang, "chunkedBadge")}
            </span>
          )}
          <span className="ml-auto">
            {report.site} · {report.activity}
          </span>
        </div>

        {inScope.length > 0 && (
          <div className="space-y-1.5" aria-label={t(lang, "ruleProbs")}>
            <p className="flex items-center gap-1.5 font-mono text-xs tracking-wide text-muted-foreground uppercase">
              <Zap className="size-4 text-primary" aria-hidden />
              {t(lang, "ruleProbs")}
            </p>
            {inScope.slice(0, 3).map((r) => (
              <div key={r.code} className="flex items-center gap-3">
                <span className="w-40 shrink-0 truncate text-sm font-medium text-foreground">
                  {r.name}
                </span>
                <span className="h-2 min-w-24 flex-1 overflow-hidden rounded-full bg-muted">
                  <span
                    className="block h-full rounded-full bg-primary"
                    style={{ width: `${Math.min(100, Math.max(0, r.prob * 100))}%` }}
                  />
                </span>
                <span className="w-9 shrink-0 text-right font-mono text-sm text-primary">
                  {r.prob.toFixed(2)}
                </span>
              </div>
            ))}
            {p.well_control && (
              <span className="inline-block rounded-sm border border-primary/60 bg-primary/10 px-2 py-0.5 font-mono text-xs font-semibold text-primary">
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

        <HighlightedText text={report.text} spans={p.evidence_spans} />

        <ExplanationSection report={report} lang={lang} />
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

/** Lazily-fetched explanation. The template is the deterministic floor and
 *  always renders once loaded; the ollama rewording is additive, labeled,
 *  and never required. Loading shows a skeleton — the card itself never
 *  blocks on this fetch (offline -> mock fallback -> quiet unavailable). */
function ExplanationSection({ report, lang }: { report: Report; lang: Lang }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState<ExplanationOut | null>(
    report.prediction.explanation,
  );
  const requestedFor = useRef<number | null>(
    report.prediction.explanation ? report.id : null,
  );

  // New report selected -> reset to its bundled explanation (if any).
  useEffect(() => {
    setExplanation(report.prediction.explanation);
    requestedFor.current = report.prediction.explanation ? report.id : null;
  }, [report.id, report.prediction.explanation]);

  useEffect(() => {
    if (!open || requestedFor.current === report.id) return;
    requestedFor.current = report.id;
    let cancel = false;
    setLoading(true);
    getExplanation(report.id)
      .then((ex) => {
        if (!cancel) setExplanation(ex);
      })
      .finally(() => {
        if (!cancel) setLoading(false);
      });
    return () => {
      cancel = true;
    };
  }, [open, report.id]);

  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex min-h-11 w-full items-center gap-2 px-4 py-2 text-left font-medium text-foreground transition-colors hover:bg-muted/60"
      >
        {open ? (
          <ChevronUp className="size-4 text-primary" aria-hidden />
        ) : (
          <ChevronDown className="size-4 text-primary" aria-hidden />
        )}
        {t(lang, "whyScore")}
        {explanation?.source === "ollama" && (
          <span className="ml-auto rounded-sm border border-primary/60 bg-primary/10 px-1.5 py-0.5 font-mono text-xs text-primary">
            {t(lang, "llmPhrased")}
            {explanation.cached ? " · cached" : ""}
          </span>
        )}
      </button>
      {open && (
        <div className="space-y-3 border-t border-border px-4 py-3">
          {loading ? (
            <div className="space-y-2" aria-busy="true" aria-label="loading explanation">
              <div className="h-3 w-3/4 animate-pulse rounded-sm bg-muted" />
              <div className="h-3 w-full animate-pulse rounded-sm bg-muted" />
              <div className="h-3 w-5/6 animate-pulse rounded-sm bg-muted" />
            </div>
          ) : explanation ? (
            <>
              {explanation.reworded && (
                <p className="text-foreground">{explanation.reworded}</p>
              )}
              <p className="font-mono text-sm whitespace-pre-line text-muted-foreground">
                {explanation.template}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Explanation unavailable — the deterministic template is produced
              by the API when it is reachable.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
