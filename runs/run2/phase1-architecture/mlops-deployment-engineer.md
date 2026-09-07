# Phase 1 — MLOps / Deployment Engineer (PS 26165)

Role: attack the model-artifact path Kaggle → offline demo. All numbers measured on this machine 2026-09-08 unless marked INFERRED. Bench harness: `/tmp/mlops-bench/` (onnxruntime 1.29.0, official `answerdotai/ModernBERT-base` `onnx/model_int8.onnx`, byte-exact 151,074,463 B, QOperator format = what `quantize_dynamic` emits).

## 1. Findings

**C4 dissolved — optimum is unusable for our model (VERIFIED).** optimum-onnx 0.1.0 declares `transformers<4.58.0,>=4.36` — hard-conflicts with transformers 5.16.1. Its TasksManager registers modernbert for exactly 4 standard tasks (feature-extraction, fill-mask, text-classification, token-classification; source: `optimum/exporters/onnx/model_configs.py`) — a custom three-head module has no mapping, and writing a custom OnnxConfig is strictly more work than hand-rolling. **Pipeline:** pin `transformers==4.57.6` (last 4.x) + torch ≤2.6/cu124 (C1 sm_60) → wrap module so `forward` returns `(sif_logits, rule_logits, span_logits)` → `torch.onnx.export(dynamo=False, opset≥17, dynamic batch+seq axes)` → `onnxruntime.quantization.quantize_dynamic(QInt8)` (renamed from `quant_dynamic` in ORT 1.29 — pin ORT). Sanity anchor: diff backbone output vs official ONNX export on fixed inputs.

**Latency measured, CPU clamped 0.60–0.86 GHz during the whole bench (C3 live):**
- bs=1 seq128, 8 threads: p50=217 ms, p95=244 ms. Default 16 threads is WORSE (p50=347, p95=476) — HT contention; pin `intra_op_num_threads=8`.
- Throughput: bs=8 → 5.2 reports/s; bs=32 → 3.5 reports/s (compute-bound ~120 GFLOP/s achieved).
- Unthrottled INFERRED (÷6.5 clock ratio, corroborated by Ollama 146.8→21.4 tok/s history): bs=1 p95 ≈ 35–75 ms → **<100 ms p95 feasible, margin thin**; bulk ≈ 30–40 reports/s.
- Arithmetic verdict on §E "≥500 reports/s classify-only": needs ~19 TFLOP/s (38 GFLOP/report × 500); this CPU sustains ~0.8–1.2 TFLOP/s int8. **Infeasible by ~15×, throttle-independent.** Even DistilBERT misses by ~6×.

**Parity gate: `|Δlogit| < 1e-3` is wrong for int8 (INFERRED from quantization fundamentals).** int8 logit deviation is typically 1e-2–1e-1 — a 1e-3 gate fails every healthy export or gets waived (gate theater). Two-tier:
- **Gate A, export parity (fp32 ONNX vs PyTorch):** max |Δlogit| ≤ 1e-4, max |Δp| ≤ 1e-5 over the eval slice. Deterministic conversion; 1e-3 was already loose.
- **Gate B, quantization parity (int8 vs fp32 ONNX), decision-level:** SIF AUC drop ≤ 0.005; recall@precision-0.80 drop ≤ 0.01; label agreement ≥ 99.5%; mean |Δp| ≤ 0.01, max |Δp| ≤ 0.05; per-rule AP drop ≤ 0.01; span token-F1 drop ≤ 0.01. The product consumes probabilities and decisions — gate those.

**Docker (VERIFIED):** daemon inactive, no compose, no podman, no system postgres — BUT `sudo -n true` works (user in wheel). C2's "human task" is three commands (`systemctl enable --now docker`, `usermod -aG docker`, compose plugin). Don't build on it anyway.

**Near-dup index (VERIFIED):** numpy brute force, 105,996 × 384-dim fp32, *throttled*: query p50=20.4 ms (budget 200 ms), bulk 5.9 ms/report, 163 MB RAM (41 MB as uint8-quantized). Exact cosine — no ANN recall fudge to defend in Q&A.

## 2. Risks

- **SEV1 — §E bulk SLA ≥500 reports/s is arithmetically impossible** here (15× miss unthrottled). Acceptance bar cannot pass as written. Fix: ≥30 reports/s sustained + precomputed demo ingest, or a distilled ~30M student (~150/s).
- **SEV2 — <100 ms p95 breaks under the 0.85 GHz clamp** (measured 244 ms). Contingency: fix power profile pre-demo (sudo available), precompute demo corpus, seq-bucketing (median narrative ~50 tokens) buys ~2×, 8-thread pin mandatory.
- **SEV2 — 1e-3 int8 parity gate = gate theater** (see above).
- **SEV3 — transformers v5 / optimum-onnx 0.1.0 / ORT API churn** — all neutralized by pinning (4.57.6 / no optimum / ORT 1.29).
- **SEV3 — docker-down packaging** — plan B below is simpler than plan A.

## 3. Recommendations (per architecture element)

- `optimum[onnxruntime]` in export path: **REJECT.** Hand-rolled `torch.onnx.export` + `quantize_dynamic`; pin transformers 4.57.6.
- Parity gate `|Δlogit|<1e-3`: **MODIFY** to two-tier Gate A/B above.
- `<100 ms p95` classify: **ADOPT** with 8-thread pin + seq-bucketing; verify unthrottled pre-demo; precompute as seatbelt.
- `≥500 reports/s` bulk: **MODIFY** to ≥30/s (measured headroom); demo bulk-ingest precomputed.
- Postgres 16 + pgvector: **REJECT for ship.** numpy memmap index (measured) + stdlib SQLite metadata. Zero services, exact search.
- Packaging (single compose + `docker save`): **MODIFY** — invert: bare-metal `run.sh` (uv venv + uvicorn + built React static + SQLite + precomputed artifacts) is THE one command and the USB tarball; compose becomes an optional wrapper if docker gets fixed (sudo: 5-min job).
- Artifact versioning: **ADOPT + specify:** `artifacts/v{N}/` = model_int8.onnx + tokenizer + metrics.json + parity_report.json + label_spec.sha256 + sha256 manifest; mirrored to private Kaggle Dataset after every run (byte-verified path), local, USB Day 3; version echoed in every API response.

## 4. Verdict

Architecture's MLOps spine is sound in direction, wrong in three load-bearing specifics (optimum, parity threshold, bulk SLA). With the modifications above the artifact path is robust and mostly verified by measurement today. GO.

<<SCORES {"ps":"26165","role":"mlops-deployment-engineer","go_no_go":6,"severity":1,"feasibility":8,"data_risk":1}>>
