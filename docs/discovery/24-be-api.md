# 24 — Backend API, schemas, ingestion, tests & packaging audit (grounded)

> **Superseded historical audit (2026-09-25).** The present-tense findings below are an audit snapshot, not current status. Resolved since that audit: `threadpoolctl` is now in `packaging/wheels/`; `packaging/selfcheck.sh` now checks stable dashboard markers (`id="root"` and a served JS bundle) rather than the stale title; and pytest configuration in `pytest.ini` now collects 10 tests. Other findings below have not been revalidated by this note and must not be read as current without checking. The original audit details are retained as history.

Audit date 2026-09-25. Read-only audit; the only writes were /tmp copies and this file.
Live demo stack at 127.0.0.1:8177 was never touched; port 8183 avoided; all probes ran on 8215 against a /tmp copy of `artifacts/demo/demo_pre.db` with `SIF_MODEL_PATH=artifacts/models/masked-v2/sif_multitask_int8.onnx`. `/api/health` on the probe reported `"classifier":"RealOnnxClassifier"` (not Mock). Probe server was killed after use (verified down).

## Verified file inventory (my own `wc -l` / `stat` this session)

Every path and line count matched the authoritative inventory **except one inventory claim**:

| Path | Claimed | Measured | Match |
|---|---|---|---|
| app/routes.py | 402 | 402 | yes |
| app/schemas.py | 239 | 239 | yes |
| app/ingest.py | 101 | 101 | yes |
| app/main.py | 72 | 72 | yes |
| app/config.py | 83 | 83 | yes |
| app/classifier.py | 617 | 617 | yes |
| app/storage.py | 642 | 642 | yes |
| app/gates.py | 423 | 423 | yes |
| app/explain.py | 417 | 417 | yes |
| app/embedder.py | 163 | 163 | yes |
| app/report_metadata.py | 43 | 43 | yes |
| app/__init__.py | 1 | 1 | yes |
| tests/adversarial_suite.py | 431 | 431 | yes |
| dashboard/e2e/dashboard.spec.ts | 101 | 101 | yes |
| run.sh | 175 | 175 | yes |
| spec/label_spec.yaml | 281 | 281 | yes |
| requirements.txt / -dev.txt | 12 / 12 | 12 / 12 | yes |
| packaging/install.sh / make_tarball.sh / selfcheck.sh / manifest.md / PENDRIVE.md | 1677 / 2393 / 4120 / 5783 / 4339 bytes | same | yes |

**Inventory correction:** `tests/adversarial_suite.py` is *not* "the only python test file". `app/tests/` exists and holds 6 more Python check scripts (1,152 LoC): `api_smoke.py` (257), `explain_check.py` (286), `near_dup_embed_check.py` (108), `onnx_bench.py` (109), `onnx_classifier_check.py` (139), `postreview_fix_check.py` (253). They are runnable stdlib self-check scripts, not pytest files. `app/*.py` totals exactly 3,203 LoC as stated.

### Commands actually run
`wc -l` on all inventory files; `ls`/`stat` on packaging + artifacts; `pytest --collect-only -q` (repo root, then `--ignore=packaging`, then scoped `tests/` and `app/`); ran `tests/adversarial_suite.py`, `app/tests/api_smoke.py`, `app/tests/explain_check.py`, `app/tests/onnx_classifier_check.py`, `app/tests/near_dup_embed_check.py`, `app/tests/postreview_fix_check.py` (all on port 8215 or offline, real int8 model; e2e Playwright NOT run — it mutates state and 8177 is frozen); uvicorn probe on 8215: health + ~30 curl/python probes (malformed JSON, empty/whitespace text, wrong types, non-UTF8 bytes, unknown fields, hostile CSVs, oversized 200k-char paste, review vocabulary, bulk 500-row ingest timing); direct gate profiling script; `pkill` probe server + verified down; `git status --porcelain` confirmed no tracked file modified.

## What exists today — endpoint inventory

FastAPI app in `app/main.py` (`create_app`, line 20), `/api/*` router from `app/routes.py`, `/api/health` registered inline (main.py:40-49), `dashboard/dist` mounted at `/` last (main.py:56-57). No CORS middleware, no auth, host default 127.0.0.1:8177 (config.py:57-58).

| Method+Path | Params | Request | Response | Side effects | UI calls it? |
|---|---|---|---|---|---|
| GET /api/health | — | — | HealthOut (status, api_version, model_version, classifier, n_reports, n_overrides) | none | yes (App.tsx:28, density.tsx:71) |
| POST /api/classify | explain, llm, persist (all bool query) | ReportIn | PredictionOut (+explanation when ?explain=1, +report_id when ?persist=1) | **writes only when persist=1** (add_ingest_batch, routes.py:110-122); explain cache write (precomputed table) | yes — always `?persist=1` (api.ts:279; explain variant `?persist=1&explain=1&llm=0`) |
| POST /api/ingest | — | IngestRequest {records | csv, column_mapping?, source} | IngestResult (received/accepted/rejected/report_ids/errors/skipped_duplicates/idempotent_replay) | single-transaction writes (storage.add_ingest_batch) + replay entry | yes — CSV path only (density.tsx:115); the `records` client helper (api.ts:315-322) has **zero call sites** |
| GET /api/reports | limit (1..1000, default 50), offset (>=0) | — | list[StoredReport] | none | yes (limit always 200; offset never sent) |
| GET /api/reports/{id} | — | — | StoredReport / 404 | none | **NO call site** (api.ts getReport is dead) |
| GET /api/reports/{id}/explanation | — | — | ExplanationOut (404 missing, 409 no-prediction, routes.py:253-254) | explain-cache write (2 ollama attempts × 8 s worst case, explain.py:329) | yes (triage-card.tsx:234; client timeout 12 s, api.ts:359) |
| GET /api/density | by (site|activity|contractor) | — | list[DensityRow] | none | yes (density.tsx:71,117) |
| GET /api/rules | — | — | list[RuleInfo] (9 keys) | none | only indirectly (api.ts getReports calls getRules) |
| GET /api/patterns | min_n>=1, limit<=100, kind (site_activity|activity_barrier) | — | list[PatternRow] | none (reads artifacts/patterns/patterns.json per request) | yes (patterns.tsx:23) |
| POST /api/review | — | OverrideWrite (field ∈ sif_label|rules|notes + value vocabulary) | StoredOverride 201 / 404 / 422 | append-only override row | yes (App.tsx:55) |
| GET /api/review | report_id? | — | list[StoredOverride] | none | yes (App.tsx:30,61) |
| GET /api/review/export | — | — | NDJSON text, latest-wins per (report_id, field) | none | **NO UI surface** (confirmed: zero references outside api_smoke) |
| GET /api/metrics/summary | — | — | MetricsSummary | none | **NO UI surface** (api.ts getMetricsSummary has zero component callers) |

Mutating endpoints: POST /classify?persist=1 (always used by UI), POST /ingest, POST /review. Read-only everything else. The UI never calls /review/export, /metrics/summary, /reports/{id}, or the records-flavored /ingest.

## Findings

1. **BLOCKER — packaging offline install cannot succeed: `threadpoolctl` wheel missing.** requirements.txt:8 pins `threadpoolctl>=3`; `ls packaging/wheels/` (37 wheels) contains no threadpoolctl wheel. `packaging/install.sh:29` runs `pip install --no-index --find-links=packaging/wheels -r requirements.txt` → pip fails resolving threadpoolctl → the claimed one-command offline bring-up is broken today. Same gap breaks `packaging/pendrive/assemble_runtimes.sh:20` (Linux runtime installs from `packaging/wheels`, sanity import includes threadpoolctl at line 20's import check). The win-wheels copy (`packaging/pendrive/dl/win-wheels`) does include it (verified), so only the shared wheels dir is stale.

2. **BLOCKER — hostile long input stalls the single-worker server ~51 s (quadratic gates).** Measured: POST /classify?persist=1 with a 194,400-char text → **51.3 s** wall (200 OK). Direct profiling of `run_gates` on the same register of text: 10k chars → 0.62 s, 50k → 3.13 s, 100k → 11.26 s (quadratic). Root cause: the classifier caps input at 10k chars (classifier.py:77-80, classifier.py:441) but **gates run on the full text** (routes.py:109,195), and `gate_negation`/`gate_severity_watch` call `_match_token_starts` (gates.py:151-159) which, per regex match, re-scans the whole text with `_TOKEN_RE.finditer` to map char→token index — O(matches × tokens). With ~84-char periodicity the negation cue matches scale linearly with text length, so cost is O(n²). Impact: one hostile paste (or one hostile CSV row) freezes the single uvicorn worker for ~a minute; no gate blocks, nothing crashes, but the "no hang" claims (classifier.py:79, gates.py:368, postreview_fix_check.py:12) are false at the API layer. Fix is a one-line pass over the text: compute token offsets once per text.

3. **BLOCKER — README/packaging throughput claim is 6× off.** Measured this session on the real int8 artifact + demo_pre copy: 500-row money-beat CSV → accepted=500, wall **68.9 s = 7.3 rows/s**. README.md:122 claims "**45.6 reports/s** … SLA ≥30/s"; api.ts:327/338 claims "measured 37 rows/s / ~15 s server-side". routes.py:173 admits the old path measured 5.33/s vs "the >=30/s SLA" — the shipped batched path does not meet the SLA either, because int8 forces per-window solo runs (`supports_exact_batch=False`, classifier.py:313, 452-453), voiding the D25 batching gain. UI still survives (90 s budget, api.ts:333) but with ~77% margin burned.

4. **MAJOR — the adversarial suite is stale and fails 18/18.** tests/adversarial_suite.py:283 `GATE_ORDER` lists 9 gates; `run_gates` (gates.py:398-409) now returns 10 (severity_watch added, gates.py:320). run_case asserts the gate set (line 334) → every case fails with "gate set mismatch". Ran with the real model on 8215: 18 failures, all gate-set mismatches (the actual gate behavior looked right — negation GRAY on #1, drill GRAY on #8, near_dup BADGE on #9/#14, WC watch GRAY on #18). README.md:127 "18/18 PASS" is false today. One-line fix: add `severity_watch` to GATE_ORDER (and the suite's default port 8177 collides with the live demo — docstring warns, but the default should not be the demo port).

5. **MAJOR — selfcheck.sh cannot pass today (title drift).** selfcheck.sh:70 greps the served dashboard HTML for `SIF-Precursor`; dashboard/dist/index.html contains **0** occurrences (title is "Safety Report Triage — OIL India", index.html:10; the JS asset also has 0). The check for `id="root"` (line 69) still passes. selfcheck also silently requires `jq` and `bc` (lines 40, 45-46, 55-64) with no preflight. Result: the claimed "two clean start→health→classify→stop cycles" proof fails at the dashboard step on every cycle.

6. **MAJOR — `rationale` contract broken three ways (verified).** API accepts/stores it: schemas.py:148 (OverrideIn.rationale), storage.py:364-369 writes it, storage.py:543 exports it in the gold JSONL. Frontend: `adaptOverride` (dashboard/src/lib/api.ts:192-203) **drops** it on GET; `postReview` supports `rationale?: string` (api.ts:410) but the only caller (App.tsx:55-60) never passes it; `types.ts:132-141 OverrideOut` has no rationale field. Net: rationale is only ever written by api_smoke; UI reviewers cannot record or see it. Additionally App.tsx:58 sends `old_value: current.prediction.band` — a UI band string ("HIGH"/"MODERATE"/"LOW"), not the previous sif_label value the API contract intends — polluting the future-gold lineage's `old_value` column.

7. **MAJOR — two more self-check scripts fail on missing artifacts.** (a) `onnx_classifier_check.py` aborts at line 65: asserts `artifacts/models/masked-v1` is a real ONNX artifact; the dir does not exist (only masked-v2 ships; also classifier.py:34 comment cites masked-v1/train.py). (b) `near_dup_embed_check.py` fails at line 50: `artifacts/corpus/train_final_v2.jsonl` missing — `artifacts/corpus/` no longer exists at all. (c) `postreview_fix_check.py` passes sections 1-3 (rule-head order, D27 batch invariance, 200k-cap + badge, valley gating) then crashes at line 161 on missing `artifacts/corpus/test.jsonl`. The dev corpus was removed from the repo but the checks still reference it.

8. **MAJOR — 500 escape via `/api/patterns`.** `_precomputed_patterns` (routes.py:289-313) does an unguarded `json.loads(path.read_text())` (line 297) and direct `data["site_x_activity"]` / `data["activity_x_barrier"]` key access (line 298) on `SIF_PATTERNS_FILE` (default artifacts/patterns/patterns.json, 96,476 bytes — comment at line 291 says "~50 KB", ~2× stale). A corrupt/truncated patterns file → JSONDecodeError/KeyError → unhandled 500 on every request until the file is fixed. Also any unexpected exception elsewhere in routes escapes as a raw 500 (no global exception handler); ingest write failures are converted to an honest 500 (routes.py:204-211) and classify-persist failures are swallowed by design (routes.py:118-122).

9. **MINOR — error schema is fastapi-default and non-uniform.** Two shapes: pydantic 422s return `{"detail":[{type,loc,msg,input,ctx}]}`; HTTPException paths (404 report not found, 409 no prediction, 422 from ingest parse ValueError, 500 rollback) return `{"detail": "<string>"}`. Probe results: empty text→422; whitespace-only text→**200** (scored; only min_length gate grays it); wrong type/null text→422; unknown body fields→silently ignored (no `extra="forbid"` on ReportIn); malformed JSON→422 json_invalid; raw non-UTF-8 bytes→422 json_invalid (no 500); array body→422; `/api/reports/notanint`→422; unknown route→404 (falls through to the StaticFiles mount); POST on a GET route→405. No 500 was observed from any malformed-input probe; the only observed 500 sources are the patterns file (finding 8) and deliberate ingest rollback.

10. **MINOR — ingestion validation gaps (none crash).** `parse_csv` (ingest.py:52-54) uses `csv.DictReader` with no size/row cap; hostile CSVs probed: unclosed quote → accepted as one row; ragged rows → accepted (extra columns ignored via DictReader); header-only → received=0. `ReportIn.text` has `min_length=1` (schemas.py:52) but **no max_length** — oversize relies on the 10k classifier cap + long_input badge; the DB stores the full text (a 200k-char paste stores 200k chars). `ingest.py:88-89`'s helpful "missing text column (aliases: …)" ValueError is unreachable: whitespace-only cells are stripped to None in `map_columns` (line 47) and pydantic rejects None before the branch — so a CSV with no text column yields the misleading error "text: Input should be a valid string" (observed), never the alias hint. records-mode accepts rows of any shape; non-string text → per-row error (observed "text: Input should be a valid string").

11. **MINOR — SQL parameterisation:** every statement uses `?` placeholders (storage.py passim) **except** `density_aggregate` (storage.py:447-455) which f-strings the facet name — but it is double-gated: route regex `pattern="^(site|activity|contractor)$"` (routes.py:266) + `self._DENSITY_FACETS` whitelist + ValueError (storage.py:445-446). No injection path found. Ingest payload hash idempotency is real (observed replay in api_smoke [4b]).

## Stale claims

| Quoted text | Location | Reality |
|---|---|---|
| "**45.6 reports/s** (5,050-row CSV … SLA ≥30/s)" | README.md:122 | Measured this session: **7.3 rows/s** (68.9 s for 500 rows, int8, 4,548-row DB) |
| "inline single-everything measured 5.33/s vs the >=30/s SLA" | app/routes.py:173 | The shipped batched path measures 7.3/s — still below the quoted 30/s SLA (int8 per-window solo runs void batching, classifier.py:313) |
| "the 500-row money beat takes ~15 s server-side at the measured 37 rows/s" | dashboard/src/lib/api.ts:327 (repeated :338) | Measured 68.9 s / 7.3 rows/s; 90 s client budget still holds |
| "every call is bounded by the 8 s timeout" / "up to 2x the timeout" | app/routes.py:102-105 | Per-call cap is 8 s (config.py:82) but `ollama_reword` makes **2 attempts** (explain.py:329) → worst-case wall ≈ 16-17 s; consistent with the reported 16-17.5 s measurement. Not re-measured (ollama not running today; explanation endpoint returned in 75 ms with ollama down) |
| "A cold call pays one bounded ollama attempt server-side (8s cap), so the client waits up to 12s" | dashboard/src/lib/api.ts:354-355 | The server tries **twice** (explain.py:329); 2×8 s > the 12 s client timeout, so a cold slow-reword result would be discarded client-side (falls to mock/null) while the server still caches it |
| "one 200k-char paste … scores in <5s, no 15.9s hang" | app/tests/postreview_fix_check.py:12 (check at :141); "hanging 15.9s" app/gates.py:368; cap rationale app/classifier.py:77-80 | True for the **classifier alone** (10k cap; the check passes) but false for the **API path**: gates run on the full text and stall ~51 s (finding 2) |
| "Adversarial suite / packaging: 18/18 PASS" | README.md:127 | Suite fails 18/18 on gate-set mismatch (finding 4) |
| "`tests/` | Golden regression, adversarial suite, parity checks" | README.md:61 | tests/ contains only adversarial_suite.py; no golden regression or parity checks anywhere |
| "app/tests/postreview_fix_check.py" as passing proof (classifier.py:263) + "masked-v1" references (classifier.py:34, onnx_classifier_check.py:3,64-69) | — | masked-v1 artifact deleted; the check fails at line 65 today |
| "~50 KB so re-parsing is noise" | app/routes.py:291 | artifacts/patterns/patterns.json is 96,476 bytes (~94 KB) — 2× the comment, harmless |
| docstring invocation contract `num_predict: 400` | app/explain.py:10 | Code sends `num_predict: 300` (explain.py:338) |
| "MiniLM … **PENDING** … until then the index runs the deterministic hashed n-gram embedding" | packaging/manifest.md:32-38 | MiniLM is live: vendored at artifacts/embeddings/minilm, loaded at startup (embedder.py:48-90); corpus index 70,398×384 loaded (storage.py:193-215) |
| "Model artifacts … 2.1M now + **ONNX pending** … est. ~280M once the INT8 ONNX lands"; "Tarball total: ~120M" | packaging/manifest.md:13,21 | ONNX landed: masked-v2 dir is 720M (int8 152M + fp32 .data 596M); embeddings 142M excluded from the tarball entirely |
| sizes table "37 wheels … 116M" | packaging/manifest.md:16 | 37 wheels exist but the set is broken: no threadpoolctl wheel → offline install fails (finding 1) |
| "bulk ingest ≥500 reports/s classify-only"; "one-command `docker compose up`"; "Postgres 16 (+pgvector …)" | HANDOFF.md:233, 236, 197-198 | Historical planning doc; runtime is SQLite, no docker, no Postgres (storage.py D5). Superseded, but it is the file a newcomer reads first |
| "all 9 IOGP rules" is consistent everywhere; "10 sentinel gates" (README.md:31) | README.md:31 | Correct vs gates.py (10 gates); but "codes" is not a gate name (min_length is) — cosmetic |
| selfcheck grep 'SIF-Precursor' | packaging/selfcheck.sh:70 | dist title is "Safety Report Triage — OIL India"; 0 occurrences → selfcheck fails (finding 5) |

## Test coverage truth

**pytest collects 0 tests.** `pytest --collect-only -q --ignore=packaging` → "no tests collected". Without the ignore it reports 3 collected + 11 collection errors — all from `packaging/pendrive/staging/**` vendored site-packages polluting the rootdir (repo's own code contributes nothing). The repo has NO pytest suite; `requirements-dev.txt` lists pytest, unused.

Runnable self-checks (real int8 model; suite/smoke spawn their own throwaway servers on SIF_TEST_PORT):

| Script | Result this session | What it actually asserts |
|---|---|---|
| app/tests/api_smoke.py (257 LoC) | **PASS** (~35 checks) | health; classify schema + span invariant + determinism; all **10** gate names incl. severity_watch (:120-123); codes/drill/language/WC-watch gates; 5-row CSV ingest + idempotent replay; reports/density/rules/patterns/metrics; near-dup on re-paste; review round-trip incl. 404 + 422 vocabulary + export JSONL; paste-persist (stateless stores nothing; re-paste dedups) |
| app/tests/explain_check.py (286 LoC) | **PASS** | template correctness; hallucinated-span rejection + retry; cache round-trip; endpoint wiring (llm disabled); 404 on missing report |
| tests/adversarial_suite.py (431 LoC) | **FAIL 18/18** | 18 hostile inputs vs gates; fails purely on the stale 9-gate GATE_ORDER (finding 4); per-case behavior itself looked correct |
| app/tests/onnx_classifier_check.py (139 LoC) | **FAIL** | contract of the real artifact; dies at masked-v1 assertion (artifact deleted) |
| app/tests/near_dup_embed_check.py (108 LoC) | **FAIL** | MiniLM pooling quickstart matrix + corpus index banner scenarios; dies on missing artifacts/corpus/train_final_v2.jsonl |
| app/tests/postreview_fix_check.py (253 LoC) | **FAIL partway** | SEV1-1/SEV1-2/SEV2-1/D27 + 200k-cap + badge checks PASS, then dies on missing artifacts/corpus/test.jsonl (:161); never reaches span-quality/explain-fallback/drill sections |
| app/tests/onnx_bench.py (109 LoC) | benchmark only (no asserts) | latency/throughput measurement |

**Completely uncovered by any test:** malformed/hostile CSV paths (unclosed quotes, ragged rows, missing text column — none of the suites fire them); the quadratic-gate stall (no size-latency guard); `/api/patterns` corrupt-file 500; `GET /reports/{id}/explanation` cold+ollama latency budget vs the UI's 12 s timeout; `OverrideWrite.rules` vocabulary round-trip (only sif_label/notes exercised); density/patterns pagination & min_n/limit bounds; `?llm=0` vs `llm=1` semantics on /classify; the UI band-vs-label `old_value` mismatch; oversized input beyond the 10k cap at the API level; non-UTF8 body handling. The e2e Playwright suite (5 tests, dashboard/e2e/dashboard.spec.ts — counted 5 `test(`) covers the UI happy paths + offline fallback + CSV import, and is deliberately not run here (mutating, live stack).

## Packaging truth

- **`./run.sh` (repo checkout): sound by inspection; NOT executed** (it binds 8177 — the frozen demo stack). Preflight checks venv + dist + model resolution (masked-v2 int8 first, run.sh:97-107), optional ollama (reuses a live server, never kills it), 60 s health wait, `--stop` pidfile hygiene. The equivalence check that does exist and passes end-to-end is api_smoke (real model, throwaway DB, 200).
- **packaging/install.sh: BROKEN today** — cannot resolve `threadpoolctl` from packaging/wheels (finding 1). Python 3.14-exact requirement enforced (install.sh:19-21).
- **packaging/selfcheck.sh: BROKEN today** by the 'SIF-Precursor' grep (finding 5). The rest of the two-cycle check (health, classify contract + span invariant via jq, dashboard asset, stop + port-free) is genuinely meaningful — it proves what it claims once the grep is fixed.
- **packaging/make_tarball.sh: stale payload.** Ships `app`, `dashboard/dist`, `artifacts/models/masked-v2` (720M incl. fp32 .data — "5.6 GB → ~0.7 GB" comment ok), `artifacts/patterns`, spec, wheels — but **not** `artifacts/embeddings/` (MiniLM model + corpus index). A tarball target boots with HashedEmbedder fallback + session-only near-dup (embedder.py:132-134, storage.py:199-202) — silently degraded near-dup vs the demo, contradicting manifest.md:28's claim that the demo "needs no corpus files" while PENDRIVE.md:14-16 (newer, Sep 10-11) correctly includes MiniLM + corpus index + demo_pre.db in the pendrive payload.
- **manifest.md sizes**: masked-v2 720M on disk vs "2.1M + ONNX pending"; tarball est. ~280M is now ~850M+ if embeddings were included (they are not); wheels missing threadpoolctl. The "Deliberately excluded" table lists `artifacts/corpus/` (270M) which no longer exists in the repo at all.
- **PENDRIVE.md**: Linux path "fully tested" per its own text (2026-09-10/11); Windows "structurally verified … **not execution-tested**" — honest. The built staging tree exists under packaging/pendrive/staging (a full vendored runtime copy inside the repo that also breaks pytest collection from the root).
- Referenced run artifacts all exist: runs/run2/ARCHITECTURE.md, DECISION_LOG.md, day2/ship_decision.md, day2/latency_v2_final.md, phase1-architecture/demo-red-teamer.md, kb/KNOWLEDGE_BASE.md, artifacts/gold/gold_metrics_final.md, threshold_report.md, patterns.json. **Missing:** artifacts/models/masked-v1/, artifacts/corpus/ (both still referenced by code/tests).

## Dead code / deletion list

- `app/routes.py:46-47` — `FLAG_THRESHOLD = 0.5`: never read (explain.py:41 comment references it; both constants duplicate the classifier's `flag_threshold()` fallback).
- `app/ingest.py:88-89` — unreachable "missing text column" ValueError (pydantic min_length rejects empty/None text first; map_columns strips whitespace to None).
- `app/ingest.py:100-101` — `dumps_jsonl`: zero callers repo-wide.
- `app/storage.py:229-232` — `add_prediction`: zero callers outside the Protocol. `add_report` is used only by app/tests/near_dup_embed_check.py:94.
- `app/storage.py:583-614` — `Storage.nearest()`: runtime near-dup path uses `nearest_base_batch` + `nearest_session`; `nearest()` is test-only.
- `app/config.py:70` — `embed_dim: int = 384`: unused (embedder.py:34 defines its own constant).
- `app/config.py:43` default `app/artifacts/model.onnx` (+ run.sh:103 glob) — `app/artifacts/` does not exist; dead fallback path.
- dashboard/src/lib/api.ts — `getReport` (:258), `getMetricsSummary` (:420), `ingest()` records-helper (:315): zero component call sites. Either wire /metrics/summary into the UI or delete.
- API fields with no UI consumer: `StoredReport.report.source`, `IngestResult.skipped_duplicates`/`idempotent_replay` (absent from types.ts:156-162), `OverrideIn.rationale` (dropped in adapter), `IngestRequest.column_mapping` (UI never sends), `GET /api/reports` `offset` param, `PatternRow.rule/kind` partially used.
- `packaging/wheels/` — not deletable, but **must add the missing threadpoolctl wheel** (or drop the requirement).
- `requirements.txt` `pandas>=2` + `pyarrow` (lines 11-12): imported nowhere in `app/` (only install.sh's import check); ~62 MB of the 116M wheels shipped to a runtime that never uses them. Dev-only.
- `app/runtime.db` (+ -shm/-wal, 16M): dev DB, gitignored, in-tree.
- `packaging/pendrive/staging/` — full payload + two vendored CPython runtime trees inside the repo; breaks `pytest --collect-only` from the root and bloats the tree.
- masked-v1 references: classifier.py:34 comment, onnx_classifier_check.py:64-69 (update to masked-v2 or drop).

## Recommendation

- **KEEP** FastAPI+SQLite storage layer, gate architecture (10 gates, error-swallowing run_gates), span invariant, explain template+cache, idempotent ingest — all verified working against the real artifact.
- **FIX (blockers):** add the threadpoolctl wheel to packaging/wheels (or drop the pin); fix selfcheck.sh:70 to grep the actual title (or fix the dist title); compute token offsets once in `_match_token_starts` to kill the quadratic gate path (gates.py:151-159) and cap gate input at MAX_INPUT_CHARS; add severity_watch to tests/adversarial_suite.py:283.
- **ADD:** a size guard at ingest (max chars/rows) or document the quadratic ceiling; unify the error body (`{"detail": str}` vs `{"detail": [...]}`) or document both; guard the patterns.json parse (routes.py:297-298) with a try/except returning [].
- **MERGE:** manifest.md with reality (MiniLM now vendored under artifacts/embeddings, model sizes, wheel list) — or fold manifest.md into PENDRIVE.md and deprecate the tarball path; the pendrive is the maintained artifact and PENDRIVE.md:14-16 already documents the correct payload.
- **REMOVE:** FLAG_THRESHOLD, dumps_jsonl, add_prediction, embed_dim, the app/artifacts default, pandas+pyarrow from runtime requirements, masked-v1 references, packaging/pendrive/staging from the repo tree (or exclude it from pytest rootdir).
- **UPDATE (stale docs):** README.md:122 throughput row (measure and re-quote; today 7.3/s), README.md:127 18/18, README.md:61 tests/ row, routes.py:173 SLA comment, api.ts:327 37-rows/s comment, explain.py:10 num_predict, gates.py:368 "15.9s" wording, manifest.md sizes/pending sections, HANDOFF.md header note that Part C (Postgres/docker) is superseded by runs/run2/ARCHITECTURE.md.