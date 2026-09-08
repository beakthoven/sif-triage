# Day-1 evening review — app/routes.py + app/storage.py + app/ingest.py

Role: review-routes (adversarial correctness). Reviewer agent 5/5.
Date: 2026-09-08. All probes against a THROWAWAY DB (`/tmp/sif-review/test.db`)
on test port 8191, same model as the demo (`onnx:masked-v1/sif_multitask_int8.onnx`,
`SIF_EXPLAIN_LLM=0`). The demo server on :8177 and `app/runtime.db` were never
touched. No git mutations.

Probe scripts shipped alongside this file for re-runs:
- `routes_storage_probe_concurrency.py` (modes: detector / readonly / pageload / pageload_writer)
- `routes_storage_probe_ingest_review_inject.py` (P3 partial/dup, P4 overrides, P5 injection)
- `routes_storage_probe_crossproc_wal.py` (cross-process WAL writer)

Seed for all probes: `artifacts/demo/bulk_ingest_5k.csv` ingested via
`POST /api/ingest` — 5,050 accepted / 0 rejected in 143.1 s (35.3 rows/s;
D25 ≥30/s SLA holds on the int8 per-row path).

---

## Findings: 1 × SEV1, 4 × SEV2, 5 × SEV3 (+3 verified negatives)

### SEV1-1 — Shared sqlite3.Connection corrupts under ANY concurrent use: silent wrong scores, phantom 404/409s, mass 500s

**Where:** `app/storage.py` — the `self._lock` guards only *writes*
(`add_report` :150, `add_prediction` :160, `add_embedding` :180, `add_override` :212,
`save_precomputed` :331) plus `nearest_session`/`_session_index`. Every read path
touches the one shared connection (`check_same_thread=False`) **unlocked**:
`get_report` :248-250, `list_reports` :252-256, `list_overrides` :258-273,
`load_precomputed` :338-342, `count_reports` :344, `count_overrides` :347, and the
`exclude_text` lookup in `nearest` :321. Uvicorn runs these sync routes on a
40-thread pool, so concurrent statements interleave on one Connection object and
scramble each other (rows returned for the wrong statement / `None` rows /
`sqlite3.InterfaceError: bad parameter or other API misuse` /
`no more rows available`).

**Reproduced (all against the 5,050-row throwaway DB):**

| Probe (30 s each) | Result |
|---|---|
| Read-only, 4 threads (1 fixed reader + 2 density + 1 list), **zero writers** | 1,097–1,184 HTTP 500 on `/api/reports/100`; **753–754 SILENT wrong sif_score in 200 OK** (another report's prediction row); **732–754 SILENT `prediction: null`** in 200 OK; 679–721 HTTP 500 on `/api/reports?limit=200`; 84–127 HTTP 500 on `/api/density`; 1 UnicodeDecodeError |
| Detector (3 fixed readers + 2 density + 2 explain-cache writers) | 434 HTTP 500 + **222 HTTP 404 for report id 100 which EXISTS** + 133 silent prediction-drop + 22 silent wrong-score |
| Page-load emulation (browser-parallel 3+2 fetches) + 1 writer/0.25 s | **588 of 597 page loads (98.5%) contained ≥1 HTTP 500** |
| 300 sequential page loads, no writer, no overlapping load | 300/300 OK |

Server log line attribution (552 InterfaceErrors in the first hammer run):
`storage.py:256 list_reports`, `:225-237 _row_to_report` (json.loads of a
scrambled/None row), `:249-250 get_report` (→ phantom 404/409), `:339-342
load_precomputed` (explain cache). Re-run of the shipped script
(`..._probe_concurrency.py readonly`) reproduces the same profile.

**Data at rest is safe**: `PRAGMA integrity_check` = ok after all probes; report
100's score in the DB file = 0.9954 before and after; WAL on. The corruption is
in-transit only and the server recovers per-request — but it serves **wrong
numbers with HTTP 200**, which is worse than a loud error for a triage demo.

**Demo-day exposure:** the dashboard fires parallel fetches on every mount
(`App.tsx:25` health+reports+overrides; `density.tsx:123` health+density) — a
lone scripted operator measured clean (300/300 loads). But ANY second client —
a judge opening the URL on their laptop, a second tab, the explain-precompute
harness running while the server is up, or a click during the ~1-2 s live
ingest beat (write overlapping the refetch) — enters the failing regime at the
rates above. The UI's error path silently falls back to MOCK data
(`density.tsx` catch → `setLive(false)`), so the failure can also present as
the demo quietly reverting to canned numbers mid-beat.

**Fix (small):** take `self._lock` around every `self._conn` access (reads
included), or switch to per-thread connections (`threading.local`, one
connection per thread, WAL makes read scaling free). The lock-only variant is
a ~10-line diff; at demo scale the 170 ms density read blocking a writer is
irrelevant. This must land before demo day.

### SEV2-1 — Corpus-index misalignment hard-stops boot (fail-safe, but a boot-killer with a fixable inconsistency)

**Where:** `app/storage.py:142-143` — `ValueError: corpus index misaligned:
N vectors vs M ids` raised in `_load_corpus_index`, called from the FastAPI
lifespan (`main.py:26`).

**Probe:** fake index dir with 10 vectors / 16 ids → `uvicorn` exits code 3,
log ends with the full traceback and the exact ValueError line
(`Application startup failed. Exiting.`). Under `run.sh` the health poll
breaks on process death and `tail -20` of the log includes the ValueError
line, so the operator DOES get an actionable message — not a silent hang.

**Assessment:** correctness-wise the raise is right (a misaligned index would
attribute near-dup banners to the WRONG corpus ids — silent wrong banners).
The trap is demo-day robustness: a partial re-copy of `artifacts/embeddings/`
(exactly the D24 transient, 70,398 vs 70,404) turns "degraded near-dup" into
"demo does not boot at all", and it is inconsistent with the missing-files
path two lines up (:136-138), which degrades gracefully with a log warning.
Recovery is one command (delete the two files → session-only mode), so: fail-
safe by design, but put the recovery line in the demo runbook, or degrade with
a loud warning like the missing path. Verified the current committed pair is
aligned (70,398 = 70,398 per `corpus_index_meta.json` + npy shape + ids
line-count).

### SEV2-2 — Duplicate re-ingest double-counts everything; no dedup, no idempotency

**Probe:** identical 50-record payload POSTed twice → both return
`accepted: 50, rejected: 0`; `n_reports` 11,315 → 11,415 (+100); density row
for the probe site shows `n_reports: 100`. There is no uniqueness constraint
(schema `reports` has none) and no content-hash check in `ingest()`. The
near-dup gate fires on the second copy (badge only — "gates never block
ingestion" by design), so the operator is *informed* per row but the store,
density ranking, flag rates, and `metrics/summary` all double-count.
Combined with SEV1 (a 500 mid-ingest, or the 143 s 5k-row ingest outliving a
proxy/browser timeout) the natural operator response — retry the upload —
silently doubles the corpus. Severity is quality/data-integrity: the demo
seed is pre-staged (D3), but a live "watch me re-upload" or a retry during
the demo poisons every aggregate the dashboard shows.

**Fix direction:** content hash (sha256 of normalized text+date+site) with
`INSERT OR IGNORE` + a `skipped_duplicates` count in `IngestResult` (keeps
counts honest), or at minimum surface the near-dup badge count in the ingest
response.

### SEV2-3 — Override queue has no integrity semantics: dupes, contradictions, free-text fields — and it feeds future gold

**Probes (all verified on the throwaway DB):**
- `POST /api/review` for nonexistent `report_id` → correct **404** ✔ (the
  guard at `routes.py:299` works).
- Exact same override POSTed twice → **both stored** (ids 1, 2); no dedup.
- Contradictory overrides on the same `(report_id, field)` (`not_sif_potential`
  then `sif_potential`) → **both 201**; history keeps both with no
  supersede/latest-wins marker. A downstream "export as future gold" reader
  (`list_overrides` returns all rows `ORDER BY id`) sees two opposing labels
  for the same report and cannot tell which won.
- `field` is a bare `str` (`schemas.py:130`) — `"garbage_field'; DROP TABLE
  overrides;--"` accepted with **201**. `new_value` is free text —
  `"maybe_sometimes"` accepted with 201. The gold schema vocabulary
  (`sif_label` / rule keys / `well_control`; `sif_potential` etc.) exists
  only in the dashboard client, not the API contract.
- `source: "blind_gold"` accepted through the same endpoint — fine per the
  docstring (eval joins blind_gold only), but nothing stops a labeler
  minting blind_gold rows outside the blind protocol.

For a table whose stated purpose is "exported downstream as future gold
labels" (routes.py:297), this is a data-quality landmine for the Kaggle
retrain lineage. **Fix direction:** pydantic `Literal` on `field` +
vocabulary validation on `new_value`, and an export rule (or a
`superseded_by` column) making latest-wins explicit.

### SEV2-4 — Ingest batch is not transactional: mid-batch failure = silent partial commit + dishonest-by-omission counts

Counts for *validation* failures are honest (probe: 5,050 rows with row 3000
missing `text` → `received=5050, accepted=5049, rejected=1`,
`errors[0]={row:2999, ...}` — correct 0-based index). But rows are committed
one-by-one inside the batch loop (`routes.py:130-137`, each `add_report` its
own transaction): a crash or 500 after row N leaves N rows in the store with
NO response body at all, and the client cannot distinguish "nothing stored"
from "2,999 stored". Retry → duplicates (see SEV2-2). Not injected live
(would need fault injection into the storage layer), so this is a code-
inspection finding, but the retry-double-count consequence is fully
reproduced by SEV2-2. **Fix direction:** return the committed id prefix in
the error path (wrap the loop so an exception still yields
`IngestResult(accepted=len(ids))`), or make the whole request one
transaction.

### SEV3-1 — `/api/density` + `/api/metrics/summary`: no pagination, N+1 queries, linear growth

Measured at 5,050 rows (p50/p95, 30 samples, warm): `/api/reports?limit=50`
1.3/2.0 ms; `/api/reports?limit=1000` 27/54 ms (pagination exists:
`limit ≤ 1000`, `offset`); **`/api/density` 171/205 ms** and
**`/api/metrics/summary` 178/213 ms** — both hardcode
`list_reports(limit=100_000)` (`routes.py:191, 315`) and `_row_to_report`
issues one extra SELECT per row (`storage.py:225-227`), ~5,051 queries per
call. Fine at demo scale; at the 100k cap each call would be ~4 s and —
worse — density/metrics would silently compute over only the LATEST 100,000
rows. `/api/patterns` serves the precomputed file: 0.8/0.9 ms.

### SEV3-2 — CSV formula-injection payloads stored verbatim (downstream risk only)

`=cmd|'/c calc'!A1`, `+SUM(1,2)`, `-10-20`, tab-prefixed `=HYPERLINK(...)`
in text/site are stored and served back verbatim (probe P5b, all 201/200).
No CSV-export endpoint exists in the app (overrides/density are JSON), so
there is no in-app sink; the risk lands on any future gold/override CSV
export opened in Excel. One-line mitigation when that exporter exists:
prefix `= + - @ \t`-leading cells with `'`.

### SEV3-3 — `column_mapping` override lookup is case-sensitive against raw keys; alias table is not

`map_columns` (`ingest.py:38`): `override[canon] in row` tests the ORIGINAL
dict keys, while the alias fallback uses lowercased keys. Probe: record with
column `Narrative_Text` + `column_mapping={"text": "narrative_text"}` → row
silently rejected (`text: Input should be a valid string`). Lowercase the
override value the same way before lookup. Silent rejection makes this an
honesty-of-errors annoyance: the operator sees "rejected" with a misleading
reason.

### SEV3-4 — `records` + `csv` both present → csv silently ignored

`parse_records` (`ingest.py:57`) returns `records` when both are given;
`received` counts only records. Probe: 1 record + 1 csv row →
`received=1, accepted=1`, the csv row vanishes without an error. Reject the
request (422) or document the precedence.

### SEV3-5 — Corpus-index absence degrades to session-only near-dup with only a log warning

`storage.py:136-138`: missing npy/ids files → `log.warning` and the demo
boots on session rows only; `/api/health` gives no indication. If
`artifacts/embeddings/` is renamed/not copied on the demo laptop, the
verbatim-training-paste banner silently never fires. Surface
`corpus_index_rows` in `/api/health` (one field) so preflight can check it.

### Verified negatives (attacked, did not reproduce)

- **SQL injection**: `' ); DROP TABLE reports;--` in text/site → stored as
  data, tables intact, counts consistent. All SQL is parameterized; the only
  string-built SQL is static. Clean.
- **Path traversal**: no file-upload endpoint exists (ingest takes JSON
  records / a CSV *string* in the JSON body) — no filename surface.
  `SIF_DB_PATH` / `SIF_PATTERNS_FILE` are operator env vars (trusted
  boundary); a bad `SIF_DB_PATH` fails loudly at startup. Clean from the API.
- **Cross-process 'database is locked' (the harness hit the explain agent
  saw)**: a second-process writer doing 300 `INSERT OR REPLACE` into
  `precomputed` against the live server under density+explain load →
  **300/300 OK, zero lock errors** (WAL + sqlite3's default 5 s busy
  timeout). The likely source of the harness's lock error is the same root
  cause as SEV1-1 (unguarded intra-process connection use surfacing as an
  OperationalError downstream) or a client opened with `timeout=0`. Fix
  SEV1-1 and re-check the harness; no WAL-level change needed.

---

## Latency summary (5,050 rows, int8 model, throwaway DB, warm, n=30)

| Endpoint | p50 | p95 | note |
|---|---|---|---|
| `/api/reports?limit=50` | 1.3 ms | 2.0 ms | paginated (limit ≤ 1000 + offset) |
| `/api/reports?limit=1000` | 27 ms | 54 ms | N+1 per-row prediction fetch |
| `/api/density?by=site` | 171 ms | 205 ms | no pagination, full scan + N+1 |
| `/api/metrics/summary` | 178 ms | 213 ms | same pattern |
| `/api/patterns` | 0.8 ms | 0.9 ms | precomputed file |
| bulk ingest (5,050 rows) | — | — | 143.1 s total, 35.3 rows/s (SLA ≥30/s ✔) |

## Files written

- `runs/run2/day1/reviews/routes_storage.md` (this file)
- `runs/run2/day1/reviews/routes_storage_probe_concurrency.py`
- `runs/run2/day1/reviews/routes_storage_probe_ingest_review_inject.py`
- `runs/run2/day1/reviews/routes_storage_probe_crossproc_wal.py`

No application code was modified. Throwaway artifacts under `/tmp/sif-review/`
(DB, logs, bad-index fixture); test server on :8191 left running for the
wave's cross-checks — kill with `kill $(lsof -t -i:8191)` when done.
