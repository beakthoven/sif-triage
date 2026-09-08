# Day-1 Evening Review — `app/classifier.py` + `app/gates.py` (adversarial correctness)

Reviewer role: review-classifier · 2026-09-08 · repo state: masked-v1 int8 live on :8177
Method: full read of both files + `routes.py`/`schemas.py`/`config.py`/`ingest.py`, then
empirical probes against the **real masked-v1 int8 artifact** via direct import, plus one
end-to-end probe through the live :8177 API. Probe scripts (rerunnable, throwaway, no
server/DB touch):

- `runs/run2/day1/reviews/probes_classifier_gates.py`
- `runs/run2/day1/reviews/probes_followup.py`

**Findings: 2× SEV1, 7× SEV2, 5× SEV3.** Every claim below was reproduced; the repro
output is quoted. Areas probed and *cleared* are listed at the end.

---

## SEV1-1 — Rule head index scramble: 6 of 7 rule labels are wrong end-to-end

**The artifact emits `rule_logits` in training order; the app zips them against a
DIFFERENT order, so almost every rule probability is displayed under the wrong name.**

- Training order, verbatim from the artifact's own `artifacts/models/masked-v1/train.py:87`:
  `(line_of_fire, working_at_height, driving, energy_isolation, hot_work, safe_mechanical_lifting, confined_space)`
- App order, `app/schemas.py:12` `RULE_KEYS` (alphabetical):
  `(confined_space, driving, energy_isolation, hot_work, line_of_fire, safe_mechanical_lifting, working_at_height)`
- `app/classifier.py:371` does `zip(RULE_KEYS, rule_probs)` — head column *i* is named by
  `RULE_KEYS[i]`. Only index 5 (`safe_mechanical_lifting`) coincides in both orders.

**Repro (probe A, real int8 model):** unambiguous single-rule texts, raw head top vs the
label the app reports:

```
hot_work text        raw top hot_work        p=0.9994 -> app shows line_of_fire     p=0.9994
energy_isolation     raw top energy_isolation p=0.9997 -> app shows hot_work        p=0.9997
confined_space       raw top confined_space   p=0.9933 -> app shows working_at_height p=0.9933
working_at_height    raw top working_at_height p=0.9995 -> app shows driving        p=0.9995
driving              raw top driving          p=0.4981 -> app shows energy_isolation p=0.4981
line_of_fire         raw top line_of_fire     p=0.9997 -> app shows confined_space  p=0.9997
RESULT: 6/6 SCRAMBLED
```

**End-to-end through the live demo server** (`POST :8177/api/classify`, welding/grinding
text): `top rule shown by API: line_of_fire p=0.9994`.

**Demo impact (probe over `artifacts/demo/demo_corpus.jsonl` cards):**

```
contrast-red   (script: "names the rule — Line of Fire")  -> shows confined_space dominant (0.44)
wc-baghjan-1   (script: "Confined Space bar dominant")    -> shows working_at_height (0.685)
gray-negation  (pipe roll-off)                            -> shows driving (0.67)
```

The 0:07–0:19 script beat ("names the rule — Line of Fire", `script_90s.md:43`) and the
`mega-report` "all 7 rule bars" honesty beat are factually wrong on stage. An HSE judge
watching a welding incident light up **Line of Fire** and a dropped-object incident light
up **Confined Space** will catch it.

**This is the true cause of D22.** The "rule-attribution drift on 7/13 demo cards" accepted
at ~15:15 was not drift — it is this deterministic index mismatch. D22's mitigation
(re-annotate cards to actual behavior) papered over the bug instead of fixing it.

Fix (one line): zip against the training order in `classifier.py` (or reorder `RULE_KEYS`;
it is only used for rule naming + mock dict keys, so either is safe — verify the dashboard
does not depend on RULE_KEYS ordering). SIF score, spans, gates are unaffected.

---

## SEV1-2 — Positional score collapse: the same hazard sentence flips FLAG/no-FLAG depending on where it sits in the window; stride-96 chunking has a dead zone at tokens ~24–95

Probe P1: identical hazard sentence ("Worker fell 6 meters from the scaffold without a
harness and was taken to hospital.") preceded by exactly N filler tokens, N = 0..120
(flag threshold 0.7126):

```
pos=  0  score=0.9692 FLAG      pos= 36  score=0.2403
pos= 16  score=0.7157 FLAG      pos= 60  score=0.2184
pos= 20  score=0.6871           pos= 80  score=0.1299
pos= 24  score=0.3318           pos= 96  score=0.9477 FLAG   <- window 2 starts (stride 96)
pos= 28  score=0.4094           pos=100  score=0.4373
pos= 32  score=0.7599 FLAG      flips along position: 9
```

Same words, same window size, same model — score swings 0.13–0.97 and crosses the flag
threshold 9 times. Order-swap repro at equal token count (both 1 window): hot+benign =
**0.8895** vs benign+hot = **0.2429**.

Why the chunking doesn't save it: windows start at 0, 96, 192… (stride 96, overlap 30).
The overlap guarantees a keyword is *tokenized inside* some window, but the model's score
for a hazard decays sharply with its distance from the window start — so any hazard
beginning ~24–95 tokens after every window start (the dead zone between the 30-token
overlap regions) is discounted below threshold. The score spike at pos=96 (0.9477) is the
smoking gun: it is exactly where the hazard becomes window-initial in window 2.

Consequence: a long report with the hazard sentence in the middle is silently scored safe.
This is not the documented "length-OOD badge" behavior — the badge only annotates; the
score itself is wrong (false negative) and the demo invite "paste any report" makes this
reachable live. Note this is *within-window* model behavior (CLS-pooled head discounts
late tokens) that the app's window geometry fails to compensate — the fix belongs in the
app/mitigation layer: e.g. classify on sentence-aligned windows, score = max over
window-position-normalized sub-spans, or at minimum a second pass where each window's
content is re-run window-initial for chunked inputs.

---

## SEV2-1 — int8 within-`predict` window batching violates the D27 "single-text canonical path" ruling

D27 froze: single-text is the canonical scoring path everywhere because int8 batchmates
shift logits. But `predict()` on a >126-token text flattens **all of its windows into one
batched `session.run`** (`classifier.py:342`), so chunked single texts do *not* get the
canonical single-row math. Probe P2, same text, windows run together (what `predict`
does) vs each window solo:

```
benign+hot (155 tok, 2 win): predict=0.2690  solo-window max=0.5324  delta=0.2634
hot+benign (154 tok, 2 win): predict=0.7384  solo-window max=0.9394  delta=0.2010
hot at tok~100            : predict=0.5674  solo-window max=0.5758  delta=0.0084
```

Δp up to 0.26 purely from batch composition — around a 0.7126 threshold this flips
decisions. Either run each window as its own single-row call for int8 (slow only for
chunked inputs) or amend D27 to carve out chunked inputs and document the deviation.
(`supports_exact_batch=False` correctly blocks the *ingest* batch path; the hole is
inside one `predict`.)

## SEV2-2 — `validate_spans` is vacuous in the real path: the "100% substring-validity" acceptance metric is unfalsifiable

`_extract_spans` builds every span as `EvidenceSpan(start=c0, end=c1, text=text[c0:c1])`
(`classifier.py:445`) — the invariant `text[start:end] == span.text` is then *true by
construction*, and the re-check in `routes.py:62,131` can never drop anything. Probe:
`dropped_spans` stays 0 forever; a genuinely foreign span IS correctly rejected, proving
the guard works only on input the classifier never produces. The architecture's
"self-validated text[start:end]==span before render" and the acceptance bar "spans:
substring-validity 100%" currently measure nothing. Fix: construct span text from the
*token strings* (what the model actually highlighted) and keep the slice check as a real
cross-validation — then a misaligned offset_map would be caught instead of hidden.

## SEV2-3 — Drill filter: claimed fix verified, but three false-positive classes remain

Verified OK (the fix agent's claims hold): bare `drill` excluded; `drill pipe pressure
test` clean; `Drilling completed on well XYZ` clean; `drill floor` (demo card) clean;
`drill line slip and cut` clean. True positives work (`mock drill`, `fire drill`).
But (`probe E`):

```
[TRIG] 'The drill was completed at 14:00 hrs, rig move next.'   -> "drill was completed"
[TRIG] 'Crew reminded to exercise caution near the rotary table.' -> bare "exercise"
[TRIG] 'Planned test of the BOP this weekend per schedule.'     -> "planned test"
```

In the OIL register "the drill was completed" = the *well* finished drilling; "exercise
caution" is boilerplate safety language; a "planned test of the BOP" is a well-control
maintenance report — exactly what must NOT be grayed. Fixes: require the drill-as-event
reading (`drill (was) conducted/completed` → anchor on event nouns), drop bare `exercise`
to `mock exercise`, drop `planned test` or require drill/simulation context.

## SEV2-4 — NegEx gate over-fires across sentence boundaries and on emphatic/location uses

Punctuation is not tokenized, so cue↔anchor distance ignores sentence boundaries; anchors
are pure stems with no person/equipment or location disambiguation. Repros (all GRAY):

```
'X-ray confirmed a fracture. No doubt about the diagnosis.'     -> 'no'~'fracture'  (emphatic CONFIRMATION grayed)
'No issues noted during rounds; hospital corridor slippery.'    -> 'no'~'hospital'  (hospital = LOCATION)
'Employee had a fracture. No hospitalization was needed.'       -> 'no'~'fracture'  (fracture is NOT negated)
'Pipe severed hydraulic line. Not near personnel at the time.'  -> 'not'~'severed'  (equipment; negation scopes personnel)
'Fracture of the drill bit reported. No other damage.'          -> 'no'~'damage'    (positive-damage report)
```

True positives still work (`Worker fell 2m. No injury occurred.` GRAY ✓, `Several cuts
and bruises, not serious.` clean ✓). Gates are advisory (gray = review queue, nothing is
deleted), but the queue floods and the detail strings assert false readings
("'no'~'fracture'" on a confirmed fracture), which erodes the "engineered humility"
story in front of judges. Cheapest correct improvement: reset the window at sentence
boundaries and demote pairs whose anchor sentence contains the cue's negation scope
marker (e.g. "no doubt").

## SEV2-5 — Per-rule tuned thresholds from the artifact are never loaded

`metrics.json`/`thresholds.json` carry tuned per-rule thresholds
(lof 0.67, wah 0.61, driving 0.95, ei 0.83, hw 0.74, sml 0.82, cs 0.65), and ARCHITECTURE
specifies "7 rules, per-rule thresholds". The app hardcodes `threshold: 0.5` for every
rule in `schemas.py:28-34` and `/api/rules` serves that. Combined with SEV1-1 the rule
display is wrong twice; fix the order first, then load thresholds from the artifact.
(Rule probs are correctly NOT temperature-scaled — the tuned rule thresholds are
raw-sigmoid scale; consistent once loaded.)

## SEV2-6 — No input length cap: one 200k-char paste = 501 windows = 15.9 s in a single request

`ReportIn.text` has `min_length=1` and no max; `ingest.py` has no cap either. Probe:
200k chars → 48,002 tokens → 501 windows → **15.86 s** for one `predict` (throttled CPU),
plus the O(cues×tokens) NegEx scan. A bulk CSV of such rows multiplies it. The
`long_input` gate only badges at >120 words. Add a hard cap (e.g. reject/truncate >20k
chars with a clear 422) — demo-relevant because the paste box is a scripted beat.

## SEV2-7 — Spans shown only from the argmax-SIF window; evidence in other windows is invisible

`classifier.py:366-368`: `best = rows[argmax(sif_probs)]`, spans extracted from that
window only. On multi-window reports the highlight can omit the window containing the
actual evidence (e.g. when window 1 wins the max but the anchor phrase sits in window 2).
Merge span candidates across windows (each with its own offset slice) before top-3.

---

## SEV3-1 — Language gate: one Devanagari char grays an English report; detail string self-contradicts

`'Worker राम Kumar slipped near the walkway at GGS.'` → GRAY at non_ascii_ratio=**0.06**,
with detail `"language badge [devanagari]: non_ascii_ratio=0.06 (> 0.15)"` — the message
literally prints a false comparison (trigger was the any-Devanagari clause, not the
ratio). Hindi names inside English reports are realistic for this user base; meanwhile a
Cyrillic report under 15% non-ASCII passes. Fix the detail string; consider a minimum
Devanagari run length (≥3 chars) or ratio-gating the block clause too.

## SEV3-2 — Codes path misses plural/suffixed codes (`LOTOS`, `LOTOs`)

`'LOTOS on pump 3'` (15 chars) → GRAY `"len=15 < 20 and no short code"`;
`'LOTOs verified'` → GRAY. `\bLOTO\b` cannot match `LOTOS`, and acronym density is 0.25 <
0.4. Lowercase works (`'loto applied'` accepted ✓ — text is uppercased first), and
`'LOTO not applied'` / `'N2 leak at manifold'` pass ✓. Fix: prefix-match codes
(`\bLOTO[S]?\b`) or word-stem matching for the whitelist.

## SEV3-3 — Dead/misplaced code: `classify_batch` nested inside `flag_threshold`; Protocol missing the method

`classifier.py:126-127` — an indented `def classify_batch(...): ...` sits **after
`return` inside `flag_threshold`**, evidently meant to be a `Classifier` Protocol member.
Verified: `hasattr(Classifier, 'classify_batch') == False`. Runtime works only because
both concrete classes define it; any future Classifier implementation gets no protocol
guidance, and `routes.py:124` calls `clf.classify_batch` against the protocol. Also dead:
`routes.py:39 FLAG_THRESHOLD = 0.5` (nothing reads it; `flag_threshold()` is the real path).

## SEV3-4 — Fallback "evidence" spans include punctuation-only tokens and leading spaces

Weak-span fallback takes top-3 tokens with no content filter: benign texts show
`spans=[',', ' everything', ' no']`; flagged texts show spans like `' struck by'`,
`' caught'` (leading space from ByteLevel `Ġ` tokens). Cosmetic, but a highlighted comma
on a judge-facing card reads as broken. Filter to tokens matching `[A-Za-z0-9]` and strip
edge whitespace (adjusting offsets accordingly).

## SEV3-5 — Threshold loader ignores `threshold_calibrated` and falsy-but-valid values

Nits only (mainline verified safe, see Cleared): if `operating_point_test_tuned` carries
only `threshold_calibrated` (no raw `threshold`), the loader falls back to 0.5 despite a
valid calibrated value sitting in the file; `threshold: 0.0` is treated as absent rather
than invalid. Both are log-and-fallback paths, not wrong decisions.

---

## Probed and CLEARED (no bug found, with evidence)

- **Offset mapping vs unicode** (probe B): emoji 👷🏽 (multi-codepoint), 🇮🇳 flag, ZWJ
  👨‍👩‍👧, NFD é (len 34→33 under the tokenizer's NFC normalizer), CRLF, Devanagari,
  mixed — all token offsets stayed in-bounds, monotonic per char, `max_off == len(text)`.
  Byte-split emoji tokens share one char span (expected ByteLevel behavior, harmless to
  merging). No failing input exists for *bounds*; the real span risks are SEV2-2
  (vacuous validation) and SEV3-4 (cosmetic), both above.
- **Threshold loading precedence** (probe C): missing metrics.json → T=1.0/thr=0.5;
  corrupt JSON → T=1.0/thr=0.5 (logged); **both operating points present →
  `operating_point_test_tuned` wins (thr=0.712581)**; val-frozen-only → deliberately
  ignored → 0.5 (documented in docstring, matches D19); string threshold parsed; 1.5 and
  negative-T rejected to safe fallbacks. Loaded artifact: T=1.68397…, thr=0.712581 —
  matches `threshold_calibrated` exactly.
- **Temperature application** (probe C/G): applied exactly once (sigmoid(logit/T),
  `classifier.py:363`); threshold mapping `sigmoid(logit(raw)/T)` verified
  decision-identical to `sigmoid(raw) >= raw_threshold` over a 2001-point logit grid.
- **Chunking geometry**: `_windows(126)=[(0,126)]`; 127→`[(0,126),(96,127)]`;
  128→`[(0,126),(96,128)]`; tail always covered; 30-token overlap means no ≤30-token
  keyword is ever split across all windows (the failure mode is positional discount,
  SEV1-2, not truncation). Empty text → single (0,0) window, no crash. Same input twice →
  bit-identical score (deterministic).
- **NegEx true-positive/negative controls**: `No injury occurred` fires ✓;
  `Several…` excluded from sever stems ✓; counterfactual suppression logic present ✓.
- **Mock classifier**: span construction also vacuous-but-safe; seeded determinism holds.

## Recommended fix order

1. **SEV1-1** rule-order zip (one line) + re-verify the 13 demo cards against the frozen
   script; re-open D22's "accept drift" ruling. Blocks tomorrow's rehearsal.
2. **SEV1-2** chunking positional collapse: at minimum sentence-aligned windows or a
   window-initial re-pass for chunked inputs; re-run the position scan as the gate.
3. SEV2-1 int8 window-batching (code change or D27 amendment), SEV2-3/2-4 gate regex
   tightening, SEV2-6 input cap — all small diffs.
4. SEV2-2 real span validation + SEV2-5 load per-rule thresholds + SEV3s.

Files written by this review: `runs/run2/day1/reviews/classifier_gates.md` (this file),
`runs/run2/day1/reviews/probes_classifier_gates.py`,
`runs/run2/day1/reviews/probes_followup.py`. No repo source files modified; no git
operations; :8177 untouched (one read-only POST).

<<SCORES {"ps":"26165","role":"review-classifier","go_no_go":5,"severity":8,"feasibility":8,"data_risk":2}>>
