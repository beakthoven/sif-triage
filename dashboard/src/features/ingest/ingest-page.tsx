/* INGEST — the /ingest route surface and the app's landing page: data in on
 * the left, result out on the right.
 *
 * Two input paths, one truth policy:
 *  1. Single paste-and-classify — POST /api/classify?persist=1 via @/lib/api.
 *  2. Bulk CSV upload — the ingest job API with real rows-done progress, ETA
 *     from the observed rate, cancel, per-row error table, and a final honest
 *     outcome (accepted / rejected / duplicates skipped). When the job API is
 *     absent, the run degrades to the synchronous POST /api/ingest with
 *     elapsed-time-only display and an unconfirmed outcome when the response
 *     wait is interrupted (see use-ingest-job.ts).
 *
 * The demo batch button is LABELLED as synthetic data — 500 register rows
 * styled on OIL field data — confirmed through the Dialog primitive.
 * Primitives come from @/components/ui per the design-system contract. */
import { useRef, useState, type DragEvent } from "react";
import { Link } from "react-router";
import { motion } from "motion/react";
import {
  ArrowRight,
  CircleCheck,
  CircleMinus,
  ClipboardPaste,
  FileSpreadsheet,
  FlaskConical,
  Gauge,
  LoaderCircle,
  RotateCcw,
  Sparkles,
  Upload,
} from "lucide-react";
import { classify, qk } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { t as tShared, type Lang } from "@/lib/phrasebook";
import type { EvidenceSpan, GateState, RuleScore } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Button,
  Card,
  CardHeader,
  Chip,
  Dialog,
  EmptyState,
  PageHeader,
  Progress,
  Skeleton,
  Table,
  Tabs,
  Textarea,
  buttonVariants,
  type ColumnDef,
} from "@/components/ui";
import { EvidenceText, GateList, RuleBars, ScoreMeter } from "@/components/domain";
import type { VerdictWord } from "@/components/domain/domain-types";
import { estimateCsvRows, fetchDemoCsv, VERIFY_WINDOW_MS } from "./ingest-api";
import { t } from "./strings";
import { useIngestRun, type IngestOutcome, type UseIngestRun } from "./use-ingest-job";

const ACTIVE_PHASES = new Set(["starting", "running", "verifying"]);
const isBusy = (p: string) => ACTIVE_PHASES.has(p);

/** Result entrance: communicates "a new result arrived" (DESIGN §7.3). */
const ENTER = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.22, ease: [0, 0, 0.2, 1] as const },
};

type RunTone = "clear" | "neutral" | "danger" | "uncertain";

function runTone(phase: string): RunTone {
  return phase === "cancelled"
    ? "neutral"
    : phase === "failed"
      ? "danger"
      : phase === "indeterminate"
        ? "uncertain"
        : "clear";
}

function runWord(lang: Lang, phase: string, mode: string): string {
  return phase === "cancelled"
    ? t(lang, "statusCancelled")
    : phase === "failed"
      ? t(lang, "statusFailed")
      : phase === "indeterminate"
        ? t(lang, "statusIndeterminate")
        : mode === "sync-verified"
          ? t(lang, "statusDoneVerified")
          : t(lang, "statusDone");
}

/* ---- Single paste path ---- */

interface PasteResult {
  reportId: number | null;
  text: string;
  score: number;
  /** Server-owned review-priority band (A4) — null when the server didn't send one. */
  band: string | null;
  latencyMs: number;
  modelVersion: string;
  offline: boolean;
  gates: GateState[];
  spans: EvidenceSpan[];
  rules: RuleScore[];
  at: number;
}

type PasteState =
  | { status: "idle" }
  | { status: "busy" }
  | { status: "error"; message: string }
  | { status: "done"; result: PasteResult };

function bandWordOf(lang: Lang, band: string | null) {
  return band === "HIGH"
    ? tShared(lang, "highPriority")
    : band === "MODERATE"
      ? tShared(lang, "moderatePriority")
      : band === "LOW"
        ? tShared(lang, "noAction")
        : t(lang, "bandUnavailable");
}

const BAND_TONE: Record<string, "high" | "moderate" | "low"> = {
  HIGH: "high",
  MODERATE: "moderate",
  LOW: "low",
};

function PasteInput({
  lang,
  text,
  setText,
  busy,
  onRun,
  textRef,
}: {
  lang: Lang;
  text: string;
  setText: (s: string) => void;
  busy: boolean;
  onRun: () => void;
  textRef: React.RefObject<HTMLTextAreaElement | null>;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <label htmlFor="ingest-paste" className="text-sm font-medium text-content-primary">
          {t(lang, "reportTextLabel")}
        </label>
        <Textarea
          id="ingest-paste"
          ref={textRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
              e.preventDefault();
              onRun();
            }
          }}
          rows={9}
          className="min-h-56 leading-7"
          placeholder={tShared(lang, "pastePlaceholder")}
          aria-describedby="ingest-paste-note"
        />
        <p id="ingest-paste-note" className="text-sm text-content-secondary">
          {t(lang, "pasteNote")}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 border-t border-border-subtle pt-4">
        <span className="font-mono text-xs text-content-secondary">
          {t(lang, "charCount", { n: text.length.toLocaleString("en-IN") })}
        </span>
        <span className="hidden font-mono text-xs text-content-secondary sm:inline">
          <kbd className="rounded-sm border border-border-default bg-surface-sunken px-1.5 py-0.5">Ctrl</kbd>
          {" + "}
          <kbd className="rounded-sm border border-border-default bg-surface-sunken px-1.5 py-0.5">Enter</kbd>
        </span>
        <Button
          size="lg"
          className="ml-auto"
          icon={<Sparkles />}
          loading={busy}
          onClick={onRun}
          disabled={busy || !text.trim()}
        >
          {busy ? tShared(lang, "pasteBusy") : tShared(lang, "pasteButton")}
        </Button>
      </div>
    </div>
  );
}

function PasteResultPanel({
  lang,
  state,
  active,
  onReset,
}: {
  lang: Lang;
  state: PasteState;
  active: boolean;
  onReset: () => void;
}) {
  if (state.status === "idle") {
    return (
      <EmptyState
        icon={<Gauge />}
        title={t(lang, "resultIdle")}
        description={t(lang, "resultIdleBody")}
        className="h-full min-h-[360px] rounded-lg border-solid bg-surface-card shadow-sm lg:min-h-[539px]"
      />
    );
  }
  if (state.status === "busy") {
    return (
      <Card aria-busy="true" role="status">
        <p className="flex items-center gap-2 text-sm font-semibold text-content-primary">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin text-content-link" />
          {t(lang, "resultBusy")}
        </p>
        <div className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-10 w-40" />
          <Skeleton className="h-3 w-full" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-3/5" />
        </div>
      </Card>
    );
  }
  if (state.status === "error") {
    return (
      <motion.div {...ENTER}>
        <Card role="alert" className="border-l-4 border-l-status-danger-fill">
          <CardHeader title={t(lang, "resultErrorTitle")} meta={t(lang, "pasteTimeout")} />
          {state.message && <p className="font-mono text-xs text-content-secondary">{state.message}</p>}
        </Card>
      </motion.div>
    );
  }

  const r = state.result;
  const band = (r.band === "HIGH" || r.band === "MODERATE" || r.band === "LOW" ? r.band : null) as VerdictWord | null;
  const firedGates = r.gates.filter((g) => g.triggered);

  return (
    <motion.div key={r.at} {...ENTER}>
      <Card role="status" className="gap-0 overflow-hidden p-0 md:p-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border-subtle px-6 py-4">
          {r.offline ? (
            <span className="font-mono text-xs text-content-secondary">{tShared(lang, "offlineNote")}</span>
          ) : r.reportId !== null ? (
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-status-ok">
              <CircleCheck aria-hidden="true" className="size-4" />
              {t(lang, "pasteStored", { id: r.reportId })}
            </span>
          ) : (
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-content-primary">
              <CircleMinus aria-hidden="true" className="size-4 text-content-secondary" />
              {t(lang, "pasteNotStored")}
            </span>
          )}
        </div>

        {r.offline && active && (
          <p role="alert" className="px-6 pt-4 text-base text-content-primary">
            {t(lang, "pasteTimeout")}
          </p>
        )}

        {!r.offline && (
          <div className="flex flex-col gap-4 bg-surface-zebra px-6 py-6">
            <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
              <div className="flex flex-col gap-1">
                <span className="text-xs font-semibold tracking-wider text-content-secondary uppercase">
                  {tShared(lang, "triageScore")}
                </span>
                <span className="text-kpi-num text-content-primary">{r.score.toFixed(3)}</span>
              </div>
              <Chip tone={r.band ? BAND_TONE[r.band] ?? "neutral" : "neutral"} className="mb-1 text-sm">
                {bandWordOf(lang, r.band)}
              </Chip>
            </div>
            <ScoreMeter score={r.score} band={band} />
            <dl className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-content-secondary">
              <div className="flex gap-1">
                <dt>{t(lang, "latencyLabel")}</dt>
                <dd className="text-content-primary">{r.latencyMs} ms</dd>
              </div>
              <div className="flex min-w-0 gap-1">
                <dt>{t(lang, "modelLabel")}</dt>
                <dd className="truncate text-content-primary" title={r.modelVersion}>
                  {r.modelVersion}
                </dd>
              </div>
            </dl>
          </div>
        )}

        <div className="flex flex-col gap-6 px-6 py-6">
          {firedGates.length > 0 ? (
            <GateList gates={r.gates} lang={lang} />
          ) : (
            <p className="text-sm text-content-secondary">{t(lang, "pasteNoGates")}</p>
          )}
          {!r.offline && r.spans.length > 0 && <EvidenceText text={r.text} spans={r.spans} lang={lang} />}
          {!r.offline && r.rules.length > 0 && <RuleBars rules={r.rules} lang={lang} limit={3} />}
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-border-subtle px-6 py-4">
          {r.reportId !== null && (
            <Link
              to={`/report/${r.reportId}`}
              className={cn(buttonVariants({ variant: "secondary", size: "md" }))}
            >
              {t(lang, "openReport")}
              <ArrowRight aria-hidden="true" />
            </Link>
          )}
          <Button variant="ghost" icon={<RotateCcw />} onClick={onReset}>
            {t(lang, "classifyAnother")}
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}

/* ---- Bulk path ---- */

function CsvInput({
  lang,
  run,
  active,
  fileLoading,
  fileError,
  pendingFile,
  onPick,
  onChoose,
  onDemo,
}: {
  lang: Lang;
  run: UseIngestRun;
  active: boolean;
  fileLoading: boolean;
  fileError: string | null;
  pendingFile: { name: string; rows: number } | null;
  onPick: (f: File) => void;
  onChoose: () => void;
  onDemo: () => void;
}) {
  const [dragging, setDragging] = useState(false);
  const disabled = active || fileLoading;

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const f = e.dataTransfer.files?.[0];
    if (f) onPick(f);
  };

  return (
    <div className="flex flex-col gap-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center justify-center gap-4 rounded-md border-2 border-dashed px-6 py-12 text-center transition-colors duration-150",
          dragging
            ? "border-action-secondary-fg bg-action-secondary"
            : "border-border-default bg-surface-zebra",
          disabled && "opacity-60",
        )}
      >
        <span
          aria-hidden="true"
          className="grid size-14 place-items-center rounded-full bg-surface-card text-content-link shadow-sm ring-1 ring-border-subtle"
        >
          <FileSpreadsheet className="size-7" />
        </span>
        <div className="space-y-1">
          <p className="text-lg font-semibold text-content-primary">
            {dragging ? t(lang, "dropActive") : t(lang, "dropTitle")}
          </p>
          <p className="text-sm text-content-secondary">{t(lang, "dropOr")}</p>
        </div>
        <Button size="lg" icon={<Upload />} loading={fileLoading} onClick={onChoose} disabled={disabled}>
          {t(lang, "chooseCsv")}
        </Button>
        {pendingFile && !active && (
          <span className="font-mono text-xs text-content-secondary">
            {pendingFile.name} · {t(lang, "rowsSelected", { n: pendingFile.rows })}
          </span>
        )}
      </div>
      {fileError && (
        <p role="alert" className="text-sm font-medium text-status-danger">
          {fileError}
        </p>
      )}
      <p className="text-sm text-content-secondary">{t(lang, "csvAliasHint")}</p>

      <div className="flex flex-col gap-4 rounded-md border border-border-subtle p-4 sm:flex-row sm:items-center">
        <span
          aria-hidden="true"
          className="grid size-10 shrink-0 place-items-center rounded-md bg-action-secondary text-content-link"
        >
          <FlaskConical className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-content-primary">{t(lang, "demoTitle")}</p>
          <p className="text-sm text-content-secondary">{t(lang, "csvAliasHintSynthetic")}</p>
          <p className="mt-1 text-xs text-content-secondary">{tShared(lang, "demoDisclosure")}</p>
        </div>
        <Button variant="secondary" onClick={onDemo} disabled={active || run.phase === "starting"}>
          {t(lang, "demoRun")}
        </Button>
      </div>
    </div>
  );
}

function Kpi({ label, value, testId }: { label: string; value: React.ReactNode; testId: string }) {
  return (
    <div data-testid={testId} className="flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-card p-4">
      <span className="text-sm text-content-secondary">{label}</span>
      <span className="text-kpi-num text-content-primary">{value}</span>
    </div>
  );
}

function RunProgress({ lang, run }: { lang: Lang; run: UseIngestRun }) {
  return (
    <Card aria-live="polite">
      <CardHeader
        icon={<LoaderCircle className="animate-spin" />}
        title={t(lang, "runningTitle")}
        meta={`${t(lang, "elapsedLabel")} ${run.elapsedSeconds}s`}
      />
      {run.phase === "verifying" ? (
        <p className="text-base font-medium text-content-primary">{t(lang, "verifying")}</p>
      ) : (
        <>
          {run.counts.total !== null && (
            <p className="flex items-baseline gap-2">
              <span className="text-kpi-num text-content-primary">{run.counts.done.toLocaleString("en-IN")}</span>
              <span className="font-mono text-lg text-content-secondary">
                / {run.counts.total.toLocaleString("en-IN")}
              </span>
            </p>
          )}
          <Progress
            indeterminate={run.phase === "starting" || run.counts.total === null}
            value={run.counts.done}
            max={run.counts.total ?? 0}
            label={
              run.phase === "starting"
                ? t(lang, "statusStarting")
                : run.counts.total !== null
                  ? t(lang, "progressRows", { done: run.counts.done, total: run.counts.total })
                  : t(lang, "progressDoneSoFar", { done: run.counts.done })
            }
            detail={`${t(lang, "elapsedLabel")} ${run.elapsedSeconds}s${
              run.observedRate !== null ? ` · ${t(lang, "progressRate", { r: run.observedRate.toFixed(1) })}` : ""
            }${
              run.phase === "running"
                ? run.etaSeconds !== null
                  ? ` · ${t(lang, "progressEta", { s: run.etaSeconds })}`
                  : ` · ${t(lang, "progressMeasuring")}`
                : ""
            }`}
          />
        </>
      )}

      {!run.hasJobApi && run.phase === "running" && (
        <p className="text-sm text-content-secondary">{t(lang, "noJobApi")}</p>
      )}
      {run.cancelRequested && <p className="text-sm text-content-secondary">{t(lang, "cancelRequested")}</p>}
      {run.cancelSupported === false && (
        <p role="alert" className="text-sm text-content-secondary">
          {t(lang, "cancelUnavailable")}
        </p>
      )}

      {run.phase === "running" && (
        <div className="flex flex-wrap items-center gap-3 border-t border-border-subtle pt-4">
          {run.hasJobApi ? (
            <Button variant="secondary" size="sm" onClick={run.cancel} disabled={run.cancelRequested}>
              {t(lang, "cancelJob")}
            </Button>
          ) : (
            <>
              <Button variant="secondary" size="sm" onClick={run.cancel}>
                {t(lang, "abortWait")}
              </Button>
              <span className="text-sm text-content-secondary">{t(lang, "abortWaitHint")}</span>
            </>
          )}
        </div>
      )}
    </Card>
  );
}

interface ErrorRow {
  row: number;
  error: string;
}

const errorColumns = (lang: Lang): ColumnDef<ErrorRow>[] => [
  { id: "row", header: t(lang, "colRow"), width: 96, cell: (r) => <span className="font-mono">{r.row < 0 ? "—" : r.row}</span> },
  { id: "error", header: t(lang, "colError"), cell: (r) => <span className="whitespace-normal">{r.error}</span> },
];

function OutcomeCard({ lang, outcome, phase }: { lang: Lang; outcome: IngestOutcome; phase: string }) {
  const delta =
    outcome.countBefore !== null && outcome.countAfter !== null ? outcome.countAfter - outcome.countBefore : null;
  const done = phase !== "failed" && phase !== "cancelled";

  return (
    <motion.div {...ENTER}>
      <Card>
        <CardHeader
          title={t(lang, "outcomeTitle")}
          meta={outcome.mode === "sync-verified" ? t(lang, "verifiedByCount") : undefined}
          actions={<Chip tone={runTone(phase)}>{runWord(lang, phase, outcome.mode)}</Chip>}
        />

        {phase === "failed" && outcome.detail && (
          <p role="alert" className="text-base text-status-danger">
            {t(lang, "serverRejected", { detail: outcome.detail })}
          </p>
        )}

        <div className="grid grid-cols-2 gap-4">
          {outcome.received !== null && (
            <Kpi testId="kpi-received" label={t(lang, "receivedLabel")} value={outcome.received} />
          )}
          {outcome.accepted !== null && (
            <Kpi testId="kpi-accepted" label={t(lang, "acceptedLabel")} value={outcome.accepted} />
          )}
          {outcome.rejected !== null && (
            <Kpi testId="kpi-rejected" label={t(lang, "rejectedLabel")} value={outcome.rejected} />
          )}
          {outcome.skippedDuplicates !== null && outcome.skippedDuplicates > 0 && (
            <Kpi testId="kpi-duplicates" label={t(lang, "duplicatesLabel")} value={outcome.skippedDuplicates} />
          )}
          {outcome.mode === "sync-verified" && delta !== null && (
            <Kpi
              testId="kpi-net"
              label={t(lang, "netChange")}
              value={
                <span className="flex flex-wrap items-baseline gap-x-2">
                  +{delta}
                  <span className="text-sm font-normal text-content-secondary">
                    {outcome.countBefore} → {outcome.countAfter}
                  </span>
                </span>
              }
            />
          )}
        </div>

        {outcome.mode === "sync-verified" && (
          <p className="text-base text-content-primary">
            {t(lang, "timeoutTruth", {
              s: outcome.waitedSeconds ?? "?",
              before: outcome.countBefore ?? "?",
              after: outcome.countAfter ?? "?",
              delta: delta ?? 0,
            })}
          </p>
        )}
        {phase === "indeterminate" && outcome.mode !== "sync-verified" &&
          (outcome.detail === "poll-lost" ? (
            <p role="alert" className="text-base text-content-primary">
              {t(lang, "pollLost")}
            </p>
          ) : (
            <p role="alert" className="text-base text-content-primary">
              {t(lang, "timeoutNoChange", {
                s: outcome.waitedSeconds ?? "?",
                w: Math.round(VERIFY_WINDOW_MS / 1000),
              })}
            </p>
          ))}
        {outcome.idempotentReplay && <p className="text-base text-content-secondary">{t(lang, "replayNote")}</p>}

        {(outcome.rejected !== null || outcome.errors.length > 0) && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-content-primary">
              {t(lang, "errorsTitle", { n: outcome.rejected ?? outcome.errors.length })}
            </h4>
            {phase === "done" && outcome.rejected === 0 && outcome.errors.length === 0 ? (
              <p className="flex items-center gap-2 text-sm text-content-secondary">
                <CircleCheck aria-hidden="true" className="size-4 text-status-ok" />
                {t(lang, "noErrors")}
              </p>
            ) : outcome.errors.length > 0 ? (
              <div className="max-h-72 overflow-auto rounded-md border border-border-subtle">
                <Table columns={errorColumns(lang)} data={outcome.errors} density="compact" stickyHeader />
              </div>
            ) : null}
          </div>
        )}

        {done && (
          <div className="border-t border-border-subtle pt-4">
            <Link to="/queue" className={cn(buttonVariants({ variant: "secondary", size: "md" }))}>
              {t(lang, "openQueue")}
              <ArrowRight aria-hidden="true" />
            </Link>
          </div>
        )}
      </Card>
    </motion.div>
  );
}

export function IngestPage({
  lang,
  onIngested,
  syncBudgetMs,
}: {
  lang: Lang;
  /** Shell hook: the run changed server state — refetch feed/health. */
  onIngested?: () => void;
  /** Test hook only: client budget for the synchronous fallback (default 90 s).
   *  Lets e2e exercise the stop-waiting/verify flow against a slow real server
   *  without waiting 90 s. Production callers omit it. */
  syncBudgetMs?: number;
}) {
  const queryClient = useQueryClient();
  const run = useIngestRun(onIngested);
  const active = isBusy(run.phase);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const textRef = useRef<HTMLTextAreaElement | null>(null);
  const [tab, setTab] = useState("single");

  const [text, setText] = useState("");
  const [paste, setPaste] = useState<PasteState>({ status: "idle" });

  const [pendingFile, setPendingFile] = useState<{ name: string; csv: string; rows: number } | null>(null);
  const [fileDialogOpen, setFileDialogOpen] = useState(false);
  const [demoDialogOpen, setDemoDialogOpen] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);

  async function classifyText() {
    if (!text.trim() || paste.status === "busy") return;
    const submitted = text;
    setPaste({ status: "busy" });
    try {
      const p = await classify(submitted);
      if (p.report_id != null) {
        void queryClient.invalidateQueries({ queryKey: ["reports"] });
        void queryClient.invalidateQueries({ queryKey: qk.clusters });
        void queryClient.invalidateQueries({ queryKey: qk.health });
      }
      setPaste({
        status: "done",
        result: {
          reportId: p.report_id ?? null,
          text: submitted,
          score: p.sif_score,
          band: p.band ?? null,
          latencyMs: p.latency_ms,
          modelVersion: p.model_version,
          offline: p.model_version === "offline",
          gates: p.gate_states,
          spans: p.evidence_spans ?? [],
          rules: p.rules ?? [],
          at: Date.now(),
        },
      });
    } catch (e) {
      setPaste({ status: "error", message: e instanceof Error ? e.message : String(e) });
    }
  }

  function resetPaste() {
    setText("");
    setPaste({ status: "idle" });
    textRef.current?.focus();
  }

  function pickFile(file: File) {
    setFileError(null);
    setPendingFile(null);
    setFileLoading(true);
    void file.text().then((csv) => {
      const est = estimateCsvRows(csv);
      if (est.rows <= 0) {
        setFileError(t(lang, "fileEmpty"));
        return;
      }
      setPendingFile({ name: file.name, csv, rows: est.rows });
      setFileDialogOpen(true);
    }).catch(() => {
      setFileError(t(lang, "fileReadFailed"));
    }).finally(() => {
      setFileLoading(false);
    });
  }

  function startCsv(csv: string, source: string) {
    run.start(csv, source, syncBudgetMs !== undefined ? { budgetMs: syncBudgetMs } : undefined);
  }

  return (
    <section aria-label={t(lang, "ingestTitle")} className="space-y-8">
      <PageHeader eyebrow={t(lang, "ingestEyebrow")} title={t(lang, "ingestTitle")} description={t(lang, "ingestSub")} />

      <div className="grid items-start gap-5 lg:grid-cols-12">
        {/* Data in */}
        <div className="flex min-w-0 flex-col gap-3 lg:col-span-7">
          <p className="eyebrow mb-0">{t(lang, "inputHeading")}</p>
          <Card density="comfortable">
            <Tabs
              variant="segmented"
              items={[
                { value: "single", label: t(lang, "tabSingle"), icon: <ClipboardPaste /> },
                { value: "bulk", label: t(lang, "tabBulk"), icon: <FileSpreadsheet /> },
              ]}
              value={tab}
              onChange={setTab}
            />

          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            tabIndex={-1}
            onChange={(event) => {
              const f = event.target.files?.[0];
              if (f) pickFile(f);
              event.target.value = "";
            }}
          />

          {tab === "single" ? (
            <PasteInput
              lang={lang}
              text={text}
              setText={setText}
              busy={paste.status === "busy"}
              onRun={() => void classifyText()}
              textRef={textRef}
            />
          ) : (
            <CsvInput
              lang={lang}
              run={run}
              active={active}
              fileLoading={fileLoading}
              fileError={fileError}
              pendingFile={pendingFile}
              onPick={pickFile}
              onChoose={() => fileInput.current?.click()}
              onDemo={() => setDemoDialogOpen(true)}
            />
          )}
          </Card>
        </div>

        {/* Result out */}
        <div className="flex flex-col gap-3 lg:sticky lg:top-24 lg:col-span-5" aria-live="polite">
          <p className="eyebrow mb-0">{t(lang, "resultHeading")}</p>
          {tab === "single" ? (
            <>
              {active && (
                <div className="flex flex-wrap items-center gap-3 rounded-md border border-border-subtle bg-verdict-uncertain-chip px-4 py-3 text-sm text-content-primary">
                  <LoaderCircle aria-hidden="true" className="size-4 animate-spin text-content-link" />
                  <span className="flex-1">{t(lang, "bulkRunningElsewhere", { done: run.counts.done })}</span>
                  <Button variant="ghost" size="sm" onClick={() => setTab("bulk")}>
                    {t(lang, "viewProgress")}
                  </Button>
                </div>
              )}
              <PasteResultPanel lang={lang} state={paste} active={active} onReset={resetPaste} />
            </>
          ) : active ? (
            <RunProgress lang={lang} run={run} />
          ) : run.outcome ? (
            <OutcomeCard lang={lang} outcome={run.outcome} phase={run.phase} />
          ) : (
            <EmptyState
              icon={<FileSpreadsheet />}
              title={t(lang, "bulkIdle")}
              description={t(lang, "bulkIdleBody")}
              className="h-full min-h-[360px] rounded-lg border-solid bg-surface-card shadow-sm lg:min-h-[539px]"
            />
          )}
        </div>
      </div>

      {/* Confirm dialogs */}
      <Dialog
        open={fileDialogOpen}
        onOpenChange={setFileDialogOpen}
        title={t(lang, "csvDialogTitle", { name: pendingFile?.name ?? "" })}
        description={t(lang, "csvDialogBody", { n: pendingFile?.rows ?? 0 })}
        closeLabel={tShared(lang, "close")}
        children={null}
        footer={
          <>
            <Button
              onClick={() => {
                setFileDialogOpen(false);
                if (pendingFile) startCsv(pendingFile.csv, pendingFile.name);
              }}
            >
              {t(lang, "startIngest")}
            </Button>
            <Button variant="ghost" onClick={() => setFileDialogOpen(false)}>
              {t(lang, "dialogCancel")}
            </Button>
          </>
        }
      />
      <Dialog
        open={demoDialogOpen}
        onOpenChange={setDemoDialogOpen}
        title={t(lang, "demoDialogTitle")}
        description={t(lang, "demoDialogBody")}
        closeLabel={tShared(lang, "close")}
        children={null}
        footer={
          <>
            <Button
              onClick={() => {
                setDemoDialogOpen(false);
                setFileLoading(true);
                void fetchDemoCsv()
                  .then((csv) => {
                    setFileLoading(false);
                    const est = estimateCsvRows(csv);
                    startCsv(csv, `${t(lang, "demoButton")} (${est.rows} ${t(lang, "rowsStat")})`);
                  })
                  .catch(() => {
                    setFileLoading(false);
                    setFileError(t(lang, "demoUnavailable"));
                  });
              }}
            >
              {t(lang, "startIngest")}
            </Button>
            <Button variant="ghost" onClick={() => setDemoDialogOpen(false)}>
              {t(lang, "dialogCancel")}
            </Button>
          </>
        }
      />
    </section>
  );
}

export default IngestPage;
