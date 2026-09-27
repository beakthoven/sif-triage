/* Slice-local read-only client for the analytics surface. The app-wide client
 * (@/lib/api, SHELL-owned) has no paginated all-reports fetch and no min-n
 * parameter on patterns, which the time series and the pattern floor need.
 * Read-only GETs against the same-origin /api (the FastAPI process serves the
 * dist; the vite dev/preview proxy forwards /api). NO mock fallback: an
 * analytics surface whose value is truthful numbers must not paint fabricated
 * numbers first (discovery F6) — failures surface as an error state. */

import type { PatternKind } from "@/lib/types";
import { flagThreshold, parseReportDate, setFlagThreshold } from "./stats";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");
const TIMEOUT_MS = 3500;
const REPORT_TIMEOUT_MS = 30_000;
const RETRY_DELAY_MS = 1000;
/** Server page size cap is 1000 rows per call (app/routes.py list_reports
 * Query le=1000, verified 2026-09-25). ponytail: 10k cap bounds the walk; a
 * dedicated aggregate endpoint on the backend removes the need entirely. */
const PAGE_SIZE = 1000;
const MAX_REPORTS = 10_000;

class TransientPageError extends Error {}

async function req<T>(path: string, timeoutMs = TIMEOUT_MS, retryPage = false): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeoutMs);
    try {
      const res = await fetch(`${BASE}${path}`, { signal: ctl.signal });
      if (!res.ok) {
        const message = `${res.status} ${res.statusText} on ${path}`;
        if (retryPage && (res.status === 408 || res.status === 429 || res.status >= 500)) {
          throw new TransientPageError(message);
        }
        throw new Error(message);
      }
      return (await res.json()) as T;
    } catch (err) {
      if (!retryPage || attempt > 0 || !(err instanceof TransientPageError || err instanceof TypeError || ctl.signal.aborted)) {
        throw err;
      }
    } finally {
      clearTimeout(timer);
    }
    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
  }
}

/* ---- /api/density (server-aggregated; n_flagged uses the server threshold) ---- */

export interface DensityWire {
  key: string;
  n_reports: number;
  n_flagged: number;
  sif_rate: number;
  mean_score: number;
}

export async function fetchDensity(
  by: "site" | "activity" | "contractor",
  dateRange?: { from: string | null; to: string | null },
): Promise<DensityWire[]> {
  const params = new URLSearchParams({ by });
  if (dateRange?.from) params.set("date_from", dateRange.from);
  if (dateRange?.to) params.set("date_to", dateRange.to);
  return req<DensityWire[]>(`/api/density?${params.toString()}`);
}

/* ---- /api/patterns (kind, min_n, limit ≤ 100 server-side) ---- */

export interface PatternWire {
  activity: string;
  site: string | null;
  barrier: string | null;
  rule: string | null;
  n: number;
  sif_rate: number;
  lift: number;
  ci_low: number;
  ci_high: number;
}

export async function fetchPatterns(
  kind: PatternKind,
  minN: number,
  limit = 100,
): Promise<PatternWire[]> {
  return req<PatternWire[]>(`/api/patterns?kind=${kind}&min_n=${minN}&limit=${limit}`);
}

/* ---- /api/metrics/summary — threshold cross-check ---- */

export interface MetricsWire {
  n_reports: number;
  n_flagged: number;
  flag_rate: number;
  flag_threshold?: number | null;
}

export async function fetchMetrics(): Promise<MetricsWire> {
  const wire = await req<MetricsWire>("/api/metrics/summary");
  // Bind the server's operating point before the report walk computes flags.
  setFlagThreshold(wire.flag_threshold);
  return wire;
}

/* ---- /api/reports paged — the only source of per-report dates + scores today.
 * The trend is computed client-side because no server endpoint aggregates by
 * period (verified 2026-09-25 via /openapi.json). Returns dated + undated
 * summaries; text is discarded immediately to keep memory flat. ---- */

export interface ReportSummary {
  id: number;
  dateIso: string | null;
  score: number;
  flagged: boolean;
}

export interface ReportsWalk {
  reports: ReportSummary[];
  truncated: boolean;
}

export async function fetchAllReports(
  onProgress?: (loaded: number) => void,
): Promise<ReportsWalk> {
  const out: ReportSummary[] = [];
  for (let offset = 0; offset < MAX_REPORTS; offset += PAGE_SIZE) {
    const rows = await req<
      {
        id: number;
        report: { date: string | null };
        prediction: { sif_score: number } | null;
      }[]
    >(`/api/reports?limit=${PAGE_SIZE}&offset=${offset}`, REPORT_TIMEOUT_MS, true);
    for (const r of rows) {
      const score = r.prediction?.sif_score ?? Number.NEGATIVE_INFINITY;
      out.push({
        id: r.id,
        dateIso: parseReportDate(r.report.date),
        score,
        flagged: score >= flagThreshold(),
      });
    }
    onProgress?.(out.length);
    if (rows.length < PAGE_SIZE) return { reports: out, truncated: false };
  }
  return { reports: out, truncated: true };
}