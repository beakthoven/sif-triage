# 40 — Frontend stack resource evaluation (Phase 0/1)

Role: Phase 0/1 resource-evaluation agent (read-only). Date: 2026-09-25.
Output: this file only. No repo code was changed.

## Method and sources

All numbers below were fetched live this session, not recalled:

- **npm downloads API** (`api.npmjs.org/downloads/point/last-month/...`): window returned by the API = 2026-08-23 → 2026-09-21. All download counts cited as "dl/mo" refer to that window.
- **npm registry** (`registry.npmjs.org/<pkg>/latest` + full doc `time.modified`): exact latest versions, licenses, peer-deps, last-publish dates.
- **Bundlephobia API** (`bundlephobia.com/api/size?package=...`): minified + gzip sizes of the *full published package*, pre-tree-shaking. In-app tree-shaken sizes are unmeasured unless stated.
- **GitHub REST/MCP**: stars, licenses, last-push/last-commit dates. GitHub REST was IP-rate-limited mid-session; missing stars were not invented — download counts are used instead.
- **Direct page fetches**: skiper-ui.com, skiper-ui.com/r/skiper4.json (raw registry payload via curl), github.com/ibelick/motion-primitives, motion-primitives.com/docs/installation, astryx.atmeta.com/docs/working-with-ai, astryx.atmeta.com/docs.
- **GitHub code search**: `useReducedMotion` and `prefers-reduced-motion` in ibelick/motion-primitives (0 hits each); `ErrorBar` in recharts/recharts (58 hits, `src/cartesian/ErrorBar.tsx` present on main); `bands` in leeoniya/uPlot (24 hits, `src/paths/utils.js` + `demos/high-low-bands`); `HashRouter` in remix-run/react-router (20 hits, present in v8 source).

## Evaluation matrix

| Candidate | License | Last activity | Adoption signal | Bundle (gzip, full pkg) | A11y | TW4 + React 19 | Verdict |
|---|---|---|---|---|---|---|---|
| Skiper UI | Custom: free **with attribution**; Pro components paid (license key) | Repo: **not locatable** — only third-party clones; site actively updated | Trusted shadcn registry (merged 2025-09-08, shadcn-ui/ui#8170); no npm pkg | Vendored per-component; pulls `framer-motion` | Unverified (component code has no a11y affordances visible in sample) | Sample code TW-safe; unverified in depth | **REJECT** |
| Motion Primitives | MIT | Last commit 2026-09-16; 6,377★ | 6,377★, 263 forks; README says "beta" | `motion` v13.4.3 = 46.6 KB gzip (13.4 peer) + vendored code | **No prefers-reduced-motion handling in any component** (code search: 0 hits) | Yes (motion peer `^18\|\|^19`; TW utilities standard) | **DEFER** |
| Astryx (Meta) | MIT (npm + LICENSE file) | Monorepo active; @astryxdesign/core v0.6.3 | © Meta Platforms; pre-1.0 | Its own StyleX-based system | Claims AA via own primitives — unverified | React 19+ **only** (would fit), StyleX not Tailwind | **REJECT** |
| @tanstack/react-table ^9.2.4 | MIT | Publish 2026-08-28 | 69.3M dl/mo; 28,453★ | 31.0 KB | Headless — a11y is ours (aria-sort, row focus) | Peer `>=18`; headless, no CSS | **ADOPT** |
| @tanstack/react-virtual ^3.14.13 | MIT | Publish 2026-09-14 | 84.5M dl/mo | 7.6 KB | Headless | Peer `^16.8\|\|^19` | **ADOPT** |
| @tanstack/react-query ^5.103.2 | MIT | Publish 2026-09-21 | 233.0M dl/mo | 13.4 KB | n/a (data layer) | Peer `^18\|\|^19` | **ADOPT** |
| recharts ^3.10.1 | MIT | Publish 2026-09-21 | 205.1M dl/mo | 148.0 KB | SVG, aria-label/role props; keyboard nav weak | Peer `^16.8…^19` | **ADOPT** |
| chart.js 4.5.1 | MIT | Publish 2025-10-13 | 45.5M dl/mo | 66.8 KB | Canvas — needs extra work for a11y | Framework-agnostic | reject |
| uPlot 1.6.32 | MIT | Publish 2025-03-14 (stable/mature) | 2.0M dl/mo | 21.3 KB | Canvas — weakest a11y story | Framework-agnostic; no official React wrapper | reject as primary; escape hatch |
| echarts 6.1.0 | Apache-2.0 | Publish 2026-05-19 | 18.5M dl/mo | **359.3 KB** | Good, but heavy | Framework-agnostic | reject |
| @visx/visx 4.0.0 | MIT | Modular, active | 0.3M dl/mo (meta pkg) | Bundlephobia unavailable → **unverified**; error bars hand-rolled via @visx/shape | Headless SVG (our job) | Peer `^18\|\|^19` | reject |
| cmdk 1.1.1 | MIT | npm 2025-08-27; repo dip/cmdk updated 2026-09-25, 12,987★ | 156.1M dl/mo | 14.6 KB | Radix-based, full keyboard + roving focus | Peer `^18\|\|^19` | **ADOPT** |
| kbar 1.0.0 | MIT | Publish 2026-08-10 | 1.1M dl/mo | 26.9 KB | Decent, opinionated UI | Peer `^17…^19` | reject |
| react-day-picker 10.0.1 | MIT | Publish 2026-08-31 | 150.1M dl/mo | 18.9 KB | Strong keyboard/SR support (v9+ rewrite) | Peer `>=16.8` | **ADOPT** |
| react-router 8.4.0 | MIT | Publish 2026-09-15; 56,586★ | 192.2M dl/mo | 59.0 KB (tree-shaken: unmeasured) | Link/navFocus handling built-in | Peer `>=19.2.7` (we run 19.2.8 ✓) | **ADOPT** |
| @tanstack/react-router | MIT | Publish 2026-09-23 | 78.3M dl/mo | 30.2 KB | Type-safe search params | Peer react 19 ✓ | reject (this app) |
| sonner 2.0.8 | MIT | Publish 2026-08-09 | 179.9M dl/mo | 9.2 KB | aria-live announcements | Peer `^18\|\|^19` | **ADOPT** |
| react-aria-components 1.21.1 | Apache-2.0 | Publish 2026-09-25 | 14.8M dl/mo | 267.7 KB (subpath imports smaller, unmeasured) | Best-in-class | Peer `^18\|\|^19` | reject for now |
| TanStack Virtual alt: react-virtuoso / react-window | MIT | react-virtuoso bundle **unverified** (Bundlephobia down) | — | unverified | — | — | reject (not evaluated numerically) |
| 30-line hash-sync (in-house) | n/a | n/a | n/a | 0 KB | None — hand-rolled | — | reject |

## Mandatory targets — detailed verdicts

### 1. Skiper UI (skiper-ui.com) — **REJECT**

Verified: 106+ components, distributed as a trusted shadcn registry (`@skiper-ui`, merged into shadcn-ui/ui trusted-registries list on 2025-09-08, PR #8170). The raw registry payload (`/r/skiper4.json`, fetched) shows single-file components (`registry:ui`) importing `motion` from **`framer-motion`** and `lucide-react`, styled with standard Tailwind utilities — so vendoring works, and the sampled code is Tailwind-4-safe (no Tailwind-3-only syntax in the sample; deeper compat unverified). License is the decisive failure: per the site's own docs, the free tier is "free to use and modify in personal and commercial projects, **attribution to Skiper UI is required**" and Pro components are gated behind a paid license key validated on every install — a custom license, not MIT, with mixed free/paid components scattered across the catalog. No official GitHub repository could be located (repo search returns only third-party clones such as nischayhq/skiper-ui at 15★ and explicit "clone of skiper/ui" forks), so stars, commit recency, and issue health are **unverifiable**. Fit: the catalog is decorative showcase UI (dynamic island, theme-toggle animations, token-swap mockups, animated icons) — exactly the class of flash this credibility-first instrument must penalize. It ships zero table, virtualization, chart, or data-density primitives, and would import a second animation dependency alongside our existing stack. It adds complexity and licensing friction; it removes nothing.

### 2. Motion Primitives (github.com/ibelick/motion-primitives) — **DEFER**

Verified: MIT; 6,377★; 263 forks; last commit 2026-09-16 (repo touched 2026-09-25 — actively maintained); README explicitly says "beta". Peer dependency is **`motion`** (the renamed Framer Motion), not `framer-motion` — docs/installation says `npm install motion`; `motion` v13.4.3: MIT, peer `^18||^19`, 74.7M dl/mo, 46.6 KB gzip. Components are copy-paste/vendored via `npx motion-primitives@latest add <name>` (works offline once copied; install needs network). Tailwind compatibility: components use plain utilities and the standard `cn(twMerge+clsx)` helper — compatible with our Tailwind 4 `@theme` setup, though it assumes a `lib/utils.ts` `cn` (we have one). Bundle: vendored component code is small, but each animated component pulls `motion` (46.6 KB gzip shared). Accessibility — the audit finding: GitHub code search for `useReducedMotion` and `prefers-reduced-motion` in the repo returned **0 hits**; none of the components respect `prefers-reduced-motion` out of the box. Motion the library supports an opt-in `<MotionConfig reducedMotion="user">`, so compliance is one wrapper away, but the kit itself does nothing. Fit for this app: mostly decoration (text effects, hover buttons, animated showcases) — penalized. The few genuinely useful pieces are `animated-progress` (bulk-ingest progress) and a number ticker for KPI counters. Deferral trigger: adopt only during a late polish phase, only for 1–3 utility primitives, and only inside a `MotionConfig reducedMotion="user"` wrapper. Until then it is weight with no triage value.

### 3. Astryx (astryx.atmeta.com/docs/working-with-ai) — **REJECT**

Being skeptical as instructed: the page fetched is real and substantive — it documents an **AI-agent docs system** (CLI generates AGENTS.md/CLAUDE.md/cursorrules, an MCP server, `--dense` token-efficient output, "no raw divs / no style={{}}" rules). Astryx itself is **Meta Platforms'** design system (github.com/facebook/astryx, © 2026 Meta Platforms, Inc.), MIT-licensed, React-19-only (`react >= 19` peer), built on StyleX (`@stylexjs/stylex` peer) with CSS-first tokens and a `@astryxdesign/cli`. But the "working with AI" doc is about AI *coding agents authoring UI code correctly* — it contains nothing about runtime human-in-the-loop / agent-in-the-loop interface patterns: no approval queues, no model-proposes/human-disposes flows, no confidence-display guidance. For our review-queue UX problem it is irrelevant; for our build process it is redundant (we already have agent conventions). Adopting the design system itself would mean replacing shadcn/Tailwind with a StyleX-based stack at **v0.6.3 (pre-1.0)** — a large migration that buys zero data-table/virtualization/chart value. Honest note: the MCP server at `https://astryx.atmeta.com/mcp` was not queried (dev-time internet would be required; we don't need it).

## Discovery slots — detailed verdicts

### (a) Data table + virtualization — **ADOPT @tanstack/react-table ^9.2.4 + @tanstack/react-virtual ^3.14.13**

This is the keystone. TanStack Table: MIT, 69.3M dl/mo, 28,453★, publish 2026-08-28, peer `react >= 18` (React 19 ✓), Bundlephobia full package 31.0 KB gzip. Headless: zero CSS/DOM opinions, so it composes with our existing shadcn `table.tsx` and Tailwind 4 tokens — we keep our visuals and delete hand-rolled sort/filter/pagination logic. It directly closes the three audited gaps: risk-ordered sortable columns (`getSortedRowModel`), server/paged filtering over 5,056+ rows (`getFilteredRowModel`/`getPaginationRowModel`), and row selection for bulk review. TanStack Virtual: MIT, 84.5M dl/mo, 7.6 KB gzip, publish 2026-09-14 — renders the reachable-nowhere tail of the queue. A11y is our job (headless): `aria-sort`, focus rings, and keyboard row navigation must be wired deliberately — this is the one adopted lib where accessibility is an explicit work item, not inherited. Rejected alternatives: AG Grid (community MIT but heavy, theming outside Tailwind, enterprise features behind commercial license); react-data-table-component (much smaller community, styling-first, stale relative to v9-era headless standard); hand-rolled table (that is the code being deleted). React-window/react-virtuoso are fine but don't integrate with Table's row model — one ecosystem, two packages, wins.

### (b) Charting — **ADOPT recharts ^3.10.1**

Decision driver: **Wilson confidence-interval whiskers must be first-class, not hand-rolled.** Recharts ships `ErrorBar` (`src/cartesian/ErrorBar.tsx` verified on current main; Storybook + docs examples present): pass computed Wilson lower/upper arrays via `dataKey` on Bar/Scatter/Line. Time series, tooltips, and responsive containers are declarative React — minimal custom code. MIT, 205.1M dl/mo, publish 2026-09-21, peer `^16.8…^19` (React 19 ✓), 148.0 KB gzip — the heaviest adopted dependency, accepted deliberately because it deletes the most custom code; set `isAnimationActive={false}` for the dense-data credibility mandate (animations are marketing-site behavior). Accessibility: SVG with `role`/`aria-label` support, but keyboard chart navigation is weak — the (a) table remains the accessibility front door; charts are the visual layer over it. Rejected: **uPlot** (21.3 KB, MIT, built-in high/low *bands* — verified in `src/paths/utils.js` — perfect fit technically and the designated escape hatch if series counts exceed ~10k points or render perf suffers; rejected as primary because it is imperative, has no official React wrapper (third-party wrappers unverified), and would re-add drawing code); **Chart.js** (66.8 KB, no first-class error bars — custom plugin needed; canvas a11y weak); **ECharts** (359.3 KB gzip — bundle disqualifier); **visx** (excellent library, wrong cost model: error bars/annotations are hand-rolled from `@visx/shape` primitives, i.e. the custom code we're deleting; meta-package size unverified).

### (c) Command palette — **ADOPT cmdk ^1.1.1**

MIT, 156.1M dl/mo, repo `dip/cmdk` 12,987★ (updated 2026-09-25), 14.6 KB gzip, peer `^18||^19` ✓, built on Radix primitives with complete keyboard model (arrow/j/k navigation, roving focus, typeahead) — matches our existing radix-ui dependency style and slots directly into our Dialog primitive as the shadcn `command` pattern. It is the unstyled substrate for the command palette AND can back keyboard-first review actions (jump-to-row, set-decision, switch-tab). One honest caveat: npm last publish 2025-08-27 (~13 months) — the repo is actively maintained (moved to `dip` org, updated today) and the API has been stable at 1.x since 2025; treat staleness as maturity here, and the risk is low. Rejected: **kbar** (MIT, 1.1M dl/mo, 26.9 KB — heavier, opinionated default UI, community 150× smaller for no functional gain).

### (d) Date-range filtering — **ADOPT react-day-picker ^10.0.1**

MIT, 150.1M dl/mo, publish 2026-08-31, 18.9 KB gzip, peer `react >= 16.8` ✓, native range mode (`mode: "range"`) for incident-window filters, strong keyboard/screen-reader support since the v9 rewrite. It is what shadcn's `calendar` wraps, so it stays inside the shadcn idiom. Risk (small): shadcn's calendar example may target the v9 API; expect a small adaptation when integrating on v10.

### (e) Router — **ADOPT react-router ^8.4.0 (declarative mode, HashRouter)**

Justified — but not "just for tabs." Three tabs alone would not justify a dependency; **filter/search/row state in the URL** does: an HSSE officer sharing a link to "open FSI > 0.8, last 90 days, page 3" is a credibility feature for a review instrument. Verified: MIT, 192.2M dl/mo, 56,586★, publish 2026-09-15, v8.0.0 released 2026-06-17; peer `react >= 19.2.7` (we run 19.2.8 ✓); `HashRouter` confirmed present in the v8 source tree (`packages/react-router/lib/dom/lib.tsx`) — hash routing requires **zero FastAPI changes**, preserving the single-static-dist constraint. `useSearchParams` gives URL-addressable filter state per tab. Rejected: **TanStack Router** (MIT, 78.3M dl/mo, 30.2 KB gzip, publish 2026-09-23 — genuinely better typed search-param validation, but its setup/loader model is a disproportionate cost for a 3-tab shell; if filter complexity explodes later, it is the upgrade path); **30-line hash-sync** (rejected because hand-rolled URL↔state sync — including back/forward, base64-encoded filter objects, and race handling — is precisely the class of fragile custom code this redesign exists to delete; 0 KB is not free, it is unpaid maintenance).

### (f) Toasts + optimistic updates — **ADOPT sonner ^2.0.8 + @tanstack/react-query ^5.103.2**

sonner: MIT, 179.9M dl/mo, publish 2026-08-09, 9.2 KB gzip, peer `^18||^19` ✓, the shadcn-blessed toaster with aria-live announcements — replaces any ad-hoc toast glue for review-submission feedback. TanStack Query: MIT, 233.0M dl/mo, publish 2026-09-21, 13.4 KB gzip, peer `^18||^19` ✓. It is adopted specifically to delete the current `useEffect`-fetch boilerplate with cancel-flag race guards (the mock-first boot pattern in `App.tsx`) while **preserving the offline-demo doctrine**: a thin `queryFn` wrapper tries the live fetch and falls back to `lib/mock.ts` fixtures, so the demo never hard-fails and every getter gets caching, dedup, and loading states for free. Review actions become `useMutation` with `onMutate` optimistic updates + rollback — the standard, battle-tested ergonomics for "human disposes" actions. This is the rare case where the library removes strictly more complexity than it adds: ~13 KB buys the removal of every hand-rolled fetch/cancel/dedup path.

## Recommended final stack (exact)

Add to `dashboard/package.json` dependencies:

| Package | Version | License | Purpose |
|---|---|---|---|
| `@tanstack/react-table` | `^9.2.4` | MIT | risk-ordered sortable queue, filtering, pagination (5,056+ rows) |
| `@tanstack/react-virtual` | `^3.14.13` | MIT | virtualized list over the queue |
| `@tanstack/react-query` | `^5.103.2` | MIT | fetch/caching/optimistic mutations; mock-fallback preserved in `queryFn` |
| `recharts` | `^3.10.1` | MIT | time-series trends + Wilson CI whiskers via `ErrorBar` |
| `cmdk` | `^1.1.1` | MIT | command palette (⌘K) + keyboard-first navigation |
| `react-day-picker` | `^10.0.1` | MIT | incident date-range filter |
| `react-router` | `^8.4.0` | MIT | declarative `HashRouter` + `useSearchParams`; deep-linkable tabs/filters |
| `sonner` | `^2.0.8` | MIT | toasts/notification ergonomics |

Unchanged (already correct): react/react-dom 19.2.8, radix-ui 1.6.7, lucide-react, `cn` 0.2.6, class-variance-authority, @fontsource IBM Plex Sans/Mono, tw-animate-css, tailwindcss 4.3.3 (`@theme` CSS-first), vite 8.2.2, typescript 7.0.2. All eight additions are MIT, bundled by Vite into `dashboard/dist` → zero runtime network calls, fully offline, single FastAPI-served dist unchanged.

## Rejected list

| Rejected | Reason |
|---|---|
| **skiper-ui** | Custom attribution-required license + paid Pro gating; no verifiable official repo (stars/recency unverifiable); decorative showcase components; zero data-density primitives; adds a second animation dep (`framer-motion`) |
| **astryx / @astryxdesign/*** | Meta design system at v0.6.3 pre-1.0; would replace shadcn/Tailwind with StyleX stack; "working-with-AI" doc is about agents authoring code, not HITL review-queue patterns — irrelevant to this project |
| **motion-primitives** (deferred, not adopted now) | No prefers-reduced-motion handling in any component (verified); value is decoration; revisit with `MotionConfig reducedMotion="user"` for ≤3 utility primitives |
| **echarts** | 359.3 KB gzip for features we don't need |
| **chart.js** | No first-class error bars; non-React API adds wrapper layer |
| **uPlot** | No official React wrapper; imperative redraw code; keep as escape hatch >10k-point series |
| **visx** | Error bars/annotations hand-rolled from shape primitives = new custom code; meta-bundle unverified |
| **kbar** | 26.9 KB vs cmdk's 14.6 KB, opinionated UI, 100× smaller community |
| **@tanstack/react-router** | Better typed search params, but disproportionate setup cost for 3 tabs |
| **30-line hash-sync** | Hand-rolled URL↔state sync is the fragile custom code being deleted |
| **react-aria-components** | Best-in-class a11y but 267.7 KB full-package gzip and overlaps radix-ui 1.6.7 we already run; adopting two primitive systems adds complexity. Named upgrade path if Radix a11y gaps bite |
| **AG Grid** | Heavy, off-Tailwind theming, enterprise feature licensing walls |
| **react-hot-toast** | Sonner is the shadcn-native standard; not separately benchmarked (its numbers unverified) |

## Bundle-size budget estimate

Baseline measured in audit 10 (`docs/discovery/10-fe-shell.md`): main JS **316 KB raw / 101 KB gzip**, CSS 61 KB, dist total 1.7 MB (39 woff2 fonts bundled).

Additions, Bundlephobia full-package gzip, pre-tree-shaking (worst case):

| Package | gzip |
|---|---|
| @tanstack/react-table 9.2.4 | 31.0 KB |
| @tanstack/react-virtual 3.14.13 | 7.6 KB |
| @tanstack/react-query 5.103.2 | 13.4 KB |
| recharts 3.10.1 | 148.0 KB |
| cmdk 1.1.1 | 14.6 KB |
| react-day-picker 10.0.1 | 18.9 KB |
| react-router 8.4.0 | 59.0 KB |
| sonner 2.0.8 | 9.2 KB |
| **Total additions** | **~301.7 KB** |

Projected main JS ≈ **~400 KB gzip** worst case (real total will be lower: router and recharts tree-shake, and recharts should be a lazy-loaded chunk off the initial route — projected initial ≈ 250–270 KB gzip). Runtime RAM impact is modest relative to the ~5 GB budget shared with the ONNX model; bundle weight here is load-time, not memory, and the demo serves locally. If the budget is later breached, dropping recharts for uPlot saves ~127 KB gzip at the cost of hand-rolled rendering.

## Three biggest risks

1. **Recharts weight + default animations.** 148 KB gzip and animation-on-by-default are both credibility hazards for a dense instrument. Mitigation: lazy-load the chart route, set `isAnimationActive={false}` everywhere, and treat the Wilson `ErrorBar` wiring as an acceptance test in the e2e suite.
2. **react-router v8 is a fresh major (2026-06).** `HashRouter` and declarative mode verified present in source, and the peer floor (`react >= 19.2.7`) is satisfied, but most examples and LLM training data skew to v6/v7 — expect small API drift during integration. Mitigation: pin exact `8.4.0` initially; validate `useSearchParams` + `HashRouter` behavior in the Playwright suite before building features on it.
3. **Ecosystem examples lag our majors.** shadcn's data-table/command/calendar recipes assume TanStack Table v8 and react-day-picker v9, and copy-paste registries (Skiper-style) assume internet at install time. We are on Table v9 and day-picker v10, and the machine is offline-first. Mitigation: treat shadcn recipes as reference, not paste targets; vendor all registry artifacts into `src/` at build time; keep the mock-fallback doctrine inside the TanStack Query layer so the demo still never hard-fails.

## Could not verify (recorded verbatim, not invented)

- Skiper UI: official GitHub repository, GitHub stars, commit recency, component-level accessibility, and deep Tailwind-4 compatibility — **not verifiable** (no canonical repo found; only third-party clones). License text taken from skiper-ui.com docs/quick-start as captured.
- @visx/visx and react-virtuoso bundle sizes — Bundlephobia API returned no data (**unverified**).
- In-app tree-shaken bundle sizes of every adopted package — unmeasured until a `vite build` after integration (Bundlephobia reports full packages).
- GitHub stars for recharts, sonner, react-day-picker, TanStack/virtual/query/router, echarts, uPlot repos — GitHub API rate-limited mid-session; download counts (verified) used instead.
- motion-primitives in-app bundle impact — vendored code per component; only the shared `motion` peer (46.6 KB gzip) is measured.
- `https://recharts.org/en-US/api/ErrorBar` returned HTTP 404; ErrorBar verified instead via GitHub source search (`src/cartesian/ErrorBar.tsx`, storybook, docs examples).
- First attempt to fetch `https://api.github.com/repos/ibelick/motion-primitives` returned HTTP 403 (rate limit); data obtained via authenticated GitHub search + commit listing afterward.