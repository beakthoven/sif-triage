# 50 — Visual Triage QA (Phase 0 Discovery)

Date: 2026-09-25. Tester: vision-capable visual-QA subagent. Target: **Triage tab** of the live app at http://127.0.0.1:8177/ (uvicorn + INT8 ONNX ModernBERT, 5,056 reports in SQLite, 1 override). Method: Playwright MCP at 1440×900 and 390×844; every screenshot read back with a vision model; computed styles and network log pulled for claims that need more than eyeballing.

Integrity notes:
- **Read-only on the app**: no source files touched, no rebuild, no restart, port 8183 untouched.
- **One intentional write through the app's own flow**: the timed Classify test (§8) posted one report ("Operator was working on the separator vessel manway…"), which the app itself persisted — counts went 148/200 → 149/201. No review decision (Confirm/Not-SIF) was ever clicked. If demo data must stay pristine, delete that row.
- **Shared browser contention**: a concurrent session was driving the same browser (a second tab on `:8199` appeared mid-run, and my tab was repeatedly flipped to Insights and back). Every state-dependent observation below was re-verified after re-selecting the Triage tab; timing numbers are approximate to ±0.4 s because of it.

---

## 1. Screenshots captured

All in `artifacts/qa-evidence/`:

| File | What it shows |
|---|---|
| triage-01-fullpage-1440.png | First load, Triage tab, desktop full page (1516 px tall) |
| triage-02-viewport-1440x900.png | Above-the-fold viewport |
| triage-03-mobile-390x844-fullpage.png | 390 px: app came up on **Insights**, tab bar clipped |
| triage-04-snapshot-mobile.yml | Mobile a11y snapshot (skip link first in tree) |
| triage-05-mobile-triage-fullpage.png | Mobile Triage tab after manual click |
| triage-07-desktop-after-reload.png | Desktop restored after the resize flip |
| triage-09-priority-queue.png | Priority queue + auto-selected high card (0.75) |
| triage-14-highcard-detail.png | Full high-priority card, "Why this score?" collapsed |
| triage-16-whyscore-expanded.png | "Why this score?" expanded — 0.66 threshold named |
| triage-17-record-outcome.png | "Record review outcome" open + skip-link pill visible |
| triage-18-evidence-spans-zoom.png | Device-scale zoom of the evidence spans |
| triage-21-uncertain-card.png | Gray route card ("Report mentions a drill or test") |
| triage-22-noreview-needed.png | Green "Low review priority" card — body is "LOTO not applied" |
| triage-24-loto-whyscore-full.png | Full explanation for the LOTO card |
| triage-25-reviewed-tab.png | The one decided card — "Reviewed by HSE", nothing else |
| triage-26-focus-decision-buttons.png | Visible focus ring on a decision button |
| triage-27-hindi-toggle.png / -28 / -29 | हिं toggle: Insights table, viewport, full Triage in Hindi |
| triage-30-classify-result.png | Freshly classified report (0.95, zero evidence spans) |
| triage-31-neardup-card.png | Near-dup card with the raw debug banner |
| triage-32-search-moran.png | Search working ("Moran" → 11/201) |
| (triage-06/08/…-*.yml) | a11y snapshots backing the keyboard/DOM claims |

---

## 2. First impression & visual hierarchy (Q2)

Desktop 1440: header ("Safety Report Triage / OIL India · HSE operations", `● Online · 5,056 reports indexed`, EN/हिं) → tab bar (Triage 10 · Insights · Decision history 1) → a full-width "Classify a report" panel → two columns: Work queue (left, ~1/3) and the detail card (right, ~2/3) → a below-the-fold "Why some reports need manual review" accordion → footer ("Model proposes, HSE disposes. Your decision becomes a training label." / "● Synthetic OIL-style demo data").

- **Where am I, what first?** Clear. The active tab is underlined, the queue announces "Work from the top as capacity allows", and the detail card answers "what am I looking at".
- **But the default selection is the worst possible teacher**: on first load the detail pane opens on a degenerate "Very short report" card that shows **no score, no rules, no evidence** — the reviewer's first contact with the "AI triage engine" is a card where the engine did nothing. (triage-01/02.)
- **Proportions**: the detail card ends at ~44% of the viewport height; the right column below it is dead whitespace on every screen I captured. The queue, not the content, anchors the eye.
- Mobile 390: stacks cleanly (classify → queue → detail), but the tab bar clips the third tab to "Decision hist…" with no scroll affordance (triage-05).

## 3. The three representative cards (Q3/Q4)

### (a) High-score flagged — "Moran · lifting", triage score 0.75 (triage-14, -16)
On-screen: giant orange "High review priority" + "Flagged for HSE review" + "triage score 0.75"; "Matching life-saving rules" bars — Safe Mechanical Lifting 0.98, Line of Fire 0.07, Working at Height 0.07; quoted text "**Crane** lifting operation with damaged **sling** over live equipment" with spans marked; collapsed "Why this score?" and collapsed "Record review outcome".

Expanded "Why this score?" (verbatim):
> "Review trigger: triage score 0.75 crossed the 0.66 review threshold.
> Strongest IOGP rule signals: Safe Mechanical Lifting (0.98).
> Report wording supporting those signals: "sling", "Crane", "Crane lifting operation with damaged sling over live equipment"."

**Verdict: verifiable, not a black box.** A skeptical officer sees the number, the threshold it crossed, the dominant rule, and the two words that drove it. Weaknesses: the third "signal" quotes the *entire report* — tautological padding; the decision buttons are hidden inside "Record review outcome"; and the metadata line is only "Moran · lifting" — **no date, no report ID, no contractor**.

### (b) Gray / uncertain — "Report mentions a drill or test" (triage-21)
> "● Manual review required
> **Report mentions a drill or test**
> Drill or exercise language detected — a rehearsal is not a precursor. Routed to review, never auto-cleared."

Full report text quoted (…mock drill conducted at Dumduma GGS on 25.08.2025… SCBA face strap found loose…). Metadata "Dumduma · emergency drill · 2026-09-25". Confirm/Not-SIF buttons directly visible. **No score, no rule bars, no highlighted trigger words.**

**Verdict:** the rationale is honest and plain-language (good), but (1) the trigger words aren't marked — the officer must re-read the text to find "drill"; (2) with no score shown you cannot tell whether the model even scored it; (3) the text's own date (25.08.2025) contradicts the card date (2026-09-25) with no explanation — the displayed date is not the incident date.

### (c) Low-score clear — "LOTO not applied", triage score 0.07 (triage-22, -24)
Green "Low review priority" / "No review needed" band; rules Working at Height 0.01, Energy Isolation 0.01, Safe Mechanical Lifting 0.00 (near-invisible bar stubs). Expanded "Why this score?" (verbatim):
> "Triage score 0.07 is below the 0.66 review threshold.
> No IOGP rule crossed its display threshold.
> Report wording supporting those signals: "LOTO", "LOTO not applied"."

**Verdict: the reasoning chain is visible — and it is exactly what makes this card alarming.** The machine acknowledges the word "LOTO" on screen and simultaneously files the report as green/never-review. "LOTO not applied" is a textbook energy-isolation precursor; the UI's loudest element is a confident green heading, while the countersignal (Energy Isolation 0.01) is a dot on an empty track. Whether the score is wrong is a model/data question — but visually the UI presents this as settled, and the only escalation path is buried in "Record review outcome".

## 4. The explanation expander, timed (Q5, ollama down)

- First expansion (Moran card): click-to-rendered **≈1.3 s** wall time (includes tooling overhead; the network log shows `GET /api/reports/5054/explanation → 200` inside it).
- Second expansion (freshly classified card): explanation text present **0.26 s** after click.
- **The predicted multi-second ollama stall did not occur in this session** — the deterministic template arrived fast both times, and no skeleton/spinner more than a flash was visible. What the user sees during the wait: nothing — no progress affordance on the expander itself. If ollama is slower on another day, the user gets a silent collapsed chevron with no "working…" cue. That is the gap to fix regardless of the stall.

## 5. Evidence-span highlighting (Q6)

`span-highlight` = bg `rgb(239,233,220)` on a white card, text `rgb(32,34,38)`, weight 500, no underline (computed styles). Device-scale zoom (triage-18): "**Crane** lifting operation with damaged **sling** over live equipment".

- Legible when you look: yes. **Noticeable at scan speed: no.** ~1.1:1 background tint against white, half a weight step, and the surrounding card shouts orange/green — the eye lands on the verdict, not the words.
- **Worse: freshly classified reports render zero spans.** The Classify result card (triage-30, score 0.95, "Working at Height 1.00") has `highlights: 0` in its blockquote, while every indexed card highlights spans. The evidence mechanism silently doesn't apply to the live flow.
- Two-word quotes in the explanation usually match the on-text spans ("torch" ×2 on the near-dup card — consistent), but the template also pads with whole-sentence quotes that correspond to nothing visibly marked.

## 6. Near-dup / "Duplicates" badges (Q7)

Queue reality check: in the 148-row Priority queue, **12 of the first 17 rows carry an orange "Duplicates" badge** — at that density it stops being a flag and becomes wallpaper (triage-14). On the card itself (triage-31), the annotation is a two-line beige callout:

> "**Matches a training record — memory, not generalization**"
> `near-dup banner: cosine=1.000 with index row syn-cs-e-0188 (>= 0.91)`

First line: genuinely good framing — keep it. Second line: **raw debug text on a reviewer screen** — an HSE officer has no idea what `syn-cs-e-0188` is, and `cosine=1.000` invites "so it's an exact copy, does it matter?". The explanation block repeats it: "Advisory gates: near_dup (…)". Internal identifiers must not leak into the reviewer surface.

## 7. Keyboard accessibility (Q8)

Programmatic + real-key walk (14+ stops), verified refs:
- **Skip link**: first focusable in DOM, appears as a dark "Skip to content" pill on focus (visible in triage-17) and jumps to `#main-content`. ✅
- Tab order: chips → queue cards → "Technical detail"/"Record review outcome" `<summary>`s → footer legend → wrap → EN → हिं → tabs → textarea → search → chips… All reachable.
- **Decision buttons reachable via keyboard**: focus `<summary>` → Enter opens `<details>` (`open: false→true`) → Tab lands on "Confirm SIF-potential", then "Not SIF-potential", with a **visible dark ring** (triage-26; computed `outline none 3px` but a rendered ring — the ring comes from another property; it is visibly there).
- Focus rings: chips/cards/summaries get the browser default `auto 1px`; header buttons a custom `solid 2px`. All visible.
- Minor quirk: the walk passes through `BODY` between sections (a focus gap, no functional failure observed). Arrow-key behavior on the tablist was not tested.

**Verdict: keyboard support is genuinely good.** The task is operable end-to-end without a mouse.

## 8. EN → हिं toggle (Q9)

Toggled; full Triage captured in Hindi (triage-29): "कार्य कतार", "उच्च समीक्षा प्राथमिकता", "यह स्कोर क्यों?", "समीक्षा परिणाम दर्ज करें", "SIF-क्षमता की पुष्टि करें / SIF-क्षमता नहीं", footer "मॉडल प्रस्तावित करता है — HSE निर्णयन करता है।…".

- **Devanagari renders correctly** — proper matras and conjuncts (क्ष, त्र), no tofu, no Latin-substitute garble. Computed font stack is `"IBM Plex Sans", system-ui, …` — Plex has no Devanagari, so glyphs come from an OS fallback (Noto-style). Visually confirmed: correct, but stylistically mismatched (serif-ish Devanagari next to Plex Latin) — a redesign should ship a real Devanagari face for brand consistency.
- Scope caveat: UI chrome is translated; report content, rule names (Safe Mechanical Lifting…), site names stay English. Acceptable for domain terms, but the split is visible.
- Toggled back to EN afterwards. Toggled-back state verified (`h1` = "Safety Report Triage").

## 9. Classify flow (timed, Q5-adjacent)

Filled the textarea with a synthetic near-miss, clicked Classify: **result rendered sub-second** (Working at Height 1.00 → score 0.95, "High review priority"). No stall, no spinner beyond a flash. Side effects: the report was **added to the queue** (Priority 148→149, All reports 200→201) with the raw text prefix as its title, no category line, **zero evidence spans**, and it re-sorted to the top of the queue. That's presumably intended ("your decision becomes a training label") but there is no confirmation or "test mode" distinction.

## 10. Prior audit claims — on-screen confirmation status

| Claim | Verdict | Evidence |
|---|---|---|
| 200-row client cap; most of 5,056 unreachable | **CONFIRMED** | Header "5,056 reports indexed" vs queue counter "x/200"/"x/201", chip "All reports 200"; network `GET /api/reports?limit=200`. 4,855 reports have no UI path. |
| Queue ordered by recency, not risk | **PARTIALLY REFUTED / opaque** | Dates visibly out of order (2025-06-12 above 2026-09-25 rows; 2025-10-22 mid-list) → not pure recency; but rows show **no scores**, so risk-ordering is unverifiable on screen. Ordering rationale is invisible either way. |
| Three disagreeing thresholds (0.7/0.4 client vs ~0.66 server) | **PARTIALLY CONFIRMED** | 0.66 is stated verbatim in every explanation ("crossed the 0.66 review threshold"); no 0.7/0.4 appears anywhere on the Triage surface — band boundaries other than 0.66 are invisible to users. |
| Card omits report date/contractor/id | **CONFIRMED (inconsistently)** | No report ID or contractor anywhere; date present on gray route cards ("Dumduma · emergency drill · 2026-09-25") but absent on scored cards ("Moran · lifting"). Text-internal dates (25.08.2025, 03.02.2025) contradict displayed dates. |
| Confirm/Not-SIF has no undo, no rationale | **CONFIRMED — worse** | Two equal-weight buttons only. The decided card shows just "● Reviewed by HSE" — not *which* decision, no who/when, no undo (triage-25). |

## 11. Defect list

Severity: **blocker** = blocks the core review workflow; **major** = materially hurts a real reviewer; **minor** = polish.

1. **BLOCKER — 4,855 of 5,056 reports are unreachable.** Client fetches `?limit=200`; every chip/counter caps at 200 while the header advertises 5,056. A reviewer triaging "all of last quarter" is silently reading a 4% sample.
2. **MAJOR — Decision capture is a dead end.** No rationale field, no undo, and the decided card doesn't even record *which* way it went ("Reviewed by HSE" only). The "training label" the footer promises cannot be reconstructed from the UI.
3. **MAJOR — Debug text on the reviewer surface.** `near-dup banner: cosine=1.000 with index row syn-cs-e-0188 (>= 0.91)` on cards and `Advisory gates: near_dup (…)` in explanations. jargon + internal row ids.
4. **MAJOR — A serious precursor is presented as confidently clear.** "LOTO not applied" → 0.07, green, Energy Isolation 0.01, while the explanation quotes "LOTO" as seen-but-dismissed wording. Even if the model is right, the UI gives the officer no visual counterweight (no amber "watch" affordance for acknowledged-but-below-threshold critical terms).
5. **MAJOR — Evidence spans are too quiet, and missing entirely on the live classify flow.** `#EFE9DC` on white, weight 500, no underline; 0 spans on freshly classified reports.
6. **MAJOR — Detail card metadata is inconsistent and incomplete.** Date on route cards only; no ID/contractor anywhere; displayed date can contradict the incident date inside the text.
7. **MAJOR — Decision actions are buried for scored cards** (inside collapsed "Record review outcome") but exposed for route cards — inconsistent, and the extra click is on the most consequential action.
8. **MAJOR — Search ignores report body text.** "LOTO" → 0 results while a loaded card's body is "LOTO not applied"; title/site/category only.
9. **MAJOR (with caveat) — Viewport resize flips the active tab to Insights and perturbs counts** (observed 10 → 3 → 10 during re-sync; flip observed twice). Caveat: a concurrent session was driving the same browser; treat the count-flicker as provisional and the flip as reproducible-in-this-session.
10. **MINOR — Queue gives no ordering rationale.** No scores per row; dates out of chronological order; "Work from the top" implies priority the list doesn't show.
11. **MINOR — Mobile 390px tab bar clips "Decision hist…".**
12. **MINOR — No loading affordance on "Why this score?"** (silent chevron; only mattered because ollama stalled *less than predicted* — 0.26–1.3 s observed).
13. **MINOR — Explanation template pads with whole-report quotes**, diluting the two genuinely informative span quotes.
14. **MINOR — Classify silently persists a new queue row** (no test-mode/confirm step; title is raw text prefix).
15. **MINOR — Near-zero rule values render as a dot on a full-width track**; the bar channel carries no information below ~0.05.
16. **MINOR — Selection resets to the first card on filter change** (context loss mid-review).
17. **MINOR (adjacent, Insights) — "100.0per 100" missing space** in the flag-rate column; 341-row table mobile columns clipped.

## 12. What works — preserve these

- **"Why this score?" names numbers, not vibes**: score, the exact 0.66 threshold, strongest rule + value, quoted trigger words. This is the right transparency skeleton; build on it (add band boundaries and the counterweight for critical terms).
- **Route cards explain themselves in plain language** ("a rehearsal is not a precursor", "never auto-cleared", "Serious-event language, low score — the model may have missed it"). The footer legend documenting all eight routes is excellent; consider surfacing it nearer the queue.
- **"Matches a training record — memory, not generalization"** — the single best sentence in the product. Keep; delete only the debug line under it.
- **Warm paper theme, quiet chrome, strong typographic hierarchy** for the verdict heading; chips with live counts; search with clear button + live counter; honest footer labels.
- **Keyboard & a11y foundation**: skip link first, native `<details>/<summary>`, real buttons everywhere, visible rings, decision buttons operable.
- **हिं toggle works end-to-end**; Devanagari renders cleanly via fallback.
- **Evidence-span mechanism on indexed cards** matches the quoted spans in the explanation — the pipeline exists; it needs salience and coverage of the live flow.

## 13. Unreached / not verified

- The predicted multi-second ollama stall (did not occur this session; twice-fast deterministic fallback observed instead).
- Arrow-key tablist semantics; screen-reader announcement quality (only structural roles verified).
- Whether search is server-side or client-side over the 200 (behavior consistent with client-side over loaded rows).
- Anything beyond the Triage tab (Insights/Decision-history defects noted only where they crossed my screen).
