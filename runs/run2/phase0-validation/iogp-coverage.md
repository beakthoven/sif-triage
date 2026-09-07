# Phase-0 Validation — Cluster: OSHA → IOGP Life-Saving-Rule coverage proxy

**Validator:** phase0-validator (independent rebuild) · **Date:** 2026-09-08
**Data:** `data/January2015toNovember2025.csv` — measured 105,996 data rows (csv.DictReader), all `Event` fields pure digits. Claimed prior numbers from HANDOFF.md §B.1 line 83.

## My proxy (documented, first-match precedence)

Match on `Final Narrative` (case-insensitive regex) and/or `Event` 2-digit prefix. Precedence = order below; first match wins, so rows count once.

1. **Permit to Work** — `\bpermit`
2. **Bypassing Safety Controls** — `\bbypass`, `\boverrid`, `guard (was/had been) (removed|disabled|bypassed)`, `(removed|disabled) (the|a) (guard|interlock|safety device|switch|guard)`
3. **Confined Space** — `confined space`, `manhole`, `tank entry`, `vessel entry`, `enter(ed|ing) (tank|vessel|silo|vault|pit|bin|hopper)`, `inside (tank|vessel|silo)`; or code `56*` (oxygen deficiency)
4. **Energy Isolation** — `lockout/lock out`, `tagout/tag out`, `energized/de-energize`, `stored energy`, `arc flash`, `unexpectedly (started|activated|energized)`
5. **Hot Work** — `hot work`, `weld`, `torch`, `grind`, `cutting (torch|metal|steel)`, `spark`; or codes `31*`,`32*` (fire/explosion)
6. **Safe Mechanical Lifting** — `crane`, `rigging`, `hoist`, `suspended/overhead load`, `sling`, `dropped load` (forklift deliberately excluded → Driving)
7. **Driving** — `forklift`, `skid steer`; or codes `2*` (transportation incidents)
8. **Working at Height** — codes `43*` (fall to lower level), `44*` (jump to lower level)
9. **Line of Fire** — codes `51*` (electrical), `62*` (struck-by), `63*` (struck-against), `64*` (caught-in/compressed), `65*` (caught/crushed in collapsing); or `struck by`, `caught (in|between)`, `crushed`, `pinch(ed|point)`, `ran over`

Scripts: `/tmp/iogp/proxy.py`, `/tmp/iogp/variant.py` (variant used broader Driving keywords `vehicle|driv|truck`).

## Measured results (N=105,996)

| Rule | Mine (n, %) | Prior claim | Note |
|---|---|---|---|
| Permit to Work | 3, 0.003% | 0.00% (3 rows) | exact match; only 1 of 3 is truly PTW ("permit-required confined space") — 2 use "permit" as verb |
| Bypassing Safety Controls | 99, 0.09% | 0.08% | <0.1% either way |
| Confined Space | 311, 0.29% | 2.5% | proxy-breadth dependent |
| Energy Isolation | 1,275, 1.20% | 6.5% | prior likely folded in 51* codes/more keywords |
| Hot Work | 3,824, 3.61% | 5.2% | same order of magnitude |
| Safe Mechanical Lifting | 3,237, 3.05% | 3.5% | close (forklift excluded) |
| Driving | 11,732, 11.07% | 12.4% | close (2* codes + forklift) |
| Working at Height | 16,907, 15.95% | 15.5% | close |
| Line of Fire | 42,018, 39.64% | 45.7% | raw code signature 38.2% (62+64+51) to 45.1% (+63+65) |
| (unmatched) | 26,590, 25.1% | ~18.6% implied | same-level falls, overexertion, exposures, violence — legitimately outside the 9 rules |

**Top-3 (LoF + WaH + Driving) = 66.7%** (variant with broad Driving keywords: 68.9%). LoF share by year stable 39–42% for 2015–23, dipping to 36.0–36.5% in 2024–25 (OIICS v1→v2 break — proxy degrades slightly but survives).

## Verdicts

- **(a) PTW + Bypassing undetectable (<0.1%): VERIFIED.** 3 permit mentions (0.003%), 1 genuinely PTW; 84–99 bypass/guard mentions (0.08–0.09%). Both are procedural and invisible in post-injury text. "Never fake them" guidance stands.
- **(b) Line of Fire dominates ~40–50%: VERIFIED.** 39.6% with precedence assignment; 45.1% raw wide-code signature (claim 45.7%, Δ0.6pp). Clearly the largest rule under any variant (next is ≤16%).
- **(c) Top-3 rules cover >65%: VERIFIED.** 66.7–68.9% depending on Driving keyword breadth.
- Per-rule non-load-bearing percentages: **PARTIAL** — Confined Space / Energy Isolation magnitudes are proxy-dependent; prior values not reproducible with a literal keyword proxy, directionally consistent.
