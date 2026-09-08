# Day-1 Review: `app/explain.py` + `app/embedder.py` + `app/config.py` (fallback correctness)

Reviewer role: `review-explain`. All findings reproduced with probes — unit level
(transport injection) and HTTP level (test server on :8195, throwaway DB in
`/tmp/sif-probe/`, fake ollama on :8196). Demo server on :8177 never touched;
no ollama/kaggle processes disturbed; no repo code modified.

## Findings by severity

- **SEV1: 1** (uncaught exception types break the silent-fallback contract → HTTP 500)
- **SEV2: 1** (score-mutation guard weaker than documented — substring match)
- **SEV3: 6** (quote-check hole, false-rejects, legacy-cache stall, hashed-fallback fail-open disclosure, cosmetic label, env-parse notes)

## Top 3

### SEV1 — `ollama_reword` catch list omits `ValueError` / `http.client.HTTPException` → explain path 500s instead of falling back

`app/explain.py:219-220` catches `(ValidationError, SpanValidationError,
json.JSONDecodeError, KeyError, TypeError, OSError)`. Two realistic failure
types escape, violating the documented contract ("Never raises; any failure
returns None so the caller falls back to the template silently", line 193-196):

1. **Non-HTTP service on the ollama port** (port squatter, proxy, TLS endpoint
   hit with plain HTTP — a real Day-of-demo hazard on a shared box).
   `urllib` raises `http.client.BadStatusLine`, an `HTTPException` (NOT an
   `OSError`). Reproduced end-to-end: fake garbage-bytes server on :8196,
   `SIF_OLLAMA_URL=http://127.0.0.1:8196`:
   `POST /api/classify?explain=1` → **HTTP 500 in 0.12s**, and 500 again on the
   repeat request (the exception fires before `save_precomputed`, so nothing is
   ever cached and every request pays it). Server log:
   `http.client.BadStatusLine: \x00\x01garbage-not-http` raised at
   `app/explain.py:207` inside `ollama_reword`, through `build_explanation:274`.
2. **`SIF_EXPLAIN_TIMEOUT=-1`** (plausible env typo — it parses as a float, so
   the fail-loud-at-import guard doesn't catch it). `urlopen` raises plain
   `ValueError: Timeout value out of range`. Reproduced end-to-end: every
   `?explain=1` request → **HTTP 500**; the same request without `explain` →
   200. Unit-level: `timeout=-1` and `timeout=-0.001` raise, `timeout=0` is
   caught (OSError path).

One-line fix: add `ValueError` and `http.client.HTTPException` to the except
tuple at `app/explain.py:219` (retry loop already handles them gracefully —
probed: injected `ValueError` from transport currently propagates; with the
wider catch it becomes a logged failed attempt).

### SEV2 — score-mutation guard is a substring check; mutated scores pass

`app/explain.py:167`: `if score_str not in out.explanation`. Reproduced
false-PASSES against the "triage score preserved verbatim" invariant
(module docstring line 13-14):

- score `0.83` reworded as **"10.83"** → accepted (`"0.83" in "10.83"`).
- score `0.83` reworded as **"0.833"** → accepted.
- triage score **omitted entirely** → accepted when a rule probability formats
  to the same 2-decimal string (probe: score 0.71, explanation mentions only
  "Hot Work (0.71)" → passes; the explanation then shows no triage score, or
  worse the number misattributed to a rule).

Fix: boundary-anchored match, e.g.
`re.search(rf"(?<![\d.]){re.escape(score_str)}(?![\d.])", out.explanation)`.
This also keeps the strict "0.8" ≠ "0.80" formatting rejection (SEV3 below)
intact.

### SEV3 — hashed-fallback near-dup fails OPEN vs the MiniLM corpus index (silently)

When `artifacts/embeddings/minilm/` is absent, `HashedEmbedder` keeps the API
up (as designed, `app/embedder.py:129-134`). But hashed query vectors against
the MiniLM-built fp16 corpus index are vector-space garbage: measured top-1
cosines 0.14–0.20 over 6 realistic report texts — far under the 0.91 banner
threshold, so the **corpus-tier near-dup gate is silently OFF** (fail-open).
Fail-open is the right side for the demo (no false banners, app boots), and
the session tier still works self-consistently (hashed-vs-hashed: exact dup
cosine 1.000 triggers, distinct text 0.514 doesn't). Empty text → zero vector,
finite, no crash, no banner. Only disclosure is the startup warning log line —
worth a health-endpoint field if the fallback can ever ship in a demo build.
(Index-build truncation parity verified: `data_pipeline/embed_corpus.py:116`
uses the same `embed_texts`; `corpus_index_meta.json` records
`truncation_word_pieces: 256`.)

## Full findings list

| # | Sev | File:line | Finding | Repro |
|---|-----|-----------|---------|-------|
| 1 | SEV1 | explain.py:219 | `ValueError`/`HTTPException` escape `ollama_reword` → HTTP 500 on `?explain=1`, uncacheable, every request | fake garbage-bytes server on :8196 → 500 twice; `SIF_EXPLAIN_TIMEOUT=-1` → 500 (non-explain control 200); unit: negative timeout raises |
| 2 | SEV2 | explain.py:167 | score guard substring-matches: "10.83"/"0.833" pass for 0.83; score omission passes when a rule prob shares the 2-decimal string | `_validate` accepts all three crafted payloads |
| 3 | SEV3 | explain.py:177 | in-prose quote check regex `"([^"]+)"` misses curly “…” quotes — mutated “Grindingg” accepted | `_validate` accepts curly-quote mutation |
| 4 | SEV3 | explain.py:167,177 | false-REJECTS of valid rewordings (silent template fallback, one wasted retry): "0.8" for "0.80"; quoting template wording ("flagged for HSE review") which is not report text | both rejected by `_validate` |
| 5 | SEV3 | explain.py:268 | legacy cache entry without `created_epoch` treated as permanently stale → one 2×timeout stall when LLM down; self-heals on that same request (`cache_payload` rewrites the field) | 3-request probe: 2 transport attempts total, then cached |
| 6 | SEV3 | embedder.py:129 | hashed fallback: corpus-tier near-dup silently off (max cosine 0.20 ≪ 0.91); session tier OK; fail-open is demo-correct | 6-text probe vs real index + session insert |
| 7 | SEV3 | gates.py:244 (out of item, observed) | session-tier near-dup hit detail says "index row N" — mislabeled tier | session dup probe: `cosine=1.000 with index row 1` |
| 8 | SEV3 | config.py:58,82-83; explain.py:45,48 | bad numeric env (`SIF_PORT=abc`, `SIF_EXPLAIN_TIMEOUT=abc`, `SIF_EXPLAIN_FALLBACK_TTL=xyz`) → ValueError at Settings()/import — fail-loud at boot (acceptable); `SIF_PORT=-1/99999` deferred to uvicorn bind error; `SIF_DB_PATH` missing dir → `sqlite3.OperationalError` at startup; `SIF_MODEL_PATH`/`SIF_EMBED_MODEL_DIR` missing → documented mock/hashed fallback, boots | per-env subprocess matrix |

## Verified good (probed, no finding)

- **All common ollama failure modes fall back silently** (transport-injected +
  real dead port): connection refused (0.00s), malformed JSON, empty content,
  missing `message` key / empty-dict / null message / null content, JSON-array
  content, schema violations (extra field, too-short), `TimeoutError`,
  `URLError`, hallucinated span, in-prose quote mutation, meta/CoT leak,
  dropped score. 16/16 → `None` → template. Retry-then-success returns the
  rewording on attempt 2. HTTP level with malformed-JSON fake ollama: 200,
  `source=template`, `reworded=null`, 12ms.
- **Cache key correctness**: `sha256(text \x00 model_version \x00
  repr(threshold))` (explain.py:88-95). Threshold IS hashed — re-tune
  0.5 → 0.712581 produces a new key; the stale entry is never served
  (2 keys stored, 2 fresh builds). `\x00` separators kill concatenation
  ambiguity (`key("AAAA") != key("AAAA\x00evil")`). Poisoning would need a
  sha256 preimage over full report text — not feasible.
- **TTL semantics exactly as documented** (explain.py:254-259): fresh template
  entry served without LLM retry; stale template + LLM back → one upgrade
  retry, entry becomes `source=ollama`; stale + LLM down → 2 attempts (bounded
  2×timeout) and `created_epoch` refreshed, next request free; ollama entries
  served verbatim forever (created_epoch=1.0 still served with LLM down).
  End-to-end slow-ollama (10s sleep, timeout=2): cache miss 4.13s → 200
  template; repeat 6.3ms cached. Cached payload round-trips through
  `ExplanationOut(**hit, cached=True)` — extra `created_epoch` key ignored by
  pydantic.
- **Embedder MiniLM path**: empty / whitespace / control-only texts → finite,
  unit-norm rows (special tokens keep the mask non-empty; 1e-9 division
  guard). 2400-word text truncates to exactly 256 word pieces — matches the
  index build (same `embed_texts`; meta `truncation_word_pieces: 256`).
  Deterministic across calls. `verify_pooling()` PASS, worst |Δ| = 4.5e-05
  (tolerance 5e-3).

## Environment / housekeeping

Probes ran on ports 8195-8196 with throwaway DBs under `/tmp/sif-probe/`
(probe scripts `probe1_failmodes.py`, `probe2_cache.py`, `fake_ollama.py` kept
there for re-runs). All probe processes killed. Demo server :8177 health
verified after the run (real `RealOnnxClassifier`, 5050 reports — untouched).

<<SCORES {"ps":"26165","role":"review-explain","go_no_go":6,"severity":8,"feasibility":9,"data_risk":3}>>
