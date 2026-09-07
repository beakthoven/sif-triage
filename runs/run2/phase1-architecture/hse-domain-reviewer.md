# Phase 1 — HSE Domain Reviewer (retired OIL/ONGC HSE, judge persona)

## 1. Findings (VERIFIED = I checked myself today; INFERRED = field experience)

- **IOGP rule naming (VERIFIED):** Current IOGP Report 459 (2018) rule 8 is **"Work Authorisation — work with a valid permit when required"**, NOT "Permit to Work". The handoff/PS use the older/common name. Indian PSUs do NOT copy the 9 verbatim: BPCL runs **12** Life Saving Rules ("Obtain and Follow Work Permit System", "Safety System Override"); ONGC runs its own ~10-rule set. Indian practice uses "Permit to Work" colloquially — display **"Work Authorisation (Permit to Work)"** and this lands perfectly.
- **DEKRA citation (VERIFIED):** The real number is **"about 20% of recordable injuries have SIF potential"** — Mercer ORC Networks/BST study group (7 firms: ExxonMobil, Shell, BHP, Cargill, ADM, Maersk, PotashCorp), 2011; Martin & Black, *Professional Safety*, Sept 2015 ("fully one-fifth"). DEKRA's own WP: "potential for serious injury is low for typically around 80% of non-SIF injuries." **"20–25%" is NOT in the sources** — the 25% upper bound is blog inflation. Worse: the 20% applies to *recordable injuries*, not to near-miss/UA-UC reports — our flag-rate on a near-miss corpus is a different quantity entirely.
- **Baghjan (VERIFIED):** Blowout 27 May 2020, fire 9 June 2020, well Baghjan-5, Tinsukia; workover by contractor M/s John Energy; WOC 48h compromised to 12h; BOP removed before cement set, no tested secondary barrier, no written instructions, no responsible officer on site (Katakey/NGT + Parliamentary panel 2023). **Baghjan is a process-safety/well-control event — the 9 LSR are personal-safety rules.** Conflating them is the single fastest way to lose an OIL drilling judge.
- **Vocabulary (VERIFIED):** GGS/GCS/EPS/CTF/GCP/ETP/WIP/SRP are genuine Indian upstream installation terms (NIDM module, ONGC docs). C5 (Nigeria dataset dead) is tolerable — OSHA register + manual glossary suffices.

## 2. Risks

- **SEV1 — Personal-safety vs process-safety conflation.** The tool tags IOGP LSR but judges will test it against Baghjan (well control). No well-control/barrier-failure concept exists anywhere in the architecture. One hostile question exposes the gap live.
- **SEV2 — "20–25%" misquote.** A domain judge who knows the literature corrects us on stage; every other number on the slide becomes suspect. Also: anchoring the *review-queue size* to 20–25% is operationally wrong — at OIL's UA/UC volumes that's an unmanageable queue; the queue must be **score-ranked with a digest**, not a fixed-rate flag.
- **SEV2 — 7-of-9 rules shown naked.** "etc." in the PS implies all 9. Unframed, judges read a gap; framed with the measured coverage (PTW 0.003%, Bypass 0.09% of 106k narratives) it reads as rigor.
- **SEV3 — Contractor register.** Synthetic text in polished English fails the smell test instantly; Hinglish/Assamese-loanword register matters more than a Hindi phrasebook.

## 3. Recommendations (per architecture element)

- Triage framing "model proposes, HSE disposes" + override queue: **ADOPT.** Modify: ranked queue + daily digest; never quote a fixed flag-rate target.
- 7-rule head, PTW/Bypass out-of-scope: **MODIFY.** Rename to "Work Authorisation (Permit to Work)"; add a deterministic review-queue nudge ("Was a valid permit in force? Was any safeguard bypassed?") so exclusion becomes a feature; keep the measured-coverage slide.
- SIF-precursor methodology: **MODIFY.** Cite "~20% of recordable injuries (BST/Mercer ORC 2011; Martin & Black 2015)"; state our flag-rate is *measured on our own gold set*, not assumed.
- Claim boundary §B.6: **ADOPT**, plus one addition: never call the tool process-safety/well-control assurance.
- **NEW (adopt):** cheap deterministic **process-safety flag** (kick, BOP, WOC, well control, H2S release, loss of containment) as a separate tag from the 7 LSR — kills the SEV1, ~1 day of work.
- Baghjan answer: **MODIFY** (stronger honest framing below).
- Synthetic corpus: **ADOPT** C5 fallback + the 20-term list below.

**20 must-have terms:** GGS, GCS, EPS, CTF, wellhead/manifold, christmas tree, flowline, workover rig, BOP, WOC (waiting on cement), mud pump/mud tank, SRP (sucker rod pump)/horse head, H2S/sour gas, LEL/gas detector, kick, POOH/RIH, flare pit, hot work/cold work permit, PSV, QRT, Duliajan, monsoon waterlogging, contractor (M/s …), wild elephant movement near installation. (24 — all earned.)

**Example reports (contractor register):**
1. *SIF-potential:* "During workover at Well NHK-xxx, while pulling tubing the tong slipped from driller hand and fell near roustabout standing at rig floor edge. luckily nobody injured. same tong second time slip this week. informed to shift in charge."
2. *Non-SIF:* "Contractor mazdoor slipped on oily walkway near GGS-3 separator area due to monsoon waterlogging. minor bruise on knee, first aid given at site dispensary, resumed duty same day."
3. *Ambiguous:* "H2S alarm activated during tank cleaning preparation at EPS Kathaloni. portable detector showed 12 ppm near manhole. work stopped, area barricaded. reading later found due to nearby flare pit as per supervisor. permit was valid."

**My 5 judge questions:** (1) "Trained on American injury text — why trust it?" → PASS: proxy disclosed + deterministic mechanism labels + blind gold + outcome-redaction ablation; FAIL: "106k reports like yours." (2) "Would it have stopped Baghjan?" → PASS: "No tool prevents blowouts. Baghjan's precursors — WOC compromised, BOP pulled without tested barrier, no officer on site — were *report-type signals that got buried*. We make such reports impossible to bury in a monthly pile; acting on them stays with management." FAIL: any yes-adjacent answer. (3) "Where does 20–25% come from?" → PASS: precise citation + own measured prevalence; FAIL: "DEKRA says so." (4) "Who is accountable when it's wrong?" → PASS: human disposes every flag, overrides logged, nothing auto-closes; FAIL: accuracy talk. (5) Live adversarial input ("no injury occurred"/Hinglish/2 words) → PASS: gray card; FAIL: confident red.

## 4. Verdict

Domain framing is fundamentally sound — the best architecture element is the human-in-loop honesty. Fix the citation, the rule naming, and add the process-safety boundary; all are ≤1 day of work. Conditional GO.
