# 20 — Backend Inference Core Audit (classifier + embedder)

Role: inference core audit. Read-only Phase 0; one output file. Live testing done on an
isolated server (port 8211, /tmp copy of demo DB), killed before finishing; the live demo
stack (:8177) was never touched.

## Files read (with line counts)

| File | LoC | Notes |
|---|---|---|
| app/classifier.py | 617 | full |
| app/embedder.py | 163 | full |
| app/config.py | 83 | full |
| app/gates.py | 423 | full |
| app/routes.py | 402 | full |
| app/main.py | 72 | full |
| artifacts/models/masked-v2/metrics.json | 102 | full |
| artifacts/models/masked-v2/{export_gate.json, thresholds.json, manifest.json} | — | full |
| data_pipeline/measure_threshold.py | 288 | full |
| training/train.py | 934 | header (1-60), eval/temp/export (440-560), grep hits |
| runs/run2/day2/ship_eval/tune_op_v2.py | 80 | header + main |
| runs/run2/day2/ship_decision.md, retrain_report.md, DECISION_LOG.md (D19/D27/D29/D31) | — | read sections |
| artifacts/demo/build_demo_pack.py, build_money_beat.py | — | seed-construction sections |
| artifacts/embeddings/corpus_ids.jsonl | 70,398 rows | source distribution computed |

Commands run: `cp artifacts/demo/demo_pre.db /tmp/qa_inf.db`; sqlite3/python inspection of
the copy; isolated uvicorn on 8211 (twice: once accidentally bare → MockClassifier — see F1;
once with `SIF_MODEL_PATH=artifacts/models/masked-v2` → RealOnnxClassifier); urllib latency
scripts; in-process ORT/MiniLM micro-benchmarks. Both servers stopped; port 8211 verified
free; /tmp artifacts removed.

## What exists today

**One /classify call, end to end** (POST /api/classify, routes.py:86-130 →
_predict_with_gates routes.py:66-74 → RealOnnxClassifier.predict = classify_batch([text])
classifier.py:429-432):

1. **Cap** — text truncated to `MAX_INPUT_CHARS = 10_000` (classifier.py:80, applied at
   classifier.py:441). Longer pastes are scored on their prefix; disclosed only by the
   long_input badge (gates.py:371-373).
2. **Tokenize** — `tokenizers.Tokenizer.from_file` (ModernBERT tokenizer.json),
   `add_special_tokens=False` (classifier.py:442). Measured 0.37 ms.
3. **Windowing** `_windows` (classifier.py:499-509) — body budget `SEQ_LEN-2 = 126` tokens
   (CLS/SEP added later); ≤126 tokens → one window; else sliding `start=0, stride=64`,
   each `(i, min(i+126, n))`, plus a tail window `(n-126, n)` if the last slice doesn't
   reach the end. A 10,000-char input = 2,308 BPE tokens = **37 windows** (measured).
4. **Padding** `_pad_rows` (classifier.py:511-523) — each row padded to *its own actual
   max length + 2*, not a fixed 128; compute cost scales with real text length.
5. **Inference** — `onnxruntime.InferenceSession`, CPUExecutionProvider,
   `ORT_ENABLE_ALL`, `intra_op_num_threads=8` (classifier.py:296-300). INT8 is
   dynamically quantized (`quantize_dynamic(QInt8)`, train.py:661). Because int8
   per-tensor dynamic quantization lets batchmates shift logits, `supports_exact_batch=False`
   (classifier.py:313) and **every window runs as its own single-row session.run**
   (classifier.py:452-453, D27). Three heads fetched per run: `sif_logit` (row-scalar),
   `rule_logits` (7 columns in TRAINING order `RULE_HEAD_ORDER`, classifier.py:36-39),
   `span_logits` (per-token).
6. **Temperature calibration** — `sif_probs = sigmoid(sif_logit / T)`, `T = 1.6484` loaded
   from metrics.json (classifier.py:356-371); T was fit by LBFGS on *val* SIF logits at
   train time (train.py:486-503, docstring line 48).
7. **Pooling across windows** — `sif_score = max(sif_probs)` over all windows
   (classifier.py:478-479); `rule_probs = max(sigmoid(rule_logits))` per column
   (classifier.py:480). **Max-pool, not mean.** Comment notes pooling probs after /T is
   equivalent (monotonic).
8. **Rule thresholds** — per-rule F1-optimal values (0.54/0.76/0.95/0.84/0.83/0.82/0.64)
   loaded from metrics.json `rules.{rule}.threshold` and **mutated into the shared
   RULE_DISPLAY table in the constructor** (classifier.py:283-291).
9. **Flag threshold** — `sif_flag_threshold` = metrics.json
   `operating_point_test_tuned.threshold` (raw 0.746401) mapped through T → **0.658108**
   (classifier.py:374-400; loaded value verified 0.6581082996119924 in-process). Stored in
   the artifact, not hardcoded; routes.py:46 `FLAG_THRESHOLD = 0.5` is fallback only.
   Selection (tune_op_v2.py:9-13): **"max recall subject to precision >= 0.80"** on the
   derived-label TEST split, tuned on the int8 single-text ship chain.
10. **Span extraction** `_extract_spans` (classifier.py:525-587) — candidates from *every*
    window: sigmoid(span_logits) > `SPAN_THRESHOLD = 0.5`, per-token char_prob max over
    overlapping offsets, runs merged across ≤3-char non-alpha gaps, scored by mean prob;
    usability filter drops <3-char / no-alpha / all-stopword spans; keyword fallback over
    frozen `_KEYWORD_LFS` regexes scored by the head's char-prob; top 3 after dropping
    spans contained in higher-scored ones; `validate_spans` invariant re-checked.
    Measured: my short wrench probe returned **0 spans** (head silent + no keyword LF hit).
11. **Gates** `run_gates` (gates.py:383-423) — 10 gates in load-bearing order with
    flag_thr = 0.6581; any gate exception degrades to a gray state (gates.py:413-422).
    `near_dup` embeds the text (MiniLM all-MiniLM-L6-v2 ONNX, masked MEAN pool + L2,
    embedder.py:48-90; single embed 24.5 ms) and compares against a **70,398-row base
    index** (entire training+synthetic corpus) at threshold 0.91 (config.py:69, measured
    per data_pipeline/measure_threshold.py).
12. **persist=1** — re-embeds the text (routes.py:114 — the gate already embedded it),
    `text_hash`, single-transaction write (routes.py:110-122). **explain=1** — template +
    optional Ollama rewording, 8 s bound.

**Embedder (app/embedder.py, 163 LoC):** MiniLM ONNX mean-pool + L2 (verified against the
official sbert quickstart sims within 5e-3, embedder.py:37-45, 151-163), truncation 256
word-pieces, 8 intra-op threads, `threading.Lock` around session (embedder.py:67), falls
back to deterministic hashed pseudo-embed if artifact absent (embedder.py:93-106).

## Findings

**F1 — BLOCKER — 71% flag rate is the model doing exactly what it was tuned to do.**
The operating point was selected as **"max recall subject to precision >= 0.80"** on a
test split with **SIF prevalence 0.6423** (tune_op_v2.py:9-15; metrics.json:79-100:
confusion tp 11102 / fp 2775 / fn 287 / tn 3567, **flag_rate 0.7826**). At 64% prevalence
no threshold can compress the queue: the shipped point flags 78.3% of test; even a
precision floor of 0.90 still flags **38.0%** (runs/run2/day2/ship_eval/
operating_point_v2.json, `recall_at_precision_0.90.flag_rate = 0.37956`). The objective
contains no queue-size or cost term at all. Live measurement (my own, n=300 random stored
rows re-scored through the isolated real-model server): **flag rate @0.6581 = 70.67%,
@0.5 = 71.67%** — the stored DB and the live model agree; nothing is "buggily" over-flagging
relative to the tuning distribution. The gap to the claimed ~20%-of-recordables regime
(team's honest claim) is 3.5x and is **not fixable by any threshold choice on this corpus**.

**F2 — BLOCKER — the label prevalence itself is a corpus-construction artifact.**
Corpus source counts (computed from artifacts/embeddings/corpus_ids.jsonl, 70,398 rows):
osha_positive 38,711 (55.0%), asrs_negative 12,035 (17.1%), osha_low_energy_negative
10,632 (15.1%), synthetic_positive 6,019 (8.5%), synthetic_negative 3,001 (4.3%) →
**63.5% SIF-positive by construction**. OSHA is a severe-injury-only reporting system:
every ingested OSHA row is a severe injury, so weak labels mark it positive *by selection*,
not by SIF-potential semantics. The synthetic positives are keyword-anchored
(train.py:14-35 docstring). No part of the label distribution represents the ~20%-of-
recordables regime the tool claims to serve, so *no* operating point tuned on it can hit
that regime; this is upstream of any threshold math.

**F3 — BLOCKER (demo credibility) — the demo DB is made of training/eval corpus rows, which
manufactures both headline numbers.** build_demo_pack.py:8-10, 727-746: bulk_ingest_5k.csv
= 3,000 rows sampled from `artifacts/synthetic/clean/*.jsonl` + 2,000 rows from
`artifacts/corpus/test.jsonl` (masked OSHA — the same test split the operating point was
tuned on) + 50 planted rows; build_money_beat.py:19-21 splits it into the 4,550-row
pre-state. Consequences measured on my /tmp copy of demo_pre.db (4,548 rows):
median stored sif_score **0.9575**; 70.05% ≥ 0.6581; near_dup fired on
**2,713/4,548 (59.7%) = 94.1% of ALL stored gate triggers**; measured top-1 cosine
**0.99998** against index row `syn-ei-a-0121` (the stored texts ARE corpus rows, and the
near-dup base index embeds that same corpus). The near-dup banner is not detecting
near-duplicates of real reports here — it is detecting "this row came from my own
training/demo set", which is tautological on this DB. Contrast probe: one genuinely novel
operational text scored near_dup max cosine **0.622** (silent) and sif_score **0.198**
(LOW, no gates) — on novel text the banner is quiet and the register sensitivity problem
appears instead (see F7).

**F4 — MAJOR — score inflation by max-pooling makes long reports flag-prone and structurally
disables gate #9.** sif_score = max over windows (classifier.py:478-479): with W windows,
P(flag) ≈ 1-(1-p)^W. Measured: a benign ~10k-char procedural narrative (37 windows) scored
**0.7722 → FLAGGED**; /classify p50 **6,806 ms** for it (n=20). Gate `chunked_low_score`
fires only when `chunked ∧ score < 0.40` (gates.py:300-317) — but max-pooling makes a
sub-0.40 max over 37 windows rare by construction, so the gate built to catch CLS positional
dead zones (D29, classifier.py:256-266 comment: measured valleys to 0.03) almost never
fires. This is a designed-in conflict: the mitigation relies on the very statistic the
pooling inflates. Also: 2,000-word reports ≈ 12k chars > the 10k cap → the last ~17% of
words are silently never scored (badge discloses the cap, gates.py:371-373).

**F5 — MAJOR — the shipped int8 artifact failed its own export gate and is decision-unstable
vs fp32.** artifacts/models/masked-v2/export_gate.json: int8 parity agreement **0.99296**
(gate ≥0.995), **AUC drop 0.1305** (gate ≤0.005), `"pass": false`; manifest.json
`"export_gate_pass": false`. ship_decision.md §2 documents that at the *tuned* operating
point int8-vs-fp32 agreement is **0.977 (46/2,000 flips)**, flips swinging p 0.017↔0.975,
and justifies shipping int8 because the op was tuned on the int8 chain itself. That
mitigation makes the *deployed* system self-consistent, but the artifact knowingly violates
the train.py export contract (train.py docstring lines 50-53), and the
`SIF_MODEL_QUANT=fp32` fallback is explicitly NOT decision-equivalent (97.7-98.3%).
The gold-blind human analysis (runs/run2/day2/_gold_analysis_dump.json) adds: on the
synthetic stratum (n=87, gold prevalence 16%) the model's precision is 0.265-0.40 — over-
flagging 2.5-4x on the register closest to OIL-like writing — and on asrs register rows
(tp=0, fp=0, fn=19) the model **never fires at all** (recall 0.0).

**F6 — MAJOR — calibration is a hook, not a validated calibrator.** T=1.6484 is fit on
*val* derived labels by LBFGS (train.py:486-503). metrics.json contains **no ECE, Brier,
or reliability-diagram metric** — nothing validates that the calibrated scale means what
its name says. The val distribution it was fit on (prevalence 0.794, D19) differs from test
(0.642) and from any plausible OIL stream. The threshold→T mapping (classifier.py:393-397)
is arithmetically self-consistent (raw 0.7464 → cal 0.6581, verified), but "temperature
scaling" here only relabels a logit; with test AUC 0.868 (vs saturated val 0.997, D19) the
ranking underneath is mediocre, so calibrated probabilities carry little decision-grade
meaning. The three-way band disagreement (gray [0.40,0.60] config.py:62-63 vs deployed
threshold 0.6581 vs client bandFor 0.7/0.4 — inherited finding #2) compounds it: the
confidence gate fired on only **1.6%** of stored rows while 70.5% of rows score >0.60.

**F7 — MAJOR — bulk ingest is ~11 rows/s, not the ≥30/s the code claims.** POST /ingest of
120 unique rows: wall **10.94 s → 11.0 rows/s** (accepted 120) on this box. routes.py:172-178
still cites "D25 bulk path: inline single-everything measured 5.33/s vs the >=30/s SLA";
after D27 made int8 single-text canonical, batching is disabled (`supports_exact_batch=False`)
and the SLA is void — but the comment still promises it. The demo's 500-row live ingest
extrapolates to ~45-90 s of synchronous blocking. fp32 batch-32 is **not** an escape hatch:
measured 13.4 s for 32 width-128 windows = **2.4 windows/s vs int8 single 5.9 windows/s**
(intra-op threads already parallelize one window; batching adds nothing on CPU here).

**F8 — MINOR — bare `python -m uvicorn app.main:app` silently boots MockClassifier.**
Settings.model_path defaults to `app/artifacts/model.onnx` (config.py:42-45) which does not
exist; `build_classifier` swallows FileNotFoundError/ImportError → mock
(classifier.py:609-617). My first isolated boot ran MockClassifier with no startup error —
only the health endpoint's `classifier` field reveals it. run.sh compensates by globbing
artifacts/models/* (run.sh preflight), but the library itself never fails loudly.

**F9 — MINOR — the threshold's evidentiary chain is not reproducible from this repo.**
metrics.json points at `artifacts/corpus/test.jsonl` and
`runs/run2/day2/ship_eval/single_text_masked_v2_test.jsonl`; the corpus dir **does not
exist** in this checkout (only artifacts/embeddings/corpus_ids.jsonl remains), so the
derived-label split the threshold was tuned on cannot be re-verified from the repo.
train.py is a Kaggle-only script (torch); retraining is out of repo reach by design, which
is fine — but then the shipped artifact should carry its own eval evidence (it partially
does: metrics.json + operating_point_v2.json under runs/).

**F10 — MINOR — constructor mutates a shared table.** `RealOnnxClassifier.__init__` writes
tuned thresholds into the module-global RULE_DISPLAY (classifier.py:283-291); safe only
because one classifier per process (its own comment says so). Latent foot-gun, no live bug.

## Root cause — the 71% flag rate, ranked

1. **Objective, not arithmetic** (F1): "max recall s.t. precision ≥ 0.80" on a 64%-prevalence
   split structurally flags ~69-78%. No bug in threshold loading — the loaded 0.6581 is
   exactly `threshold_calibrated` from metrics.json (verified in-process).
2. **Corpus composition** (F2): 63.5% weak-label positives from a severe-injury-only OSHA
   source + keyword-labeled synthetic rows. The score distribution the tuner saw has almost
   no mass where OIL's claimed regime (~20%) lives.
3. **Demo DB = training distribution** (F3): median score 0.9575 because the rows *are*
   (masked) corpus rows; this is why density tops read sif_rate 1.0 and why near_dup owns
   94% of triggers. Neither number describes model behavior on real data.
4. **Max-pool + int8 artifacts** (F4, F5): window max-pooling adds a multiplicative
   flag-probability term for long inputs; the int8 export failed its parity gate, so the
   deployed scorer is the noisy variant of a mediocre ranker.

Not the cause: the near-dup index does not touch sif_score (gate_near_dup is badge-only,
gates.py:267-276); OSHA's severe-injury-only base rate matters only through the *labels*,
not through any runtime path.

## Latency & memory (all measured this session; isolated server, port 8211)

| Probe | n | p50 | p95 | max |
|---|---|---|---|---|
| /classify short (~60 tok body) | 100 | 236.8 ms | 319.1 ms | 806.5 ms (warm-up) |
| /classify 300 random stored rows | 300 | 244.4 ms | 405.6 ms | 733.2 ms |
| /classify 10k-char input (37 windows) | 20 | 6,806 ms | 7,145 ms | 7,177 ms |
| /classify?persist=1 | 10 | 273.8 ms | 307.7 ms | 345.0 ms |
| POST /ingest 120 rows | 1 | — | — | 10,942 ms (11.0 rows/s) |

Decomposition (in-process, n=60 stored rows): predict p50 165.4 ms (session.run int8
103.3 ms @ width 62, ≈184 ms/window @ width 128); MiniLM embed 24.5 ms; nearest_base matmul
(70,398×384) 15.6 ms; run_gates incl. its own re-embed ≈ 66 ms; HTTP+pydantic ≈ 3 ms.
Inside the session: single `InferenceSession`, CPUExecutionProvider, ORT_ENABLE_ALL,
intra_op=8; **no batching on the deployed path**, no IOBinding, no fixed shapes (padding
follows real length), span head computed on every run even when spans are discarded.
Memory: uvicorn worker RSS **596 MB** (int8 weights 152 MB + MiniLM 90 MB + fp32 index
70,398×384 ≈ 108 MB + ORT arena). Note the int8-vs-fp32 file split: int8 152 MB single file,
fp32 2.95 MB graph + 596 MB external data (manifest.json) — the fp32 fallback needs both.

## Gaps vs production

- No operating point that encodes queue compression or OISD SLA economics; no
  precision/recall target stated anywhere in the runtime artifact.
- No calibration validation (ECE/Brier/reliability) in metrics.json; T fit on a val split
  with a different label prevalence than test or deployment.
- No per-window score dispersion in PredictionOut — max-pool hides inter-window
  disagreement that would directly power the chunked_low_score gate.
- No loud degraded-mode signal: model_version string is the only tell for MockClassifier
  (F8); no hash verification of the artifact at boot beyond run.sh's existence checks.
- Bulk ingest is synchronous with no progress/queue; 11 rows/s vs the 30/s claim (F7).
- Gate trigger-rate telemetry is not aggregated anywhere (only derivable by scanning
  gate_states JSON row by row, as I did).
- No eval-time honesty about the eval: gold analysis exists (n=400 consensus) but sits in
  runs/; the runtime artifact's AUC field (0.9969) is the *val* number while test AUC is
  0.868 — nothing at boot surfaces this.

## Recommendation

- **KEEP** RealOnnxClassifier's single-text canonical path + span-invariant
  (`validate_spans`) + lazy imports/mock parity — the discipline is right and spans the
  exact-substring invariant judges will probe.
- **KEEP** sliding-window chunking + `chunked_low_score` gate, but see ADD #3; the CLS
  positional caveat is honestly documented (classifier.py:256-266).
- **KEEP** the artifact-resident operating point (metrics.json → classifier.py:374-400) —
  correct home; only the *selection objective* is wrong (ADD 1).
- **KEEP** the near-dup MiniLM index and its measured 0.91 threshold — the mechanism is
  sound (verified: novel text cosine 0.622, silent); fix the demo DB composition (REMOVE 2),
  not the threshold.
- **REMOVE** the stale "≥30/s SLA" claim at routes.py:176 — measured 11.0 rows/s on the
  deployed int8 single-text path; a false throughput promise on a demo surface is worse
  than a slow ingest.
- **REMOVE** the silent MockClassifier fallback in build_classifier (classifier.py:609-617) —
  require `SIF_ALLOW_MOCK=1` for mock, mirroring run.sh --allow-mock; bare boots must fail
  loudly (F8).
- **ADD** re-tune the operating point for queue compression: the artifacts already carry the
  curve — P≥0.90 → threshold_cal ≈ 0.995, flag rate 0.38 / recall 0.53 on test
  (operating_point_v2.json); pair it with the severity_watch/negation gates as the safety
  net and re-apply on gold, not derived labels.
- **ADD** calibration metrics (ECE, Brier, reliability bins) into metrics.json at train time
  and a startup log line stating prevalence + flag-rate of the tuned point.
- **ADD** per-window dispersion to PredictionOut (min/max/argmax window) so max-pool
  inflation is visible and `chunked_low_score` can key off window-min instead of pooled max.
- **ADD** `SIF_MODEL_QUANT=fp32` documentation as NOT decision-equivalent (97.7-98.3%
  agreement at tuned op, ship_decision.md §2) — today a quant flip silently changes
  decisions.
- **MERGE** the double embedding in /classify: `gate_near_dup` embeds per row (gates.py:256-261),
  then persist path embeds again (routes.py:114) — pass the vector down once; saves ~25 ms
  and removes a drift seam.
- **MERGE** `ingest` phase-1 classify with per-text window reuse: nothing to reuse today on
  int8 (single-row by design), so simply drop `INGEST_BATCH=32` pretense (routes.py:51) and
  state the real throughput; or prefilter bulk rows by text-hash/index before int8 scoring.
- **NOT WORTH IT**: torch-based serving (banned), vLLM/TensorRT-class stacks (encoder
  classifier, CPU-only, no-torch constraint), fp32 batch-32 (measured slower than int8
  single: 2.4 vs 5.9 windows/s), OpenVINO EP / IOBinding / static-shape padding — plausible
  ~1.2-1.5x but unmeasured here; do not bank on them.

## Verification ledger

Measured by me this session (isolated server :8211 on /tmp/qa_inf.db, real
onnx:masked-v2/sif_multitask_int8.onnx): flag rates 70.67% (@0.6581) / 71.67% (@0.5) on
n=300 stored rows; latency table above; 37-window/6.8 s long-input probe; int8-vs-batchmate
probe (single pair: no shift observed — D27's measured Δ stands on their data, not mine);
in-process threshold load 0.6581082996119924 = metrics.json threshold_calibrated; near-dup
novel-text probe cosine 0.622; DB-copy statistics (4,548 rows, score/gate distributions,
2,713 near_dup, corpus_ids source counts, top-1 cosine 0.99998). Everything else is cited
to files. Failed/incomplete: none of my commands failed; the first server boot ran
MockClassifier (recorded as F8 evidence, then re-run with SIF_MODEL_PATH set). The demo
server :8177 was never contacted; port 8211 released and /tmp copies deleted.