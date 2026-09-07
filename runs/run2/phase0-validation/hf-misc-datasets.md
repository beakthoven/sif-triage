# Phase 0 Validation — HF Misc Datasets (Cluster: SmartQHSE + electricsheepafrica)

Validator: independent re-probe on this machine, 2026-09-08. All numbers below were measured with curl/python against huggingface.co API + raw file download; nothing taken from HANDOFF.md.

## Findings table

| # | Dataset | Exists | Gated/Private | License (measured) | Rows (measured) | Files | Verdict |
|---|---------|--------|---------------|--------------------|-----------------|-------|---------|
| 1 | SmartQHSE/major-process-safety-incidents-2026 | YES (HTTP 200) | gated:false, private:false | **cc-by-4.0** (README YAML + cardData + tag) | **15** | .gitattributes, README.md, croissant.json, data.csv (2,261 B), data.json, data.jsonl | VERIFIED |
| 2 | SmartQHSE/named-process-safety-incidents-extended-2026 | YES | gated:false | **cc-by-4.0** (cardData/tag; LICENSE file present) | **44** (card text says "40") | README.md, LICENSE, data.csv (6,020 B) | VERIFIED w/ CORRECTION |
| 3 | electricsheepafrica/africa-synth-energy-oilgas-safety-incidents-nigeria | YES | gated:false | card says **"other"**; README body says **MIT** | **3,000** | README.md, nigerian_oilgas_safety_incidents.csv (127,387 B) | FAILED (on "text/style reference") |

## Claim-by-claim detail

**Claim 1 — "major-process-safety-incidents-2026: 15–40 famous disaster vignettes, CC-BY-4.0" → VERIFIED.**
15 records measured (wc -l data.csv = 16 incl. header; data.jsonl = 15 JSON records) — low end of claimed range. "Vignettes" is fair **only for data.jsonl**: 17 fields incl. direct_cause, root_causes (list), key_lessons (list), regulatory_response, material_released, injuries, primary_source_url. The CSV is a terse 8-col subset (id,name,date,country,operator,industry,fatalities,api_rp_754_tier). Caveat: HF datasets-server `/info` returns **failed config** for this repo (auto-conversion broken) — HF viewer preview unavailable; direct raw download works fine. Created 2026-05-03, lastModified 2026-05-29, 104 downloads.

**Claim 2 — named-process-safety-incidents-extended-2026 exists → VERIFIED; row count CORRECTED.**
44 rows measured (datasets-server num_examples=44 and local csv.DictReader=44); README says "40 named". Schema: name, year, country, industry, fatalities, immediate_cause, root_cause_summary, regulatory_consequence — all short one-line strings (e.g. Halifax 1917, root cause "Loading and routing controls inadequate"). Terse lookup table, not narrative vignettes. Spans 1917–2024 per card.

**Claim 3 — "africa-synth-…-nigeria: synthetic oil-gas safety incident TEXT, style reference (for OIL-register text)" → FAILED.**
Dataset exists and is synthetic oil-gas safety data, but measured schema is 5 categorical columns: incident_id, date, operator, type, severity. **Zero prose/text fields.** type ∈ {fatality 773, explosion 772, fire 734, injury 721}; severity ∈ {low 1037, high 1001, medium 962} — near-uniform random labels; sample row has a "fatality" with severity "low", confirming random assignment. There is no incident register text to imitate — unusable as a "style reference". License is NOT CC-BY-4.0: card license="other", README states MIT. README self-warns: "⚠️ Synthetic dataset — not suitable for empirical analysis or policy inference."

## SmartQHSE org — other relevant datasets (measured: 34 total in org)

Worth knowing for a PSM/SIF demo knowledge layer: `hse-qa-corpus` (62 dl) + `hse-qa-corpus-v2-2026`, `hse-incident-investigation-methods-2026`, `hazop-guidewords-reference-2026`, `risk-matrix-reference-2026`, `iogp-life-saving-rules-2018`, `hse-glossary`, `hse-acronym-dictionary-2026`, `hse-standards-crosswalk`, `hse-kpi-catalog-2026`, `hse-incident-rate-formulas`, `osha-rates-2026`, `osha-regulated-chemicals-pel-2026`, `iso-45001-2018-clause-reference-2026`. (Existence/download counts measured via `api/datasets?author=SmartQHSE`; licenses not individually re-verified — INFERRED CC-BY family from the two checked.)

## Commands used (verbatim)

```
curl huggingface.co/api/datasets/{repo}                      # exists/gated/license/siblings
curl huggingface.co/api/datasets?author=SmartQHSE&limit=100  # org inventory (34 repos)
curl datasets-server.huggingface.co/info?dataset={repo}      # schema + num_examples
curl -L .../resolve/main/data.csv | wc -l; python3 csv.DictReader  # row counts, samples
curl -L .../resolve/main/README.md | grep -i licen           # license text (nigeria: MIT)
```

## Impact on build

Datasets 1–2 are solid, free, ungated CC-BY-4.0 demo/reference vignette sources — usable as-is (fetch raw files, not the HF datasets-server, for #1). Dataset 3 cannot serve its HANDOFF-stated purpose (style reference); if synthetic OIL-register prose is needed, it must be generated elsewhere (e.g. templated from dataset 1's JSONL fields). None of these are load-bearing for the core SIF-precursor engine.
