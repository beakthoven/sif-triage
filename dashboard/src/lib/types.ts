/*
 * TS mirrors of the FastAPI pydantic models in app/schemas.py — the runtime
 * contract. Field names follow the API (sif_score, rule_probs, well_control,
 * evidence_spans, gate_states, model_version). Presentation-only additions
 * (latency_ms, explanation, rank/prev_rank) are derived client-side in api.ts.
 * Endpoints: POST /api/classify, POST /api/ingest, GET /api/ingest/{job_id},
 * GET /api/reports, GET /api/reports/{id}, GET /api/reports/{id}/explanation,
 * GET /api/density, GET /api/rules, GET /api/patterns?kind=, GET|POST
 * /api/review, GET /api/metrics/summary, GET /api/health.
 *
 * Workstream A additions (self-consistency + barrier gates + operating point)
 * are OPTIONAL fields on PredictionOut: absence means "not measured", never
 * fabricate a value. The ingest job endpoints LANDED (verified in
 * app/routes.py this session): POST /api/ingest answers 202 IngestJobAccepted
 * above INGEST_SYNC_MAX_ROWS (100) and GET /api/ingest/{job_id} serves
 * IngestJobStatus — IngestJob below mirrors that poll body.
 */

/** Review-priority band. The SERVER owns the operating point (Workstream A4):
 *  the client-side bandFor() derivation was deleted — band arrives from the
 *  API when the server contract carries it, and is undefined otherwise. */
export type Band = "HIGH" | "MODERATE" | "LOW";

/** General input gates (app/gates.py). action decides the UI: "gray" routes
 *  to human review (never auto-cleared); "badge" annotates the triage card
 *  only (near_dup banner, chunked); "block" is reserved. */
export type GateKind =
  | "min_length"
  | "negation"
  | "language"
  | "confidence"
  | "drill"
  | "near_dup"
  | "long_input"
  | "well_control_watch"
  | "chunked_low_score"
  | "severity_watch"
  | "verdict_stability";

/** Barrier-failure gate family (Workstream A2). These fire on explicit
 *  ABSENCE of control language (LOTO not applied, no gas test, no permit…). */
export type BarrierGateKind =
  | "energy_isolation_absent"
  | "gas_test_absent"
  | "permit_absent"
  | "fire_watch_absent"
  | "standby_absent"
  | "atmosphere_unmonitored"
  | "fall_protection_absent";

/** GET /api/clusters?min_cos=0.91 — server-owned star groups. */
export interface ClusterOut {
  exemplar_id: number;
  member_ids: number[];
  n: number;
  reviewed_member_ids: number[];
  max_cos: number;
}

export interface ClustersOut {
  threshold: number;
  n_scored: number;
  n_skipped: number;
  dim: number;
  n_clusters: number;
  n_members: number;
  clusters: ClusterOut[];
}

export type GateAction = "badge" | "gray" | "block";

export interface GateState {
  /** Wire: a free string (app/schemas.py GateState.name: str). The union
   *  covers every gate the runtime emits today — 11 general gates plus the
   *  seven barrier-failure gates (app/gates.py dispatch) — so
   *  barrier names type-check. UNKNOWN future names
   *  can still arrive on the wire: render gate names only via gateCopyFor()
   *  (lib/phrasebook.ts, safe fallback), never via an exhaustive
   *  Record<GateKind, …> lookup, and never crash on an unseen name. */
  name: GateKind | BarrierGateKind;
  triggered: boolean;
  detail: string;
  action: GateAction;
}

/** Server agreement fraction (Workstream A3): the fraction of scored
 *  variants whose verdict agrees with the mean-score verdict (0..1). UI
 *  stability words are derived from this number where needed. */
export type VerdictStability = number;

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
  cue_hit: boolean | null;
}

/** GET /api/reports/{id}/explanation (app/explain.py). The template is
 *  deterministic and always present; reworded is the optional Ollama
 *  rewording (null whenever the LLM is down or failed validation). */
export interface ExplanationOut {
  template: string;
  reworded: string | null;
  spans_quoted: string[];
  source: "template" | "ollama";
  cached: boolean;
  model_version: string;
}

/** API PredictionOut (app/schemas.py) + client-measured latency only. The
 *  optional A-series fields are server-owned; absence means not measured. */
export interface PredictionOut {
  sif_score: number; // calibrated triage score; labeled "triage score"
  score_spread?: number | null; // spread across variant scores (A3)
  n_variants?: number | null; // N scored surface variants (A3)
  variant_scores?: number[] | null; // per-variant raw scores (A3)
  verdict_stability?: VerdictStability | null; // fraction of variant verdicts in agreement (A3)
  band?: Band | null; // server-owned review-priority band (A4); never derived client-side
  flag_threshold?: number | null; // server-owned operating point (A4)
  gray_band_low?: number | null; // server-owned review band floor (A4)
  gray_band_high?: number | null; // server-owned review band ceiling (A4)
  rule_cue_hits?: Record<string, boolean> | null; // conservative text cue matches, when computed
  latency_ms: number; // measured around POST /classify; 0 for stored reports
  rules: RuleScore[]; // 7 in-scope from rule_probs + 2 declared out-of-scope
  well_control: boolean; // deterministic well-control barrier tag
  evidence_spans: EvidenceSpan[];
  gate_states: GateState[];
  model_version: string;
  chunked: boolean; // long input overflowed seq_len — sliding-window path ran
  explanation: ExplanationOut | null; // only via /classify?explain=1; else fetched on expand
  report_id?: number | null; // server row id, only via /classify?persist=1 (paste flow)
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

/** GET /api/patterns row — lift-ranked co-occurrence with n + Wilson CI.
 *  kind=site_activity: activity × site cell (barrier null).
 *  kind=activity_barrier: activity × barrier cell (site null).
 *  rule = dominant IOGP rule tag. id is assigned client-side for list keys. */
export type PatternKind = "site_activity" | "activity_barrier";

export interface PatternOut {
  id: string;
  kind: PatternKind;
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

/** POST /api/review payload / review-queue row (StoredOverride).
 *  Overrides become future gold labels. ts mirrors created_at. rationale is
 *  part of the wire contract (OverrideIn) and must survive the round trip —
 *  it is the audit-trail answer to "why was the model overruled". */
export interface OverrideOut {
  id: number;
  report_id: number;
  field: string;
  old_value: string | null;
  new_value: string;
  labeler: string;
  rationale: string | null;
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

/** POST /api/ingest, 200 shape (app/routes.py IngestResult): payloads up to
 *  INGEST_SYNC_MAX_ROWS (100 unique rows) and every idempotent replay finish
 *  synchronously. Larger payloads answer 202 + an IngestJob id instead —
 *  poll GET /api/ingest/{job_id} (IngestJob below). */
export interface IngestResult {
  received: number;
  accepted: number;
  rejected: number;
  report_ids: number[];
  errors: IngestError[];
  skipped_duplicates: number;
  idempotent_replay: boolean;
}

/** GET /api/ingest/{job_id} poll body — exact mirror of app/routes.py's
 *  IngestJobStatus (verified in routes.py this session). status walks
 *  queued → running → done | error; done/total are the truthful classify
 *  progress; accepted/rejected/skipped_duplicates/errors/report_ids carry
 *  the honest final outcome (populated at status=done). detail is non-null
 *  ONLY on error — the whole batch rolled back and NOTHING was stored, so a
 *  retry is safe (payload-hash replay dedups). 404 on poll = unknown id /
 *  TTL eviction / server restart; re-POSTing the payload is safe either way.
 *  The ingest wire is owned by features/ingest/ingest-api.ts +
 *  use-ingest-job.ts; lib carries only this type mirror. */
export interface IngestJob {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  received: number;
  total: number;
  done: number;
  accepted: number;
  rejected: number;
  skipped_duplicates: number;
  errors: IngestError[];
  report_ids: number[] | null;
  detail: string | null;
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
  ece?: number | null;
  brier?: number | null;
  calibration_n?: number | null;
  calibration_split?: string | null;
  flag_threshold?: number | null;
  gray_band_low?: number | null;
  gray_band_high?: number | null;
}

export interface HealthOut {
  status: string;
  api_version: string;
  model_version: string;
  classifier: string;
  n_reports: number;
  n_overrides: number;
}