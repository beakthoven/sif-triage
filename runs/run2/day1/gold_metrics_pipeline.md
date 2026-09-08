# Gold metrics pipeline — one-command final gold eval

Built Day-1 evening (2026-09-08) for Wednesday's eval. Script: `gold/compute_gold_metrics.py`.
Status: **self-check PASS** (Wilson units + full end-to-end on simulated labels in a temp dir);
score cache pre-warmed for all 500 gold items; repo left in the clean pre-labeling state
(no `artifacts/gold/labels/`, no merged/export files).

## Usage

```bash
# Wednesday, after labeling (and any adjudication):
.venv/bin/python gold/compute_gold_metrics.py

# Anytime — full validation, touches nothing real:
.venv/bin/python gold/compute_gold_metrics.py --self-check
```

The script auto-runs `gold/export_labels.py` first if `labels_merged.jsonl` is missing but
`artifacts/gold/labels/` has labeler files, so the single command above is the whole flow.
Exit codes: `0` = metrics written; `2` = score cache written but no labels found yet
(pre-labeling state — tonight's warm run exits 2 by design); `1` = self-check failure.

## Inputs

| input | path | notes |
|---|---|---|
| gold items | `artifacts/gold/gold_items.jsonl` | 500 items, frozen sample |
| merged labels | `artifacts/gold/labels_merged.jsonl` | from `export_labels.py` (auto-run if missing) |
| model | `artifacts/models/masked-v1/` | int8 ONNX + `metrics.json` |

## What it does (protocol mapping)

1. **Scores all 500 gold items** with the ship config: `onnx_score.Scorer`, **single-text
   per-row int8, batch=1** — the D27 canonical path (batch int8 shifts logits with batch
   composition, D25, so batch=1 is the only legal scoring path and the one the threshold
   was tuned on). Cache → `artifacts/gold/model_scores.jsonl`, keyed by a model
   fingerprint (onnx sha + threshold + scoring path). **Idempotent**: a full-fingerprint
   cache hit skips the model entirely; `--rescore` forces.
2. **Applies the FROZEN threshold ONCE**: `p_raw >= 0.821855` from
   `metrics.json operating_point_test_tuned` (D27 single-text-tuned). The val-frozen
   `thresholds.json` point (6.58e-5) is vacuous at natural prevalence (D19) and is
   deliberately never read. No re-tuning on gold.
3. **Per-stratum metrics**: `osha_2024_25`, `asrs`, `synthetic` separately + **real-only
   pooled headline** (synthetic never pooled, spec `gold.reporting`). Recall, precision,
   F1, confusion, flag rate; **Wilson 95% CIs** (z=1.96; recall CI over positives,
   precision CI over flagged). Flags: `PRECISION_FLOOR_FAIL` (SEV1) if real-pooled
   precision < 0.80 — the operating-point claim fails; `RECALL_CI_TOO_WIDE` (SEV2) if
   recall CI width > 0.12; `INCOMPLETE_LABELING`, `ADJUDICATION_PENDING`,
   `AGREEMENT_MISMATCH` as applicable.
4. **Rules**: per-rule P/R/F1 on the real pooled stratum (model rule probs vs frozen
   `rule_thresholds`; human rule tags = union over raters). **Macro-F1 over rules with
   ≥50 gold positives**; smaller rules merged into `Other` with disclosure
   (spec `cs_ei_support_weakness`).
5. **Agreement**: Fleiss' κ human-vs-human only, functions imported from
   `export_labels.py` (double-labeled subset + n=4 pilot subset, bootstrap SE), and
   cross-checked against `agreement.json` when present (κ near-exact; bootstrap SE within
   MC tolerance). **Adjudication queue** → `artifacts/gold/adjudication_queue.jsonl`:
   every item without a unanimous `sif`/`non_sif` label (disagreement or any `unsure`),
   **blind** — no stratum, no model output, so the 3rd labeler stays clean.
6. **Money-slide outputs**: `artifacts/gold/gold_metrics.json` (full machine-readable
   result incl. provenance) + `artifacts/gold/gold_metrics.md` (every figure with CI and n).

Gold truth = **unanimous label** across an item's raters; consensus rule tags = union.
Adjudicated items are excluded until rulings land — after adjudication, merge rulings into
the label files and re-run; the score cache makes re-runs seconds.

## Expected outputs

| file | content |
|---|---|
| `artifacts/gold/model_scores.jsonl` | 500 rows: `gold_id, sif_logit, p_raw, p_cal, rule_probs, fingerprint, scored_at` |
| `artifacts/gold/adjudication_queue.jsonl` | blind worklist for the 3rd labeler |
| `artifacts/gold/gold_metrics.json` | strata metrics + CIs + flags + rules + κ + provenance |
| `artifacts/gold/gold_metrics.md` | headline table, per-stratum table, flags, rules macro-F1, κ, adjudication, provenance |

The markdown's **real pooled (headline)** row is the money slide:
recall/precision/F1 at the frozen threshold, each with Wilson 95% CI and n.

## Self-check (what `--self-check` proves)

- Wilson implementation reproduces the corrected eval table (eval-metrics-engineer.md §1a):
  0.85@60 → [0.739, 0.919]; 0.85@100 → [0.767, 0.907]; n=0 → Nones.
- Constructed confusion case: TP/FP/FN/TN, P/R/F1 exact; CI denominators correct.
- End-to-end in a temp dir: simulated labels for all 500 items (4 raters on the 20 pilots,
  2 on the 150 doubles, 1 otherwise, via `simulate_labeling.sim_label`) → auto-export →
  metrics → asserts: 500 scored; consensus+adjudication+unlabeled == 500; non-empty blind
  adjudication queue; synthetic separate from real pooled; κ matches `export_labels.py`;
  `in_macro == (n_pos >= 50)` for every rule; markdown sections present; **second run is a
  pure cache hit with byte-identical cache**; **`artifacts/gold/` untouched**.
- Tonight's run: all checks PASS. `artifacts/gold/` contains only `gold_items.jsonl`,
  `sample_manifest.json`, and the pre-warmed `model_scores.jsonl` — the pre-labeling state
  is otherwise clean.

## Notes / boundaries

- Requires `.venv` (onnxruntime/tokenizers/numpy); the rest of the gold toolchain stays
  stdlib-only. Scoring defaults to `--threads 4` to leave headroom for the demo server
  on :8177.
- Baselines (regex/TF-IDF/zero-shot LLM) and Holm-corrected McNemar are **not** in this
  script — they need baseline scores on the same gold items; wire them in when those
  score files exist (compare against `model_scores.jsonl`).
- ECE/calibration on gold is deliberately absent (binning noise at gold n; see
  eval-metrics-engineer.md SEV3-1).
- Simulated-label runs in the self-check produce nonsense metrics by construction (heuristic
  labels vs real model) — that run validates plumbing, not model quality.
