# Phase 0 Validation — Prior Run Artifacts + PS Dataset (Validator: phase0-validator, cluster 2)

Date: 2026-09-08. Machine: this host, Python 3.14.6. All numbers measured by me today; nothing taken from HANDOFF.md.

## Findings

| # | Claim | Measured | Verdict |
|---|-------|----------|---------|
| 1 | `data/sih2026_ps.csv` has 226 PS | `csv.DictReader` → exactly **226** records (172 Software, 54 Hardware). Raw `wc -l`=3307 due to embedded newlines — CSV parse is the correct count. | VERIFIED |
| 2 | `data/software_ps.json` has 172 software PS | JSON list, `len=172`, zero duplicate `id`s, keys: id/title/theme/org/dept/ideas/desc/dataset | VERIFIED |
| 3 | PS 26165 exists with EMPTY dataset-link | Exactly 1 row in CSV (`problem statement id`='26165', `ps number`='SIH26165'); `dataset link` = `''`. Also present in software_ps.json (`id`='26165', `dataset`=`''`). | VERIFIED |
| 4 | `runs/run1/all_blocks.json` parses, ~155 verdict blocks | `json.load` OK; list of exactly **155** dicts, keys: ps/role/feasibility/data_risk/demo_wow/uniqueness/punch/win_prob/phase | VERIFIED |
| 5 | `aggregate_scores.py runs/run1/phase1_all.txt` produces table+json | Ran on a /tmp copy (script writes `<input>.aggregated.json` beside input; running literally on run1 would overwrite the existing artifact — see Caveat 1). Exit 0; parsed 48 blocks / 24 PS; printed ranked table; wrote JSON. Regenerated JSON **byte-identical** to `runs/run1/phase1_all.aggregated.json`. | VERIFIED |
| 6 | 26165 appears as top scorer in phase3/phase4 | phase3 aggregated: **26165 rank 1/8, composite 29.71 (n=7)**; 24 grep hits in phase3_all.txt. phase4_all.txt: 10 hits incl. literal line "Final result: PS 26165 (OIL SIF-precursor NLP) wins". | VERIFIED |
| 7 | prefilter.py + build_items.py reusable, no bit-rot | Both stdlib-only (csv/json/re/sys/os). prefilter re-run on live CSV → survivors=109, excluded=63, outputs **byte-identical** to run1 phase0_ranked/excluded.json. build_items.py phase1 regenerated 48 items = run1 phase1_items.json count. | VERIFIED |

## PS 26165 quoted fields (verbatim from sih2026_ps.csv)

- **problem statement title:** "AI/NLP Engine to Detect Serious Injury & Fatality (SIF) Precursors in OIL's Unsafe-Act/Unsafe-Condition and Near-Miss Reports"
- **organization / department:** Oil India Limited / Oil India Limited | **theme:** Miscellaneous | **ideas:** 0/500 | **deadline:** 20 September 2026
- **description (abridged to key sentences; full text is 3 paragraphs):** "OIL collects large volumes of UA/UC observations, near-miss and incident reports through its HSSE platform but these are triaged manually… Global best practice (DEKRA Martin & Black 2015; EEI SIF Precursor model; VelocityEHS 2024 PSIF classifier) has established that low-severity incidents do not share the same causes as fatalities… Build a prototype that ingests OIL's free-text safety reports and automatically a) Classifies each as SIF-potential vs non-SIF-potential b) Tags it to the relevant IOGP Life-Saving Rule (e.g., Energy Isolation, Hot Work, Confined Space, Line of Fire) c) Surfaces recurring precursor patterns (activity, location, barrier failure) via a dashboard. Expected Outcome: A working AI/NLP with an interactive dashboard that ranks sites/activities by SIF-precursor density… Relevant Data Availability: OIL's UA/UC observations, near-miss and incident reports."

## Caveats / notes

1. **aggregate_scores.py side effect:** always writes `<input-basename>.aggregated.json` next to the input; on run1 inputs it silently overwrites prior artifacts. Re-run validators must copy inputs to scratch first (as done here).
2. **Mojibake in source CSV:** 26165's description contains `â€"` sequences (double-encoded em-dash/en-dash, e.g. "20â€"25%"). Cosmetic; does not affect counts, but any UI quoting the raw CSV should fix encoding.
3. **26165 was NOT top early:** phase1 rank 18/24 (comp 22.5), phase2 rank 9/10 (comp 5.5) — it only won in phase3 appeals. Claim 6 as stated ("top in phase3/phase4") is accurate, but anyone reading run1 should know the trajectory was bottom→top.
4. prefilter.py regexes are SIH-2026-specific (column names, exclusion patterns) — reusable as-is only for same-schema CSVs; fine for this project.

## Commands used

- `python3 -c csv.DictReader…` on data/sih2026_ps.csv (counts, 26165 row dump)
- `python3 -c json.load…` on data/software_ps.json, runs/run1/all_blocks.json (len, keys, dup check)
- `cp phase1_all.txt /tmp && python3 pipeline/aggregate_scores.py /tmp/...` (exit 0, table+json)
- JSON equality: regenerated /tmp aggregated vs runs/run1/phase1_all.aggregated.json → identical
- `python3 pipeline/prefilter.py data/sih2026_ps.csv /tmp/pf_out` → byte-identical to run1 phase0 outputs
- `python3 pipeline/build_items.py phase1 runs/run1/phase0_shortlist.json /tmp/items_test.json` → 48 items
- `grep -c 26165 runs/run1/phase3_all.txt phase4_all.txt` → 24 / 10; rank extraction from all three aggregated JSONs
