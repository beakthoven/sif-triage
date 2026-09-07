# Phase-0 Validation: OSHA CSV (data/January2015toNovember2025.csv)

Validator: phase0-validator / cluster "OSHA CSV structure + content stats". Date: 2026-09-08.
Method: pandas 2.3.3 (preinstalled), read_csv dtype=str, EventDate parsed %m/%d/%Y. All numbers below MEASURED on this machine. File present, 57,403,269 bytes.

## Findings

| # | Claim | Measured | Verdict |
|---|-------|----------|---------|
| 1 | 105,996 rows, 28 cols, exact names | 105,996 rows, 28 cols, all 28 names match verbatim | VERIFIED |
| 2 | Final Narrative 0% missing, med 182 chars/31 words, p95=371, max=2134 | missing 0.0%; median 182; words-median 31; p95 371; max 2134 | VERIFIED |
| 3 | Hospitalized/Amputation are counts (0-6), binarize >0 | counts not flags confirmed. Hospitalized max=6, nonzero 85,841. Amputation max=2 (not 6), nonzero 27,961, 7 NaN | PARTIAL (Amputation range 0-2) |
| 4 | Loss of Eye = 35 rows | nonzero=35, max=1, 5 NaN | VERIFIED |
| 5 | 66 exact-duplicate narratives | duplicated(keep=first)=66 (106 rows in dup groups) | VERIFIED |
| 6 | NatureTitle whitespace variants (' Fractures') | 18,428 rows with leading/trailing whitespace; 349 raw vs 303 stripped uniques; ' Fractures' present | VERIFIED |
| 7 | OIICS v1 titles 2015-23, v2 2024-25; comma-loss artifact 0.1%->66% | EventTitle leading-space: 0% 2015-22, 1.3% 2023, 100% 2024-25. Double-space rate (comma-loss signature): EventTitle 0.09-0.18% (2015-23) -> 66.11% (2024), 64.66% (2025). Comma rates drop: SourceTitle 69%->45%, PartOfBodyTitle 49%->22% | VERIFIED |
| 8 | High-energy prefix coverage: 62x=14,799; 64x=23,626; 43x=17,509; 51x=2,106; 32x=713; total 58,753=55.4%; +53x=4,632 -> 59.8% | Reproduces EXACTLY via string startswith on Event (codes are mixed 2/3/4 digit: 2,458/28,262/75,276). Caveats: '32x' 3-digit v2 codes are fires/explosions (320/321/322); '53x' includes 533x "Contact with hot objects" (1,912 rows), pure environmental heat 531x=2,250; numeric //100 semantics gives only 49,285=46.5%. Labels loose, counts + 55.4%/59.8% arithmetic exact | VERIFIED (with methodology caveat: string-prefix, mixed-length codes) |
| 9 | Oil & gas NAICS 211/213 = 2.6-3.3% | 2,756 rows = 2.60% | VERIFIED |
| 10 | 70.4% narratives contain outcome words; P(Amp>0\|'amputat')=98.6%; 'almost'=28; 'could have'=3 | P(Amp>0\|'amputat')=98.6% (n=27,146) VERIFIED; 'almost'=28 VERIFIED; 'could have'=3 VERIFIED. 70.4% leakage: word-list dependent — my 10-stem list (amputat,fractur,hospital,fatal,death,died,burn,lacerat,crush,concus,dislocat) gives 76.4%; exact 70.4% not reproducible without their word list | PARTIAL (3 sub-claims VERIFIED, 70.4% UNVERIFIABLE) |
| 11 | 70.9% of narratives open with 'An employee was' | startswith (lower+strip): 63.6%. 70.9% is the CONTAINS-anywhere rate | CORRECTED: opens-with=63.6% |
| 12 | vocab: workover=36, christmas tree=13, h2s=12 | 36 / 13 / 12 (case-insensitive substring) | VERIFIED |
| spot | EventDate Jan 2015 - Nov 2025 | min 2015-01-01, max 2025-11-30; years 2015-2025 all present | VERIFIED |

## Commands
- `python3 /tmp/validate.py` / `/tmp/v2.py` / `/tmp/v3.py`: pandas read_csv (dtype=str), groupby year on parsed EventDate, string-prefix vs numeric-prefix on Event, char/word stats, case-insensitive substring counts.

## Verdicts
CLAIM rows-cols-schema: VERIFIED — 105,996x28, names match.
CLAIM narrative-stats: VERIFIED — med 182c/31w, p95 371, max 2134, 0% missing.
CLAIM hosp-amp-counts: PARTIAL — counts not flags; Hospitalized 0-6, Amputation only 0-2.
CLAIM loss-of-eye-35: VERIFIED — exactly 35.
CLAIM dup-66: VERIFIED — 66 excess exact duplicates.
CLAIM naturetitle-whitespace: VERIFIED — 18,428 rows.
CLAIM oiics-2024-break: VERIFIED — double-space 0.18%->66.11%, leading-space 100% in 2024-25.
CLAIM highenergy-55.4pct: VERIFIED — exact via string-prefix; caveat mixed code lengths, '32x'=fires, '53x' includes hot-object contact.
CLAIM oilgas-naics: VERIFIED — 2.60%.
CLAIM leakage-70.4: PARTIAL — 98.6%/28/3 verified; 70.4% word-list-dependent (mine: 76.4%).
CLAIM opens-employee-was: CORRECTED — 63.6% open with it; 70.9% merely contain it.
CLAIM vocab-rarity: VERIFIED — 36/13/12.
CLAIM date-range: VERIFIED — 2015-01-01 to 2025-11-30.
