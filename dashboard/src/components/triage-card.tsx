import { ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { HighlightedText } from "@/components/highlighted-text";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { getExplanation } from "@/lib/api";
import { t, type Lang } from "@/lib/phrasebook";
import { reportActivityLabel, reportSiteLabel } from "@/lib/report-display";
import type { ExplanationOut, Report } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * THE triage card (money shot) — the one memorable element on the page.
 * The verdict is the biggest type: "High review priority" in the single
 * amber accent (#B45309), marked by a quiet 3px amber top-border (the old
 * hazard stripe's last appearance). Score is a calm mono number labeled
 * "triage score" — never %, never "detected" (D14 / UX SEV1-1).
 *
 * D22: the top-3 in-scope rule probabilities render as thin bars — never a
 * single asserted rule. The sub-line says "Flagged for HSE review" on
 * HIGH/MODERATE (review SEV2-4/SEV2-5); LOW reads "No action needed" in
 * quiet green, without the amber border.
 *
 * Badge gates annotate here instead of routing to the gray queue:
 * near_dup -> amber left-border "memory, not generalization" note;
 * chunked / long_input -> a slate dot label. The explanation expander
 * fetches GET /api/reports/{id}/explanation lazily — async with a skeleton,
 * the card never blocks on it; template always renders, the ollama
 * rewording is shown when (and only when) the API produced one.
 */
export function TriageCard({
  report,
  lang,
  reviewed = false,
  onOverride,
}: {
  report: Report;
  lang: Lang;
  reviewed?: boolean;
  onOverride?: (reportId: number, decision: "confirm" | "not_sif") => void;
}) {
  const p = report.prediction;
  const siteLabel = reportSiteLabel(report);
  const activityLabel = reportActivityLabel(report);
  const [decision, setDecision] = useState<"confirm" | "not_sif" | null>(null);
  const inScope = p.rules.filter((r) => r.in_scope);
  const nearDup = p.gate_states.find((g) => g.name === "near_dup" && g.triggered);
  const longInput = p.gate_states.find((g) => g.name === "long_input" && g.triggered);
  const chunked = p.chunked || longInput !== undefined;
  const reviewPriority = p.band !== "LOW";
  const verdict =
    p.band === "HIGH"
      ? t(lang, "highPriority")
      : p.band === "MODERATE"
        ? t(lang, "moderatePriority")
        : t(lang, "noAction");

  useEffect(() => {
    setDecision(null);
  }, [report.id]);

  function decide(next: "confirm" | "not_sif") {
    setDecision(next);
    onOverride?.(report.id, next);
  }

  return (
    <Card
      className={cn(
        "gap-0 border-border py-0",
        reviewPriority && "border-t-[3px] border-t-verdict",
      )}
    >
      <CardContent className="gap-0 px-6 pt-6 pb-6">
        {/* Verdict + score */}
        <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-2">
          <h2
            className={cn(
              "text-3xl font-semibold tracking-tight first-letter:uppercase",
              reviewPriority ? "text-verdict" : "text-ok",
            )}
          >
            {verdict}
          </h2>
          <p
            className="flex items-baseline gap-2 text-sm text-muted-foreground"
            aria-label={t(lang, "triageScore")}
          >
            {t(lang, "triageScore")}
            <span className="font-mono text-sm text-muted-foreground">
              {p.sif_score.toFixed(2)}
            </span>
          </p>
        </div>
        {reviewPriority && (
          <p className="mt-1.5 text-sm text-muted-foreground">{t(lang, "flaggedFor")}</p>
        )}

        {/* Show useful report context without leaking raw missing-value placeholders. */}
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>
            {siteLabel}
            {activityLabel ? ` · ${activityLabel}` : ""}
          </span>
          {chunked && (
            <span
              className="inline-flex items-center gap-1.5 font-medium text-quiet"
              title={longInput?.detail}
            >
              <span className="status-dot bg-quiet" aria-hidden />
              {t(lang, "chunkedBadge")}
            </span>
          )}
        </div>

        {/* Near-dup note: badge gate, amber left border, quiet. */}
        {nearDup && (
          <div className="mt-4 border-l-[3px] border-l-verdict bg-verdict/5 px-4 py-2.5">
            <p className="text-sm font-medium text-foreground">
              {t(lang, "nearDupBanner")}
            </p>
            {nearDup.detail && (
              <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                {nearDup.detail}
              </p>
            )}
          </div>
        )}

        {/* Matching life-saving rules — thin quiet bars, top 3 in-scope */}
        {inScope.length > 0 && (
          <div className="mt-6 space-y-2" aria-label={t(lang, "ruleProbs")}>
            <p className="text-sm font-medium text-muted-foreground">
              {t(lang, "ruleProbs")}
            </p>
            {inScope.slice(0, 3).map((r) => (
              <div key={r.code} className="flex items-center gap-3">
                <span className="w-44 shrink-0 truncate text-sm text-foreground">
                  {r.name}
                </span>
                <span className="h-1 min-w-24 flex-1 overflow-hidden rounded-full bg-muted">
                  <span
                    className="block h-full rounded-full bg-foreground/70"
                    style={{ width: `${Math.min(100, Math.max(0, r.prob * 100))}%` }}
                  />
                </span>
                <span className="w-9 shrink-0 text-right font-mono text-sm text-foreground">
                  {r.prob.toFixed(2)}
                </span>
              </div>
            ))}
            {p.well_control && (
              <p className="inline-flex items-center gap-1.5 pt-1 text-xs font-medium text-quiet">
                <span className="status-dot bg-quiet" aria-hidden />
                {t(lang, "wellControlTag")}
              </p>
            )}
          </div>
        )}
        <div className="mt-5">
          <HighlightedText text={report.text} spans={p.evidence_spans} />
        </div>

        <ExplanationSection report={report} lang={lang} />
      </CardContent>

      <CardFooter className="border-t border-border px-6 py-4 [.border-t]:pt-4">
        {reviewed ? (
          <p className="inline-flex items-center gap-2 text-sm font-medium text-ok">
            <span className="status-dot bg-ok" aria-hidden />
            {t(lang, "alreadyReviewed")}
          </p>
        ) : (
          <details className="w-full">
            <summary className="cursor-pointer text-sm font-medium text-foreground">
              {t(lang, "recordOutcome")}
            </summary>
            <p className="mt-2 text-xs text-muted-foreground">{t(lang, "optionalReview")}</p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button
                size="lg"
                variant={decision === "confirm" ? "default" : "outline"}
                onClick={() => decide("confirm")}
                className="min-h-11"
              >
                {t(lang, "confirm")}
              </Button>
              <Button
                size="lg"
                variant={decision === "not_sif" ? "default" : "outline"}
                onClick={() => decide("not_sif")}
                className="min-h-11"
              >
                {t(lang, "notSif")}
              </Button>
              {decision && (
                <p role="status" className="text-sm font-medium text-ok">
                  {t(lang, "decisionSaved")}
                </p>
              )}
            </div>
          </details>
        )}
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
    <div className="mt-6 border-t border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex min-h-11 w-full items-center gap-2 py-2 text-left text-sm font-medium text-foreground transition-colors hover:text-foreground/70"
      >
        {open ? (
          <ChevronUp className="size-4 text-muted-foreground" aria-hidden />
        ) : (
          <ChevronDown className="size-4 text-muted-foreground" aria-hidden />
        )}
        {t(lang, "whyScore")}
        {explanation?.source === "ollama" && (
          <span className="ml-auto inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
            <span className="status-dot bg-quiet" aria-hidden />
            {t(lang, "llmPhrased")}
            {explanation.cached ? ` · ${t(lang, "cached")}` : ""}
          </span>
        )}
      </button>
      {open && (
        <div className="space-y-3 pb-2">
          {loading ? (
            <div className="space-y-2" aria-busy="true" aria-label={t(lang, "loadingExplanation")}>
              <div className="h-3 w-3/4 animate-pulse rounded-sm bg-muted" />
              <div className="h-3 w-full animate-pulse rounded-sm bg-muted" />
              <div className="h-3 w-5/6 animate-pulse rounded-sm bg-muted" />
            </div>
          ) : explanation ? (
            <p className="whitespace-pre-line text-foreground">
              {explanation.reworded ?? explanation.template}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t(lang, "explanationUnavailable")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
