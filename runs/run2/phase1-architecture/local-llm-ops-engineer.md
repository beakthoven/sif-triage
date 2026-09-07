# Phase 1 Refinement — Local-LLM Ops (Ollama layer; C3/C10 attack surface)
Role: local-llm-ops-engineer | 2026-09-08 | All numbers VERIFIED on this machine (CPU clamped 0.60–0.85 GHz throughout; idle-server benchmarks only — one taken during a model pull measured 5–20× degraded) unless marked INFERRED.

## 1. Findings

**1a. Model bake-off — evidence-span JSON extraction, real OSHA narratives** (/api/chat, top-level `think:false`, `format:schema`, temp 0, num_predict 400):

| Metric | qwen3:4b (n=50) | qwen3:8b (n=25, same seed) |
|---|---|---|
| JSON parse / schema-valid | 100% / 100% | 100% / 100% |
| Verbatim-exact spans, 1st try | **96% (48/50)** | 92% (23/25) |
| Final failure after 1 corrective retry | **0%** | 8% (2/25 truncated spans, unfixable by retry) |
| Gen tok/s (throttled) | 4.1 | 2.3 |
| Prompt tok/s (prefix-cached) | 70.3 | 35.0 |
| Wall per report | 20.9 s | 39.6 s |
| RSS serving | ~3.0 GiB | ~5.6 GiB |

8b pulled (4.87 GiB) and benchmarked. 92-vs-96 isn't significant at n=25, but 8b had to *win* to justify 1.9× latency + 2.6 GiB — it didn't, and it owned both unrecoverable failures. **4b wins the load-bearing path.**

**1b. C10 think-suppression matrix (0.32.5 + qwen3:4b) — phase0's "/no_think" advice is WRONG.** VERIFIED: `think:false` + `format:schema` WORKS on both /api/generate and /api/chat (clean JSON, 24 tok, zero reasoning). `/no_think` suffix is BROKEN on both endpoints (chat: 300/300 tokens burned thinking, empty content; generate: empty response). `think:false` *without* `format` is IGNORED on both endpoints — 300 tok of reasoning dumped into the response, 80–100 s stall. **Working invocation for builders:** `POST /api/chat {"messages":[…], "think":false, "format":<json-schema>, "options":{"temperature":0,"num_predict":400}}`. The schema constraint is what actually suppresses thinking; free-text tasks must use a schema wrapper (`{"translation":str}` etc.) — VERIFIED working. Upstream: `think` inside `options{}` is silently ignored (ollama/ollama#14793); we pass it top-level, but qwen3 only honors it under grammar constraint.

**1c. Ollama bump.** Ran latest stable v0.33.3 (2026-09-02) isolated on port 11435, same model store: **think:false-without-format still ignored on both endpoints — identical to 0.32.5** (VERIFIED). Bump value is only the v0.32.15 parser-wedge fix + v0.33.0 prefill restore-points (retries resume prefill — helps our retry path). Safe, mildly warranted; pin one version at build start and freeze.

**1d. Zero-shot baseline cost** (metrics-table row): ~360-tok prompt (shared prefix cached) + ~12 output tok ⇒ throttled ≈7.5 s/report → 1k ≈ 2.1 h, 2k ≈ 4.2 h; unthrottled ≈2.9 s → 1k ≈ 50 min. **Feasible as overnight local precompute on 4b even under clamp.** Kaggle P100 ~15–30 min (INFERRED, post-C1 fix).

**1e. Hindi probe** (6 industrial-safety sentences, schema-wrapped): 4b = 2/6 acceptable, 2/6 garbled, 2/6 total gibberish (welding-fire → nonsense about conductors; dropped-object → hallucinated shock). The शोक/grief bug didn't literally recur when the instruction states the correct term — still demo-unsafe. **8b clearly better (3/6 good) but still 1/6 nonsense** ("shiny iron utensils" for welding). Neither is safe for live/free translation.

## 2. Risks

- **SEV1-1 (count=1): CPU clamp persists** (0.60–0.85 GHz, 41.5 °C, AC, performance governor). LLM stays non-load-bearing by design, but §E's **<100 ms p95 classification bar likely also fails** (~6× ⇒ ~180–200 ms, INFERRED) — every §E latency number is at risk. Power-profile fix (charger/BIOS/firmware) = Day-1 human task alongside C2-docker.
- **SEV2-1:** Any call forgetting `format` silently burns num_predict on reasoning (80–100 s stall). One wrapper, always schema.
- **SEV2-2:** Adopting 8b anyway (§B.7 names it) = 1.9× precompute time + 2.6 GiB for zero measured gain.
- **SEV3-1:** Hindi QA, no native speaker on team — mitigations in rec 5.
- **SEV3-2:** 8b's 8% unrecovered span-truncation tail — moot if 4b adopted (4b retries recovered 2/2).

## 3. Recommendations

1. **Runtime model (§B.7 qwen3:8b) → MODIFY to qwen3:4b.** Optionally generate demo-corpus rewordings dev-time with 8b/cloud (legal) and ship precomputed; runtime stays 4b.
2. **"pydantic + schema + exact-substring + 1 retry" (§B.7) → ADOPT**, explicit state machine: `CALL(/api/chat, think:false, format:schema, temp 0, num_predict 400) → VALIDATE (json→pydantic→enum→case-sensitive verbatim-substring, non-empty spans) → RETRY once with invalid output + error appended (recovered 2/2, VERIFIED) → FALLBACK to template from span head + rule probs; log. Circuit breaker: >20% failures over rolling 20 calls ⇒ LLM off, "standard phrasing" badge.` End-to-end failure with this design: **0/50**.
3. **C10 → MODIFY:** single schema-always wrapper mandated; delete `/no_think` from docs (VERIFIED broken); bump 0.33.3 for wedge/prefill fixes only, then freeze.
4. **Precompute (§A.5/§B.8) → ADOPT, enumerated** (keyed by sha256(normalized text)): (a) reworded explanations for every demo-corpus report — paste-demos, contrast pair, all 10 §B.3 adversarial inputs, ~20 on-screen bulk rows; (b) bulk-ingest result tables; (c) Hindi phrasebook; (d) review-queue scripted states. **Live:** classifier + gates on novel judge input (sub-second even clamped) + ONE rehearsed encore rewording. **Invisibility:** explanation card always renders instantly with template text in identical styling; a validated rewording swaps in only inside an 8 s deadline — judges cannot distinguish states.
5. **Hindi (§C) → MODIFY:** ~30-string phrasebook (8 UI labels, ~10 canned explanations, 5 gate banners, disclaimers), demo-touched screens only; dev-time cloud translation + back-translation via a *different* provider + terminology from published Hindi safety signage. Stretch slide + one precomputed card; never live translation.
6. **Zero-shot baseline (§B.5) → ADOPT as local overnight precompute** on 4b (§1d); Kaggle only after C1. Metrics-table row, never runtime.
7. **Live-LLM in demo → REJECT** beyond the single encore (20–40 s clamped / ~5 s unthrottled per call — too slow for a <1 s wow).

## 4. Verdict

The contract (schema JSON, exact spans, retry, template fallback, precompute-first) is measurably strong: 100% JSON/schema compliance, 0/50 final failures. The model choice (8b) and C10 workaround (`/no_think`) are wrong as written — cheap fixes, no redesign. The real SEV1 is the power clamp: it threatens §E latency system-wide and is a human-hardware task. **GO after the 4b swap + wrapper mandate.**
