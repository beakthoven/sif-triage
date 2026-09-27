/* DECISIONS — the compliance audit surface + CAPA closure loop.
 *
 * Answers, per row: WHO (a real reviewer identity — self-declared, disclosed
 * as such), WHEN (recorded server-side), WAS (the value replaced), NOW (the
 * winning value), WHY (mandatory rationale on every correction recorded
 * here), plus report context (snippet + id + severity band) and an append-only
 * Correct flow whose supersede lineage the NDJSON export carries. CAPA fields
 * (owner / due / status + OISD FIR-24h / IIR-30d aging) make decisions reach
 * closure instead of dying in a log.
 *
 * Contract: imports only @/components/ui, @/lib/*, and this slice. i18n EN/हिं
 * via ./strings (keys "dec*" — mergeable into the phrasebook without clash). */
import { useCallback, useEffect, useMemo, useState } from "react";
import { getMetricsSummary, getRules } from "@/lib/api";
import { ChartNoAxesColumn, ClipboardList, Download, History, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { cn } from "@/lib/utils";
import { Chip } from "@/components/ui/chip";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Tooltip } from "@/components/ui/tooltip";
import type { Lang } from "@/lib/phrasebook";
import type { MetricsSummary, RuleInfo } from "@/lib/types";
import { AuditTable } from "./audit-table";
import { AmendDialog, CapaDialog } from "./dialogs";
import {
  computeWorkload,
  exportNdjson,
  fetchAuditRows,
  getReportMeta,
  knownLabelers,
  loadCapas,
  loadReviewer,
  saveCapa,
  saveReviewer,
  supersededIds,
  type AuditSnapshot,
  type AuditRow,
  type Capa,
  type CapaStore,
  type ReportMeta,
} from "./data";
import { dt } from "./strings";

interface StatusMsg {
  kind: "ok" | "err";
  text: string;
}

export default function DecisionsView({ lang }: { lang: Lang }) {
  const [snapshot, setSnapshot] = useState<AuditSnapshot | null>(null);
  const [metas, setMetas] = useState<Record<number, ReportMeta | null>>({});
  const [capas, setCapas] = useState<CapaStore>(() => loadCapas());
  const [reviewer, setReviewer] = useState(() => loadReviewer());
  const [rules, setRules] = useState<RuleInfo[]>([]);
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [amendRow, setAmendRow] = useState<AuditRow | null>(null);
  const [capaRow, setCapaRow] = useState<AuditRow | null>(null);
  const [status, setStatus] = useState<StatusMsg | null>(null);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    setLoadError(false);
    try {
      const snap = await fetchAuditRows();
      setSnapshot(snap);
      const ids = [...new Set(snap.rows.map((r) => r.report_id))];
      const [results, metrics] = await Promise.all([
        Promise.all(ids.map((id) => getReportMeta(id))),
        getMetricsSummary(),
      ]);
      setMetas(Object.fromEntries(ids.map((id, i) => [id, results[i]])));
      setSummary(metrics);
    } catch {
      setSnapshot(null);
      setLoadError(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // getRules also refreshes the lib's live rule display metadata.
  useEffect(() => {
    let cancel = false;
    void getRules().then((rs) => {
      if (!cancel) setRules(rs);
    });
    return () => {
      cancel = true;
    };
  }, []);

  const changeReviewer = useCallback((name: string) => {
    setReviewer(name);
    saveReviewer(name);
  }, []);

  const onExport = useCallback(async () => {
    try {
      const n = await exportNdjson();
      setStatus({ kind: "ok", text: `${n} ${dt(lang, "exportOk")}` });
    } catch {
      setStatus({ kind: "err", text: dt(lang, "exportFail") });
    }
  }, [lang]);

  const rows = snapshot?.rows ?? [];
  const superseded = useMemo(() => supersededIds(rows), [rows]);
  const workload = useMemo(() => computeWorkload(rows, capas), [rows, capas]);

  const onSaveCapa = (capa: Capa) => {
    if (!capaRow) return;
    setCapas(saveCapa(capaRow.id, capa, capas));
    setCapaRow(null);
    setStatus({ kind: "ok", text: dt(lang, "capaSaved") });
  };

  const labelers = knownLabelers(rows);

  const aged = workload.firAged + workload.iirAged;

  return (
    <section aria-label={dt(lang, "decTitle")} className="space-y-6 md:space-y-8">
      <PageHeader
        eyebrow={dt(lang, "decEyebrow")}
        title={dt(lang, "decPageTitle")}
        description={dt(lang, "decSub")}
        actions={
          <>
            {snapshot?.offline && (
              <Chip tone="uncertain" size="md">
                {dt(lang, "offlineChip")}
              </Chip>
            )}
            <Tooltip content={dt(lang, "exportHint")}>
              <Button
                variant="secondary"
                size="md"
                disabled={snapshot === null || loadError}
                onClick={() => void onExport()}
              >
                <Download aria-hidden="true" />
                {dt(lang, "exportBtn")}
              </Button>
            </Tooltip>
          </>
        }
      >
        {snapshot?.offline && <p className="text-sm text-content-muted">{dt(lang, "offlineNote")}</p>}
      </PageHeader>

      <p
        role="status"
        aria-live="polite"
        className={cn(
          "text-sm empty:hidden",
          status?.kind === "err" ? "text-status-danger" : "text-content-secondary",
        )}
      >
        {status?.text ?? ""}
      </p>

      {loadError ? (
        <ErrorState
          title={dt(lang, "loadFailed")}
          description={dt(lang, "retry")}
          onRetry={() => void load()}
        />
      ) : snapshot === null ? (
        <Progress indeterminate label={dt(lang, "loadingLabel")} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<History />}
          title={dt(lang, "emptyTitle")}
          description={dt(lang, "emptyBody")}
          action={<Button variant="primary" onClick={() => window.location.assign("/#/queue")}>{dt(lang, "openReports")}</Button>}
        />
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-12 lg:gap-6">
            <Card density="compact" className="lg:col-span-4">
              <CardHeader icon={<UserRound />} title={dt(lang, "reviewerCardTitle")} />
              <Field label={dt(lang, "reviewerHeading")} hint={dt(lang, "reviewerHint")} required>
                <Input
                  value={reviewer}
                  onChange={(e) => changeReviewer(e.target.value)}
                  placeholder={dt(lang, "reviewerPlaceholder")}
                  list="decisions-known-labelers"
                />
              </Field>
              <datalist id="decisions-known-labelers">
                {labelers.map((n) => (
                  <option key={n} value={n} />
                ))}
              </datalist>
            </Card>

            <Card density="compact" className="lg:col-span-8">
              <CardHeader
                icon={<ClipboardList />}
                title={dt(lang, "workloadTitle")}
                actions={
                  aged > 0 ? (
                    <Chip tone="danger" size="sm">
                      {dt(lang, "overdue")}
                    </Chip>
                  ) : undefined
                }
              />
              <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border-subtle bg-border-subtle sm:grid-cols-4">
                <Stat label={dt(lang, "workloadOpen")} value={workload.open} />
                <Stat label={dt(lang, "workloadProgress")} value={workload.inProgress} />
                <Stat label={dt(lang, "workloadClosed")} value={workload.closed} />
                <Stat label={dt(lang, "workloadNoCapa")} value={workload.noCapa} />
              </dl>
              <div className="flex flex-wrap gap-2">
                <Chip tone={workload.firAged > 0 ? "danger" : "clear"} size="sm">
                  {workload.firAged} {dt(lang, "workloadFirAged")}
                </Chip>
                <Chip tone={workload.iirAged > 0 ? "danger" : "clear"} size="sm">
                  {workload.iirAged} {dt(lang, "workloadIirAged")}
                </Chip>
              </div>
              {workload.byOwner.length > 0 && (
                <p className="text-sm text-content-secondary">
                  {dt(lang, "workloadByOwner")}:{" "}
                  {workload.byOwner.map((o) => `${o.owner} (${o.n})`).join(", ")}
                </p>
              )}
              <p className="text-xs text-content-muted">{dt(lang, "workloadNote")}</p>
            </Card>

            <Card density="compact" className="lg:col-span-12">
              <CardHeader
                icon={<ChartNoAxesColumn />}
                title={dt(lang, "metricsTitle")}
                meta={
                  summary ? (
                    <span className="font-mono text-xs">
                      {summary.classifier} · {summary.model_version}
                    </span>
                  ) : undefined
                }
              />
              {summary ? (
                <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border-subtle bg-border-subtle md:grid-cols-4">
                  <Stat
                    label={dt(lang, "metricsReports")}
                    value={summary.n_reports.toLocaleString("en-IN")}
                  />
                  <Stat
                    label={dt(lang, "metricsFlagged")}
                    value={summary.n_flagged.toLocaleString("en-IN")}
                  />
                  <Stat
                    label={dt(lang, "metricsFlagRate")}
                    value={`${(summary.flag_rate * 100).toFixed(1)}%`}
                  />
                  <Stat label={dt(lang, "metricsOverrides")} value={summary.n_overrides} />
                </dl>
              ) : (
                <p className="text-sm text-content-muted">{dt(lang, "metricsUnavailable")}</p>
              )}
            </Card>
          </div>

          <Card density="compact" className="gap-0 p-0 md:p-0">
            <CardHeader
              icon={<History />}
              className="p-4 md:p-6"
              title={dt(lang, "decTitle")}
              meta={
                <span className="font-mono text-xs">
                  {rows.length.toLocaleString("en-IN")} {dt(lang, "recordsWord")}
                </span>
              }
            />
            <div className="border-t border-border-subtle">
              <AuditTable
                lang={lang}
                rows={rows}
                metas={metas}
                capas={capas}
                superseded={superseded}
                onCorrect={setAmendRow}
                onCapa={setCapaRow}
              />
            </div>
          </Card>
        </>
      )}

      <AmendDialog
        open={amendRow !== null}
        onOpenChange={(o) => {
          if (!o) setAmendRow(null);
        }}
        lang={lang}
        row={amendRow}
        rules={rules}
        reviewer={reviewer}
        onReviewerChange={changeReviewer}
        onSubmitted={() => {
          setStatus({ kind: "ok", text: dt(lang, "amendOk") });
          void load();
        }}
      />

      <CapaDialog
        open={capaRow !== null}
        onOpenChange={(o) => {
          if (!o) setCapaRow(null);
        }}
        lang={lang}
        row={capaRow}
        meta={capaRow ? (metas[capaRow.report_id] ?? null) : null}
        existing={capaRow ? (capas[capaRow.id] ?? null) : null}
        defaultOwner={reviewer}
        onSave={onSaveCapa}
      />
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-1 bg-surface-card px-4 py-3">
      <dt className="text-xs font-semibold tracking-wide text-content-secondary uppercase">{label}</dt>
      <dd className="text-kpi-num text-2xl text-content-primary md:text-3xl">{value}</dd>
    </div>
  );
}

export { DecisionsView };
