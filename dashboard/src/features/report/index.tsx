import { useMemo, useState } from "react";
import { useParams } from "react-router";
import { ArrowLeft } from "lucide-react";
import type { BarrierState, Stability, VerdictWord } from "@/components/domain/domain-types";
import { VerdictCard } from "@/components/domain/verdict-card";
import { Button, EmptyState, ErrorState, Skeleton } from "@/components/ui";
import { useExplanation, useOverrides, usePostReview, useReport } from "@/lib/api";
import { formatDisplayDate } from "@/lib/format";
import { t, type Lang } from "@/lib/phrasebook";
import type { GateState, OverrideOut, PredictionOut, Report } from "@/lib/types";
import { BARRIER_LABELS, c } from "./copy";
import { DecisionPanel, latestLabelDecision, type RecordedDecision } from "./decision-panel";

/* ---- derivation: server facts only, no private client thresholds --------- */

/** Legacy fallback for pre-operating-point responses whose explanation
 *  template still names the server threshold. Current prediction payloads
 *  expose flag_threshold directly; never derive a replacement threshold. */
export function thresholdFromTemplate(template: string): number | null {
  const m = template.match(/(?:crossed|below) the (0\.\d{1,4}) review threshold/);
  return m ? Number(m[1]) : null;
}

/** Review-priority word from server decisions only. The server's band when
 *  the wire carries it (A4); else the server's own routing — flagged at the
 *  server operating point → HIGH; a triggered gray gate (confidence band,
 *  well-control watch, chunked-low, severity watch, verdict stability)
 *  means the server routed this report to human review → MODERATE; otherwise
 *  LOW. No private client threshold anywhere. */
function verdictBand(pred: PredictionOut, threshold: number): VerdictWord {
  if (pred.band) return pred.band;
  if (pred.sif_score >= threshold) return "HIGH";
  if (pred.gate_states.some((g) => g.triggered && g.action === "gray")) return "MODERATE";
  return "LOW";
}

/** A3 self-consistency, as the domain StabilityIndicator expects it. The
 *  server's verdict_stability is the FRACTION of variants agreeing with the
 *  mean-score verdict; the indicator wants a flip COUNT — derived, not
 *  invented. Hidden while the runtime scored a single variant (older rows). */
function stabilityOf(pred: PredictionOut): Stability | null {
  const nVariants = typeof pred.n_variants === "number" ? pred.n_variants : 0;
  const spread = typeof pred.score_spread === "number" ? pred.score_spread : null;
  if (nVariants <= 1 || spread === null || !Number.isFinite(spread)) return null;
  const agreement = pred.verdict_stability;
  const verdictFlips =
    typeof agreement === "number" && Number.isFinite(agreement)
      ? Math.max(0, nVariants - Math.round(agreement * nVariants))
      : null;
  return { spread, nVariants, verdictFlips };
}

/** The barrier-failure gate family (implementation-plan A2). Gate names are
 * the contract with app/gates.py; only FIRED gates are surfaced — absence of
 * a signal is disclosed separately, never inferred. */
const BARRIER_GATES = new Set([
  "energy_isolation_absent",
  "gas_test_absent",
  "permit_absent",
  "fire_watch_absent",
  "standby_absent",
  "atmosphere_unmonitored",
  "fall_protection_absent",
]);

function barrierStates(gates: GateState[], lang: Lang): BarrierState[] {
  return gates
    .filter((g) => BARRIER_GATES.has(g.name) && g.triggered)
    .map((g) => ({
      gate: g.name,
      label: BARRIER_LABELS[g.name]?.[lang] ?? g.name.replace(/[_-]+/g, " "),
      detail: g.detail,
    }));
}

/** General gates for GateList: barrier gates are excluded (they render
 * through VerdictCard's own BarrierList slot, not as generic gate rows).
 * long_input's windowing jargon is reduced to the reviewed plain sentence;
 * all other details pass verbatim (GateList strips vector math itself). */
function inputGates(gates: GateState[], lang: Lang): GateState[] {
  return gates
    .filter((g) => !BARRIER_GATES.has(g.name))
    .map((g) =>
      g.name === "long_input" && g.triggered ? { ...g, detail: t(lang, "chunkedBadge") } : g,
    );
}

/** Overrides for THIS report only — DEMO_MODE's fixture fallback returns the
 * whole override table, so the filter is load-bearing. */
function reportOverrides(report: Report | null, data: OverrideOut[] | undefined) {
  return (data ?? []).filter((o) => o.report_id === report?.id);
}

/** useParams only inside SHELL's router (routes.tsx always mounts inside
 * HashRouter); outside one, the id prop wins. */
function useParamsSafe(): Record<string, string | undefined> {
  try {
    return useParams();
  } catch {
    return {};
  }
}

/**
 * Report detail — the single-report surface at /report/:id.
 *
 * One unified VerdictCard per report (score + evidence always visible, every
 * band — HIGH included). The report text, fired barrier notes and decision form
 * share the main column so reviewers read what happened and act in one flow.
 * Metadata preserves the event-vs-ingest date distinction; variants and review
 * history stay visible without repeating detector internals.
 *
 * The verdict area renders from the operating point on the loaded prediction;
 * a legacy explanation-template parse is only a fallback. Explanation content
 * fills into the card when its independent query resolves.
 */
export default function ReportDetail({
  id: idProp,
  lang = "en",
}: {
  id?: string | number;
  lang?: Lang;
}) {
  const params = useParamsSafe();
  const raw = idProp ?? params.id;
  const idNum = typeof raw === "number" ? raw : Number(raw);
  const validId =
    (typeof raw === "number" || /^[1-9]\d*$/.test(raw ?? "")) &&
    Number.isSafeInteger(idNum) && idNum > 0;

  const reportQ = useReport(validId ? idNum : null);
  const report = reportQ.data ?? null;
  const explanationQ = useExplanation(report?.id ?? null, Boolean(report));
  const overridesQ = useOverrides(report ? report.id : undefined);
  const postReview = usePostReview();

  const [submitError, setSubmitError] = useState<string | null>(null);

  const recorded: RecordedDecision | null = useMemo(
    () => latestLabelDecision(reportOverrides(report, overridesQ.data)),
    [report, overridesQ.data],
  );

  async function submitDecision(
    choice: "confirm" | "reject",
    rationale: string,
    reviewer: string,
  ): Promise<boolean> {
    if (!report) return false;
    const newValue = choice === "confirm" ? "sif_potential" : "not_sif_potential";
    setSubmitError(null);
    try {
      await postReview.mutateAsync({
        report_id: report.id,
        field: "sif_label",
        old_value: report.prediction.band ?? null,
        new_value: newValue,
        labeler: reviewer,
        rationale,
      });
      return true;
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
      return false;
    }
  }

  const pred = report?.prediction ?? null;
  const explanation = explanationQ.data ?? null;
  const threshold =
    pred?.flag_threshold ??
    (explanation ? thresholdFromTemplate(explanation.template) : null);
  const overridesError = overridesQ.isError
    ? overridesQ.error instanceof Error
      ? overridesQ.error.message
      : "override load failed"
    : null;

  return (
    <div className="space-y-6" aria-label={c(lang, "eyebrow")}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow">{c(lang, "eyebrow")}</p>
          <h1 className="page-title">
            {t(lang, "colReport")} <span className="font-mono">#{validId ? idNum : "—"}</span>
          </h1>
        </div>
        <Button variant="secondary" size="sm" icon={<ArrowLeft />} onClick={() => history.back()}>
          {c(lang, "back")}
        </Button>
      </div>

      {!validId || reportQ.data === null ? (
        <EmptyState title={c(lang, "notFoundTitle")} description={c(lang, "notFoundBody")} />
      ) : reportQ.isPending ? (
        <LoadingBlock lang={lang} />
      ) : reportQ.isError || !report || !pred ? (
        <ErrorState
          title={c(lang, "loadFailedTitle")}
          description={c(lang, "loadFailedBody")}
          onRetry={() => void reportQ.refetch()}
        />
      ) : (
        <>
          <MetaBlock report={report} lang={lang} />

          {threshold !== null ? (
            <>
              <VerdictCard
                report={report}
                score={pred.sif_score}
                band={verdictBand(pred, threshold)}
                threshold={threshold}
                stability={stabilityOf(pred)}
                modelVersion={pred.model_version}
                rules={pred.rules}
                spans={pred.evidence_spans}
                gates={inputGates(pred.gate_states, lang)}
                barriers={barrierStates(pred.gate_states, lang)}
                explanation={explanation}
                decision={
                  <DecisionPanel
                    report={report}
                    lang={lang}
                    recorded={recorded}
                    submitting={postReview.isPending}
                    submitError={submitError}
                    overridesError={overridesError}
                    onSubmit={submitDecision}
                    onDismissError={() => setSubmitError(null)}
                  />
                }
                lang={lang}
                density="comfortable"
              />
              {pred.variant_scores != null && pred.variant_scores.length > 1 && (
                <p className="font-mono text-xs text-content-secondary">
                  {c(lang, "variantScoresLabel")}:{" "}
                  {pred.variant_scores.map((s) => s.toFixed(3)).join(" · ")}
                </p>
              )}
            </>
          ) : explanationQ.isPending ? (
            <div
              className="grid gap-6 rounded-md border border-border-subtle bg-surface-card p-6 shadow-sm md:p-8 lg:grid-cols-[1fr_320px]"
              aria-busy="true"
            >
              <div className="space-y-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-11/12" />
                <Skeleton className="h-4 w-4/6" />
              </div>
              <div className="space-y-3">
                <Skeleton className="h-10 w-32" />
                <Skeleton className="h-3 w-full" />
              </div>
            </div>
          ) : (
            <WithheldNotice lang={lang} onRetry={() => void explanationQ.refetch()} />
          )}
        </>
      )}
    </div>
  );
}

/* ---- sections ------------------------------------------------------------ */

function MetaBlock({ report, lang }: { report: Report; lang: Lang }) {
  // SHELL's planned Report split (event_date / ingested_at) lights these rows
  // up the moment lib carries them; today the API exposes one merged date and
  // the block says so instead of presenting two fabricated facts.
  const ext = report as Report & { event_date?: string | null; ingested_at?: string | null };
  const eventDate =
    typeof ext.event_date === "string" && ext.event_date ? ext.event_date : report.reported_at;
  const ingested = typeof ext.ingested_at === "string" && ext.ingested_at ? ext.ingested_at : null;

  const facts: { label: string; value: string; mono?: boolean }[] = [
    { label: t(lang, "colReport"), value: `#${report.id}`, mono: true },
    { label: t(lang, "site"), value: report.site || "—" },
    { label: c(lang, "metaActivity"), value: report.activity || "—" },
    { label: c(lang, "metaContractor"), value: report.contractor || c(lang, "metaContractorMissing") },
    { label: c(lang, "metaEventDate"), value: formatDisplayDate(eventDate, lang), mono: true },
    {
      label: c(lang, "metaIngested"),
      value: ingested ? formatDisplayDate(ingested, lang) : "—",
      mono: true,
    },
  ];

  return (
    <section aria-label={c(lang, "eyebrow")} className="space-y-2">
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border-subtle bg-border-subtle shadow-sm sm:grid-cols-3 lg:grid-cols-6">
        {facts.map((f) => (
          <div key={f.label} className="flex min-w-0 flex-col gap-1 bg-surface-card px-4 py-3">
            <dt className="text-xs font-semibold tracking-wider text-content-secondary uppercase">{f.label}</dt>
            <dd
              className={`truncate text-content-primary ${f.mono ? "font-mono text-sm" : "text-sm font-medium"}`}
              title={f.value}
            >
              {f.value}
            </dd>
          </div>
        ))}
      </dl>
      {ingested === null && (
        <p className="max-w-prose text-xs text-content-secondary">{c(lang, "dateConflation")}</p>
      )}
    </section>
  );
}

function LoadingBlock({ lang }: { lang: Lang }) {
  return (
    <div aria-busy="true" className="space-y-6">
      <p className="text-sm text-content-secondary">{c(lang, "loadingReport")}</p>
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-72 w-full" />
    </div>
  );
}

function WithheldNotice({ lang, onRetry }: { lang: Lang; onRetry: () => void }) {
  return (
    <div
      role="note"
      className="flex flex-col gap-4 rounded-md border border-border-subtle bg-surface-card p-6 shadow-sm md:p-8"
    >
      <p className="max-w-prose text-base text-content-primary">{c(lang, "verdictWithheld")}</p>
      <div>
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {c(lang, "retry")}
        </Button>
      </div>
    </div>
  );
}
