# Phase 0 Discovery & Redesign Plan

**SIH 2026 · Problem Statement 26165 · Oil India Limited**
**Theme:** Smart Automation · **Idea deadline:** 30 September 2026
**Repository:** `/home/dakkshesh/sih26-round2` · **Date:** 2026-09-25

This is the single source of truth for the production overhaul. Phase 1 (frontend) and
Phase 2 (backend) decisions are derived from this document and recorded in
`docs/frontend-stack-decision.md` and `docs/backend-stack-decision.md`.

Supporting evidence lives in `docs/discovery/` (16 reports, 19 recorded subagent findings)
and `artifacts/qa-evidence/` (screenshots). Numbers marked **[measured]** were produced by
the orchestrator against the live stack on 2026-09-25.

---

## 1. Executive verdict

The prototype works and is genuinely impressive in places: real game fine-tuned inference at
~18 ms CPU, entirely offline, with honest uncertainty handling and an evaluation story most
hackathon entries never attempt. **It is not yet decision-grade, and the gap is not cosmetic.**

Three defects dominate. Two are fixable now; one must be disclosed.

| # | Defect | Evidence | Fixable now? |
|---|---|---|---|
| **D1** | **The triage score is not stable under paraphrase.** Rephrasing one confined-space scenario moves the score from 0.026 to 0.861 (sd 0.31); the flagged/clear verdict **flips** across meaning-preserving rewrites. Passive voice collapses it to ~0.03. **[measured]** | `60-orchestrator-novel-probe.md` §Result 3 | Partly — see §5.1 |
| **D2** | **The model penalises the near-miss register.** Adding *"Fortunately no injury occurred"* to a real scenario **drops** the score 0.280 → 0.100. That sentence is the signature of the genre the PS is about. **[measured]** | `60-orchestrator-novel-probe.md` §Result 6 | **Yes — cheap, validated** |
| **D3** | **Procedural barrier failures are systematically under-detected.** No gas test before tank entry → consensus 0.318; LOTO omitted → 0.280; hot work beside an open oily drain with no fire watch → 0.126. All should flag. Physical mechanisms are caught well. **[measured]** | `60-orchestrator-novel-probe.md` §Results 2, 5 | **No** — needs new training signal |

D2 has a validated one-line-class fix worth +0.349 on affected text. D3 is a labelling
problem inherited from OIICS codes, which encode *what physically happened to an injured
person*, not *which barrier was absent* — and the PS explicitly asks for barrier failures and
IOGP rule violations. We must disclose it honestly rather than paper over it.

A fourth issue is a **credibility** problem rather than a modelling one:

| # | Issue | Detail |
|---|---|---|
| **D4** | Headline gold precision (P 0.976) was measured at **89.9 % gold prevalence** vs 64.2 % in the test split. Precision does not transfer to deployment prevalence. Also: scores are described as "calibrated" though **no ECE or Brier score exists anywhere in the repo** (`train.py:486-503` fits T=1.648 on validation only). And the headline figure rests on a post-deadline re-label of one labeler's entire queue, disclosed in `runs/run2/kb/` but **not** in README. | `31-training-eval.md` |

Everything below follows from trying to make D1–D3 visible, fixable, or honestly disclosed.

**D1 corroborated independently.** The multimodal flows agent, working separately in a browser
with no knowledge of my probe, wrote essentially the same scenario — BOP ram removed without
isolating the annulus, suspended load overhead, workers below, no permit to work — and got
**0.487, below the 0.658 threshold, not flagged**. My phrasing of the same incident scored
0.874. Two authors, one incident, verdict flipped. **[differential, measured independently]**
See `53-visual-flows.md`.

---

## 2. Official problem statement (re-verified)

Verified live against sih.gov.in today. **The project brief is correct; the repo's own
`HANDOFF.md` is stale.**

| Field | Verified value |
|---|---|
| PS ID / title | 26165 — "AI/NLP Engine to Detect Serious Injury & Fatality (SIF) Precursors in OIL's Unsafe-Act/Unsafe-Condition and Near-Miss Reports" |
| Organisation | Oil India Limited (OIL) |
| Category | Software |
| Theme | **Smart Automation** — *not* "Miscellaneous" as `HANDOFF.md:23` states |
| Deadline | 30 September 2026 (extended); PS count now 240, was 226 in the on-disk snapshot |
| Dataset | **Correction:** not "OIL provides no dataset". The PS ends "Relevant Data Availability (if any): OIL's UA/UC observations, near-miss and incident reports." No *link* is published, but data is asserted. Use that precise wording. |

Full detail and the verdict table: `docs/discovery/01-ps-verification.md`.

No official SIH 2026 evaluation rubric is obtainable — third-party rubrics conflict and are
unverifiable. **Do not claim rubric alignment.**

---

## 3. Feature inventory — what exists today

**Backend** — Python 3.14, FastAPI, no torch at runtime, ~3,200 LoC in `app/`.

| Surface | State |
|---|---|
| `POST /api/classify` | Working. ONNX INT8 ModernBERT multi-task: SIF head, 7 IOGP rule heads, token span head. p95 ~18 ms CPU. **[confirmed]** |
| `POST /api/ingest` | Working. JSON records or raw CSV. Measured **11 rows/s**, not the 45.6/s in README nor the ≥30/s comment at `routes.py:176`. |
| `/api/reports`, `/reports/{id}` | Working, but the client caps at 200 rows against 5,056 stored. |
| `/api/reports/{id}/explanation` | Deterministic template + optional Ollama reword. **Cache is 100 % dead** — key changed with the version suffix, 0/63 hits. Live #[measured] 17.5 s when Ollama is absent, vs the 8 s the comment claims. |
| `/api/density`, `/api/patterns` | Working but **saturated**: all 197 pattern cells `sif_rate=1.0`, one identical lift 1.499; density top rows 100 % flagged. Served from artifact before live DB (`routes.py:329-331`), so they can never change with real ingests. |
| `/api/review` (GET/POST) | Working append-only with `supersedes` lineage. `rationale` is accepted and stored but **dropped by the frontend adapter** (`api.ts:192-203`) and never displayed. |
| `/api/review/export` | Working, compliance-grade NDJSON. **No UI control exists.** |
| 10 sentinel gates | Working, deterministic, pure functions. Their persisted `gate_states` snapshots are stale — 8-gate schema stored while code now emits 10. |

**Frontend** — React 19.2, TypeScript 7, Vite 8, Tailwind 4, shadcn/ui via radix. No router, no
data-fetching library, **no table library, no chart library**. ~1,550 LoC. Three tabs:
Triage / Insights / Decision History.

**Data & training** — OSHA SIR (105,996 rows) + NASA ASRS + synthetic OIL corpus; OIICS-derived
deterministic labels; temporal + employer-grouped splits (verified clean); Kaggle 2×T4 fine-tune.

---

## 4. Pain points — code reading *and* visual walkthrough

**From the visual walkthrough** (`52-visual-review-responsive.md`, 29 screenshots reviewed by a
multimodal subagent — I cannot see these myself; findings are theirs):

- **Decision History fails as an audit trail.** Columns are Report/Field/Was/Now/Reviewer/When. No rationale (never captured), "who" is only the string "HSE reviewer", report is a bare `#5049` with no snippet. An auditor gets *what* and *when*, not *who* or *why*. Export is unreachable from the UI. No undo, amend, or correction path exists anywhere.
- **The audit tab is invisible on phones.** At ≤390 px the "Decision history" tab strip clipped to x=428 in a 360 px viewport with no scroll affordance. Reviews and required columns (Reviewer, When) are hidden behind horizontal scrollers.
- **Focus is invisible on two keyboard stops.** Both `tablist` and `tabpanel` compute `outline: none` — Tab moves focus and nothing is marked (WCAG 2.4.7 failure).
- **Dark mode is not implemented** despite `@custom-variant dark` existing in `index.css`. Under `prefers-color-scheme: dark` every tab stays `rgb(245,244,240)`.
- One AA contrast failure: inactive sub-tab at 3.70:1. Passing: skip link, logical tab order, no traps, reduced-motion correctly suppressed.

**From code reading:**

- Mock fixtures collide with live row ids — mock ids 2588–2619 are real rows. Any transient fetch error swaps real data for **scripted, invented model output** on a safety-critical surface (`api.ts:253,262,361`).
- Three disagreeing thresholds: client `bandFor` 0.7/0.4 (`api.ts:129`), server tuned op 0.658 (`classifier.py:179`), gray band [0.40,0.60] (`config.py`). A card can read "Flagged" at a score the metrics do not count.
- **Only 12 of 1,000 reports fall in the gray band** — scores are bimodal (p10 0.011, median 0.966, p90 0.996), so there is almost no middle to review. **[measured]**
- SQLite has no `busy_timeout`; a held external lock caused a verified 5 s block then HTTP 500 under concurrent write. Zero secondary indexes. `/density` full-scans per request.
- No Devanagari font ships despite a prominent EN/हिं toggle; every Hindi string renders in an OS substitute.
- README claims a "reviewer time saved" benefit that was never measured.
- Masking runs at **training** time but never at inference — no `mask_text` call exists in `app/`. This is D2's mechanism. **[verified independently]**

---

## 5. Root cause — why symptoms look the way they do

### 5.1 The 71 % flag rate is a seeding artifact, not a tuning error

Confirmed and refined by `30-data-pipeline.md`, every number computed there:

OSHA SIR is **severe-injury-only** by inclusion criterion, so mechanism-derived labels mark
65.30 % of 105,996 rows positive. `corpus_ids.jsonl` is **63.54 % positive**. The demo database
is seeded from the synthetic register whose rows are the training corpus — measured top-1
near-dup cosine **0.99998** — so it scores itself: live `flag_rate 0.7095`, median 0.958,
**[measured]** bimodal. **No threshold can fix this**; the corpus needs a negative-dominant
register and a re-tuned operating point at realistic prevalence.

Good news: splits are clean (temporal + exact-dedup + boundary screen + group-disjoint
validation). No contamination.

### 5.2 Why D1 and D3 resist the obvious fix

I hypothesised that applying the training-time masking at inference would stabilise scores.
**It does not** — for the 16 tank-entry paraphrases, raw and masked scores came back
*identical*, because those texts contain no outcome words. The instability is intrinsic to the
learned representation, not a pre-processing artifact. ([measured], `60-...` §Result 6.)

Separately, self-consistency averaging **does** fix reliability but not validity: mean-of-8
paraphrase averaging cuts sd from 0.308 → 0.076, but it stabilises around 0.318, which is
*still unflagged*. The consensus answer for procedural cases is wrong, not merely noisy.

Reliability and validity therefore need **separate** treatments (§7, items A1 and A3).

### 5.3 What the model is reliably good at — the honest basis for a product claim

Benign/administrative text is cleared with conviction: mean 0.0111, sd 0.0046, **0 of 16
false flags** across paraphrases. Physical high-energy mechanisms are caught: suspended load
over personnel 0.961, pressurised release 0.903, personnel in a vessel during nitrogen purge
0.890. The failure is concentrated in **barrier absence** — precisely the IOGP Life-Saving-Rule
slice the PS names. That is a coherent, defensible line to draw.

---

## 6. Gaps vs what an HSSE officer would expect

From `02-domain-expectations.md` — the capability checklist for a decision-grade tool, tagged
against today's three tabs.

**Conspicuously absent:** CAPA / action-closure loop with owner and due date (Confirm/Not-SIF
is terminal today); escalation & alerting; time-to-triage SLA; any time dimension at all;
exportable regulatory pack reachable from the UI; complete audit trail (no rationale);
recurrence/repeat-offender tracking; reviewer workload view; shift/season effects.

**Domain context to respect:** OISD requires an FIR within 24 h and an IIR within one month.
API RP 754 and IOGP 456 leading indicators are time-series by definition — our analytics has no
time dimension, which is disqualifying for that framing today. The Katakey committee's central
Baghjan finding was **unexecuted actions**; our product currently reproduces that failure mode
because nothing tracks actions to closure.

**Language reality:** OIL's Assam workforce means field reports realistically contain Hindi,
Assamese, and transliterated mixed text. Today non-ASCII is grayed out and never translated. A
romanised-Hindi guarding incident scored **0.0074**. Offline remedies exist (AI4Bharat
IndicTrans2, MIT) but `44-res-backend-oss.md` verified **0 Devanagari rows** in either demo
database and recommends **defer** — real but unproven demand, and IndicXlit is rejected because
its pip package pulls torch.

---

## 7. Target information architecture

Derived from the above, not assumed. Five surfaces replace today's three tabs.

| Surface | Purpose | Replaces |
|---|---|---|
| **1. Triage queue** | Risk-ordered worklist. Sort by score, filter by rule/site/time, paginate over all rows, keyboard-first. A reviewer processes hundreds per shift. | Triage tab (today it cannot sort or paginate) |
| **2. Report detail & evidence** | One report, full model reasoning: score **with a stability indicator**, evidence spans, per-rule probabilities, active gates, source text. Never a bare number. | Triage card expander |
| **3. Analytics** | Time series first (precursor rate over time, by site/activity/rule/barrier), then density ranking and pattern mining, all with n + Wilson CIs and min-n guards. | Insights tab |
| **4. Ingest** | Dedicated surface for single paste + bulk CSV, with **real progress**, row counts, and error rows. Batch job history. | Buried inside Insights → Density |
| **5. Decisions & actions** | The audit trail plus action closure: who, when, before/after, rationale, with correct/amend and NDJSON export. Then carries the CAPA fields the domain demands. | Decision History |

Plus **Settings / Model ops**: model version and operating point in use, corpus provenance,
metric provenance, the limitations disclosure itself. Judges reward a team that shows its
limitations before being asked.

**Every AI verdict must render alongside its reasoning.** Given D1, that now includes showing
*how much the verdict moves under paraphrase* — turning our biggest weakness into visible,
honest signal rather than a hidden failure.

---

## 8. Master KEEP / REMOVE / ADD / MERGE plan

**From the live user-flow walkthrough** (`53-visual-flows.md`, 16 screenshots):

- **Bulk ingest reports failure while succeeding — SEV-1.** Real server time for 500 rows was **80.6 s** (~6.2 rows/s, against a dialog that promises "about 15 seconds"). The client timed out at 90 s and displayed *"Ingest failed — live data unchanged. Check the API and retry."* That message is **false**: `/api/health` went 4,551 → 5,051, all 500 rows persisted. A retry is safe only because the endpoint is idempotent (a direct re-POST returned 500 `skipped_duplicates`) — the user is still being lied to about the outcome.
- **The progress bar is fictional**: paced to 0 → 92 % in ~15 s, then a ~75 s silent crawl. No cancel, no row-level progress, no ETA. This is the demo's headline beat and it currently reads as a crash.
- **Duplicate stacked cards for one report**, with no unified score/evidence view.
- **Inverted explainability richness**: the *benign* card renders score, band, rule bars and "Why this score?". The *dangerous* card hides its score and evidence behind a gray-state card. Precisely backwards for a safety tool.
- Density re-rank is genuine server-side (Kathalguri GCS 88 → 213, #2 → #1) but appears only after a **manual reload**, which resets "Movement" to 0 everywhere.
- Text-substitution bug: "Flag rate" renders **`100.0per 100`** (missing space) — and reads 100 % on every row, i.e. zero signal.

**From the Insights analytics walkthrough** (`51-visual-insights.md`, 17 screenshots):

- **The density ranking is not actionable — it ranks noise.** Of 341 rows, **271 have n ≤ 5 and 173 have n = 1**. Single-report entities rank #14–#20 at "100 per 100" with no caveat. Sorting places n=3 @ 33 % *above* n=35 @ 0 %. No confidence interval, no baseline, no minimum-n guard. Compared with the cost of nothing, this actively misleads: a site with one report looks maximally dangerous.
- **A statistical mislabel:** the pattern cards show `95% CI [0.91, 1.00]` — that is the confidence interval of the **rate**, but it is presented where a reader takes it for the **lift's**. All 40 pattern cells are `rate=1.0, lift=1.499` (clamped), so "lift-ranked" is degenerate.
- **Facets are unreachable**: `by=activity` and `by=contractor` exist server-side but the view hardcodes `by=site`.
- Keyboard: the deepest tablist is hand-rolled `role=tab` buttons with **no arrow-key support**; at 390 px the flag-rate column is off-screen with no scroll affordance.
- *Process note:* this agent observed uncommanded tab flips and a second instance on another port. Evidence points to **contention on a shared Playwright browser between concurrent QA processes** — not an application bug. It independently supports making tab/filter state URL-addressable (§8).

**From the Triage queue walkthrough** (`50-visual-triage.md`, 38 screenshots) — the primary screen:

- **The 200-row cap is a visible contradiction**: the header reads "5,056 reports indexed" while the queue reads "x/200" and a chip says "All reports 200". **4,855 reports are unreachable**, and the UI admits it to the user.
- **"LOTO not applied" scored 0.07 and rendered green "No review needed"** — while the explanation text quotes "LOTO" as seen-but-dismissed and the Energy Isolation bar is a 0.01 dot. A textbook Energy Isolation precursor is presented as *confidently clear*. This is a third independent confirmation of D3.
- **Debug internals leak onto reviewer screens**: near-dup cards render `cosine=1.000 with index row syn-cs-e-0188 (>= 0.91)` and explanations print "Advisory gates: near_dup (…)". Reviewers see raw vector math and training-row identifiers.
- **Decision capture is a dead end**: two equal-weight buttons, no rationale field, no undo, and after deciding, the card reads only "Reviewed by HSE" — **not which decision was taken**.
- **Evidence spans are too quiet to see** (`#EFE9DC` on white, no underline) and are **absent entirely on freshly classified reports** — a 0.95-score result rendered zero highlights, while indexed cards have them. The explainability layer's flagship evidence support does not fire at the moment a user most needs it.
- **Search ignores body text**: searching "LOTO" returned 0 results while a loaded card's body was literally "LOTO not applied".
- Metadata is inconsistent: cards show either a date or not depending on card type, one shows dates that contradict the report text, and no ID or contractor appears anywhere.

**Preserve deliberately** — these are genuinely good and verified by that walkthrough: "Why this score?" names the exact threshold, top rule and quoted words rather than hand-waving; gray-state cards self-explain in plain language ("a rehearsal is not a precursor… never auto-cleared"); the near-dup framing "Matches a training record — memory, not generalization" is excellent; the skip link is first in the DOM and visible on focus; the keyboard path to the decision buttons is complete with visible rings; Devanagari renders cleanly via OS fallback (no tofu); the footer honestly labels synthetic data.

*Correction to an earlier reading:* that walkthrough timed the explanation expander at **1.3 s then 0.26 s with Ollama down — no multi-second stall**. My own ~17.5 s figure comes from `23-be-explain.md`'s deliberately hung-LLM stub, a harsher condition. Both are recorded; the honest statement is that worst-case stall depends on whether Ollama is absent-down versus hung.

### Backend

| Action | Item | Justification |
|---|---|---|
| **ADD** | Apply `mask_text` at inference before scoring | D2. Measured +0.349 on near-miss text; restores the genre the PS targets. One call, no new dependency. |
| **ADD** | Self-consistency scoring: score N surface variants, serve mean + spread | D1. Measured sd 0.308 → 0.076 at n=8; ~160 ms affordable against an 18 ms base call. |
| **ADD** | `verdict_stability` gray gate keyed on that spread | Extends the existing 10-gate humility philosophy instead of inventing a new one. |
| **ADD** | ECE + Brier and a calibration report | The word "calibrated" is currently unsupported (`31-training-eval.md`). |
| **ADD** | Date index + time parameters on `/density`, `/reports`, `/patterns` | No time dimension anywhere; leading-indicator standards require it. |
| **ADD** | `PRAGMA busy_timeout` + retry; secondary indexes | Kills the verified 5 s block → HTTP 500 under concurrent write. |
| **ADD** | `gate_schema_version` + backfill recompute | Stored snapshots are an 8-gate schema while code emits 10; severity_watch hides 45 cases. |
| **ADD** | Capture `rationale` at decision time; surface reviewer identity | The audit trail currently answers neither "who" nor "why". |
| **ADD** | structlog + Prometheus RED metrics; pydantic-settings; hypothesis | Replaces observability silence and hand-rolled env parsing. All four verified available for Python 3.14. |
| **ADD** | Regenerate `patterns.json` / density seed | Saturated at sif_rate 1.0; numbers can never move, which is worse than showing nothing. |
| **KEEP** | FastAPI+uvicorn, hand-rolled onnxruntime, SQLite+numpy near-dup, pure-Python gates | All four survive adversarial comparison (`44-res-backend-oss.md`). Framework swaps buy ~0 ms on an 18 ms model-bound path. |
| **KEEP** | The 10-gate gray-state system; 7+2 IOGP model with two declared out-of-scope | The strongest part of the submission; genuinely differentiated. |
| **MERGE** | `/classify` double embed into the batched matmul | Same work done twice at 13.8 ms vs 3.5 ms per row. |
| **REMOVE** | Ollama rewording as default (`SIF_EXPLAIN_LLM=0`) | Adds no information by construction; 17.5 s stall with the server down **[measured]**; cache already 0 % hit rate. Template stays as the product. |
| **REMOVE** | Split badge vs gray in `gate_trigger_counts` | 93 % of triggers are near_dup badges, drowning the 186 real gray cases. |
| **REMOVE** | Stale claims: ≥30 rows/s comment, 8 s timeout comment, 45.6 rows/s README line | All three contradicted by measurement. |

### Frontend

| Action | Item | Justification |
|---|---|---|
| **ADD** | TanStack Table + Virtual | Fixes: no sorting, 200-row cap, no pagination over 5,056 rows. |
| **ADD** | TanStack Query | Deletes `useEffect` fetch boilerplate; `queryFn` can still fall back to `mock.ts` so the offline doctrine survives. |
| **ADD** | Recharts (lazy-loaded) from analytics route | `ErrorBar` verified present in v3 → Wilson CI whiskers first-class. Zero charts exist today; `--chart-1..5` tokens are dead. |
| **ADD** | cmdk palette; react-day-picker range; react-router HashRouter; sonner | Keyboard-first navigation, the missing date filter, deep-linkable filter state. |
| **ADD** | `@fontsource/ibm-plex-sans-devanagari` + font-stack slot | Hindi toggle ships with zero Devanagari coverage. Verified the package exists; the Mono Devanagari does not. |
| **ADD** | Real ingest progress tied to server rows done, cancel, ETA, and honest success/failure | Server succeeds in 80.6 s while the UI declares failure; the progress bar is paced fiction. This is the demo's money beat. |
| **ADD** | One unified verdict card per report, with score + evidence always visible regardless of band | Today the dangerous card hides score and evidence while the benign card shows them — inverted for a safety tool. |
| **ADD** | Strip debug internals from reviewer-facing copy (raw cosine, index row ids, gate names) | Reviewers currently see vector math and training-row identifiers. Keep the honest *framing* ("matches a training record"), drop the internals. |
| **ADD** | Body-text search; consistent report metadata (id, site, activity, contractor, correct event vs ingest dates) | Search returns nothing for a term present in a loaded card's body; dates shown contradict the report text. |
| **ADD** | Make evidence spans legible (underline/higher contrast) and fix their absence on freshly classified reports | Too faint to see, and zero highlights at the moment of classification — the explainability layer's core support does not fire when needed. |
| **ADD** | ESLint, `typecheck` script, minimal CI, e2e DB isolation | Today the only gate is `tsc -b` inside build. |
| **KEEP** | `index.css` token architecture; radix/shadcn primitives; `use-flip.ts`; typed phrasebook | Real token discipline (0 raw hex, 0 arbitrary colours); FLIP double-guarded for reduced-motion and verified working. |
| **MERGE** | `gray-state-card`'s parallel EN/HI table into the phrasebook | Two i18n mechanisms for one 103-key surface. |
| **MERGE** | Mock fixtures behind an explicit demo-mode flag | Mock ids collide with live rows and silently swap in invented model output on a safety-critical screen. This is the highest-severity frontend defect. |
| **REMOVE** | Client-side `bandFor()` | Three disagreeing thresholds; the server must own the operating point. |
| **REMOVE** | Fabricated fallback score 0.5 + fake gate on API failure | Invents model output. Show an error state instead. |
| **REMOVE** | ~20 dead tokens (sidebar ×9, chart ×5, accent, `--paper`) | Unused CSS custom properties. |

### Claims & documentation

| Action | Item | Justification |
|---|---|---|
| **ADD** | Limitations surface in-product and in README | Judges penalise overclaiming more than disclosed weakness. This is currently our largest unforced error. |
| **CORRECT** | Disclose that gold P 0.976 was measured at 89.9 % prevalence | Precision does not transfer; state this before a reviewer finds it (§1, D4). |
| **ADD** | INT8 export-gate row in README's honest-claims table | `export_gate.json` says `pass:false` (ΔAUC 0.1305) yet the artifact ships. Defensible — surface it rather than hide it. |
| **REMOVE** | Unmeasured "reviewer time saved" | Nothing measures it. |
| **CORRECT** | "OIL provides no dataset" → no published link, data asserted | Verified against the PS text. |
| **CORRECT** | `HANDOFF.md` theme, PS counts, and the phantom TanStack/Recharts line | All three stale; that file is wrong where it matters. |
| **MERGE** | Substitute-labeler disclosure from `runs/run2/kb/` into README | The headline number depends on it. |

---

## 9. Honest limitations to state up front

1. Training distribution is a **US post-injury proxy** (OSHA) plus synthetic text — not OIL's register. Domain shift is real and acknowledged (ASRS stratum recall 0.00 shows what happens off-distribution).
2. **Demand for Indic translation is plausible but unproven** — zero Devanagari rows exist in any database we hold. Deferred, not adopted.
3. The 71 % flag rate is a **demo-database artifact**; do not present it as a field measurement.
4. **Procedural barrier failures are under-detected** (D3). This is the largest remaining gap and is not fixable within this work cycle.
5. No validated deployment-prevalence precision exists. All gold metrics were measured at 89.9 % prevalence.

---

## 10. What this means for sequencing

The backend fixes to **D2 (runtime masking)** and **D1 (self-consistency + stability gate)**
are small, measurable, and independent of the frontend. They should land first because they
change what the product is allowed to claim, which changes what the UI must display.

Then the frontend rebuild against the corrected contract, then the claims documentation.

Evidence index for this document:
`01-ps-verification`, `02-domain-expectations`, `10-fe-shell`, `11-fe-triage`,
`12-fe-insights`, `13-fe-review-tokens`, `20-be-inference`, `21-be-storage`, `22-be-gates`,
`23-be-explain`, `30-data-pipeline`, `31-training-eval`, `40-res-frontend-stack`,
`44-res-backend-oss`, `52-visual-review-responsive`, `60-orchestrator-novel-probe`
— all in `docs/discovery/`.
