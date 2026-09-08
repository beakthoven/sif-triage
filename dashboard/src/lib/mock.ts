import type {
  DensityRow,
  EvidenceSpan,
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
];

function gateStates(...triggered: GateKind[]): GateState[] {
  return ALL_GATES.map((name) => ({
    name,
    triggered: triggered.includes(name),
    detail: triggered.includes(name) ? "offline demo fixture" : "",
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
      explanation:
        "Dropped object from the derrick into an occupied area with no exclusion " +
        "zone below — classic Line-of-Fire exposure on a workover rig.",
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
      explanation:
        "Well-control barrier stack degraded: BOP pulled before cement set, gas at " +
        "shakers, compressed workover window. Baghjan-class precursor signature.",
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
      explanation:
        "Loss of containment on a live flowline with missing secondary controls " +
        "(barricade, spill kit).",
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
      explanation:
        "Low-energy slip event, same-level, caught by the worker. Routine " +
        "housekeeping precursor.",
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
      explanation: "",
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
      explanation: "",
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
      explanation: "",
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
      explanation: "",
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
  }
}
validateMock();

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

/** Offline fallback for GET /api/patterns — lift-ranked activity × site
 *  co-occurrence with n + Wilson CI. */
export const PATTERNS: PatternOut[] = [
  { id: "PAT-1", activity: "Workover operations", site: "Duliajan — Workover Rig #7", n: 14, sif_rate: 0.43, lift: 3.2, ci_low: 0.31, ci_high: 0.58 },
  { id: "PAT-2", activity: "Well servicing", site: "Baghjan EPS", n: 11, sif_rate: 0.38, lift: 2.8, ci_low: 0.24, ci_high: 0.49 },
  { id: "PAT-3", activity: "Flowline patrol", site: "GGS-2, Duliajan", n: 9, sif_rate: 0.32, lift: 2.4, ci_low: 0.18, ci_high: 0.41 },
  { id: "PAT-4", activity: "Lifting operations", site: "Tengakhat — Rig #3 pipe yard", n: 7, sif_rate: 0.27, lift: 2.1, ci_low: 0.12, ci_high: 0.33 },
  { id: "PAT-5", activity: "Hot work", site: "Moran GGS-1", n: 5, sif_rate: 0.24, lift: 1.9, ci_low: 0.08, ci_high: 0.29 },
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
