# Phase 0 Validation — NASA ASRS HF Dataset (`elihoole/asrs-aviation-reports`)

Date: 2026-09-08. All findings measured live on this machine via HF Hub API + curl. Nothing INFERRED unless marked.

## Verdicts

| # | Claim | Verdict | Measured evidence |
|---|-------|---------|-------------------|
| 1 | Dataset exists at `elihoole/asrs-aviation-reports` | VERIFIED | `GET /api/datasets/...` → HTTP 200, sha `f1e681e9`, private=false, downloads=493 |
| 2 | 47,723 near-miss narratives | VERIFIED | datasets-server `/size` → `num_rows: 47723` exactly (train 38,655 / val 4,295 / test 4,773) |
| 3 | Apache-2.0 license | VERIFIED | tag `license:apache-2.0`; cardData `license: [apache-2.0]` |
| 4 | NOT gated | VERIFIED | `gated: false`; unauthenticated HEAD + range-GET on resolve URL both succeeded (only warning: lower rate limits without HF_TOKEN) |
| 5 | train/val/test JSONL ~270/30/33 MB | VERIFIED | `/tree/main` exact bytes: train 270,248,264 (≈270 MB), val 29,941,842 (≈30 MB), test 33,260,860 (≈33 MB). Total 333,450,966 B |
| 6 | Direct download works (302→CDN) | VERIFIED | HEAD on resolve URL → HTTP 302 → `https://us.aws.cdn.hf.co/xet-bridge-us/...` (signed CloudFront-style URL, `x-linked-size: 29941842` matches tree) |

No FAILED claims. Row count and all three file sizes match the handoff exactly.

## File list (GET /api/datasets/elihoole/asrs-aviation-reports/tree/main)

| file | bytes |
|------|-------|
| .gitattributes | 1,610 |
| README.md | 5,792 |
| asrs-aviation-reports-train.jsonl | 270,248,264 |
| asrs-aviation-reports-validation.jsonl | 29,941,842 |
| asrs-aviation-reports-test.jsonl | 33,260,860 |

Also has auto-converted Parquet (63 MB total) via datasets-server — usable with `datasets` lib or `/rows` endpoint without downloading JSONL.

## Record schema (streamed first 2 MB of validation shard; 286 complete records parsed)

- 111 fields per record, all string-typed (empty string for missing).
- ID: `acn_num_ACN` (e.g. "1677948"); also `Person 1.10_ASRS Report Number.Accession Number`.
- Narrative text fields: **`Report 1_Narrative`** (primary, populated in sample), `Report 2_Narrative`, `Report 1.1_Callback`, `Report 2.1_Callback`, `Report 1.2_Synopsis`.
- Weak-label candidates (no explicit target column): `Events_Anomaly` (e.g. "ATC Issue All Types; Conflict Airborne Conflict; Deviation / Discrepancy - Proce..."), `Assessments_Contributing Factors / Situations`, `Assessments.1_Primary Problem`, `Person 1.7_Human Factors`, `Events.5_Result`.
- Structured context: Time/Place/Environment, `Aircraft 1.*` (35 fields), `Aircraft 2.*`, `Person 1/2.*`, `Component.*`, `Events.*`, `Assessments.*`. Many UAS-specific fields are empty in crewed-aviation reports.
- Note: dataset is tagged `task_categories:summarization` (narrative→synopsis), NOT classification — using it for SIF-precursor detection requires deriving labels from the Events/Assessments fields.

## Commands used

1. `curl -sS https://huggingface.co/api/datasets/elihoole/asrs-aviation-reports`
2. `curl -sS https://huggingface.co/api/datasets/elihoole/asrs-aviation-reports/tree/main`
3. `curl -sS "https://datasets-server.huggingface.co/size?dataset=elihoole%2Fasrs-aviation-reports"`
4. `curl -sSI https://huggingface.co/datasets/elihoole/asrs-aviation-reports/resolve/main/asrs-aviation-reports-validation.jsonl` (302 chain)
5. `curl -sSL -r 0-2000000 <resolve-url-validation>` → parsed first record (111 keys) with python3 json

## Relevance to PS 26165

Dataset is alive, ungated, exactly the size/rows claimed, and downloadable anonymously today. Caveat (INFERRED): narratives are aviation near-misses, not oil & gas — usable only as a transfer/domain-analogy corpus for the SIF-precursor engine, not as primary training data for Oil India's incident taxonomy.
