import type {
  DensityRow,
  EvidenceSpan,
  OverrideOut,
  PatternOut,
  Report,
  RuleScore,
} from "./types";

/* Span offsets are computed by construction (indexOf) and validated below —
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
    id: "RPT-2614",
    text: R1_TEXT,
    site: "Duliajan — Workover Rig #7",
    activity: "Workover operations",
    contractor: "DeepWell Services",
    reported_at: "2026-09-06",
    prediction: {
      triage_score: 0.87,
      band: "HIGH",
      latency_ms: 38,
      rules: rules(
        [
          ["LoF", "Line of Fire", 0.91],
          ["WaH", "Working at Height", 0.64],
        ],
        ...PTW_BYPASS_OOS,
      ),
      well_control_tag: false,
      spans: spanify(R1_TEXT, [
        "above the occupied drill floor",
        "1 m from the floorman",
        "No barricade or dropped-object netting",
      ]),
      gates: [],
      explanation:
        "Dropped object from the derrick into an occupied area with no exclusion " +
        "zone below — classic Line-of-Fire exposure on a workover rig.",
    },
  },
  {
    id: "RPT-2601",
    text: R2_TEXT,
    site: "Baghjan EPS",
    activity: "Well servicing",
    contractor: null,
    reported_at: "2026-09-04",
    prediction: {
      triage_score: 0.74,
      band: "HIGH",
      latency_ms: 41,
      rules: rules(
        [
          ["EI", "Energy Isolation", 0.55],
          ["LoF", "Line of Fire", 0.41],
        ],
        ...PTW_BYPASS_OOS,
      ),
      well_control_tag: true,
      spans: spanify(R2_TEXT, [
        "pulling the BOP before cement had fully set",
        "gas was detected at the shale shakers",
        "reduced from 48 h to 12 h",
      ]),
      gates: [],
      explanation:
        "Well-control barrier stack degraded: BOP pulled before cement set, gas at " +
        "shakers, compressed workover window. Baghjan-class precursor signature.",
    },
  },
  {
    id: "RPT-2597",
    text: R3_TEXT,
    site: "GGS-2, Duliajan",
    activity: "Flowline patrol",
    contractor: "Pipeline O&M Crew",
    reported_at: "2026-09-03",
    prediction: {
      triage_score: 0.62,
      band: "MODERATE",
      latency_ms: 35,
      rules: rules(
        [
          ["EI", "Energy Isolation", 0.58],
          ["CS", "Confined Space", 0.22],
        ],
        ...PTW_BYPASS_OOS,
      ),
      well_control_tag: false,
      spans: spanify(R3_TEXT, ["pinhole leak weeping crude", "not barricaded"]),
      gates: [],
      explanation:
        "Loss of containment on a live flowline with missing secondary controls " +
        "(barricade, spill kit).",
    },
  },
  {
    id: "RPT-2588",
    text: R4_TEXT,
    site: "Naharkatia Warehouse",
    activity: "Material handling",
    contractor: null,
    reported_at: "2026-09-02",
    prediction: {
      triage_score: 0.18,
      band: "LOW",
      latency_ms: 31,
      rules: rules([["SML", "Safe Mechanical Lifting", 0.12]], ...PTW_BYPASS_OOS),
      well_control_tag: false,
      spans: [],
      gates: [],
      explanation:
        "Low-energy slip event, same-level, caught by the worker. Routine " +
        "housekeeping precursor.",
    },
  },
  {
    id: "RPT-2616",
    text: G1_TEXT,
    site: "GGS-2, Duliajan",
    activity: "Flowline patrol",
    contractor: null,
    reported_at: "2026-09-06",
    prediction: {
      triage_score: 0.41,
      band: "MODERATE",
      latency_ms: 33,
      rules: rules([["LoF", "Line of Fire", 0.38]], ...PTW_BYPASS_OOS),
      well_control_tag: false,
      spans: [],
      gates: ["low_confidence"],
      explanation: "",
    },
  },
  {
    id: "RPT-2610",
    text: G2_TEXT,
    site: "Tengakhat — Rig #3 pipe yard",
    activity: "Lifting operations",
    contractor: "DeepWell Services",
    reported_at: "2026-09-05",
    prediction: {
      triage_score: 0.66,
      band: "MODERATE",
      latency_ms: 36,
      rules: rules([["SML", "Safe Mechanical Lifting", 0.72]], ...PTW_BYPASS_OOS),
      well_control_tag: false,
      spans: spanify(G2_TEXT, ["sling slipped while lifting a casing"]),
      gates: ["negation"],
      explanation: "",
    },
  },
  {
    id: "RPT-2609",
    text: G3_TEXT,
    site: "GGS-2, Duliajan",
    activity: "Flowline patrol",
    contractor: null,
    reported_at: "2026-09-05",
    prediction: {
      triage_score: 0.6,
      band: "MODERATE",
      latency_ms: 44,
      rules: rules([["EI", "Energy Isolation", 0.52]], ...PTW_BYPASS_OOS),
      well_control_tag: false,
      spans: [],
      gates: ["language"],
      explanation: "",
    },
  },
  {
    id: "RPT-2615",
    text: G4_TEXT,
    site: "Duliajan — Workover Rig #7",
    activity: "Workover operations",
    contractor: "DeepWell Services",
    reported_at: "2026-09-06",
    prediction: {
      triage_score: 0.85,
      band: "HIGH",
      latency_ms: 37,
      rules: rules([["LoF", "Line of Fire", 0.9]], ...PTW_BYPASS_OOS),
      well_control_tag: false,
      spans: spanify(G4_TEXT, ["above the occupied drill floor"]),
      gates: ["near_dup"],
      explanation: "",
    },
  },
];

/* Invariant check — mirrors the server-side span self-validation contract.
 * Runs at module load; also runnable standalone: node src/lib/mock.ts */
function validateMock(): void {
  for (const r of REPORTS) {
    for (const s of r.prediction.spans) {
      if (r.text.slice(s.start, s.end) !== s.text) {
        throw new Error(
          `span offset mismatch in ${r.id}: [${s.start}:${s.end}]`,
        );
      }
    }
  }
}
validateMock();

/** GET /rankings/density — two snapshots: prev (pre-ingest) and current
 *  (post-ingest re-rank). The demo beat: Baghjan EPS climbs to #1. */
export const DENSITY_BEFORE: DensityRow[] = [
  { key: "Duliajan · Workover ops", n_reports: 128, n_flagged: 34, flag_rate: 0.266, rank: 1, prev_rank: 1 },
  { key: "GGS-2 · Flowline patrol", n_reports: 96, n_flagged: 22, flag_rate: 0.229, rank: 2, prev_rank: 2 },
  { key: "Baghjan EPS · Well servicing", n_reports: 74, n_flagged: 16, flag_rate: 0.216, rank: 3, prev_rank: 3 },
  { key: "Moran GGS-1 · Hot work", n_reports: 61, n_flagged: 11, flag_rate: 0.18, rank: 4, prev_rank: 4 },
  { key: "Naharkatia · Material handling", n_reports: 88, n_flagged: 12, flag_rate: 0.136, rank: 5, prev_rank: 5 },
  { key: "Tengakhat · Lifting ops", n_reports: 53, n_flagged: 7, flag_rate: 0.132, rank: 6, prev_rank: 6 },
];

export const DENSITY_AFTER: DensityRow[] = [
  { key: "Baghjan EPS · Well servicing", n_reports: 98, n_flagged: 32, flag_rate: 0.327, rank: 1, prev_rank: 3 },
  { key: "Duliajan · Workover ops", n_reports: 141, n_flagged: 39, flag_rate: 0.277, rank: 2, prev_rank: 1 },
  { key: "GGS-2 · Flowline patrol", n_reports: 108, n_flagged: 25, flag_rate: 0.231, rank: 3, prev_rank: 2 },
  { key: "Moran GGS-1 · Hot work", n_reports: 66, n_flagged: 12, flag_rate: 0.182, rank: 4, prev_rank: 4 },
  { key: "Tengakhat · Lifting ops", n_reports: 71, n_flagged: 11, flag_rate: 0.155, rank: 5, prev_rank: 6 },
  { key: "Naharkatia · Material handling", n_reports: 93, n_flagged: 12, flag_rate: 0.129, rank: 6, prev_rank: 5 },
];

/** GET /patterns — lift-ranked activity×location×barrier co-occurrence,
 *  n + Wilson CI. One plain sentence, one count. */
export const PATTERNS: PatternOut[] = [
  {
    id: "PAT-1",
    sentence: "LINE OF FIRE × drill floor × missing barricade",
    n: 14,
    lift: 3.2,
    ci_low: 0.31,
    ci_high: 0.58,
    window_days: 30,
  },
  {
    id: "PAT-2",
    sentence: "Dropped object × workover rig × no exclusion zone",
    n: 11,
    lift: 2.8,
    ci_low: 0.24,
    ci_high: 0.49,
    window_days: 30,
  },
  {
    id: "PAT-3",
    sentence: "Flowline leak × GGS manifold × barricade missing",
    n: 9,
    lift: 2.4,
    ci_low: 0.18,
    ci_high: 0.41,
    window_days: 30,
  },
  {
    id: "PAT-4",
    sentence: "Lifting ops × casing yard × uncertified sling",
    n: 7,
    lift: 2.1,
    ci_low: 0.12,
    ci_high: 0.33,
    window_days: 30,
  },
  {
    id: "PAT-5",
    sentence: "Hot work × tank farm × gas test not recorded",
    n: 5,
    lift: 1.9,
    ci_low: 0.08,
    ci_high: 0.29,
    window_days: 30,
  },
];

/** Review queue: overrides already logged (→ future gold labels). */
export const OVERRIDES: OverrideOut[] = [
  {
    report_id: "RPT-2410",
    field: "label",
    old_value: "not_sif_potential",
    new_value: "sif_potential",
    labeler: "hse.kgohain",
    source: "override",
    ts: "2026-09-05T14:22:10+05:30",
  },
  {
    report_id: "RPT-2566",
    field: "band",
    old_value: "MODERATE",
    new_value: "HIGH",
    labeler: "hse.rbora",
    source: "override",
    ts: "2026-09-06T09:41:03+05:30",
  },
  {
    report_id: "RPT-2579",
    field: "rule",
    old_value: "Safe Mechanical Lifting",
    new_value: "Line of Fire",
    labeler: "hse.kgohain",
    source: "override",
    ts: "2026-09-06T11:07:55+05:30",
  },
];
