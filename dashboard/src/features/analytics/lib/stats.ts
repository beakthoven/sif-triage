/* Deterministic statistics for the analytics surface: date parsing, period
 * bucketing, trend deltas and the min-n / ranking logic. Pure functions — the
 * UI stays declarative and the numbers are testable. The Wilson interval is
 * reused from the domain slice (@/components/domain/domain-logic) so there is
 * exactly one interval implementation in the app. */

import { wilson } from "@/components/domain/domain-logic";

export type Facet = "site" | "activity" | "contractor";
export type Granularity = "week" | "month";
export type RankingMode = "wilson" | "rate";

/** The served operating point. /api/metrics/summary now exposes it as
 * flag_threshold (server-owned since the ensemble re-tune), so
 * setFlagThreshold() binds the server's value at load and flagThreshold()
 * returns it. FLAG_THRESHOLD remains only the offline fallback for when the
 * API is unreachable — the analytics slice must never crash offline.
 * ponytail: the load-time cross-check against metrics.n_flagged stays as the
 * drift alarm; this fallback constant is the last hardcode left. */
export const FLAG_THRESHOLD = 0.5647; // ensemble re-tune 2026-09-26;
// provenance: artifacts/demo/ensemble_operating_point_v2.json (N=4 ensemble,
// max recall subject to precision >= 0.80, n=17,731 derived-label test split)

let servedThreshold: number | null = null;

/** Bind the server's operating point (called when /api/metrics/summary
 * resolves). Ignored unless it is a sane open-interval probability. */
export function setFlagThreshold(v: number | null | undefined): void {
  servedThreshold =
    typeof v === "number" && Number.isFinite(v) && v > 0 && v < 1 ? v : null;
}

export function hasServedFlagThreshold(): boolean {
  return servedThreshold !== null;
}

/** Threshold for client-side flagged counting: the server's value when
 * known, the offline fallback otherwise. */
export function flagThreshold(): number {
  return servedThreshold ?? FLAG_THRESHOLD;
}

export function formatThreshold(value: number): string {
  return value.toFixed(4).replace(/\.?0+$/, "");
}

export function fmtPer100(x: number): string {
  return (x * 100).toFixed(1);
}

/* ---- Dates: the register mixes ISO (2024-01-15) and DD.MM.YYYY; 3,007 of
 * 5,057 live rows have no date at all. Unparseable dates are excluded from the
 * trend and the exclusion is disclosed on-surface. ---- */

export function parseReportDate(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const s = raw.trim();
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
  const m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(s);
  if (m) {
    const iso = `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
    return Number.isNaN(Date.parse(`${iso}T00:00:00Z`)) ? null : iso;
  }
  return null;
}

function mondayOf(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  const dow = (d.getUTCDay() + 6) % 7; // Monday = 0
  d.setUTCDate(d.getUTCDate() - dow);
  return d.toISOString().slice(0, 10);
}

export function bucketKey(dateIso: string, granularity: Granularity): string {
  return granularity === "month" ? dateIso.slice(0, 7) : mondayOf(dateIso);
}

/* ---- Trend buckets ---- */

export interface TrendBucket {
  key: string; // "2024-05" or the Monday ISO date
  label: string; // raw key; tick labels are formatted in the chart layer
  n: number; // dated reports in the bucket
  flagged: number; // reports at/above FLAG_THRESHOLD
  ratePer100: number | null; // null when n === 0 (honest gap, not a fake 0)
  ci: [number, number] | null; // Wilson CI of the rate, per-100 units
  ciErr: [number, number] | null; // recharts asymmetric errors [v-lo, hi-v]
}

function addMonths(y: number, m: number): [number, number] {
  const total = y * 12 + (m - 1) + 1;
  return [Math.floor(total / 12), (total % 12) + 1];
}

export function formatBucketLabel(
  bucket: TrendBucket,
  granularity: Granularity,
  months: string[],
): string {
  if (granularity === "month") {
    return `${months[Number(bucket.key.slice(5, 7)) - 1]} ${bucket.key.slice(2, 4)}`;
  }
  const d = new Date(`${bucket.key}T00:00:00Z`);
  return `${d.getUTCDate()} ${months[d.getUTCMonth()]}`;
}

/** Buckets spanning the requested window (falling back to the data bounds
 * only where the window is open), zero-filled so reporting gaps stay visible
 * as gaps. A window entirely outside the data yields no buckets — the caller
 * shows its empty state instead of silently spanning the union. */
export function buildTrendBuckets(
  dated: { dateIso: string; flagged: boolean }[],
  granularity: Granularity,
  range: { from: string | null; to: string | null },
): TrendBucket[] {
  const dates = dated.map((r) => r.dateIso).sort();
  if (dates.length === 0) return [];
  const from = range.from ?? dates[0];
  const to = range.to ?? dates[dates.length - 1];
  if (from > to) return [];

  const keys: string[] = [];
  if (granularity === "month") {
    let key = from.slice(0, 7);
    const end = to.slice(0, 7);
    while (key <= end) {
      keys.push(key);
      const [y, m] = addMonths(Number(key.slice(0, 4)), Number(key.slice(5, 7)));
      key = `${y}-${String(m).padStart(2, "0")}`;
    }
  } else {
    let cursor = mondayOf(from);
    while (cursor <= to) {
      keys.push(cursor);
      const d = new Date(`${cursor}T00:00:00Z`);
      d.setUTCDate(d.getUTCDate() + 7);
      cursor = d.toISOString().slice(0, 10);
    }
  }
  if (keys.length === 0) return [];

  const byKey = new Map<string, { n: number; flagged: number }>();
  for (const r of dated) {
    const k = bucketKey(r.dateIso, granularity);
    if (k < keys[0] || k > keys[keys.length - 1]) continue;
    const agg = byKey.get(k) ?? { n: 0, flagged: 0 };
    agg.n += 1;
    if (r.flagged) agg.flagged += 1;
    byKey.set(k, agg);
  }

  return keys.map((key) => {
    const agg = byKey.get(key) ?? { n: 0, flagged: 0 };
    const rate = agg.n > 0 ? agg.flagged / agg.n : null;
    const ci = rate === null ? null : wilson(rate, agg.n);
    return {
      key,
      label: key,
      n: agg.n,
      flagged: agg.flagged,
      ratePer100: rate === null ? null : rate * 100,
      ci: ci === null ? null : ([ci[0] * 100, ci[1] * 100] as [number, number]),
      ciErr:
        rate === null || ci === null
          ? null
          : ([(rate - ci[0]) * 100, (ci[1] - rate) * 100] as [number, number]),
    };
  });
}

/* ---- Trend delta: aggregate the last k buckets vs the previous k. ---- */

export interface TrendDelta {
  recentRate: number; // per 100
  recentN: number;
  priorRate: number;
  priorN: number;
  delta: number; // percentage points
}

export function trendDelta(buckets: TrendBucket[], k = 4): TrendDelta | null {
  if (buckets.length === 0) return null;
  const recent = buckets.slice(-k);
  const prior = buckets.slice(Math.max(0, buckets.length - 2 * k), buckets.length - k);
  const agg = (list: TrendBucket[]) => ({
    n: list.reduce((s, b) => s + b.n, 0),
    flagged: list.reduce((s, b) => s + b.flagged, 0),
  });
  const r = agg(recent);
  const p = agg(prior);
  if (r.n === 0 && p.n === 0) return null;
  const recentRate = r.n > 0 ? (r.flagged / r.n) * 100 : null;
  const priorRate = p.n > 0 ? (p.flagged / p.n) * 100 : null;
  return {
    recentRate: recentRate ?? 0,
    recentN: r.n,
    priorRate: priorRate ?? 0,
    priorN: p.n,
    delta: recentRate !== null && priorRate !== null ? recentRate - priorRate : 0,
  };
}

/* ---- Density ranking with the min-n guard ---- */

export interface DensityStat {
  key: string;
  nReports: number;
  nFlagged: number;
  rate: number; // 0..1
  meanScore: number;
  ciLow: number; // Wilson lower bound, 0..1 — the sort key for "certainty"
  ciHigh: number;
}

export function toDensityStat(row: {
  key: string;
  n_reports: number;
  n_flagged: number;
  sif_rate: number;
  mean_score: number;
}): DensityStat {
  const [ciLow, ciHigh] = wilson(row.sif_rate, row.n_reports);
  return {
    key: row.key,
    nReports: row.n_reports,
    nFlagged: row.n_flagged,
    rate: row.sif_rate,
    meanScore: row.mean_score,
    ciLow,
    ciHigh,
  };
}

/** Rank by certainty (Wilson lower bound, n tiebreak) or by the raw point
 * estimate. A site at 100% with n=13 (LB ≈ 86) ranks BELOW one with n=213
 * (LB ≈ 97) — the n=3@33%-beats-n=35@0% pathology disappears. The @/components
 * /domain DensityTable renders rows in the order given, so the chosen
 * ordering IS the ranking the user sees. */
export function rankDensity(rows: DensityStat[], mode: RankingMode): DensityStat[] {
  const copy = [...rows];
  if (mode === "wilson") {
    copy.sort(
      (a, b) => b.ciLow - a.ciLow || b.nReports - a.nReports || a.key.localeCompare(b.key),
    );
  } else {
    copy.sort((a, b) => b.rate - a.rate || b.nReports - a.nReports || a.key.localeCompare(b.key));
  }
  return copy;
}

export function splitByMinN(
  ranked: DensityStat[],
  minN: number,
): { ranked: DensityStat[]; quarantined: DensityStat[] } {
  return {
    ranked: ranked.filter((r) => r.nReports >= minN),
    quarantined: ranked
      .filter((r) => r.nReports < minN)
      .sort((a, b) => b.nReports - a.nReports || a.key.localeCompare(b.key)),
  };
}