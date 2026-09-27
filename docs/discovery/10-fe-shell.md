# 10 — Frontend shell, build tooling, dependency truth, i18n

Role: Phase 0 discovery agent (read-only) for dashboard shell, build tooling, dependency audit, i18n.
Date: 2026-09-25. Nothing outside `docs/discovery/10-fe-shell.md` was written.

## Files actually read (line counts)

| File | Lines | Note |
|---|---|---|
| dashboard/index.html | 16 | full |
| dashboard/src/main.tsx | 17 | full |
| dashboard/src/App.tsx | 213 | full |
| dashboard/src/lib/utils.ts | 1 | full |
| dashboard/src/lib/use-flip.ts | 36 | full |
| dashboard/src/lib/report-display.ts | 57 | full |
| dashboard/src/lib/phrasebook.ts | 166 | full |
| dashboard/src/components/lang-toggle.tsx | 34 | full |
| dashboard/src/components/paste-classify.tsx | 70 | full |
| dashboard/src/components/gray-state-card.tsx | 215 | lines 1–88 in full (gate-copy block) + regex census of remainder |
| dashboard/src/components/ui/{badge,button,card,separator,table,tabs}.tsx | 48/66/102/25/115/87 | full (all six) |
| dashboard/src/index.css | 150 | full |
| dashboard/vite.config.ts | 29 | full |
| dashboard/tsconfig.json / tsconfig.app.json / tsconfig.node.json | 7/30/24 | full |
| dashboard/components.json | 25 | full |
| dashboard/package.json | 35 | full |
| dashboard/playwright.config.ts | 18 | full |
| dashboard/e2e/dashboard.spec.ts | 101 | full |
| dashboard/package-lock.json | — | parsed programmatically (versions, sync check) |
| dashboard/.env.production | — | **READ FAILED**: tool refuses `.env*` as a sensitive-file pattern. Only stat obtained: 286 bytes, mtime 2026-09-08. Content claims below are inferences from build outputs, marked as such. |

Tools used: Read/Grep/Glob tools, `find`, `wc`, `npx playwright test --list` (read-only listing), `npx tsc -p tsconfig.app.json --noEmit --incremental false` (writes nothing; exit 0), `node` scripts (lockfile parse, phrasebook census, import census, bundle size), `npm view` (registry metadata only), `grep` on dist assets, `stat`. No builds, no installs, no writes to the live app on 8177.

## What exists today

### Shell
- `index.html:1-16`: static `lang="en"`, inline SVG favicon (offline-safe), EN-only `<title>`, no CSP meta tag, single `#root` mount.
- `main.tsx:1-17`: StrictMode; imports IBM Plex Sans 400/500/600/700 + Mono 400/500/600 via `@fontsource/*` CSS (bundled woff2 → fully offline); mounts `App`.
- `App.tsx:14-213`: single component owning ALL state (`lang`, `workspace`, `reports`, `overrides`, `health`, `sessionOverrides`). Three tabs (triage/insights/decisions) via Radix Tabs with `forceMount` + `data-[state=inactive]:hidden` (App.tsx:182-196) so in-progress paste text and queue survive tab switches. Mock-first boot: `reports`/`overrides` initialize from `lib/mock.ts` (App.tsx:19-20), then a `Promise.all([getHealth, getReports, getOverrides])` swaps in live data with a cancel-flag race guard (App.tsx:24-40). Header health dot + `n_reports.toLocaleString("en-IN")` (App.tsx:136). `document.documentElement.lang` synced to the toggle (App.tsx:42-44). Offline override fallback records negative-id local rows (App.tsx:64-77). Skip-link (App.tsx:110-115), tab badges for pending decisions and override count.
- No router anywhere (no router dep, no URL state, no history integration). Insights nests two more Radix tab groups (locations/patterns; site-activity/activity-barrier) — 5 logical surfaces, 0 deep-linkable URLs.

### Libraries & config
- `vite.config.ts:12-28`: `@vitejs/plugin-react` + `@tailwindcss/vite`, `@`→`src` alias, dev AND preview proxies `/api` → `http://localhost:8177` (env-overridable). Header comment (lines 6-9) says the API has no CORS middleware — **verified true** (`grep CORSMiddleware app/main.py` → no match), so same-origin serving via FastAPI StaticFiles is load-bearing, and dev mode only works through this proxy.
- `tsconfig.app.json:18-23`: `strict`, `noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly`, `noFallthroughCasesInSwitch`, `noUncheckedSideEffectImports`, `verbatimModuleSyntax`, `moduleResolution: bundler`, `noEmit`. Near-maximum strictness. `tsconfig.json` is a project-references shell over app+node configs.
- `components.json`: shadcn CLI config, style "radix-vega", icon library lucide, aliases `@/components`, `@/lib`.
- `src/lib/utils.ts` is one line: `export { cn } from "cn"`. The `cn@0.2.6` package (node_modules/cn/package.json) is the shadcn-ui org's compiled class-merge engine — a drop-in replacement for clsx+tailwind-merge with conflict resolution, zero deps. This is a legitimate choice, not a homegrown stub.
- `index.css:1-3` imports `tailwindcss`, `tw-animate-css`, and **`shadcn/tailwind.css`** — resolves to `node_modules/shadcn/dist/tailwind.css` (verified with `require.resolve`). So `shadcn@4.21.0` is a genuine runtime (CSS) dependency, not a phantom.
- Font stacks (index.css:8-9): `"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` and Plex Mono equivalents. **No Devanagari entry anywhere.** Base font-size 18px "projector-legible" (index.css:106). WCAG-conscious palette with documented contrast rationale (index.css:54-60). Global `prefers-reduced-motion` kill-switch (index.css:144-150).

### Tests
- `playwright.config.ts`: `testDir ./e2e`, `workers: 1`, `fullyParallel: false`, 120s test / 15s expect timeouts, `baseURL = PLAYWRIGHT_BASE_URL ?? http://127.0.0.1:8177` (line 10), trace retain-on-failure, optional chromium executablePath override (offline-friendly). **No `webServer` key** — tests never boot a dev server or build anything; they attach to whatever already answers on 8177, i.e. the production uvicorn process serving the prebuilt dist.
- `npx playwright test --list` (ran this session, exit 0): **5 tests, 1 file**, serial:
  1. `dashboard.spec.ts:4` "supports the complete live review workflow" — tabs render, search-filter ("quartz" → slab report), expand "Why this score?" (aria-expanded asserted), "Needs decision" filter, paste-classify a unique report → "Manual review required", click "Not SIF-potential", Decisions table shows the override + "HSE reviewer", Insights/Patterns nested tabs, EN↔HI toggle with `html lang` attribute assertions (lines 45-49), and a zero-console-errors gate at the end (lines 5-8, 51).
  2. `:54` mobile 390×844 — no horizontal overflow (`scrollWidth === clientWidth`), heading visible.
  3. `:65` unsubmitted paste text survives a tab round-trip.
  4. `:73` CSV import accepts 1/1, then "Run demo batch" ingests **500/500 into the live API** (line 88) and the FLIP "just climbed to #1" re-rank message appears.
  5. `:92` offline honesty — `page.route("**/api/**") abort` → header shows "Offline demo", classify still produces "Manual review required" + "offline placeholder" copy.
- No unit tests of any kind for `lib/` (bandFor, report-display heuristics, phrasebook, use-flip) — coverage is entirely end-to-end.

### Build/tooling
- `package.json:6-10` scripts: `dev`, `build` (`tsc -b && vite build`), `preview`, `test:e2e`. **No `lint`, no `typecheck`, no `format` script.**
- No ESLint/Biome/Prettier config anywhere in dashboard/ or repo root (checked: `.eslintrc*`, `eslint.config.*`, `.prettierrc*`, `biome.json*` → none). No `.husky`, no `core.hooksPath`. No `.github/workflows` in the repo. Zero CI.
- Lockfile ground truth (all resolved & installed on disk): typescript **7.0.2**, vite **8.2.2**, react/react-dom **19.2.8**, lucide-react **1.42.0**, shadcn **4.21.0**, cn **0.2.6**, radix-ui **1.6.7**, tailwindcss **4.3.3**, @fontsource/ibm-plex-{sans,mono} **5.3.0**, @types/node **26.5.0**, @playwright/test **1.63.0**. Lockfile root entries verified in sync with package.json (0 mismatches → `npm ci` is reproducible).
- Verified this session: `npx tsc -p tsconfig.app.json --noEmit --incremental false` → **exit 0** (clean typecheck under TS 7).
- Bundle: dist total 1.7 MB; main JS 316 KB raw / 101 KB gzipped; CSS 61 KB; 39 woff2 font files; `public/live_ingest_500.csv` (204 KB) copied into dist. dist rebuilt 2026-09-25 14:28 and contains current phrasebook strings (grep "just climbed to #1" → hit in `dist/assets/index-B6Nq_RHL.js`), so dist matches src.
- `run.sh:81-82` requires the prebuilt dist (`npm ci && npm run build` once, online); runtime is fully offline. dist contains no baked `8177`/localhost string → `VITE_API_BASE` built as `""` (same-origin), consistent with `api.ts:28` default and (inferred, not read) with `.env.production`'s purpose.

## Findings

1. **Dependency truth: 10/10 runtime deps are really imported — zero phantom, zero unused.** Evidence: import census over `src/**` (every package appears; `shadcn` via `index.css:3`; `cn` via `lib/utils.ts:1` and the six ui files; `lucide-react` in exactly 4 files importing 5 icons: Search (feed.tsx:1), Upload (density.tsx:1), Loader2 (paste-classify.tsx:1), ChevronDown/ChevronUp (triage-card.tsx:1)). Severity: none (this is the good state). Why it matters: a hostile judge auditing package.json finds no bloat — but see finding 2 for where the overclaim actually lives.
2. **HANDOFF.md:149 still claims "Custom React + shadcn/ui + TanStack Table/Query + Recharts".** Verified false: no TanStack/Recharts in package.json, in any import, or in README (repo-wide grep: only match is `HANDOFF.md:149`; README.md's sole "chart" hit is a Mermaid `flowchart LR` at line 16, and `docs/discovery/02-domain-expectations.md:54` already documented the package list as clean). Severity: **minor** (doc-only) but reputationally sharp — HANDOFF is exactly the doc a judge reads first; it advertises two libraries that do not exist in the build. Fix is a one-line doc edit.
3. **E2E tests run against the live production server and mutate its database.** Evidence: no `webServer` in playwright.config.ts; `baseURL` defaults to `127.0.0.1:8177` (playwright.config.ts:10); the paste flow persists via `POST /api/classify?persist=1` (`api.ts:266-279`), and test 4 ingests 500 reports (dashboard.spec.ts:73-89, "accepted 500/500"). I ran only `--list` (read-only); running the suite would write ~501 rows into the live DB. Severity: **major** for demo ops — there is no test-database isolation, no teardown, no marker; an accidental `npm run test:e2e` before the finale pollutes the demo corpus and could shift the flag-rate story. Tests are otherwise high quality (real assertions, offline-honesty test, console-error gate) — this is an operational-safety gap, not a quality gap.
4. **E2E code is outside the typecheck surface.** `tsconfig.app.json:29` includes only `src`; `tsconfig.node.json:23` includes only `vite.config.ts`; no third tsconfig covers `e2e/` or `playwright.config.ts`. `tsc -b` therefore type-checks 100% of app code and 0% of test code. Severity: minor. Cheap fix: a `tsconfig.e2e.json` + `typecheck` script.
5. **No lint, no formatter, no git hooks, no CI.** Checked: no eslint/biome/prettier configs (dashboard or root), no `.husky`, no `core.hooksPath`, no `.github/workflows`. Severity: **major** for production credibility — the only quality gate that exists is `tsc -b` inside `npm run build`, which nobody is forced to run before committing. Combined with a bleeding-edge dependency set (finding 9), nothing detects drift between demo days.
6. **i18n is bilingual-complete but split across two mechanisms, with dead keys.** Phrasebook census (parsed from source this session): **103 keys, 103 `en` entries, 103 `hi` entries — 100% coverage, zero missing-language fallbacks**; `t()` is exhaustively typed via `as const` + `keyof` (phrasebook.ts:162-165), so a missing key cannot compile. 92 keys are actually referenced; **11 are dead**: `tabDecisions`, `workspaceTriage`, `workspaceTriageSub`, `workspaceInsights`, `workspaceDecisions`, `awaiting`, `overrides`, `overridesNote`, `siteActivity`, `activityBarrier`, `operationalOverview`. Separately, `gray-state-card.tsx:16-87` hardcodes a second translation table (10 gates × `{name, sentence, hiName, hiSentence}`) inside the component, bypassing the phrasebook — the gate copy for both languages lives in a different file and mechanism from all other UI strings. Severity: minor (works today; drift risk when copy is edited, and 11 unused keys confuse auditors). `t(lang, ...)` usage scan found zero used-but-undefined keys.
7. **The Hindi UI renders in an OS fallback font, not IBM Plex — the toggle's most visible promise is typographically broken.** The chosen fonts do not ship Devanagari: `@fontsource/ibm-plex-sans` subsets are cyrillic/cyrillic-ext/greek/latin/latin-ext/vietnamese; `@fontsource/ibm-plex-mono` is cyrillic/latin/vietnamese (verified by listing `files/` — 168 files, zero `devanagari`). dist ships 39 woff2 assets, none Devanagari. `index.css:8-9` fallback stacks contain no Devanagari-capable named font, so every Hindi string — the prominent हिं toggle label (lang-toggle.tsx:28), all 103 hi strings, and the 10 gate `hiName/hiSentence` copies (gray-state-card.tsx:21-86) — renders in whatever the OS substitutes (on a bare Linux demo laptop that can be an ugly mismatch or, in pathological cases, tofu). Remedy verified available this session via registry metadata: `@fontsource/ibm-plex-sans-devanagari@5.3.0` exists (IBM ships a separate Plex Sans Devanagari family); `@fontsource/ibm-plex-mono-devanagari` **does not exist** (npm E404) — so mono-font Hindi cells can never match Plex Mono; `@fontsource/noto-sans-devanagari@5.3.0` exists as an alternative. Severity: **major** — the EN/हिं toggle is a headline feature for an Assam-based client; inconsistent fonts in HI mode are visible in the first 5 seconds of any demo.
8. **Locale formatting is hardcoded to `en-IN` and never switches with the toggle.** Exactly two call sites: `App.tsx:136` (`toLocaleString("en-IN")` for the report count) and `views/review.tsx:76` (`toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })` for decision timestamps). Defensible (Indian HSE ops locale), but it means the language toggle changes only chrome strings — numbers/dates/title never localize. Related: `document.title` stays English in HI mode (index.html:10; App.tsx:42-44 syncs `lang` attr but not title), the toggle choice is not persisted (refresh resets to EN), and `phrasebook.ts:1` correctly scopes the toggle to UI chrome only ("Source reports are always shown unchanged") — report text is never translated, matching the backend's gray-and-preserve policy for Hindi reports (finding in domain docs). Severity: minor; the title/persistence items are 5-line fixes that polish a flagship feature.
9. **Stack coherence: TS 7 + Vite 8 + React 19.2 + Tailwind 4 + unified `radix-ui` + `cn` is bleeding-edge but internally consistent, and it compiles today.** Evidence: all versions pinned by lockfile (see inventory), lockfile in sync, `tsc --noEmit` exit 0 this session, dist built successfully today from this exact tree. The `radix-ui` monolith package (1.6.7) replaces the per-primitive `@radix-ui/react-*` packages — used for Slot (badge/button), Tabs, Separator only. `cn` is the shadcn-ui engine that replaces clsx+tailwind-merge with conflict resolution (node_modules/cn/README.md). Risk is ecosystem maturity and upgrade churn, not incoherence: with no CI (finding 5), a future `npm ci`-on-a-new-machine surprise lands on demo day. Severity: minor as-is (frozen lockfile); major if anyone regenerates the lockfile casually before the finale.
10. **No router = no deep links, no URLs, no back-button semantics.** All navigation is `useState` in App.tsx:16 (3 top tabs) + nested tabs in insights; refresh always lands on Triage; a filtered queue ("Needs decision", search "quartz") cannot be shared or bookmarked; browser Back exits the app. For a 3-tab demo this is a defensible scope decision, but production HSSE tooling lives on links (audit trail per report, density filtered to a site/date-range, an override's evidence). Severity: **major** product gap for the finale; low-cost partial remedy exists (URL-hash tab/filter sync) without pulling react-router.
11. **No CSP, and the shell trusts its own bundle.** index.html has no `Content-Security-Policy` meta; the app fetches only same-origin `/api` in production builds (no CDN anything — fonts and CSV are bundled), so the offline posture is genuinely good; a minimal CSP would close the story. Severity: minor.
12. **Verified-good surface worth keeping**: the strict tsconfig; the typed phrasebook; the honest offline doctrine (mock-first boot App.tsx:19-20, offline override fallback App.tsx:64-77, offline-honesty e2e test dashboard.spec.ts:92-100); the FLIP re-rank hook honoring `prefers-reduced-motion` (use-flip.ts:19-29); a11y touches (skip link App.tsx:110-115, `aria-pressed` lang buttons lang-toggle.tsx:19, `html lang` sync App.tsx:42-44, 18px projector base font index.css:106); Radix `forceMount` + `hidden` pattern preserving in-flight work across tabs (App.tsx:182-196). These are the trust-building details judges notice.

## Pain points (real HSSE reviewer at an oil & gas major)

- Clicking Browser-Back leaves the dashboard instead of returning to the previous tab/filter; there is no way to send a colleague "the queue filtered to needs-decision" — everything is ephemeral state (App.tsx:16,146).
- A reviewer who toggles हिं sees safety-critical gate explanations (well_control_watch, severity_watch — the highest-stakes copy in the product, gray-state-card.tsx:66-86) rendered in a font that does not belong to the app's visual system. In a domain where typography carries authority, this reads as "demo", not "tool".
- Refresh wipes the language choice, the workspace tab, and any URL context — an auditor mid-review of decision history lands back on an empty-feeling Triage tab.
- Nothing tells the reviewer that e2e "demo batch" ingest permanently writes 500 synthetic reports into the same store as real data (`Run demo batch` → 500/500 accepted); if judges run the Playwright suite or the demo-batch button twice, the corpus and its metrics drift silently.
- The footer disclaimer "Synthetic OIL-style demo data" (phrasebook.ts:109) is good; but HANDOFF.md's TanStack/Recharts line directly contradicts what a technically-fluent judge sees in package.json, and trust lost on page 1 of the handoff is hard to win back.

## Gaps vs production

- CI pipeline (lint + typecheck + build + e2e against an ephemeral backend) — nothing enforces the quality bar that today exists only by discipline.
- Linter/formatter baseline; pre-commit hooks.
- Unit tests for pure logic: `bandFor()` threshold semantics (band is derived client-side per orchestrator's note), `reportSiteLabel`/`inferredSite` regexes (report-display.ts:21-41), phrasebook completeness (en/hi parity could be a 5-line test).
- Typecheck coverage for e2e/playwright config.
- Devanagari webfont + font-stack update (finding 7).
- URL state (even hash-based) for tabs/filters; localization of `document.title`; persisted language choice.
- Test-data isolation for e2e (dedicated DB/profile or explicit cleanup), so the suite is runnable without contaminating the demo corpus.
- CSP meta and a documented dependency-upgrade policy for the bleeding-edge stack.

## Recommendation

KEEP — `package.json` dependency set exactly as-is (10/10 used, zero waste; rare and defensible under audit).
KEEP — React 19 / TS 7 / Vite 8 / Tailwind 4 / unified radix-ui / cn engine combo (verified compiling, internally coherent, frozen lockfile; changing stacks before the finale is pure risk).
KEEP — `vite.config.ts` same-origin proxy design (correctly justified: app/main.py has no CORS middleware, verified).
KEEP — typed `phrasebook.ts` t() design and 103/103 bilingual coverage (exhaustive-by-construction).
KEEP — the 5-test e2e suite's assertions and the offline-honesty test (genuinely strong for a demo repo).
KEEP — strict tsconfig incl. `erasableSyntaxOnly`/`noUncheckedSideEffectImports`; add only surface, don't loosen.
KEEP — use-flip FLIP hook + reduced-motion handling; `forceMount`+hidden tab persistence.
REMOVE — 11 dead phrasebook keys (or wire the 3 workspace-ish ones; dead keys are drift bait).
REMOVE — "TanStack Table/Query + Recharts" from HANDOFF.md:149 (doc edit; contradicts the real, already-clean package.json).
ADD — `@fontsource/ibm-plex-sans-devanagari` import in main.tsx + `"IBM Plex Sans Devanagari"` slot in the index.css:8 stack (registry-verified to exist; Plex Mono Devanagari does not exist — accept mono fallback, optionally add `@fontsource/noto-sans-devanagari`).
ADD — `typecheck` npm script + a tsconfig covering `e2e/` and `playwright.config.ts` (currently typecheck-blind).
ADD — minimal CI (GitHub Actions: `npm ci && tsc -b && vite build && playwright test --list`+optional run) and an ESLint flat config with `typescript-eslint` strict; this is the single cheapest credibility upgrade.
ADD — e2e isolation: run against a scratch DB copy (or add teardown deleting persisted test rows) so `test:e2e` can never pollute the demo corpus.
ADD — URL-hash sync for the 3 tabs + language + queue filter (≈30 lines, no router dependency) if deep-linking stays out of scope; a full router only if finale demos need shared filtered views.
MERGE — gray-state-card.tsx:16-87 inline EN/HI gate table into `phrasebook.ts` (one i18n mechanism, one file to edit).
MERGE — language persistence (localStorage) + `document.title` localization into the existing App lang effect (App.tsx:42-44).

## Verification summary

- `npx playwright test --list` → 5 tests listed (read-only; suite NOT executed — it would write to the live 8177 app).
- `npx tsc -p tsconfig.app.json --noEmit --incremental false` → exit 0 (no artifacts written).
- Phrasebook census, import census, lockfile sync, bundle sizes, font-subset listing, registry lookups: all run this session as described above; no metrics invented.
- Failed/unavailable: reading `dashboard/.env.production` (tool guard refuses env-pattern files); I did not bypass it. Its 286 bytes are inferable only indirectly: dist ships no baked API host (same-origin build) and vite loads `.env.production` for `vite build` by default.