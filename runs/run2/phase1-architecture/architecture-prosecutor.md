# Phase 1 — Architecture Prosecutor (integration / kill-shot hunt)

Role: architecture-prosecutor · PS 26165 · Date 2026-09-08 · VERIFIED = measured this session; INFERRED marked.

## 1. Findings (with numbers)

**Critical path & stall points.** True chain: label-spec → OSHA parse + ASRS weak-labels + synthetic corpus → Kaggle train → ONNX export → API contract → dashboard → offline package → blind gold → §E. Stall-prone handoffs, with earliest smoke test + deadline:
- **torch-pin on P100** (C1). VERIFIED independently: PyTorch dropped sm_60 from cu128/cu129 builds (dev-discuss, PR #158478); cu124/cu126 wheels cover sm_50–90, and cu126 exists through torch 2.14. Fix is real but unexecuted. Smoke test: notebook installs `torch==2.6.0+cu124` + pinned transformers 4.x, runs 10 fine-tune steps on 100 dummy rows, saves+retrieves checkpoint. **Deadline H4 Day 1.**
- **ONNX multi-task export** (C4). optimum's task library does not cover a custom SIF+7-rule+span head (INFERRED from optimum design); probe must export the *actual* head architecture, not stock ModernBERT. **Deadline H6 Day 1**, before first real training run.
- **Dashboard ↔ API.** Contract must freeze as OpenAPI JSON by **H8 Day 1** or Day-2 dashboard stream blocks.
- **Gold labeling ↔ metrics.** §E recall@precision-CI and span≥95% both need the gold set; nothing else on Day 3 may slip into it.

**Contradictions found:**
1. **Span head is unbuildable as drawn.** §C dev-time has NO span-supervision derivation step (OSHA has no span labels), and §A.4's gold task is SIF labels only — yet §E demands "span exact-match ≥95% on gold." Neither training signal nor eval labels exist. SEV1.
2. **seq128 vs 2000-word adversarial input (§B.3 #5).** §C has no chunking node and no owner. Worse: span-head offsets across sliding windows need re-mapping to source text or evidence highlighting breaks on exactly the demo attack. Assign to API layer (window overlap + offset remap + max-pool). MODERNBERT p99 claim covers OSHA (max 2134 chars), not the attack input (~13k chars).
3. **RAM budget copy error.** §B.4 "Ollama 8B Q4 ~3.2 GB" — VERIFIED that 3.2 GB is the *4B* RSS (ollama ps: 2.97 GiB now). 8B blob is 4.87 GiB → RSS ~5.3–5.6 GiB (INFERRED). Real peak ≈ 6.5 GiB stack vs 13 GiB available now — fits, but the number in the deck must be remeasured, not quoted.
4. **Synthetic corpus timing is fiction at local speed.** 8–10k reports × ~150 tokens at measured 4 tok/s (clamp) = ~100 h serial; even unclamped 21 tok/s ≈ 20 h. Must be dev-time cloud LLM (legal per §A.2) or template generation. Local Ollama gen cannot be on the Day-1 critical path.
5. **pgvector-Postgres + Label Studio both silently require the dead docker daemon** (C2). Gold labeling tooling currently has no working platform.
6. **"No torch at runtime" vs CPU-fallback training on the demo machine** — compatible only if serving venv is torch-free and training venv separate; state it or §E offline-demo audit gets messy.

## 2. Risks ranked

**SEV1 (project-killers):**
1. **P100 torch-pin unresolved** — no pin, no training; CPU fallback at 0.85 GHz clamp is 6–12 h for a 5k config = dead. Fallback demand: H4 smoke test; last-resort fallback = official ONNX encoder frozen + sklearn heads trained CPU-side in minutes (shippable, honest).
2. **Docker daemon down, needs root** (C2) — blocks compose packaging, pgvector, Label Studio, "one-command up" in §E. Human escalation Day 1 H0; fallback: bare-metal run scripts + SQLite + numpy cosine near-dup. If root never comes: accept-and-document, rehearse bare-metal demo.
3. **Span-head hole end-to-end** (supervision + gold span annotation missing) — de-scope to deterministic keyword-attribution highlighting OR add weak keyword-derived span labels + gold span annotation. Decide at H2 label-spec freeze, not Day 2.
4. **CPU clamp 0.85 GHz persists** (VERIFIED: all cores 0.85 GHz right now) — §E "<100 ms p95, ≥500 reports/s" is measured on this machine; at ~6× slowdown the INT8 model lands ~180 ms and ingest ~80/s: acceptance fails. Human investigates power adapter/BIOS Day 1; else re-benchmark and report honest numbers.

**SEV2 (quality-killers):** synthetic-corpus schedule (use cloud LLM, see #4 above); gold-set effort underestimated — 500 reports × (label+spans) ≈ 45–60 s each = 6–8 person-hours, not 4 (A.4); zero-shot-LLM baseline at 4 tok/s → cap n≤200 or run via cloud; ASRS weak-label derivation (C6) is new unscheduled Day-1 work; Snorkel frozen (C11) → plain heuristic LFs.

**SEV3:** think:false workaround (C10) — /no_think; git init (C12); psycopg LGPL note.

## 3. Recommendations per §C element

- OIICS label derivation / dual maps: **ADOPT** (validated P0-1).
- Outcome-masking + ablation: **ADOPT**; mask word-list frozen in label spec (C9).
- Snorkel: **REJECT** → plain heuristic LFs (C11; one less stale dep).
- ASRS negatives: **MODIFY** → add Events_Anomaly/Assessments weak-label step, owner + 2 h budget.
- Synthetic corpus: **MODIFY** → cloud-LLM generation at dev time; DGMS/OISD vocab acquisition needs an explicit owner (currently nobody).
- Multi-task span head: **MODIFY** → cut to keyword-attribution unless span supervision is specced at H2.
- Kaggle training: **MODIFY** → pin torch 2.6+cu124 & transformers 4.x; re-probe GPU each session; checkpoint→Kaggle Dataset mirror per run (already good).
- Baselines: **MODIFY** → zero-shot n≤200 via cloud LLM.
- ONNX int8 + parity gate: **ADOPT**, gate moved BEFORE training (already C4).
- Postgres+pgvector: **MODIFY** → SQLite + numpy cosine fallback pre-built; docker path only if daemon fixed by Day 2.
- FastAPI: **MODIFY** → owns chunking/offset-remap; OpenAPI contract frozen H8.
- React dashboard: **ADOPT** against mocked contract.
- Ollama layer: **MODIFY** → 100% precomputed for demo; live path is encore only (clamp).
- Docker compose packaging: **MODIFY** → bare-metal scripts as equal-priority deliverable, rehearsed Day 2.

**Day-1 resequence:** H0 docker+power human escalation; H0–2 label spec (incl. span decision); H1–4 Kaggle torch smoke; H2–6 ONNX probe (local CPU, parallel); H2–8 data pipeline ∥ synthetic corpus (cloud); H6–12 train run 1 + regex/TF-IDF baselines; H12–16 export+parity+mirror. First slip: torch pin. Pre-emptively de-scoped: span head, pattern mining (→static table), zero-shot n.

**Stage embarrassment top-3 + insurance:** (1) live demo stutters (clamp/docker) → bare-metal fallback + 90 s recording + precomputed outputs; (2) circularity/leakage Q&A → blind gold done by Day 2 late + ablation table + §B.6 rehearsal; (3) everything-gray on adversarial input → tune gates on synthetic corpus, rehearse contrast pair, near-dup banner as feature.

## 4. Verdict

Architecture is directionally sound; §C as written is NOT executable — span head unspecified end-to-end, chunking unowned, two hard deps on a dead daemon, and Day 1 assumes local-LLM generation speeds this machine cannot deliver. With the MODIFY list applied: GO.

<<SCORES {"ps":"26165","role":"architecture-prosecutor","go_no_go":6,"severity":4,"feasibility":7,"data_risk":3}>>
