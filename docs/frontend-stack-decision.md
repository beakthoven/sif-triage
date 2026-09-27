# Frontend Stack Decision

**Project:** SIH 2026 · PS 26165 · Oil India Limited
**Date:** 2026-09-25 · **Full evaluation:** `docs/discovery/40-res-frontend-stack.md`

Every library below was evaluated against six criteria: **license**, maintenance/adoption,
bundle impact, accessibility support, offline-vendoring feasibility, and Tailwind-4 +
React-19 compatibility. Compatibility with the offline demo is non-negotiable — the built
`dashboard/dist` is served statically by the same FastAPI process, with no node host at
runtime.

---

## 1. What we are building against

The existing frontend is React 19.2 + TypeScript 7 + Vite 8 + Tailwind 4 + shadcn/ui on Radix,
~1,550 LoC, with **no router, no data-fetching library, no table library, and no chart library**.
Measured today: baseline bundle **323.96 KB raw / 101.96 KB gzip** JS.

Three structural constraints shape every choice below:

1. **This is a dense review instrument, not a marketing site.** Reviewers process hundreds of
   reports per shift. We reward clarity, keyboard efficiency and density; we explicitly penalise
   libraries whose value is decoration.
2. **The product is safety-critical** — every model verdict must render alongside its reasoning.
   Any library whose output cannot be made explainable is disqualified.
3. **Phase 0 found the triage score is not stable under paraphrase** (sd 0.31, verdict flips on
   meaning-preserving rewrites; see `docs/redesign-plan.md` §1 D1). The UI must therefore display
   *verdict stability*, not just a number. This ruled out several animation-first options.

---

## 2. Verdicts on the mandated candidates

### Skiper UI — **REJECT**

Skiper is a genuine shadcn registry (`@skiper-ui`, merged into the trusted-registries list on
2025-09-08) with 100+ components, and it vendors cleanly. It fails on two counts:

- **Licensing.** The free tier requires **attribution**, and Pro components sit behind a paid
  license key validated at install time. That is a custom license with mixed free/paid
  components scattered through one catalogue — unacceptable for a competition submission whose
  provenance will be examined. **No official source repository could be located**; only third-party
  clones exist, so stars, commit recency and issue health are **unverifiable**.
- **Fit.** The catalogue is showcase decoration — animated icons, dynamic-island, theme toggles.
  It ships **zero** table, virtualization, or chart primitives: nothing the queue needs. It would
  also pull a second animation dependency alongside what we already run.

It adds licensing friction and complexity and removes nothing.

### Motion Primitives — **DEFER** (not rejected)

Genuinely good: MIT, 6,377★, last commit 2026-09-16, actively maintained. The peer dependency is
`motion` (renamed Framer Motion), and components vendor offline cleanly.

Two reasons not to adopt now:

- **Zero `prefers-reduced-motion` handling anywhere in the library** — verified by code search,
  0 hits for `useReducedMotion` / `prefers-reduced-motion`. The library can be made compliant with
  a `<MotionConfig reducedMotion="user">` wrapper, but the components do nothing by default. Our
  existing `use-flip.ts` already handles this correctly with a double guard; adopting this would be
  a regression in accessibility hygiene.
- Mostly decorative — exactly what this instrument penalises.

**Deferral trigger:** adopt in a late polish phase, only for 1–3 primitives (notably
`animated-progress` for bulk-ingest), always inside a `reducedMotion="user"` wrapper.

### Astryx (Meta) — **REJECT, as irrelevant**

I read `astryx.atmeta.com/docs/working-with-ai` expecting human-in-the-loop patterns. It documents
an **AI coding-agent documentation system**: a CLI generating `AGENTS.md` / `CLAUDE.md`, an MCP
server, `--dense` token-efficient output, and "no raw divs / no `style={{}}`" rules.

It contains **nothing** about runtime agent-in-the-loop UX — no approval queues, no
model-proposes/human-disposes flows, no confidence-display guidance. For our review-queue problem
it is off-topic; for our build process it is redundant, since this project already carries explicit
agent conventions.

Astryx the design system is Meta's MIT StyleX-based kit at **v0.6.3 (pre-1.0)**. Adopting it would
mean replacing shadcn/Tailwind wholesale for zero data-density value. Declined.

---

## 3. What we are adopting, and why

| Package | Version | License | Size (gzip) | Why |
|---|---|---|---|---|
| `@tanstack/react-table` | ^9.2.4 | MIT | 31.0 KB | The keystone. Fixes three audited defects at once: no risk-ordered sort, no server pagination (only 200 of 5,056 rows reachable), no row selection for bulk review. Headless, so it composes with our existing tokens. |
| `@tanstack/react-virtual` | ^3.14.13 | MIT | 7.6 KB | Renders the tail of the queue that is currently unreachable. |
| `@tanstack/react-query` | ^5.103.2 | MIT | 13.4 KB | Deletes every hand-rolled `useEffect`-fetch-with-cancel-flag path. A thin `queryFn` wrapper preserves the offline-demo doctrine by falling back to `lib/mock.ts`, so the demo still never hard-fails. Rare case where the library removes strictly more complexity than it adds. |
| `recharts` | ^3.10.1 | MIT | 148.0 KB | Chosen on one criterion: `ErrorBar` is verified present in v3 source, so **Wilson confidence-interval whiskers are first-class** rather than hand-rolled. Zero charts exist today; our statistics must be visible, not just computed. Lazy-loaded. `isAnimationActive={false}` by policy. |
| `cmdk` | ^1.1.1 | MIT | 14.6 KB | Radix-based, complete keyboard model. Unstyled substrate for both the palette and keyboard-first review actions (jump-to-row, set-decision). |
| `react-day-picker` | ^10.0.1 | MIT | 18.9 KB | Native range mode for incident-window filters. There is **no** date parameter anywhere in the product today; leading-indicator standards (API RP 754, IOGP 456) are time-series by definition. |
| `react-router` | ^8.4.0 | MIT | 59.0 KB | Adopted for **addressable filter state**, not merely tabs. `HashRouter` was verified in the v8 source tree, so it needs **zero FastAPI changes** and preserves the single-static-dist constraint. A shareable "FSI > 0.8, last 90 days, page 3" URL is a credibility feature for a review instrument. |
| `sonner` | ^2.0.8 | MIT | 9.2 KB | shadcn-blessed toaster with `aria-live` announcements; also the asynchronous bulk-ingest completion surface. |
| `@fontsource/ibm-plex-sans-devanagari` | ^5.3.0 | OFL | *(font)* | Today we ship a prominent EN/हिं toggle with **zero Devanagari coverage** — every Hindi string falls back to an OS substitute. Verified the package exists; the Mono Devanagari does not (E404), so the mono token keeps a fallback stack. |

**Explicitly rejected:** ECharts (359 KB — bundle disqualifier), Chart.js (no first-class error
bars), uPlot (technically excellent and fast, but imperative with no official React wrapper; kept
as the >10k-point escape hatch), visx (error bars would be hand-rolled from primitives — the code
we are deleting), react-aria-components (267 KB, overlaps radix-ui), TanStack Router
(disproportionate loader model for a 3-tab shell), AG Grid (heavy, commercial ceiling), kbar, and a
hand-rolled 30-line hash-sync (0 KB is not free — it is unpaid race-condition maintenance).

---

## 4. Budget

Additions total **~302 KB gzip**, against a measured 101.96 KB baseline — worst case ~400 KB, and
roughly 250–270 KB after tree-shaking and the lazy-loaded chart chunk. RAM impact is minor against
the 5 GB demo budget. This is an accepted, deliberate cost: these libraries **delete** hand-rolled
sort/filter/pagination/fetch/chart code rather than adding surface.

---

## 5. Honest limitations of this decision

- **Not verified:** Skiper UI's official repo/stars (none locatable) and deep Tailwind-4
  compatibility; `@visx` and `react-virtuoso` bundle sizes (Bundlephobia unavailable); post-integration
  tree-shaken sizes — these need a real `vite build` after migration. GitHub star counts for a few
  repos hit API rate limits, so I used verified download counts instead. Recharts' docs page 404'd;
  `ErrorBar` was confirmed via source instead. All download figures are from the API window
  2026-08-23 → 2026-09-21.
- **Accessibility is a work item, not a freebie.** TanStack Table and Virtual are headless, and
  recharts keyboard navigation is weak. `aria-sort`, row focus management and the chart's accessible
  table equivalent must be wired deliberately. The table stays the accessibility front door; charts
  are a visual layer over it.
- `react-day-picker` v10 may need a small adaptation against shadcn's v9-era calendar example.

---

## 6. One-paragraph defence

We kept a bleeding-edge but internally coherent existing core (React 19.2 / TS 7 / Vite 8 /
Tailwind 4 / Radix) and added only headless, MIT-licensed, high-adoption libraries that replace
hand-rolled code we had already written badly — sorting, pagination, fetching, charting — while
rejecting every option whose value was decoration, licensing friction, or a stack migration. Three
candidates specifically named for evaluation were declined with reasons: Skiper UI for a custom
attribution/paywalled license and no verifiable source repository, Astryx as categorically
irrelevant to human-in-the-loop review (and pre-1.0), and Motion Primitives deferred for having no
`prefers-reduced-motion` support. The result is a denser, keyboard-first, explainability-forward
instrument whose data layer can still fall back to fixtures offline.
