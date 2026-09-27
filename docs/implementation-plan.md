# Implementation Plan — Production Overhaul

**SIH 2026 · PS 26165 · Oil India Limited** · 2026-09-25
**Prerequisites:** `docs/redesign-plan.md` (Phase 0), `docs/frontend-stack-decision.md`,
`docs/backend-stack-decision.md`, `docs/discovery/60-orchestrator-novel-probe.md`

This is the execution plan. It names the fix for every finding, the order, and the verification
gate that must pass before the next workstream starts. Sequencing is driven by one rule:
**correctness fixes change what the product may claim, and claims change what the UI must show.**

---

## 0. The reframing (read first)

Two corrections from inspecting the rendered screenshots myself:

1. **The gate system already compensates for model misses.** A report scoring **0.487** — below
   the 0.658 flag threshold — is nonetheless routed to review by
   `well_control_watch: barrier tag fired but triage score 0.487 < flag threshold 0.658 — rare
   high-consequence domain, automated screening defers`. The humility layer worked. It did **not**
   fire for LOTO / gas-test / fire-watch cases, which rendered green.
2. **Decision history already shows Was→Now** (`Low-priority → SIF-potential`). It lacks rationale,
   real reviewer identity, and any correction path — not the before/after.

The first is the most valuable thing in this document, because it turns D3 from "needs retraining"
into "needs more of what already works":

> **Generalise `well_control_watch` into a barrier-failure gate family.** Deterministic, offline,
> testable, zero training cost — and it is precisely the PS phrase "identifying barrier failures".

The model's *score* can remain what it honestly is: good at physical mechanism, weak at procedural
absence. The **system** becomes the decision-grade artefact. That is also the honest framing for
the judges: *"the model proposes; deterministic barrier detection and a human dispose."*

---

## 0.1 Historical audit — superseded (2026-09-26)

The findings below preserve the audit snapshot from 2026-09-25; they are not current blockers. Several have since been resolved: the adversarial suite now passes 18/18 plus #10b with the real classifier; selfcheck uses stable dashboard markers (`id="root"` plus the served bundle); `threadpoolctl` is now present in `packaging/wheels/`; and pytest collects 10 tests through `pytest.ini`. The remaining historical findings should be rechecked before being treated as current. See [`overhaul-summary.md`](overhaul-summary.md) for dated current-state evidence.

| # | Blocker | Verified evidence | Severity |
|---|---|---|---|
| **B0** | **The adversarial regression suite is red and the README claims it is green.** `GATE_ORDER` lists 9 gates; `run_gates` emits 10 (`severity_watch`). Line 334 asserts `set(gates) == set(GATE_ORDER)` → every case fails. README:127 claims "18/18 PASS". | `tests/adversarial_suite.py:283,334` vs `app/gates.py:408` | blocker |
| **B1** | **The offline bring-up proof cannot pass.** `selfcheck.sh:70` greps `SIF-Precursor`; the built title is `Safety Report Triage — OIL India`. README claims "self-check: 2 clean cycles". | `packaging/selfcheck.sh:70` vs `dashboard/dist/index.html` | blocker |
| **B2** | **The air-gapped USB install is broken.** `threadpoolctl` is missing from `packaging/wheels/`, so `install.sh`'s offline `pip install` fails on the exact dependency the near-dup matmul needs. | `ls packaging/wheels/` | blocker |
| **B3** | **O(n²) gate matching stalls long input.** `_match_token_starts` (`gates.py:151-159`) measured 0.6 s at 10k chars, 3.1 s at 50k, **11.3 s at 100k**, **51.3 s** at 194k. | measured | blocker |
| **B4** | **Bulk ingest is ~6× slower than documented.** Measured 7.3 rows/s (68.9 s / 500 rows) against README 45.6/s and `api.ts:327,338` "37 rows/s ≈ 15 s". This is the mechanism behind the SEV-1 false-failure. | measured | blocker |
| **B5** | `rationale` is accepted and stored server-side but **never sent** by the UI (`App.tsx:55-60` sends a band string as `old_value`) and **dropped** on read (`api.ts:192-203`). | verified | major |
| **B6** | `pytest --collect-only` collects **0** tests — rootdir is polluted by `packaging/pendrive/staging`. Three self-checks (`onnx_classifier_check`, `near_dup_embed_check`, `postreview_fix_check`) fail on deleted `masked-v1` / `artifacts/corpus`. `/api/patterns` can 500 on a corrupt `patterns.json`. | verified | major |
| **B7** | Inventory correction: `app/tests/` holds **6** runnable self-check scripts (1,152 LoC) that no README section lists. | `README.md:61` stale | minor |

**Consequence for sequencing:** there is now no working regression gate and no working bring-up
proof. Those must be restored **before** any other change, or we cannot tell whether our fixes
regressed anything.

---

## 1. Workstream S — Make the test and packaging story TRUE *(do first)*

Nothing else is safe to change until the safety net is real.

1. **Fix `GATE_ORDER`** to the actual 10-gate set (add `severity_watch`), or better: derive it from
   `gates.run_gates`' own dispatch table so it can never drift again. Re-run `adversarial_suite.py`
   and make it genuinely green — then, and only then, is the README line honest.
2. **Fix `selfcheck.sh:70`** to assert the real title (or better, a stable marker like `id="root"`
   plus `/api/health` `status:ok`) and run two full cycles to green.
3. **Vendor the missing `threadpoolctl` wheel** into `packaging/wheels/`, then run
   `packaging/install.sh` in an isolated prefix to prove the offline pip step completes.
4. **Fix the O(n²) `_match_token_starts`** (precompute a token-start offset table; or bound input
   length and chunk it — a 100k-char paste must not stall the request thread for 51 s).
5. **Repair the broken self-checks**: repoint `onnx_classifier_check` at `masked-v2`
   (`masked-v1` is deleted), repoint `near_dup_embed_check` / `postreview_fix_check` at whatever
   replaces the deleted `artifacts/corpus`, or delete them honestly.
6. **Make pytest collectable**: add a `pytest.ini`/`pyproject` `testpaths` that excludes
   `packaging/`, `dashboard/`, `.venv/`.
7. **Fix `run_gates`-vs-suite drift as a permanent guard**: one property test asserting the suite's
   gate set equals `run_gates`' gate set.

**Gate:** `adversarial_suite.py` green · `selfcheck.sh` 2 clean cycles · `pytest --collect-only` > 0 ·
100k-char classify < 1 s · README's 18/18 and self-check lines are factually true.

Only after this gate passes do we have a trustworthy signal for Workstreams A–D.

---

## 2. Workstream A — Backend correctness (do second)

Small, measurable, independent of the frontend. Each item has a hard verification gate.

### A1 · Runtime masking *(fixes D2)* — **do first, highest ratio**

- **Root cause:** `data_pipeline/masking.py` runs at training only (`build_corpus.py:209,274`).
  No `mask_text` call exists anywhere in `app/`.
- **Fix:** call `mask_text()` on inbound text in the classifier's preprocessing path
  (`app/classifier.py`, immediately before tokenization) so inference matches training.
  Import it as a plain module — it is pure regex, no dependencies.
- **Evidence:** measured **+0.349** on near-miss text; repairs the anti-feature where
  *"Fortunately no injury occurred"* **drops** a score 0.280 → 0.100.
- **Gate:** re-run the paired-probe harness (§A6). The near-miss delta must shrink to ≈0 and no
  benign case may move above 0.10. Record before/after in the docs.

### A2 · Barrier-failure gate family *(the D3 fix)* — **the headline feature**

- **Pattern to copy:** `gate_well_control_watch` in `app/gates.py`. Same contract:
  `GateState(name, triggered, detail, action)`, `action="gray"` so it is never auto-cleared.
- **New gates**, all deterministic, each firing on explicit **absence of control** language rather
  than mere mention (so *"LOTO applied and verified"* must NOT fire):

  | Gate | Fires on | IOGP rule |
  |---|---|---|
  | `energy_isolation_absent` | LOTO/lockout *not applied*, isolations *not verified*, no de-energisation | Energy Isolation |
  | `gas_test_absent` | *no* gas test / detector / atmospheric testing before entry | Confined Space |
  | `permit_absent` | *no* permit to work / PTW not raised | Permit to Work |
  | `fire_watch_absent` | fire watch *absent / left / gone* | Hot Work |
  | `standby_absent` | *no* standby man / attendant posted | Confined Space |
  | `atmosphere_unmonitored` | purging in progress / no monitoring during entry | Confined Space |

- **Negation-aware matching** is mandatory: require cues such as `not|no|without|absent|never|was
  not|omitted|missed|failed to` adjacent to the control term. A bare mention is advisory only.
  Implement as a small declarative table (regex + cue list) inside `gates.py`, **not** a rule-engine
  library — `44-res-backend-oss.md` rejected those on evidence (abandoned / LGPL / cannot express
  the windowed-regex and embedding-backed gates).
- **Behaviour:** when a barrier gate fires and `sif_score < flag_threshold`, still route to review
  (as `well_control_watch` does), and surface the specific barrier named in the verdict card.
- **Gate:** property tests (hypothesis) asserting: positive-absence phrases fire, their negated
  forms do not, and benign administrative text fires none. Target: ≥95 % precision on a 50-case
  hand-labelled set, and **0 fires** on the 4 benign probe cases.

### A3 · Self-consistency scoring + `verdict_stability` gate *(fixes D1 reliability)*

- **Fix:** score N surface variants (N=4 default, configurable), return `sif_score` = mean, plus
  `score_spread` (sd or min/max) and `variant_scores`. Add a `verdict_stability` gate with
  `action="gray"` when spread exceeds a tuned threshold.
- **Cost:** ~20 ms × N → ~80–160 ms, acceptable (bulk path can share a single score per row).
- **Evidence:** mean-of-8 cuts sd **0.308 → 0.076**. It does **not** fix validity — the consensus
  for procedural cases stabilises around 0.318, still unflagged. **Disclose both halves.**
- **Variants:** deterministic surface transforms (voice, clause reorder, synonym table) so it is
  reproducible offline — not an LLM call.
- **Gate:** re-run the 16-paraphrase harness; spread must drop ≥3× and the verdict must stop
  flipping for any single input.

### A4 · Operating point + calibration honesty

- Re-tune the flag threshold **on realistic prevalence**, not the 63.5 %-positive corpus. Target
  the documented "max recall at precision ≥ 0.80" objective but report the resulting **flag rate**,
  because a triage tool must compress the queue.
- Compute **ECE and Brier** and write them into `metrics.json`. Either measure calibration or stop
  using the word — today `train.py:486-503` fits T=1.648 on validation with no calibration metrics
  anywhere in the repo.
- **Gate:** `metrics.json` contains ECE/Brier; README claims match the artifact exactly.

### A5 · Storage + observability hardening

- `PRAGMA busy_timeout` + bounded retry (kills the verified 5 s block → HTTP 500 on concurrent write).
- Secondary indexes: `overrides(report_id)`, `reports(date)`, and the facet `GROUP BY` keys.
- Date parameters on `/density`, `/reports`, `/patterns` + a cached time-series endpoint.
- `gate_schema_version` + one-shot backfill recompute (gates are pure functions; ~1 s).
- Adopt `structlog` + `prometheus-client` RED metrics, `pydantic-settings`, `hypothesis`.
  All four verified available for Python 3.14.
- **Gate:** concurrent-write test no longer 500s; `/metrics` scrapable; regression suite green.

### A6 · The probe harness becomes a real test

Convert `60-orchestrator-novel-probe.md` into a committed, runnable evaluation:
`tests/probe_process_safety.py`, n≥100 scenarios, IOGP-rule-stratified, ≥2 labelers where possible.
This is what makes every claim defensible. Until it exists, every number in that file is
directional and must be labelled as such.

---

## 2. Workstream B — Data & honesty

### B1 · De-saturate the demo database *(fixes the 71 % flag rate)*

The demo DB is seeded from the training corpus (measured top-1 near-dup cosine **0.99998**), so it
scores itself: `flag_rate 0.7095`, median 0.958, and 59.7 % near-dup banners.

- Rebuild the seed from **novel, negative-dominant** register-style text (routine observations,
  housekeeping, inspections) at approximately the domain-realistic mix (~20 % genuine precursors).
- Keep a small deliberately-memorised set so the near-dup "memory, not generalisation" feature
  still demonstrates — it is a genuine asset.
- Regenerate `artifacts/patterns/patterns.json` from live data: today all 197 cells are
  `sif_rate=1.0` with one identical lift 1.499, served *before* the live DB
  (`routes.py:329-331`), so numbers can never change.
- **Gate:** fresh-DB flag rate lands in a credible band (report the number, do not tune to a
  target), near-dup banner rate drops below ~10 %, and patterns change when reports are ingested.

### B2 · Claims correction *(fixes D4)*

Edit README + `HANDOFF.md`:
- Disclose gold P 0.976 was measured at **89.9 % gold prevalence** (vs 64.2 % test) — precision
  does not transfer.
- Surface the **INT8 export gate `pass:false`** (agreement 0.993, ΔAUC 0.1305) as a row in the
  honest-claims table, with the defence (op tuned on the int8 chain; local ΔAUC 0.0035; 97.7 %
  decision agreement).
- Merge the substitute-labeler disclosure out of `runs/run2/kb/` into the main README.
- Remove the unmeasured **"reviewer time saved"** claim.
- Correct **"OIL provides no dataset"** → no published link, data asserted by the PS.
- Fix `HANDOFF.md` theme (Smart Automation, not Miscellaneous), PS count, deadline, and delete the
  phantom TanStack/Recharts line.
- Correct stale throughput claims: 45.6 rows/s README line, ≥30/s comment at `routes.py:176`.
- **Gate:** every claim traces to a file; a reviewer cannot find an overclaim we did not volunteer.

---

## 3. Workstream C — Frontend structural rebuild

Stack decided in `docs/frontend-stack-decision.md`. Build against the **corrected API contract**
from Workstream A.

### C1 · Foundation
`@tanstack/react-table` + `react-virtual`, `react-query`, `react-router` HashRouter (URL-addressable
filter/tab state — also removes the shared-browser contention we observed), `sonner`,
`react-day-picker`, `cmdk`, lazy-loaded `recharts`, `@fontsource/ibm-plex-sans-devanagari`.

### C2 · The five surfaces (from `redesign-plan.md` §7)
1. **Triage queue** — risk-ordered sort, full pagination over all rows, body-text search, filters
   (rule / site / activity / date), keyboard-first, bulk select.
2. **Report detail & evidence** — **one unified card**; score + **stability indicator** + evidence
   spans + rule probabilities + active gates + source text, always visible regardless of band.
3. **Analytics** — time series first, then density/patterns with **n, Wilson CIs, and a min-n
   guard** (173 entities currently have n=1 and still rank); lift must carry its own CI and be
   labelled as such; expose `by=activity|contractor` facets.
4. **Ingest** — real progress tied to server rows done, cancel, ETA, **honest success/failure**,
   error rows, job history. (Today it declares failure while the server succeeds.)
5. **Decisions & actions** — rationale capture, real reviewer identity, correct/amend/undo,
   NDJSON export button, then CAPA fields (owner / due / status) so actions reach closure.

### C3 · Defect fixes that are not optional
- Remove debug internals from reviewer copy (raw `cosine=1.000 … index row syn-cs-e-0188`).
- Delete client-side `bandFor()` — the server owns the operating point.
- Delete the fabricated offline fallback (score 0.5 + fake gate); show an error state.
- Merge mock fixtures behind an explicit demo-mode flag (mock ids collide with live rows and
  silently swap invented model output onto a safety-critical screen).
- Legible evidence spans (underline / contrast); fix their absence on freshly classified reports.
- Consistent metadata (id, site, activity, contractor, event vs ingest date).
- Fix `100.0per 100` substitution; drop zero-signal columns ("Movement" on fresh load).
- A11y: restore focus rings on `tablist`/`tabpanel` (`outline: none` → WCAG 2.4.7 fail), fix the
  3.70:1 inactive-tab contrast, implement **or remove** the dead dark-mode variant, make the mobile
  tab strip and wide tables scrollable with affordances.
- Merge `gray-state-card`'s parallel EN/HI table into the phrasebook; remove ~20 dead tokens.

**Gate:** screenshot-every-screen visual QA after each milestone, `npm run build` clean, e2e green
against an **isolated DB**, no console errors, keyboard-only pass of the full decision flow.

---

## 4. Workstream D — Deliberately *not* doing

Stated so the boundary is defensible rather than accidental:

- **No retraining** for D3. Barrier gates cover the PS ask; retraining on new labels is a separate
  research cycle and would not be honest to ship unvalidated in this window.
- **No Indic translation.** Zero Devanagari rows exist in any DB we hold; demand is plausible but
  unproven. `IndicXlit` is rejected outright (pins `fairseq` → torch). The font fix in C1 is what
  we owe; translation is deferred and disclosed.
- **No OpenTelemetry, no broker queue, no Postgres, no rule-engine library, no StyleX/Astryx, no
  Skiper UI.** Each rejected on evidence in the two stack-decision docs.

---

## 5. Sequencing & verification gates

| Order | Workstream | Gate before proceeding |
|---|---|---|
| 0 | **S — test & packaging truth** | adversarial suite genuinely green · selfcheck 2 clean cycles · pytest collects >0 · 100k-char classify <1 s · threadpoolctl vendored and `install.sh` pip step proven offline |
| 1 | A1 runtime masking | paired-probe re-run; near-miss delta ≈0 |
| 2 | A2 barrier gates | hypothesis suite green; 0 fires on benign probes |
| 3 | A3 self-consistency | spread ≥3× tighter; no verdict flips |
| 4 | A4 + A5 | ECE/Brier in metrics.json; no 500 under concurrency |
| 5 | B1 + B2 | fresh DB flag rate credible; every claim traceable |
| 6 | C1–C3 | build clean; e2e green; visual QA per milestone |
| 7 | D-docs `overhaul-summary.md` | full offline `./run.sh` bring-up verified end to end |

Workstreams A and B can run in parallel with C1 scaffolding. **C2 must not start before S and
A1–A3**, because the verdict card's content depends on the new contract (stability, barrier gates)
and because there is currently no regression gate to protect the rebuild.

---

## 6. Main-objective coverage (original brief)

| Brief requirement | Status / where |
|---|---|
| Re-verify official PS text | Done — `01-ps-verification.md`; theme corrected to Smart Automation |
| Deep discovery + KEEP/REMOVE/ADD/MERGE | Done — `redesign-plan.md` §8 |
| Written discovery report | Done — 19 reports in `docs/discovery/` |
| Multimodal visual walkthrough + UX critique | Done — 4 agents, 94 screenshots, 4 visual reports |
| Frontend structural redesign + stack doc | Planned — C1–C3; `frontend-stack-decision.md` |
| Evaluate skiper-ui / motion-primitives / astryx + more | Done — `40-res-frontend-stack.md`; all three declined/deferred with reasons |
| Backend audit + modernization + stack doc | Done + planned — audit complete incl. `24-be-api.md`; fixes in A1–A5; `backend-stack-decision.md` |
| Evaluate modern alternatives per component | Done — `44-res-backend-oss.md` |
| Feature expansion (real-time flagging, feedback loop, Indic, audit trail, alerting) | Audit trail → C5; feedback loop → existing override path hardened; Indic → deferred honestly; real-time → classify is already <20 ms, so the queue is near-real-time by design; alerting → sonner + queue badges |
| `docs/overhaul-summary.md` | Pending — final deliverable after build |
| Verified end-to-end run instructions | Pending — must be re-verified after C |
| Visual QA evidence | Ongoing — `artifacts/qa-evidence/` |

---

## 7. The one-paragraph pitch this plan enables

*"We detect SIF precursors in OIL's UA/UC and near-miss reports using a fine-tuned ModernBERT
multi-task model running fully offline on CPU at ~18 ms. We found — and can show you — that a
score alone is not decision-grade: it is unstable under paraphrase and weak at procedural barrier
absence. So we did two things. We fixed the train/serve skew that made the model penalise
near-miss language, and we extended our deterministic humility gates to detect barrier failures
directly — no gas test, no LOTO, no permit, no fire watch — which is exactly the ask. Every
verdict now shows its evidence, its threshold, and how stable it is; every reviewer decision is
recorded with rationale and feeds future ground truth. Model proposes, HSE disposes."*
