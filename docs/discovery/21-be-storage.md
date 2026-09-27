# 21 — Persistence + vector/near-dup layer audit

Role: Phase 0 discovery — persistence + vector/near-dup layer audit (PS 26165, OIL India).
Date: 2026-09-25. Read-only audit; the only writes were to this file and to /tmp copies of the DB.

## Files read (with line counts)

| File | LoC | Why |
|---|---|---|
| app/storage.py | 642 | primary subject |
| app/config.py | 83 | Settings: db path, near_dup_threshold, embed dirs |
| app/ingest.py | 101 | text_hash / normalize_text used by report_hashes |
| app/routes.py | 402 | every caller of storage (density, patterns, review/export, metrics) |
| app/main.py | 72 | SQLiteStorage construction in lifespan |
| app/embedder.py | 163 | MiniLM ONNX embedder feeding the index |
| app/gates.py | 423 | gate_near_dup → nearest_base_batch/nearest_session call sites |
| app/schemas.py | 239 | StoredReport/PredictionOut/OverrideWrite contracts |

Tools/commands run: `sqlite3` (schema dump, `EXPLAIN QUERY PLAN`, PRAGMAs, counts on /tmp copies), `curl -w %{time_total}` timing loops, venv-python timing scripts (corpus-index load, storage init, matvecs, 5k-row insert, forced-rollback test, cross-process lock test, 13-way concurrent burst). Isolated server on **port 8212 only** (`cp artifacts/demo/demo_pre.db /tmp/qa_sto.db`), killed afterwards, all /tmp artifacts removed. The live 8177 stack was never touched; port 8183 (stale foreign process) avoided.

## What exists today

### Schema (storage.py:56-112; verified byte-identical in artifacts/demo/demo_pre.db via `sqlite3 .schema`)

Nine objects, all `CREATE TABLE IF NOT EXISTS`, no ORM, no Alembic (declared at storage.py:1-5, "DECISION_LOG D5"):

| Table | Columns | Why it exists |
|---|---|---|
| `schema_meta` | id=1 CHECK, version | gates the inline v1→v2 migration (storage.py:163-172) |
| `reports` | id AUTOINCREMENT PK, text NOT NULL, date/site/activity/contractor nullable, source NOT NULL dflt 'api', created_at | narrative + optional structured facets (CSV ingest may lack facets) |
| `predictions` | report_id INTEGER PK REFERENCES reports(id), sif_score REAL, rule_probs/gate_states/evidence_spans TEXT (JSON), well_control INT, model_version, created_at | frozen model output, 1:1 with reports, `INSERT OR REPLACE` re-classify (storage.py:234-251) |
| `overrides` | id, report_id FK, field, old_value, new_value, labeler, source dflt 'override', rationale, created_at | append-only review log = future gold + audit trail |
| `embeddings` | report_id PK REFERENCES reports(id), vector BLOB (fp32 `.tobytes()`, 1,536 B/row) | persistence for the session near-dup tier across restarts |
| `precomputed` | key TEXT PK, payload TEXT, created_at | Ollama-reword cache (keys `explain:<sha256>` — 63 rows in demo_pre.db) + pattern payloads (app/explain.py:20,138) |
| `report_hashes` | hash TEXT PK, report_id FK | normalized-text sha256 dedup, SEV2-2 (ingest.py:57-66) |
| `ingest_payloads` | hash TEXT PK, result TEXT = full IngestResult JSON | byte-identical re-POST replay (routes.py:133-154) |
| `sqlite_sequence` | — | AUTOINCREMENT bookkeeping (reports, overrides) |

Row counts (measured `SELECT COUNT(*)`): **demo_pre.db** 4,548 reports / 4,548 predictions / 4,548 embeddings / 0 overrides / 1 ingest_payload; **live app/runtime.db** 5,056 / 5,056 / 1 override / 4 payloads, sources: pre-state-seed 4548, dashboard 500, adv_seed 2, live-paste 1, smoke 5. **Indexes: none beyond implicit PK/unique autoindexes** (`sqlite_autoindex_report_hashes_1`, `precomputed`, `ingest_payloads`). No index on `overrides.report_id`, no index on `reports.date|site|activity|contractor`, no index on `predictions.sif_score`.

Migration: none beyond `CREATE TABLE IF NOT EXISTS` + the one-shot v1→v2 backfill (storage.py:163-172). SCHEMA_VERSION=2. No downgrade guard: `if version < 2` only — a v3 DB opened by this code proceeds silently until a query hits a missing column.

### Near-dup index — two tiers, numpy brute force

- **Base tier**: `artifacts/embeddings/corpus_embeddings_fp16.npy` = 70,398×384 fp16 (54 MB on disk, per corpus_index_meta.json), upcast to fp32 in RAM at startup = **108 MB** (storage.py:193-215). Loaded via `np.load(mmap_mode="r").astype(np.float32)` + 70,398-line `corpus_ids.jsonl` parse. **Measured: 0.50 s total** (0.22 s npy+upcast, 0.30 s ids parse; re-measured through real `SQLiteStorage(db, artifacts/embeddings)` init = 0.50 s). Not the startup bottleneck; the full 6.78 s spawn→healthy boot (measured, real ONNX + corpus idx + 4,548-row DB) is dominated by ONNX session load.
- **Session tier**: embeddings table warmed lazily into a preallocated 4,096-row fp32 buffer on the **first** near-dup query after restart (storage.py:349-360); measured warm = **57.4 ms** for 4,548 rows. `add_ingest_batch`/`add_embedding` append in place, O(1) amortized, doubling via `np.concatenate` when full (storage.py:339-347).
- **Persistence**: yes — the embeddings table is the persistence layer; the in-RAM buffer is a cache. The base tier is rebuilt only offline (`data_pipeline/embed_corpus.py`; meta logs 1,736 s for 70k rows = 40.5 rows/s). **No runtime path ever adds a row to `_base_mat`** — ingested rows are covered only by the session tier.
- **Query costs (measured this session, BLAS pinned to 1 thread per storage.py:36-47):**
  - `nearest_base_batch` single row (70,398×384 matvec): **13.81 ms** — paid on **every `/classify`** via gates.py:261 (`base_hit=None` path).
  - `nearest_base_batch` batch=32: **111.52 ms** (~3.5 ms/row) — the D25 batch win; projected corpus-tier cost of a 5,000-row ingest = 157 chunks × 111.5 ms ≈ **17.5 s**.
  - `nearest_session` matvec (4,548×384): **2.29 ms**.
  - 100,000×384 matvec (100k extrapolation): **19.7 ms**, 154 MB RAM. Still brute-force O(n·d) per request; no FAISS/ANN anywhere (grep: only docs/deck/deck.md:292 mentions the pgvector swap path).
- **Degraded modes** (storage.py:200-212): absent files → warning + session-only near-dup (silently weaker: verbatim-corpus banners off); shape mismatch → hard `ValueError` with recovery instructions. `nearest()` (top-k with exclude_text) is **test-only** (app/tests/near_dup_embed_check.py); runtime uses the two-tier split.

### Concurrency

- Exactly **one** `sqlite3.Connection` for the process, `check_same_thread=False`, every access (reads included) serialized by one `threading.RLock` (storage.py:149-152; the docstring records the SEV1-1 fix: interleaved statements on one connection returned each other's rows).
- `PRAGMA journal_mode=WAL` (storage.py:152, persists in the file header — verified), `PRAGMA foreign_keys=ON` (storage.py:153). **`busy_timeout` never set** — Python's default `timeout=5.0` applies.
- Verified live: an external process holding `BEGIN IMMEDIATE` for 7 s while the server took `POST /review` → server blocked **5.04 s** then **HTTP 500** (Internal Server Error). So any offline script (pattern mining, gold tooling) writing to the live DB file breaks review writes within 5 s.
- Single uvicorn worker (run.sh "workers 1"); sync endpoints run in FastAPI's threadpool → all threads funnel into the RLock. Measured 13-request concurrent burst (10 reads + 2 density + 2 review writes + 1 persist-classify): reads degraded 13-45 ms → **104-385 ms**, writes 313-365 ms, zero errors. Graceful at demo concurrency, but reads queue behind any long lock holder.
- Phase-2 commit of a 5,000-row ingest (one transaction, lock held throughout): **0.63 s** measured (7,948 rows/s) — every request blocks ~0.6 s during a 5k bulk commit. The slow part of bulk ingest is Phase 1 classification, not the write.
- Metrics cache (`_writes_version` counter, storage.py:173-176): first `/api/metrics/summary` after any write = **240 ms** (full scan + JSON-parse of 4,548 gate_states **under the lock**); subsequent = 4-11 ms. Overrides correctly don't invalidate it.
- Connection handles found: one — created in `__init__` (storage.py:150), closed in `close()` (storage.py:640-642). No pool, no per-request handles, no other file handles (corpus npy is a memmap, released only at process exit).

### Query efficiency (EXPLAIN QUERY PLAN, measured on demo_pre.db)

| Query | Plan | Measured latency |
|---|---|---|
| `/density` GROUP BY (storage.py:441-469) | `SCAN r`, PK `SEARCH p`, `USE TEMP B-TREE FOR GROUP BY` — full scan **per request, no cache, no date filter, no limit** | **21-103 ms** at 4,548 rows (median ~60 ms) |
| `/reports` LEFT JOIN ORDER BY id DESC LIMIT/OFFSET | `SCAN r` (reverse rowid walk, no sort needed) + PK `SEARCH p` | 50 rows: 25-35 ms; 1,000 rows: **267-580 ms** (1.48 MB payload) |
| `/metrics/summary` (storage.py:471-499) | `SCAN predictions` + JSON parse, cached per writes_version | miss 240 ms / hit 4-11 ms |
| `/health` | 2× `COUNT(*)` `SCAN` (storage.py:632-638) | 4-13 ms |
| `list_overrides(report_id)` | `SCAN overrides` — no index on report_id | trivial at n≈1 |
| hash lookups (report_hashes, ingest_payloads) | indexed autoindex searches | sub-ms |
| `/patterns` | serves artifacts/patterns/patterns.json (96 KB, present) **before** any DB touch (routes.py:329-331); fallback = `list_reports(100_000)` full materialization | 0 DB cost in default config |

### Data integrity (verified by forced failure)

- `add_ingest_batch` is a single transaction (storage.py:265-305). Test: 500-row batch with a DB-level `NOT NULL` violation on `predictions.sif_score` at row 250 → `IntegrityError`, **full rollback**: report count unchanged (4548→4548), **0 stray `report_hashes` rows**. routes.py:204-211 converts to 500 "ingest failed and was rolled back; nothing stored". Honest.
- Within-batch + cross-request dedup via `report_hashes` (storage.py:279-283); payload replay verified live (identical re-POST → `idempotent_replay: true`, same ids).
- FK enforcement on → no orphans via API writes; demo_pre.db verified: 0 reports without predictions, 0 without embeddings.
- Residual: `add_report`/`add_prediction`/`add_embedding` are separate transactions (storage.py:218-231, 253-262) — a crash between them can orphan a report without a prediction (schema tolerates it; density counts missing preds as 0.0, storage.py:451-452). **No runtime caller today** (routes only use `add_ingest_batch`) — dormant, test-only.
- No DELETE path anywhere: append-only; no data-removal capability (relevant for a real deployment's retention needs).
- `ingest_payloads.result` stores the full result JSON including every report_id — unbounded growth, harmless at demo scale.

### Export path (verified live)

`GET /api/review/export` → `application/x-ndjson`, one JSON object per line (routes.py:381-388). Verified: 9 override rows → 4 lines; **latest-wins per (report_id, field)**; exact-duplicate collapse; `supersedes` carries the collapsed ids (chain `[6,1]` observed after two label flips on report 100). Line schema (storage.py:502-523): report_id, field, value, old_value, labeler, source, rationale, decided_at, override_id, supersedes.
Gaps for compliance: exports **only** the override rows — no report text, no original `sif_score`, no gate states, no prediction snapshot (a consumer must re-join via `/reports/{id}`); no date/labeler filter, no pagination, no server-side file. `ensure_ascii=True` escapes Hindi rationale to `\uXXXX` (valid, lossless, not human-readable). `labeler` defaults to `"hse_reviewer"` when the POST omits it (schemas.py:147 — verified in my probe).

## Findings

1. **No migration strategy beyond CREATE IF NOT EXISTS + one inline backfill** — storage.py:54, 163-172. Severity: **major**. The v1→v2 backfill (hash backfill) is the entire migration story; there is no Alembic, no forward-migration registry, and **no guard against `version > 2`** (a newer-schema DB opens silently and fails later on missing columns). For a "production-grade overhaul" submission, persistence without a declared migration story is the weakest single claim in this layer — judges who ask "how do you evolve the schema?" get no answer today.
2. **/density is an uncached full scan per request with no time dimension** — storage.py:441-469; EXPLAIN shows `SCAN r` + temp B-tree; measured 21-103 ms at 4,548 rows, linear growth. At 100k rows every request re-scans ~100k rows. The `reports.date` column exists (604 distinct dates, 2024-01-01→2025-11-29) but no endpoint or aggregation uses it — a leading-indicator tool whose core aggregate cannot answer "this month". Root cause: density was de-N+1'd (SEV3-1) but never cached (unlike metrics, storage.py:173-176) and never given a time key.
3. **Cross-process write contention = 5 s block then HTTP 500** — verified: external `BEGIN IMMEDIATE` held 7 s → server `POST /review` blocked 5.043 s → 500. Root cause: `sqlite3.connect()` called without `timeout=` (storage.py:150), so the default 5 s busy timeout applies; no retry, no graceful 503. Any CLI script that writes the live DB (or two app processes) collides. Severity: **major** (latent until someone runs an offline tool against the live DB — exactly the workflow the packaging/pendrive docs encourage).
4. **No secondary indexes at all.** `EXPLAIN QUERY PLAN SELECT * FROM overrides WHERE report_id = ?` → `SCAN overrides`; density's GROUP BY uses a temp B-tree because site/activity/contractor are unindexed; no index on `reports.date`. Fine at 5k rows (measured), proportionally worse at 100k. Severity: **major** only in combination with #2; individually minor.
5. **Every `/classify` pays a 13.8 ms 70k×384 matvec** (gates.py:261 when `base_hit` isn't passed) — the corpus matvec is the single largest fixed cost on the interactive path; the ingest path's batching (routes.py:192, 111.5 ms/32 rows ≈ 3.5 ms/row) shows the fix already exists but wasn't carried to `/classify`. Severity: minor (bounded, honest), but it compounds with finding 3's lock: the session-tier query takes the RLock per call.
6. **Metrics-cache miss blocks all requests** — first `/metrics/summary` after any write = 240 ms at 4,548 rows (full gate_states JSON parse under the RLock). Scales linearly: at 100k predictions ≈ 5 s full-queue stall after every ingest. Severity: minor at demo scale, major at production scale.
7. **Near-dup index is honest but linear.** Session matvec 2.29 ms @ 4.5k → 19.7 ms @ 100k (measured); base tier frozen at 70,398 vectors (rebuilt only offline at 40.5 rows/s, corpus_index_meta.json). No ANN, no runtime promotion of ingested rows into the base tier. Defensible for the demo; a linear-per-request scan is the ceiling to disclose, not hide. Severity: minor.
8. **Session-index warm is lazy** — the 57 ms embeddings-table scan lands on the **first user near-dup query after restart**, not at boot (storage.py:352-358), while boot already pays 0.5 s for the corpus index. Cosmetic unfairness; move to lifespan. Severity: minor.
9. **`add_report`/`add_prediction`/`add_embedding` can orphan rows on crash** (separate transactions, storage.py:218-231) — dormant (no runtime caller; batch path is atomic and verified). Severity: minor.
10. **Export incompleteness for compliance** — overrides-only; no joined prediction snapshot or text; no filters/pagination (finding above). Severity: minor-to-major depending on how far the compliance story is claimed.
11. **Worth keeping, verified good**: WAL + foreign_keys + single-connection RLock (SEV1-1), atomic batch ingest with verified rollback, payload-level idempotent replay, content-hash dedup, schema_version row, the measured BLAS pin (documented at storage.py:36-47 with a real mechanism), degraded-mode warnings for the corpus index, latest-wins export with supersedes.

## Root cause

No hard blockers in this layer — no data loss or corruption was demonstrable. Root causes for the top majors:

- **Finding 2 (per-request full-scan density, no time dim)**: the SEV3-1 fix moved aggregation from Python to SQL but stopped there — no cache (unlike metrics), no facet indexes, and the date column exists in the schema since v1 yet no aggregate is keyed on it. It is a design gap (time-series absent from the query layer), not a bug.
- **Finding 3 (5 s block → 500)**: default `timeout=5.0` of `sqlite3.connect` was never surfaced as a decision; WAL allows concurrent readers but only one writer, and the app was designed single-process. The failure mode is an *unhandled* `OperationalError` (500) rather than a retry/backoff or an honest 503.
- **Finding 1 (no migration story)**: SCHEMA_VERSION was introduced to serve one purpose (the hash backfill); nothing exists for adding columns/tables. The docstring (storage.py:4-5) names this deliberately ("No ORM, no Alembic — fixed schema") — a demo choice that will be read as missing engineering if claimed as production.

## Gaps vs production

- No migration tooling (Alembic-style or hand-rolled versioned DDL with a downgrade guard).
- No indexes on any query filter beyond PKs (report_id on overrides; date/facet columns for time-sliced density).
- No time dimension exposed anywhere in the persistence layer's aggregates (604 dates sit unused).
- No busy_timeout/retry policy or writer-arbitration for multi-process access; no documented rule "offline tools must not write the live DB".
- No retention/deletion path; no backup/VACUUM/ANALYZE strategy; no point-in-time recovery (WAL exists but nothing checkpoints/ships it).
- Export lacks the joined record (text + original score + gates) a compliance consumer needs; no CSV/NDJSON of reports+predictions at all (only overrides export exists).
- Vector index: no recall/latency regression harness in CI for the near-dup tiers (app/tests/near_dup_embed_check.py exists but is a manual check, not wired into pytest).
- Cache (`_writes_version`) is process-local — correct, but restart-after-write re-pays the 240 ms miss with no warmup.

## Recommendation

- **KEEP** — SQLite + WAL + single-connection RLock: measured 7,948 rows/s write, 5-100 ms reads at 5k rows, graceful 13-way concurrency; the Protocol (storage.py:119-143) already preserves the swap path (docs/deck/deck.md:292).
- **KEEP** — two-tier near-dup design (frozen fp16 corpus + session tier) and the BLAS pin: 0.5 s startup / 13.8 ms per interactive query is honest and documented with measured rationale (storage.py:36-47).
- **KEEP** — atomic `add_ingest_batch`, `report_hashes` dedup, `ingest_payloads` replay: all three verified by forced-failure and re-POST tests this session.
- **ADD** — `PRAGMA busy_timeout` (raised, e.g. 30 s) + a retry wrapper, and a stated rule that offline tools never write the live DB: eliminates the verified 5 s→500 failure mode for one line of code.
- **ADD** — a real migration story: either adopt Alembic or hand-roll versioned DDL v3+ with an explicit `version > SCHEMA_VERSION` refusal; the schema-version row already exists, finish the mechanism.
- **ADD** — date-dimension to `/density` (and an index on `reports.date`): the data is already there (604 distinct dates); this unlocks the time-series claim API RP 754/IOGP 456 demand, in SQL, cached like metrics.
- **ADD** — index `overrides.report_id` (one CREATE INDEX); export should include the joined report text + original `sif_score` (or ship a second export).
- **MERGE** — `/classify`'s per-row base matvec (13.8 ms) into the chunk-batched matmul already used by `/ingest` (3.5 ms/row): same function exists, wire the interactive path to batch=1 amortization via a small matvec cache or accept it and disclose.
- **REMOVE** — AUTOINCREMENT (plain INTEGER PK suffices; no delete path exists) and the test-only `nearest()` exclude_text N+1 loop (test-only, but it sets a bad example for the runtime path).
- **REMOVE** — nothing at the storage layer is overbuilt; the overbuild risk lies elsewhere (patterns serving, frontend). This layer is the most disciplined part of the codebase.

Verdict on the engine choice: **SQLite remains defensible** for a fully-offline, single-machine submission at this scale (measured: write 8k rows/s, reads 5-100 ms at 5k rows, 19.7 ms brute-force cosine at the 100k extrapolation, 154 MB RAM). Postgres/pgvector (docs/deck/deck.md:292) buys concurrency + ANN + migrations but adds install burden where docker is banned; DuckDB adds a second engine without fixing the single-writer write path. Keep the Protocol swap path documented; do not adopt either now.