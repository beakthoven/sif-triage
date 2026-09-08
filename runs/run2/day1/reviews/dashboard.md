# Day-1 Evening Review — dashboard/src (demo-flow logic + offline behavior)

**Reviewer role:** review-dashboard · **Date:** 2026-09-08 · **Mode:** read-only source review + live probing
**Probed:** live demo server `:8177` (read-only: stateless `/api/classify` + GETs only — health verified
unchanged `n_reports=5050, n_overrides=0` after probing); throwaway full instance on `:8191`
(SIF_DB_PATH=/tmp copy of `app/runtime.db`, n=11420); static-only `dashboard/dist` on `:8190`
(API-down simulation). All throwaways stopped after probing.
**Evidence screenshot:** `runs/run2/day1/reviews/dashboard_beat2_corruption.png` (live Beat-2 card on :8177).

## Verdict

Two SEV1s. The offline doctrine and async-cancellation design are genuinely solid (verified live, see §D).
The demo's money beat is currently broken in the browser: the span pipeline corrupts the report text on
11 of 13 demo cards, and the standard documented rebuild command silently produces an OFFLINE-only bundle.

**Counts: SEV1 ×2 · SEV2 ×7 · SEV3 ×7** (+ 5 cross-owner notes for other agents)

---

## SEV1

### SEV1-1 — Span pipeline corrupts the report text on the money cards (11/13 demo cards)

Two stacked defects, both reproduced live on :8177:

**(a) Server emits unsorted spans; `HighlightedText` assumes sorted → duplicated text segments.**
`dashboard/src/components/highlighted-text.tsx:15-20` walks spans in array order and resumes the plain
text from `cursor = s.end` of the *previous* span. When a span's `start < cursor`, the gap is never
emitted as a skip but the trailing `text.slice(cursor)` re-emits already-rendered text → the blockquote
shows **duplicated chunks of the report**. Probe of `/api/classify` for all 13 `demo_corpus.jsonl` cards:
spans unsorted on 11/13; reimplementing the component's slicing reproduces corrupted output
(e.g. contrast-green 322→389 chars, verbatim-osha 354→527, long-report 2259→2575).

Live-UI confirmation (screenshot): Beat 2 `contrast-green` card renders
*"…at Jorajan during pipe handling in the morning[.] drilling rig RJ[-]18 **at Jorajan during pipe
handling in the morning**…"* — the clause twice. Stored feed cards are equally affected (report #5050:
*"…fall onto fall toward him when the A-frame…shifted, causing the material to fall onto…"*).
Affected 90-s beats: **2 (contrast-green), 4 (wc-baghjan-1), 7 (verbatim-osha)** + encores. Beat 1
(contrast-red) and wc-baghjan-3 escape only because their spans happen to be sorted.
Client fix is one line (sort spans by `start`, drop overlaps) — but see (b).

**(b) The span *content* is garbage regardless of order.** Server spans for the hero cards:
contrast-red → `'.'`, `'ethe'`, `'red'`; contrast-green → `'.'`, `' drilling'`, `'-'`;
wc-baghjan-1 → `'.'`, `'h'`, `' Bag'`. Substring-valid but semantically meaningless — the demo's core
wow ("shows you exactly why, in the report's own words", D2) currently highlights punctuation.
Expected spans per annotations ("fell past the drill floor", "near two roughnecks") are absent.
Root cause is model/span-head side (owner: classifier/explain agent — D2's keyword-attribution fallback
looks like the honest ship path), but even after (a) is fixed the amber marks stay meaningless until
span extraction is fixed or the fallback ships.

### SEV1-2 — Documented rebuild command silently bakes `localhost:8177` → whole app falls to mock at the doctrine address

`api.ts:28` defaults `VITE_API_BASE` to `http://localhost:8177`; the D26 fix ("rebuild with relative base")
exists **only in the deployed `dist/` artifact, not in source or any build script**. Reproduced:
plain `npx vite build` (fresh, today) emits a bundle containing `localhost:8177` (grep count 1);
`run.sh:82` and `packaging/make_tarball.sh:31` both instruct exactly `npm ci && npm run build` with no env.
A rebuilt bundle served at `http://127.0.0.1:8177/` fetches cross-origin (`localhost` ≠ `127.0.0.1`),
the API has no CORS middleware → every call fails → **silent OFFLINE/mock mode on demo day**
(mock data presented as the feed; only the small "OFFLINE DEMO" badge betrays it).
`demo_verification.md` F8 flagged the symptom pre-D26; the fix was never encoded.
Fix: default `BASE` to `""` (same-origin) and/or commit `dashboard/.env.production` with `VITE_API_BASE=`.
Current deployed dist is correct (verified: no `localhost`/`127.0.0.1` strings in bundle, all 15 page-load
requests same-origin) — do not rebuild until the default is fixed.

## SEV2

### SEV2-1 — Ingest failure under a LIVE server silently swaps real density rows for hardcoded mock numbers

`views/density.tsx:164`: on `ingestCsv` throw, `setRows(cur => cur === DENSITY_BEFORE ? DENSITY_AFTER : DENSITY_BEFORE)`.
When live rows were loaded (identity ≠ mock), the table jumps to **DENSITY_BEFORE (fabricated)** while the
header still says LIVE. Reproduced on throwaway :8191 (real rows loaded) by rejecting only `/api/ingest`
in-page: table flipped to `Duliajan — Workover Rig #7|128` etc. with the LIVE badge on. An ingest hiccup
mid-demo would put invented numbers in front of judges with zero indication. Fix: on failure keep `cur`,
show an honest error note, flip to the scripted path only when never-live.

### SEV2-2 — "Simulate ingest → re-rank" has no confirm and no idempotency: every press inserts 6 new rows

Reproduced on throwaway :8191: press → `n_reports 11421→11427` ("accepted 6/6"), second press → `11433`.
Each press re-inserts the same 6 hardcoded Baghjan records (they then also earn near-dup badges).
A stray/double press on the demo DB perturbs the money-beat arithmetic (script pins 31+50+15=96; the
:8177 DB is already at 5050). Needs a confirm or a "already ingested this session" disable.

### SEV2-3 — Paste race: rapid clicks fire N classify POSTs; raced rows share ONE negative id

Reproduced on :8177 page: 5 same-task clicks on Classify → **5 POST /api/classify** (the `classifying`
state guard cannot flush between same-task dispatches) → 6 identical LIVE queue rows. Because the id is
allocated from the render-closure (`Math.min(0, ...reports.map(r=>r.id)) - 1`, `feed.tsx:51`), all raced
rows got the **same id** — clicking any one sets `aria-current="true"` on all five (verified in DOM).
Duplicate React keys to boot. Physical double-click is likely spared, but Ctrl+Enter/impatient clicks
during a slow (clamped) classify can hit it. Fix: allocate ids from a ref counter; disable the button
synchronously (`disabled` attr is already bound — set it via `useState` + check a ref in `submitPaste`).

### SEV2-4 — Triage card asserts a single rule, contradicting D22's ruling; asserts 0.00-prob rules on LOW cards

D22 adjudicated: "the design shows per-rule probabilities, **never a single asserted rule**". The card
renders `Rule: {top.name} {top.prob}` (`triage-card.tsx:94`). With D22 drift live this is wrong on the
hero card: contrast-red asserts **"Rule: Confined Space 0.44"** (annotation expects Line of Fire dominant).
On LOW cards it asserts nonsense: `contrast-green` → "Rule: Working at Height **0.00** (2nd: Driving 0.00)"
(screenshot). Either show the top-N probability bars per D22, or suppress the rule line when top prob < flag
threshold.

### SEV2-5 — "Flagged for HSE review" chip renders on every card including LOW

`triage-card.tsx:47-49` shows the chip unconditionally. Beat 2's narration is "the system leaves it
alone" — the LOW card on screen says "Flagged for HSE review" (screenshot). Gate the chip to HIGH/MODERATE
or reword per band.

### SEV2-6 — Language-gate copy claims live translation that doctrine adjudicated away

`gray-state-card.tsx:38`: "Hindi detected → translated → scored, shown as a pipeline" + "translation
available" badge (`:92-96`). `app/gates.py:170`: "Report text is never machine-translated live
(adjudicated)" — live translation is an explicitly *rejected* proposal (DECISION_LOG). The false sentence
is visible in the Sentinel legend on **every** feed view and on the hinglish gray card (encore row).
Reword to "language beyond current support — routed to review, original preserved, never silently
mis-scored" per the rehearsed line.

### SEV2-7 — Gray cards / Review queue offer no disposition action

Beat 3 line: "a human glances and disposes in seconds" — `GrayStateCard` has zero buttons and takes no
`onOverride`; the Review tab renders gated reports as the same button-less cards. There is no UI path to
dispose a gated report (Confirm/Not-SIF exist only on `TriageCard`). Either add disposition actions to
`GrayStateCard` or drop the line from the script.

## SEV3

1. **Paste box wiped on any tab switch** — Radix unmounts inactive `TabsContent` (verified: inactive panels
   have 0 children); `pasteText` lives in `FeedView`. Paste 380 words, glance at Density, text gone
   (reproduced). Lift state to App or `forceMount`.
2. **Density progress interval not cleared on unmount** (`density.tsx:117,137,172` — no effect cleanup);
   harmless under React 19 (setState no-op) but sloppy; a mid-ingest tab switch leaves the interval firing.
3. **`bandFor` comment vs code mismatch** (`api.ts:130-132`): comment says "match the server's gray band
   [0.40, 0.60]" but HIGH is `>= 0.7`; a 0.65 score shows MODERATE while 0.45 is a gray card. Behavior
   defensible, comment wrong — fix the comment or derive from config.
4. **Hindi toggle: demo-critical card strings stay English** — reproduced in हिं mode: "HIGH REVIEW
   PRIORITY" (every BandBadge), "Band", "Rule: …", "Declared out-of-scope (never scored): …", DUP/GATE
   chips, the entire Sentinel legend, density table headers, patterns blurbs, "…just climbed to #1".
   Phrasebook scope is chrome-only by design (hinglish row annotation acknowledges this), but the Beat-4
   claim "the interface speaks Hindi" lands on a card whose band/rule/footer chrome is half-English.
   Also: **no Devanagari font is vendored** — `@fontsource/ibm-plex-*` ships latin/cyrillic/greek/vietnamese
   only (verified: 80 assets, zero devanagari); Hindi chrome renders via system font fallback — tofu risk
   on a bare demo laptop and a gap in the "vendored fonts, zero external requests" story.
5. **"%" doctrine**: the only user-visible literal `%` is `95% CI` in the patterns view (`patterns.tsx:13,100`;
   confirmed rendered live). Scores/rates are "per 100" elsewhere per doctrine — adjudicate whether the CI
   label gets the same treatment ("95% CI" → "95 in 100"?) or is an accepted stats notation.
6. **Feed optics**: 60% of the top-200 queue rows carry a **DUP chip** (probed /api/reports: 120/200) —
   Beat 7's special banner moment is diluted by a wall of DUP badges; also mixed date formats in the queue
   ("07.11.2025" vs "2025-01-09", rows #4855/#4854).
7. **Re-rank money beat may show no visible #1 change on the current DB**: live `/api/density` top cells are
   saturated rate-1.0 (`Kathalguri 157/157`, …); on the throwaway the ingest produced no
   "…just climbed to #1" line (the line only renders when a *new* #1 emerges). Rehearsal must confirm the
   FLIP beat on the real demo DB state or pre-stage the fallback (script's Sensitivity note covers this).

## Verified GOOD (attacked, held)

- **Offline doctrine / zero external**: all 15 page-load requests on :8177 same-origin (HTML, JS, CSS,
  woff2, /api/*); fonts vendored via @fontsource; favicon is inline SVG; no CDN/analytics/fonts external.
  Dist bundle contains no `localhost`/`127.0.0.1` literal (D26 artifact is good — see SEV1-2 for the trap).
- **API-down per view** (static-only :8190, every /api/* 404s): header flips to OFFLINE DEMO; feed renders
  mock queue; classify yields the designed all-gray confidence card + "API unreachable — offline
  placeholder, not a score" note (never a fake score); density shows mock BEFORE + scripted 2 s re-rank
  with the "climbed to #1" line; patterns/review render mocks; override click falls back to a local
  negative-id row and the Review badge increments. No crashes, no red.
- **Async correctness**: explanation expander cancels on report switch/unmount (cancel flag, deps
  `[open, report.id]`); App mount fetch has a cancel flag; mid-classify tab navigation loses nothing
  (result lands via App-level `onClassified` — verified: 1 POST, row present after round-trip);
  patterns kind-toggle hammered 6× in 360 ms settles on the final selection with matching cards.
- **Doctrine greps**: no `red-`/`rose-`/hex-red in src (the `--destructive` token + `destructive` variants
  in `ui/badge|button.tsx` are unused dead variants — no `variant="destructive"` call sites); no
  "accuracy"/"predict*" user-visible strings; score always labeled "triage score"; rates "per 100".
- **Build**: `tsc -b` clean; `vite build` clean in 156 ms, **no chunk-size warning** (307 kB JS /
  97.6 kB gzip); deterministic content hashing. Absolute `/assets/*` paths mean dist works only from a
  root mount (the FastAPI `/` mount — the supported path); it does **not** work from `file://` or a
  sub-path (acceptable per run.sh doctrine; noted for the USB-fallback story).
- **Server state untouched**: :8177 health identical before/after probing (5050 reports, 0 overrides);
  writes went only to throwaway DBs; throwaway instances on :8190/:8191 stopped.

## Cross-owner notes (reproduced live, not dashboard-owned)

1. **first-aid-green still scores 0.964 HIGH** on masked-v1 (D21 — v4 retrain pending; fallback line ready).
2. **Well-control tag over-fires vs annotations**: contrast-red wc=True (`\bbop\b` hits "BOP deck"),
   hinglish wc=True (`\bworkover\b`), long-report wc=True — spec-frozen keywords (`classifier.py:47-66`,
   D23) vs card annotations expecting false. Gray-gated cards hide it; the Beat-1 hero card shows the tag.
3. **long-report encore beat hijacked**: live negation gate fires (annotation asserts it can't) → gray
   card replaces the chunked-badge amber card. Annotation/self-check stale for the current model+gate.
4. **codes-only lands LOW (0.115), not the annotated gray/review-queue state** — score outside [0.40,0.60];
   no EI keyword tag visible (top rule hot_work 0.01). Codes-path min_length acceptance itself works.
5. **`/api/review` accepted junk historically** (found in the app/runtime.db copy: `field="garbage_field';
   DROP TABLE overrides;--"`, `new_value="maybe_sometimes"`, all report_id=1 — another agent's probes).
   Server-side validation gap; API agent's lane. Client-side POST with report_id=-1 (optimistic LIVE row)
   did **not** persist (n_overrides unchanged) — good.

## Files written

- `runs/run2/day1/reviews/dashboard.md` (this file)
- `runs/run2/day1/reviews/dashboard_beat2_corruption.png` (live Beat-2 card: duplicated text, fragment highlights, D28 banner, LOW-card "Flagged for HSE review")
