/*
 * VerdictCard — ONE card per report. Fixes today's inversions:
 *  - Score + evidence are ALWAYS visible regardless of band (today the
 *    DANGEROUS card hides them behind a gray-state card while the benign
 *    card shows them — precisely backwards for a safety tool).
 *  - A single <article> root: one report can never render as two stacked
 *    cards. Gray routing is expressed as REVIEW wording + gate rows, never
 *    by replacing the card with a scoreless gray shell.
 *  - The decision footer shows WHICH decision was taken (today a decided
 *    card reads only "Reviewed by HSE").
 *  - Evidence spans render straight from the prediction, so they appear on
 *    freshly classified reports too.
 */

import { formatDisplayDate } from "@/lib/format";
import type { Lang } from "@/lib/phrasebook";
import { t } from "@/lib/phrasebook";
import type { EvidenceSpan, GateState, RuleScore } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";
import { effectiveWord } from "./domain-logic";
import type { BarrierState, ExplanationView, Stability } from "./domain-types";
import { ScoreReadout } from "./score-readout";
import { EvidenceText } from "./evidence-text";
import { RuleBars } from "./rule-bars";
import { GateList } from "./gate-list";
import { BarrierList } from "./barrier-list";
import { ExplanationBlock } from "./explanation-block";

export function VerdictCard({
  report,
  score,
  band,
  threshold,
  stability,
  modelVersion,
  rules,
  spans,
  gates,
  barriers,
  explanation,
  decision,
  lang = "en",
  density = "comfortable",
  className,
}: {
  report: {
    id?: number | string | null;
    text: string;
    site?: string | null;
    activity?: string | null;
    contractor?: string | null;
    reported_at?: string | null;
  };
  score: number;
  /** Review-priority word for the score, derived by the caller from the
   *  SERVER operating point (never a private client threshold). */
  band: Parameters<typeof effectiveWord>[0];
  /** The server's tuned operating point — required, passed to ScoreReadout. */
  threshold: number;
  stability?: Stability | null;
  modelVersion?: string | null;
  rules?: RuleScore[] | null;
  spans?: EvidenceSpan[] | null;
  gates?: GateState[] | null;
  /** Fired barrier-failure gates (A2 family) — surfaces the named absent
   *  safeguard next to the verdict, as the barrier gates require. */
  barriers?: BarrierState[] | null;
  explanation?: ExplanationView | null;
  /** Rendered at the bottom of the main (text) column so the decision form
   *  fills the space under the report text instead of leaving a hole when the
   *  side rail (score + gates + rules) runs taller. The decision entry point
   *  itself lives in this slot — one decision control per screen. */
  decision?: ReactNode;
  lang?: Lang;
  density?: "compact" | "comfortable";
  className?: string;
}) {
  const word = effectiveWord(band, stability);
  const compact = density === "compact";
  const title =
    report.site?.trim() ||
    report.activity?.trim() ||
    (report.id != null ? `${t(lang, "colReport")} #${report.id}` : "");
  const dateLabel = report.reported_at ? formatDisplayDate(report.reported_at, lang) : null;
  const pad = compact ? "p-4" : "p-6 md:p-8";
  return (
    <article
      data-report-id={report.id ?? undefined}
      className={cn(
        "flex flex-col overflow-hidden rounded-md border border-border-subtle bg-surface-card shadow-sm",
        className,
      )}
    >
      <header
        className={cn(
          "flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-border-subtle",
          compact ? "px-4 py-3" : "px-6 py-4 md:px-8",
        )}
      >
        {title ? (
          <h2 className="max-w-3xl text-xl font-semibold text-content-primary">{title}</h2>
        ) : (
          <h2 className="sr-only">{t(lang, "colReport")}</h2>
        )}
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm text-content-secondary">
          {report.contractor ? <span>{report.contractor}</span> : null}
          {dateLabel ? <span>{dateLabel}</span> : null}
          {report.id != null ? <span className="font-mono">#{report.id}</span> : null}
        </div>
      </header>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]">
        {/* Verdict rail — first in reading order on small screens. Always
            visible: every band, every gate state. */}
        <aside
          className={cn(
            "flex flex-col gap-6 border-b border-border-subtle bg-surface-zebra lg:order-2 lg:border-b-0 lg:border-l",
            pad,
          )}
        >
          <ScoreReadout
            score={score}
            band={word}
            threshold={threshold}
            stability={stability}
            modelVersion={modelVersion}
            lang={lang}
          />
          {gates && gates.length > 0 ? <GateList gates={gates} lang={lang} /> : null}
          {rules && rules.length > 0 ? <RuleBars rules={rules} lang={lang} /> : null}
        </aside>

        <div className={cn("flex min-w-0 flex-col gap-6", pad)}>
          <EvidenceText text={report.text} spans={spans} lang={lang} />
          {barriers && barriers.length > 0 ? <BarrierList barriers={barriers} lang={lang} /> : null}
          {explanation ? (
            <ExplanationBlock
              template={explanation.template}
              source={explanation.source}
              cached={explanation.cached}
              reworded={explanation.reworded}
              lang={lang}
            />
          ) : null}
          {decision}
        </div>
      </div>
    </article>
  );
}