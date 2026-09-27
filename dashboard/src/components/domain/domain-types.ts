/*
 * Shared types for the domain (explainability) components.
 * Import-only file — no runtime code — so domain-logic.ts stays runnable
 * under `node domain-selfcheck.ts` (type-only imports are erased).
 */

/** The review-priority WORD paired with the verdict tokens (design-system
 *  spec §2 "Verdict — always paired with a word"). The server owns the
 *  operating point; callers derive the word from it, never from a private
 *  client-side threshold. */
export type VerdictWord = "HIGH" | "MODERATE" | "LOW" | "CLEAR" | "REVIEW";

/** Self-consistency output from the classifier (workstream A3): the spread
 *  of the score across N deterministic paraphrase variants. `spread` is a
 *  dispersion figure (sd or max−min); `verdictFlips` counts variants whose
 *  flag verdict differed from the consensus. Null/undefined when the runtime
 *  scored a single variant (older runtime) — the indicator then hides. */
export interface Stability {
  spread: number;
  nVariants: number;
  verdictFlips?: number | null;
}

/** One fired barrier-failure gate (workstream A2 family: no gas test, no
 *  LOTO, no permit, no fire watch, no standby, unmonitored atmosphere).
 *  `label` is the reviewer-facing barrier name; `detail` is the gate's own
 *  human phrasing of the absence. */
export interface BarrierState {
  gate: string;
  label: string;
  detail: string;
}

/** Explanation as the verdict card renders it (subset of ExplanationOut,
 *  with the optional LLM rewording). */
export interface ExplanationView {
  template: string;
  source: "template" | "ollama";
  cached: boolean;
  reworded?: string | null;
}

/** One recorded human decision — WHO (labeler), WHEN (ts), WAS (oldValue),
 *  NOW (newValue) and RATIONALE. Structurally satisfied by OverrideOut in
 *  @/lib/types once the rationale adapter stops dropping it. */
export interface DecisionRecord {
  id?: number;
  reportId?: number;
  field: string;
  oldValue: string | null;
  newValue: string;
  labeler: string;
  ts: string;
  rationale?: string | null;
  source?: string | null;
}

/** One honest-limitation entry for LimitationsPanel. */
export interface LimitationItem {
  title: string;
  body: string;
}