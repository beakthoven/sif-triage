# FINAL E2E REHEARSAL PASS — ship-v1.0 (product-pass UI, post-16:45 build)

**Date:** 2026-09-10 ~11:24–11:40 UTC · **Auditor:** final validation swarm, agent 5 (E2E rehearsal)
**Method:** Playwright MCP, real Chromium, 1920×1080 @100%, against live stack `http://127.0.0.1:8177` (masked-v2 int8, pre-state 4,548 reports, Kathalguri #2). Full user-path clicks/types/dialogs — no API shortcutting except post-hoc verification. All traffic logged via network panel.

## Verdict: PASS — the complete 90-second flow works end-to-end on the current build, every beat lands as scripted, copy is the new plain-language version, and the pre-state restores cleanly (byte-identical screenshot).

## Beat table

| # | Beat | Expected | Observed | Result | Screenshot |
|---|------|----------|----------|--------|-----------|
| 1 | Idle feed | Queue + detail card, calm UI | "Report queue · 9", amber/slate priority chips, Sentinel gate list rendered | PASS | `final_rehearsal_01_feed.png` |
| 2 | Paste contrast-green | LOW | "no action needed", triage score 0.01, all rule bars 0.01, no flag | PASS | `final_rehearsal_02_paste_green_low.png` |
| 3 | Paste contrast-red | HIGH, LoF bar, WC chip | "High review priority" 0.93, **Line of Fire 0.85 dominant** (WaH/SML 0.01), **"Well-control / barrier tag" chip present**, "Flagged for HSE review" | PASS — matches script verbatim | `final_rehearsal_03_paste_red_high.png` |
| 4 | Density tab (pre) | Moran #1 / Kathalguri #2 | #1 Moran GGS-1 98/98, #2 Kathalguri GCS 88/88, Δ rank column present | PASS | `final_rehearsal_04_density_before.png` |
| 5 | Ingest button + confirm | Dialog, then real ingest | Plain dialog: "Ingest the 500-report demo batch? Real classification, about 15 seconds. This runs once per session." → accepted → "accepted 500/500" | PASS | (in #6) |
| 6 | Money beat re-rank | Kathalguri #2→#1 | **#1 Kathalguri GCS 213/213, +1 chip; Moran GGS-1 105/105 → #2, −1 chip; "Kathalguri GCS just climbed to #1."**; button locks to "Batch ingested — re-ranked" [disabled] | PASS — exact script arithmetic | `final_rehearsal_05_density_reranked.png` |
| 7 | Paste verbatim-osha | Near-dup banner | Score 1.00, LoF 0.89, banner **"Matches a training record — memory, not generalization"** + detail "cosine=1.000 with index row 4798 (>= 0.91)" | PASS | `final_rehearsal_06_verbatim_neardup_banner.png` |
| 8 | Paste gray-drill | Gray gate card | "Needs human review" / **"Report mentions a drill or test"** / "…a rehearsal is not a precursor. Routed to review, never auto-cleared." Queue shows GATE chip | PASS | `final_rehearsal_07_drill_gray.png` |
| 9 | Explanation expander | "Why this score?" expands | Expands in place: "This report is flagged for HSE review with a triage score of 1.00. The implicated IOGP rule is Line of Fire (0.89)…" + attribution "phrased by local LLM · cached" | PASS | `final_rehearsal_08_explanation.png` |
| 10 | Patterns tab + toggle | Both pattern kinds | Site × Activity: #1 "derrick/mast climbing × Workover Rig #7" 37 reports, lift 1.5×, 95% CI [0.91, 1.00] (matches scripted narration). Toggle → Activity × Barrier: #1 "gas cutting abandoned flowline × LEL re-test not done after break" | PASS | `final_rehearsal_09_patterns.png`, `final_rehearsal_10_patterns_barrier.png` |
| 11 | Review tab | Gate queue visible | "Awaiting your review (9)" incl. the live drill paste at top; plain-language gate names throughout | PASS | `final_rehearsal_11_review.png` |
| 12 | Hindi toggle | UI chrome in Hindi, content untouched | Title "सुरक्षा रिपोर्ट ट्रायाज", tabs फ़ीड/घनत्व/पैटर्न/समीक्षा, "ऑनलाइन · 5,050 रिपोर्ट अनुक्रमित", "आपकी समीक्षा की प्रतीक्षा में (9)"; report bodies stay English (phrasebook-only, by design); EN toggle restores | PASS | `final_rehearsal_12_hindi.png` |
| 13 | Override on a feed report | Decision recorded + visible in Review | Clicked "Confirm SIF-potential" on feed row #5049 (tubing-rack OSHA row) → button goes active; Review tab gains **"(1)" badge**; "Logged overrides" table shows #5049, HIGH → sif_potential, hse_reviewer, timestamped. Server confirms `n_overrides: 1`, POST /api/review → 201 | PASS | `final_rehearsal_13_override_logged.png` |
| 14 | Restore pre-state | 4548 + Kathalguri #2 | `./run.sh --stop` → `cp artifacts/demo/demo_pre.db app/runtime.db` → `rm -f runtime.db-shm/-wal` → `./run.sh` → health: n_reports **4548**, n_overrides **0**; UI density: Moran #1 98/98, Kathalguri #2 88/88; ingest button re-armed | PASS — restored screenshot is **byte-identical** to beat-4 (both 137,494 B) | `final_rehearsal_14_restored_prestate.png` |

## Copy audit (all 4 tabs, full innerText sweep — `final_rehearsal_pagetext.json`)

Searched for: `onnx`, `ad-hoc`, `int8`, `fp32`, `logit`, `ModernBERT`, `MiniLM`, `embedding`, `AUC`, `quantiz`, `regex`, `calibrated`, `SIF_MODEL`, `.onnx`, `API`, `JSON`.

- **No `onnx:` strings visible anywhere in the UI.** (The token survives only in `GET /api/health` JSON `model_version` — an API field, never rendered.)
- **No "ad-hoc classify" meta.** The classify calls go out as `POST /api/classify?persist=1&explain=1&llm=0` — no live LLM in the demo path (hard rule 3 honored by the UI itself).
- **Gate names are all plain language:** "Very short report." / "Negation detected." / "Language not currently scored." / "Uncertain score." / "Report mentions a drill or test." / "Possible duplicate of a training record." / "Long report, scored in sections." / "Possible well-control concern." / "Long report with uncertain score." — each with a one-sentence plain-English explanation ending in the "never auto-cleared" doctrine line.
- Confirm dialog, ingest completion ("accepted 500/500 · Kathalguri GCS just climbed to #1."), and footer ("Model proposes, HSE disposes. …", "demo data: synthetic OIL-style reports") all clean.

### Residual jargon that still leaks (minor, all in small-print detail lines — none on stage-critical copy)

1. **Override table raw tokens** (Review tab): `Field: sif_label`, `Now: sif_potential` — snake_case machine names in the one table an HSE judge may read closely after the override beat. Suggest display-mapping to "Flag" / "SIF-potential".
2. **Gray-card detail line:** "negated outcome language (cue~outcome within 5 tokens): 'no'~'damage'" — "cue~outcome within 5 tokens" is NLP jargon.
3. **Well-control watch line:** "barrier tag fired but triage score 0.019 < flag threshold 0.658" — numeric threshold comparison is technical (though arguably good Q&A ammo).
4. **Annotation prefixes:** "near-dup banner: …", "drill badge: mock drill" — internal component names used as label prefixes (the banner headline itself is the scripted plain sentence; only the small detail line carries the prefix).
5. **Cosmetic data nit (not UI copy):** post-ingest density table shows lowercase "workover rig #7" alongside title-case "Workover Rig #5" — inconsistent site casing inside the ingested CSV.

None of these appear in headlines, buttons, banners, gate names, or the money beat. Judges would have to read fine print in the Review tab to see #1–#4.

## Hygiene checks

- **Zero console errors/warnings** across the whole run.
- **Zero external network requests** — all 30 requests same-origin `127.0.0.1:8177` (vendored IBM Plex fonts, `/api/*`, static CSV). Offline doctrine holds.
- **No double-click of the ingest button** (hard rule 5); button self-disables after one run.
- Live paste behavior note: 4 pastes + 500 ingest raised n_reports 4548→5051 (verbatim-osha near-dup was not double-stored — consistent with hard rule 4's "already submitted" design).
- Paste latency: every classify visibly landed in under a second on this machine (unclamped), matching the "say under a second, quote no numbers" doctrine.

## Files

- Screenshots: `runs/run2/day3/final_rehearsal_01..14_*.png` (14 files, 1920×1080)
- Full-text sweep dump: `runs/run2/day3/final_rehearsal_pagetext.json`
- This report: `runs/run2/day3/final_rehearsal.md`
- DB restored to `artifacts/demo/demo_pre.db`; stack left RUNNING in pre-state on :8177.
