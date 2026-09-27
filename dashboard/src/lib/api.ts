import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DENSITY_BEFORE, MOCK_EXPLANATIONS, OVERRIDES, PATTERNS, REPORTS } from "./mock";
import type {
  ClustersOut,
  DensityRow,
  ExplanationOut,
  GateState,
  HealthOut,
  MetricsSummary,
  OverrideOut,
  PatternKind,
  PatternOut,
  PredictionOut,
  Report,
  RuleInfo,
  RuleScore,
} from "./types";

/* Typed fetch client for the FastAPI runtime (app/routes.py + app/schemas.py),
 * consumed through @tanstack/react-query hooks.
 *
 * HONESTY CONTRACT (replaces the old "UI never hard-fails" fixture doctrine):
 *  - A fetch failure THROWS. React Query surfaces the error and the surface
 *    renders an ErrorState. No transient error may silently swap real rows
 *    for invented model output on a safety-critical screen.
 *  - Fixtures (lib/mock.ts) are reachable ONLY behind VITE_DEMO_MODE=1.
 *    Default OFF. Mock row ids 2588–2619 collide with real server rows — they
 *    must never render as live data.
 *  - The fabricated offline classify fallback (score 0.5 + a fake
 *    "confidence" gate) is DELETED. classify() throws when the API fails.
 *  - The ingest money beat carries NO client path here: bulk CSV goes through
 *    features/ingest/ingest-api.ts (startIngest 202/200 branch) and
 *    use-ingest-job.ts (poll GET /api/ingest/{job_id}, verify via /api/health).
 *    The old lib ingestCsv() rendered "accepted undefined" for the 202 shape —
 *    deleted, not fixed, so no surface can re-import it.
 *
 * Base URL: import.meta.env.VITE_API_BASE, defaulting to "" (same-origin —
 * the FastAPI process serves this dist at /, so relative /api requests are
 * the path that works from a browser; the API has no CORS middleware).
 * The vite dev/preview proxy forwards /api → the API. */

export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "1";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");
const TIMEOUT_MS = 3500; // plain fetches; getExplanation overrides below

/* ---- Raw wire shapes (app/schemas.py — these names win) ---- */

interface ApiReportIn {
  text: string;
  date: string | null;
  site: string | null;
  activity: string | null;
  contractor: string | null;
  source: string;
}

interface ApiPredictionOut {
  sif_score: number;
  score_spread?: number | null;
  n_variants?: number | null;
  variant_scores?: number[];
  verdict_stability?: PredictionOut["verdict_stability"];
  band?: PredictionOut["band"];
  flag_threshold?: number | null;
  gray_band_low?: number | null;
  gray_band_high?: number | null;
  rule_cue_hits?: Record<string, boolean> | null;
  rule_probs: Record<string, number>;
  well_control: boolean;
  evidence_spans: { start: number; end: number; text: string }[];
  gate_states: GateState[];
  model_version: string;
  chunked?: boolean;
  explanation?: ExplanationOut | null;
  report_id?: number | null; // set by /classify?persist=1 only
}

interface ApiStoredReport {
  id: number;
  report: ApiReportIn;
  prediction: ApiPredictionOut | null;
  created_at: string;
}

interface ApiDensityRow {
  key: string;
  n_reports: number;
  n_flagged: number;
  sif_rate: number;
  mean_score: number;
}

interface ApiPatternRow {
  activity: string;
  n: number;
  sif_rate: number;
  lift: number;
  ci_low: number;
  ci_high: number;
  site: string | null;
  barrier: string | null;
  rule: string | null;
  kind: PatternKind;
}

interface ApiStoredOverride {
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

/* Rule display metadata — mirror of RULE_DISPLAY in app/schemas.py, refreshed
 * from GET /api/rules whenever the API is reachable. The local copy keeps the
 * UI honest (7 in-scope + 2 declared out-of-scope) even fully offline. */
const RULE_META: Record<string, { display: string; in_scope: boolean }> = {
  confined_space: { display: "Confined Space", in_scope: true },
  driving: { display: "Driving", in_scope: true },
  energy_isolation: { display: "Energy Isolation", in_scope: true },
  hot_work: { display: "Hot Work", in_scope: true },
  line_of_fire: { display: "Line of Fire", in_scope: true },
  safe_mechanical_lifting: { display: "Safe Mechanical Lifting", in_scope: true },
  working_at_height: { display: "Working at Height", in_scope: true },
  work_authorisation: {
    display: "Work Authorisation (Permit to Work)",
    in_scope: false,
  },
  bypassing_safety_controls: {
    display: "Bypassing Safety Controls",
    in_scope: false,
  },
};

let liveRuleMeta: typeof RULE_META | null = null;

function ruleMeta(): typeof RULE_META {
  return liveRuleMeta ?? RULE_META;
}

/** Display name for a rule key (live /api/rules metadata when fetched). */
export function ruleDisplayName(code: string): string {
  return ruleMeta()[code]?.display ?? code;
}

class HttpError extends Error {
  readonly status: number;

  constructor(status: number, statusText: string, path: string) {
    super(`${status} ${statusText} on ${path}`);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit, timeoutMs = TIMEOUT_MS): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctl.signal,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!res.ok) throw new HttpError(res.status, res.statusText, path);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

/* ---- Adapters: API contract → UI shapes ---- */

function adaptPrediction(p: ApiPredictionOut): PredictionOut {
  const meta = ruleMeta();
  const rules: RuleScore[] = Object.entries(p.rule_probs)
    .map(([code, prob]) => ({
      code,
      name: meta[code]?.display ?? code,
      prob,
      in_scope: meta[code]?.in_scope ?? true,
      cue_hit: p.rule_cue_hits?.[code] ?? null,
    }))
    .sort((a, b) => b.prob - a.prob);
  // The two out-of-scope IOGP rules are no longer rendered anywhere: the
  // report detail shows only what is scored. Their disclosure lives in the
  // Data & limitations dialog, not on every report.
  return {
    sif_score: p.sif_score,
    score_spread: p.score_spread ?? null,
    n_variants: p.n_variants ?? null,
    variant_scores: p.variant_scores ?? null,
    verdict_stability: p.verdict_stability ?? null,
    band: p.band ?? null,
    flag_threshold: p.flag_threshold ?? null,
    gray_band_low: p.gray_band_low ?? null,
    gray_band_high: p.gray_band_high ?? null,
    latency_ms: 0,
    rules,
    well_control: p.well_control,
    evidence_spans: p.evidence_spans,
    gate_states: p.gate_states,
    model_version: p.model_version,
    chunked: p.chunked ?? false,
    explanation: p.explanation ?? null,
    report_id: p.report_id ?? null,
  };
}

function adaptReport(s: ApiStoredReport): Report | null {
  if (!s.prediction) return null;
  return {
    id: s.id,
    text: s.report.text,
    site: s.report.site ?? "(unspecified)",
    activity: s.report.activity ?? "(unspecified)",
    contractor: s.report.contractor,
    reported_at: s.report.date ?? s.created_at.slice(0, 10),
    prediction: adaptPrediction(s.prediction),
  };
}

function adaptOverride(o: ApiStoredOverride): OverrideOut {
  return {
    id: o.id,
    report_id: o.report_id,
    field: o.field,
    old_value: o.old_value,
    new_value: o.new_value,
    labeler: o.labeler,
    rationale: o.rationale ?? null,
    source: o.source,
    ts: o.created_at,
  };
}

function withRanks(rows: ApiDensityRow[], prev: DensityRow[] | null): DensityRow[] {
  const prevRank = new Map((prev ?? []).map((r) => [r.key, r.rank]));
  return rows.map((r, i) => ({
    ...r,
    rank: i + 1,
    prev_rank: prevRank.get(r.key) ?? i + 1,
  }));
}

/* ---- Endpoints (plain fetchers; hooks below) ---- */

/** GET /api/clusters?min_cos=0.91 — server-owned star groups for queue compression. */
export async function getClusters(): Promise<ClustersOut> {
  return req<ClustersOut>("/api/clusters?min_cos=0.91");
}

/** GET /api/health — null when unreachable (the badge IS the error signal). */
export async function getHealth(): Promise<HealthOut | null> {
  try {
    const h = await req<HealthOut>("/api/health");
    return h.status === "ok" ? h : null;
  } catch {
    return null;
  }
}

/** GET /api/rules — all 9 IOGP rules; refreshes the live display metadata.
 *  Offline: the static mirror, not a fixture swap (it is declared metadata,
 *  not model output). */
export async function getRules(): Promise<RuleInfo[]> {
  try {
    const rs = await req<RuleInfo[]>("/api/rules");
    liveRuleMeta = Object.fromEntries(
      rs.map((r) => [r.key, { display: r.display, in_scope: r.in_scope }]),
    );
    return rs;
  } catch {
    return Object.entries(RULE_META).map(([key, m]) => ({
      key,
      display: m.display,
      in_scope: m.in_scope,
      threshold: m.in_scope ? 0.5 : null,
    }));
  }
}

/** GET /api/reports — the feed. Reports without predictions are dropped.
 *  Offline + VITE_DEMO_MODE=1 only: fixture rows. Otherwise THROWS. */
export async function getReports(params: { limit?: number; offset?: number } = {}): Promise<Report[]> {
  const limit = params.limit ?? 200;
  const offset = params.offset ?? 0;
  try {
    await getRules();
    const rows = await req<ApiStoredReport[]>(`/api/reports?limit=${limit}&offset=${offset}`);
    return rows.map(adaptReport).filter((r): r is Report => r !== null);
  } catch (e) {
    if (DEMO_MODE) return REPORTS;
    throw e;
  }
}

/** GET /api/reports/{id}. 404 is missing; other failures reach ErrorState. */
export async function getReport(id: number): Promise<Report | null> {
  try {
    return adaptReport(await req<ApiStoredReport>(`/api/reports/${id}`));
  } catch (e) {
    if (e instanceof HttpError && e.status === 404) return null;
    if (DEMO_MODE) return REPORTS.find((r) => r.id === id) ?? null;
    throw e;
  }
}

/** POST /api/classify?persist=1 — paste-flow triage that PERSISTS the report
 *  (latency measured client-side) and returns the real server row id.
 *  opts.explain bundles the deterministic explanation template (llm=0: a cold
 *  ollama reword on novel text would stall the card for seconds).
 *  THROWS when the API is unreachable — no fabricated score, no fake gate.
 *  The surface shows an error state instead. */
export async function classify(
  text: string,
  opts?: { explain?: boolean },
): Promise<PredictionOut> {
  const t0 = performance.now();
  const query = opts?.explain ? "?persist=1&explain=1&llm=0" : "?persist=1";
  const p = await req<ApiPredictionOut>(`/api/classify${query}`, {
    method: "POST",
    body: JSON.stringify({
      text,
      source: "live-paste",
    }),
  });
  return { ...adaptPrediction(p), latency_ms: Math.round(performance.now() - t0) };
}

/* ---- Ingest has NO client path in lib — see the header comment above. The
 * bulk-upload money beat belongs to features/ingest (startIngest +
 * useIngestRun), which branches on the server's 202 job id and polls
 * GET /api/ingest/{job_id} for truthful progress instead of guessing. ---- */

/** GET /api/reports/{id}/explanation — fetched lazily when the triage-card
 *  expander opens (never blocks the card). A cold call pays one bounded
 *  ollama attempt server-side (8s cap), so the client waits up to 12s.
 *  null when unreachable, missing, or the report has no prediction — the
 *  caller then hides the section (honest "unavailable", not fabricated). */
export async function getExplanation(reportId: number): Promise<ExplanationOut | null> {
  try {
    return await req<ExplanationOut>(`/api/reports/${reportId}/explanation`, undefined, 12_000);
  } catch {
    if (DEMO_MODE) return MOCK_EXPLANATIONS[reportId] ?? null;
    return null;
  }
}

/** GET /api/density — precursor-density ranking. rank is the sorted position;
 *  prev_rank comes from the caller's previous snapshot (the re-rank beat). */
export async function getDensity(
  by: "site" | "activity" | "contractor" = "site",
  prev: DensityRow[] | null = null,
): Promise<DensityRow[]> {
  try {
    return withRanks(await req<ApiDensityRow[]>(`/api/density?by=${by}`), prev);
  } catch (e) {
    if (DEMO_MODE) return prev ?? DENSITY_BEFORE;
    throw e;
  }
}

/** GET /api/patterns?kind= — lift-ranked co-occurrence.
 *  site_activity: activity × site cells. activity_barrier: activity ×
 *  barrier cells (served from the precomputed synthetic-corpus stats). */
export async function getPatterns(
  kind: PatternKind = "site_activity",
): Promise<PatternOut[]> {
  try {
    const rows = await req<ApiPatternRow[]>(`/api/patterns?kind=${kind}`);
    return rows.map((r, i) => ({ id: `${kind}-${i + 1}`, ...r }));
  } catch (e) {
    if (DEMO_MODE) return PATTERNS.filter((p) => p.kind === kind);
    throw e;
  }
}

/** GET /api/review — the override queue (future gold labels). Throws when
 *  unreachable, unless VITE_DEMO_MODE=1. */
export async function getOverrides(reportId?: number): Promise<OverrideOut[]> {
  try {
    const q = reportId === undefined ? "" : `?report_id=${reportId}`;
    const rows = await req<ApiStoredOverride[]>(`/api/review${q}`);
    return rows.map(adaptOverride);
  } catch (e) {
    if (DEMO_MODE) return OVERRIDES;
    throw e;
  }
}

/** POST /api/review — "model proposes, HSE disposes". Throws when offline;
 *  callers must NOT record a local fake decision row (the audit trail is the
 *  server's write path). The reviewer identity is whatever the caller passes
 *  in `labeler` (decision-panel persists it under lib/identity.ts's
 *  REVIEWER_KEY); when no reviewer is captured the server applies its own
 *  "hse_reviewer" default (app/schemas.py OverrideIn) — a disclosed
 *  anonymous fallback, not an invented name. `rationale` is the "why the
 *  model was overruled" field and is REQUIRED by the UI form; it is stored
 *  server-side and round-trips on read via adaptOverride above. */
export async function postReview(input: {
  report_id: number;
  field: string;
  old_value?: string | null;
  new_value: string;
  labeler?: string;
  rationale?: string;
}): Promise<OverrideOut> {
  const o = await req<ApiStoredOverride>("/api/review", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return adaptOverride(o);
}

/** GET /api/metrics/summary — null when unreachable (caller hides the card). */
export async function getMetricsSummary(): Promise<MetricsSummary | null> {
  try {
    return await req<MetricsSummary>("/api/metrics/summary");
  } catch {
    return null;
  }
}

/* ---- React Query layer ---- */

/** Stable query keys. Filter state that must survive a shared link
 *  ('queue?fsi=0.8&range=90d&page=3') lives in the URL (useSearchParams in
 *  the feature); keys here carry only server-shaped params. */
export const qk = {
  health: ["health"] as const,
  rules: ["rules"] as const,
  clusters: ["clusters", 0.91] as const,
  reports: (params: { limit?: number; offset?: number } = {}) =>
    ["reports", params] as const,
  report: (id: number) => ["report", id] as const,
  overrides: (reportId?: number) =>
    reportId === undefined
      ? (["overrides"] as const)
      : (["overrides", reportId] as const),
  density: (by: "site" | "activity" | "contractor") => ["density", by] as const,
  patterns: (kind: PatternKind) => ["patterns", kind] as const,
  explanation: (reportId: number) => ["explanation", reportId] as const,
  metrics: ["metrics-summary"] as const,
};

export function useHealth() {
  return useQuery({ queryKey: qk.health, queryFn: getHealth, staleTime: 15_000, refetchInterval: 30_000 });
}

export function useRules() {
  return useQuery({ queryKey: qk.rules, queryFn: getRules, staleTime: Infinity });
}

export function useReports(params: { limit?: number; offset?: number } = {}) {
  return useQuery({ queryKey: qk.reports(params), queryFn: () => getReports(params) });
}

export function useClusters() {
  return useQuery({ queryKey: qk.clusters, queryFn: getClusters, staleTime: 5 * 60_000 });
}

export function useReport(id: number | null) {
  return useQuery({ queryKey: qk.report(id ?? -1), queryFn: () => getReport(id!), enabled: id !== null });
}

export function useOverrides(reportId?: number) {
  return useQuery({ queryKey: qk.overrides(reportId), queryFn: () => getOverrides(reportId) });
}

export function useDensity(by: "site" | "activity" | "contractor" = "site", prev: DensityRow[] | null = null) {
  return useQuery({ queryKey: qk.density(by), queryFn: () => getDensity(by, prev) });
}

export function usePatterns(kind: PatternKind = "site_activity") {
  return useQuery({ queryKey: qk.patterns(kind), queryFn: () => getPatterns(kind) });
}

/** Lazily fetched explanation — never blocks the card. `enabled` is false
 *  until the card's expander opens. */
export function useExplanation(reportId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: qk.explanation(reportId ?? -1),
    queryFn: () => getExplanation(reportId!),
    enabled: enabled && reportId !== null,
    staleTime: Infinity,
  });
}

export function useMetricsSummary() {
  return useQuery({ queryKey: qk.metrics, queryFn: getMetricsSummary });
}

/** POST /api/review with rationale — invalidates the decisions audit trail. */
export function usePostReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: postReview,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["overrides"] });
      void qc.invalidateQueries({ queryKey: qk.clusters });
      void qc.invalidateQueries({ queryKey: qk.metrics });
    },
  });
}

/** Paste-classify — persists on the server, then refreshes queue + metrics +
 *  health counts. Errors propagate to the caller for the ErrorState card. */
export function useClassify() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { text: string; explain?: boolean }) =>
      classify(input.text, { explain: input.explain }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["reports"] });
      void qc.invalidateQueries({ queryKey: qk.clusters });
      void qc.invalidateQueries({ queryKey: qk.metrics });
      void qc.invalidateQueries({ queryKey: qk.health });
    },
  });
}

/** Bulk CSV ingest — NOT here. The money beat is owned by features/ingest
 *  (startIngest + useIngestRun): a 202 job id is polled on
 *  GET /api/ingest/{job_id} and only server-reported counts are rendered;
 *  a timeout aborts the wait, never the verdict (the outcome is verified
 *  against /api/health's live report count). The old useIngestCsv() sat on
 *  the fabricated "accepted undefined" outcome and is deleted. */