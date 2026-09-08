# E2E Browser Test Report — SIF-Precursor Engine Demo (SIH 26165)

- **Date:** 2026-09-08
- **Stack:** FastAPI @ http://localhost:8177, `MockClassifier` mock-0.1.0, demo-armed (11 seeded reports at start, 17 after the density ingest beat)
- **Browser:** Chromium via Playwright MCP, viewports 1920×1080 and 1366×768
- **Method:** real-browser clicking/reading via accessibility snapshots + screenshots; API cross-checks with `curl`/`python urllib` where the UI had no control for the step
- **Console errors/warnings across the whole session: 0 (zero).** No verbatim errors to report.

## Verdicts by step

| # | Step | Verdict |
|---|------|---------|
| 1 | Feed view loads | **PASS** |
| 2 | Paste-classify (weld/fire-watch report) | **FAIL — no paste box exists in the UI.** API-verified, with one **critical** gate false-positive (see B1) |
| 3 | Near-dup beat (paste same text twice) | **FAIL — no paste UI; also cannot work via API** (`/api/classify` is stateless, see B2) |
| 4 | Gray-state (drill report) | **PASS (API) / untestable in UI** — drill gate grays correctly; gray card rendering verified on seeded gated reports |
| 5 | Codes path ("LOTO not applied", 16 chars) | **PASS (API) / untestable in UI** — not rejected by min_length |
| 6 | Explanation expander | **PASS** — template + cached ollama-reworded paragraph both render |
| 7 | Override (Not-SIF) → Review queue | **PASS** — tab badge +1, row logged, persisted server-side |
| 8 | Density view + ingest/re-rank beat | **PASS** — progress bar, "accepted 6/6", Baghjan EPS #1 ▲3, visible re-sort. One staleness bug (B3) |
| 9 | Patterns view (both kinds) | **PASS** — site×activity and activity×barrier both render 20 rows each with n + 95% CI |
| 10 | Hindi toggle | **PASS (chrome) / PARTIAL** — header, tabs, buttons, footer switch to Devanagari; Patterns view body and band badges stay English (B4) |
| 11 | Console capture + screenshots | **PASS** — 0 console errors/warnings; 12 screenshots saved (list below) |
| 12 | 1366×768 projector fallback | **PASS** — no horizontal overflow, no clipping on the triage card |

## Step details

**1. Feed view** — Queue lists all 11 seeded reports with site, #id·date, and per-row badges (DUP, GATE, band chips). Triage card renders with amber hazard-stripe "▽ LOW REVIEW PRIORITY — Flagged for HSE review" band. **No red SIF card anywhere; no % scores** (score shown as "triage score 0.22", rules as "Rule: Energy Isolation 0.42 (2nd: Confined Space 0.31)"). Rule chips present; evidence span highlighted in the blockquote (`<mark>During</mark>`). Sentinel gate legend (7 gates) renders below. Screenshot 01.

**2. Paste-classify — UI MISSING.** There is no paste/classify input anywhere in the dashboard: no textarea/form/input in `App.tsx`, `views/feed.tsx`, or any component; `classify()` in `dashboard/src/lib/api.ts:269` is exported but **never imported by any component**. Verified behavior via `POST /api/classify` instead (19 ms, well under 2 s):
- score 0.3476; top rules **hot_work 0.806 (1st)**, **line_of_fire 0.375 (2nd)** — expected rules tagged ✓
- evidence span `[51,59] "grinding"` — exact substring of the input ✓
- **BUT the negation gate fires (gray action)**: `"negated high-severity language (cue~anchor within 5 tokens): 'without'~'fire', 'without'~'fell', 'could'~'fire'"` — see B1. Per `feed.tsx` the UI swaps the triage card for a gray-state card whenever a gray gate triggers, so the hero paste would show a **Negation-guard gray card, not the scored triage card the demo script expects**.

**3. Near-dup beat — cannot work.** Second identical paste through `/api/classify` returns the identical prediction with **no near_dup trigger** — the endpoint is stateless and the near-dup index is the training corpus, so nothing remembers the first paste. (The seeded demo of this banner works: report #11 ships with near_dup pre-triggered, cosine 0.990 vs index row 1, and renders the "Matches a training record — memory, not generalization" banner — screenshot 04.)

**4. Gray-state (drill)** — API: drill gate triggers with action `gray` (`"drill badge: mock drill, simulated"`), score 0.2595 — correctly NOT a flagged/red card. Gray-state card rendering itself verified in-browser on seeded gated reports (e.g. #10 "Negation guard" replaces the triage card in the feed — screenshot 05; drill card for #7 visible in the Review tab — screenshot 07).

**5. Codes path** — API: "LOTO not applied" (16 chars) is **not** rejected; `min_length` gate does not trigger (codes path works). Card would render: score 0.2147, span `[0,4] "LOTO"`. Two observations: (a) near_dup fires at **cosine 1.000 with index row 8** — this string is verbatim in the training corpus, so the demo would also show a near-dup banner; (b) top rule is hot_work 0.381 with energy_isolation 2nd at 0.362 — for a LOTO report energy_isolation should clearly lead (mock quirk, demo-visible if judges ask).

**6. Explanation expander** — On report #11 the expander opens with badge "phrased by local LLM · cached" and renders both paragraphs: the ollama-reworded one first, then the template ("Triage score 0.22 — below the review threshold. No IOGP rule crossed its display threshold. Evidence phrases: \"During\". Advisory gates: near_dup (…)"). Screenshot 06.

**7. Override** — Clicked "Not SIF-potential" on #11. Review tab badge increments to "Review 1"; override appears in "Logged overrides → future gold labels" table (#11 · sif_label · LOW → not_sif_potential · hse_reviewer · 8 Sept 2026, 12:37 pm). Server confirms persistence: `/api/review` returns the row and `/api/health` shows `n_overrides: 1`. Screenshot 07.

**8. Density** — Ranked table (Rank/Site/Reports/Flagged/SIF rate/Mean score/Δ rank) renders pre-ingest: #1 Moran GGS-1 … #4 Baghjan EPS. Clicking "Simulate ingest → re-rank" shows the animated hazard-stripe progress bar, then "accepted 6/6" + "Baghjan EPS just climbed to #1."; the table visibly re-sorts with Δ-rank arrows (Baghjan ▲3 → #1 with 8 reports; Moran/GGS-2/Duliajan each ▼1). Server-side persisted (`n_reports: 17`). Screenshots 08–10.

**9. Patterns** — Both tabs render 20 cards each with n (19–47 reports), SIF rate, lift 1.5×, and Wilson 95% CI (e.g. site×activity #1 "derrick/mast climbing × Workover Rig #7", 37 reports, CI [0.91, 1.00]; activity×barrier #1 "gas cutting abandoned flowline × LEL re-test not done after break", 47 reports, CI [0.92, 1.00]). Screenshots 11–12.

**10. Hindi toggle** — "हिं" switches UI chrome to Devanagari: title "SIF-पूर्वसंकेत पहचान इंजन", subtitle "OIL इंडिया · ट्रायाज कंसोल", tabs फ़ीड/घनत्व/पैटर्न/समीक्षा, queue header "रिपोर्ट कतार · 11", expander "यह स्कोर क्यों?", override buttons "SIF-क्षमता की पुष्टि करें / SIF-क्षमता नहीं", footer translated. Screenshot 13. English remains in: Patterns view body (view receives no `lang` prop), band badges ("LOW REVIEW PRIORITY"), report text (expected), gate legend (B4).

**12. 1366×768** — Feed renders two-column without breakage; JS scan found **no horizontal overflow** (`scrollWidth == innerWidth == 1366`, zero elements exceeding viewport) and no clipped text on the triage card. Override buttons fall below the fold (normal scroll, not clipping). Screenshot 14.

## Bugs / findings (report-only, per instructions nothing was fixed)

- **B1 (critical, demo-breaking): negation-gate false positive on the hero paste.** The weld/fire-watch report triggers the negation guard via `'without'~'fire'`, `'without'~'fell'`, `'could'~'fire'`. "Without fire watch" and "Could have been major fire" are mechanism/hazard statements, not outcome negations. In the UI this report would gray-card instead of showing the scored triage card. (`app/gates.py` cue~anchor window is too permissive.)
- **B2 (critical, demo-breaking): paste-classify UI does not exist.** No input in any view; `classify()` in `dashboard/src/lib/api.ts` is dead code. Steps 2–5 of the 90-second script have no UI path. The near-dup re-paste beat additionally cannot work because `/api/classify` is stateless.
- **B3 (minor): stale header count + feed after density ingest.** After "Simulate ingest → re-rank" the header still reads "LIVE · mock-0.1.0 · **11 reports**" and the feed queue still shows 11, while the server holds 17 and the density table shows Baghjan at 8 reports. `App.tsx` fetches health/reports only once at mount; nothing re-fetches after the DensityView ingest.
- **B4 (minor): Hindi toggle coverage gaps.** Patterns view body (descriptions, card content) and the band badges ("LOW/MODERATE/HIGH REVIEW PRIORITY") stay English. Chrome translates fine.
- **B5 (cosmetic): near-dup banner detail wraps awkwardly** — the mono detail "near-dup banner: cosine=0.990 with index row 1 (>= 0.91)" wraps mid-token inside the hazard-stripe banner at 1920×1080 (visible in screenshot 01/04). Readable but scruffy on a projector.
- **B6 (note, not a bug): Review tab heading vs card count.** "Awaiting HSE disposition (4)" counts gated *reports* while 6 gate *cards* render (a report can trigger several gray gates). Consistent internally; may confuse a judge glancing at it.
- **B7 (note): seeded evidence spans are weak in mock mode** — report #11's highlighted evidence is the single word "During", and the "LOW REVIEW PRIORITY" band still carries the sub-line "Flagged for HSE review", which slightly undercuts the "below review threshold" explanation text.

## Console log

Playwright console capture (all levels, `includePreserved`) for the entire session: **Total messages: 0 (Errors: 0, Warnings: 0)** — checked after initial load and again after all 12 steps.

## Screenshots (`runs/run2/day1/e2e/screenshots/`)

| File | Content |
|------|---------|
| `01_feed_view.png` | Feed view, full page, 1920×1080 (step 1) |
| `04_neardup_banner.png` | Triage card #11 with near-dup banner (step 3 UI-equivalent) |
| `05_gray_state_card_feed.png` | Gray-state Sentinel card in feed (report #10, negation guard) (step 4 UI-equivalent) |
| `06_explanation_expander.png` | Explanation expander open, LLM-cached badge (step 6) |
| `07_review_tab_override.png` | Review tab, full page: gated queue + logged override row (step 7) |
| `08_density_pre_rerank.png` | Density table before ingest (step 8) |
| `09_density_ingest_progress.png` | Progress bar + "accepted 6/6" + re-sort (step 8) |
| `10_density_post_rerank.png` | Post-rerank table, Baghjan #1 ▲3 (step 8) |
| `11_patterns_site_activity.png` | Patterns, site×activity (step 9) |
| `12_patterns_activity_barrier.png` | Patterns, activity×barrier (step 9) |
| `13_hindi_toggle.png` | Devanagari chrome (step 10) |
| `14_feed_1366x768.png` | Feed at 1366×768, no overflow (step 12) |

(`02`/`03` intentionally unused — the paste-classify result and paste-driven near-dup screenshots could not be captured because the paste UI does not exist; see B2.)

## Bottom line

The four-tab console, override loop, explanation expander, density re-rank beat, patterns, Hindi chrome, and the 1366×768 fallback are all demo-ready with a clean console. The **90-second script's opening beats (steps 2–5) are blocked by a missing paste-classify UI (B2)**, and even via API the hero weld report is sabotaged by a **negation-gate false positive (B1)**. Fix B1 and either build the paste box or re-choreograph the script to use the ingest path before the demo.

---

## FIXES (2026-09-08, same day — B1/B2/B3 resolved, B4–B7 untouched)

### B1 — negation gate re-scoped to outcomes only (`app/gates.py`)

The gate now anchors **only** on outcome stems (the masking.py frozen stem set,
mirrored, plus `harm`/`hurt`/`casualt`/`damage`) and no longer carries
`_MECHANISM_STEMS` at all — mechanism/barrier words (`fire`, `fell`, `LOTO`,
`fire watch`) can never anchor a negation match. Counterfactual markers
(`could have`, `would have`, `might have`, `narrowly`, `almost`, `nearly`,
`luckily`, `fortunately`) were removed from the cue list and now act as
**suppressors**: a marker within the ±5-token window kills the cue~anchor pair
it scopes. Detail message reworded: `negated outcome language (cue~outcome
within 5 tokens): 'no'~'injury'`.

Verified matrix (unit-level + live API + browser):

| Input | Verdict |
|---|---|
| Hero weld text (`grinding … without fire watch … Could have been a major fire.`) | **scores** (0.38, Hot Work 0.64 top) — no gray |
| `Worker fell 4m. No injury occurred.` | **still grays** — `'no'~'injury'` |
| `LOTO not applied` | scores (codes path; negation silent) |
| `no one was in the area when the pipe fell` | negation silent (absence of exposure; mock score 0.52 lands in the confidence band — orthogonal, intended) |
| `Deepwater … crew could not kill the well` | **still grays** — `'not'~'kill'` (bare `could` is not a suppressor; `could have` is) |
| `No deaths reported — could have been worse.` | suppressed → no gray (near-miss register) |

Suite change: `tests/adversarial_suite.py` did **not** assert the old wrong
behavior (the hero case was never in it), so no expectation needed reversing.
Two regression cases were **added** and one strengthened: #16 hero weld report
(negation silent, zero gray gates, hot_work leads), #17 absence-of-exposure
(negation silent), #13 gained a `not negation.triggered` assertion. Suite is
now **17/17 PASS**; `app/tests/api_smoke.py` PASS (unchanged).

### B2 — paste-classify UI built (Feed view, above the queue)

New `dashboard/src/components/paste-classify.tsx` (textarea + Classify button
+ `Ctrl+Enter` hint, EN/हिं phrasebook strings) wired into
`dashboard/src/views/feed.tsx`. Submit → `POST /api/classify?explain=1&llm=0`
(`classify()` in `api.ts` gained an `explain` option; `llm=0` is a new,
additive query param in `app/routes.py` that pins the deterministic
explanation template — a cold ollama reword on novel text would stall the
card up to 2×8 s on this CPU-clamped box). The result renders through the
**same** card pipeline as the queue (gray swap, near-dup banner, explanation
expander with the bundled template) and is prepended to the queue as an
optimistic **LIVE** row (negative id — never collides with server ids).
Busy state shows a hazard-stripe skeleton card in the result panel. API down
→ gray placeholder card `API unreachable — offline demo mode` + an inline
`offline placeholder, not a score` note in the paste box — verified live by
killing the server mid-session; no crash.

Browser-verified (Chromium via Playwright MCP, 1920×1080 + 1366×768):
hero paste → scored triage card (fix_02), verbatim training-row paste →
near-dup banner `cosine=1.000 with index row osha-2021065076` (fix_03),
negated outcome → Negation-guard gray card (fix_04), `LOTO not applied` →
scored card via codes path (fix_05), API-down → offline note (fix_07).
**Correction to the fix brief:** the MiniLM index is built from
`artifacts/corpus/train_final_v2.jsonl` (70,404 rows per
`corpus_index_meta.json`), **not** `test.jsonl` — the verbatim row used is
`osha-2021065076` from `train_final_v2.jsonl`, which IS in the index.

### B3 — header count + feed queue refresh after density ingest

`App.tsx` now passes `onIngested={refreshLive}` to `DensityView`
(`dashboard/src/views/density.tsx` calls it after a successful live ingest
only). `refreshLive` refetches `getHealth()` + `getReports()`; optimistic
LIVE rows (id < 0) survive the swap. Verified in-browser: header went
**17 → 23 reports** and the feed queue re-fetched (23 server + 4 LIVE rows)
the moment "accepted 6/6" landed (fix_06). (The DB now holds 23 reports —
this verification ran the ingest beat once more; harmless demo data.)

### Regression + hygiene

- `.venv/bin/python tests/adversarial_suite.py` → **17/17 PASS**; `app/tests/api_smoke.py` → **SMOKE PASS** (both spawn their own throwaway-DB server; the demo stack was stopped/restarted around them, DB untouched).
- `cd dashboard && npm run build` → clean (TS + vite).
- Console after all fix verification: **0 errors, 0 warnings** with the API up (the deliberate API-down test logs one browser-level `net::ERR_CONNECTION_REFUSED`, which no JS can suppress — expected, not an app error).
- 1366×768 re-check: no horizontal overflow with the paste box (`scrollWidth == innerWidth == 1366`, fix_08).
- Stack left running on :8177 (`.venv/bin/python -m app.main`, MockClassifier, 23 reports).

New screenshots (`runs/run2/day1/e2e/screenshots/`):

| File | Content |
|------|---------|
| `fix_01_feed_with_paste_box.png` | Feed with the paste box above the queue |
| `fix_02_hero_classify_scored_card.png` | Hero weld paste → scored card, expander open (B1+B2) |
| `fix_03_neardup_banner.png` | Verbatim train row → near-dup banner on scored card |
| `fix_04_negation_gray.png` | `No injury occurred` → Negation-guard gray card |
| `fix_05_loto_codes.png` | `LOTO not applied` → scored card (codes path, step 5) |
| `fix_06_ingest_header_refresh.png` | Post-ingest header 17 → 23 reports (B3) |
| `fix_07_offline_note.png` | API down → offline note + gray placeholder, no crash |
| `fix_08_feed_1366x768.png` | Feed + paste box at 1366×768, no overflow |
