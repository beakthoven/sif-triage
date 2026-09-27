/* Ingest run state machine — INGEST slice.
 *
 * One active run at a time. Truth rules enforced here:
 * - Progress numbers come ONLY from server counts (GET /api/ingest/{id}, the
 *   202-job path) or the final IngestResult — never from a timer. When the
 *   payload runs synchronously (<= INGEST_SYNC_MAX_ROWS, or an idempotent
 *   replay), the display shows elapsed time only and says so.
 * - "Cancel" is confirmed only by a terminal job status. If the request fails,
 *   polling continues without claiming the import stopped.
 * - "Stop waiting" aborts the response wait, not server processing. A rising
 *   database count cannot identify this batch or prove completion; without a
 *   batch result the outcome remains unconfirmed. Identical uploads are
 *   idempotent, so retrying retrieves the result without a second import.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { qk } from "@/lib/api";
import {
  cancelIngestJob,
  getIngestJob,
  getReportCount,
  ServerRejectionError,
  startIngest,
  VERIFY_WINDOW_MS,
  type IngestJobError,
} from "./ingest-api";

const POLL_MS = 1_000;
const VERIFY_POLL_MS = 2_500;
const MAX_POLL_FAILURES = 5;

export type IngestPhase =
  | "idle"
  | "starting"
  | "running"
  | "verifying"
  | "done"
  | "cancelled"
  | "failed"
  | "indeterminate";

export type IngestOutcomeMode =
  | "job" // 202 job: server-reported counts
  | "sync" // 200 synchronous IngestResult
  | "sync-verified" // wait aborted; database count increased, batch result unknown
  | "sync-unconfirmed"; // wait aborted; outcome could not be confirmed

export interface IngestOutcome {
  mode: IngestOutcomeMode;
  received: number | null;
  accepted: number | null;
  rejected: number | null;
  skippedDuplicates: number | null;
  idempotentReplay: boolean;
  errors: IngestJobError[];
  countBefore: number | null;
  countAfter: number | null;
  waitedSeconds: number | null;
  detail: string | null;
  cancelledAfterDone: number | null;
}

export interface IngestHistoryEntry extends IngestOutcome {
  id: number;
  source: string;
  startedAt: number;
  endedAt: number;
  phase: Exclude<IngestPhase, "idle" | "starting" | "running" | "verifying">;
}

export interface IngestCounts {
  done: number;
  total: number | null;
  accepted: number | null;
  rejected: number | null;
  skippedDuplicates: number | null;
  idempotentReplay: boolean;
  errors: IngestJobError[];
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const TERMINAL_PHASES: IngestPhase[] = ["done", "cancelled", "failed", "indeterminate"];

export interface UseIngestRun {
  phase: IngestPhase;
  source: string | null;
  elapsedSeconds: number;
  counts: IngestCounts;
  hasJobApi: boolean;
  cancelRequested: boolean;
  cancelSupported: boolean | null;
  outcome: IngestOutcome | null;
  history: IngestHistoryEntry[];
  start: (csv: string, source: string, opts?: { budgetMs?: number }) => void;
  cancel: () => void;
  /** Observed classification rate (rows/s) from real counts + wall clock. */
  observedRate: number | null;
  etaSeconds: number | null;
}

export function useIngestRun(onTerminal?: () => void): UseIngestRun {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<IngestPhase>("idle");
  const [source, setSource] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [counts, setCounts] = useState<IngestCounts>({
    done: 0,
    total: null,
    accepted: null,
    rejected: null,
    skippedDuplicates: null,
    idempotentReplay: false,
    errors: [],
  });
  const [hasJobApi, setHasJobApi] = useState(false);
  const [cancelRequested, setCancelRequested] = useState(false);
  const [cancelSupported, setCancelSupported] = useState<boolean | null>(null);
  const [outcome, setOutcome] = useState<IngestOutcome | null>(null);
  const [history, setHistory] = useState<IngestHistoryEntry[]>([]);

  const startedAtRef = useRef<number | null>(null);
  const jobIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const phaseRef = useRef<IngestPhase>("idle");
  const countBeforeRef = useRef<number | null>(null);

  const setPhaseBoth = (p: IngestPhase) => {
    phaseRef.current = p;
    setPhase(p);
  };

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(
    () => () => {
      clearTimer();
      abortRef.current?.abort();
    },
    [],
  );

  // Elapsed-time ticker — wall clock only, never drives the progress bar.
  useEffect(() => {
    if (phase !== "starting" && phase !== "running" && phase !== "verifying") return;
    const i = setInterval(() => {
      if (startedAtRef.current) {
        setElapsedSeconds(Math.max(0, Math.round((Date.now() - startedAtRef.current) / 1000)));
      }
    }, 1_000);
    return () => clearInterval(i);
  }, [phase]);

  const finish = useCallback(
    (
      p: Exclude<IngestPhase, "idle" | "starting" | "running" | "verifying">,
      o: IngestOutcome,
      src: string,
      startedAt: number,
    ) => {
      clearTimer();
      jobIdRef.current = null;
      abortRef.current = null;
      setCounts((c) => ({
        ...c,
        accepted: o.accepted ?? c.accepted,
        rejected: o.rejected ?? c.rejected,
        skippedDuplicates: o.skippedDuplicates ?? c.skippedDuplicates,
        idempotentReplay: o.idempotentReplay || c.idempotentReplay,
        errors: o.errors.length > 0 ? o.errors : c.errors,
      }));
      setOutcome(o);
      setPhaseBoth(p);
      setHistory((h) => [
        { ...o, id: Date.now(), source: src, startedAt, endedAt: Date.now(), phase: p },
        ...h,
      ]);
      if ((o.accepted !== null && o.accepted > 0) || o.mode === "sync-verified") {
        void queryClient.invalidateQueries({ queryKey: ["reports"] });
        void queryClient.invalidateQueries({ queryKey: qk.clusters });
        void queryClient.invalidateQueries({ queryKey: qk.health });
      }
      onTerminal?.();
    },
    [onTerminal, queryClient],
  );

  const start = useCallback(
    (csv: string, label: string, opts?: { budgetMs?: number }) => {
      if (!TERMINAL_PHASES.includes(phaseRef.current) && phaseRef.current !== "idle") return;
      const startedAt = Date.now();
      startedAtRef.current = startedAt;
      countBeforeRef.current = null;
      jobIdRef.current = null;
      setSource(label);
      setElapsedSeconds(0);
      setCancelRequested(false);
      setCancelSupported(null);
      setOutcome(null);
      setCounts({
        done: 0,
        total: null,
        accepted: null,
        rejected: null,
        skippedDuplicates: null,
        idempotentReplay: false,
        errors: [],
      });
      setPhaseBoth("starting");

      void (async () => {
        countBeforeRef.current = await getReportCount();
        const ctl = new AbortController();
        abortRef.current = ctl;
        setPhaseBoth("running");
        try {
          const started = await startIngest(csv, { budgetMs: opts?.budgetMs, signal: ctl.signal });
          if (started.kind === "sync") {
            // Synchronous IngestResult — final outcome, no row progress existed.
            setHasJobApi(false);
            finish(
              "done",
              {
                mode: "sync",
                received: started.result.received,
                accepted: started.result.accepted,
                rejected: started.result.rejected,
                skippedDuplicates: started.result.skippedDuplicates,
                idempotentReplay: started.result.idempotentReplay,
                errors: started.result.errors,
                countBefore: countBeforeRef.current,
                countAfter: null,
                waitedSeconds: null,
                detail: null,
                cancelledAfterDone: null,
              },
              label,
              startedAt,
            );
            return;
          }
          // ---- 202 job path: authoritative row counts from the server ----
          setHasJobApi(true);
          jobIdRef.current = started.jobId;
          setCounts((c) => ({ ...c, total: started.total, rejected: started.rejected ?? null }));
          let consecutiveFailures = 0;
          const tick = async (): Promise<void> => {
            if (!jobIdRef.current || TERMINAL_PHASES.includes(phaseRef.current)) return;
            const s = await getIngestJob(started.jobId);
            if (s === null) {
              consecutiveFailures += 1;
              if (consecutiveFailures >= MAX_POLL_FAILURES) {
                finish(
                  "indeterminate",
                  {
                    mode: "job",
                    received: started.received,
                    accepted: null,
                    rejected: started.rejected,
                    skippedDuplicates: null,
                    idempotentReplay: false,
                    errors: [],
                    countBefore: countBeforeRef.current,
                    countAfter: null,
                    waitedSeconds: null,
                    detail: "poll-lost",
                    cancelledAfterDone: null,
                  },
                  label,
                  startedAt,
                );
                return;
              }
            } else {
              consecutiveFailures = 0;
              setCounts({
                done: s.done,
                total: s.total ?? started.total,
                accepted: s.accepted,
                rejected: s.rejected ?? started.rejected,
                skippedDuplicates: s.skippedDuplicates,
                idempotentReplay: s.idempotentReplay,
                errors: s.errors,
              });
              if (s.phase !== "running") {
                finish(
                  s.phase === "failed" ? "failed" : s.phase === "cancelled" ? "cancelled" : "done",
                  {
                    mode: "job",
                    received: started.received,
                    accepted: s.accepted,
                    rejected: s.rejected ?? started.rejected,
                    skippedDuplicates: s.skippedDuplicates,
                    idempotentReplay: s.idempotentReplay,
                    errors: s.errors,
                    countBefore: countBeforeRef.current,
                    countAfter: null,
                    waitedSeconds: null,
                    detail: s.detail,
                    cancelledAfterDone: s.phase === "cancelled" ? s.done : null,
                  },
                  label,
                  startedAt,
                );
                return;
              }
            }
            timerRef.current = setTimeout(() => void tick(), POLL_MS);
          };
          timerRef.current = setTimeout(() => void tick(), POLL_MS);
        } catch (e) {
          const aborted =
            ctl.signal.aborted || (e instanceof DOMException && e.name === "AbortError");
          if (aborted) {
            setHasJobApi(false);
            setPhaseBoth("verifying");
            const before = countBeforeRef.current;
            const deadline = Date.now() + VERIFY_WINDOW_MS;
            let after: number | null = null;
            while (Date.now() < deadline) {
              await sleep(VERIFY_POLL_MS);
              after = await getReportCount();
              if (before !== null && after !== null && after > before) break;
            }
            finish(
              "indeterminate",
              {
                mode: before !== null && after !== null && after > before ? "sync-verified" : "sync-unconfirmed",
                received: null,
                accepted: null,
                rejected: null,
                skippedDuplicates: null,
                idempotentReplay: false,
                errors: [],
                countBefore: before,
                countAfter: after,
                waitedSeconds: Math.round((Date.now() - startedAt) / 1000),
                detail: null,
                cancelledAfterDone: null,
              },
              label,
              startedAt,
            );
          } else if (e instanceof ServerRejectionError) {
            finish(
              "failed",
              {
                mode: "sync",
                received: null,
                accepted: null,
                rejected: null,
                skippedDuplicates: null,
                idempotentReplay: false,
                errors: [],
                countBefore: countBeforeRef.current,
                countAfter: null,
                waitedSeconds: null,
                detail: e.detail,
                cancelledAfterDone: null,
              },
              label,
              startedAt,
            );
          } else {
            finish(
              "failed",
              {
                mode: "sync",
                received: null,
                accepted: null,
                rejected: null,
                skippedDuplicates: null,
                idempotentReplay: false,
                errors: [],
                countBefore: countBeforeRef.current,
                countAfter: null,
                waitedSeconds: null,
                detail: e instanceof Error ? e.message : String(e),
                cancelledAfterDone: null,
              },
              label,
              startedAt,
            );
          }
        }
      })();
    },
    [finish],
  );

  const cancel = useCallback(() => {
    if (jobIdRef.current) {
      setCancelRequested(true);
      void (async () => {
        const ok = await cancelIngestJob(jobIdRef.current as string);
        if (!ok) {
          setCancelRequested(false);
          setCancelSupported(false);
          // Keep polling: the server has no cancel; the run finishes truthfully.
        } else {
          setCancelSupported(true);
        }
      })();
    } else {
      // Synchronous path: stop waiting -> the verifying flow proves the outcome.
      abortRef.current?.abort();
    }
  }, []);

  // Observed rate + ETA — derived from real counts and wall clock only.
  const observedRate = counts.done >= 1 && elapsedSeconds >= 1 ? counts.done / elapsedSeconds : null;
  const etaSeconds =
    counts.total !== null && counts.total > counts.done && observedRate && observedRate > 0
      ? Math.ceil((counts.total - counts.done) / observedRate)
      : null;

  return {
    phase,
    source,
    elapsedSeconds,
    counts,
    hasJobApi,
    cancelRequested,
    cancelSupported,
    outcome,
    history,
    start,
    cancel,
    observedRate,
    etaSeconds,
  };
}