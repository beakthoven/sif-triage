/* Ingest client — INGEST slice. Codes against the LANDED backend contract
 * (app/routes.py, observed this session against a RealOnnxClassifier server):
 *
 *   POST /api/ingest {csv|records, source}
 *     -> 200 IngestResult            small payloads (<= INGEST_SYNC_MAX_ROWS)
 *                                    and ALL idempotent replays: synchronous
 *                                    final result, no row-level progress.
 *     -> 202 IngestJobAccepted       larger payloads: {job_id, status:"queued",
 *                                    poll:"/api/ingest/{job_id}", received,
 *                                    total, rejected}
 *   GET  /api/ingest/{job_id}
 *     -> {job_id, status:"queued"|"running"|"done"|"error", received, total,
 *         done, accepted, rejected, skipped_duplicates, errors[], report_ids,
 *         detail}  (detail non-null only on error: whole batch rolled back).
 *     404 = unknown id / evicted / server restarted — re-POST is safe.
 *   DELETE /api/ingest/{job_id}     requests cancellation before commit;
 *         non-2xx means cancellation was not confirmed.
 *
 * A timed-out POST does not prove failure. The global report count can show
 * database changes, but only a batch response confirms this import's result.
 */
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

/** Client budget for the synchronous POST window (covers the 200-completes-
 * inline case; a >100-row payload answers 202 in ms). "Stop waiting" aborts
 * earlier via the explicit button. */
export const SYNC_BUDGET_MS = 90_000;

/** Window for observing database count changes after an interrupted wait. */
export const VERIFY_WINDOW_MS = 20_000;

const INGEST_URL = `${BASE}/api/ingest`;
const HEALTH_URL = `${BASE}/api/health`;

export interface IngestJobError {
  row: number;
  error: string;
}

/** Normalised snapshot of one ingest job (wire shape tolerated). */
export interface IngestJobStatus {
  jobId: string;
  phase: "running" | "done" | "cancelled" | "failed";
  rawStatus: string;
  done: number;
  total: number | null;
  accepted: number | null;
  rejected: number | null;
  skippedDuplicates: number | null;
  idempotentReplay: boolean;
  detail: string | null;
  errors: IngestJobError[];
}

/** IngestResult subset the UI shows (200-synchronous path). */
export interface SyncIngestResult {
  received: number | null;
  accepted: number;
  rejected: number;
  skippedDuplicates: number | null;
  idempotentReplay: boolean;
  errors: IngestJobError[];
}

export type StartIngestOutcome =
  | { kind: "sync"; result: SyncIngestResult }
  | { kind: "job"; jobId: string; total: number; received: number; rejected: number };

const TERMINAL_OK = new Set(["done", "complete", "completed", "finished", "success", "succeeded", "ok"]);
const TERMINAL_CANCELLED = new Set(["cancelled", "canceled", "cancel"]);
const TERMINAL_FAILED = new Set(["failed", "error", "failure"]);

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function normalizeErrors(v: unknown): IngestJobError[] {
  if (!Array.isArray(v)) return [];
  return v
    .map((e): IngestJobError | null => {
      if (typeof e === "string") return { row: -1, error: e };
      if (e && typeof e === "object") {
        const o = e as Record<string, unknown>;
        const row = num(o.row) ?? num(o.index) ?? num(o.line) ?? -1;
        const msg = o.error ?? o.message ?? o.detail ?? o.reason;
        if (typeof msg === "string") return { row, error: msg };
      }
      return null;
    })
    .filter((e): e is IngestJobError => e !== null);
}

export class ServerRejectionError extends Error {
  public readonly detail: string;

  constructor(detail: string) {
    super(`server rejected ingest: ${detail}`);
    this.detail = detail;
  }
}

async function fetchJsonOrAbort(
  url: string,
  init: RequestInit,
): Promise<{ status: number; body: unknown }> {
  const res = await fetch(url, { ...init });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const j = body as { detail?: unknown } | null;
    const detail =
      j && typeof j.detail === "string"
        ? j.detail
        : `${res.status} ${res.statusText} on ${new URL(url, location.href).pathname}`;
    throw new ServerRejectionError(detail);
  }
  return { status: res.status, body };
}

/** POST /api/ingest. The server decides: <=INGEST_SYNC_MAX_ROWS (and every
 *  idempotent replay) completes synchronously with the final IngestResult;
 *  larger payloads return 202 + a job id to poll. Throws ServerRejectionError
 *  on 4xx/5xx (422 = payload rejected; 500 = rolled back, nothing stored) and
 *  an AbortError when the budget elapses or `signal` aborts. Without a batch
 *  response, neither completion nor failure is confirmed. */
export async function startIngest(
  csv: string,
  opts?: { budgetMs?: number; signal?: AbortSignal },
): Promise<StartIngestOutcome> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), opts?.budgetMs ?? SYNC_BUDGET_MS);
  const onExternalAbort = () => ctl.abort();
  opts?.signal?.addEventListener("abort", onExternalAbort);
  try {
    const { status, body } = await fetchJsonOrAbort(
      INGEST_URL,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv, source: "dashboard" }),
        signal: ctl.signal,
      },
    );
    const o = body as Record<string, unknown>;
    if (status === 202 && typeof o?.job_id === "string") {
      return {
        kind: "job",
        jobId: o.job_id,
        total: num(o.total) ?? 0,
        received: num(o.received) ?? 0,
        rejected: num(o.rejected) ?? 0,
      };
    }
    return {
      kind: "sync",
      result: {
        received: num(o?.received),
        accepted: num(o?.accepted) ?? 0,
        rejected: num(o?.rejected) ?? 0,
        skippedDuplicates: num(o?.skipped_duplicates) ?? num(o?.skippedDuplicates),
        idempotentReplay: o?.idempotent_replay === true,
        errors: normalizeErrors(o?.errors),
      },
    };
  } finally {
    clearTimeout(timer);
    opts?.signal?.removeEventListener("abort", onExternalAbort);
  }
}

/** Poll one job. null = poll failed (network hiccup, 404 eviction, restart).
 *  404 means re-POST is safe — the caller surfaces that after it gives up. */
export async function getIngestJob(jobId: string): Promise<IngestJobStatus | null> {
  try {
    const res = await fetch(`${INGEST_URL}/${encodeURIComponent(jobId)}`, { method: "GET" });
    if (!res.ok) return null;
    const o = (await res.json()) as Record<string, unknown>;
    const done = num(o.done) ?? num(o.processed) ?? 0;
    const total = num(o.total);
    const accepted = num(o.accepted);
    const rejected = num(o.rejected);
    const hasResultCounts = accepted !== null || rejected !== null;
    const s = typeof o.status === "string" ? o.status : "";
    const finished = hasResultCounts && done >= (total ?? Number.MAX_SAFE_INTEGER);
    const phase: IngestJobStatus["phase"] = TERMINAL_CANCELLED.has(s.toLowerCase())
      ? "cancelled"
      : TERMINAL_FAILED.has(s.toLowerCase())
        ? "failed"
        : TERMINAL_OK.has(s.toLowerCase())
          ? "done"
          : finished
            ? "done"
            : "running";
    return {
      jobId,
      phase,
      rawStatus: s,
      done,
      total,
      accepted,
      rejected,
      skippedDuplicates: num(o.skipped_duplicates) ?? num(o.skippedDuplicates),
      idempotentReplay: o.idempotent_replay === true,
      detail: typeof o.detail === "string" ? o.detail : null,
      errors: normalizeErrors(o.errors),
    };
  } catch {
    return null;
  }
}

/** Request cancellation; polling confirms the terminal job status. */
export async function cancelIngestJob(jobId: string): Promise<boolean> {
  try {
    const res = await fetch(`${INGEST_URL}/${encodeURIComponent(jobId)}`, { method: "DELETE" });
    return res.ok;
  } catch {
    return false;
  }
}

/** GET /api/health -> live stored-report count (null when unreachable). */
export async function getReportCount(): Promise<number | null> {
  try {
    const res = await fetch(HEALTH_URL, { method: "GET" });
    if (!res.ok) return null;
    const o = (await res.json()) as Record<string, unknown>;
    return num(o.n_reports);
  } catch {
    return null;
  }
}

/** GET /live_ingest_500.csv — the synthetic demo register extract shipped as a
 *  static asset (same file the old density beat uploaded). Throws when absent. */
export async function fetchDemoCsv(timeoutMs = 5_000): Promise<string> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}/live_ingest_500.csv`, { signal: ctl.signal });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} on /live_ingest_500.csv`);
    return await res.text();
  } finally {
    clearTimeout(timer);
  }
}

/* ---- Client-side CSV row estimate (confirm-dialog only; the server's
 *  validated row list is authoritative). RFC4180-lite: quoted fields may
 *  contain newlines/commas; "" is an escaped quote. ponytail ceiling: no
 *  BOM/quoting-strictness handling beyond that. ---- */
export function estimateCsvRows(csv: string): { rows: number; columns: string[] } {
  let inQuotes = false;
  let pending = false; // any field content seen since the last record end
  let firstRecord = true;
  let records = 0;
  const columns: string[] = [];
  let field = "";
  const pushField = () => {
    if (firstRecord) columns.push(field.trim());
    field = "";
  };
  const endRecord = () => {
    pushField();
    records += 1;
    firstRecord = false;
    pending = false;
  };
  for (let i = 0; i < csv.length; i++) {
    const c = csv[i];
    if (inQuotes) {
      if (c === '"') {
        if (csv[i + 1] === '"') i++;
        else inQuotes = false;
      } else {
        field += c;
      }
      pending = true;
      continue;
    }
    if (c === '"') {
      inQuotes = true;
      pending = true;
    } else if (c === ",") {
      pushField();
      pending = true;
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && csv[i + 1] === "\n") i++;
      if (pending) endRecord();
    } else {
      field += c;
      pending = true;
    }
  }
  if (pending) endRecord();
  return { rows: Math.max(0, records - 1), columns };
}