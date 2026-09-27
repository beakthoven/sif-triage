# 52 — Visual QA: Decision History, Responsive, Accessibility

Date: 2026-09-25. Live app http://127.0.0.1:8177/ (real stack, 5,056 reports; ollama down as expected).
Method: Chrome DevTools MCP, real rendered screenshots (read into vision), DOM/CSS computed-style sampling, `fetch()` probes from page context. Read-only. All colors below are rendered computed values; contrast ratios computed from canvas-parsed sRGB values with the WCAG 2.x formula (shown per row). Evidence: `artifacts/qa-evidence/a11y-*.png`.

## PART A — Decision History (audit trail for a compliance tool)

Rendered columns at 1440×900 (`a11y-01-decision-history-1440x900.png`): Report | Field | Was | Now | Reviewer | When. Single row: `#5049 · SIF assessment · ~~Low priority~~ → **SIF-potential** · HSE reviewer · 25 Sept 2026, 1:36 pm`.

| Audit requirement | Rendered? | Detail |
|---|---|---|
| WHO decided | Partial | Generic role string "HSE reviewer" (`labeler: hse_reviewer` in NDJSON). No named user, no auth identity. |
| WHEN | Yes | "25 Sept 2026, 1:36 pm" (IST; NDJSON `decided_at: 2026-09-25T08:06:18+00:00` — consistent). |
| BEFORE value | Yes | "Low priority", struck through, muted grey. |
| AFTER value | Yes | "SIF-potential", bold. |
| RATIONALE | **Missing** | No rationale/note column rendered. Server NDJSON has a `rationale` field but its value is `null` — not captured anywhere. |
| Report identity | Weak | Row shows bare `#5049`; no title/snippet — an auditor cannot tell what report this was without cross-referencing IDs. |

1. **Export: NOT reachable from the UI.** `GET /api/review/export` exists server-side (HTTP 200, `application/x-ndjson`, fields: report_id, field, value, old_value, labeler, source=override, rationale=null, decided_at, override_id, supersedes) but no export/download control exists anywhere in the DOM (button inventory: skip-link, EN, हिं, 3 tabs, Classify, 5 filters, 10 queue items, 2 decision buttons, Insights actions only). `/api/review/decisions` is 404.
2. **Correct/undo: does not exist.** No undo/revert/amend/edit control in the Decision History panel or anywhere else in the app. `supersedes: []` suggests the backend anticipates supersession, but the UI cannot trigger it.
3. **Auditor verdict: FAIL.** A reviewer decision's *why* is nowhere (UI or data), the actor is an anonymous role, the row is ID-only, there is no export surface, and no correction path. For "prove what your reviewers decided and why", this screen answers what/when/whence but not who/why, and cannot hand over evidence.

## PART B — Responsive (6 viewports × 3 tabs)

Page-level horizontal scroll: **none anywhere** (`scrollWidth == clientWidth` at all 6 sizes). Failures are inside overflow containers and the tab strip.

| Viewport | Triage | Insights (density table) | Decision History |
|---|---|---|---|
| 1920×1080 | clean | clean | clean |
| 1440×900 | clean | clean | clean |
| 1024×768 | clean, 2-col splits | table fits | table fits |
| 768×1024 | clean | table fits | clean |
| 390×844 | **tab strip clips** | table columns clipped | **tab strip clips; Reviewer+When columns hidden** |
| 360×640 | **tab strip clips** | table columns clipped | **tab strip clips; 5 of 6 columns hidden** |

Specifics (measured):

- **Decision-history tab clipped off-screen at ≤390px.** The main tab strip is an inner scroll container (`group/tabs-list`, overflow-x:auto; scrollW 411 vs clientW 324 at 360px). The "Decision history" tab's right edge renders at x=428–429 vs viewport 360–390 — the audit tab is invisible until swiped, with no fade/arrow affordance. Keyboard focus auto-scrolls it into view; pointer users get nothing.
- **Density table at 390/360:** inside `div.relative.w-full.overflow-x-auto` (scrollW 641 vs 322 at 360). Rendered visible columns: Rank, Site, Reports (header itself truncated to "Report"); Flagged/Flag rate/Movement hidden until horizontal swipe; no visible scrollbar or scroll hint (`a11y-02-insights-360x640.png`, `a11y-02-insights-390x844.png`).
- **Decision History at 360/390:** table scrollW 742 vs 322; "Now" header clipped to "No", values truncated ("SIF-p…"); Reviewer and When — the audit columns — fully off-canvas (`a11y-02-dechist-360x640.png`, `a11y-02-dechist-390x844.png`).
- No content is *destroyed* at small widths — everything survives in swipe containers — but two navigational/audit surfaces are invisible by default and their scrollability is undiscoverable. "Ctrl+Enter to classify" hint is rendered on touch widths where it is meaningless.

## PART C — Accessibility

1. **Skip link: present and correct.** First Tab stop, `href="#main-content"`, renders as a high-contrast dark pill top-left on focus (`a11y-03-focus-01-skiplink.png`).
2. **Tab order (inventory of 27 stops, DOM order):** skip link → EN → हिं → tablist → (arrow keys move tabs) → tabpanel → textarea → search → 5 filter pills → 10 queue items → Technical-detail summary → Confirm SIF-potential → Not SIF-potential → disclosures. Logical, no keyboard traps, disabled Classify correctly skipped, every control reachable. Tabs use Radix roving-tabindex (arrow keys inside tablist) — operable, though Tab does not land on the tab buttons themselves.
3. **Focus indicators — two invisible stops (WCAG 2.4.7):**
   - `role=tablist` container: computed `outline: none 3px rgb(91,100,112)` → **no ring when focused**.
   - `role=tabpanel`: classes include `outline-none`; computed `outline: none` → **page scrolls to the panel and nothing visibly marks it** (`a11y-03-focus-03-tab-triage.png`).
   - Visible stops: skip link (styled pill), EN/हिं (rounded ring), textarea (darkened border), queue items (default `auto` ring), Confirm/Not-SIF buttons (clear double ring, `a11y-03-focus-08-confirm-sif.png`).
   - **"Needs decision" dark pill: no discernible ring** while focused (`a11y-03-focus-06-pill.png`). Default ring color rgb(91,100,112) on pill bg rgb(32,34,38) ≈ **2.84:1** — below the 3:1 non-text minimum (vs cream bg rgb(245,244,240) it is ≈5.14:1, fine on light elements). The app leans on the browser's dark-slate default ring, which dies on dark components.
4. **Dark mode: NOT implemented.** With `prefers-color-scheme: dark` emulated on all three tabs, body stays rgb(245,244,240), no `.dark` class on `<html>`, no in-app theme toggle. Renders identically light everywhere (`a11y-04-darkmode-triage.png`, `-insights-locations.png`, `-dechist.png`). Not "broken" — absent.
5. **Reduced motion: correctly suppressed.** Stylesheets contain 2 `prefers-reduced-motion` blocks: global `*, ::before, ::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }` and `.shimmer { animation: none }`. (Verified via stylesheet inspection + `matchMedia`; the DevTools MCP cannot toggle the media query at runtime.)
6. **Contrast survey (rendered colors, canvas-parsed, WCAG formula):**

| Element | Fg (effective) | Bg (effective) | Ratio | AA 4.5:1 |
|---|---|---|---|---|
| Muted grey text rgb(91,100,112) — header meta, hints, queue subtitles, Review chips, DH cells, footer | 91,100,112 | 240–253 light greys | 5.17–5.89 | pass |
| Manual-review chip rgb(100,116,139) 13.5px | 100,116,139 | 253,253,251 | 4.67 | pass (thin margin) |
| "Short note" oklab @0.8 → rgb(77,78,81) | 77,78,81 | 253,253,251 | 8.17 | pass |
| **Inactive sub-tab "Recurring patterns" oklab @0.6 → rgb(121,122,125)** | 121,122,125 | 240,238,232 | **3.70** | **FAIL** |

Single contrast failure: inactive sub-tabs (and by extension inactive main tabs use the same `text-muted-foreground/60` pattern) at 15.75px normal weight need 4.5:1; they render 3.7:1.

## Screenshot index (artifacts/qa-evidence/)

- `a11y-01-decision-history-1440x900.png` — Decision History tab, light, 1440
- `a11y-02-triage-{1920x1080,1440x900,1024x768,768x1024,390x844,360x640}.png`
- `a11y-02-insights-{1920x1080,1440x900,1024x768,768x1024,390x844,360x640}.png`
- `a11y-02-dechist-{1920x1080,1024x768,768x1024,390x844,360x640}.png` (1440 version is a11y-01)
- `a11y-03-focus-01-skiplink … 08-confirm-sif.png` — focus walk stops
- `a11y-04-darkmode-triage.png`, `a11y-04-darkmode-insights-locations.png`, `a11y-04-darkmode-dechist.png` — dark emulation, all still light
