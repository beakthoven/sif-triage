/* Reviewer identity — WHO recorded a decision (audit-trail "who decided").
 * There is no auth in this stack: the identity is self-declared by the
 * reviewer, persisted locally, and disclosed as such in the UI. ONE storage
 * key for every surface that records a decision (REPORT's decision panel and
 * DECISIONS' reviewer picker both used to hold private copies —
 * "sif.reviewer" vs "sif26.reviewer" — so a name saved on one surface was
 * invisible to the other). Import the constant; do not re-create the string. */

/** localStorage key holding the reviewer's own display name. */
export const REVIEWER_KEY = "sif26.reviewer";

/** Anonymous fallback identity — also the server's default (app/schemas.py
 *  OverrideIn.labeler). Disclosed in the UI as an anonymous default; never
 *  replaced with an invented person's name. */
export const DEFAULT_REVIEWER = "hse_reviewer";