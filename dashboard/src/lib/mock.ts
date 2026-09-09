import type {
  DensityRow,
  EvidenceSpan,
  ExplanationOut,
  GateAction,
  GateKind,
  GateState,
  OverrideOut,
  PatternOut,
  Report,
  RuleScore,
} from "./types";

/* Offline-demo fallback data (the "UI never hard-fails" doctrine). Shapes
 * match the reconciled API contract in types.ts — api.ts falls back to this
 * module whenever the API is unreachable.
 *
 * Span offsets are computed by construction (indexOf) and validated below —
 * the UI only slices, never computes offsets (server contract). */

function spanify(text: string, needles: string[]): EvidenceSpan[] {
  return needles
    .map((n) => {
      const start = text.indexOf(n);
      if (start < 0) throw new Error(`mock span not found: "${n}"`);
      return { start, end: start + n.length, text: n };
    })
    .sort((a, b) => a.start - b.start);
}

function rules(top: [string, string, number][], ...outOfScope: string[]): RuleScore[] {
  const scoped = top.map(([code, name, prob]) => ({
    code,
    name,
    prob,
    in_scope: true,
  }));
  const oos = outOfScope.map((name) => ({
    code: "OOS",
    name,
    prob: 0,
    in_scope: false,
  }));
  return [...scoped, ...oos];
}

const PTW_BYPASS_OOS: string[] = [
  "Work Authorisation (Permit to Work)",
  "Bypassing Safety Controls",
];

const ALL_GATES: GateKind[] = [
  "min_length",
  "negation",
  "language",
  "confidence",
  "drill",
  "near_dup",
  "long_input",
  "well_control_watch",
  "chunked_low_score",
];

/** Mirrors app/gates.py: near_dup + long_input are badge-only (annotate the
 *  triage card); the rest route to the gray review queue when triggered. */
const GATE_ACTIONS: Record<GateKind, GateAction> = {
  min_length: "gray",
  negation: "gray",
  language: "gray",
  confidence: "gray",
  drill: "gray",
  near_dup: "badge",
  long_input: "badge",
  well_control_watch: "gray",
  chunked_low_score: "gray",
};

function gateStates(...triggered: GateKind[]): GateState[] {
  return ALL_GATES.map((name) => ({
    name,
    triggered: triggered.includes(name),
    detail: triggered.includes(name) ? "offline demo fixture" : "",
    action: GATE_ACTIONS[name],
  }));
}

const R1_TEXT =
  "During pulling operations on Well DJS-142, the derrickhand dropped a spanner " +
  "from the monkey board, falling above the occupied drill floor, landing 1 m from " +
  "the floorman who was making connections. No barricade or dropped-object netting " +
  "was in place below the derrick.";

const R2_TEXT =
  "While pulling the BOP before cement had fully set on Well BGN-11, returns " +
  "increased at the flowline and gas was detected at the shale shakers. The well " +
  "was shut in and mud weight raised. The workover window had been reduced from " +
  "48 h to 12 h earlier that week.";

const R3_TEXT =
  "Patrol found a pinhole leak weeping crude on the 4-inch flowline near the " +
  "manifold at GGS-2. The area was not barricaded and the spill kit was missing " +
  "from its station. The line was isolated and clamped the same shift.";

const R4_TEXT =
  "Storekeeper slipped on an oil patch near the drum storage rack at the " +
  "Naharkatia warehouse and caught himself on the racking. Area was cleaned and " +
  "absorbent laid the same shift.";

const G1_TEXT =
  "Worker mentioned something unusual near the manifold area during the shift. " +
  "Details unclear, follow-up requested.";

const G2_TEXT =
  "No injury and no damage occurred when the sling slipped while lifting a casing " +
  "pup joint at the Rig #3 pipe yard. The load settled back onto the rack.";

const G3_TEXT =
  "गीजीएस-2 के पास पाइपलाइन से रिसाव देखा गया। क्षेत्र को बैरिकेड नहीं किया गया था " +
  "और स्पिल किट अपने स्थान पर नहीं थी।";

const G4_TEXT =
  "During pulling operations on Well DJS-142, the derrickhand dropped a spanner " +
  "from the monkey board, falling above the occupied drill floor, landing about a " +
  "metre from the floorman on shift.";

const R5_TEXT =
  "During the night shift at the Moran GGS-1 compressor station, the operations " +
  "crew carried out a scheduled pigging run on the 8-inch condensate line. Before " +
  "launching, the receiver isolation valve was found passing, so the crew bled " +
  "the trapped pressure to the flare and re-seated the valve. While the pig was " +
  "in transit, the line pressure trend showed two unexplained drops, each " +
  "recovering within ten minutes. On arrival, the pig brought out heavy wax and " +
  "a piece of gasket material that did not match any flange on the launcher. The " +
  "crew walked the line with a gas detector and found a faint reading near the " +
  "road crossing sleeve, but no visible seep. The sleeve was excavated the next " +
  "morning and the coating was found disbonded over a length of about one metre, " +
  "with shallow external corrosion pitting underneath. The line was kept in " +
  "service at reduced pressure pending a sleeve repair, and the finding was " +
  "logged for the integrity review board with a recommendation to add the " +
  "crossing to the annual close-interval survey.";

/** Offline fallback for GET /api/reports/{id}/explanation (app/explain.py
 *  shape): the deterministic template is always present; the reworded
 *  paragraph demonstrates the optional Ollama path (source/cached honest). */
export const MOCK_EXPLANATIONS: Record<number, ExplanationOut> = {
  2614: {
    template:
      "Triage score 0.87 — flagged for HSE review.\n" +
      "IOGP rules implicated: Line of Fire (0.91), Working at Height (0.64).\n" +
      'Evidence phrases: "above the occupied drill floor", "1 m from the floorman", "No barricade or dropped-object netting".',
    reworded:
      "This report is flagged for HSE review with a triage score of 0.87. The " +
      "implicated IOGP rules are Line of Fire (0.91) and Working at Height " +
      '(0.64), supported by the evidence phrases "above the occupied drill ' +
      'floor" and "1 m from the floorman".',
    spans_quoted: ["above the occupied drill floor", "1 m from the floorman"],
    source: "ollama",
    cached: true,
    model_version: "mock-0.1.0",
  },
  2601: {
    template:
      "Triage score 0.74 — flagged for HSE review.\n" +
      "IOGP rules implicated: Energy Isolation (0.55).\n" +
      "Well-control/barrier tag: raised.\n" +
      'Evidence phrases: "pulling the BOP before cement had fully set", "gas was detected at the shale shakers", "reduced from 48 h to 12 h".',
    reworded: null,
    spans_quoted: [
      "pulling the BOP before cement had fully set",
      "gas was detected at the shale shakers",
      "reduced from 48 h to 12 h",
    ],
    source: "template",
    cached: true,
    model_version: "mock-0.1.0",
  },
  2597: {
    template:
      "Triage score 0.62 — flagged for HSE review.\n" +
      "IOGP rules implicated: Energy Isolation (0.58).\n" +
      'Evidence phrases: "pinhole leak weeping crude", "not barricaded".',
    reworded: null,
    spans_quoted: ["pinhole leak weeping crude", "not barricaded"],
    source: "template",
    cached: true,
    model_version: "mock-0.1.0",
  },
  2588: {
    template:
      "Triage score 0.18 — below the review threshold.\n" +
      "No IOGP rule crossed its display threshold.\n" +
      "Evidence phrases: none extracted.",
    reworded: null,
    spans_quoted: [],
    source: "template",
    cached: true,
    model_version: "mock-0.1.0",
  },
  2615: {
    template:
      "Triage score 0.85 — flagged for HSE review.\n" +
      "IOGP rules implicated: Line of Fire (0.90).\n" +
      'Evidence phrases: "above the occupied drill floor".\n' +
      "Advisory gates: near_dup (matches a training record — memory, not generalization).",
    reworded: null,
    spans_quoted: ["above the occupied drill floor"],
    source: "template",
    cached: true,
    model_version: "mock-0.1.0",
  },
  2619: {
    template:
      "Triage score 0.44 — flagged for HSE review.\n" +
      "IOGP rules implicated: Energy Isolation (0.51).\n" +
      'Evidence phrases: "receiver isolation valve was found passing".\n' +
      "Advisory gates: long_input (chunked: 173 words > 120; sliding-window max-pool applies).",
    reworded: null,
    spans_quoted: ["receiver isolation valve was found passing"],
    source: "template",
    cached: true,
    model_version: "mock-0.1.0",
  },
};

export const REPORTS: Report[] = [
  {
    id: 2614,
    text: R1_TEXT,
    site: "Duliajan — Workover Rig #7",
    activity: "Workover operations",
    contractor: "DeepWell Services",
    reported_at: "2026-09-06",
    prediction: {
      sif_score: 0.87,
      band: "HIGH",
      latency_ms: 38,
      rules: rules(
        [
          ["line_of_fire", "Line of Fire", 0.91],
          ["working_at_height", "Working at Height", 0.64],
        ],
        ...PTW_BYPASS_OOS,
      ),
      well_control: false,
      evidence_spans: spanify(R1_TEXT, [
        "above the occupied drill floor",
        "1 m from the floorman",
        "No barricade or dropped-object netting",
      ]),
      gate_states: gateStates(),
      model_version: "mock-0.1.0",
      chunked: false,
      explanation: MOCK_EXPLANATIONS[2614],
    },
  },
  {
    id: 2601,
    text: R2_TEXT,
    site: "Baghjan EPS",
    activity: "Well servicing",
    contractor: null,
    reported_at: "2026-09-04",
    prediction: {
      sif_score: 0.74,
      band: "HIGH",
      latency_ms: 41,
      rules: rules(
        [
          ["energy_isolation", "Energy Isolation", 0.55],
          ["line_of_fire", "Line of Fire", 0.41],
        ],
        ...PTW_BYPASS_OOS,
      ),
      well_control: true,
      evidence_spans: spanify(R2_TEXT, [
        "pulling the BOP before cement had fully set",
        "gas was detected at the shale shakers",
        "reduced from 48 h to 12 h",
      ]),
      gate_states: gateStates(),
      model_version: "mock-0.1.0",
      chunked: false,
      explanation: MOCK_EXPLANATIONS[2601],
    },
  },
  {
    id: 2597,
    text: R3_TEXT,
    site: "GGS-2, Duliajan",
    activity: "Flowline patrol",
    contractor: "Pipeline O&M Crew",
    reported_at: "2026-09-03",
    prediction: {
      sif_score: 0.62,
      band: "MODERATE",
      latency_ms: 35,
      rules: rules(
        [
          ["energy_isolation", "Energy Isolation", 0.58],
          ["confined_space", "Confined Space", 0.22],
        ],
        ...PTW_BYPASS_OOS,
      ),
      well_control: false,
      evidence_spans: spanify(R3_TEXT, ["pinhole leak weeping crude", "not barricaded"]),
      gate_states: gateStates(),
      model_version: "mock-0.1.0",
      chunked: false,
      explanation: MOCK_EXPLANATIONS[2597],
    },
  },
  {
    id: 2588,
    text: R4_TEXT,
    site: "Naharkatia Warehouse",
    activity: "Material handling",
    contractor: null,
    reported_at: "2026-09-02",
    prediction: {
      sif_score: 0.18,
      band: "LOW",
      latency_ms: 31,
      rules: rules([["safe_mechanical_lifting", "Safe Mechanical Lifting", 0.12]], ...PTW_BYPASS_OOS),
      well_control: false,
      evidence_spans: [],
      gate_states: gateStates(),
      model_version: "mock-0.1.0",
      chunked: false,
      explanation: MOCK_EXPLANATIONS[2588],
    },
  },
  {
    id: 2616,
    text: G1_TEXT,
    site: "GGS-2, Duliajan",
    activity: "Flowline patrol",
    contractor: null,
    reported_at: "2026-09-06",
    prediction: {
      sif_score: 0.41,
      band: "MODERATE",
      latency_ms: 33,
      rules: rules([["line_of_fire", "Line of Fire", 0.38]], ...PTW_BYPASS_OOS),
      well_control: false,
      evidence_spans: [],
      gate_states: gateStates("confidence"),
      model_version: "mock-0.1.0",
      chunked: false,
      explanation: null,
    },
  },
  {
    id: 2610,
    text: G2_TEXT,
    site: "Tengakhat — Rig #3 pipe yard",
    activity: "Lifting operations",
    contractor: "DeepWell Services",
    reported_at: "2026-09-05",
    prediction: {
      sif_score: 0.66,
      band: "MODERATE",
      latency_ms: 36,
      rules: rules([["safe_mechanical_lifting", "Safe Mechanical Lifting", 0.72]], ...PTW_BYPASS_OOS),
      well_control: false,
      evidence_spans: spanify(G2_TEXT, ["sling slipped while lifting a casing"]),
      gate_states: gateStates("negation"),
      model_version: "mock-0.1.0",
      chunked: false,
      explanation: null,
    },
  },
  {
    id: 2609,
    text: G3_TEXT,
    site: "GGS-2, Duliajan",
    activity: "Flowline patrol",
    contractor: null,
    reported_at: "2026-09-05",
    prediction: {
      sif_score: 0.6,
      band: "MODERATE",
      latency_ms: 44,
      rules: rules([["energy_isolation", "Energy Isolation", 0.52]], ...PTW_BYPASS_OOS),
      well_control: false,
      evidence_spans: [],
      gate_states: gateStates("language"),
      model_version: "mock-0.1.0",
      chunked: false,
      explanation: null,
    },
  },
  {
    id: 2615,
    text: G4_TEXT,
    site: "Duliajan — Workover Rig #7",
    activity: "Workover operations",
    contractor: "DeepWell Services",
    reported_at: "2026-09-06",
    prediction: {
      sif_score: 0.85,
      band: "HIGH",
      latency_ms: 37,
      rules: rules([["line_of_fire", "Line of Fire", 0.9]], ...PTW_BYPASS_OOS),
      well_control: false,
      evidence_spans: spanify(G4_TEXT, ["above the occupied drill floor"]),
      gate_states: gateStates("near_dup"),
      model_version: "mock-0.1.0",
      chunked: false,
      explanation: MOCK_EXPLANATIONS[2615],
    },
  },
  {
    id: 2619,
    text: R5_TEXT,
    site: "Moran GGS-1",
    activity: "Pipeline pigging",
    contractor: null,
    reported_at: "2026-09-07",
    prediction: {
      sif_score: 0.44,
      band: "MODERATE",
      latency_ms: 52,
      rules: rules(
        [["energy_isolation", "Energy Isolation", 0.51]],
        ...PTW_BYPASS_OOS,
      ),
      well_control: false,
      evidence_spans: spanify(R5_TEXT, ["receiver isolation valve was found passing"]),
      gate_states: gateStates("long_input"),
      model_version: "mock-0.1.0",
      chunked: true,
      explanation: MOCK_EXPLANATIONS[2619],
    },
  },
];

/* Invariant check — mirrors the server-side span self-validation contract.
 * Runs at module load; also runnable standalone: node src/lib/mock.ts */
function validateMock(): void {
  for (const r of REPORTS) {
    for (const s of r.prediction.evidence_spans) {
      if (r.text.slice(s.start, s.end) !== s.text) {
        throw new Error(
          `span offset mismatch in ${r.id}: [${s.start}:${s.end}]`,
        );
      }
    }
    const ex = r.prediction.explanation;
    if (ex) {
      if (!ex.template.trim()) throw new Error(`empty template in ${r.id}`);
      for (const q of ex.spans_quoted) {
        if (!r.text.includes(q)) {
          throw new Error(`explanation span not verbatim in ${r.id}: "${q}"`);
        }
      }
      if (ex.reworded && !ex.reworded.includes(r.prediction.sif_score.toFixed(2))) {
        throw new Error(`reworded explanation lost the triage score in ${r.id}`);
      }
    }
    if (r.prediction.chunked && r.text.split(/\s+/).length <= 120) {
      throw new Error(`chunked badge on a short report in ${r.id}`);
    }
  }
  for (const p of PATTERNS) {
    if (p.kind === "activity_barrier" && (p.site !== null || p.barrier === null)) {
      throw new Error(`activity_barrier row malformed: ${p.id}`);
    }
    if (p.kind === "site_activity" && p.site === null) {
      throw new Error(`site_activity row missing site: ${p.id}`);
    }
  }
  // Every mock explanation is attached to the report it describes.
  for (const id of Object.keys(MOCK_EXPLANATIONS)) {
    if (!REPORTS.some((r) => r.id === Number(id))) {
      throw new Error(`MOCK_EXPLANATIONS orphan: ${id}`);
    }
  }
}

/** Offline fallback for GET /api/density — two snapshots: prev (pre-ingest)
 *  and current (post-ingest re-rank). The demo beat: Baghjan EPS climbs to #1. */
export const DENSITY_BEFORE: DensityRow[] = [
  { key: "Duliajan — Workover Rig #7", n_reports: 128, n_flagged: 34, sif_rate: 0.266, mean_score: 0.312, rank: 1, prev_rank: 1 },
  { key: "GGS-2, Duliajan", n_reports: 96, n_flagged: 22, sif_rate: 0.229, mean_score: 0.287, rank: 2, prev_rank: 2 },
  { key: "Baghjan EPS", n_reports: 74, n_flagged: 16, sif_rate: 0.216, mean_score: 0.271, rank: 3, prev_rank: 3 },
  { key: "Moran GGS-1", n_reports: 61, n_flagged: 11, sif_rate: 0.18, mean_score: 0.244, rank: 4, prev_rank: 4 },
  { key: "Naharkatia Warehouse", n_reports: 88, n_flagged: 12, sif_rate: 0.136, mean_score: 0.208, rank: 5, prev_rank: 5 },
  { key: "Tengakhat — Rig #3 pipe yard", n_reports: 53, n_flagged: 7, sif_rate: 0.132, mean_score: 0.197, rank: 6, prev_rank: 6 },
];

export const DENSITY_AFTER: DensityRow[] = [
  { key: "Baghjan EPS", n_reports: 98, n_flagged: 32, sif_rate: 0.327, mean_score: 0.371, rank: 1, prev_rank: 3 },
  { key: "Duliajan — Workover Rig #7", n_reports: 141, n_flagged: 39, sif_rate: 0.277, mean_score: 0.322, rank: 2, prev_rank: 1 },
  { key: "GGS-2, Duliajan", n_reports: 108, n_flagged: 25, sif_rate: 0.231, mean_score: 0.289, rank: 3, prev_rank: 2 },
  { key: "Moran GGS-1", n_reports: 66, n_flagged: 12, sif_rate: 0.182, mean_score: 0.247, rank: 4, prev_rank: 4 },
  { key: "Tengakhat — Rig #3 pipe yard", n_reports: 71, n_flagged: 11, sif_rate: 0.155, mean_score: 0.221, rank: 5, prev_rank: 6 },
  { key: "Naharkatia Warehouse", n_reports: 93, n_flagged: 12, sif_rate: 0.129, mean_score: 0.203, rank: 6, prev_rank: 5 },
];

/** Offline fallback for GET /api/patterns?kind= — lift-ranked co-occurrence
 *  with n + Wilson CI. site_activity: activity × site; activity_barrier:
 *  activity × barrier (site null), rule = dominant IOGP rule tag. */
export const PATTERNS: PatternOut[] = [
  { id: "site_activity-1", kind: "site_activity", activity: "Workover operations", site: "Duliajan — Workover Rig #7", barrier: null, rule: "line_of_fire", n: 14, sif_rate: 0.43, lift: 3.2, ci_low: 0.31, ci_high: 0.58 },
  { id: "site_activity-2", kind: "site_activity", activity: "Well servicing", site: "Baghjan EPS", barrier: null, rule: "energy_isolation", n: 11, sif_rate: 0.38, lift: 2.8, ci_low: 0.24, ci_high: 0.49 },
  { id: "site_activity-3", kind: "site_activity", activity: "Flowline patrol", site: "GGS-2, Duliajan", barrier: null, rule: "energy_isolation", n: 9, sif_rate: 0.32, lift: 2.4, ci_low: 0.18, ci_high: 0.41 },
  { id: "site_activity-4", kind: "site_activity", activity: "Lifting operations", site: "Tengakhat — Rig #3 pipe yard", barrier: null, rule: "safe_mechanical_lifting", n: 7, sif_rate: 0.27, lift: 2.1, ci_low: 0.12, ci_high: 0.33 },
  { id: "site_activity-5", kind: "site_activity", activity: "Hot work", site: "Moran GGS-1", barrier: null, rule: "hot_work", n: 5, sif_rate: 0.24, lift: 1.9, ci_low: 0.08, ci_high: 0.29 },
  { id: "activity_barrier-1", kind: "activity_barrier", activity: "Well servicing", site: null, barrier: "BOP function test overdue", rule: "energy_isolation", n: 16, sif_rate: 0.44, lift: 3.4, ci_low: 0.33, ci_high: 0.6 },
  { id: "activity_barrier-2", kind: "activity_barrier", activity: "Workover operations", site: null, barrier: "Dropped-object zone not barricaded", rule: "line_of_fire", n: 13, sif_rate: 0.39, lift: 3.0, ci_low: 0.27, ci_high: 0.55 },
  { id: "activity_barrier-3", kind: "activity_barrier", activity: "Lifting operations", site: null, barrier: "Sling inspection lapsed", rule: "safe_mechanical_lifting", n: 10, sif_rate: 0.31, lift: 2.5, ci_low: 0.19, ci_high: 0.46 },
  { id: "activity_barrier-4", kind: "activity_barrier", activity: "Flowline patrol", site: null, barrier: "Spill kit missing at station", rule: "energy_isolation", n: 8, sif_rate: 0.28, lift: 2.2, ci_low: 0.15, ci_high: 0.42 },
  { id: "activity_barrier-5", kind: "activity_barrier", activity: "Hot work", site: null, barrier: "Gas test not repeated after break", rule: "hot_work", n: 6, sif_rate: 0.25, lift: 2.0, ci_low: 0.1, ci_high: 0.38 },
];

/** Offline fallback for GET /api/review — overrides already logged
 *  (→ future gold labels). */
export const OVERRIDES: OverrideOut[] = [
  {
    id: 1,
    report_id: 2410,
    field: "sif_label",
    old_value: "not_sif_potential",
    new_value: "sif_potential",
    labeler: "hse.kgohain",
    source: "override",
    ts: "2026-09-05T14:22:10+05:30",
  },
  {
    id: 2,
    report_id: 2566,
    field: "sif_label",
    old_value: "MODERATE",
    new_value: "HIGH",
    labeler: "hse.rbora",
    source: "override",
    ts: "2026-09-06T09:41:03+05:30",
  },
  {
    id: 3,
    report_id: 2579,
    field: "line_of_fire",
    old_value: "Safe Mechanical Lifting",
    new_value: "Line of Fire",
    labeler: "hse.kgohain",
    source: "override",
    ts: "2026-09-06T11:07:55+05:30",
  },
];

validateMock();
