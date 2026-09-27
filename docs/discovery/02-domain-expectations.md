# 02 — HSSE / Oil & Gas Domain Expectations (Phase 0 Discovery)

**Role:** HSSE / oil-and-gas domain-expectations researcher.
**Task:** establish what a real, decision-grade SIF-precursor intelligence tool for Oil India Limited (OIL) would be judged against, and grade today's shipped product against that bar.

## Files actually read (line counts)

Repo (read-only; nothing modified except this file):

| File | Read | Notes |
|---|---|---|
| `README.md` | full, 153 LoC | honest-claims table, claim boundary, Baghjan framing |
| `app/config.py` | full, 83 LoC | gray band, near-dup 0.91, short codes, Ollama settings |
| `app/gates.py` | partial: line-map of all gate functions (1-50, 107-423 via grep+read) | language/negation/confidence gates read in full |
| `app/routes.py` | partial, 402 LoC total | endpoints list, `/reports`, `/density`, `/review/export`, `/rules` |
| `app/schemas.py` | partial | `RULE_DISPLAY` block lines 27-48 (7 in-scope + 2 out-of-scope IOGP rules) |
| `app/classifier.py` | partial, 617 LoC total | rule-head ordering comments |
| `dashboard/package.json` | full, 35 LoC | dependency audit |
| `dashboard/src/lib/api.ts` | partial, 426 LoC total | `bandFor()` lines 129-131, mock fallback line 166 |
| `dashboard/src/lib/mock.ts` | grep | single Devanagari fixture lines 120-121 |
| `dashboard/src/views/insights.tsx` | full, 34 LoC | density+patterns merged tab |
| `dashboard/src/views/review.tsx` | full, 87 LoC | overrides table only |
| `dashboard/src/views/feed.tsx` | grep excerpts | filter model (decision/priority/reviewed/informational/all) |
| `dashboard/src/App.tsx` | grep | tabs triage / insights / decisions (lines 146-170) |
| `runs/run2/ARCHITECTURE.md` | grep excerpt | line 129 Baghjan framing |
| `spec/drafts/maps_draft.md` | grep excerpt | line 60 well-control/barrier tag |
| `tests/adversarial_suite.py` | grep excerpts | Baghjan narrative probes |

Live-stack probes (read-only HTTP GET, no writes, no restarts): `GET /api/metrics/summary`, `GET /api/density?by=site` on http://127.0.0.1:8177 — both succeeded.

Tools used: repo Read/Grep/Bash (`ls`, `wc`, read-only `curl`); web research via the Exa search/fetch MCP tools (10 searches; every search returned results; one exceeded inline size and was mined from its saved output file). No browser automation was needed; no fetch failed.

## What exists today (factual inventory of the domain surface)

- **Classification**: ModernBERT ONNX int8, 3 heads — binary SIF score, 7 in-scope IOGP Life-Saving Rule probabilities, evidence spans (`app/schemas.py:31-47`; out-of-scope: Work Authorisation/PTW and Bypassing Safety Controls, `app/schemas.py:38-47`). Plus a deterministic well-control/barrier tag (`spec/drafts/maps_draft.md:60`, `data_pipeline/oiics_maps.py:170`).
- **10 sentinel gates** with gray/badge/block semantics (`app/gates.py`); language gate grays any Devanagari or >15% non-ASCII text and explicitly never machine-translates (`app/gates.py:196-212`).
- **Persistence + analytics**: SQLite storage, near-dup MiniLM cosine index (0.91 threshold, `app/config.py:64-69`), density aggregate by site/activity/contractor only (`app/routes.py:263-273`), pattern mining with Wilson CIs (`app/routes.py:316+`).
- **Human-in-loop**: Confirm/Not-SIF overrides persisted, one NDJSON export of overrides for the ML pipeline (`app/routes.py:381-386`). Review tab is a read-only table of logged overrides (`dashboard/src/views/review.tsx:38-87`).
- **Live state** (probed 2026-09-25): 5,056 reports, flag rate **0.7095** (3,587 flagged), near_dup gate triggered on 3,021 of ~3,237 gate triggers, `sif_rate: 1.0` on every top density site.
- **No**: CAPA/action tracking, escalation, SLA timers, time dimension on any endpoint, CSV/regulatory export, auth/roles, chart library, router, server-side band. Band is client-side (`dashboard/src/lib/api.ts:129-131`).

## Findings

1. **The live flag rate (70.95%) destroys the triage value proposition the domain expects.** A SIF-precursor program exists to compress what a reviewer must read; the ORC 2011/Mercer BST study the README itself cites (`README.md:143-144`) found only **~20% of recordable injuries carry SIF potential** (EEI SIF guide, eei.org sifPrecursorGuide.pdf, Exhibit 1). The live stack flags 71% of its own corpus (`/api/metrics/summary`: `flag_rate:0.7095`), and every top-density site shows `sif_rate:1.0` — a density view where all sites are 100% flagged cannot rank risk, it only ranks volume. **Severity: major.** The corpus is synthetic, but the UI is tuned so that on OIL's real mixed traffic the reviewer saves ~29% of reading at best. A hostile reviewer will ask: "what fraction of the queue does this actually cut?"
2. **Hindi/Devanagari field text can never be triaged — only grayed.** `gate_language` routes any Devanagari (or >15% non-ASCII) report to the gray review queue and the code comment says "Report text is never machine-translated live (adjudicated)" (`app/gates.py:196-212`). The demo ships exactly one Hindi fixture (`dashboard/src/lib/mock.ts:120-121`). OIL's field workforce writes in Assamese/Hindi (OIL operates Tinsukia/Dibrugarh, Assam); OISD publishes its own guidelines in Hindi (`oisd.gov.in/hi/IncidentGuidelines`). OSS to close this offline exists and is mature: **AI4Bharat IndicTrans2** (22 scheduled languages incl. Assamese `asm_Beng`, Bodo `brx_Deva`, Hindi; MIT license, distilled variants; github.com/ai4bharat/IndicTrans2) and **IndicXlit** transliteration (github.com/AI4Bharat/IndicXlit). For scanned reports, **IndicPhotoOCR v2** (scene OCR, 11 Indic languages incl. Assamese; github.com/anikde/IndicPhotoOCRV2) and Tesseract `asm`/`hin` traineddata (tessdoc Data-Files.md) exist — though Tesseract's Indic accuracy is historically poor (logical-segmentation Assamese ~26-65% in the ACL-2015 Indic OCR study, aclanthology.org/U15-1002.pdf). **Severity: blocker for a real OIL deployment, major for the demo.** Today the population most likely to file non-English reports is precisely the population the tool cannot score.
3. **No CAPA / corrective-action loop — the loop stops at the override.** Industry incident platforms all close the loop: VelocityEHS "Select, assign, and track all your corrective actions… automated, escalating notifications" (ehs.com Incident Management + Action Management), Intelex CAPA with due dates and audit trail (intelex.com incident-reporting-software), Cority "Assign, track, and verify corrective and preventive actions" (cority.com). Here, Confirm/Not-SIF is terminal: no owner, no due date, no closure state anywhere in the schema or routes (`app/routes.py` has no /actions endpoint; `app/schemas.py` has no action model). The Baghjan inquiry's core finding was that identified precursor actions were not executed and tracked (NGT Katakey committee interim report, indiankanoon.org/doc/118063652: "failure of following the Standard Operating Procedures… lack of proper supervision"). A triage tool without a remediation register reproduces the failure mode it claims to fix. **Severity: major.**
4. **No escalation, alerting, or SLA timers.** OISD's own regime is time-boxed: First Information Report for major incidents within **24 h**, Internal Investigation Report within **one month**, quarterly summaries within **45 days** (`oisd.gov.in IncidentGuidelines` table rows 1-5). The Katakey committee report documents that at Baghjan "precious time" was lost after the first blowout symptoms because "no responsible officers were present at the site" (The Wire, science.thewire.in, Nov 2020). The product has no concept of *age* of an unreviewed gray item, no alert when a well-control-tagged report sits unreviewed, no routing to a person. Escalation is the single most domain-specific expectation for an OIL tool. **Severity: major.**
5. **No time dimension anywhere in the analytics.** `/density` accepts only `by=site|activity|contractor` (`app/routes.py:266`); `/reports` has only limit/offset, no date filter (`app/routes.py:227-233`). No weekly/monthly trend, no shift/season slicing, no time-to-triage. API RP 754 and IOGP Report 456 define leading indicators as **tiered, time-series counts** (api.org RP 754 fact sheet: "Tiers 1 and 2 are suitable for nationwide public reporting and Tiers 3 and 4 are intended for internal use"; IOGP 456 3rd ed., May 2023, upstream four-tier KPI framework + Well Control Incident levels). A point-in-time density ranking is a map, not a trend — and HSE leaders judge tools by trend lines. **Severity: major.**
6. **Review-priority band is computed client-side and is disconnected from the model's calibrated thresholds.** `bandFor()` hardcodes ≥0.7 HIGH / ≥0.4 MODERATE (`dashboard/src/lib/api.ts:129-131`) while the server's flag threshold and gray band [0.40, 0.60] live in the model artifact and config (`app/config.py:62-63`, per-rule F1-tuned thresholds loaded in `app/classifier.py:286-291`). Two different cut-lines for the same score, in different processes — a domain reviewer cross-checking the card against the API payload sees contradictory severity. **Severity: minor** (easy fix, bad optics).
7. **README promises a metric it never ships.** `README.md:9-10`: "We report triage score, extraction precision, and **reviewer time saved** — never prediction accuracy." The honest-claims table (`README.md:117-129`) contains latency, precision/recall, ingest rate, near-dup, McNemar comparisons — **no reviewer-time-saved measurement exists**. Hostile reviewers check the claim boundary first. **Severity: minor-major** (one sentence fix or one measurement).
8. **The out-of-scope justification for PTW / Bypassing Safety Controls contradicts the domain catalogs.** `README.md:145-147`: both rules "declared out of scope (<0.1% detectable in free text)". IOGP's own FPI scenario catalog codes "Disabling or bypassing safety controls without authorization and alternative controls in place → Fatality" and permit/authorization failures as recurring narrative scenarios grouped by activity/cause/consequence (`data.iogp.org/Downloads/Safety/PotentialFPIExamples.pdf`). The honest limitation is the **training corpus** (US OSHA narratives), not free text generally. Keeping the out-of-scope UI declaration is right; the stated *reason* is contradicted by the literature and should be re-worded. **Severity: minor.**
9. **Near-dup suppression collides with the core SIF insight: near misses are the signal, not noise.** DEKRA/Martin & Black: near-miss events carry **higher** SIF potential than recordables, and SIF prevention targets "exposures that have SIF potential" (DEKRA white paper "Determining Serious Injury and Fatality Potential"). The live stack grays 3,021/5,056 reports on near-dup (`/api/metrics/summary`), i.e., ~60% of the corpus is de-prioritized into the review queue as duplicates. The threshold is measured honestly (0.91, FPR=0 on random pairs, `app/config.py:64-68`), but near-twins of *flagged* reports are the classic place where a second, worse instance hides. Domain expectation: duplicate **roll-up** (group under the first report, escalate on recurrence), not silent de-prioritization into a queue that is already 71% flagged. **Severity: minor-major.**
10. **Barrier coding is a keyword tag, not a barrier model.** The product's "activity_barrier" pattern is co-occurrence mining over text; the domain practice codes barrier failure against a bow-tie register with named barriers, degradation controls, and SECEs (IChemE Hazards 30, Boult: barrier definitions, "should NOT include words such as training, competency, policy"; India's own Petroleum & Natural Gas (Safety in Offshore Operations) Rules 2008 require investigations to state "which barriers have failed… which barriers should have been established"). The repo's well-control tag is a genuine domain-correct hook (maps to IOGP 456 Well Control Incident levels), but calling pattern co-occurrence "barrier" analysis will be challenged. **Severity: minor for demo, major for production claim.**
11. **Positive findings (verified, worth keeping):** (a) the gray-state system operationalizes exactly what DEKRA says is hardest — "agreement and calibration on the definitions of SIF and SIF Potential" plus a "valid, reliable, repeatable classification scheme" (DEKRA white paper); the never-auto-clear review queue matches EEI's precursor-assessment discipline (eei.org sifPrecursorGuide.pdf). (b) The Baghjan framing in the repo is consistent with the public record and does **not** overclaim prevention: `runs/run2/ARCHITECTURE.md:129` ("Never claim the tool would have prevented it"; WOC 48h→12h, BOP pulled before cement set, no officer on site) matches the Katakey committee findings (BOP operated without tested secondary barrier; supervision deficiencies — indiankanoon.org/doc/118063652) and The Wire's "time lost" record. (c) "Model proposes, HSE disposes" matches how VelocityEHS/Cority position AI ("human-in-the-loop validation"). (d) Package claims are accurate — there is no TanStack/Recharts anywhere; `dashboard/package.json:12-23` lists only fonts/cva/cn/lucide/radix/shadcn/tw-animate, and no README or dashboard doc claims otherwise (grep found zero matches for tanstack/recharts in `README.md` and `dashboard/`).
12. **The one export serves the ML pipeline, not the HSSE office.** `GET /review/export` is NDJSON of overrides "as future gold labels" (`app/routes.py:381-386`). There is no export that a regulatory affairs officer could take to an OISD quarterly submission or an internal HiPo review board. **Severity: major** for decision-grade credibility.

## Pain points (where a real OIL HSSE reviewer loses trust)

- **"So what do I do now?"** After Confirm/Not-SIF there is no assignment, no owner, no follow-up state. The reviewer's next action lives in a different system (email/spreadsheet), which is exactly the fragmentation the tool was bought to end.
- **Queue saturation.** 71% flagged + 60% near-dup gray means the feed looks like "everything is urgent and everything is a duplicate." Domain reviewers calibrate trust within minutes on this.
- **Language dead end.** A supervisor pastes a real Assamese/Hindi report and gets a gray card saying the system can't read it. One dead end like this in a demo and the Assam-field narrative ("our people report in our language") collapses.
- **No dates anywhere.** No "trend over last 12 weeks at Kathalguri GCS", no "this pattern is 4x last month". Density without time reads as a snapshot, not intelligence.
- **Bands without policy.** HIGH/MODERATE/LOW mean nothing operationally — no SLA, no owner role, no escalation attached to HIGH. A reviewer asks "HIGH since when? and who was supposed to look?"
- **No export/forward path.** Cannot print, cannot attach to the safety committee pack, cannot reconcile with the OISD register.
- **No users.** Everything is one anonymous reviewer; audit trail is a single override row (`/api/metrics/summary`: `n_overrides: 1`). In a real HSSE audit (ISO 45001, OISD GDN-206 SMS expectations), "who decided" is the first question.

## Gaps vs production (decision-grade credibility)

1. CAPA/action closure loop with owners, due dates, escalating reminders (VelocityEHS/Intelex/Cority baseline).
2. Escalation routing + SLA timers tied to OISD statutory clocks (FIR 24 h, IIR 1 month).
3. Time-series analytics per site/activity/contractor (weekly buckets, period-over-period deltas).
4. Offline Indic translation/normalization path (IndicTrans2 distilled runs on CPU; keeps the no-cloud constraint).
5. Regulatory/decision export pack (incident register CSV/NDJSON aligned to OISD reporting fields, HiPo near-miss compendium — PNGRB HLC report explicitly demands "a compendium of all Near-miss incidents" be maintained by entities).
6. Multi-user audit trail: who triaged, who overrode, when, with the report text hash.
7. Contractor stratification beyond a density facet: per-contractor trend, repeat-offender/recurrence detection (same site+activity+contractor repeating).
8. Human-factors / energy-mechanism classification layer (DEKRA taxonomy of high-energy mechanisms; IOGP FPI catalog groups by activity/cause/causal factor).
9. Barrier-state register linkage (even a manual bow-tie register that the well-control tag references).
10. Reviewer workload view (items per reviewer, aging of gray queue) — nothing today measures the reviewer's burden, though "reviewer time saved" is the headline claim.

## Indian statutory landscape (what the tool would be measured against)

For OIL's onshore Assam operations the regulators stack, per the PNGRB HLC report (`pngrb.gov.in/pdf/TPIAs/HLC_20241028.pdf`: "OISD is the statutory authority for Exploration & Production - Offshore and DGMS is the statutory authority for Exploration & Production - Onshore"):

- **OISD** (Oil Industry Safety Directorate, MoPNG): audits (ESA/SSA/PCSA), incident database, investigations; its guidelines require the 24 h FIR, quarterly summary + minor/HiPo near-miss Incident Reporting Format, IIR within one month, and forwarding of anything reported to PESO/DGMS/DISH/ICG/CPCB/PNGRB (oisd.gov.in IncidentGuidelines). OISD-GDN-206 (SMS) clause 4.12 governs incident investigation; contractor HSE plans list "failure to furnish a FIR within 4 hours" as an infraction (OISD tender HSE framework document, bidplus.gem.gov.in/.../7037650).
- **DGMS** (Mines Act 1952 regime; OMR 2017): statutory authority for onshore E&P mines — OIL's drilling/workover sites fall here; incident notices to DGMS are mandatory.
- **PNGRB**: downstream (CGD/pipelines) T4S + ERDMP regulations require a maintained "Incident Recording System" for all incidents including near-miss (ERDMP regs §96/97, pngrb.gov.in); HLC 2024 recommends an entity-level near-miss compendium and standardized investigation formats — OIL's own Baghjan exposure makes this directly relevant to its gas-gathering/pipeline side.
- **Petroleum Act 1934 + Petroleum Rules 2002, PESO (Explosives Act 1884)**: storage/licensing; PESO consent status was a named Baghjan failure.
- **Factories Act 1948** (via DISH, Assam): GGS/processing installations as factories — notice of dangerous occurrences and accidents (Sections 88/88A) with prescribed timelines.
- **BOCW Act 1996 + rules**: OIL's rig/infrastructure construction work — contractor-incident registers and welfare obligations; the OISD HSE framework explicitly requires BOCWR compliance tracking for contract personnel.
- **Environment (Protection) Act 1986 / EIA, Water Act 1974, Air Act 1981**: the Baghjan proceedings found OIL without mandatory CTE/CTO consents for most of 2006-2020 (NGT Katakey report) — an "operating without consent" finding an internal HSSE dashboard should have been able to surface as a recurring register item.

**Implication for the tool:** none of these acts/rules appear anywhere in the repo (no statutory taxonomy in `app/schemas.py`, no reporting-format export). A "decision-grade" OIL tool must at minimum carry an incident register whose fields map to the OISD FIR/quarterly format, because that is the artefact OIL's HSSE function actually produces.

## Repo claims vs domain literature — cross-check

| Repo claim (location) | Literature check | Verdict |
|---|---|---|
| "~20% of recordable injuries having SIF potential (BST/Mercer ORC 2011; Martin & Black 2015)" (`README.md:142-144`) | EEI SIF guide: "potential for SIF events is low for about 80 percent of non-SIF injuries. About 20 percent of recordable injuries have the potential to be SIFs" (eei.org, Exhibit 1) | **Consistent** — correctly scoped to recordables, not near-misses |
| "Never claim prediction accuracy; triage + extraction only" (`README.md:9-11`, 139-141) | DEKRA: measure *rate of potential SIFs*, "whether the situation repeated would eventually be a SIF" — classification, not prediction | **Consistent**, well-aligned |
| PTW + Bypassing Safety Controls "<0.1% detectable in free text" (`README.md:145-147`) | IOGP FPI catalog codes bypassing-safety-controls as a recurring Fatality-potential narrative scenario (data.iogp.org PotentialFPIExamples.pdf) | **Tension** — true of this repo's OSHA-derived training data, overstated as a general claim about free text |
| Baghjan framing: "precursors existed and were buried… we do not claim this tool would have prevented any past incident" (`README.md:148-150`, `runs/run2/ARCHITECTURE.md:129`) | Katakey committee: BOP operated "without testing secondary safety barrier", supervision deficiencies; The Wire: "precious time lost", "no responsible officers were present at the site" | **Consistent and well-corroborated** — the repo's precursor list (WOC duration, BOP/cement, officer absence) matches the public record |
| Review-priority band HIGH/MODERATE/LOW (`dashboard/src/lib/api.ts:129-131`) | No SIF-program literature uses a 0.7/0.4 two-cut band; severity ladders are outcome-based (IOGP FPI Actual/Potential/Near-Miss; API RP 754 Tiers 1-4) | **Divergent** — band is an ad-hoc UI heuristic, not anchored to any standard ladder; flag it or map it |
| Flag rate as a success proxy | ORC 2011: ~20% SIF-potential prevalence in recordables; a triage tool's value is the read-fraction it removes | **Tension** — live flag rate 70.95% (API) far exceeds any plausible SIF-potential prevalence; corpus is synthetic, but the demo narrative should disclose this |

## Capability checklist for a credible OIL HSSE tool

| # | Capability | Tag | Today's status |
|---|---|---|---|
| 1 | Free-text incident triage with calibrated, explainable scores + evidence | must-have | **SHIPPED** — calibrated score, spans, deterministic explanations (`README.md:119-124`) |
| 2 | Human-in-loop classification with consistency controls (gray band, never auto-clear) | must-have | **SHIPPED** — 10 gates (`app/gates.py`) |
| 3 | IOGP LSR rule coverage incl. explicit out-of-scope declaration | must-have | **SHIPPED** — 7/9 + 2 declared (`app/schemas.py:31-47`); reason wording wrong (finding 8) |
| 4 | Mixed-script (Assamese/Hindi) report handling, offline | must-have | **ABSENT** — gray-only (`app/gates.py:196-212`) |
| 5 | Queue compression: flagged fraction ≪ review capacity | must-have | **FAILING** — 70.95% flag rate (live API) |
| 6 | CAPA: assign owner, due date, closure, escalating reminders | must-have | **ABSENT** |
| 7 | Escalation/alerting + SLA clocks (OISD FIR 24 h) | must-have | **ABSENT** |
| 8 | Trend over time per site/activity/contractor | must-have | **ABSENT** (`app/routes.py:263-267`) |
| 9 | Audit trail: who/what/when, exportable | must-have | **PARTIAL** — 1-override table, no auth, no export of decisions (`review.tsx:38-87`) |
| 10 | Regulatory pack export (OISD incident register / quarterly summary fields) | must-have | **ABSENT** (only ML gold export, `routes.py:381`) |
| 11 | Contractor stratification + recurrence/repeat-offender tracking | must-have | **PARTIAL** — density facet only (`routes.py:266`) |
| 12 | Near-dup roll-up with escalation on repeats | must-have | **PARTIAL** — suppression-to-gray only |
| 13 | API RP 754 / IOGP 456 tier mapping for process-safety events | nice-to-have | **ABSENT** — but well-control tag is the natural anchor (`oiics_maps.py:170`) |
| 14 | Barrier-state coding against a bow-tie/SECE register | nice-to-have | **ABSENT** (tag only; see finding 10) |
| 15 | Human-factors/energy-mechanism taxonomy | nice-to-have | **ABSENT** |
| 16 | Shift/season slicing | nice-to-have | **ABSENT** (no time dimension at all) |
| 17 | Reviewer workload / aging dashboard | nice-to-have | **ABSENT** |
| 18 | LSR/PSF violation analytics tied to field-verification programs | nice-to-have | **ABSENT** (LSR heads exist; no verification-workflow tie-in — IOGP SWC model, Report 459-1) |
| 19 | Scanned-document OCR ingestion | nice-to-have | **ABSENT**; blocked by the project's no-vision constraint — document as accepted limitation, use IndicPhotoOCR-class tools only if the constraint is ever relaxed |
| 20 | Cloud translation / external LLM for any language handling | out-of-scope-with-reason | Offline runtime constraint is real and defensible; IndicTrans2 local inference satisfies it |
| 21 | Incident *prediction* (probability a report precedes an actual SIF) | out-of-scope-with-reason | README claim boundary already forbids it — keep; matches DEKRA (measure potential, not predict) |
| 22 | Vision/image analysis of incident photos | out-of-scope-with-reason | Inherited hard constraint; free-text triage is the PS, keep it |

## Recommendation

- **KEEP** the 10-gate gray-state system — it implements the industry's hardest problem (repeatable SIF-potential classification) and is the repo's most domain-credible asset.
- **KEEP** the 7+2 IOGP rule model with out-of-scope declarations — industry-standard taxonomy (`app/schemas.py:31-47`); re-word the out-of-scope reason to "not detectable in our training corpus" rather than "not detectable in free text" (finding 8).
- **KEEP** the measured near-dup index — but reframe as **roll-up** (finding 9).
- **KEEP** the Baghjan framing exactly as written (`runs/run2/ARCHITECTURE.md:129`, `README.md:148-150`) — it is consistent with the NGT record.
- **REMOVE** client-side `bandFor()` (`dashboard/src/lib/api.ts:129-131`) — move band thresholds server-side next to the calibrated thresholds; one source of truth.
- **REMOVE** "reviewer time saved" from the README claim boundary (`README.md:9-10`) until it is actually measured — or measure it.
- **ADD** a time dimension: date filters on `/reports` and `/density` plus a weekly bucketed trend endpoint — smallest change with the largest decision-grade payoff.
- **ADD** a minimal CAPA model (action_id, report_id, owner, status, due_ts, closed_ts) and wire Confirm/Not-SIF to an action suggestion; this is what separates "triage demo" from "HSSE system".
- **ADD** offline Indic normalization: run IndicTrans2 (distilled, MIT, CPU-viable) translate-before-classify so the language gate degrades to a badge instead of a permanent gray dead end; keep the no-cloud constraint intact.
- **ADD** an OISD-aligned export: incident register (CSV/NDJSON) with the fields OISD's incident reporting format and quarterly summary expect; reuses the existing export plumbing (`routes.py:381-386`).
- **MERGE** the "decisions" review tab with the feed's review filter (`dashboard/src/views/feed.tsx:73` and `dashboard/src/views/review.tsx`) into one review workflow (queue → decision → action) — today the same concept lives in two places with different data.
- **MERGE** escalation into the existing gate actions: a well-control-tagged or severity-watch report aging past N hours is exactly a gate-shaped rule; no new subsystem needed.

## Key sources

- IOGP Life-Saving Rules (9 rules, Report 459): https://www.iogp.org/workstreams/safety/safety/life-savingrules/ ; Start Work Checks (Report 459-1): https://www.iogp.org/bookstore/product/life-saving-rules-start-work-checks/
- Shell LSR transition (SPE 215565): https://jpt.spe.org/transition-to-industry-life-saving-rules-embeds-human-performance-in-practice
- Harbour Energy LSR+PSF standard (IOGP 459 + 638): https://www.harbourenergy.com/media/mvolg4mi/hbr-glo-hse-std-0002.pdf
- DEKRA, "Determining Serious Injury and Fatality Potential": https://dekraprod-media.e-spirit.cloud/d6df64f5-b4d9-468c-8ffa-874a167a15ab/media/dekra-or-wp-determining-serious-injury-and-fatality-potential.pdf
- EEI SIF Precursor Customization Project guide: https://www.eei.org/-/media/Project/EEI/Documents/Issues-and-Policy/Power-to-Prevent-SIF/sifPrecursorGuide.pdf (ORC 2011 ~20% figure, decision-tree vs narrative review)
- VelocityEHS Incident Management (AI PSIF Insights, CAPA): https://www.ehs.com/solution/safety/incident-management/ ; Cority: https://www.cority.com/corityone/incident-management-software/ ; Intelex: https://www.intelex.com/incident-reporting-software/
- API RP 754 fact sheet (4 tiers): https://www.api.org/-/media/files/oil-and-natural-gas/refining/process%20safety/rp-754-fact-sheet.pdf ; IOGP Report 456 3rd ed: https://www.iogp.org/bookstore/product/process-safety-recommended-practice-on-key-performance-indicators/
- IOGP FPI definitions + scenario catalog: https://www.iogp.org/wp-content/uploads/2024/07/FPI-Definitions-flyer.pdf ; https://data.iogp.org/Downloads/Safety/PotentialFPIExamples.pdf
- Barrier/bow-tie quality rules (IChemE Hazards 30, Boult): https://www.icheme.org/media/25679/hazards-30-paper-10-boult.pdf
- OISD incident reporting guidelines (FIR 24 h, quarterly, IIR 1 month): https://www.oisd.gov.in/hi/IncidentGuidelines
- PNGRB High-Level Committee report (near-miss compendium; DGMS = onshore statutory authority): https://www.pngrb.gov.in/pdf/TPIAs/HLC_20241028.pdf ; PNGRB ERDMP regs: https://www.pngrb.gov.in/OurRegulation/PNGRB%20Regulations/D.%20Technical%20Standards%20and%20Specifications%20including%20Safety%20Standards%20(T4S)/D.2.%20ERDMP%20Regulations/ERDMP-Post%20Amendment-17.09.2020.pdf
- Baghjan NGT (Katakey committee) findings: http://indiankanoon.org/doc/118063652/ ; NGT progress report: https://www.greentribunal.gov.in/sites/default/files/news_updates/REPORT%20IN%20OA%2043%20of%202020%20%26%2044%20of%202020-EZ%20titled%20Bonani%20Kakkar%20Vs.%20%20Oil%20India%20Limited%20%26%20Ors.pdf ; "precious time" reporting: https://science.thewire.in/politics/government/oil-india-baghjan-blowout-expert-panel-report-national-green-tribunal-precious-time/ ; background: https://en.wikipedia.org/wiki/2020_Assam_gas_and_oil_leak
- Indic OSS: IndicTrans2 (22 langs, MIT): https://github.com/ai4bharat/IndicTrans2 ; IndicXlit: https://github.com/AI4Bharat/IndicXlit ; IndicPhotoOCR v2 (11 langs incl. Assamese): https://github.com/anikde/IndicPhotoOCRV2 ; Tesseract data (asm/hin): https://github.com/tesseract-ocr/tessdoc/blob/main/Data-Files.md ; Indic OCR accuracy study: https://aclanthology.org/U15-1002.pdf