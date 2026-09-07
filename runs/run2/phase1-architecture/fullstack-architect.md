# Phase 1 — Full-Stack Architect (runtime system: API, DB, dashboard, build sequence)
PS 26165 | 2026-09-08 | VERIFIED = measured on this machine today; INFERRED otherwise.

## 1. Findings (with numbers)

- **Postgres+pgvector as runtime hard-dep is unjustified.** VERIFIED: no local postgres binary, docker inactive+disabled (root needed), sqlite3 3.53.3 present. VERIFIED: numpy brute-force top-10 cosine over 110,000×384 MiniLM embeddings = **25 ms on the throttled CPU** (169 MB float32, fits RAM trivially). pgvector buys exact nothing below ~1M vectors; brute force IS exact. SQLite+WAL+single-writer ingester handles demo write rates; FastAPI is stateless over it.
- **CPU still clamped 0.85 GHz** (VERIFIED: cpu0 scaling_cur_freq=854170). Everything CPU is ~6× slow: ONNX p95 <100 ms and bulk-ingest ≥500/s acceptance bars are at risk **while clamped** (INFERRED from 6×; unclamped they were plausibly fine). LLM live path = dead (4 tok/s, VERIFIED by phase0).
- **C10 mitigation is weaker than claimed.** VERIFIED counter-evidence: `/api/chat` + `think:false` + `/no_think` → qwen3:4b still produced reasoning, exhausted num_predict (done_reason=length). Only `format`=JSON-schema forced clean output (phase0 VERIFIED). Design rule: **always set format=schema; never rely on think suppression; budget num_predict for hidden reasoning**.
- **tokenizers wheel risk: CLEARED.** VERIFIED: tokenizers 0.23.2 ships cp310-**abi3** manylinux wheels → installs on Python 3.14. Char-offset mapping at ONNX runtime is unblocked.
- **Bulk ingest bar**: 500 reports/s classify-only requires batched ONNX (batch 32, seq 128); single-text calls won't reach it even unclamped (INFERRED). Ingest endpoint must queue → batch worker, not classify inline.

## 2. Risks ranked

**SEV1 (project-killer)**
1. Runtime hard-depends on Postgres+pgvector via docker; docker is DOWN and needs root (C2). If Day-3 arrives unrooted, demo is dead. Fix = SQLite swap (§3), decided NOW, not Day 3.
2. CPU clamp unresolved at demo → latency/throughput acceptance bars fail. Human task Day 1: investigate PD-adapter/BIOS; until fixed, treat all latency numbers as 6× pessimistic and rehearse offline with clamp.

**SEV2 (quality-killer)**
- int8 ONNX export fails under transformers v5 × optimum-onnx 0.1.0 (C4) → fp32 fallback 2–4× slower → latency budget blown. Gate: export smoke-test BEFORE training (already planned; make it blocking).
- Span-offset drift: any text normalization (whitespace/unicode strip) after offset computation silently misaligns UI highlights. Contract: offsets computed against the canonical stored text; server validates `text[start:end]==span_text` before responding; UI only slices, never computes.
- Pattern mining shipped as decoration (hand-wavy co-occurrence) → hostile Q&A kill. Must be lift-ranked stats on real fields with n and Wilson CIs (§3).

**SEV3**: Ollama think-suppression waste (dev-time latency only; precompute covers); Snorkel frozen (C11 — use plain heuristic LFs, skip dep); shadcn cold build time.

## 3. Module cut-line + verdicts (hours = 2–4 students + agent swarm)

| Module | h | Call |
|---|---|---|
| Ingestion+validation (CSV/paste/JSON, alias-map config, min-length, dedup) | 8 | MUST. **MODIFY**: one canonical mapping + alias dict (text/narrative/description→text; optional date/site/activity/contractor→NULL). CUT arbitrary-mapping UI — demo data is self-generated. |
| Classification svc (ONNX, calibration, batching queue) | 10 | MUST. ADD batch-worker; never inline per-row. |
| Gates: confidence + near-dup | 5 | MUST (near-dup doubles as §B.3 #9 defense; reuse MiniLM brute-force, 4h). |
| Gate: negation | 3 | SHOULD — 10-line NegEx keyword rule → force review queue. CUT-able last. |
| Gate: language | 2 | CUT live detect→translate; static phrasebook JSON + ~20 pre-translated demo reports. |
| Explanation renderer (templates) | 3 | MUST — templates are the source of truth. |
| Ollama reword layer | 6 | **MODIFY**: precompute script (build-time, format=schema, pydantic-validate, exact-substring span check, template fallback) = MUST; live endpoint = SHOULD, cut first. |
| Dashboard: feed+highlights | 8 | MUST. |
| Density ranking (site/activity) | 5 | MUST (PS core; SQL GROUP BY + sif_rate). |
| Rule breakdown chart | 3 | MUST (free off same query). |
| Pattern mining | 5 | MUST-as-real. **MODIFY**: structured facets (activity×location×barrier_lost) carried by synthetic generator + OIICS Event/SourceTitle on OSHA; output = lift vs baseline rate, n, Wilson CI. Fallback for free-text-only uploads: keyword-facet GROUP BY. REJECT runtime LLM tagging (dev-time-only per constraints). |
| Review queue + override | 6 | MUST (demo finale + acceptance bar). |
| Override→gold loop | 2 | MUST: `overrides(report_id, field, old, new, labeler, source, ts)`; source ∈ {override, blind_gold}; GET /api/overrides/export.csv emits gold-schema CSV; eval joins blind_gold only — separation by column, never by convention. |
| DB | 4 | **REJECT Postgres+pgvector for runtime. ADOPT SQLite + numpy-brute-force** behind a 40-line `Storage` protocol (ingest/get/list/log_override/get_embeddings). Second impl only if docker is rooted — don't write it now (YAGNI). Fixed `schema.sql`, CREATE IF NOT EXISTS + schema_version row; no Alembic. |
| API | 6 | REST only; **REJECT websockets**. `POST /classify`, `POST /ingest`+`GET /ingest/{id}` (job poll), `GET /reports`, `GET /reports/{id}`, `GET /rankings/density?by=site|activity`, `GET /patterns`, `POST /overrides`, `GET /overrides/export.csv`, `GET /metrics`. Pydantic models double as TS types. |
| Auth | 0 | CUT (single-user demo). |

**Cut order on Day-2 slip:** live Ollama → language gate → negation gate → pattern view degrades to precomputed static table → review-queue UI polish (endpoint stays).

## 4. Verdict

Runtime architecture is directionally right (precompute doctrine, template-first explanations, REST FastAPI, custom dashboard) but carries one SEV1 dependency (Postgres/docker) that measured reality rejects, and under-specifies three seams (offset ownership, LLM JSON contract, pattern-mining honesty). With the SQLite swap, char-offset server contract, schema-enforced precompute, and the cut-line above, the 72h build fits: MUST total ≈ 55 person-hours of agent-accelerated work across 2 parallel streams. GO after modifications.

<<SCORES {"ps":"26165","role":"fullstack-architect","go_no_go":6,"severity":2,"feasibility":7,"data_risk":2}>>
