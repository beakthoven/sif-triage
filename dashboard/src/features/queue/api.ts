/* Queue data loader. Reads GET /api/reports with offset paging — limit ≤ 1000
 * is the server contract (app/routes.py list_reports, Query le=1000) — until a
 * short page ends the register. NO mock fallback: on any failure the caller
 * renders an error state instead of partial or fabricated rows.
 *
 * Deliberate ceiling: sort/search/filter run client-side over the full
 * register because /api/reports exposes only limit+offset (verified
 * routes.py:227-233 this session); server-side query params would need a
 * routes.py change (STORE's slice). If those land, swap this module's loader
 * and drop the client filter pass.
 *
 * band / verdict_stability / score_spread are server-owned A-series fields —
 * optional on the wire; absence is rendered "not measured". verdict_stability
 * is an agreement fraction; the unstable label is derived at the UI boundary. */

import type { Band, ClustersOut } from "@/lib/types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");
const TIMEOUT_MS = 30_000;
const RETRY_DELAY_MS = 1000;
const BATCH = 1000;
const CLUSTERS_URL = `${BASE}/api/clusters?min_cos=0.91`;

/** Mirror of the /api/reports wire shape (app/schemas.py StoredReport). */
export interface QueueWireRow {
  id: number;
  report: {
    text: string;
    date: string | null;
    site: string | null;
    activity: string | null;
    contractor: string | null;
    source: string;
  };
  prediction: {
    sif_score: number;
    band?: Band | null;
    verdict_stability?: number | null;
    rule_probs: Record<string, number>;
    gate_states: { name: string; triggered: boolean; detail: string; action: string }[];
  } | null;
  created_at: string;
}

/** Flattened queue row: every field a column, filter, or chip renders. */
export interface QueueRow {
  id: number;
  text: string;
  site: string | null;
  activity: string | null;
  contractor: string | null;
  /** The report's own event date, when the wire carries one (mostly null in
   *  the demo register — the UI never passes the ingestion date off as it). */
  eventDate: string | null;
  ingestedDate: string;
  /** Date shown in the Date column: event date when present, else ingestion. */
  displayDate: string;
  dateIsIngested: boolean;
  /** null when the stored row has no prediction — rendered "Not scored". */
  score: number | null;
  /** Server-owned review-priority band (A4). null = not banded on the wire. */
  band: Band | null;
  /** Triggered gray-action gates — the honest per-row review flags. */
  grayGates: { name: string; detail: string }[];
  nearDup: boolean;
  ruleProbs: Record<string, number>;
}

class TransientQueueError extends Error {}

function waitForRetry(signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    signal?.throwIfAborted();
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal?.reason);
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, RETRY_DELAY_MS);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

async function fetchBatch(offset: number, signal?: AbortSignal): Promise<QueueWireRow[]> {
  for (let attempt = 0; ; attempt++) {
    signal?.throwIfAborted();
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
    const onOuterAbort = () => ctl.abort();
    signal?.addEventListener("abort", onOuterAbort, { once: true });
    try {
      const res = await fetch(`${BASE}/api/reports?limit=${BATCH}&offset=${offset}`, {
        signal: ctl.signal,
      });
      if (!res.ok) {
        const message = `${res.status} ${res.statusText} on /api/reports?offset=${offset}`;
        if (res.status === 408 || res.status === 429 || res.status >= 500) {
          throw new TransientQueueError(message);
        }
        throw new Error(message);
      }
      const batch = (await res.json()) as QueueWireRow[];
      signal?.throwIfAborted();
      return batch;
    } catch (err) {
      signal?.throwIfAborted();
      if (attempt > 0 || !(err instanceof TransientQueueError || err instanceof TypeError || ctl.signal.aborted)) {
        throw err;
      }
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onOuterAbort);
    }
    await waitForRetry(signal);
  }
}

function adaptRow(w: QueueWireRow): QueueRow {
  return {
    id: w.id,
    text: w.report.text,
    site: w.report.site,
    activity: w.report.activity,
    contractor: w.report.contractor,
    eventDate: w.report.date,
    ingestedDate: w.created_at.slice(0, 10),
    displayDate: w.report.date ?? w.created_at.slice(0, 10),
    dateIsIngested: w.report.date == null,
    score: w.prediction ? w.prediction.sif_score : null,
    band: w.prediction?.band ?? null,
    grayGates: (w.prediction?.gate_states ?? [])
      .filter((g) => g.triggered && g.action === "gray")
      .map((g) => ({ name: g.name, detail: g.detail })),
    nearDup: (w.prediction?.gate_states ?? []).some(
      (g) => g.name === "near_dup" && g.triggered,
    ),
    ruleProbs: w.prediction?.rule_probs ?? {},
  };
}

/** Fetch the server's star-cluster grouping; never infer groups client-side. */
export async function fetchQueueClusters(signal?: AbortSignal): Promise<ClustersOut> {
  const response = await fetch(CLUSTERS_URL, { signal });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} on /api/clusters`);
  }
  return (await response.json()) as ClustersOut;
}

/** Page the whole register off the server. Throws after a failed page's retry. */
export async function fetchQueueRows(
  signal?: AbortSignal,
  onProgress?: (loaded: number) => void,
): Promise<QueueRow[]> {
  const all: QueueRow[] = [];
  for (let offset = 0; ; offset += BATCH) {
    const batch = await fetchBatch(offset, signal);
    for (const w of batch) all.push(adaptRow(w));
    onProgress?.(all.length);
    if (batch.length < BATCH) return all;
  }
}