# FINAL AUDIT — PS-COMPLIANCE LENS (SIH 26165)

**Auditor role:** PS-COMPLIANCE AUDITOR (fresh-eyes swarm, Phase 3 gate)
**Date:** 2026-09-09 · **Live stack probed:** `http://localhost:8177` (`onnx:masked-v2/sif_multitask_int8.onnx`, RealOnnxClassifier, 5,048 reports — health JSON captured at audit time)
**Method:** doctrine-compliant — every claim below was re-verified against the live API (read-only GETs + stateless POST /classify), the live dashboard UI (Playwright, screenshots saved alongside this file), the source code, and two throwaway servers on ports 8191/8192 with throwaway DBs for all mutating tests. Ports 8001-8004 and `artifacts/gold/labels*/` were not touched.

**The PS text (HANDOFF.md §A.1, verbatim):** "Build a prototype that ingests OIL's free-text safety reports and automatically: (a) classifies each as SIF-potential vs non-SIF-potential, (b) tags it to the relevant IOGP Life-Saving Rule (Energy Isolation, Hot Work, Confined Space, Line of Fire, etc.), (c) surfaces recurring precursor patterns (activity, location, barrier failure) via a dashboard ranking sites/activities by SIF-precursor density."

## Verdict per clause

| Clause | Verdict | Confidence |
|---|---|---|
| (a) SIF-potential classification | **COMPLIANT — verified live** | high |
| (b) IOGP Life-Saving Rule tagging | **COMPLIANT with a declared, evidence-backed gap (7/9 rules)** | high |
| (c) Pattern surfacing + density dashboard | **COMPLIANT — verified live, 2 caveats** | high |
| Review queue + override→label loop | **WORKING — mutation-tested on throwaway stack** | high |
| Claimed-but-not-working | **2 found** (1 SEV1-class demo-optics, 1 script/screen mismatch) | — |

---

## (a) SIF-potential classification — COMPLIANT

Live `POST /api/classify` on :8177 (stateless, no DB writes):

| Input (paraphrase) | sif_score | Verdict |
|---|---|---|
| Grinding on live crude flowline, sparks, no gas test, fire watch absent | **0.9882** | flagged ✓ |
| Canteen doormat loose, taped down, no injury | **0.0054** | not flagged ✓ (negation gate correctly grayed the "no injury" phrasing) |
| Demo card `contrast-red` (wrench dropped past drill floor near roughnecks) | **0.9338** | HIGH ✓ |
| Demo card `contrast-green` (same spanner, floor cleared) | **0.0121** | LOW ✓ — the contrast lands |

The flag threshold is not a guess: `RealOnnxClassifier` loads `operating_point_test_tuned` from the artifact's `metrics.json` (raw 0.746401 → calibrated 0.658108, T=1.6484), temperature-mapped at load (`app/classifier.py:374-401`). Reported operating point (from `runs/run2/day2/ship_decision.md`, not re-derived by me): P 0.8000 / R 0.9748 on the 17,731-row temporal holdout. UI framing is compliant with the triage doctrine: "triage score", amber "review priority" band, never "% accuracy" / "SIF DETECTED" (D14; observed in the rendered UI).

## (b) IOGP Life-Saving Rule tagging — COMPLIANT WITH DECLARED GAP

**All 9 rules are handled; 7 are model-tagged, 2 are declared out-of-scope with measured evidence.**

Live probe — each of the 7 in-scope rules fires dominantly on matching text (masked-v2 int8):

| Probe text | Dominant rule prob | sif |
|---|---|---|
| Lockout/tagout skipped, motor energized | energy_isolation **1.00** | 0.764 |
| Scaffolder at 25 m, harness not clipped | working_at_height **0.999** | 0.957 |
| Crane, suspended load over walkway, frayed sling | safe_mechanical_lifting **1.00** | 0.973 |
| Manhole/tank entry, no ventilation/gas test | confined_space **0.999** | 0.836 |
| Forklift speeding, ran over toolbox, no seat belt | driving **0.998** | 0.729 |
| Hot work at live flowline | hot_work **0.9999** | 0.988 |
| Demo card contrast-red (dropped wrench) | line_of_fire **0.853** | 0.934 |

`GET /api/rules` returns all 9: 7 with `in_scope: true` + per-rule F1-tuned thresholds loaded from the artifact (0.54–0.95), and `work_authorisation` ("Work Authorisation (Permit to Work)") + `bypassing_safety_controls` with `in_scope: false`, `threshold: null`.

**Is 7/9 + declaration compliant? My ruling: yes, and it is the strongest available answer.**
- The PS says "tags it to the relevant IOGP Life-Saving Rule (…, etc.)" — the system does tag reports to rules; for the 2 procedural rules it *declares* the gap instead of faking tags.
- The gap is measured, not asserted: PTW = 3 rows of 105,996 (0.003%, and only 1 of 3 is genuinely PTW); Bypassing = 0.08–0.09% (`runs/run2/phase0-validation/iogp-coverage.md`, "(a) PTW + Bypassing undetectable: VERIFIED"). Both are procedural violations invisible in post-injury narrative text — a coverage ceiling of the data genre, not an implementation shortcut.
- The declaration is ubiquitous, not buried: README "Honest claims" §; deck slide 11 ("What we DON'T claim — the slide judges remember"); the triage card renders "Declared out-of-scope (never scored): Work Authorisation (Permit to Work) · Bypassing Safety Controls" on **every** card (`dashboard/src/lib/api.ts:160-162` pushes the OOS pair unconditionally); the mega-report encore script turns the gap into the honesty beat (the mega report literally contains "started without any PTW" → shown greyed).
- Residual risk: a literalist judge could score "the PS lists 9 rules, you cover 7". Mitigation is in place (slide 11 + the measured <0.1% numbers). Faking would be worse — a single "why does this PTW report have no PTW tag?" with faked tags would detonate the honesty doctrine that protects the whole pitch. **Keep as is.**

Bonus beyond spec: the deterministic **well-control/barrier tag** (Baghjan-class events the 9 personal-safety rules structurally miss) — verified live (`well_control: true` on kick/BOP/wellhead text; app keyword list synced to the frozen spec per D23).

Caveat (disclosed, not a defect): rule attribution on *unseen phrasings* drifts — my ad-hoc "dropped spanner struck bystander" text came back hot_work-dominant (0.822) over line_of_fire (0.55). The demo card phrasing is LoF-dominant as scripted. The design mitigates by showing per-rule probability bars, never a single asserted rule (D22). A judge freelancing novel texts may produce odd dominant rules — the rehearsed answer is the probability bar, and the override loop is the disposition.

## (c) Density ranking + pattern surfacing — COMPLIANT (live-verified), 2 caveats

**Density view (PS: "ranking sites/activities by SIF-precursor density"): WORKING, live.**
- `GET /api/density?by=site|activity|contractor` — single SQL GROUP BY over the live DB; sums to exactly 5,048 reports; 341 site rows with real variance (283/341 below 100% flag rate; bottom rows 0.0 at mean score ~0.01).
- UI verified by screenshot (`audit_density_tab.png`): ranked table (#1 Kathalguri GCS 213/213, rate 100.0 per 100, mean 0.96, Δrank column), "Simulate ingest → re-rank" button, FLIP re-rank animation wired (`use-flip.ts`).
- The re-rank beat is real: ingesting rows changes the ranking live (verified on throwaway :8191 — 2 ingested rows appeared in density immediately).

**Pattern mining (PS: "recurring precursor patterns (activity, location, barrier failure)"): WORKING.**
- `GET /api/patterns?kind=site_activity|activity_barrier` — lift-ranked cells with n, SIF rate, Wilson 95% CI, dominant rule tag (`data_pipeline/pattern_mine.py`; stats reproduced in `pattern_mine_selfcheck.py`). UI screenshot: `audit_patterns_tab.png` — "derrick/mast climbing × Workover Rig #7 · Working at Height · 37 reports · lift 1.5× · 95% CI [0.91, 1.00]".
- All three PS facets are covered: activity ✓, location ✓ (site), barrier failure ✓ (activity×barrier cells carry real failure modes: "LEL re-test not done after break", "PFAS inspected but wrongly worn").

**Caveat 1 (medium): pattern cards are precomputed from the synthetic corpus, not from live ingested data.** When `artifacts/patterns/patterns.json` exists (it does, and ships in the tarball), `/api/patterns` serves it verbatim — patterns do **not** recompute after a judge uploads their own CSV. The live-DB fallback exists and works (verified on throwaway :8192 with `SIF_PATTERNS_FILE` pointed at nothing: live cells with lift + CIs computed from ingested rows), but it is not the shipped configuration. The demo narrative only claims "the pattern miner reads structured facets — no LLM guessing", which is true — but a technical judge who asks "did those patterns come from the file I just uploaded?" gets a nuanced answer: density yes, pattern cards are the corpus statistics. Recommend one rehearsed sentence; do not improvise.

**Caveat 2 (cosmetic): top pattern cards are uniform.** All 197 site×activity cells are rate=1.0, lift=1.499 (the synthetic corpus's positive cells are generator-labeled 100% SIF); ranking among them is by n and CI width only. Judges may notice every card reads "100 per 100". The activity×barrier family does have variance (16 zero-rate cells). Honest stats, samey visuals.

## Review queue + override→label loop — WORKING (mutation-tested)

On throwaway servers (:8191/:8192, throwaway DBs, real masked-v2 model):
- Ingest → override → list → export chain verified end-to-end: `POST /api/review` 201 (`sif_label` confirm/not_sif, and a `rules` override accepting the OOS key `work_authorisation`); invalid values rejected 422 (`"banana"`, `"made_up_rule"` — the SEV2-3 vocabulary contract); `GET /api/review` lists history; `GET /api/review/export` emits NDJSON, latest-wins per (report, field), with `source: "override"` kept separate from `"blind_gold"` for eval hygiene.
- Live review tab screenshot (`audit_review_tab.png`): "Awaiting HSE disposition (4)" — real gated reports from the live DB (2 drill/simulation, 1 negation guard, 1 low-confidence 0.551 in gray band), each with the gate reason rendered.
- Live demo DB correctly shows `n_overrides: 0` — the queue is fresh for the demo beat; the dashboard's Confirm/Not-SIF buttons POST real writes (`App.tsx:40-75`), footer "Model proposes, HSE disposes. Your decision becomes a training label."

---

## Claimed-but-not-working — 2 findings

### F1 (SEV1-class, demo optics): ALL 13 demo cards' cached explanations contain a Python error string

**Status: cross-confirmed.** `runs/run2/day2/final_audit_rehearsal.md` (F3) found this independently; I re-derived it from scratch and extend it with the full blast radius and root cause.

- **Repro (ran 4×, stable):** `POST /api/classify?explain=1&llm=0` with the `contrast-red` text → `explanation.template` ends with `Advisory gates: near_dup (gate error: AttributeError: '_NullStorage' object has no attribute 'nearest_base_batch')` **while the same response's live `gate_states` show near_dup healthy** ("max cosine=0.781", not triggered).
- **Worse:** the ollama *reworded* paragraph — the plain-English text judges read first — paraphrases the error: *"…with an advisory gate error noted as near_dup (gate error: AttributeError: '_NullStorage' object has no attribute 'nearest_base_batch')"* (verified verbatim on contrast-red, wc-baghjan-1, verbatim-osha). The reword validators (score-verbatim, span-substring, meta-language regex) all pass this prose.
- **Blast radius (read-only count on the live DB):** 70 `explain:*` rows in the `precomputed` table; **63 contaminated** — exactly the precomputed batch (13 demo cards + top-50 feed reports). All 13/13 demo cards affected, both source=ollama (49) and source=template (14). The 7 clean rows are live-written cache entries (healthy path).
- **Root cause:** `artifacts/explanations/precompute.py:61-76` stubs gates with `_NullStorage`, which implements `nearest()` but not `nearest_base_batch()`/`nearest_session()` that `gate_near_dup` (post-D25) calls → AttributeError → `run_gates` degrades to a triggered gray "gate error" state (`app/gates.py:297-305`) → `render_template` bakes triggered-gate details into the template (`app/explain.py:135-138`) → ollama rewords the contaminated template → cached under keys that match live lookups (threshold-aware since fix C — which is exactly why they hit).
- **The live path is clean** — novel text gets fresh gate states; this is a fossil from precompute time, not a runtime bug.
- **Fix (cheap, ~30 min):** add the two stub methods to `_NullStorage` (or point the harness at real storage), **delete the 63 poisoned rows** (cache keys won't change on their own), re-run precompute, acceptance = `SELECT COUNT(*) FROM precomputed WHERE payload LIKE '%gate error%'` → 0 + one browser click-through of "Why this score?" on contrast-red. Until then: **do not open the explanation expander within judge sight** (rehearsal auditor's F3 interim guidance — concur).
- **Note on prior verification:** `demo_final_state.md §3` claimed "63/63, 0 errors; cache-hit serving verified live 0.5–7.7 ms" — true on the checked invariants (span validity, cache-hit latency), but content was never grepped. The check measured the pipe, not the water.

### F2 (medium): Beat-1 script narrates evidence spans that will not be on screen

- `artifacts/demo/script_90s.md` beat 1 says: *"shows you exactly why, in the report's own words"* with the card note *"spans on 'fell past the drill floor' / 'near two roughnecks'"*.
- **Live reality:** `contrast-red` returns `evidence_spans: []` (verified twice; `demo_final_state.md §8 O1` — the span head is dead at runtime and the D2 keyword fallback deliberately excludes "fell"/"dropped" as too noisy per the frozen spec). The hero card of the demo shows **no highlights**.
- Span highlighting itself works where vocabulary matches (verified live: "grinding"/"sparks" on my probe, `LOTO` on codes-only, `Welding` on wc-baghjan-3, `sling` on mega-report).
- **Fix options (already adjudicated — do not hack the app mirror):** either land the frozen-spec change (add a falling-object keyword family to the LoF LF) + re-run affected derivations, or re-narrate beat 1 to point at the rule-probability bar + well-control chip as the "why" and let wc-baghjan-3/codes-only carry the live highlight moment. Cheapest safe fix is the narration edit.

## Smaller notes (no action blocking)

- **Pure process-safety text scores low on the SIF head:** my ad-hoc "well kicked, gas migration, kill line blocked" scored 0.0286 (well_control tag fired ✓). The 3 scripted wc-baghjan cards all score HIGH (0.90/0.99/0.98), so the demo is safe — but the Baghjan Q&A answer leans on the deterministic tag + framing, not the classifier. Consistent with the rehearsed line ("we raise precursor visibility; we do not replace well-control assurance").
- **Density top-of-table is all 100%** — expected on the seeded demo corpus (71% overall flag rate; sort is rate-then-n). If a judge asks "why is everything 100%": scroll — 283 of 341 sites are below.
- **README still has 2 TODO placeholders** (architecture diagram, full claims table) against the §E "README with architecture diagram + honest-claims section" bar; deck slide 8 (gold metrics) is a fill-after-labeling slot by design. Flagging for the production-shaped lens, not a PS-clause gap.
- Hindi phrasebook toggle verified live (full UI chrome switch, report text untouched) — as designed.

## Isolation & safety statement

Ports 8001-8004 (labeling) never touched; `artifacts/gold/labels*/` never read or written. All mutating tests ran on throwaway DBs (`/tmp/sif_audit*.db`, deleted after) on ports 8191/8192, servers killed after. Live :8177 received only GETs and stateless `POST /api/classify` calls (no /ingest, no /review writes). One nuance: `/api/classify?explain=1` on cache miss writes an explanation-cache row — all my classify calls hit the precomputed cache (all 13 cards) or were plain classify (no writes), so the live DB was not mutated by this audit.

## Score rationale

- **go_no_go 7/10** — every PS clause is demonstrably delivered and live-verified; the two claimed-but-not-working items both sit on beat 1 (the money card) but both have cheap same-night fixes (cache purge + re-run; narration edit). Conditional GO: fix F1 before any judge sees an explanation.
- **severity 7/10** — F1 puts a Python AttributeError into the plain-English HSE explanation of the hero card; it undermines the single most-load-bearing claim ("every failure mode ends in a designed gray card" / "honest system") precisely where judges look. No spec clause is broken; no data or eval integrity is harmed.
- **feasibility 8/10** — the PS was buildable and is built: real model, real latency, real loop. The 2-rule gap is a measured data-genre ceiling with a defensible declaration, and the well-control tag recovers the Baghjan-shaped hole the PS's rule list can't see.
- **data_risk 4/10** — no real OIL data exists (inherent to the PS; disclosed on deck slide 6 with the detector-separability admission); demo density/patterns are synthetic-corpus statistics labeled as such; gold protocol verified in code as blind (labelers see masked text + EventTitle only, no model output — `gold/labeler_app.py` docstring + spec `gold.labeling`). Residual: pattern mining runs on generator labels, and the demo's 71% flag rate reflects the seeded corpus, not natural prevalence — both disclosed.

<<SCORES {"ps":"26165","role":"ps_compliance","go_no_go":7,"severity":7,"feasibility":8,"data_risk":4}>>
