# Label-spec component A — OIICS dual era-conditional maps + SIF-positive definition

**Status:** DRAFT for H2 freeze (D9, D15). Code: `data_pipeline/oiics_maps.py` (stdlib+pandas,
self-check green, ~4 s). Machine-readable fragment: `spec/drafts/maps_fragment.yaml`.
All numbers measured on `data/January2015toNovember2025.csv` (105,996 rows; v1 2015-23 = 88,250,
v2 2024-25 = 17,746) on this machine, 2026-09-08.

## 1. Dual era-conditional prefix maps (D9)

The 2024 OIICS v2.01 break is a code **renumbering**, verified against `value_counts` of
EventTitle per 2-digit prefix per era (the module's self-check re-verifies every claim and
fails loudly if any drifts):

| prefix | v1 meaning (n) | v2 meaning (n) | rule consequence |
|---|---|---|---|
| 62x | struck by falling/swinging object (14,607) | animal bites (192) | LoF → unmapped |
| 43x | fall to lower level (15,012) | fall on same level (2,497) | WaH → unmapped (negative pool) |
| 41x | slip without fall (259) | fall to lower level (3,130) | unmapped → WaH |
| 64x | caught in running equipment (21,462) | struck by falling object (2,164) | LoF → LoF (rule-stable) |
| 65x | collapsing structure / trench cave-in (236) | struck by/caught in running powered equipment (4,053) | LoF → LoF |
| 66x | rubbed/abraded (19) | caught/wedged between, struck by rolling objects (1,262) | unmapped → LoF |
| 44x/45x | jump to lower level (255) / PFAS-arrested fall (64) | eliminated (0 rows) | WaH → gone |
| 31x/32x | fires / explosions | explosions / fires — **swapped** | both stay hot_work |
| 22x–25x | rail / animal / pedestrian-struck / water-vehicle | shifted sub-codes | 2x stays transportation in both eras |

Cross-rule collisions are **explicitly registered** in `RENUMBERED_CROSSRULE = {41, 43, 44, 45, 62, 66}`
and handled by era keying; same-rule re-titles in `RENUMBERED_SAME_RULE = {22, 23, 24, 25, 31, 32, 63, 64, 65}`.
The self-check asserts no prefix collides outside these registers.

Deliberate deviations from the phase-1 F2 sketch: v1 `45x` (PFAS-arrested fall, n=64) mapped to
Working at Height — a height fall occurred; v2 `42x` ("stepping between levels", n=151) left
unmapped (not same-level, not a height fall).

## 2. Seven learnable IOGP rules (multi-hot) + well-control tag

Assignment = era-conditional code prefix map **plus** narrative/SourceTitle keyword LFs
(CS/EI/HW/SML/Driving/LoF; WaH is code-only). Rows are **multi-hot**; `primary_rule` is
deterministic (keyword matches first, rare-first tie order CS > EI > SML > HW > Driving > WaH > LoF)
and used only for stratification/macro-F1.

Measured rule distribution (multi-hot, % of rows; eras stable → maps are era-consistent):

| rule | v1 | v2 | all |
|---|---|---|---|
| line_of_fire | 48.78 | 47.41 | 48.55 |
| working_at_height | 17.37 | 17.64 | 17.42 |
| driving | 11.55 | 12.03 | 11.63 |
| hot_work | 3.78 | 3.77 | 3.78 |
| safe_mechanical_lifting | 3.55 | 4.30 | 3.68 |
| energy_isolation | 2.32 | 2.78 | 2.40 |
| confined_space | 0.29 | 0.66 | 0.35 |
| **unmatched** | **24.05** | **24.52** | **24.13** |
| multi-rule rows | 11.39 | 12.57 | 11.59 |

Deltas vs phase-1 F2 (LoF 44.2%, union 74.7%, multi 5.91%) come from this implementation's
wider keyword LF set and true multi-hot accounting; they are self-consistent and reproducible
via the module. CS/EI remain marginal classes (0.35% / 2.40%) — SEV2-3 stands; synthetic
quota must carry them.

**Well-control/barrier tag** (Baghjan-class, deterministic, narrative+SourceTitle):
n=185 rows (0.175%; v1 152 / v2 33). Patterns: blowout, blow-out, blowout preventer, well control,
BOP, workover, christmas tree, H2S, hydrogen sulfide, gas migration, lost circulation, snubbing,
coiled tubing, wellhead. Bare "kick" deliberately excluded (collides with "kicking" in violence
titles). Rare as expected — the tag exists so this class is impossible to bury, not for volume.

## 3. SIF-positive definition (D15) — measured candidates, frozen pick

Era-conditional prefix frozensets; positive rate per era:

| candidate | definition | v1 | v2 | era gap |
|---|---|---|---|---|
| A_strict | legacy 5-mechanism, era-translated (v1: 43,62,64,51,32 / v2: 41,64,65,51,31) | 60.40% | 55.57% | 4.8pp |
| **B_middle (FROZEN)** | **high-energy mechanism codes: contact 6x + fall-from-height 4x + fire/explosion 31/32 + electrical 51** (v1: 31,32,43,44,45,51,62,63,64,65 / v2: 31,32,41,51,63,64,65,66) | **65.52%** | **64.21%** | **1.3pp** |
| C_broad | B + transportation 2x + oxygen-deficiency 56 (all 7-rule code prefixes) | 74.32% | 73.50% | 0.8pp |
| D_keyword | rule union incl. narrative keyword LFs (not a prefix set; not code-deterministic) | — | — | 75.87% overall |

Cautionary anchor (reproduced exactly by the self-check): the legacy v1 prefix set applied
era-blind gives **55.43% overall but 30.73% on 2024-25** — the silent test-set collapse (D9/SEV1-4).

**Rationale for freezing B_middle:**
- *Defensible middle* of the measured 55→76% swing: not the narrow 5-mechanism legacy set
  (A), not the everything-the-rules-touch union (C/D).
- *Strict high-energy mechanism set*: every prefix maps to line_of_fire / working_at_height /
  hot_work / energy_isolation — high kinetic/potential/thermal/electrical energy contact.
  Excludes transportation 2x (mixed mechanisms: falls from vehicles, pedal-cycle falls sit
  next to pedestrian-struck-by) and oxygen-deficiency 56 (exposure, not energy contact);
  those rows still carry their rule labels for the multi-label head.
- *Era-consistent in meaning*: 1.3pp era gap vs A's 4.8pp; the v2 set contains the v2
  renumbered equivalents of exactly the same mechanisms.
- *Code-only/deterministic*: reproducible without narrative text, immune to masking and
  keyword-list drift — unlike D (75.87%, keyword-dependent, unfreezable as frozensets).

Frozen overall prevalence: **65.30% (n=69,214/105,996)** — v1 65.52% (57,819/88,250),
v2 64.21% (11,395/17,746). Downstream class-balance, thresholds, and metrics planning
should use these numbers.

## 4. Reproduce

```
python3 data_pipeline/oiics_maps.py   # ~4 s; asserts + prints all numbers above
```
