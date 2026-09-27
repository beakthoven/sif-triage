# 01 — Problem-Statement Verification: SIH 2026 PS 26165

**Role:** Official problem-statement verification (Phase 0 discovery, read-only).
**Date of verification:** 2026-09-25.
**Verifier:** Phase-0 subagent, assignment 01.

## Sources and files actually read

| Source | Detail |
|---|---|
| `data/sih2026_ps.csv` | 3,307 lines, 226 data rows, 14-column official-scrape snapshot. Header + full 26165 row parsed field-by-field with Python `csv`. |
| `data/software_ps.json` | 1,721 lines, 172 entries (software track). Entry 26165 = lines 1342–1351, read in full. |
| `HANDOFF.md` | 239 lines; lines 23, 78, 160–165 read (grep context). |
| `README.md` | 153 lines; line 3 + grep for theme/dataset claims. |
| `spec/label_spec.yaml` | Lines 1–6 (PS reference header). |
| `requirements.txt` | Lines 1–4 (PS reference header). |
| **Live sih.gov.in** | `https://www.sih.gov.in/sih2026PS` fetched 2026-09-25 — full PS list, 240 entries (s.no 1–240), 95,062 chars of extracted text. |
| **Mirror (labeled fallback)** | `https://sih2026.vuce.in/ps/SIH26165` — third-party mirror ("Vedant Chalke"), fetched for full description text because the sih.gov.in list page does not expose descriptions in text extraction. |

**Tools used:** Grep, Read, Bash (Python csv/json parsing), FetchURL (sih.gov.in ×2, vuce.in ×1), exa web search (×2). No files modified; no writes to the running server.

## What exists today (inventory of the verification surface)

**1. On-disk official snapshot — stale, but carries the verbatim description.**
`data/sih2026_ps.csv:2630` and `data/software_ps.json:1343-1351` both carry PS 26165 with identical 1,292-char description text (byte-identical; verified by programmatic comparison). The snapshot's metadata is frozen at an earlier scrape:

- theme `Miscellaneous` (`data/software_ps.json:1345`, `data/sih2026_ps.csv:2630` last field)
- ideas `0/500` (`data/software_ps.json:1348`)
- deadline "20 September 2026" (all 226 rows)
- 226 PS total, 172 software entries (verified exactly: 226 CSV rows, 172 JSON entries)
- `dataset` field = empty string (`data/software_ps.json:1350`); CSV `dataset link` column = empty
- `contact info` and `youtube link` fields also empty for 26165

**2. Live official portal — current, and it contradicts the snapshot in four fields.**
Extraction of the s.no 165 block from `https://www.sih.gov.in/sih2026PS` (fetched today):

```
             165
        Oil India Limited
        AI/NLP Engine to Detect Serious Injury & Fatality (SIF) Precursors in OIL's
        Unsafe-Act/Unsafe-Condition and Near-Miss Reports
            Software
            SIH26165
            64/500
            Smart Automation
            30 September 2026
```

Portal-wide deltas vs the local snapshot: **240** PSs live (was 226); **every** deadline now "30 September 2026" (was 20 September); raw theme tallies shifted — "Smart Automation" ×56 / "Miscellaneous" ×15 on the live page vs Smart Automation ×31 / Miscellaneous ×38 in the local CSV. OIL's sibling PSs 26120 (13/500), 26121 (14/500), 26122 (60/500) are all live-listed as Smart Automation too.

**3. Third-party mirrors — mutually inconsistent, all unofficial.**
`sih2026.vuce.in/ps/SIH26165` (description text matches the on-disk snapshot verbatim, with clean em/en dashes — proving the local file's `â€”`/`â€“` are local-save encoding damage, not portal content); its theme pages surfaced 26165 under *both* Smart Automation (55) and Miscellaneous (38) in search highlights (pages not fetched directly). GitHub mirror `NoBugNinja/Smart-India-Hackathon-SIH-2026-Problem-Statements` says Miscellaneous. Scribd catalogues say Smart Automation and invent a "Prize: ₹1,00,000 INR" line with no source.

## Verbatim official description text obtained

From `data/sih2026_ps.csv` row 26165 (description field, identical to `data/software_ps.json:1349`), quoted **exactly as stored on disk** — note the two mojibake artifacts (`â€”`, `â€“`), which are UTF-8-read-as-Latin-1 damage from the original save:

> • Background OIL collects large volumes of UA/UC observations, near-miss and incident reports through its HSSE platform but these are triaged manually after certain time intervals such as monthly, quarterly etc.However, Global best practice (DEKRA Martin & Black 2015; EEI SIF Precursor model; VelocityEHS 2024 PSIF classifier) has established that low-severity incidents do not share the same causes as fatalities â€” non-fatal US accidents fell 51% over 15 years while fatalities fell only 25.5%.Leading operators therefore separately flag the ~20â€“25% of reports carrying genuine fatal potential.
>
> Problem Description Build a prototype that ingests OIL's free-text safety reports and automatically a) Classifies each as SIF-potential vs non-SIF-potential b) Tags it to the relevant IOGP Life-Saving Rule (e.g., Energy Isolation, Hot Work,Confined Space, Line of Fire)
> c) Surfaces recurring precursor patterns (activity, location, barrier failure) via a dashboard.
>
> Expected Outcome/Solution A working AI/NLP with an interactive dashboard that ranks sites/activities by SIF-precursor density and auto-maps to Life-Saving Rules, enabling HSE to focus interventions where fatal potential is highest.
>
> Relevant Data Availability (if any)
> OIL's UA/UC observations, near-miss and incident reports.

The vuce.in mirror reproduces the same text with clean dashes ("—", "20–25%"), confirming the artifacts are local-only. The live sih.gov.in list page does **not** render description text in its HTML extraction, so the mirror + on-disk snapshot are the only full-text sources obtained; the two agree word-for-word.

## VERDICT table

| # | Fact under verification | Verdict | Source |
|---|---|---|---|
| 1 | Title = "AI/NLP Engine to Detect Serious Injury & Fatality (SIF) Precursors in OIL's Unsafe-Act/Unsafe-Condition and Near-Miss Reports" | **VERIFIED** (exact, 3 sources) | [sih.gov.in/sih2026PS](https://www.sih.gov.in/sih2026PS) s.no 165; `data/sih2026_ps.csv:2630`; `data/software_ps.json:1344` |
| 2 | PS id 26165 / SIH26165, s.no 165 | **VERIFIED** | Live portal s.no 165 → SIH26165; `data/software_ps.json:1343` |
| 3 | Organization = Oil India Limited (department also OIL) | **VERIFIED** | Live portal s.no 165; `data/software_ps.json:1346-1347` |
| 4 | Category = Software | **VERIFIED** | Live portal; `data/sih2026_ps.csv:2625` (row start); `data/software_ps.json` (all 172 entries are software-track) |
| 5 | Theme = **Smart Automation** | **VERIFIED against live sih.gov.in (2026-09-25)**. The project brief is right; the repo's own data is stale. | Live portal s.no 165 → "Smart Automation"; contradicts `data/software_ps.json:1345`, `data/sih2026_ps.csv:2630`, `HANDOFF.md:23` ("Miscellaneous") |
| 6 | Core ask = auto-surface genuine SIF precursors from UA/UC + near-miss reports; classify SIF-potential; tag IOGP Life-Saving Rules; surface precursor patterns (activity, location, barrier failure); replace manual monthly/quarterly triage | **VERIFIED verbatim** (all elements present in official text) | `data/software_ps.json:1349`; [sih2026.vuce.in/ps/SIH26165](https://sih2026.vuce.in/ps/SIH26165) |
| 7 | Stated expected outcome/deliverable = "A working AI/NLP with an interactive dashboard that ranks sites/activities by SIF-precursor density and auto-maps to Life-Saving Rules, enabling HSE to focus interventions where fatal potential is highest." | **VERIFIED verbatim** | Same sources as #6 |
| 8 | "OIL provides NO dataset" | **CORRECTED** — imprecise as stated. The structured dataset-link field is empty everywhere (no downloadable dataset published), *but* the PS itself asserts data availability: "Relevant Data Availability (if any) OIL's UA/UC observations, near-miss and incident reports." Precise phrasing: *no dataset link published; OIL names its own reports as the relevant data but provides nothing concrete.* | `data/software_ps.json:1350` (`"dataset": ""`); `data/sih2026_ps.csv` row 26165 field `dataset link` = ""; description tail in `data/software_ps.json:1349` |
| 9 | HANDOFF.md:23 — theme "Miscellaneous" | **CORRECTED** (stale-snapshot value; live portal says Smart Automation) | Live portal; vs `HANDOFF.md:23` |
| 10 | HANDOFF.md:78 — "226 PS total / 172 software"; "26165's dataset link field is empty" | **CORRECTED.** True of the on-disk snapshot (exactly 226 CSV rows / 172 JSON entries — verified), but the live portal now enumerates **240** PSs, ideas count for 26165 is 64/500, and deadlines moved to 30 September 2026. The "dataset link empty" part is still true. | Live portal (240 blocks, all "30 September 2026"); `HANDOFF.md:78`; local counts verified programmatically |
| 11 | Live-portal idea-submission deadline for 26165 = **30 September 2026**; **64/500** ideas already submitted | **VERIFIED** (new fact, not in any repo file) | Live portal s.no 165 |
| 12 | Published SIH 2026 software-track evaluation criteria | **NOT VERIFIABLE.** sih.gov.in pages fetched (home + PS list) contain process flow only, no scoring rubric. Third-party rubrics exist and conflict: Scribd "Marking" doc (3 rounds, 20/30/50 weights), sihone.pages.dev playbook (5 pillars, 30/25/20/15/10), reskilll.com PPT rubric (5 weighted params) — all unofficial, none cross-consistent, none traceable to an official document. | [sih.gov.in/](https://www.sih.gov.in/) (no criteria found); Scribd doc/806781314; sihone.pages.dev/playbook; reskilll.com/blogs/sih-2026-ppt-template — all labeled **unofficial, unverified** |
| 13 | Live portal reachable | **VERIFIED — YES, fully reachable, no block.** Two sih.gov.in fetches and one mirror fetch all succeeded in seconds. | Fetched 2026-09-25 |

## Findings

**1. The repo's PS snapshot is stale in four load-bearing fields — theme, ideas count, deadline, and PS count. Severity: major.**
`HANDOFF.md:23` says "Theme: Miscellaneous" and `HANDOFF.md:78` says "226 PS total / 172 software" and "26165's `dataset link` field is empty". The first two were correct of the scrape on disk, but the live portal (fetched today) says: theme **Smart Automation**, 240 PSs, ideas 64/500, deadline 30 September 2026. The theme shift is corroborated en masse — live "Smart Automation" ×56 vs local ×31, live "Miscellaneous" ×15 vs local ×38 — i.e., SIH reshuffled themes across the board, and 26165 moved into Smart Automation. Why it matters: any deck or doc quoting "Miscellaneous" or "226 PS" invites a judge with the portal open to conclude the team didn't verify the problem statement it is solving. The brief under which this redesign runs has the theme right; the repo's own context file has it wrong.

**2. "OIL provides NO dataset" needs precise rephrasing before it reaches a slide. Severity: major.**
The PS does not say "no dataset". It ends with "Relevant Data Availability (if any) OIL's UA/UC observations, near-miss and incident reports." — an assertion that OIL's reports exist as relevant data, with the structured `dataset link` field left empty (`data/software_ps.json:1350`). Contrast with 26166 (ISRO), whose dataset-link field literally contains "Specific datasets link will be provided - TBD" (`data/sih2026_ps.csv:2631`) — an explicit promise of future data. 26165 makes no such promise, so "no downloadable dataset is published" is true; "OIL provides no data at all" is not, and a jury drawn from OIL will notice the difference. The repo's synthetic-corpus + public-proxy strategy is the right response, but the framing must be "OIL declares data availability; no link is published; we built on disclosed public/synthetic proxies" — not "OIL gave us nothing".

**3. The idea-submission deadline on the live portal is 30 September 2026 — five days from today. Severity: major (operational timing, informational only).**
Every row of the live list says "30 September 2026"; the local snapshot's "20 September 2026" is superseded. If idea submission via SPOC has not already happened for this team, the window is closing. Not verifiable from here whether this team's idea was already submitted (the repo shows no submission artifacts), so this is a flag for the orchestrator, not a claim.

**4. No official evaluation criteria are obtainable, and third-party rubrics actively contradict each other. Severity: major for finale prep.**
The two sih.gov.in pages I could fetch expose the participation process flow but no scoring weights. The competing unofficial claims (Scribd: rounds weighted 20/30/50; sihone.pages.dev: pillars 30/25/20/15/10; reskilll: PPT-level 20/25/20/20/15) cannot all be right. Consequence: the redesign docs must not claim alignment with "official SIH criteria" unless the orchestrator obtains an official rubric (e.g., from AICTE/SIH comms or the SPOC portal login, which I cannot access). Design for the universally-agreed axes instead: working demo, problem alignment, innovation, feasibility, impact.

**5. The PS text is thin on specifics — and the repo's honesty posture is the correct countermeasure. Severity: minor (context, not a defect).**
The official description names no data volume, no sample reports, no label definitions, and gives four example IOGP rules ("Energy Isolation, Hot Work, Confined Space, Line of Fire") as parenthetical examples only. The repo's approach — OSHA-sourced OIICS grounding, ASRS near-miss register with the disclosed ASRS recall 0.00, synthetic stratum reported separately at P 0.347, and two IOGP rules declared out of scope — is a defensible answer to a PS that guarantees nothing. Keep those disclosures; they read as diligence, not weakness.

**6. The on-disk description text carries mojibake and will leak into any quote taken from `data/sih2026_ps.csv`. Severity: minor.**
The snapshot's em/en dashes are stored as `â€”`/`â€“` (2 occurrences in the 26165 description; `â€™` appears across many other rows, e.g. `data/sih2026_ps.csv:385`). Anyone quoting the PS verbatim from the CSV into deck or dataset docs prints the damage. Quote from the mirror-verified clean text instead, or re-encode once.

**7. `contact info` and `youtube link` are empty for 26165 in the snapshot; the live list page exposes neither field. Severity: minor.**
No official explainer video or PS-owner contact is obtainable through my access. If the team wants direct OIL clarification (e.g., on data availability), the portal login/SPOC channel is the only route found.

## Pain points (where an HSSE reviewer or SIH judge loses trust)

- **Stale metadata in our own docs.** A judge cross-checking the portal sees Smart Automation / 64/500 / 30 Sep / 240 PSs while our HANDOFF says Miscellaneous / 0/500 / 20 Sep / 226. One mismatch is enough to plant "did they even read the PS?" doubt.
- **The data question is the trust frontier.** The PS asserts data availability but publishes nothing. Judges from OIL will ask: "What reports did you actually run on?" The answer must lead with the disclosed composition (OSHA OIICS 55.4% high-energy mapping, ASRS, synthetic) and the honest strata splits — not with the 5056-report SQLite demo, which contains no OIL data.
- **IOGP example rules.** The PS names four example rules in parentheses. Judges will look for them on the dashboard. Permit-to-Work / Bypassing-Safety-Controls being out of scope is a defensible disclosure, but the four named examples must be visibly covered.
- **"Working AI/NLP" is the deliverable bar.** The PS's expected outcome is a working engine + interactive dashboard that ranks sites/activities by SIF-precursor density and auto-maps to Life-Saving Rules. Any reviewer comparing this list against the app must find every clause: rank by site *and* activity (`/density?by=site|activity`), auto-map to rules, focus interventions. Anything unimplemented should be visible as scoped-out, not silent.

## Gaps vs production (verification-surface gaps)

- **No official PS-detail page fetch.** The sih.gov.in list page does not expose description text in extraction; full text came from the on-disk snapshot (verbatim, mojibake and all) cross-confirmed by an unofficial mirror. An official per-PS detail URL (the portal's JS modal) was not fetched — a logged-in browser session on sih.gov.in would close this.
- **No official evaluation rubric.** Third-party rubrics conflict; nothing authoritative obtained. Finale scoring strategy is currently calibrated against hearsay.
- **No confirmation of future OIL dataset release.** The snapshot's empty dataset-link field plus the contrast with ISRO's "TBD" row is the best evidence available; whether OIL will publish reports during SIH 2026 is unknown.
- **Snapshot provenance is undocumented.** Nothing in the repo records *when* or *how* `data/sih2026_ps.csv` / `software_ps.json` were scraped, which is exactly why the stale-theme bug survived undetected until now.

## Recommendation

- **KEEP** the on-disk PS snapshot (`data/sih2026_ps.csv`, `data/software_ps.json`) as provenance for the verbatim description — it is the only full-text source on disk and matches the mirror word-for-word.
- **UPDATE (orchestrator action; I did not edit it)** `HANDOFF.md:23` (theme → Smart Automation, per live portal) and `HANDOFF.md:78` (226→240 PSs live, ideas 64/500, deadline 30 Sep 2026, dataset-link-empty → "no dataset link published; PS asserts data availability"). One-line justification: our own context file currently asserts portal facts the portal has since changed.
- **REPLACE** the "OIL provides NO dataset" claim everywhere with: "No dataset link is published; the PS asserts OIL's UA/UC/near-miss reports as relevant data; the project trains on disclosed public/synthetic proxies." One-line justification: the current phrasing overstates the PS and invites a jury trap.
- **KEEP** the synthetic + OSHA + ASRS data doctrine and its stratum disclosures — it is the correct and defensible answer to a PS with no distributed dataset.
- **ADD** a one-page PS-alignment matrix to the finale deck: PS clause a) → `/classify` SIF head, b) → 7 IOGP rule heads (5 in scope, 2 declared out), c) → `/density` + `/patterns`, expected outcome → triage feed + review queue. One-line justification: the PS deliverable is enumerated clause-by-clause, so the mapping should be too.
- **MERGE** the verified live-portal facts (title, org, category, theme, deadline, ideas count) into the upcoming `docs/redesign-plan.md` as the single authoritative PS block, quoting the live-portal extraction above rather than the mojibake'd CSV.
- **ADD** to `docs/frontend-stack-decision.md` / deck planning: no official SIH 2026 evaluation criteria were verifiable; treat all published weightings as unofficial hearsay and optimize for demo quality + PS alignment + honest metrics instead.

## Portal reachability — plain statement

**The live portal IS reachable.** `https://www.sih.gov.in/sih2026PS` fetched successfully twice (95 KB extracted text, 240 PS entries, s.no 1–240, SIH26001–SIH26240, all deadlines "30 September 2026"); `https://sih.gov.in/` fetched successfully (process-flow page, no PS data, no criteria). No blocks, no captchas. The PS **description** text is not rendered in the list-page extraction, so the verbatim description was obtained from the on-disk official snapshot (`data/software_ps.json:1349`, quoted above) and confirmed word-for-word against the third-party mirror `sih2026.vuce.in/ps/SIH26165` (clearly labeled fallback). The single field the live portal shows for 26165 that the snapshot lacks currency on: theme (Smart Automation), ideas count (64/500), and deadline (30 September 2026) — quoted verbatim in the extraction block above.