/* Queue view state: URL-synced filters + the client-side filter pass.
 * The URL is the shareable state: ?sort&q&band&rule&site&activity&from&to.
 * Invalid or unknown values fall back to defaults — never a crash. */

import { hasFacet } from "@/lib/report-display";
import type { QueueRow } from "./api";

export type QueueSort = "score-desc" | "score-asc" | "id-desc" | "id-asc";
export type VerdictFilter = "all" | "high" | "moderate" | "low" | "review";

export interface QueueFilters {
  q: string;
  sort: QueueSort;
  verdict: VerdictFilter;
  rule: string | null;
  site: string | null;
  activity: string | null;
  /** Inclusive bounds on the DISPLAYED date (event date, else ingestion). */
  from: string | null;
  to: string | null;
}

export const DEFAULT_FILTERS: QueueFilters = {
  q: "",
  sort: "score-desc",
  verdict: "all",
  rule: null,
  site: null,
  activity: null,
  from: null,
  to: null,
};

const SORTS: QueueSort[] = ["score-desc", "score-asc", "id-desc", "id-asc"];
const VERDICTS: VerdictFilter[] = ["all", "high", "moderate", "low", "review"];

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function opt(params: URLSearchParams, key: string): string | null {
  const v = params.get(key);
  return v && v.trim() !== "" ? v.trim() : null;
}

export function parseFilters(search: string): QueueFilters {
  const p = new URLSearchParams(search);
  const sort = p.get("sort");
  const verdict = p.get("band");
  return {
    q: p.get("q") ?? "",
    sort: sort && (SORTS as string[]).includes(sort) ? (sort as QueueSort) : DEFAULT_FILTERS.sort,
    verdict:
      verdict && (VERDICTS as string[]).includes(verdict)
        ? (verdict as VerdictFilter)
        : DEFAULT_FILTERS.verdict,
    rule: opt(p, "rule"),
    site: opt(p, "site"),
    activity: opt(p, "activity"),
    from: p.get("from")?.match(DATE_RE)?.[0] ?? null,
    to: p.get("to")?.match(DATE_RE)?.[0] ?? null,
  };
}

export function serializeFilters(f: QueueFilters): string {
  const p = new URLSearchParams();
  if (f.sort !== DEFAULT_FILTERS.sort) p.set("sort", f.sort);
  if (f.verdict !== DEFAULT_FILTERS.verdict) p.set("band", f.verdict);
  if (f.q.trim() !== "") p.set("q", f.q.trim());
  if (f.rule) p.set("rule", f.rule);
  if (f.site) p.set("site", f.site);
  if (f.activity) p.set("activity", f.activity);
  if (f.from) p.set("from", f.from);
  if (f.to) p.set("to", f.to);
  return p.toString();
}

export function isFiltersActive(f: QueueFilters): boolean {
  return serializeFilters({ ...f, sort: DEFAULT_FILTERS.sort }) !== "";
}

export interface RuleThresholds {
  map: Map<string, number>;
}

/** Filter rows against the URL state. Every predicate is plain and inspectable
 *  — the queue is the surface a skeptic checks first. */
export function applyFilters(
  rows: QueueRow[],
  f: QueueFilters,
  ruleThresholds: Map<string, number>,
): QueueRow[] {
  const q = f.q.trim().toLowerCase();
  return rows.filter((r) => {
    if (q !== "") {
      const hay = `${r.text} ${r.site ?? ""} ${r.activity ?? ""} ${r.contractor ?? ""} ${r.id}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (f.verdict === "review") {
      if (r.grayGates.length === 0) return false;
    } else if (f.verdict !== "all") {
      // Band is server-owned (A4); rows without a band cannot be honestly
      // classified and are excluded from band filters.
      if (r.band === null) return false;
      if (f.verdict === "high" && r.band !== "HIGH") return false;
      if (f.verdict === "moderate" && r.band !== "MODERATE") return false;
      if (f.verdict === "low" && r.band !== "LOW") return false;
    }
    if (f.rule) {
      const prob = r.ruleProbs[f.rule];
      const th = ruleThresholds.get(f.rule) ?? 0.5;
      if (prob === undefined || prob < th) return false;
    }
    if (f.site && r.site !== f.site) return false;
    if (f.activity && r.activity !== f.activity) return false;
    if (f.from && r.displayDate < f.from) return false;
    if (f.to && r.displayDate > f.to) return false;
    return true;
  });
}

/** Filter options from the loaded register — real distinct values, no guesses. */
export function distinctOptions(
  rows: QueueRow[],
  pick: (r: QueueRow) => string | null,
): string[] {
  const set = new Set<string>();
  for (const r of rows) {
    const v = pick(r);
    if (hasFacet(v)) set.add(v);
  }
  return [...set].sort((a, b) => a.localeCompare(b));
}