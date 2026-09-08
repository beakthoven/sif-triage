# Day-1 Report — Gold Set Sampler + Blind Labeling Tool (PS 26165)

Date: 2026-09-08 · Owner: gold tooling · Status: **built, self-checked, sampled**
Spec basis: `spec/label_spec.yaml` `gold:` + `contamination:` (FROZEN v1.0.0), `runs/run2/DECISION_LOG.md` D7/D8/D11.

## What was built

| Path | Purpose |
|---|---|
| `gold/gold_common.py` | Shared constants (7 rules, labeler ids, seed 42); parity-asserted against `oiics_maps` at sample time. |
| `gold/sample_gold.py` | Deterministic sampler (seed 42). Emits `artifacts/gold/gold_items.jsonl` + `artifacts/gold/sample_manifest.json`. `--synthetic-file` fills the reserved synthetic slots later. |
| `gold/labeler_app.py` | Blind labeling web app, **pure stdlib** (`http.server`), one instance per labeler. |
| `gold/export_labels.py` | Admin merge → `labels_merged.jsonl` + `agreement.json`; Fleiss' κ from scratch with bootstrap SE; `--self-test` with hand-computed examples. |
| `gold/RUBRIC.md` | One-page human labeling guide (7 rules, triage question, edge cases, blind protocol). |
| `artifacts/gold/gold_items.jsonl` | **400 rows emitted** (300 OSHA + 100 ASRS; 100 synthetic reserved). |
| `artifacts/gold/sample_manifest.json` | Full audit trail: counts, prevalences, seeds, input SHA-256s, balances, pilot ids. |

## Composition achieved (vs frozen spec)

| Stratum | Spec | Achieved | Notes |
|---|---|---|---|
| OSHA 2024–25 | 300 | **300** | From `artifacts/corpus/test.jsonl` (17,731-row temporal held-out pool). |
| — of which oil-gas NAICS 211/213 | up to 150 | **150** | **364 available** in the pool (2.05%; 290/364 SIF-positive) — cap of 150 was binding, not availability. |
| ASRS | 100 | **100** | Same prescreen as `build_corpus.py` (drop high-energy `Events_Anomaly`, ≥20 words, exact-dedup) **plus leakage guard**: 12,035 ACNs already in corpus `train.jsonl` excluded → pool 6,022 → sample 100. Verified 0 gold ASRS texts appear in train. |
| Synthetic | 100 | **RESERVED** (G0401–G0500) | QA pending. `python3 gold/sample_gold.py --synthetic-file <qa-passed.jsonl>` fills exactly these ids; pilot and OSHA/ASRS double-flags verified stable across that re-run. |

**SIF-positive prevalence (B_middle proxy, for CI width):** natural test-pool 0.6423 → achieved **0.7500** on the OSHA stratum via the oil-gas oversample alone (115/150 oil-gas sampled are proxy-positive). **Enrichment ratio 1.1677**, 0 positive-swaps needed (target ≥0.40 far exceeded; swap logic implemented but untriggered). At 0.75 proxy prevalence the 300-OSHA stratum carries ~225 proxy positives — comfortable recall-CI headroom on the real strata.

## Double-label + pilot design (D7: 500 single + 150 double)

- **150 double-labeled**, seed-stratified 90 OSHA / 30 ASRS / 30 synthetic. 120 flagged in the current 400-row emission; the 30 synthetic double-flags are pre-assigned by id and materialize when the stratum fills.
- **20-item calibration pilot**, identical for all 4 labelers, drawn from double-flagged OSHA (15) + ASRS (5), stable across synthetic fill (verified by re-run comparison). Served first by the app, marked `[calibration pilot]`.
- Assignments: primary exactly **100/labeler** (125 at 500), secondary 29–31/labeler (37–38 at 500) — within the ±2 balance requirement. Secondary never equals primary (asserted).
- Judgment budget: **560** now (~140/labeler ≈ 1.75 h at 45 s), ~690 at full design — inside D7's 6–8 person-hours.
- Fleiss' κ subset sizes at full design: 130 items with n=2 raters + 20 pilot items with n=4 raters.

## Blind protocol guarantees (the anti-circularity claims)

1. `gold_items.jsonl` contains **only** `gold_id, source_stratum, masked_text, event_title, is_pilot, assignment` — verified zero derived-label/provenance fields (`sif_label`, `naics`, `oiics`, `employer`, `rules`, …). Derived labels were used only for stratification stats in the manifest.
2. The app payload per item is `{gold_id, masked_text, event_title, is_pilot}` — nothing else exists server-side per item to leak.
3. **Outcome-stem-free display**: both `masked_text` and `event_title` pass `mask_count == 0` (6 OIICS titles like "Injured by object wielded…" are now masked — caught and fixed by the self-check).
4. Per-labeler queue order shuffled with per-labeler seeds; pilot block first.
5. Labels autosave **append-only**, timestamped, to `artifacts/gold/labels/<labeler>.jsonl`; the app has **no endpoint that reads any label file** (404 verified) — labelers cannot see each other's labels or their own history.
6. Server-side validation: rejects gold_ids outside the labeler's queue and unknown labels/rules (400 verified).
7. OSHA gold ⊆ boundary-screened temporal test set; ASRS gold ∩ train = ∅ (both machine-verified).

## Self-checks run (all PASS)

- Sampler: composition counts; no duplicate gold_ids; double overlap = 120 emitted + 30 reserved = 150 design; primary balance exact, secondary within ±1; pilot = 20, all double-flagged; no leaked fields; no unmasked outcome stems; RULES/`ASRS_DROP_PREFIXES` parity with `oiics_maps`/`build_corpus`; achieved prevalence ≥ 0.40.
- Kappa (`--self-test`): hand-computed 3-rater example κ = 1/3 ✓; perfect agreement κ = 1 ✓; mixed case κ = 0.6 ✓; chance-level κ = 0 ✓.
- App smoke test: serves item, keyboard flow, autosave append, invalid-id rejection, resume-after-restart (skips labeled), per-labeler queues differ.
- Export dry run on fabricated labels: grouped κ by rater count (n=2 doubles κ=0.0±0.53 at 50% raw agreement — hand-verified; n=4 pilot κ=0.238), merge output correct.
- Synthetic-fill dry run: 500 rows, exactly 150 doubles stratified 90/30/30, pilot + existing flags unchanged.

## How the human team runs this (Day 2 evening, per D7)

```bash
# 4 terminals (or 4 machines on LAN is NOT supported — localhost only, by design):
python3 gold/labeler_app.py --labeler a --port 8001
python3 gold/labeler_app.py --labeler b --port 8002
python3 gold/labeler_app.py --labeler c --port 8003
python3 gold/labeler_app.py --labeler d --port 8004
# Each labeler opens http://127.0.0.1:<their port>/ and reads gold/RUBRIC.md first.
# Keys: S / N / U, Enter to save a SIF label. Ctrl-C anytime; re-run resumes.

# After all four finish (and after synthetic QA fills slots + re-label):
python3 gold/export_labels.py            # merge + Fleiss' κ + bootstrap SE
python3 gold/export_labels.py --self-test
```

## Known limitations / notes

- Emitted double-labeled count is **120** until the synthetic stratum fills (30 flags pre-assigned by id; design total 150). If synthetic QA fails entirely, κ still has the 120-item real subset.
- κ is computed per rater-count group (n=2 doubles, n=4 pilot) because classic Fleiss requires fixed raters/item; generalized varying-n κ deliberately not implemented (stdlib, verifiable > clever).
- `is_pilot` is visible to labelers (`[calibration pilot]` marker) — intentional: the calibration round is a known protocol phase, not provenance.
- ASRS narratives inherently read as aviation register; blindness covers stratum/provenance *metadata*, not text content (accepted in D8).
- Append-only means no re-labeling through the app; corrections are admin-side edits before export (export keeps the latest record per labeler/item).
