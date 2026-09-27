# Discovery 12 — Frontend Insights / Analytics / Pattern-Mining Audit

**Role:** Insights / analytics / pattern-mining auditor (Phase 0, read-only)
**Date:** 2026-09-25
**Repo:** /home/dakkshesh/sih26-round2 · Live stack observed at http://127.0.0.1:8177 (GET requests only; nothing written or restarted)

## Files actually read (with line counts)

| File | LoC | Notes |
|---|---|---|
| dashboard/src/views/insights.tsx | 34 | full read |
| dashboard/src/views/density.tsx | 260 | full read |
| dashboard/src/views/patterns.tsx | 125 | full read |
| dashboard/src/lib/mock.ts | 553 | full read |
| dashboard/src/lib/api.ts | 426 | full read (getDensity 367–376, getPatterns 381–390, ingestCsv 329–334, fetchDemoIngestCsv 340–350, withRanks 205–212) |
| dashboard/src/lib/use-flip.ts | 36 | full read |
| dashboard/src/lib/types.ts | 182 | full read |
| dashboard/src/lib/phrasebook.ts | 166 | targeted read |
| dashboard/src/App.tsx | 213 | full read (tab structure) |
| dashboard/src/index.css | 130–150 | reduced-motion + chart tokens |
| dashboard/e2e/dashboard.spec.ts | 38–45 | insights coverage |
| app/routes.py | 263–358 | /density, /patterns servers |
| app/storage.py | 439–469 | density_aggregate |
| app/classifier.py | 179–200, 370–395 | flag_threshold |
| docs/deck/demo_card.md | 32 | money-beat expectation |
| artifacts/patterns/patterns.json | — | parsed (provenance + saturation) |
| artifacts/models/masked-v2/metrics.json | — | operating_point_test_tuned |

**Tools:** Read, Grep, Bash (curl GETs against 127.0.0.1:8177, `wc`, `git log` history inspection, python JSON inspection of patterns.json/metrics.json). No writes except this file; no builds, no installs, port 8177 untouched.

## What exists today

**insights.tsx (34 LoC) is a thin two-item tab shell, not a three-part composite.** It renders one nested `Tabs` (insights.tsx:20–31) with exactly two `TabsContent`s: `DensityView` ("Locations") and `PatternsView` ("Recurring patterns"). The "ingest trigger" the orchestrator described is not a third sibling — it is a pair of buttons *inside* DensityView (density.tsx:160–181): a real CSV upload button and a "Run demo batch" button that fetches `public/live_ingest_500.csv` and POSTs it through the real `/api/ingest` (api.ts:329–334, 90 s timeout because the 500-row beat takes ~15 s server-side). The view's only own state is which sub-tab is open.

**DensityView (260 LoC)** — the strongest surface in the app:
- Fetches `GET /api/density?by=site` on mount (density.tsx:68–79). The API supports `by=site|activity|contractor` (routes.py:266); the UI hardcodes `"site"` (density.tsx:71, 117) — the other two facets are unreachable from any screen.
- Renders a plain shadcn table: rank, site, reports, flagged, flag-rate per 100, movement (density.tsx:214–248). No chart, no bars.
- Money beat: "Run demo batch" POSTs the 500-row extract through the real ingest path, then `getDensity("site", rows)` re-fetches with the pre-ingest snapshot as `prev` so `withRanks` (api.ts:205–212) derives `prev_rank`, and rows re-sort with FLIP (density.tsx:117; comment density.tsx:20–27 documents the demo_pre.db restore dependency).
- Honest failure handling: on ingest error it keeps live rows and shows a destructive alert rather than swapping in mocks (density.tsx:121–125); `role="progressbar"` with proper aria values (density.tsx:183–195); `window.confirm` before the destructive live demo ingest (density.tsx:101).

**PatternsView (125 LoC)** — two kinds (`site_activity`, `activity_barrier`) switched by *manual* `role="tab"` buttons, not radix (patterns.tsx:38–60 — a second, different tab implementation inside the same view). Ranked list of top 10 cells: `activity × site/barrier`, rule tag, `n "reports reviewed"`, rate per 100, and lift + 95% CI hidden behind a `<details>` "Statistical detail" expander (patterns.tsx:99–106). Its own comment: "No sankey, no chart lib — one sentence, one count, honest stats" (patterns.tsx:12).

**use-flip.ts (36 LoC)** — minimal, correct FLIP: caches per-key `getBoundingClientRect().top`, on commit applies an inverse `translateY` then transitions to 0 over 600 ms cubic-bezier (use-flip.ts:18–33). Doubly guarded for reduced motion: a JS `matchMedia` gate (use-flip.ts:19) *and* a global CSS kill-switch `@media (prefers-reduced-motion: reduce)` zeroing all transition durations with `!important` (index.css:144–150), which also covers the progress-bar width transition.

**Fixture side (mock.ts).** `DENSITY_BEFORE`/`DENSITY_AFTER` (mock.ts:484–500) are the scripted offline re-rank snapshots (Baghjan 3→1). `PATTERNS` (mock.ts:505–516) carries 5+5 hand-written rows with varied rates (43%, 38%, …) and CIs that look statistically alive. `validateMock()` (mock.ts:441–480) self-checks span offsets and shape invariants at module load — good hygiene, but the *patterns* fixtures are now further from reality than the density ones (see F1).

**Server contract (what these views actually consume):**
- `/api/density?by=` — one SQL GROUP BY, `n_flagged = SUM(sif_score >= flag_threshold)`, sorted `(-sif_rate, -n_reports)` (storage.py:441–469). No date param.
- `/patterns?kind=` serves a **precomputed file first** (`artifacts/patterns/patterns.json`, routes.py:289–331); only when the file is absent does it fall back to live DB aggregation. `activity_barrier` has *no* live fallback ("ingested reports carry no barrier facet", routes.py:326, 332–333).

**History (special task 2).** `git log` on App.tsx: at commit `716c2c1` App.tsx had **three top-level tabs** — `feed | density | patterns` (old App.tsx lines 130–147, verified via `git show`). Commit `afe32ad` ("Post-ship hardening … insights redesign") merged density+patterns under the single Insights tab with the nested two-tab structure that exists now. So: **density.tsx / patterns.tsx are not dead code** — they are the sole bodies of the merged tab — but they are reachable *only* through the nested tabs; with no router and no URL sync, neither surface is deep-linkable and both reset to "Locations" on reload. docs/deck/demo_card.md:32 still describes the beat as living on a "density view", stale relative to the current IA.

## Findings

**F1 — BLOCKER: the Patterns tab is saturated synthetic statistics presented as findings.**
The server serves `artifacts/patterns/patterns.json` before ever touching the DB (routes.py:329–331). I parsed the file: **all 197 site×activity cells have `sif_rate == 1.0`** (`n_sif == n` for every row), and **all 197 have the identical lift 1.499** — the ranking is purely an n-count tiebreak. 121 of 137 barrier cells are also at 1.0. The live API confirms: `GET /api/patterns` returns rows like `derrick/mast climbing × Workover Rig #7, n 37, sif_rate 1.0, lift 1.499, CI [0.906, 1.0]`. The UI renders each as "37 reports reviewed · 100 flagged per 100" (patterns.tsx:91–97) with CI `[0.91, 1.00]` in the expander. Root cause: the mining corpus is synthetic with base rate **0.6673** (patterns.json `corpus` field: 9,027 rows, 6,024 SIF), so lift is capped at 1/0.6673 = 1.499 and planted cells were seeded 100% SIF. Why it matters: a hostile judge who opens the expander sees a 95% CI that says "this cell is 91–100% SIF" on *every* row — the statistical furniture is present but vacuous, which is worse than absent. These numbers also *cannot change* with ingests (barrier facet doesn't exist in ingested reports, routes.py:326), so the "Import more reports to begin" empty-state copy (phrasebook.ts:129) is misleading.

**F2 — BLOCKER: the density ranking is saturated by the same synthetic seed.**
Live `GET /api/density?by=site` today: 341 rows; the top 8 are all `sif_rate 1.0` with mean_score 0.91–0.97 (Kathalguri GCS 213/213, Moran GGS-1 105/105, …); **58 rows at exactly 1.0**; **271 of 341 rows have n ≤ 5**; median sif_rate 0.0; two case-duplicate site keys ("workover rig #5"/"Workover Rig #5"). docs/deck/demo_card.md:32 openly documents the planting ("site #1, 213/213 flagged … min score 0.760 vs 0.658 threshold"). The flag threshold driving `n_flagged` is the D19 tuned point `operating_point_test_tuned.threshold_calibrated = 0.658` (metrics.json; wired via classifier.py:179–187, routes.py:272). So the table the demo wants judges to act on ("where to inspect next", density.tsx:147 subtitle) shows a tie of ten 100%-flagged sites, then falls off a cliff to n≤5 cells — no discrimination between #1 and #10, and no statistical distinction between n=13@100% and n=213@100%. This is the frontend face of the domain agent's 71% flag-rate finding; the seed data was *constructed* so the money beat's target site saturates.

**F3 — MAJOR: no time dimension in either surface, client or server.**
Neither `/density` nor `/patterns` accepts a date parameter (routes.py:266, 319–321); neither view offers one; no trend or movement-over-time exists anywhere. The only "movement" is `prev_rank − rank` from the in-session re-rank snapshot (api.ts:205–212) — which is **0 for every row on a fresh page load** (withRanks defaults `prev_rank = rank` when `prev` is null, api.ts:210), so the Movement column reads as a bug 99% of the time it is on screen. API RP 754 / IOGP 456 leading-indicator practice is time-series by definition; a density ranking with no date filter cannot answer "is Kathalguri getting worse or was that one month?" The data exists (reports carry `date`/`created_at`; adaptReport exposes `reported_at`, api.ts:187) — the analytics surfaces just ignore it.

**F4 — MAJOR: zero charts, and the chart tokens are dead code.**
Grep across dashboard/src for `<svg|<rect|<path|chart|d3|recharts|…` finds only CSS token definitions `--chart-1..5` (index.css:22–25, 84–88) consumed by nothing, plus the patterns.tsx comment bragging about no chart lib. Confirmed: the entire analytics surface is text tables. For a finale pitched as "where to inspect next", there is no flag-rate bar, no rate-vs-n visual, no CI whisker, no sparkline, and above all no time series. The tokens suggest a chart was planned and never built.

**F5 — MAJOR: the app's only bulk-ingest surface lives inside an analytics view.**
feed.tsx contains zero csv/ingest/upload references; the single CSV-import affordance in the whole product is the button pair inside DensityView (density.tsx:149–181). A data-management action (ingest 500 rows, mutating server state) is embedded in the "where to inspect next" ranking table, next to a demo-fixture button. Coherence verdict on special task 1: the tab is *structurally* coherent (34 LoC, clean composition) but *conceptually* incoherent — Insights mixes "look at the data" with "change the data". The header-count/feed refetch coupling (`onIngested → refreshLive`, App.tsx:100–106) exists *only because* ingest lives here.

**F6 — MAJOR: mock-first paint shows fabricated numbers in the insights surfaces.**
DensityView initializes `rows = DENSITY_BEFORE` (density.tsx:56) and PatternsView initializes with mock `PATTERNS` (patterns.tsx:16–18) before the live fetch resolves. The footer discloses "Synthetic OIL-style demo data" (App.tsx:206–208), but in practice the swap is visible: mock and live share key strings (e.g. "Moran GGS-1" — mock rank 4, live rank 2 at sif_rate 1.0), so on first load the flagged column jumps 11→105 while `useFlip(rows)` (density.tsx:66) animates the row sliding — motion not tied to any user action, immediately after fabricated numbers were on screen. The mock-first doctrine is defensible for the triage feed; for an *analytics* surface whose whole value is truthful numbers, it is the wrong default (compare: the classifier paste flow deliberately refuses a fake score, api.ts:289–310).

**F7 — MINOR/MAJOR: the FLIP beat works, is accessible, and is fragile operationally.**
The hook itself is sound: per-key position cache, inverse transform, 600 ms ease-out, double reduced-motion guard (use-flip.ts:19, index.css:144–150) — motion degrades to a static swap correctly, and RankDelta deliberately uses weight not hue (density.tsx:29–42), consistent with the "no red/green" rule. But: (a) it is the *only* consumer of meaningful motion in the app and it fires on any rows commit, including the F6 initial swap; (b) the beat requires the demo_pre.db restore (density.tsx:20–27) — on today's live 8177 DB Kathalguri is *already* #1 (verified via API), so a naive re-run shows zero movement and the "just climbed to #1" note never appears; (c) there is **no e2e coverage** of the ingest/re-rank beat — dashboard.spec.ts (38–45) only smoke-checks tab visibility and the "Statistical detail" expander; grep for density/flip/ingest in e2e finds nothing.

**F8 — MAJOR: statistical presentation is half-honest — patterns have n+CI, density has nothing, and neither shows the baseline.**
Patterns rows show n (patterns.tsx:91), per-100 rate (:95), and lift+CI behind one click (:99–106). That is the right skeleton — but "lift 1.5×" is meaningless without the corpus base rate (0.667), which is never surfaced; the label "reports reviewed" (phrasebook.ts:130) misdescribes *mined corpus counts* as reviewed reports; and no provenance is stated on the surface (user cannot tell precomputed-synthetic from live-DB from mock). Density shows n, flagged, rate per 100 (density.tsx:236–241) but **no CI, no lift, no baseline** — so a 13-report site at 100% outranks a 213-report site at 100% purely by n-tiebreak, silently (storage.py:468 sorts `-sif_rate, -n_reports`). For a credibility-first submission the asymmetry is backwards: the surface where sample size varies wildly (341 sites, 271 with n≤5) is the one without caveats.

**F9 — MINOR: dead and unreachable UI affordances.**
`mean_score` is computed server-side (storage.py:452, 464) and typed (types.ts:105) but rendered nowhere. The `by=activity|contractor` facets are implemented end-to-end server-side but expose no switcher. `--chart-1..5` tokens unused. The "Show all locations" button on a fresh load reveals 341 rows where 271 are n≤5 noise — no floor/`min_n` filter client-side (the server /patterns has `min_n=2` default, /density has none).

**F10 — MINOR: silent stale-state window after ingest.**
If the post-ingest `getDensity` re-fetch fails, api.ts:373–375 returns the previous snapshot — the user sees "accepted 500/500" (density.tsx:116) next to a table that didn't change, with no error. Also `window.confirm` (density.tsx:101) is a native dialog that breaks the otherwise-consistent design language, and it guards only the demo button, not the CSV path (a picked file ingests immediately, no preview, one generic error string `ingestFailed`).

## Pain points (HSSE reviewer at an oil & gas major)

1. **"Which site do I inspect?" is unanswerable** — the table they are told to act on is a wall of 100.0 flag rates (F2). A reviewer will assume the tool is broken or the data rigged, and the demo card's admission that the target cell was *planted* makes the whole ranking feel staged if noticed.
2. **"Reviewed by whom?"** — "37 reports reviewed" for numbers nobody reviewed (F1/F8) is the kind of wording a domain expert catches instantly and holds against everything else on the page.
3. **No "since when?"** — no dates anywhere on the analytics surfaces (F3). Leading-indicator practice is trend-based; a ranked snapshot with no time context reads as a snapshot of an unknown period.
4. **Dead ends** — a density row is a terminus: no drill-down to the underlying reports, no link to the triage queue filtered by site, no inspection/CAPA action. The ranking says "inspect next" and offers nothing to inspect *with*.
5. **Movement column = 0 everywhere on first load** (F3/F7) — looks broken before the demo beat ever runs.
6. **Two tab systems in one view** — radix nested Tabs (insights.tsx) plus hand-rolled `role="tab"` buttons (patterns.tsx:44–59): keyboard/screen-reader behavior differs between sibling controls.

## Gaps vs production

- Time series / date filtering (the single biggest analytics gap; data model already has dates).
- Any visualization at all — a decision-grade surface needs at least rate bars with Wilson CI whiskers and a period-over-period trend; nothing exists.
- Statistical honesty floor on density: CI/lift per row, minimum-n display or filter, baseline rate shown next to lift, exposure normalization caveat (report counts measure reporting culture as much as risk).
- Drill-down: density row → filtered report list → review queue. Patterns → "create inspection/CAPA action" (the domain report's missing closure loop).
- Provenance labeling on-surface: live-DB vs precomputed-synthetic vs offline-mock are three different data worlds served through one indistinguishable UI.
- Facet switching (site / activity / contractor) and CSV export of the ranking.
- Dedup/normalization of raw site strings ("workover rig #7" vs "Workover Rig #7" rank separately, verified live).

## Recommendation

- **KEEP** the insights.tsx two-tab nesting — it is the right IA consolidation over the old 3-tab layout (git `716c2c1` → `afe32ad`); 34 LoC, e2e-covered, nothing to split.
- **KEEP** use-flip.ts as-is — correct FLIP, double reduced-motion guard, 36 LoC; suppress it only until the first *live* fetch lands (see FIX below).
- **KEEP** the honest-error ingest path (density.tsx:121–125) and the real-path demo beat (real parse/classify, no scripted numbers) — this is the most credible thing on the surface.
- **MOVE** CSV upload + demo batch out of DensityView into a dedicated ingest surface (own card, or into Triage where data entry already lives) — analytics should not mutate data.
- **REPLACE** mock-first initial states (DENSITY_BEFORE / PATTERNS) in the insights surfaces with an empty/loading state; keep the mock doctrine for the triage feed only. First paint on an analytics screen must not be fabricated numbers.
- **ADD** a date dimension to /density//patterns + a period control in the UI (data already carries `date`) — without it neither surface can support API RP 754-style leading-indicator claims.
- **ADD** one chart: per-row Wilson CI whisker or a rate-vs-n bar in the density table; the `--chart-1..5` tokens (index.css:84–88) already exist for it. SVG primitives, no new chart library, consistent with the no-chart-lib doctrine.
- **ADD** min-n display + baseline rate next to lift, and a provenance chip ("mined from synthetic corpus, 2026-09-08" vs "live DB") on both surfaces.
- **ADD** density row drill-down → reports at that site (link into the triage queue filtered by site); a ranking without a path to action is dead weight.
- **REGENERATE** patterns.json (and the density seed) from non-saturated cells — all-1.0 rates with one distinct lift value make the "Statistical detail" expander self-refuting. At minimum filter saturated cells to a separate "planted demo targets" section.
- **ADD** facet switcher for by=site|activity|contractor (server-complete, one line of UI per facet) and a `min_n` floor on the density table.
- **FIX** stale-refetch silence: surface a visible error when the post-ingest density re-fetch falls back to `prev` (api.ts:373–375).
- **REMOVE** the Movement column from default view (it is all zeros except immediately after the beat) or gate it behind "after a re-rank" state.
- **ADD** e2e coverage for the ingest → re-rank beat; today only tab visibility is tested (dashboard.spec.ts:38–45), so the product's money beat has zero automated verification.