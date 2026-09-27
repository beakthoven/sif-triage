/* DECISIONS data layer — the append-only audit log, CAPA closure state, and
 * the reviewer identity, all local to this feature slice (lib/** is SHELL's).
 *
 * The audit view reads the full wire log, including rationale, write order
 * and legacy rows. Writes reuse the shared postReview client. */
import { DEMO_MODE, getReport, postReview } from "@/lib/api";
import { REVIEWER_KEY } from "@/lib/identity";
import { OVERRIDES } from "@/lib/mock";
import type { OverrideOut } from "@/lib/types";

/* ---- wire shape: app/schemas.py StoredOverride ---- */

export interface AuditRow {
  id: number;
  report_id: number;
  field: string;
  old_value: string | null;
  new_value: string;
  labeler: string;
  rationale: string | null;
  source: "override" | "blind_gold";
  created_at: string;
}

export interface AuditSnapshot {
  rows: AuditRow[];
  /** True when the API was unreachable and rows are the demo fixtures. */
  offline: boolean;
}

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");
const TIMEOUT_MS = 30_000;

/** GET /api/review — full append-only log WITH rationale. Live failures throw
 * so the caller can offer retry instead of presenting sample decisions. */
export async function fetchAuditRows(): Promise<AuditSnapshot> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE}/api/review`, { signal: ctl.signal });
    if (!res.ok) throw new Error(`${res.status} on /api/review`);
    const rows = (await res.json()) as AuditRow[];
    return { rows, offline: false };
  } catch (error) {
    if (!DEMO_MODE) throw error;
    return {
      rows: OVERRIDES.map((o: OverrideOut) => ({
        ...o,
        rationale: null,
        created_at: o.ts,
      })),
      offline: true,
    };
  } finally {
    clearTimeout(timer);
  }
}

export type AmendField = "sif_label" | "rules" | "notes";

export interface AmendInput {
  reportId: number;
  field: AmendField;
  oldValue: string | null;
  newValue: string;
  labeler: string;
  rationale: string;
}

/** POST /api/review via the lib client (it already forwards labeler and
 *  rationale). The backend is deliberately append-only: this APPENDS a row
 *  that supersedes the earlier one; GET /review/export collapses latest-wins
 *  and records the supersedes lineage. Throws when offline. */
export async function amendDecision(input: AmendInput): Promise<void> {
  await postReview({
    report_id: input.reportId,
    field: input.field,
    old_value: input.oldValue,
    new_value: input.newValue,
    labeler: input.labeler,
    rationale: input.rationale,
  });
}

/** GET /api/review/export — compliance NDJSON, latest-wins per
 *  (report_id, field) with exact-dup collapse + supersedes ids (storage.py).
 *  Downloads as a file; returns the line count. Throws when offline. */
export async function exportNdjson(): Promise<number> {
  const res = await fetch(`${BASE}/api/review/export`);
  if (!res.ok) throw new Error(`${res.status} on /api/review/export`);
  const text = await res.text();
  const blob = new Blob([text], { type: "application/x-ndjson" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sif-decision-log-${new Date().toISOString().slice(0, 10)}.ndjson`;
  a.click();
  URL.revokeObjectURL(url);
  return text.split("\n").filter((l) => l.trim().length > 0).length;
}

/* ---- report context (snippet + severity) for audit rows ----
 * The audit log carries only report_id; the snippet + band come from
 * GET /api/reports/{id}. ponytail: per-id GETs with a cache — fine at the
 * audit-log scale (tens of rows); swap to a batch endpoint if logs hit 1000s. */

export interface ReportMeta {
  id: number;
  snippet: string;
  text: string;
  site: string;
  reportedAt: string;
  band: "HIGH" | "MODERATE" | "LOW" | null;
  wellControl: boolean;
}

const metaCache = new Map<number, Promise<ReportMeta | null>>();

export function getReportMeta(id: number): Promise<ReportMeta | null> {
  const hit = metaCache.get(id);
  if (hit) return hit;
  const p = (async () => {
    try {
      const r = await getReport(id);
      if (!r) {
        metaCache.delete(id);
        return null;
      }
      const flat = r.text.replace(/\s+/g, " ").trim();
      return {
        id,
        text: r.text,
        snippet: flat.length > 160 ? `${flat.slice(0, 160)}…` : flat,
        site: r.site,
        reportedAt: r.reported_at,
        // band is server-owned and optional (A4): absent ≠ low — mapped to null.
        band: r.prediction.band ?? null,
        wellControl: r.prediction.well_control,
      } satisfies ReportMeta;
    } catch {
      metaCache.delete(id);
      return null;
    }
  })();
  metaCache.set(id, p);
  return p;
}

/* ---- reviewer identity (WHO) ----
 * Honest by construction: there is no auth in this stack, so the identity is
 * self-declared, persisted locally, and disclosed as such in the UI. */

export function loadReviewer(): string {
  try {
    return localStorage.getItem(REVIEWER_KEY) ?? localStorage.getItem("sif.reviewer") ?? "";
  } catch {
    return "";
  }
}

export function saveReviewer(name: string): void {
  try {
    localStorage.setItem(REVIEWER_KEY, name);
  } catch {
    /* private mode: identity stays session-only */
  }
}

/** Distinct labelers seen in the log, oldest-first — feeds the identity
 *  picker. The anonymous "hse_reviewer" default sorts last. */
export function knownLabelers(rows: AuditRow[]): string[] {
  const seen = new Set<string>();
  for (const r of rows) if (r.labeler) seen.add(r.labeler);
  return [...seen].sort((a, b) =>
    a === "hse_reviewer" ? 1 : b === "hse_reviewer" ? -1 : a.localeCompare(b),
  );
}

/* ---- CAPA (owner / due / status) + OISD aging clocks ----
 * ponytail ceiling: CAPA state lives in localStorage (per-browser), not the
 * server — there is no backend table for it yet. The UI discloses this;
 * upgrade path: a /api/capa table keyed by override_id. */

export type CapaStatus = "open" | "in_progress" | "closed";
export type OisdTrack = "fir" | "iir";

export interface Capa {
  owner: string;
  due: string; // yyyy-mm-dd
  status: CapaStatus;
  track: OisdTrack;
}

export type CapaStore = Record<number, Capa>; // keyed by override id

const CAPA_KEY = "sif26.capa.v1";

export function loadCapas(): CapaStore {
  try {
    const raw = localStorage.getItem(CAPA_KEY);
    return raw ? (JSON.parse(raw) as CapaStore) : {};
  } catch {
    return {};
  }
}

export function saveCapa(id: number, capa: Capa, store: CapaStore): CapaStore {
  const next = { ...store, [id]: capa };
  try {
    localStorage.setItem(CAPA_KEY, JSON.stringify(next));
  } catch {
    /* private mode: session-only */
  }
  return next;
}

export const FIR_CLOCK_MS = 24 * 3_600_000;
export const IIR_CLOCK_MS = 30 * 86_400_000;

/** Overdue = not closed AND (past the OISD clock for its track, or past its
 *  own due date). Closed items never age. */
export function capaAged(capa: Capa, createdAt: string, now: Date): boolean {
  if (capa.status === "closed") return false;
  const t0 = new Date(createdAt).getTime();
  if (Number.isFinite(t0)) {
    if (now.getTime() - t0 > (capa.track === "fir" ? FIR_CLOCK_MS : IIR_CLOCK_MS)) return true;
  }
  if (capa.due) {
    const due = new Date(`${capa.due}T23:59:59`).getTime();
    if (Number.isFinite(due) && now.getTime() > due) return true;
  }
  return false;
}

export interface Workload {
  open: number;
  inProgress: number;
  closed: number;
  firAged: number;
  iirAged: number;
  noCapa: number;
  byOwner: { owner: string; n: number }[];
}

/** Reviewer-workload summary over override rows (blind_gold rows are
 *  pre-labeled corpus, not reviewer decisions — excluded). */
export function computeWorkload(rows: AuditRow[], capas: CapaStore, now = new Date()): Workload {
  let open = 0;
  let inProgress = 0;
  let closed = 0;
  let noCapa = 0;
  let firAged = 0;
  let iirAged = 0;
  const owners = new Map<string, number>();
  for (const row of rows) {
    if (row.source !== "override") continue;
    const capa = capas[row.id];
    if (!capa) {
      noCapa += 1;
      continue;
    }
    if (capa.status === "closed") {
      closed += 1;
      continue;
    }
    if (capa.status === "in_progress") inProgress += 1;
    else open += 1;
    owners.set(capa.owner, (owners.get(capa.owner) ?? 0) + 1);
    if (capaAged(capa, row.created_at, now)) {
      if (capa.track === "fir") firAged += 1;
      else iirAged += 1;
    }
  }
  return {
    open,
    inProgress,
    closed,
    firAged,
    iirAged,
    noCapa,
    byOwner: [...owners.entries()]
      .map(([owner, n]) => ({ owner, n }))
      .sort((a, b) => b.n - a.n),
  };
}

/** OISD track auto-suggestion: the well-control (Baghjan-class barrier) tag
 *  marks a major-incident-class report → FIR clock; everything else IIR. */
export function suggestTrack(meta: ReportMeta | null): OisdTrack {
  return meta?.wellControl ? "fir" : "iir";
}

/** Default due date: today + the track's OISD clock (local midnight). */
export function defaultDue(track: OisdTrack): string {
  const d = new Date();
  d.setDate(d.getDate() + (track === "fir" ? 1 : 30));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Rows that a later row on the same (report_id, field) supersedes — the
 *  client-side view of the lineage the export computes server-side. */
export function supersededIds(rows: AuditRow[]): Set<number> {
  const latest = new Map<string, number>();
  for (const r of rows) {
    latest.set(`${r.report_id}|${r.field}`, r.id);
  }
  return new Set(rows.filter((r) => latest.get(`${r.report_id}|${r.field}`) !== r.id).map((r) => r.id));
}
