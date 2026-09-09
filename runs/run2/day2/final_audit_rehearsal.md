# FINAL AUDIT — DEMO REHEARSAL (Phase 3, fresh-eyes swarm)

**Lens:** demo-rehearsal auditor. **Date:** 2026-09-09, ~14:00–15:30 IST. **Stack audited:** LIVE `:8177` (masked-v2 int8, `1d46ccadcba3`, 5,048 seeded reports) — verified `GET /api/health` before and after: `n_reports=5048, n_overrides=0` (unchanged; all live-stack probes used the stateless `/api/classify` path). Mutating ingest/override beats were executed on a **throwaway copy on :8191** (`SIF_DB_PATH=/tmp/audit8191.db`, sqlite `.backup` snapshot), torn down after. Ports 8001–8004 and `artifacts/gold/labels*/` never touched. Browser: Playwright MCP @ 1920×1080 (chrome-devtools MCP broken on this machine — configured chromium-1234 binary missing, only chromium-1243 installed; **fix the MCP config before Day-3 recording runs**).

---

## VERDICT SUMMARY

Every **live-classify beat passes with margin** (contrast pair, gray gates, WC tag, language gate, near-dup banner, encores). But the **money beat (script beats 5–6) cannot be executed as written on the seeded DB**, the **explanation cache serving all 13 demo cards contains a raw Python AttributeError**, and the **CPU power clamp has RETURNED** (all cores pinned ≤0.86 GHz under load again). All three are fixable tonight; none are self-healing. Details with repro below.

---

## SEV1 FINDINGS

### F1 — CPU clamp is BACK (script hard-rule #2 violated if latency is quoted)

Repro (today, on AC mains, battery 97%, Tctl 40 °C, governor `performance`, boost=1):
- 8-thread 5 s burn: **all 16 logical cores pinned 0.60–0.86 GHz** (exact pre-fix signature from `CPU_CLAMP_REPORT.md`: platform limit, not thermal).
- `POST /api/classify` contrast-red ×5: **153–209 ms** server wall (yesterday, unclamped: 48–56 ms on the same cards).
- Yesterday's "RESOLVED" (KB §8) did not survive the night. `ACAD online=1` today, yet clamped — both `ucsi-source-psy` entries show odd state (one "Charging", one "Discharging"); per the clamp report's recurrence checklist, **check the AC source/wattage first**.
- Impact: card latency readouts today show 91–450 ms (vs 30–53 ms yesterday); `long-report` 1.06 s. Still inside every beat window (max beat budget 9–12 s), so the 90 s is NOT at risk from speed; the risk is the CLOSE beat's "local latency" number and any judge-requested live benchmark. **Morning-of demo: run the clamp-report one-liner health check as step 0 of the boot checklist; re-measure the 4 metrics-slide numbers if unclamped; otherwise the slide must keep the precomputed (unclamped, dated) numbers and the presenter must not quote live latency.**

### F2 — Money beat is unexecutable as scripted on the seeded DB

The script (beats 5–6) says: *drag `bulk_ingest_5k.csv` onto the upload zone → progress replay → density view → FLIP re-rank → "Kathalguri GCS was #2 with 31 reports, now #1, ninety-six flagged."* Verified against code + live UI:

1. **There is no upload zone.** No `type="file"`/`onDrop`/drag affordance anywhere in `dashboard/src` (grepped). The only ingest affordance is the **"Simulate ingest → re-rank" button on the Density tab**, which POSTs a **hardcoded 6-row Baghjan-EPS batch** (`dashboard/src/views/density.tsx:24-63`) — not the 5,050-row CSV. The 5k CSV was ingested by curl at seed time (135 s); there is no UI path for it, and 135 s (≈250 s+ clamped) cannot fit the scripted 13 s beat anyway.
2. **Kathalguri is ALREADY #1** (pre-seeded post-state): `#1 Kathalguri GCS 213/213, rate 100.0, mean 0.96` — matches `demo_final_state.md` §1 exactly. The scripted "#2 → #1, 31 → 96" cannot happen; **the number 96 appears on no screen** (site table: 213; Patterns site×activity cell "DG exhaust duct inspection × Kathalguri GCS": **31 reports** — the pattern artifact is precomputed and does not include the ingested CSV rows).
3. **What the scripted click actually does now** (executed on throwaway :8191): native confirm dialog — *"Ingest the 6-report Baghjan demo batch into the LIVE database? The API dedups exact repeats — this runs once per session."* → progress bar (~2 s) → `accepted 6/6` → header ticks 5048→5054 → button disables, label becomes **"Batch ingested — re-ranked"** → **Δ rank 0 on every row, no FLIP animation, no "just climbed to #1" line** (Kathalguri untouchable at rate 1.0; Baghjan EPS 276→282 reports, stays ~#59 at 98.2%). On reload the button re-enables; a second accept hits the payload-hash replay (`POST /api/ingest` 200, **0 new rows stored** — idempotency verified: n stayed 5054 across two POSTs).
4. **The script's fallback assets don't exist.** `demo_pre.db` / `demo_post.db` are referenced in the script header and beat-6 fallback ("swap to `demo_post.db`") — **neither file exists anywhere in the repo** (`find` clean). The current `app/runtime.db` IS the post-state; there is no pre-state snapshot to boot from.

**Decision required tonight (rehearsal procedure):**
- **Option A — present pre-seeded (recommended):** boot the current DB; beats 5–6 become "the register is already in" narration over the live Density tab; the 6-row button click is optional and shows a real ingest + honest `accepted 6/6` (but no re-rank — do NOT promise motion). Presenter line: *"#1 Kathalguri GCS — 213 reports, 213 flagged, every one a confined-space near miss from the DG exhaust-duct cell. That is where your next inspection goes."* (213 is the on-screen number; never say 96.) The FLIP/re-rank animation then lives only in the Day-3 recording, not the live run.
- **Option B — rebuild a pre-state DB** (Kathalguri #2/31, CSV not yet ingested) + a working bulk-upload UI or API-driven backstage swap: this is new code + a re-seed tonight; the 135 s ingest still can't run live in a 13 s beat. Not recommended at T-19 h.
- Either way: **strike the drag-and-drop beat from the script, strike the 31→96 numbers, and either produce `demo_pre.db`/`demo_post.db` or delete the fallback lines that reference them.**

### F3 — Explanation cache poisoned: raw AttributeError on every demo card's "Why this score?"

Repro: paste `contrast-red` → click **"Why this score?"** → the LLM-reworded paragraph reads: *"…with an advisory gate error noted as near_dup (gate error: AttributeError: '_NullStorage' object has no attribute 'nearest_base_batch')"*. Same text in the template fallback paragraph below it.

- Scope: **63/63 rows** of the `precomputed` table in `app/runtime.db` (the 13 demo cards + top-50 feed reports — i.e., exactly the cards a judge will click) contain the string in BOTH `template` and `reworded` payload fields.
- Root cause: the precompute run executed the gate pipeline without storage attached; `app/gates.py:303` converted the exception into a `detail` string, which flowed into the template and the LLM reword. `demo_final_state.md` §3 verified "63/63, 0 errors; spans exact" but never grepped the payload text — the poison passed review.
- The **live uncached path is clean** (probed `POST /api/classify?explain=1` on a fresh text → template-only, no error text). So the fix is cheap: **re-run `artifacts/explanations/precompute.py` against the live stack with storage attached (or purge the 63 rows and let them re-cache), then grep the `precomputed` table for `gate error` as the acceptance check.** Until then, do not click "Why this score?" within judge sight; the passive card label is safe.

---

## SEV2 FINDINGS

### F4 — Override buttons 404 silently on live-paste cards (breaks the "judge's own report" encore if clicked)

Repro (throwaway :8191): paste any card → click **"Not SIF-potential"** → `POST /api/review` → **404 Not Found** (console error only; the card shows no toast, no state change — the presenter cannot tell it failed). Ad-hoc pastes have no persisted report id, so the review POST has nothing to attach to. On a **persisted feed report** the round-trip is fully green: click feed #5048 → "Not SIF-potential" → **201**, Review tab logs `#5048 | sif_label | HIGH → not_sif_potential | hse_reviewer | <timestamp>` under "Logged overrides — overrides → future gold labels"; clicking "Confirm SIF-potential" flips it back (201, latest-wins). Script fix: in the judge's-own-report encore, **never click the override buttons on the pasted card** — if a judge asks "and then what?", open the same text's nearest feed row or say the disposition lands once the report is ingested. (Also note: the card's band does not change after override — by design, "model proposes, HSE disposes"; the disposition lives in the Review log. Don't narrate the card changing.)

### F5 — Scripted words that will mismatch the screen (all verified live)

| Script says | Screen shows | Fix |
|---|---|---|
| Beat 1: "shows you exactly why, in the report's own words" + spans on "fell past the drill floor" / "near two roughnecks" | contrast-red HIGH 0.93, LoF 0.85 — **zero highlighted spans** (`<mark>` count 0; span head dead → keyword fallback → frozen spec excludes "fell"/"dropped"; §5-O1 known but script never updated) | Re-narrate: point at the **rule bar** ("Line of Fire 0.85") as the "why", or adjudicate adding a falling-object keyword family to the frozen spec |
| Beat 3: "routed out of the queue" | Card + legend copy: "**Routed to review**, never auto-cleared" (gates route INTO the human queue) | Say "routed to a human, never auto-cleared" |
| Beat 7 banner copy: "matches an ingested record — memory, not generalization"; corpus: "banner names the matched report id" | Actual banner: "**Matches a training record** — memory, not generalization", detail "cosine=1.000 with **index row 2399** (≥ 0.91)" (an index offset, not a report id) | Quote the screen verbatim; if saying "the file we just ingested", note the row is also in the training index |
| Beat 4: "flash `hinglish` card (precomputed tile on the feed, one click)" | **No hinglish tile exists** (0 Devanagari rows in the 5,048-row DB — verified via SQL) | Paste it live (verified: GRAY language gate + "translation available" chip, Devanagari preserved, ~1 s) or use screenshot `final_08_hinglish.png` |
| Beat 5 pattern card: "Line of Fire × drill floor × missing barricade, 14 reports in 30 days" | No such card in either Patterns view. Real #1 site×activity: "**derrick/mast climbing × Workover Rig #7 — 37 reports, rate 100/100, lift 1.5×, CI [0.91, 1.00]**"; money-relevant #2: "DG exhaust duct inspection × Kathalguri GCS — **31 reports**, CI [0.89, 1.00]" | Quote a real card; note every visible card reads rate 100 / lift 1.5× — a sharp judge may ask why they're all identical; have the mining-method answer ready |
| Script header: "dashboard pinned to `http://127.0.0.1:5173`" | Live stack serves same-origin on **`http://127.0.0.1:8177`** (D26 rebuild); nothing listens on 5173 | Update checklist |
| Encore `mega-report`: "all 7 in-scope rule bars" | HIGH 0.98 but **3/7 bars elevated** (HW 0.62, SML 0.58, EI 0.35; LoF 0.22, CS 0.07, WaH 0.05, Driving 0.00); no CHUNKED badge (119 words < 120-word gate — `demo_final_state`'s "CHUNKED fires" claim is stale) | Narrate the probability bars honestly ("three rules strongly elevated") + PTW/Bypassing greyed out-of-scope chips |
| Encore `codes-only` (demo_corpus expects GRAY, "EI keyword tag", "routed to review as terse/low-information") | Plain **LOW 0.07** card, "no action needed", `LOTO` span highlighted; codes-path accept exists only as an API gate detail ("short report accepted via codes path: LOTO"), no visible badge | Re-annotate the card: LOW + LOTO highlight is the win ("a naive validator throws this away; ours scores it") — do not claim review routing |
| contrast-red card | Shows a **WELL-CONTROL / BARRIER TAG** the script never mentions ("BOP deck" keyword; §5-O2 cosmetic over-tag) | One-line disclaimer if a judge asks: deterministic keyword tag, defensible on this text |

---

## BEAT-BY-BEAT VERIFIED RESULTS (live :8177 unless noted)

| Beat | Card / action | Expected (script/corpus) | OBSERVED (evidence) | Time | Verdict |
|---|---|---|---|---|---|
| 0:07 RED | paste `contrast-red` | HIGH, LoF dominant, spans | **HIGH 0.93, LoF 0.85**, WC tag present, **0 spans**, no gray, no banner | card 323 ms | PASS w/ F5 span + WC narration fixes |
| 0:19 GREEN | paste `contrast-green` | LOW clean | **LOW 0.01**, "no action needed", all rule bars 0.01, no gray/banner/spans | card 244 ms | PASS — contrast lands (0.93 vs 0.01) |
| 0:28 GRAY×2 | `gray-negation` | Sentinel negation gray | **SENTINEL GATE — Negation guard**, "'no'~'injury' within 5 tokens" | — | PASS |
| | `gray-drill` | Sentinel drill gray | **SENTINEL GATE — Drill/simulation** ("drill badge: mock drill") | API 281 ms, render 420 ms | PASS |
| 0:38 WC | `wc-baghjan-1` | HIGH + CS bar + WC tag | **HIGH 0.90, Confined Space 0.94, WELL-CONTROL tag** | API 391 ms (card 238 ms) | PASS |
| 0:47 हिं | `hinglish` | language gray + translation chip, verbatim text | **SENTINEL GATE — Language gate + "translation available" chip**, `language badge [devanagari]: non_ascii_ratio=0.16 (> 0.15)` | API 754 ms | PASS (paste live; no feed tile — F5) |
| 0:47 UNPLUG | pull ethernet, refresh | zero external requests | Full reload: **15/15 requests same-origin 127.0.0.1:8177** (HTML/JS/CSS/vendored IBM Plex woff2/API) — nothing external | reload <1 s | PASS — beat cannot lose |
| 0:53 BULK | drag 5k CSV → replay | upload zone + progress | **No upload UI exists**; only 6-row button (dialog → `accepted 6/6` → +6 rows → button disables "Batch ingested — re-ranked") | ~2 s bar | **FAIL as scripted — F2** |
| 1:06 RE-RANK | Kathalguri #2(31)→#1(96), FLIP | climb animation | Kathalguri **already #1, 213/213**; after click: **Δ rank 0 everywhere, no FLIP, no "climbed" line** (throwaway-verified) | — | **FAIL as scripted — F2** |
| 1:15 NEAR-DUP | paste `verbatim-osha` | banner "memory, not generalization" | **HIGH 1.00 + banner: "Matches a training record — memory, not generalization", cosine=1.000 vs index row 2399** | API 703 ms (card 450 ms) | PASS w/ wording fix (F5) |
| — OVERRIDE | Confirm/Not-SIF round-trip | review log entry | Feed report: **201 both directions, logged** in Review ("Logged overrides — overrides → future gold labels"); live-paste card: **404 silent** (F4) | ~175 ms | PASS on feed reports only |
| — हिं TOGGLE | EN/हिं phrasebook | chrome flips, text untouched | Header/tabs/labels flip (SIF-पूर्वसंकेत पहचान इंजन / फ़ीड / घनत्व / पैटर्न / समीक्षा); band names stay EN; report text never translated; toggles back clean | instant | PASS |
| Encore | `codes-only` | (corpus: GRAY) | **LOW 0.07**, `LOTO` span highlighted, codes-path accept in API gate detail | API 194 ms | PASS — annotation stale (F5) |
| Encore | `first-aid-green` | LOW | **LOW 0.26**, no gates, no spans (D21 fix holds) | API 310 ms | PASS |
| Encore | `long-report` | HIGH + chunked badge | **HIGH 0.75, long_input gate: "chunked: 376 words > 120; sliding-window max-pool"**, LoF 0.66, near-dup max 0.747 (no banner) | API 1059 ms | PASS |
| Encore | `mega-report` | HIGH + 7 bars | **HIGH 0.98, 3/7 bars elevated, WC tag, span `sling`, no CHUNKED badge** | API 502 ms | PASS w/ honest-line narration (F5) |
| — PATTERNS | pattern card w/ CI | scripted LoF card | Scripted card absent; real top cards verified w/ n + Wilson CIs | — | PASS w/ re-quote (F5) |

**Timing read:** even clamped, the slowest 90 s-path interaction is 0.75 s (hinglish) and the slowest encore is 1.06 s (long-report). Beat pacing is not at risk; quoted latency numbers are (F1).

---

## REQUIRED TONIGHT (before T-2h rehearsal gate)

1. **F3:** re-run/scrub the explanation precompute; acceptance = `SELECT COUNT(*) FROM precomputed WHERE payload LIKE '%gate error%'` → 0, plus one browser click-through of "Why this score?" on contrast-red.
2. **F2:** pick Option A (re-narrate, recommended) or B (rebuild pre-state); rewrite beats 5–6 accordingly; delete or produce `demo_pre.db`/`demo_post.db`; strike the drag-and-drop and 31→96 lines; presenter says **213/213**.
3. **F5:** apply the script wording table (spans, banner copy, hinglish tile, pattern card, mega/codes encores, port 8177).
4. **F4:** add "never click override on a pasted card" to the encore hard rules.
5. **F1 (morning-of):** clamp health-check one-liner as boot step 0; re-measure slide numbers if unclamped; check AC adapter wattage per `CPU_CLAMP_REPORT.md` recurrence checklist.
6. Fix the chrome-devtools MCP browser path (chromium-1234 → 1243) or plan the Day-3 recording on Playwright MCP.

## What is SOLID (no action)

Unplug beat (zero external requests, vendored fonts), both gray gates, language gate, near-dup banner, contrast pair, WC tag, Hindi toggle, override round-trip on feed reports, ingest idempotency (dialog + session disable + payload-hash replay + per-row dedup), live classify path on all 13 cards, and the live explanation path (uncached) — all reproduced with evidence above.
