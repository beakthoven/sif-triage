# Discovery 11 — FE Core Triage Surface Audit

Role: core triage surface audit — the screen an HSE reviewer stares at all day (SIH 2026 PS 26165, OIL, Smart Automation). Phase 0, read-only.

**Files read (with line counts):**
- `dashboard/src/views/feed.tsx` (351) — queue + paste + detail-pane orchestration
- `dashboard/src/components/triage-card.tsx` (289) — the money-shot card + ExplanationSection
- `dashboard/src/components/paste-classify.tsx` (70)
- `dashboard/src/components/band-badge.tsx` (39)
- `dashboard/src/components/highlighted-text.tsx` (44)
- `dashboard/src/components/gray-state-card.tsx` (215) — GrayStateCard + SentinelGateLegend
- `dashboard/src/lib/report-display.ts` (57)
- `dashboard/src/lib/types.ts` (182)

**Supporting files read to trace data flow:** `dashboard/src/lib/api.ts` (426), `dashboard/src/App.tsx` (213), `dashboard/src/lib/mock.ts` (553), `dashboard/src/lib/phrasebook.ts` (166), `app/routes.py` (402), `app/gates.py` (423), plus targeted greps of `app/storage.py`, `app/schemas.py`, `app/classifier.py`.

**Tools used:** Read, Grep, and four read-only `curl` GETs against the live stack at 127.0.0.1:8177 this session: `/api/health`, `/api/metrics/summary`, `/api/reports?limit=2`, `/api/reports/2614/explanation`. Nothing was written, built, installed, or restarted. All live numbers below are from those probes (flag_rate 0.7095; gate counts near_dup 3021, confidence 78, negation 42, drill 36, well_control_watch 29, long_input 25, severity_watch 5, min_length 1; mean_score 0.6997; n_reports 5056; n_overrides 1; model `onnx:masked-v2/sif_multitask_int8.onnx`).

---

## What exists today

**Screen anatomy** (feed.tsx:164-350): top-to-bottom — PasteClassify box, then a two-column grid: left = "Work queue" card (sticky, 300px min), right = detail pane. Below, a `<details>` panel exposing the full 10-gate legend (SentinelGateLegend). Empty-queue state exists (feed.tsx:175-180).

**Paste flow** (feed.tsx:86-125): POST `/api/classify?persist=1&explain=1&llm=0` (api.ts:279). Server returns a real row id (`report_id`); the pasted row is prepended via `onClassified` with server-side dedup of repeat pastes (App.tsx:96-98). Offline/persist-failure falls back to a negative-id placeholder with an honest all-gray `confidence` gate, `model_version:"offline"`, score 0.5 (api.ts:290-309) — the paste box then shows "API unreachable — offline placeholder, not a score" (phrasebook offlineNote). Ctrl+Enter submits; busy skeleton in the detail pane (feed.tsx:306-317).

**Work queue** (feed.tsx:182-303): 5 filter chips with live counts — Needs decision / Priority / Reviewed / No review needed / All (feed.tsx:128-162) — plus a text search over `site + activity + text` (feed.tsx:62-66, client-side only). Rows show site label (with inference fallbacks, report-display.ts:21-53), activity, date, and a right-side chip: "LIVE" for session pastes, amber "Duplicates" for triggered near_dup, green "Reviewed", quiet "Review" for any gray gate, else the BandBadge. No sort control, no pagination.

**Detail pane**: if the selected report has triggered non-badge gates, one `GrayStateCard` **per gate** (feed.tsx:318-328); otherwise a single `TriageCard` (feed.tsx:330-335).

**TriageCard evidence inventory** (what the reviewer actually sees, in order):

| # | Evidence | Where | Skeptic-verifiable from this screen? |
|---|----------|-------|--------------------------------------|
| 1 | Verdict: "High/Moderate/Low review priority" + amber 3px top border for MODERATE/HIGH | triage-card.tsx:51-56, 68-72 | No — band is derived **client-side** at fixed 0.7/0.4 (api.ts:129-131); thresholds are neither shown nor the server's tuned point |
| 2 | "triage score 0.87" mono number | triage-card.tsx:85-93 | No provenance: `model_version` is in the payload (types.ts:80) but **never rendered anywhere on this surface**; no calibration or threshold context |
| 3 | Site · activity (+ "Scored in sections" slate dot when chunked) | triage-card.tsx:100-114 | Partially — site falls back to regex inference or first-sentence title (report-display.ts:21-53), so the "site" may be model-guessed without saying so |
| 4 | Near-dup banner: "Matches a training record — memory, not generalization" + mono detail | triage-card.tsx:117-128 | **Yes** — live detail is verifiable: `near-dup banner: cosine=1.000 with index row syn-lof-a-0151 (>= 0.91)` (gates.py:272-274, observed live) |
| 5 | Top-3 in-scope IOGP rule bars with 2-dp probabilities | triage-card.tsx:131-151 | Partially — bar vs number is consistent, but only 3 of 7 in-scope rules are shown (`slice(0,3)`, line 136); the 2 declared out-of-scope rules (PTW, Bypassing, forced prob 0 in api.ts:161-163) are filtered out and their declaration is invisible here; no per-rule evidence linkage |
| 6 | "Well-control / barrier tag" quiet label when `well_control` true | triage-card.tsx:152-156 | No — a bare boolean tag with no detail of what fired it; the explanatory gate (`well_control_watch`) only fires when score < flag threshold (gates.py:279-297), so a flagged well-control report shows the tag with zero justification |
| 7 | Evidence spans: amber `<mark>` over server-validated char offsets | highlighted-text.tsx:15-43 | **Yes, strongly** — spans are verbatim slices of the canonical text, sorted/de-overlapped defensively (lines 15-20); a reader can check every highlight against the report text |
| 8 | "Why this score?" expander → explanation | triage-card.tsx:246-288 | **Yes when loaded** — template includes score, threshold ("crossed the 0.66 review threshold" observed live), rule names with probs, and verbatim quoted spans; LLM rewording is labeled "phrased by local LLM · cached" (lines 260-265) |
| 9 | Decision footer: Confirm SIF-potential / Not SIF-potential | triage-card.tsx:167-204 | See findings 6-7 |

**GrayStateCard** (gray-state-card.tsx:102-185): one card per triggered gray gate — plain-English gate name and sentence, the report text verbatim in a blockquote, site/activity/date line, and a collapsible "Technical detail" showing the server's numeric gate detail (e.g. `len=10 < 20 and no short code`, observed live). Same Confirm/Not-SIF footer. The card never shows the model score — intentional, but the reviewer cannot see whether a scored number exists at all.

**Gate legend** (gray-state-card.tsx:189-215): all 10 gates with EN/हिं names and sentences, always accessible under "Why some reports need manual review" (feed.tsx:341-348).

---

## Findings

**F1. BLOCKER — Mock fixtures collide with live report ids; transient API errors silently swap real data for fabricated data on a safety-critical surface.**
`App.tsx:19-20` seeds the entire UI from `mock.REPORTS` (9 scripted reports, ids 2588-2619, mock.ts:227-437) and swaps when the API answers. Every getter falls back to mock on *any* error: `getReports` → the whole scripted queue (api.ts:253), `getReport` → `REPORTS.find(id)` (api.ts:262), `getExplanation` → `MOCK_EXPLANATIONS[reportId]` (api.ts:361). The collision is real, not theoretical: I measured `GET /api/reports/2614/explanation` → 200 with triage score **0.97** and near-dup cosine 1.000 vs `syn-lof-a-0151`; `MOCK_EXPLANATIONS[2614]` (mock.ts:148-162) claims "Triage score 0.87 … Line of Fire (0.91)…", i.e. a **fabricated explanation with different numbers for a real report**, served whenever that one fetch hiccups (server restart, proxy blip). Same for ids 2588, 2597, 2601, 2615, 2619. For a tool whose entire pitch is "black-box scores are unacceptable", an error path that renders invented model output for a live report is disqualifying as-is.

**F2. BLOCKER — Only 200 of 5,056 reports are reachable, the queue is ordered by recency, and there is no sort-by-score anywhere.**
`getReports(limit=200)` is the hard ceiling (api.ts:245; App.tsx:29 calls it with the default); the server supports `limit<=1000` + `offset` (routes.py:230-231) but the client never uses offset, has no pagination/load-more, and no sort UI. Server order is `ORDER BY r.id DESC` (storage.py:415) — newest first, not risk-first. Consequence: the "Priority queue" filter (band ≥ 0.4, no gray gates — feed.tsx:69-72) holds thousands of rows (mean_score 0.6997, 3,587 flagged ≥ 0.66) presented in **id order**; a reviewer "working from the top" (priorityGuidance, phrasebook.ts:102) is reviewing by insertion order, not by score. Reports 201-5,056 (including potentially higher-scored older rows) are invisible and unsearchable. This is the volume story collapsing at the exact surface meant to carry it.

**F3. MAJOR — Three different threshold regimes decide "flagged" depending on which surface you ask.**
Client band: HIGH ≥ 0.7, MODERATE ≥ 0.4 (api.ts:129-131, comment claims it "matches the server's gray band" — it matches only the 0.4 edge). Server flag threshold: **0.66**, tuned from metrics.json (classifier.py:179-187; confirmed live: explanation template says "crossed the 0.66 review threshold"). Gray/confidence band: [0.40, 0.60] (config; gates.py:215-224). So a 0.45 card shows amber "Flagged for HSE review" (triage-card.tsx:95-96) while `/api/metrics/summary` does not count it as flagged (flag_rate 0.7095 is at 0.66), and a 0.67 shows "Moderate" although the server flagged it. Reviewer-facing amber and headline metrics disagree by construction.

**F4. MAJOR — The near-dup banner is noise: it appears on ~60% of the register.**
`gate_trigger_counts.near_dup = 3021` of 5,056 rows (measured this session). On the triage card that is the amber "Matches a training record — memory, not generalization" banner (triage-card.tsx:117-128) and in the queue an amber "Duplicates" chip (feed.tsx:270-278). A humility disclosure designed for rare memory-leak cases is now the most common element on the screen — it cannot function as signal. This is the UI face of the orchestrator's finding 2 and it also drags ML jargon ("generalization") into an HSE reviewer's face (see Pain points).

**F5. MAJOR — Score provenance is invisible on the triage surface.**
`model_version` travels on every prediction (types.ts:80) yet is rendered nowhere on this screen (only the global health line shows a count, App.tsx:128-139). No model name, no calibration statement, no operating point. Combined with F3 (client-derived band), a hostile judge can fairly call the verdict line a frontend re-interpretation of an unlabeled number. The honesty infrastructure exists in data but not on the surface where it matters.

**F6. MAJOR — Override flow: optimistic success, silent offline degradation, no undo, contradictory decisions allowed.**
Trace: click → `decide()` sets state and calls `onOverride` (triage-card.tsx:62-65) → App POSTs `/api/review` with `labeler:"hse_reviewer"` hardcoded (api.ts:414) → "Decision recorded" renders immediately (triage-card.tsx:196-200), *before* the POST resolves. On success, `getOverrides()` refetch flips the footer to "Reviewed by HSE" and the row leaves the Needs-decision filter (App.tsx:55-61, feed.tsx:73). On **any** failure — offline, or a 4xx like the server's 404 for unknown report ids (routes.py:368-369) — the catch silently appends a local-only override with an identical "Decision recorded" message (App.tsx:62-77): a reviewer cannot tell a persisted audit decision from an in-memory one. No undo; the opposite button stays live, so Confirm-then-Not-SIF records two contradictory overrides with no warning (server keeps both; only `/review/export` collapses latest-wins, routes.py:381-388). No rationale capture although `postReview` supports `rationale` (api.ts:404-417) and no reviewer identity exists.

**F7. MAJOR — The audit trail's vocabulary is broken in three places.**
(a) The UI stores `old_value = current.prediction.band` ("HIGH") for field `sif_label` (App.tsx:58) — a band string inside a label field. (b) The mock fixtures contain rows the live write contract rejects: mock override id 2 has `new_value "HIGH"` for `sif_label` and id 3 uses `field "line_of_fire"` (mock.ts:541-550), but `OverrideWrite` allows only `field ∈ {sif_label, rules, notes}` (schemas.py:163) with `sif_label ∈ ("sif_potential","not_sif_potential")` (schemas.py:156, 167-170) — the fixtures predate the SEV2-3 contract. (c) `reviewedReportIds` is built from *all* override rows regardless of field (App.tsx:85), so a facet override (or the mock's stale rows) marks a report "Reviewed by HSE" with no SIF decision ever recorded — and the reviewed state on the card shows no who/when (triage-card.tsx:168-172).

**F8. MAJOR — No temporality on the money shot, and event-vs-ingestion dates are conflated.**
TriageCard renders site/activity and nothing else (triage-card.tsx:100-114): no `reported_at`, no contractor, no source, no report id. The queue shows a date but it is `s.report.date ?? created_at.slice(0,10)` (api.ts:187) — for the entire 5,056-row register ingested 2026-09-25 (observed live: `date:null` on stored rows), every card silently displays the *ingestion* date as if it were the event date. A triage tool whose domain standards (API RP 754, IOGP 456) are time-series has a money shot with zero time semantics.

**F9. MAJOR — The honesty system covers 3.8% of rows while the amber queue is the real workload.**
Summing measured gray-action gate triggers: 29+42+78+36+5+1 = **191** rows (well_control_watch, negation, confidence, drill, severity_watch, min_length) vs 3,587 flagged at 0.66. The 10-gate humility system — the product's strongest honesty asset — gates a tiny minority; the vast majority of reviewer load is the unsorted, unfiltered "Priority queue" of F2. The demo narrative ("gray gates route the uncertain") and the production reality (71% amber) are the same screen telling two different stories.

**F10. MINOR — Selection silently jumps.** `selected = find(selectedId) ?? filteredReports[0]` (feed.tsx:83-84): after recording a decision, or toggling a filter, the detail pane switches to a different report with no signal beyond the highlight. Mid-review context loss.

**F11. MINOR — Explanation expander is one-shot with a misleading failure message.** The fetch fires once per report (`requestedFor.current` set before the request, triage-card.tsx:230-244); a failed fetch permanently shows "Explanation is unavailable while the service is offline" (phrasebook.ts:148-151) even when the failure was a 404 or a timeout *while online*, and there is no retry control. Loading/empty states are otherwise well built (skeleton, cancel flag, template floor always renders once loaded — triage-card.tsx:268-285). Pasted rows always carry a bundled template (`llm=0`, api.ts:279), so the "phrased by local LLM" chip can only ever appear via cached server rows — and live today `reworded: null` on every fetch (measured), i.e. the LLM path is invisible in the current deployment.

**F12. MINOR — Rule display is a top-3 peek, not a verdict.** 4 of 7 in-scope rules hidden (`slice(0,3)`, triage-card.tsx:136); out-of-scope declaration (PTW/Bypassing "shown as such, never faked" — types.ts:50-51) never reaches this surface. A skeptic cannot see what the model *didn't* fire on.

**F13. MINOR — One gray card per gate multiplies the same report.** A report triggering two gray gates renders two stacked cards, each repeating the full text and its own Confirm/Not-SIF pair (feed.tsx:318-328); one decision marks both reviewed, which is correct behavior but visually implies two decisions exist.

**F14. KEEP-WORTHY — Accessibility discipline is real.** `aria-pressed` filter chips (feed.tsx:209), `aria-current` queue rows (feed.tsx:246), `aria-busy` skeletons, `role="status"` decision confirmation, sr-only search label, skip link (App.tsx:110-115). This is the kind of polish judges should see called out.

---

## Pain points (a real HSSE reviewer at an oil & gas major)

1. **"Memory, not generalization" is engineer-speak.** An HSE superintendent reads "Matches a training record — memory, not generalization" (triage-card.tsx:120) and asks: *is this a real duplicate report I should merge, or a model confession?* Neither the banner nor the queue chip says what to *do* (dismiss? merge? investigate the original?). Gate `long_input`'s technical detail leaks "sliding-window max-pool applies (length-OOD)" (gates.py:376) — same problem.
2. **The Duplicates chip has no destination.** Near-dup rows carry an amber chip (feed.tsx:270-278) but near_dup is badge-action, so those rows sit in Priority/Informational filters; there is no "duplicate lane" to work through 3,021 of them.
3. **"Reviewed by HSE" is anonymous and undated** — no reviewer name, no timestamp, no way to see *what* was decided (confirm vs not-sif) without leaving to the history tab.
4. **Working the queue has no throughput affordances:** no keyboard navigation (j/k, Enter), no next/prev, no progress counter ("12 of 87 this shift"), no bulk actions, no aging/SLA display. For hundreds per shift the mouse-only one-card-at-a-time loop is the bottleneck, not the model.
5. **Trust inversion:** the most verifiable evidence (spans, gate numeric details, template explanation) is present but the least verifiable (score provenance, threshold, band derivation) sits at the top of the card in the biggest type.
6. **Ctrl+Enter hint but no keyboard story elsewhere** — the only shortcut on the surface is paste submission (paste-classify.tsx:36-41).

## Gaps vs production

- Pagination / server-side filtering / sort by score, date, site, contractor (server supports `offset`; client doesn't plumb it — routes.py:230-231).
- Virtualization or any large-list strategy; `limit=200` currently hides the problem instead of solving it.
- Date-range filter anywhere on the triage surface (orchestrator finding 5 applies to the money screen too).
- Decision lifecycle: owner, due date, closure status, undo/correction — today `sif_label` overrides are append-only rows with no state machine (routes.py:361-371); OISD-style FIR/IIR clocks are unrepresentable.
- Reviewer identity + rationale capture (schema supports both; UI supplies neither — api.ts:414, App.tsx:55-60).
- URL/deep-link state: selected report, filter, and query die on refresh; no shareable link to "the report I escalated".
- Honest degraded modes: no error banner when the API dies mid-session (only the paste box ever signals it); mock fallbacks (F1) instead of visible degradation.
- Model provenance block on the card (model_version, calibration/threshold, at minimum a link to the operating point).
- Distinct event-date vs ingestion-date fields (data carries both today; UI collapses them, api.ts:187).

## Recommendation

- **KEEP** — the gray-gate system (GrayStateCard + numeric `gate.detail` + legend): the single strongest skeptic-verifiable honesty asset; fix its volume problem (F4/F9), don't dilute it.
- **KEEP** — `HighlightedText`'s server-validated-span doctrine (highlighted-text.tsx:14-20, "UI only slices, never computes") — exactly the right trust boundary.
- **KEEP** — lazy explanation with deterministic template floor and labeled LLM rewording (triage-card.tsx:209-288); add a retry affordance and a truthful failure label.
- **KEEP** — paste flow with `persist=1` real ids and the honest offline gray placeholder (api.ts:266-311) — this is what "never fake a score" should look like; it is the *opposite* of F1's other fallbacks.
- **KEEP** — the a11y patterns (F14/F14 note above) as the baseline for the redesign.
- **REMOVE** — mock-by-id fallbacks on `getReports`/`getReport`/`getExplanation` (api.ts:253, 262, 361): an error must render a visible degraded state, never fabricated data for real ids.
- **REMOVE** — client-side `bandFor` (api.ts:129-131): the server must emit the band at its tuned operating point (0.66) so card, metrics, and queue agree.
- **REMOVE** — "memory, not generalization" as primary copy; replace with reviewer-actionable language ("Duplicate of an earlier record — compare before deciding"), keep the ML framing in the technical detail expander only.
- **ADD** — server-side score sort + offset pagination + "load more"; make the Priority queue ordered by `sif_score` desc.
- **ADD** — decision integrity: rationale input, reviewer identity (even a local username picker), undo window, and disable/confirm on the opposite button after a choice.
- **ADD** — report date + contractor + id on the triage card; separate `event_date` from `ingested_at` in the UI.
- **ADD** — a model-provenance line on the card (model_version, flag threshold, calibrated) — cheap, and it defuses the black-box objection where it matters most.
- **MERGE** — multi gray cards for one report into a single card listing triggered gates with one decision (feed.tsx:318-328).
- **MERGE** — mock fixtures behind an explicit demo mode (`?demo=1` or a build flag) instead of the default data path; `DENSITY_BEFORE` and scripted beats belong to a demo context, not the error path.