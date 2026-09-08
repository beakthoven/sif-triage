/*
 * TS mirrors of the FastAPI pydantic models (runtime contract).
 * Endpoints (fullstack-architect §3): POST /classify, POST /ingest,
 * GET /reports, GET /reports/{id}, GET /rankings/density, GET /patterns,
 * POST /overrides, GET /overrides/export.csv, GET /metrics.
 * When the API lands, replace the mock module with fetch calls — shapes stay.
 */

/** Band semantics per D14: "review priority" band, never "%", never red. */
export type Band = "HIGH" | "MODERATE" | "LOW";

/** The 4 engineered gray states ("Sentinel gates") — routed to review, never auto-cleared. */
export type GateKind = "low_confidence" | "negation" | "language" | "near_dup";

/** Char offsets are computed server-side against canonical text and
 *  self-validated (text[start:end] === span text) before render. UI only slices. */
export interface EvidenceSpan {
  start: number;
  end: number;
  text: string;
}

/** IOGP Life-Saving Rule score. PTW + Bypassing are declared out-of-scope
 *  (<0.1% detectable) — shown as such, never faked. */
export interface RuleScore {
  code: string;
  name: string;
  prob: number;
  in_scope: boolean;
}

/** POST /classify response — also embedded in each report detail. */
export interface PredictionOut {
  triage_score: number; // calibrated, temperature-scaled; labeled "triage score"
  band: Band;
  latency_ms: number;
  rules: RuleScore[];
  well_control_tag: boolean; // deterministic Baghjan-class barrier tag
  spans: EvidenceSpan[];
  gates: GateKind[];
  explanation: string; // deterministic template (LLM reword is optional)
}

export interface Report {
  id: string;
  text: string;
  site: string;
  activity: string;
  contractor: string | null;
  reported_at: string; // ISO date
  prediction: PredictionOut;
}

/** GET /rankings/density?by=site|activity row. */
export interface DensityRow {
  key: string; // site or activity label
  n_reports: number;
  n_flagged: number;
  flag_rate: number; // 0..1
  rank: number;
  prev_rank: number;
}

/** GET /patterns row — lift-ranked facet co-occurrence, n + Wilson CI. */
export interface PatternOut {
  id: string;
  sentence: string; // one plain sentence, e.g. "LINE OF FIRE × drill floor × missing barricade"
  n: number;
  lift: number;
  ci_low: number;
  ci_high: number;
  window_days: number;
}

/** POST /overrides payload / review-queue row. Overrides become future gold labels. */
export interface OverrideOut {
  report_id: string;
  field: string;
  old_value: string;
  new_value: string;
  labeler: string;
  source: "override" | "blind_gold";
  ts: string;
}
