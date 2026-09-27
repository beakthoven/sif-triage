# Discovery 51 — Visual QA of the Insights Tab (screenshots, live 8177)

**Role:** Multimodal visual-QA auditor (Phase 0, read-only; screenshots-only writes)
**Date:** 2026-09-25
**Surface:** http://127.0.0.1:8177/ → Insights tab (Locations / Recurring patterns / bulk ingest)
**Method:** Playwright MCP against the live stack (GET-only; no source changes, no restarts, port 8183 avoided). Every claim below is backed by a screenshot in `artifacts/qa-evidence/` read back with vision, and cross-checked against source (`dashboard/src/views/density.tsx`, `patterns.tsx`, `insights.tsx`, `App.tsx`, `index.css`) and read-only API GETs the app itself makes.

## Screenshot inventory (artifacts/qa-evidence/)

| File | What it shows |
|---|---|
| insights-01-default-1440.png | Insights/Locations default, 1440×900 — saturated table, dead Movement |
| insights-02-fullpage-1440.png | Full page (1440×1414) — entire sub-tab is subtitle + 2 buttons + table |
| insights-03-mobile-390-default.png | 390×844 — table clipped at Reports; flag rate off-screen |
| insights-04-mobile-fullpage.png | 390×1464 full page — confirms only Rank/Site/Reports visible |
| insights-05-mobile-table-scrolled-right.png | After 289px scroll — numbers shown, site names gone |
| insights-06-patterns-default-1440.png | Pattern cards #1–#4, all "100 flagged per 100" |
| insights-07-pattern-card-statdetail-expanded.png | (captured Triage after a session flip; superseded by 08) |
| insights-08-pattern-cards-statdetail-two-expanded.png | Cards #1/#2 with "lift 1.5× · 95% CI [0.91, 1.00]" |
| insights-09-patterns-barrier-tab.png | BUG EVIDENCE: after clicking "Activity × failed barrier" the workspace is back on Triage |
| insights-10-patterns-barrier-cards.png | Activity × failed-barrier cards (all 100/100 again) |
| insights-11-after-show-all-click.png | BUG EVIDENCE: after "Show all locations (341)" click, workspace back on Triage |
| insights-12-density-341-expanded-tail.png | (captured the session flip to Triage; superseded) |
| insights-12-density-tail-tiny-n.png | Expanded 341-row table top (Hindi locale active at capture). Tail rows themselves DOM-verified live: 271/341 n≤5, 173 n=1, 58 @100.0%, and n=3@33.3% (#79) ranking above n=35@0.0% (#80) |
| insights-13-focus-main-tab-arrowright.png | Keyboard ArrowRight: visible bracket focus ring on main Insights tab (Hindi locale active at capture) |
| insights-14/14b-focus-nested-pill-retry.png | Nested pill Tab-stop attempts — ring not visible at capture; see caveats |
| insights-15-mobile-patterns-390.png | 390×844 pattern cards — wraps fine; main tab label still clipped |

## 1. Density table as a hostile reviewer sees it

Column headers (verbatim): **Rank · Site · Reports · Flagged · Flag rate · Movement**. Sample rows: `#1 Kathalguri GCS 213 213 100.0 per 100 0`, `#2 Moran GGS-1 105 105 100.0 per 100 0`, `#13 Rig OIL-36, NHK 2 2 100.0 per 100 0`, `#14 Baghjan, Well BHJ-112 1 1 100.0 per 100 0`.

- **Saturation confirmed and worse than claimed.** 58 of 341 rows have flagged == reports (100.0%); the entire top-9 is 100.0%, and #14–#20 are n=1 wells. Screenshot 01/02.
- **Tiny-n confirmed exactly:** API `GET /api/density?by=site` returns 341 rows; **271 have n≤5, 173 have n=1**. Both API and the rendered DOM agree.
- **No statistical annotation anywhere.** No Wilson CI, no baseline, no minimum-n note, no tooltips (no `title` attrs in source). The only "statistics" on screen is the gray suffix "per 100". A one-report well ranks as the 14th-best inspection target with the same visual authority as a 213-report site.
- **Sort is statistically illiterate:** rate desc, tie-break n desc — so `n=3 @ 33.3%` (#79) outranks `n=35 @ 0.0%` (#80). Rows with *zero* flags (actually useful safety info) pile up mid-table unmarked. API field `mean_score` exists but is never rendered.
- **Not actionable.** I cannot tell "where to inspect next" from this: 58 tied-at-100% cells, 271 noise rows, no confidence, no time context.

## 2. Movement column — reads broken on fresh load

Every row shows `0`. Source: `prev_rank - rank` (density.tsx:243) and `prev_rank` only exists after an ingest re-rank passes the previous snapshot. A first-time user concludes the column is dead/stuck. Up-deltas render bold black, down-deltas gray with a minus — no arrows, no color semantics, no legend.

## 3. Charts — definitively ZERO

No chart, bar, sparkline, or plot exists in any Insights sub-surface (screenshots 01/02/06/08/10/15). Source agrees: `patterns.tsx` comment says "No sankey, no chart lib"; the only chart artifacts are dead CSS tokens `--chart-1..5` (index.css:84–88) used by no component.

## 4. Time dimension — definitively ABSENT

No date filter, no trend, no week/month selector, no per-period deltas anywhere in the tab (screenshots + source). `reported_at` exists in the data model (types.ts:93) but Insights never touches it. **API RP 754 / IOGP 454-456 are time-series standards by definition; a static ranking cannot answer "is this getting worse?" This surface does not satisfy leading-indicator practice.**

## 5. Pattern cards

Face shows: rank, "activity × site" (or × barrier), a rule tag (Working at Height / Confined Space / Hot Work / Driving), "N reports reviewed", "100 flagged per 100". **n is present; lift and CI are buried** in a per-card collapsed `<details>` "Statistical detail" (patterns.tsx:99–106): `lift 1.5× · 95% CI [0.91, 1.00]`. The CI is ambiguous — it is the Wilson CI of the *flag rate*, but reads as the CI of the lift. No tiny-n caveat on cards either.

Degeneracy confirmed from API: all 40 patterns (both kinds) have `sif_rate=1.0` and `lift=1.499` — every card is clamped at the same lift, so "lift-ranked" ordering is arbitrary within ties and the headline stat differentiates nothing.

## 6. Bulk-ingest placement

`Import CSV` (primary, upload icon, hidden file input) + `Run demo batch` + progress bar + "climbed to #1" status live **inside Insights → Locations, top-left above the table** (density.tsx:145–210). Prominent once found — but semantically buried: an analytics ranking sub-tab is the last place a reviewer looks for data ingestion, and nothing on Triage or Decision history hints it exists. The demo money-beat (Kathalguri #2→#1 FLIP re-rank) is chained to it.

## 7. Keyboard / nesting clarity

Three nesting levels: main tabs (underline) → "Insight type" pills → "pattern kind" underline tabs. Main tabs are Radix with working arrow-key roving focus and a visible bracket-style ring (insights-13). The deepest "pattern kind" tablist is hand-rolled buttons with `role="tab"` but **no arrow-key roving tabindex** (patterns.tsx:44–58) — violates the WAI-ARIA tabs pattern; three Tab-stops before any data. The nested pill ring could not be captured cleanly (see §8); its CSS (`focus-visible:ring-[3px]`) exists. A11y text of the rate cell reads "100.0per 100" (visual gap only).

## 8. Session-integrity anomalies (root cause unresolved — flagged, not attributed)

Across the session the workspace flipped Insights→Triage uncommanded 3× (screenshots 09, 11 are direct evidence), the language toggle changed to Hindi uncommanded (visible in insights-12/13), and once a **second browser tab opened at 127.0.0.1:8199 serving a different dataset (4,548 vs 5,056 reports)**. No redirect code exists in the dashboard source; `workspace` has a single writer (`onValueChange`); no reloads occurred (single document request). DOM probes showed `activeElement` jumps with `:focus-visible=false` I did not cause. Strongest hypothesis: **the Playwright browser is shared with another concurrent QA process** (parallel subagent clicking the same tab). The redesign should make tab state URL-addressable (`?tab=insights&sub=patterns&kind=...`) — it makes navigation observable, restoreable, and this class of ambiguity debuggable.

## Top defects for the redesign plan (ranked)

1. Ranking with no uncertainty: 100%-saturated + n=1-dominated ordering; need Wilson lower bound / shrinkage / min-n floor in the *sort*, and a visible CI or "low-n" badge (271/341 rows qualify).
2. No time axis anywhere — fails API RP 754 / IOGP leading-indicator framing; add period filter + trend deltas.
3. Zero charts; dead chart tokens; table-only decision surface.
4. Movement column dead on load; lift clamped at 1.5× for all patterns; CI ambiguous and hidden.
5. Bulk ingest inside an analytics sub-tab; `by=activity|contractor` facets unreachable from the UI (hardcoded `by=site`, density.tsx:71).
6. Mobile: flag-rate column off-screen with no scroll affordance; main tab label clipped.
7. Hand-rolled tablist without arrow-key support; "100.0per 100" a11y text.
8. Uncommanded workspace flips / shared-session ambiguity (URL-addressable state).
