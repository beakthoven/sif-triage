# Phase 1 — Demo Red-Teamer (attack surface: the 90 seconds on stage)

Measured 2026-09-08 on this machine unless INFERRED.

## 1. Findings

**§B.3 inputs vs actual Part-C gates (confidence · negation · language · near-dup):**

| # | Input | Gate? | Judge sees |
|---|---|---|---|
| 1 | "fell 4m. No injury occurred" | YES (negation) | Gray review-queue card |
| 2 | Sarcasm | YES (confidence τ) | Gray "insufficient signal" |
| 3 | Hinglish | PARTIAL — live translate at 4 tok/s = 30-60s freeze; precompute it | Gray card + translation |
| 4 | "Forklift incident." (18 chars) | COLLISION: min-20-char validation (#10) fires before confidence gate | "Too short to assess" — document precedence |
| 5 | 2000-word report | NO gate, chunking only; train max=2134 chars (VERIFIED) → severe length-OOD, max-pool inflates score | Card + add "length-OOD" badge |
| 6 | Deepwater Horizon | YES | Gray + rehearsed framing |
| 7 | All-9-rules report | PARTIAL (PTW/Bypass out of scope) | 7 rule bars + honest line |
| 8 | "Fire drill completed" | **MISSING from Part C** — confident RED live | Needs 5th gate |
| 9 | Verbatim train row | YES (near-dup) | "Memory, not generalization" banner |
| 10 | Empty/garbage | YES | Rejection toast |

**5 new attacks:** (a) **Baghjan narrative** — model correctly reds; the trap is our mouth. Rehearse: "we raise precursor visibility, we don't replace well-control assurance." (b) **Assamese script** — OSHA non-ASCII = 0.000000 (VERIFIED); langdetect→gray "language not yet supported," never attempt translation. (c) **Codes-only "LOTO not applied"** = 16 chars (VERIFIED) → min-length validation rejects a *legit* terse report — humiliating. Fix: code-word whitelist → gray "terse, low-information" + Energy-Isolation keyword tag. (d) **Our own synthetic row** — banner only fires if synthetic corpus is in the pgvector index; index must = OSHA-train + ASRS + synthetic. (e) **First-aid case** — no gate, pure model quality; add to adversarial suite, expected GREEN; if it reds live: "this is why humans dispose."

**Throttle math (C3, honest):** ModernBERT-base = 22 layers × ~5.0M MACs/token ≈ 110M MACs/token → **28 GFLOPs/text at seq128** (the ~0.15 GFLOP figure is per-token, ~190× off). Measured anchor: fp32 GEMM 53 GFLOPS at 0.73GHz = 28% of Zen5 peak. Int8 VNNI peak at 0.85GHz ≈ 1.74 TOPS; at 25-45% efficiency → **classify p95 ≈ 50-120ms clamped** (INFERRED from anchor), ~10-20ms unclamped. **Bulk 5k at ≥500/s needs ~7 TOPS sustained — impossible even unclamped** (realistic ceiling 150-330/s with seq64 bucketing; clamped ~40-90/s → 5k = 1-2 min, not 10s). AC online, battery 100%, clamp persists (VERIFIED).

**Near-dup FP proxy (VERIFIED, char 3-5gram TF-IDF, 4k fall narratives, 20k distinct pairs):** p99.9=0.39, max=0.62, zero pairs >0.8. But one-word template twin ("…wrist/ankle") = 0.81; MiniLM semantic cosine runs hotter. 0.9 threshold probably safe — validate in embedding space.

## 2. Risks

- **SEV1-1:** Live 5k ingest + "<1s card" scripted live under unresolved 0.85GHz clamp — the script as written fails on stage.
- **SEV1-2:** Docker daemon DOWN (C2) — compose demo, tarball, unplug rehearsal all blocked; bare-metal fallback must be rehearsed, not theoretical.
- **SEV2-1:** Drill filter missing → confident false-red on judge attack #8.
- **SEV2-2:** Min-length rejects legit codes-only reports.
- **SEV2-3:** "<100ms p95" slide + §E "≥500/s" are unmeasured claims current hardware can't honor.
- **SEV3-1:** Browser DNS/cache stalls on NIC flap — use 127.0.0.1 literal, vendored fonts, verify zero external requests via Playwright offline run.
- **SEV3-2:** Demo-corpus rows re-pasted self-trigger the near-dup banner — exclude session inserts or show "already submitted."

## 3. Recommendations

- **ADOPT** precompute-everything + gray-card doctrine — it makes any judge input survivable.
- **MODIFY** demo flow: 5k ingest precomputed, progress replayed from real run log; live-classify only a visible ~100-row batch (~2-6s clamped, honest).
- **MODIFY** §E fast-bar → "≥200 reports/s, length-bucketed seq≤64, measured"; latency slide kept ONLY if clamp fixed and p95 re-measured <100ms.
- **MODIFY** gates: add drill filter (5th gate, half-day LF), terse-code whitelist, precedence order (validation→language→length→confidence→negation→near-dup).
- **MODIFY** near-dup: threshold from measured embedding-space curve (66 known dups + template twins, FP<0.1%); index includes synthetic.
- **Unplug move:** kill WiFi too; dashboard pinned to 127.0.0.1; offline Playwright network-log verification; rehearsed bare-metal fallback (uvicorn + local postgres + host-native ollama).
- **90s recording:** Day-3 morning, non-presenting teammate, Playwright-driven pacing, laptop + USB; becomes primary if final rehearsal fails twice. Hotspot = pre-demo dependency pulls only.
- **Judge's own report: GO unconditionally** — every failure mode ends in a designed gray card; framing: "if the model is unsure it says so — model proposes, HSE disposes." Route >500-word reports to async.
- **REJECT** live LLM Hinglish translation under clamp; **REJECT** quoting 500/s or <100ms until measured.

## 4. Verdict

Demo philosophy (precompute + gray gates + triage framing) is sound — hostile inputs are safe by construction. Not stage-ready as written: two latency/throughput claims exceed measured hardware reality under C3, drill gate absent, docker down. All fixable Day 1-2.
