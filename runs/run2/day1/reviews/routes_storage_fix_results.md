# SEV1/SEV2 fix results — app/storage.py + routes.py + ingest.py (+ schemas.py)

Fix agent for `routes_storage.md` findings. Date: 2026-09-08. All probes against
throwaway DBs under /tmp/sif-fix/ on test ports 8192-8195 (demo :8177 and
app/runtime.db untouched — migration verified on a *copy*). No git mutations.
Re-run harness: `routes_storage_fix_verify.py` (same dir; `storage` | `api PORT`).

Seed: 20,000 reports + predictions direct-SQL (density/concurrency don't need
real scores; api_smoke + near_dup_embed_check cover the real ingest path).
Model: `onnx:masked-v1/sif_multitask_int8.onnx`, `SIF_EXPLAIN_LLM=0`.

## SEV1-1 — shared sqlite3.Connection corruption → FIXED (RLock over ALL access)

`threading.Lock` (writes only) → `threading.RLock` covering every `self._conn`
access, reads included. RLock because the batch write nests session-index
appends under the same hold. Reads stay one-statement each, so hold times are
sub-ms; numpy matmuls (nearest/index) never hold the lock.

Reviewer's concurrency probe re-run (30 s each, 20k-row DB):

| mode | pre-fix (this machine) | post-fix |
|---|---|---|
| `readonly` | 1,100 HTTP 500; **810 silent wrong scores**; **611 phantom prediction-null**; 759 list 500; 51 density 500 | 2,382 reads + 4,180 density + 2,090 list — **0 failures of any kind** |
| `detector` (readers + explain-cache writers) | (reviewer: 434 500s, 222 phantom 404s) | 2,449 reads + 1,296 density + 433 writes — **0 failures** |
| `pageload_writer` (browser-parallel + 1 writer/0.25s) | (reviewer: 98.5% of loads ≥1 500) | **596/596 loads clean**, 111 writes ok |

Throughput cost of the lock (same 20k DB, 8 s windows):

| bench | pre-fix | post-fix |
|---|---|---|
| `GET /reports/100`, 1 thread | 3,512 rps, 0 err | 3,495 rps, 0 err (**-0.5%, noise**) |
| `GET /reports/100`, 8 threads | 2,099 rps, **2,196 err** | 3,924 rps, **0 err** (useful throughput UP ~87% — pre-fix "rps" counted fast 500s) |
| `GET /reports?limit=50`, 8 threads | 32.5 rps, **2,426 err** | 970 rps, **0 err** |

No measurable lock cost at demo QPS; correctness restored. Thread-local
connections were the alternative — rejected as the bigger diff (per-thread
connection lifecycle, schema-init fan-out, WAL checkpoint coordination) for
zero measured benefit at this scale.

## SEV2-2 — duplicate re-ingest → FIXED (per-row hash dedup + payload replay)

- `text_hash` = sha256 of whitespace-normalized text (ingest.py). New
  `report_hashes` table (schema v2; v1→v2 migration backfills existing rows —
  verified on a 5,050-row copy of the demo DB: 5,050/5,050 backfilled, boot
  clean, density covers all rows).
- Within-batch: dedup before classification (keep first), counted in new
  `IngestResult.skipped_duplicates`.
- Cross-request: sha256 of the canonical payload (`_payload_hash`); an
  identical re-POST returns the stored result with `idempotent_replay=true`
  and writes nothing. Different payload with overlapping rows → per-row skip
  at write time (counted in `skipped_duplicates`).

Probe (api-mode A1/A2): identical 8-row POST twice → store delta **exactly 8**
(not 16); overlapping 5-row payload → accepted 1 + skipped 4; whitespace-variant
within-batch dup → accepted 2 + skipped 1. The probe is nonce-randomized so it
is re-runnable against the same DB (two consecutive PASS runs).

## SEV2-4 — non-transactional ingest → FIXED (single-transaction batch)

Ingest is now two-phase: classify/embed/gates with no writes, then
`storage.add_ingest_batch()` commits all rows (+ hashes) in ONE transaction.
A failure rolls everything back and the client gets an honest 500
("ingest failed and was rolled back; nothing stored") instead of a silent
partial. Probe (storage-mode S2): injected failure at row 3 of 5 → exception
propagates, `count_reports()==0`, connection healthy, clean retry stores 5/5.
Behavior note: near-dup gates now see committed rows only, not earlier rows of
the same request (within-batch exact dups are skipped instead of bannered) —
documented in routes.py.

## SEV2-3 — override loop → FIXED (vocabulary + latest-wins export)

- `OverrideWrite` (strict write contract): `field` ∈ {sif_label, rules, notes};
  `new_value` validated per field (sif_label ∈ {sif_potential, not_sif_potential};
  rules = comma-separated known rule keys; notes non-empty). Reads stay lenient
  (`StoredOverride`) so pre-validation rows remain readable. History stays
  append-only (audit).
- `GET /api/review/export` (application/x-ndjson) → `export_overrides()`:
  latest-wins per (report_id, field), exact-dup collapse, `supersedes` lists
  the collapsed/overridden ids. Line schema documented on the method.
- Probe (api-mode A3): garbage field → 422; `maybe_sometimes` → 422; unknown
  rule key → 422; valid rules/sif_label → 201; export shows 1 winner with
  supersedes [2,3]. Storage-mode S4 covers the same at the table level.

## SEV3-1 — density/metrics full scan + N+1 → FIXED (SQL aggregate + cache)

- `/api/density` = one GROUP BY over the reports⋈predictions join (same
  semantics: missing prediction counts as 0.0; verified exact vs brute force,
  storage-mode S5). No more 100k-row silent cap.
- `/api/metrics/summary` = one scan, cached per (writes_version, threshold);
  invalidates on any report/prediction write.
- N+1 killed everywhere: `_row_to_report` now reads a LEFT JOIN row (one
  query for `get_report`/`list_reports`).

Latency at 20k rows (n=30, warm): **density p50 463.7→5.5 ms, p95 539.0→6.5 ms**
(target p95 <300 ms — 8× headroom); **metrics p50 451.9→0.3 ms, p95 521.5→0.4 ms**.
`reports?limit=1000` 18.8→16.4 ms (residual is pydantic serialization, not queries).

## SEV2-1 — index-misalignment boot-killer → hardened (hard fail kept)

Raise kept; message now names the recovery. Boot probe (10 vectors / 16 ids):
exit code 3, log line:
`corpus index misaligned: 10 vectors vs 16 ids under /tmp/sif-fix/badindex.
Recovery: re-copy a matched corpus_embeddings_fp16.npy + corpus_ids.jsonl pair,
or DELETE BOTH files to boot in session-only near-dup mode (degraded:
verbatim-corpus banners off).`

## Regression battery (all on test ports, final integrated tree)

- `SIF_TEST_PORT=8193 .venv/bin/python app/tests/api_smoke.py` → **PASS**
  (extended: idempotent-replay check [4b], override 422 + export checks [7];
  override values moved to the canonical sif_potential/not_sif_potential vocabulary)
- `.venv/bin/python app/tests/near_dup_embed_check.py` → **PASS**
- `.venv/bin/python app/tests/explain_check.py` → **PASS**
- `.venv/bin/python runs/run2/day1/reviews/routes_storage_fix_verify.py storage` → **PASS**
- `... api 8192` → **PASS** (twice consecutively — re-runnable)
- Reviewer probe `routes_storage_probe_concurrency.py` (readonly/detector/pageload_writer) → **all clean**

## Files changed

- `app/storage.py` — RLock everywhere; schema v2 (report_hashes, ingest_payloads)
  + v1→v2 migration; `add_ingest_batch` (single transaction); payload replay;
  LEFT-JOIN reads (N+1 dead); `density_aggregate`; `metrics_aggregate` + cache;
  `export_overrides`; actionable misalignment message
- `app/routes.py` — two-phase ingest with replay + within-batch dedup + honest
  rollback error; density/metrics on aggregates; `GET /api/review/export`;
  review POST uses strict contract
- `app/ingest.py` — `normalize_text` + `text_hash`
- `app/schemas.py` — `OverrideWrite` strict model + vocabulary constants;
  `IngestResult.skipped_duplicates` / `.idempotent_replay`
- `app/tests/api_smoke.py` — canonical override vocabulary; replay + 422 + export checks
- `runs/run2/day1/reviews/routes_storage_fix_verify.py` — new, the re-run harness

Not done (out of my item's scope): SEV3-3 (column_mapping case), SEV3-4
(records+csv precedence), SEV3-2 (CSV formula-injection — no export sink yet;
the new /review/export is JSONL not CSV), SEV3-5 (health corpus-rows field).
Demo server restart with the new code is a wave-level decision — migration on
boot is verified safe on the runtime.db copy.
