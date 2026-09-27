# 13 — Review/Decision-History Surface + Design Token System Audit

**Phase 0 discovery — READ-ONLY.** Role: frontend review/audit surface + design token system.

**Files actually read (line counts):** `dashboard/src/views/review.tsx` (87), `dashboard/src/index.css` (150, complete), `dashboard/src/lib/mock.ts` (553), `dashboard/src/App.tsx` (213). Supporting reads (to verify claims, not reassigned surfaces): `lib/api.ts` (426), `lib/types.ts` (182), `lib/phrasebook.ts` (166), `components/ui/tabs.tsx` (87), `components/ui/table.tsx` (115), `components/gray-state-card.tsx` (215), `components/triage-card.tsx` (289), `components/band-badge.tsx` (39), `lib/utils.ts` (1), `index.html` (16); backend excerpts `app/schemas.py:140-203`, `app/storage.py:131-143,362-371,502-522`, `app/routes.py:361-388`, `dashboard/node_modules/cn/package.json`.

**Tools used:** Read, Grep (token/utility/ad-hoc counts across `dashboard/src`), Bash — `python3` WCAG 2.x relative-luminance contrast computation (alpha-blend cases computed by blending fg over bg in sRGB space before luminance), `cat` of the `cn` npm package metadata. Nothing modified; nothing on port 8177 touched.

---

## What exists today

### A. The token system (complete extraction — `index.css` is the single token source)

Three layers, all in `index.css`:

1. **`@theme inline` bridge (index.css:7-52)** — exposes ~30 shadcn semantic tokens (`background`…`sidebar-ring`), the 3 app-specific semantic tokens (`--color-verdict/--color-ok/--color-quiet`, index.css:11-13), 2 font stacks (`--font-sans`, `--font-mono`, index.css:8-9), and a 7-step radius scale all derived from one `--radius: 0.625rem` (index.css:89, 45-51) via `calc(var(--radius) * k)`.
2. **`:root` values (index.css:61-98)** — 35 custom properties, the complete inventory:

| Token(s) | Value | Real consumers (utility-usage counts grepped across `src/`) |
|---|---|---|
| `--verdict` `#b45309` | amber verdict | 12 uses: `text-verdict` 4, `bg-verdict` 5, `border-t/l-verdict` 2, `bg-verdict/5` 1 (triage-card, band-badge) |
| `--ok` `#047857` | quiet green | 12: `text-ok` 7, `bg-ok` 5 (status dots, "Reviewed by HSE") |
| `--quiet` `#64748b` | slate humility | 13 uses: `bg-quiet` 9 (status dots), `text-quiet` 4 (gray-state-card:129, triage-card:107,153) |
| `--background` `#f5f4f0` | paper | `bg-background` 5 |
| `--foreground` `#202226` | ink | `text-foreground` 51 |
| `--card` `#fdfdfb` / `--card-foreground` `#1c1e21` | card surfaces | `bg-card` 4, `text-card-foreground` 1 |
| `--popover` `#ffffff` + fg | popovers | shadcn primitives only |
| `--primary` `#1c1e21` / `--primary-foreground` `#ffffff` | ink buttons, skip link | `bg-primary` 5, `text-primary` 5 |
| `--secondary`/`--secondary-foreground` `#f0eee8`/`#1c1e21` | secondary buttons/badges | `bg-secondary` 4 (ui/button, ui/badge variants) |
| `--muted` `#f0eee8` / `--muted-foreground` `#5b6470` | quiet surfaces/labels | `bg-muted` 28, `text-muted-foreground` 74 — by far the dominant pair |
| `--accent`/`--accent-foreground` `#edeae2`/`#1c1e21` | — | `bg-accent` 0, `text-accent` 0 — **dead** |
| `--destructive` `#b42318` | error | `bg-destructive` 7 (all in ui/button, ui/badge `aria-invalid` variants), `text-destructive` 3 (density.tsx:200 `role="alert"`) |
| `--border` `#dedcd4` / `--input` `#d8d5cc` / `--ring` `#1c1e21` | hairlines/focus | `border-border` 30 (+ global default `* { @apply border-border outline-ring/50 }` index.css:101-103), `border-input` 4, `ring-ring` 5 |
| `--chart-1..5` | amber/slate ramp | **0 uses anywhere** — dead |
| `--sidebar*` (9 props, index.css:90-97 + @theme 14-21) | sidebar theme | **0 uses** — dead (no sidebar exists in the app) |
| `--paper` `#f5f4f0` (index.css:62) | duplicate of `--background` | 0 refs outside its own definition — dead alias |
| `--radius` `0.625rem` | derives sm/md/lg/xl/2xl/3xl/4xl | `rounded-md/lg/sm` widely; `rounded-4xl` (badge.tsx:7) |
| `--font-heading` (index.css:10) | aliases `--font-sans` | no-op token |

3. **Layer/base + components (index.css:100-142)** — html root `font-size: 18px` with a stated rationale ("base 18px, min 16px — projector-legible", index.css:106); `tabular-nums`, `line-height: 1.5`; 5 component classes (`page-shell`, `eyebrow`, `page-title`, `span-highlight`, `status-dot`); `::selection` `#e8ddca`; a global `prefers-reduced-motion` kill-switch (index.css:144-149).

**Type scale:** no custom size tokens — the Tailwind default ramp sits on the single 18px root decision (index.css:106), so text-xs = 13.5px, text-sm = 15.75px, base = 18px, 3xl = 33.75px. One decision scales the whole ramp — coherent. **Spacing:** no custom scale; Tailwind default utilities, with card spacing tokenized as `--card-spacing` var shorthand (ui/card.tsx:14).

**Ad-hoc usage quantified (grep, this session):**
- Raw hex in component markup: **0**. All hex lives in `index.css` (`:root`, `span-highlight` `#efe9dc` :130, `::selection` `#e8ddca` :140) plus one code comment (triage-card.tsx:15).
- Arbitrary color utilities (`text-[#`, `bg-[rgb…`): **0** in `src/`.
- Arbitrary-value utilities (`w-[`, `h-[`, `max-w-[…`): **~20 instances total**, ALL structural/layout — `max-w-[1320px]` (index.css:118), `h-[calc(100%-1px)]`/`p-[3px]` (ui/tabs.tsx:25,63), `border-t-[3px]`/`border-l-[3px]` (triage-card.tsx:71,118), `max-h-[22rem]`/`lg:max-h-[calc(100vh-16rem)]` (feed.tsx:233), `grid-cols-[minmax(300px,0.8fr)_minmax(0,1.7fr)]` (feed.tsx:182). No color-arbitrary values anywhere.
- Verdict: **real token discipline, not utility soup** — with ~20% dead weight (sidebar ×9 + @theme mappings, chart ×5, accent pair, `--paper`, `--font-heading`). Class merging is the official shadcn `cn` v0.2.6 (compiled clsx+tailwind-merge replacement; verified `node_modules/cn/package.json`), so App-level overrides of ui-primitive defaults (e.g. `text-muted-foreground` over the base `text-foreground/60`, ui/tabs.tsx:63) resolve predictably.

### B. The decision-history surface (`review.tsx`, 87 LoC)

- Two states: empty (dashed card, review.tsx:40-48) or a single `Table` with **6 columns**: Report / Field / Was / Now / Reviewer / When (review.tsx:53-61). Values humanized via a small label map (review.tsx:13-25); `old_value` struck through, `new_value` bold (review.tsx:68-73); timestamps `toLocaleString("en-IN")` hardcoded regardless of UI language (review.tsx:76).
- Data = `GET /api/review` → `OverrideOut[]` (App.tsx:27-31, 194-196). `OverrideOut` fields: `id, report_id, field, old_value, new_value, labeler, source, ts` (types.ts:132-141). **No rationale, no report text, no gate context, no link, no filter, no export, no pagination.**
- The backend is materially richer than the UI: `OverrideIn.rationale` exists (schemas.py:148), is persisted (storage.py:366-369), and is exported (`/api/review/export`, routes.py:381-388; latest-wins per (report_id, field) with `supersedes` lineage, storage.py:502-522). Write vocabulary is validated (`field: Literal["sif_label","rules","notes"]`, `SIF_LABEL_VALUES = ("sif_potential","not_sif_potential")`, schemas.py:156-170).
- The write path: one click on Confirm / Not-SIF in triage-card (triage-card.tsx:180-195) or gray-state-card (gray-state-card.tsx:161-174) → `POST /api/review` (api.ts:404-417) with `labeler: "hse_reviewer"` hardcoded (api.ts:414) and `old_value` = the client-derived **band** (App.tsx:58).

### C. App chrome (header/footer, `App.tsx` 213)

Header: title + health dot + report count + lang toggle (App.tsx:116-143); skip link (110-115); `document.documentElement.lang` syncs on toggle (42-44). Footer: "Model proposes, HSE disposes. Your decision becomes a training label." + an **unconditional** chip "Synthetic OIL-style demo data" (200-209, phrasebook.ts:109). Tabs = Radix primitives (`radix-ui` TabsPrimitive, ui/tabs.tsx:4), `forceMount` + `data-[state=inactive]:hidden` (App.tsx:182-196). `cn` v0.2.6 = official shadcn-ui compiled class-merge (verified in node_modules).

### D. Mock fixtures (`mock.ts`, 553 LoC)

9 `REPORTS` (mock.ts:227-437: ids 2588-2619, real OIL site names — Duliajan, Baghjan EPS, GGS-2, Moran GGS-1, Naharkatia, Tengakhat), 6 `MOCK_EXPLANATIONS` (147-225), 2×6 `DENSITY` rows (484-500), 10 `PATTERNS` (505-516), 3 `OVERRIDES` (520-551). Self-labeling: gate detail strings read "offline demo fixture" (mock.ts:84), `model_version: "mock-0.1.0"` throughout, plus a module-load invariant validator (mock.ts:441-480). UI disclosure: header flips to "Offline demo" when health is null (App.tsx:133); footer chip is static; **no per-row synthetic marker**.

---

## Findings

1. **Decision history is a thin table, not an audit surface — but the backend already supports the audit.** Observation: 87 LoC renders 6 columns and nothing else. Evidence chain for the dropped `rationale`: stored (schemas.py:148) → persisted (storage.py:366-369) → exported (storage.py:519) → present on the wire (api.ts:89 `ApiStoredOverride.rationale`) → **dropped** in `adaptOverride` (api.ts:192-203) → absent from `OverrideOut` (types.ts:132-141) → absent from `review.tsx` → never captured at decision time (single click, triage-card.tsx:180-195). Even the phrasebook's only "audit trail" string is a dead key (`overridesNote`, phrasebook.ts:74-77, 0 usages). Severity: **blocker** for the compliance story — the surface that judges will treat as "the audit trail" records a value flip with no reason.
2. **Reviewer identity is theater.** Live: constant `"hse_reviewer"` (api.ts:414; server default schemas.py:147), rendered as "HSE reviewer" (review.tsx:22). Offline fallback: fabricated plausible personnel names `"hse.kgohain"`, `"hse.rbora"` (mock.ts:527,537,547) in identical table formatting. Severity: **major**. In a compliance tool, "who decided" with a constant is not an answer; a fabricated name is worse than a blank.
3. **The UI forbids correction; the data model anticipates it.** After one decision the buttons vanish ("Reviewed by HSE", gray-state-card.tsx:154-158, triage-card.tsx:168-172; App.tsx:85 builds `reviewedReportIds` to suppress re-decision). Yet the backend is deliberately append-only latest-wins with `supersedes` lineage (routes.py:363-366, storage.py:506-510). A mis-click on Confirm is permanent **in the UI only** — the exact correction flow the schema supports is unreachable. Severity: **major**.
4. **Export is backend-only.** `/api/review/export` returns compliance-grade NDJSON (latest-wins, exact-dup collapse, `supersedes`, `rationale`, `decided_at` — routes.py:381-388, storage.py:512-522), but review.tsx has no export affordance of any kind, and nothing in phrasebook.ts references it. Severity: **major** — for a compliance tool, "is it exportable?" is answered yes at the API and no at the product.
5. **`old_value` vocabulary is incoherent in the audit rows.** Live flow writes `field: "sif_label"` with `old_value = current.prediction.band` — a client-derived HIGH/MODERATE/LOW string (App.tsx:58) — while the documented `sif_label` vocabulary is `("sif_potential","not_sif_potential")` (schemas.py:156). The validator checks only `new_value` (schemas.py:166-170), so band values pass. Mock fixtures make it worse: row 1 uses label vocabulary (mock.ts:525-526), row 2 band vocabulary (535-536), row 3 uses `field: "line_of_fire"` (mock.ts:544) which is **not a legal write field at all** (schemas.py:163) — that fixture cannot be produced by the real endpoint. `humanize()` then renders "High priority" under a column the docs call an SIF assessment (review.tsx:16-21). Severity: **major** — the audit table's semantics are incoherent between rows.
6. **No trace from a decision back to its evidence.** `#{o.report_id}` is plain text (review.tsx:66); no router exists, so a reviewer cannot open the report, its score, or its evidence spans behind a decision. No date/reviewer/field filter, no pagination. Severity: **major** (compounds the orchestrator's "no time dimension" finding — the audit surface has none either).
7. **Accessibility is largely real, with three concrete defects.** Positives: Radix Tabs give genuine roving-tabindex keyboard nav + `focus-visible` rings (ui/tabs.tsx:4,63) — not a hand-rolled ARIA reimplementation; skip link present (App.tsx:110-115); `lang` attribute syncs (App.tsx:42-44); status dots are `aria-hidden` with adjacent text; decisions confirm via `role="status"` (triage-card.tsx:197); `prefers-reduced-motion` honored (index.css:144-149). Defects: (a) skip-link target `<main>` lacks `tabIndex={-1}` (App.tsx:145) so activation does not move focus into content; (b) skip link uses `focus:` not `focus-visible:` (App.tsx:112); (c) review table has no caption and the container `overflow-x-auto` (ui/table.tsx:9-10) is not keyboard-scrollable. Severity: **minor**.
8. **Contrast: measured, mostly passing, two real failures + one wrong self-documentation.** WCAG 2.x relative luminance, computed this session (alpha cases blended in sRGB):

| Pair | Ratio | Verdict |
|---|---|---|
| amber `#b45309` on paper `#f5f4f0` | 4.56:1 | PASS 4.5 (0.06 margin) |
| amber on card `#fdfdfb` / popover `#fff` | 4.93 / 5.02 | PASS |
| ok `#047857` on paper / card | 4.98 / 5.38 | PASS |
| quiet `#64748b` on paper | 4.32:1 | **FAIL body** (passes 3:1 large/UI) — safe only because all `text-quiet` sits on card (4.67:1); undocumented invariant |
| muted-fg `#5b6470` on paper / card / muted / accent | 5.45 / 5.89 / 5.17 / 4.99 | PASS |
| muted-fg `/70` on paper (App.tsx:135) | **2.97:1** | **FAIL** (text-sm body) |
| muted-fg `/70` on card (gray-state-card.tsx:149) | **3.08:1** | **FAIL** (text-xs mono detail) |
| ink `#202226` on paper / `#1c1e21` on card / white on primary | 14.47 / 16.40 / 16.71 | PASS |
| destructive `#b42318` on card | 6.46 | PASS |
| span-highlight fg on `#efe9dc` | 13.17 | PASS |
| rule-bar fill `bg-foreground/70` vs track | 5.34 | PASS |
| focus ring `ring/50` blended on paper | 3.19 | PASS 3:1 UI |
| border `#dedcd4` on card / paper | 1.35 / 1.25 | decorative hairlines (informational) |
| input border `#d8d5cc` on card | 1.44 | decorative (inputs identified by bg+placeholder) |

   Severity: **minor** (the two `/70` text instances are small peripheral strings), but note `index.css:57`'s own comment claims amber is "5.9:1 on white" — measured **5.02:1**. The token file's self-documentation overstates its own AA margin; and amber's 4.56:1 on paper means any future `text-verdict/80`-style alpha use on paper would fail body AA.
9. **Footer disclosure mislabels direction.** "Synthetic OIL-style demo data" (App.tsx:205-208, phrasebook.ts:109) renders unconditionally — including when the app is live showing real ingested OIL reports (5,056 rows). Offline, the inverse: fixture rows carry no per-row synthetic marker; only the header flips to "Offline demo" (App.ts:133) and the data self-labels (`mock-0.1.0`, "offline demo fixture"). Severity: **minor** (medium if a judge screenshots the live app with the synthetic chip visible).
10. **Dead token weight.** `--sidebar*` ×9 (+ @theme mappings), `--chart-1..5`, `--accent`/`--accent-foreground` utilities, `--paper`, `--font-heading`: **0 real consumers each**. Dead phrasebook keys: `overridesNote`, `tabDecisions`, `workspaceDecisions` (grepped, 0 usages). Severity: **minor**.

**What is genuinely good and worth naming:** the semantic color trio (`verdict`/`ok`/`quiet`) is a real token system — one amber, reserved; words + position carry band semantics, never hue alone (band-badge.tsx:11-12, index.css:54-60); 0 raw hex and 0 arbitrary color values in markup; `text-3xl` verdict as the largest type on the card (triage-card.tsx:77-84); the "no red/green pairing" rule is honored (destructive appears only in ui-primitive `aria-invalid` variants and one density error alert, density.tsx:200); explanation expander has `aria-expanded`, skeleton `aria-busy` (triage-card.tsx:251,271); 18px root with tabular-nums is a deliberate projector-legibility decision, documented in-line (index.css:106-110).

---

## Pain points (where an HSSE reviewer at an oil & gas major loses trust)

- **"Who signed this off?"** → a constant string, or — if the demo runs offline — two plausible Assamese names that correspond to no real system. Either answer invites a follow-up the surface can't support.
- **"I clicked Confirm on the wrong report."** → no undo, no re-decide, no supersede. The backend supports it; the UI forbids it.
- **"The OISD inspector wants the decision log."** → the reviewer must be told "there's an API endpoint" — nothing on the surface exports, prints, or links it.
- **"Show me report #2566 that was overridden."** → impossible; the id is text, the router doesn't exist, the report can't be opened from the audit row.
- **"What did the model originally say and why?"** → `old_value` is a band in one row and a label in another (finding 5), so the Was→Now story is unreliable.
- **"Which of these names are real?"** → offline fixtures and live rows are visually identical in the table; only the header status chip differentiates.
- Date/decency of scale: at hundreds of overrides the flat table just scrolls; no filter, no sort, no jump-to-date.

---

## Gaps vs production

- Rationale capture (input) and rationale display (column/expand) — the storage layer already has the column.
- Reviewer identity: even a lightweight "who is reviewing?" session name beats a constant; the audit claim collapses without it.
- Export button (NDJSON/CSV) wired to `/api/review/export`, with a supersede/correction flow in the UI.
- Time dimension: date filtering on decisions (and reports) — matches the orchestrator's cross-cutting finding 5.
- Deep links (URL per report/decision) — blocked today by the no-router decision; feeds the frontend-stack decision doc.
- Scale: pagination or virtualization once overrides > ~200; sort by date/report.
- Per-row synthetic labeling for offline fixtures; conditional footer chip tied to data provenance, not hard-coded.
- Token docs accuracy: correct index.css:57's "5.9:1" to the measured 5.02:1; document the "text-quiet never on paper" invariant; prune the ~20 dead tokens (sidebar/chart/accent/paper/font-heading).

---

## Recommendation

- **KEEP** the `index.css` token architecture (semantic trio + `@theme inline` wiring + derived radius + 18px root): measured AA pass on every real text pair, zero raw hex in markup, ~20 arbitrary values all structural — this is real discipline, cheap to keep.
- **KEEP** Radix Tabs + shadcn table/card primitives and the `cn` merge strategy: native keyboard nav, correct focus rings, no hand-rolled ARIA.
- **KEEP** the backend audit design (`/review` append-only + `/review/export` latest-wins with `supersedes`): it is the strongest compliance asset in this surface — build the UI on it.
- **KEEP** the mock-fixture self-validation (`validateMock`, mock.ts:441-480) and its "offline demo fixture" gate-detail labeling.
- **REMOVE** `--sidebar*` (9 tokens + 8 @theme mappings), `--chart-1..5` (+ mappings), `--accent`/`--accent-foreground` utilities, `--font-heading` alias: 0 consumers, pure maintenance noise.
- **MERGE** `--paper` into `--background` (or invert the alias direction so one hex exists once): duplicate definitions invite drift.
- **ADD** a rationale input to the decision flow and a rationale column/expand in review.tsx — backend schema, storage, and export already support it; only the UI contract and view need the field threaded through (`adaptOverride`, `OverrideOut`).
- **ADD** an Export control on the review surface hitting `/api/review/export` (NDJSON today; CSV wrapper optional).
- **ADD** a lightweight reviewer-identity capture (session name prompt or header field) replacing the hardcoded `"hse_reviewer"` (api.ts:414); fix `old_value` to always carry the model's actual prior value (score-band AND label, or normalize field values) — one vocabulary per field.
- **ADD** report deep-links from audit rows (requires the router decision), plus date/sort on the decision table.
- **ADD** per-fixture synthetic markers in the UI for offline rows, and make the footer chip conditional on data provenance.
- **FIX** (small diffs): `tabIndex={-1}` on `#main-content`, `focus-visible:` on the skip link, `text-muted-foreground/70` → full `text-muted-foreground` (2 real AA failures), correct the amber contrast comment (5.02:1, not 5.9), add a `<caption>` or `aria-describedby` to the review table.

**Bottom line:** the token system passes its audit with real discipline and two cosmetic lies (a wrong self-documented contrast number and ~20 dead tokens). The decision-history surface does not pass: the backend already implements a credible audit trail (validated vocabulary, append-only, rationale, NDJSON lineage export) and the 87-line UI surfaces almost none of it — no rationale, no identity, no correction, no export, no traceability. The cheapest large win available in this codebase is UI-only: thread the fields that already exist to the screen.

---

## Measurement provenance

- **Contrast ratios** computed this session with the WCAG 2.x relative-luminance formula (`lin = (c/12.92 if c<=0.04045 else ((c+0.055)/1.055)^2.4)`, `L = 0.2126R+0.7152G+0.0722B`, `(L1+0.05)/(L2+0.05)`), via a 25-line `python3` script run in this session. Alpha-modifier pairs (e.g. `text-muted-foreground/70`) were computed by blending fg over bg per sRGB channel at the stated alpha first, then applying the formula. Repo was not modified; script ran inline.
- **Token/usage counts** grepped this session across `dashboard/src` (`*.ts`/`*.tsx`): semantic utility counts in section A's table; raw-hex grep `#[0-9a-fA-F]{3,8}` (matches only `index.css` + one comment); arbitrary-color grep `-(text|bg|border|ring|from|to|shadow)-[(#|rgb|hsl|oklch` → 0; arbitrary-value grep `(text|bg|w|h|min-…|p|px|py|pt|pb|gap|size|rounded|border|ring|basis|top|bottom|left|right|inset)-[...]` → 18 occurrences (+2 `border-t/l-[3px]` variants matched by a second pattern); dead-token greps (`bg-sidebar`, `bg-chart`, `bg-accent`, `text-accent`, `border-sidebar`, `--paper` refs) → 0 each.
- **Phrasebook dead keys** grepped across `src/*.tsx` excluding `phrasebook.ts` → 0 usages (`overridesNote`, `tabDecisions`, `workspaceDecisions`).
- **What I did not measure:** I did not open the live app on port 8177 (read-only constraint honored; no browser session, no screenshot). All runtime-behavior statements (mock fallback rendering, offline names appearing) are inferred from source paths, cited above. The `5,056 reports` count comes from the orchestrator's brief, not my own observation.