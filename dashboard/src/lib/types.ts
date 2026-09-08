/*
 * TS mirrors of the FastAPI pydantic models in app/schemas.py — the runtime
 * contract. Field names follow the API (sif_score, rule_probs, well_control,
 * evidence_spans, gate_states, model_version). Presentation-only additions
 * (band, latency_ms, explanation, rank/prev_rank) are derived client-side in
 * api.ts. Endpoints: POST /api/classify, POST /api/ingest, GET /api/reports,
 * GET /api/reports/{id}, GET /api/density, GET /api/rules, GET /api/patterns,
 * GET|POST /api/review, GET /api/metrics/summary, GET /api/health.
 */

/** Band semantics per D14: "review priority" band, never "%", never red.
 *  Derived client-side from sif_score (the API returns no band). */
export type Band = "HIGH" | "MODERATE" | "LOW";

/** The 6 Sentinel input gates (app/gates.py). triggered=true means "routed
 *  to review, never auto-cleared" — gates annotate, they never block. */
export type GateKind =
  | "min_length"
  | "negation"
  | "language"
  | "confidence"
  | "drill"
  | "near_dup";

export interface GateState {
  name: GateKind;
  triggered: boolean;
  detail: string;
}

/** Char offsets are computed server-side against canonical text and
 *  self-validated (text[start:end] === span text) before render. UI only slices. */
export interface EvidenceSpan {
  start: number;
  end: number;
  text: string;
}

/** IOGP Life-Saving Rule score, adapted from the API's rule_probs map.
 *  PTW + Bypassing are declared out-of-scope (<0.1% detectable) — shown as
 *  such, never faked. */
export interface RuleScore {
  code: string;
  name: string;
  prob: number;
  in_scope: boolean;
}

/** API PredictionOut (app/schemas.py) + client-derived presentation fields. */
export interface PredictionOut {
  sif_score: number; // calibrated triage score; labeled "triage score"
  band: Band; // derived in api.ts — the API contract carries no band
  latency_ms: number; // measured around POST /classify; 0 for stored reports
  rules: RuleScore[]; // 7 in-scope from rule_probs + 2 declared out-of-scope
  well_control: boolean; // deterministic Baghjan-class barrier tag
  evidence_spans: EvidenceSpan[];
  gate_states: GateState[];
  model_version: string;
  explanation: string; // deterministic template; "" until the renderer ships
}

/** API StoredReport flattened for the UI: id is the server row id (int). */
export interface Report {
  id: number;
  text: string;
  site: string;
  activity: string;
  contractor: string | null;
  reported_at: string; // ISO date
  prediction: PredictionOut;
}

/** GET /api/density row. rank/prev_rank are derived client-side: rank is the
 *  position in the sorted response, prev_rank the rank in the previous
 *  snapshot (the re-rank FLIP beat). */
export interface DensityRow {
  key: string; // site / activity / contractor label
  n_reports: number;
  n_flagged: number;
  sif_rate: number; // 0..1
  mean_score: number;
  rank: number;
  prev_rank: number;
}

/** GET /api/patterns row — lift-ranked activity × site co-occurrence,
 *  n + Wilson CI. id is assigned client-side for list keys. */
export interface PatternOut {
  id: string;
  activity: string;
  site: string;
  n: number;
  sif_rate: number;
  lift: number;
  ci_low: number;
  ci_high: number;
}

/** POST /api/review payload / review-queue row (StoredOverride).
 *  Overrides become future gold labels. ts mirrors created_at. */
export interface OverrideOut {
  id: number;
  report_id: number;
  field: string;
  old_value: string | null;
  new_value: string;
  labeler: string;
  source: "override" | "blind_gold";
  ts: string;
}

/** GET /api/rules row — all 9 IOGP rules; out-of-scope declared, never faked. */
export interface RuleInfo {
  key: string;
  display: string;
  in_scope: boolean;
  threshold: number | null;
}

export interface IngestError {
  row: number;
  error: string;
}

export interface IngestResult {
  received: number;
  accepted: number;
  rejected: number;
  report_ids: number[];
  errors: IngestError[];
}

export interface MetricsSummary {
  n_reports: number;
  n_flagged: number;
  flag_rate: number;
  mean_score: number;
  n_overrides: number;
  gate_trigger_counts: Record<string, number>;
  model_version: string;
  classifier: string;
}

export interface HealthOut {
  status: string;
  api_version: string;
  model_version: string;
  classifier: string;
  n_reports: number;
  n_overrides: number;
}
