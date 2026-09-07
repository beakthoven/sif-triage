# Phase 1 — NLP Training Engineer (PS 26165)

Attacks: multi-task design, outcome-masking, seq_len, imbalance, P100 budget, session strategy.
Measurements today: ModernBERT tokenizer on 20k sampled OSHA narratives (local `tokenizers` 0.23.2, official `tokenizer.json`); masking/keyword probes via pandas. FLOPs math VERIFIED-arithmetic, MFU INFERRED.

## 1. Findings (with numbers)

**seq_len=128 — VERIFIED, claim holds.** Chars/token = 4.54. Token lengths (incl. [CLS]/[SEP]): mean 43.6, median 40, p95 80, **p99 = 112**, p99.9 = 165, max 252. **0.38%** of narratives exceed 128 tokens; none exceed 256. 128 covers p99 as claimed. Keep 128; the 0.38% tail is already handled by sliding-window gate §B.3#5. 256 would cost ~2× compute for 0.4% of data — reject.

**Outcome-masking: method in Part C is broken; fix is free.** "Strip outcome clauses" at sentence granularity: **19.1% of rows become EMPTY, 20.1% <40 chars** (n=5000, 6-stem list); mean 199→126 chars. That destroys 1/5 of the corpus and biases against short narratives. Token-level neutralization (outcome stems → `injury`): 70.5% of rows modified, **0% empty**, mean length 199→195 chars. Mandate token/phrase-level masking, not clause-stripping.

**Span head: label coverage is the real cost.** No token-level gold exists, and the 4-person-hour gold budget (300–500 reports ≈ 29 s/report) cannot span-label. Heuristic keyword anchors measured per-rule coverage inside positive narratives: `fell` 86.8% (falls), `caught` 39.5% / `pinch` 12% / `between` 28.5% (caught-in, union ≈55%), `struck` 26.3% / `hit` 7.3% (struck-by, union ≈30%); 72.8% of all narratives have ≥1 mechanism keyword. So heuristic spans are feasible but noisy and rule-skewed. Part E's "span exact-match ≥95% on gold" is unreachable under weak supervision AND undefined (no human span gold). Fallbacks already exist: LLM span extraction was 4/4 verbatim on this machine; rendering can project any predicted span onto the source text (verbatim by construction).

**Masking is the right leakage fix.** Near-miss register confirmed absent in OSHA (28 'almost', 3 'could have'); labels derive from OIICS mechanism, not outcome, so outcome words are pure proxy-leakage. Masking aligns train with the deployment distribution (near-miss has no outcome vocab). Signal destroyed is minimal (length-neutral per above; mechanism keywords retained).

**Imbalance.** Binary ~55–60% positives: near-balanced; class-weighting is noise (ratio ~1.2:1) — use plain BCE + validation-tuned threshold for recall@precision≥0.80. Rules: support spans LoF ~40% → CS ~2.5% (16:1). CS still has ~1.5k positives at 60k rows — learnable. Use per-rule pos_weight (capped ≤5) **and** per-rule thresholds tuned on val (F1-optimal); thresholds alone under-train rare rules, weights alone distort calibration.

**P100 training budget — fits comfortably.** Fwd+bwd ≈ 6·N·S = 6×111M×128 ≈ 8.5e10 FLOPs/example (attention ~4%). 60k texts × 3 epochs, padded 128: ~1.5e16 FLOPs. P100: fp16 18.7 TFLOPS peak (fp32 9.3; native fp16 CUDA cores, no tensor cores). At 25–40% MFU (typical BERT-base, short seq): **~25–60 min/run**; dynamic padding → ~half. Both variants + baselines ≈ 1.5–2.5 GPU-h of the 30 h quota — >10 full iterations of headroom. Batch 32 fp16 ≈ 4–5 GB VRAM — fits; batch 64 OK. Two P100 gotchas: **flash-attention-2 does not support sm_60** — must load with `attn_implementation="sdpa"`; AMP needs GradScaler fp16 (no bf16).

**One session, sequential variants.** Torch sm_60 reinstall (≤2.6/cu124) is a per-session ~2.5 GB download (INFERRED 5–15 min); GPU allocation is a lottery; session death is the classic death. One notebook: export-smoke-test (C4) → train masked → checkpoint+push to Kaggle Dataset → train unmasked → push. Never two sessions.

## 2. Risks

- **SEV1: none.** All architecture-level blockers have in-plan fixes.
- **SEV2-a: clause-stripping masking** (19% data destruction) — as written in Part C; fix: token-level neutralization.
- **SEV2-b: span-head acceptance metric** ("≥95% exact-match on gold") unreachable/undefined — no human span gold fits the 4-hour budget; weak labels cap token-F1 ≈0.6–0.8 (INFERRED).
- **SEV2-c: FA2-on-P100 crash** if `sdpa` not forced — costs a debugging cycle.
- **SEV3:** word-list sensitivity of masking (70.4% vs 76.4%) — freeze list in label spec; per-rule label noise on CS/EI proxies (P0-2 caveat).

## 3. Recommendations

- **ModernBERT-base multi-task (binary + 7-rule): ADOPT.**
- **Span head: MODIFY.** Train on weak keyword-anchor labels (cheap, deterministic, gives the <100 ms no-LLM highlight); relabel acceptance metric to **token-F1 vs LLM-annotated dev spans (target ≥0.7)** plus render-time verbatim guarantee; humans never span-label gold. If token-F1 <0.5 on the dev check, cut the head and fall back to LLM/keyword highlight — demo unaffected (precomputed evidence).
- **Outcome-masking: MODIFY** to token-level neutralization; frozen stem list in label spec.
- **Ablation set (exact):** A unmasked-train/masked-eval (leakage dependence); B masked/masked (headline, deployment condition); C masked/unmasked (robustness); D unmasked/unmasked (leaky ceiling; D−B = what leakage buys); E masked model on synthetic OIL near-miss corpus + ASRS negatives (target-distribution sanity).
- **Loss: MODIFY** — plain BCE for binary; per-rule capped pos_weight + per-rule tuned thresholds for rules.
- **seq_len 128: ADOPT.**
- **One notebook session for both variants: ADOPT (mandate).**
- **Training estimate 15–40 min (handoff, 2×T4): MODIFY to 25–60 min/run on 1× P100** — still fits trivially.

## 4. Verdict

Model architecture is sound and P100-feasible with two mandatory corrections (token-level masking, sdpa attention) and one scope redefinition (span-head metric). Nothing here kills the project; the masking bug would have silently cost 19% of training data.
