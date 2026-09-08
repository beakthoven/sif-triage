import { DENSITY_BEFORE, MOCK_EXPLANATIONS, OVERRIDES, PATTERNS, REPORTS } from "./mock";
import type {
  Band,
  DensityRow,
  ExplanationOut,
  GateState,
  HealthOut,
  IngestResult,
  MetricsSummary,
  OverrideOut,
  PatternKind,
  PatternOut,
  PredictionOut,
  Report,
  RuleInfo,
  RuleScore,
} from "./types";

/* Typed fetch client for the FastAPI runtime (app/routes.py + app/schemas.py).
 * Every getter falls back to the mock module when the API is unreachable —
 * the offline-demo doctrine: the UI never hard-fails.
 *
 * Base URL: import.meta.env.VITE_API_BASE, defaulting to "" (same-origin —
 * the FastAPI process serves this dist at /, so relative /api requests are
 * the path that works from a browser; the API has no CORS middleware).
 * The vite dev/preview proxy forwards /api → the API. */

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");
const TIMEOUT_MS = 3500;

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
  rule_probs: Record<string, number>;
  well_control: boolean;
  evidence_spans: { start: number; end: number; text: string }[];
  gate_states: GateState[];
  model_version: string;
  chunked?: boolean;
  explanation?: ExplanationOut | null;
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

/** Review-priority band (D14) derived from the calibrated score — the API
 *  contract carries no band. Thresholds match the server's gray band
 *  [0.40, 0.60] and the demo fixtures. */
export function bandFor(score: number): Band {
  return score >= 0.7 ? "HIGH" : score >= 0.4 ? "MODERATE" : "LOW";
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
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
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
    }))
    .sort((a, b) => b.prob - a.prob);
  for (const [code, m] of Object.entries(meta)) {
    if (!m.in_scope) rules.push({ code, name: m.display, prob: 0, in_scope: false });
  }
  return {
    sif_score: p.sif_score,
    band: bandFor(p.sif_score),
    latency_ms: 0,
    rules,
    well_control: p.well_control,
    evidence_spans: p.evidence_spans,
    gate_states: p.gate_states,
    model_version: p.model_version,
    chunked: p.chunked ?? false,
    explanation: p.explanation ?? null,
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

/* ---- Endpoints ---- */

/** GET /api/health — null when unreachable (badge + fallback trigger). */
export async function getHealth(): Promise<HealthOut | null> {
  try {
    const h = await req<HealthOut>("/api/health");
    return h.status === "ok" ? h : null;
  } catch {
    return null;
  }
}

/** GET /api/rules — all 9 IOGP rules; refreshes the live display metadata. */
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

/** GET /api/reports — the feed. Reports without predictions are dropped. */
export async function getReports(limit = 200): Promise<Report[]> {
  try {
    await getRules();
    const rows = await req<ApiStoredReport[]>(`/api/reports?limit=${limit}`);
    return rows
      .map(adaptReport)
      .filter((r): r is Report => r !== null);
  } catch {
    return REPORTS;
  }
}

/** GET /api/reports/{id}. */
export async function getReport(id: number): Promise<Report | null> {
  try {
    return adaptReport(await req<ApiStoredReport>(`/api/reports/${id}`));
  } catch {
    return REPORTS.find((r) => r.id === id) ?? null;
  }
}

/** POST /api/classify — stateless single-report triage (latency measured
 *  client-side). opts.explain bundles the deterministic explanation template
 *  (llm=0: a cold ollama reword on novel text would stall the card for
 *  seconds — the template is the demo-safe floor). Offline: an all-gray
 *  placeholder, never a fake score. */
export async function classify(
  text: string,
  opts?: { explain?: boolean },
): Promise<PredictionOut> {
  const t0 = performance.now();
  const query = opts?.explain ? "?explain=1&llm=0" : "";
  try {
    const p = await req<ApiPredictionOut>(`/api/classify${query}`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    return { ...adaptPrediction(p), latency_ms: Math.round(performance.now() - t0) };
  } catch {
    return {
      sif_score: 0.5,
      band: "MODERATE",
      latency_ms: 0,
      rules: [],
      well_control: false,
      evidence_spans: [],
      gate_states: [
        {
          name: "confidence",
          triggered: true,
          detail: "API unreachable — offline demo mode",
          action: "gray",
        },
      ],
      model_version: "offline",
      chunked: false,
      explanation: null,
    };
  }
}

/** POST /api/ingest — persist + classify a batch of raw records. Throws when
 *  the API is unreachable (callers fall back to the scripted mock beat). */
export async function ingest(
  records: Record<string, unknown>[],
): Promise<IngestResult> {
  return req<IngestResult>("/api/ingest", {
    method: "POST",
    body: JSON.stringify({ records, source: "dashboard" }),
  });
}

/** POST /api/ingest with a CSV body — the bulk-upload demo path (the server
 *  maps narrative/description/report aliases onto the text column). Throws
 *  when the API is unreachable. */
export async function ingestCsv(csv: string): Promise<IngestResult> {
  return req<IngestResult>("/api/ingest", {
    method: "POST",
    body: JSON.stringify({ csv, source: "dashboard" }),
  });
}

/** GET /api/reports/{id}/explanation — fetched lazily when the triage-card
 *  expander opens (never blocks the card). A cold call pays one bounded
 *  ollama attempt server-side (8s cap), so the client waits up to 12s;
 *  cached/template answers return in ms. null when unreachable, missing,
 *  or the report has no prediction — the caller then hides the section. */
export async function getExplanation(reportId: number): Promise<ExplanationOut | null> {
  try {
    return await req<ExplanationOut>(`/api/reports/${reportId}/explanation`, undefined, 12_000);
  } catch {
    return MOCK_EXPLANATIONS[reportId] ?? null;
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
  } catch {
    return prev ?? DENSITY_BEFORE;
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
  } catch {
    return PATTERNS.filter((p) => p.kind === kind);
  }
}

/** GET /api/review — the override queue (future gold labels). */
export async function getOverrides(reportId?: number): Promise<OverrideOut[]> {
  try {
    const q = reportId === undefined ? "" : `?report_id=${reportId}`;
    const rows = await req<ApiStoredOverride[]>(`/api/review${q}`);
    return rows.map(adaptOverride);
  } catch {
    return OVERRIDES;
  }
}

/** POST /api/review — "model proposes, HSE disposes". Throws when offline. */
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
    body: JSON.stringify({ labeler: "hse_reviewer", ...input }),
  });
  return adaptOverride(o);
}

/** GET /api/metrics/summary — null when unreachable. */
export async function getMetricsSummary(): Promise<MetricsSummary | null> {
  try {
    return await req<MetricsSummary>("/api/metrics/summary");
  } catch {
    return null;
  }
}
