/*
 * Barrel for @/components/domain — the only import surface feature slices
 * should use. (Spec: design-system §4, "Domain components".)
 */

export { VerdictCard } from "./verdict-card";
export { ScoreReadout } from "./score-readout";
export { ScoreMeter } from "./score-meter";
export { StabilityIndicator } from "./stability-indicator";
export { EvidenceText } from "./evidence-text";
export { RuleBars } from "./rule-bars";
export { GateList } from "./gate-list";
export { ExplanationBlock } from "./explanation-block";
export { BarrierList } from "./barrier-list";
export { DensityTable } from "./density-table";
export { PatternCard } from "./pattern-card";
export { IngestProgress, type IngestStatus } from "./ingest-progress";
export { DecisionRow } from "./decision-row";
export { LimitationsPanel, DEFAULT_LIMITATIONS } from "./limitations-panel";

export {
  effectiveWord,
  mergeSpans,
  spanSegments,
  stripVectorMath,
  wilson,
  UNSTABLE_SPREAD_DEFAULT,
} from "./domain-logic";
export { dt, gateLabel } from "./domain-strings";
export type {
  BarrierState,
  DecisionRecord,
  ExplanationView,
  LimitationItem,
  Stability,
  VerdictWord,
} from "./domain-types";