# HANDOFF — SIH26165 SIF-Precursor Detection Engine (OIL India)

**To the model receiving this:** you are a Kimi-K3 orchestrator agent in the exact same environment this file was written in (Linux, working dir `/home/dakkshesh/sih26-round2`, `gh` CLI authenticated as `beakthoven`, **Kaggle MCP with 2x NVIDIA T4 GPUs, 30 GPU-hours/week quota**, AgentSwarm + subagent tools, skills system, Ollama 0.32.5 installed). This file is your **entire prior context** — a multi-round, 150+ agent research program has already been run. Do NOT redo it blindly. Your job: **validate → refine via swarm → build → test → ship** a production-grade solution in **3 days of 24/7 execution**.

---

# PART A — YOUR MISSION PROMPT

## A.0 The three governing doctrines (read first, obey always)

**Doctrine 1 — INDEPENDENT VALIDATION.** Every fact in this handoff was verified once, by agents, in the past. You do not trust it. Before any load-bearing fact influences a decision, **re-validate it independently**: re-run the probe, re-check the file, re-query the API, re-measure on this machine. Facts decay (a government API died mid-run twice during the research that produced this file). Budget the first hours of Phase 0 for validation of anything the build depends on: data files, schema numbers, model repos, API endpoints, quota/session type (this handoff originally assumed a P100 GPU — it is in fact 2x T4; verify the actual session type via the Kaggle MCP before writing the training notebook). Where a fact fails re-validation, fix the plan, note the correction, move on. Verification is cheap; building on a lie is fatal.

**Doctrine 2 — SWARM DEBATE + VALIDATION, ALWAYS.** Never take a single inference — yours or anyone's — as truth. For every research question, design decision, architecture choice, and pre-ship validation, **spawn a network of agents with diverse, adversarial personas** (advocates, prosecutors, domain specialists, red-teamers, validators), let them fight, and aggregate their structured verdicts. Individual agents are noisy estimators; a diversified panel's aggregated signal is the best estimate available — this is the same reason markets price better than analysts. Concretely:
- Use `AgentSwarm` for every non-trivial research/review/validation step: minimum a pro/con pair, ideally 4–12 specialists for load-bearing decisions.
- Enforce the machine-readable verdict convention in every swarm prompt: agents end with `<<SCORES {"ps":"...","role":"...","go_no_go":N,...}>>` so `pipeline/aggregate_scores.py` can average the noise quantitatively.
- You are the adjudicator: read the disagreements, rule on them with evidence, document why the losing side lost (their arguments become your Q&A defense).
- Persona prompts and mitigation patterns are already written for you in `~/.kimi-code/skills/sih-ps-selector/references/` — reuse or fork them.

**Doctrine 3 — EXHAUSTIVE, QUALITY-FIRST, FULL AUTONOMY.** Inside the 3-day box and the hard constraints (§A.2), quality is the only objective and you have unlimited latitude to reach it: create your own skills, scripts, pipeline infrastructure, test harnesses, and sub-workflows; use every tool, MCP server, and CLI at your disposal to its fullest; spend tokens, API calls, and swarm agents freely — the cost of one more validation round is always lower than the cost of shipping something wrong. "No matter what it takes" within the constraints means: exhaust the search, never cut a corner that affects accuracy, honesty, or demo reliability.

## A.1 What you are building

**SIH 2026 Problem Statement 26165** (Oil India Limited, Theme: Miscellaneous):
> "AI/NLP Engine to Detect Serious Injury & Fatality (SIF) Precursors in OIL's Unsafe-Act/Unsafe-Condition and Near-Miss Reports."
> Build a prototype that ingests OIL's free-text safety reports and automatically:
> (a) classifies each as SIF-potential vs non-SIF-potential,
> (b) tags it to the relevant IOGP Life-Saving Rule (Energy Isolation, Hot Work, Confined Space, Line of Fire, etc.),
> (c) surfaces recurring precursor patterns (activity, location, barrier failure) via a dashboard ranking sites/activities by SIF-precursor density.
> Context: OIL triages UA/UC + near-miss reports manually, monthly/quarterly. Research (DEKRA Martin & Black 2015, EEI, VelocityEHS 2024 PSIF) shows low-severity incidents don't share causes with fatalities — leading operators flag the ~20–25% of reports with genuine fatal potential. [CORRECTED 2026-09-08: the sources say ~20% of *recordable injuries* (BST/Mercer ORC 2011; Martin & Black 2015) — see ARCHITECTURE.md claim boundary. Never quote the 20–25%-of-reports form.] OIL provides NO dataset (their reports are confidential).

**The 9 IOGP Life-Saving Rules:** Bypassing Safety Controls, Confined Space, Driving, Energy Isolation, Hot Work, Line of Fire, Safe Mechanical Lifting, Permit to Work, Working at Height.

## A.2 Hard constraints (non-negotiable)

1. **NO image/vision AI anywhere.**
2. **Runtime = 100% local, zero cloud third-party dependencies** (personal data-privacy requirement). Cloud LLMs (Qwen/Kimi/DeepSeek/GPT etc.) are allowed **ONLY at development time** (synthetic data generation, labeling QA). Cloud LLMs must never see anything but public data + generated text.
3. **Demo runs on this exact machine** (profile in §B.4) — must work offline.
4. **Training compute: Kaggle, 2x NVIDIA T4 GPUs, ~30 GPU-hours/week quota** (via Kaggle MCP) — ample; a fine-tune run costs roughly 15–40 min. Verify session type yourself (Doctrine 1).
5. **Team: 2–4 students, full-stack + LLM strength. Demo must impress non-technical judges AND survive hostile technical Q&A from OIL HSE experts.**
6. **Timeline: 3 days, 24/7 agentic execution.**

## A.3 Your operating mode

**Phase 0 (first 2–3 hours) — READ + INDEPENDENTLY VALIDATE.** Read this file fully, then the artifacts on disk. Re-validate every load-bearing fact per Doctrine 1: the OSHA CSV's shape and label coverage, ASRS accessibility, model repo availability, Ollama functionality on this machine, Kaggle session type (2x T4) and quota via MCP, network access. Log each as VERIFIED / CORRECTED / FAILED in your working notes.

**Phase 1 — ARCHITECTURE REFINEMENT SWARM (mandatory before coding).** The architecture in §C is your *starting foundation*, not gospel. Spawn an AgentSwarm of 8–12 specialist agents (NLP training engineer, data pipeline engineer, MLOps, full-stack architect, demo red-teamer, HSE domain reviewer, evaluation/metrics engineer, local-LLM ops, UX designer, methodology skeptic) to attack and improve it — each gets §B + §C + the constraint set. Aggregate their structured verdicts (Doctrine 2). Adopt what survives scrutiny; document rejected proposals briefly. Swarm infrastructure: `~/.kimi-code/skills/sih-ps-selector/` (rosters + methodology), `pipeline/` (item builder + score aggregator).

**Phase 2 — BUILD (72-hour plan in §D).** Parallelize independent streams (data pipeline ∥ training ∥ dashboard) across subagents. Use **established OSS aggressively** (§B.7) — integrate anything that improves speed or output quality, runtime stays local-only. Swarm-review each critical component after it's built (a 2–4 agent adversarial review per component: correctness, edge cases, quality).

**Phase 3 — PROOF (test, harden, rehearse).** The acceptance bar in §E is the definition of done. Run the adversarial input suite (§B.3). Rehearse the demo offline on this machine — ethernet unplugged. Final gate: a swarm validation round (fresh-eyes agents auditing the built system against the PS text and §E).

**Toolkit, use it all to the max:** AgentSwarm for parallel research/build/review; Kaggle MCP for GPU training (2x T4); `gh` CLI for OSS discovery; WebSearch/FetchURL for verification; the `webapp-testing` skill (Playwright) for e2e UI tests; other skills as relevant; file + bash tools for everything else. Measure on this machine any number that matters.

## A.4 Non-delegable human tasks (tell the user, schedule them)

1. **Blind gold-set labeling: 300–500 reports, ~4 person-hours, Day 3.** Humans label WITHOUT seeing model/LLM output (anti-circularity). Eval-only, never trained on.
2. Demo-day physical presence + rehearsal attendance.
3. (Optional, if time) one domain-expert review of ~50 synthetic OIL-style reports (~₹3k via LinkedIn outreach to a retired ONGC/OIL HSE officer). Deferred-risk mitigation only.

## A.5 The three mandatory disciplines (violating any one is a project-killer)

1. **Triage framing, never prediction.** We are a "hazard-exposure triage tool validated against human-adjudicated labels." Never claim fatality-prediction accuracy.
2. **The blind gold set is human-labeled, LLM-hidden, eval-only.** No exceptions — this is the answer to the circularity kill-question.
3. **Precompute everything demoable.** The live local-LLM path is the encore, never the foundation.

---

# PART B — KNOWLEDGE BASE (research output of the prior program — re-validate per Doctrine 1 before relying on it)

## B.1 Verified data assets

| Asset | Path / URL | Facts (verified at research time — re-check) |
|---|---|---|
| **OSHA Severe Injury Reports** | `data/January2015toNovember2025.csv` (+ `data/osha_sir.zip`) | **105,996 rows**, 28 cols, Jan 2015–Nov 2025, official osha.gov download (dashboard: osha.gov/severe-injury-reports → `/sites/default/files/January2015toNovember2025.zip`). Columns: `ID, UPA, EventDate, Employer, Address1/2, City, State, Zip, Latitude, Longitude, Primary NAICS, Hospitalized, Amputation, Loss of Eye, Inspection, Final Narrative, Nature/NatureTitle, Part of Body/Title, Event/EventTitle, Source/SourceTitle, Secondary Source/Title, FederalState`. `Final Narrative` = free text, 0% missing, median 182 chars/31 words, p95=371 chars, max 2134. US federal public domain. |
| **NASA ASRS** | HF `elihoole/asrs-aviation-reports` | **47,723 near-miss narratives**, Apache-2.0, not gated, train/val/test JSONL (~270/30/33 MB), download path verified (302→CDN works). The only large REAL near-miss corpus — supplies the counterfactual register ("almost", "could have") OSHA lacks. Use for near-miss language + negatives; aviation vocab ≠ oilfield (robustness/augmentation, not primary signal). |
| **SmartQHSE process-safety vignettes** | HF `SmartQHSE/major-process-safety-incidents-2026`, `named-process-safety-incidents-extended-2026` | 15–40 famous disasters (Bhopal, Piper Alpha, Macondo/Deepwater Horizon), CC-BY-4.0. Demo vignettes only. |
| **Synthetic oil-gas safety (style ref)** | HF `electricsheepafrica/africa-synth-energy-oilgas-safety-incidents-nigeria` | Style reference for generating OIL-register text. |
| **PS dataset (full SIH list)** | `data/sih2026_ps.csv`, `data/software_ps.json` | 226 PS total / 172 software. 26165's `dataset link` field is empty. |
| Prior run artifacts | `runs/run1/` | All swarm outputs + aggregated scores from the selection pipeline. |

**OSHA label-mapping coverage (measured):** high-energy OIICS prefixes → `62*` struck-by 14,799; `64*` caught-in 23,626; `43*` fall-to-lower-level 17,509; `51*` electrocution 2,106; `32*` thermal 713 → **58,753 rows = 55.4%**; adding `53*` heat exposure (4,632) → 59.8%.

**OSHA → IOGP rule coverage (measured, keyword/code proxy):** Line of Fire 45.7%, Working at Height 15.5%, Driving 12.4%, Energy Isolation 6.5%, Hot Work 5.2%, Safe Mechanical Lifting 3.5%, Confined Space 2.5% — **Bypassing Safety Controls 0.08%, Permit to Work 0.00% (3 rows)**. These two are *procedural* violations invisible in post-injury text → **declare them "not inferable from injury narratives" on the slide; never fake them.**

## B.2 The five SEV1 traps found by the pre-mortem swarm (all mitigations baked into §C)

1. **No negative class:** 99.4% of OSHA rows are realized severe injuries (inclusion criterion: hospitalization/amputation/eye-loss). `Hospitalized`/`Amputation` are COUNTS (0–6), not flags — binarize `>0`. `Loss of Eye` = 35 rows, drop. Negatives must come from ASRS + synthetic + low-energy OIICS categories.
2. **Outcome-word leakage:** 70.4% of narratives contain outcome words; P(Amputation flag | "amputat" in text) = **98.6%**. Outcome vocabulary NEVER appears in near-miss text ("almost"=28 rows, "could have"=3). → **outcome-masking** before training (strip outcome clauses); report masked vs unmasked ablation.
3. **Two IOGP rules unlearnable** (see above).
4. **Label circularity:** LLM-labels → humans-audit-LLM = anchoring (+10–20% agreement). → labels derived deterministically from human-coded OIICS; humans label gold BLIND; labeler-LLM and judge-LLM must be different providers (dev-time only anyway).
5. **Domain shift:** only 2.6–3.3% of OSHA rows are oil & gas NAICS (211/213); `workover`=36 rows, `christmas tree`=13, `h2s`=12; imperial units; US legalese register. → synthetic OIL-style corpus + DGMS-vocabulary grounding + pipeline-first framing.

**Also:** OIICS taxonomy breaks in 2024 (v1 titles 2015–23, v2 titles 2024–25; comma-loss artifact jumps 0.1%→66%) → build dual label maps or roll up to parent codes. `NatureTitle` has whitespace variants ('Fractures' vs ' Fractures   ') → `.strip()` everything. 66 exact-dup narratives → dedup before splitting. 70.9% of narratives open with "An employee was…" → template overfitting risk; de-boilerplate features. Splits: employer-grouped + temporal (train ≤2023, test 2024–25).

**Indian data reality:** DGMS portals login-gated; no public Indian oil-safety narrative corpus exists. OISD is India's standards body — cite OISD alongside IOGP on slides (Indian oil PSUs already run IOGP-derived "Life Saving Rules" campaigns). OIL context: Assam fields, Duliajan, GGS/GCS/EPS installations, workover rigs, contractor-heavy workforce, monsoon hazards. Baghjan 2020 blowout is the reference disaster judges may name — the honest answer: "swiss-cheese — we raise precursor visibility, we don't replace well-control assurance."

## B.3 Adversarial judge inputs (demo red-team — build the gates)

| # | Input | Risk | Gate |
|---|---|---|---|
| 1 | "Worker fell 4m. No injury occurred." | Negation unseen in training → false red | NegEx-style negation layer → forces review queue, never auto-green |
| 2 | Sarcasm ("Great, another day nobody died") | OOD instability | Confidence gate: max-prob < τ → gray "insufficient signal" card |
| 3 | Hinglish report | OOD (OSHA is 0% non-ASCII) | Language detect → translate (dev-time phrasebook / local LLM) → score |
| 4 | "Forklift incident." (2 words) | Keyword red | Min-length + confidence gate |
| 5 | 2000-word report | Truncation | Sliding-window chunking, max-pool score |
| 6 | Deepwater Horizon summary | Off-corpus vocab | Gray gate + honest framing |
| 7 | All-9-rules mega report | Under-tagging | Show per-rule probabilities, not binary tags |
| 8 | "Fire drill completed, no hazards" | Drill false-red | Drill/simulation filter |
| 9 | Verbatim OSHA row from train set | "You memorized!" | Near-dup detector (cosine > 0.9) → banner: "matches training record — memory, not generalization." Converts attack into the duplicate-detection feature |
| 10 | Empty/garbage | Crash | Input validation, min 20 chars |

Leakage hygiene: temporal + employer-grouped splits, state them on a slide, run near-dup check live. Latency budget: classify <100ms, near-dup check ~200ms, LLM evidence async.

## B.4 Machine profile (the demo target — measured; re-verify)

AMD Ryzen AI 7 350 (8c/16t Zen5, AVX-512), 30 GB RAM (~13 used at idle), Radeon 860M iGPU (**gfx1152 — NOT officially ROCm/Ollama-GPU supported; Vulkan offload ≤+30% optional experiment, never load-bearing**), NO NVIDIA, 517 GB free disk, Ollama 0.32.5 (consider bump to ≥0.33). No torch installed yet.

**Live benchmark on this machine (qwen3:4b Q4_K_M, temp 0, think=false):** ~148–161 tok/s prompt, ~21 tok/s gen; **4/4 verbatim-exact evidence spans** across 4 extraction tests with Ollama JSON-schema enforcement; correctly abstained on a hallucination probe; Hindi at 4B is weak ("shock"→"शोक"/grief — use 8B minimum for any Hindi, or phrasebook). RAM budget verified: ONNX classifier ~0.6 GB + Postgres ~0.3 GB + dashboard ~0.1 GB + Ollama 8B Q4 ~3.2 GB ≈ **5 GB peak**.

## B.5 Model & training decisions (with rationale)

- **ModernBERT-base** (`answerdotai/ModernBERT-base`, Apache-2.0, ~149M, ONNX-tagged) over DistilBERT: ~2× faster, better accuracy, drop-in. seq_len=128 covers p99 of narratives.
- **Multi-task head:** binary SIF + 7-way multi-label rules (class-weighted BCE) + **token-classification span head** (evidence highlighting inside the model — deterministic, free, no runtime LLM needed for the core wow).
- **Labels:** deterministic derivation from OIICS (§B.1/B.2), NOT LLM opinion. LLM labeling assistance = dev-time optional labeling function only.
- **Training:** **Kaggle 2x T4** primary (fp16 tensor cores, 16 GB each; batch 32 seq128 fits easily; ~15–40 min/run; optionally data-parallel across both GPUs or run two configs back-to-back; ~30 GPU-hrs/week covers dozens of runs). Checkpoint every epoch → push ONNX+metrics to a private Kaggle Dataset/HF repo after each run (session-death insurance). Local CPU fallback: ~1–2h for a 5k-text config overnight (install torch CPU early, smoke-test 500 samples first). iGPU training: skip (gfx1152 ROCm is a rabbit hole).
- **Eval protocol:** employer-grouped + temporal splits; gold = 300–500 blind human labels (300@20% prevalence → recall CI [0.80,0.95], too wide — prefer 500+; 1000 → [0.85,0.94]); report **recall at fixed precision ≥0.80** (operating point, PR curve shown), macro-F1 only over rules with ≥50 gold positives (merge others into "Other" and say why), κ ± SE, temperature scaling for calibration. Baselines on ONE table: regex/keyword, TF-IDF+LogReg, zero-shot LLM, fine-tune — with CIs + McNemar p-values. If fine-tune ≈ zero-shot LLM (expected), that's a FEATURE: "1/1000th cost, deterministic, air-gapped."
- **Outcome-validation experiment (honest version):** AUC of SIF-score vs `Amputation` within fixed `EventTitle` strata + ablation with outcome clauses redacted (score should hold → mechanism, not outcome, drives it). State the restricted-range caveat.

## B.6 The never-say sentences (Q&A landmines)

1. "Our model detects SIF potential with X% accuracy." (no validated ground truth exists anywhere)
2. "It learned from 106k real safety reports like OIL's." (US post-injury proxy, different genre)
3. "The LLM validates the model's predictions." (circularity confession)
Also: never claim proprietary data access, never claim it would have caught Baghjan, never present mock/synthetic data as real without labels.

**The claim you CAN make:** "A hazard-exposure triage tool: deterministic high-energy-mechanism detection + IOGP rule tagging with human-verified extraction precision on an adjudicated gold set, reducing manual triage from monthly batches to seconds — with a human review queue whose overrides become future ground truth."

## B.7 OSS integration table (verified at research time; re-check before installing)

| Slot | Choice | Why / notes |
|---|---|---|
| Base model | `answerdotai/ModernBERT-base` | Apache-2.0, ONNX-tagged |
| Training/export | transformers + `optimum[onnxruntime]` + onnxruntime | int8 dynamic quantization (fp16 useless on CPU); parity gate on every export |
| Weak supervision | **Snorkel** | labeling functions over OIICS + keywords; LLM as one fallible LF |
| Audit/review UI (BUILD-TIME ONLY) | **Label Studio** (28.2k★, Apache-2.0, actively maintained) | docker-compose, ML-backend pre-annotation, gold export. Do NOT put in demo compose |
| Local LLM | **Ollama** (installed) + **Qwen3-8B Q4_K_M** | Ollama structured outputs (JSON-schema) built-in — skip outlines/instructor. Skip LM Studio (closed-source, distribution risk), LocalAI, llama.cpp server (duplicates) |
| Embeddings/dedup | sentence-transformers `all-MiniLM-L6-v2` + **pgvector** (inside Postgres) | skip Qdrant/FAISS (extra moving parts) |
| API | FastAPI + SQLModel + psycopg | no torch at runtime |
| Dashboard | Custom React + shadcn/ui + TanStack Table/Query + Recharts | skip Metabase/Superset/Grafana (RAM, cold-start, AGPL) |
| LLM JSON validation | pydantic (+ Ollama schema enforcement) + exact-substring span check + 1 retry | never fuzzy-match below 0.95 |
| Packaging | single docker-compose + `docker save` tarball + `ollama create` from vendored .gguf | fully offline, ~8–10 GB footprint |
| Explicitly avoid | LangChain/LlamaIndex, Celery, auth frameworks, second LLM server, vector-DB services | debugging surface; vibe-code speed |

## B.8 Demo design (offline-hardened)

- localhost docker-compose; `docker save` tarball on USB; precomputed evidence for demo corpus; hotspot + 90s recording as fallbacks; browser on same machine.
- Four input gates from §B.3 (confidence, negation, language, near-dup banner).
- Contrast pair rehearsed: "dropped spanner, no one nearby" (green) vs "dropped spanner above occupied deck" (red, Line of Fire).
- Signature move: **unplug the ethernet cable mid-demo and keep classifying** ("air-gapped by design — your incident data never leaves your premises"). PS never asks for on-prem — pitch as bonus, not compliance.
- Demo flow (90s): paste near-miss → red SIF card + span highlight + rule tag (<1s) → bulk-ingest 5k reports → site/activity density re-ranks → review queue override → "that override just became a training label" → metrics slide.
- Metrics money slide (4 numbers): recall @ precision 0.80 with Wilson CI (n=gold); κ ± SE from label audit; fine-tune within ~1.5 F1 of zero-shot LLM at 1/1000th cost, ~30ms CPU; outcome-redaction ablation AUC vs keyword baseline.

## B.9 Selection-pipeline provenance (why 26165, in one paragraph)

172 software PS → deterministic pre-filter → 24-candidate debate swarm (48 agents) → 10-finalist engineering pre-mortem (40) → 8-finalist appeal round (29) → 7-finalist verification (14) → 26165 #1 (appeal 6.14/10, top of field) → local-only re-evaluation swarm (9 agents incl. on-machine benchmarks) → score rose to ~8.4/10. Rivals and why they lost: 26102 MPLADS (API login-walled, no fraud ground truth, framing risk), 26083 Heatwave (no mortality data, "where's the AI", capped ceiling), 26155 Network Auditor (NTRO expert judges, 30-vendor scope), 26092 Scheme Matching (myScheme pre-exists; backup pick), 26068 WeatherGPT (12+ clones), 26047 (hidden vision module in PS), 26043 (CPGRAMS clone), 26046/26089/26101 (synthetic-data credibility / crowding / runtime-MCQ-on-local-8B weakness).

## B.10 Existing infrastructure (reuse, fork, or replace at your discretion — Doctrine 3)

- **Skill:** `~/.kimi-code/skills/sih-ps-selector/` — SKILL.md (5-phase adversarial methodology), `references/debate-roster.md`, `references/engineering-roster.md` (persona prompts + mitigation patterns), `references/reference-run.md`.
- **Pipeline scripts:** `pipeline/prefilter.py`, `pipeline/build_items.py`, `pipeline/aggregate_scores.py` (parses `<<SCORES {...}>>` blocks — enforce this block in every swarm prompt you write).
- **Run artifacts:** `runs/run1/` — all swarm outputs (phase1–4) + `all_blocks.json` (155 structured verdicts).

---

# PART C — FINALIZED ARCHITECTURE (your starting foundation — refine via Phase 1 swarm)

```
DEV-TIME (cloud legal; only public/synthetic data leaves the machine)
  OSHA SIR parse ──► OIICS label derivation (deterministic, dual v1/v2 maps)
       │                    │
  ASRS download ──► outcome-masking ──► Snorkel LFs ──► train/eval splits
       │                    │                              (employer-grouped + temporal)
  Synthetic OIL corpus (LLM-gen, dedup, outcome-leak filter)
       │
       ▼
  Kaggle 2x T4: ModernBERT-base multi-task fine-tune
       (SIF binary + 7-rule multi-label + span head; class-weighted BCE;
        masked & unmasked variants; ~15–40 min/run)
       │──► baseline table (regex / TF-IDF+LogReg / zero-shot LLM / fine-tune)
       ▼
  int8 ONNX export + parity gate (|Δlogit| < 1e-3) + versioned artifact
  (mirrored to private Kaggle Dataset after every run)

RUNTIME (100% local; ~5 GB RAM peak on the demo machine)
  CSV/Excel upload · paste box · JSON API (column-mapping config)
       ▼
  Ingestion → validation → Postgres 16 (+pgvector: MiniLM dedup/near-dup)
       ▼
  FastAPI + onnxruntime: ModernBERT INT8 multi-task
       → SIF score (calibrated, temperature-scaled)
       → rule probabilities (7 rules; PTW/Bypass declared out-of-scope)
       → evidence spans (span head; exact-substring validated)
       → input gates: confidence · negation · language · near-dup
       ▼
  Explanation renderer: deterministic templates (label, rule, spans, confidence)
       └── optional Ollama Qwen3-8B Q4 rewording (async, template fallback,
           grammar-enforced JSON, precomputed for demo corpus)
  Hindi: pre-translated phrasebook JSON
       ▼
  React dashboard: report feed + highlighted evidence · site/activity
  precursor-density ranking · rule breakdown · pattern mining
  (activity×location×barrier co-occurrence) · review/override queue
  (overrides → future gold labels; "model proposes, HSE disposes")
```

**Claim boundary:** triage + extraction precision + time saved. Never prediction accuracy (§B.6).

---

# PART D — 72-HOUR EXECUTION PLAN

**Day 1 (validate → data + model):** Doctrine-1 validation pass → label spec frozen (hour 2) → OSHA parse + strip/dedup → OIICS dual-map label derivation → outcome-masking → ASRS pull + register mix → synthetic OIL corpus (~8–10k; stratified by rule; 8-gram Jaccard dedup; reject outcome-leak; LLM-ism detector AUC<0.9) → **Kaggle 2x T4 fine-tune** (masked + unmasked) → baseline table → ONNX + parity gate + artifact mirror. *Smoke-test the Kaggle→local artifact path in the first 4 hours — an unrehearsed artifact path is the classic death.*
**Day 2 (system):** FastAPI inference → ingestion+validation → Postgres+pgvector → dashboard (feed, highlights, density ranking, rule breakdown, override queue, pattern mining) → templated explanations → Ollama layer + phrasebook → input gates. Per-component adversarial swarm review as each lands (Doctrine 2).
**Day 3 (proof):** offline docker + USB tarball → adversarial suite (§B.3) green → metrics slide → **TEAM blind-labels 300–500 gold** (schedule this!) → κ + recall@precision computed → Q&A deck (§B.6) → webapp-testing skill pass (Playwright e2e) → final fresh-eyes swarm validation against PS text + §E → full rehearsal, ethernet unplugged.

Parallelize with subagents: data-pipeline ∥ training-notebook ∥ dashboard are independent streams after the label spec is frozen.

---

# PART E — ACCEPTANCE BAR (definition of done)

- **Accurate:** recall@precision-0.80 reported with CIs on the blind gold; beats regex + TF-IDF baselines significantly (McNemar p<0.05); span exact-match ≥95% on gold.
- **Fast:** <100 ms p95 classification on this machine; bulk ingest ≥500 reports/s classify-only.
- **Tested:** ONNX-vs-PyTorch parity gate; 50-row golden regression; adversarial suite (§B.3) all gated; Playwright e2e of the demo path.
- **Reliable:** 100% offline demo (verified by unplugging); template fallback for every LLM call; gray-card path for low confidence.
- **Production-shaped:** one-command `docker compose up`; schema-validated ingestion with column-mapping config; versioned model artifacts; override → label feedback loop working; README with architecture diagram + honest-claims section.
- **Validated:** every claim in the final deck traces to something you measured yourself, on this machine, in the last 72 hours (Doctrine 1).

**Go. Validate the foundation, swarm every decision, build like the deadline is real — it is.**
