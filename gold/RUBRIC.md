# Gold Labeling Rubric — SIF-Potential Triage (v1.0, frozen 2026-09-08)

You are labeling incident/near-miss reports for **SIF-potential**: could this
event have killed or permanently injured someone? You see only the report
text (outcome words are blanked as `[OUTCOME]`) and a short title. Judge the
**exposure**, never the outcome.

## The one question

> **Could this have plausibly killed or permanently injured someone if
> circumstances were slightly different?**

- Yes → **S** (SIF-potential)
- No → **N** (non-SIF)
- Genuinely cannot tell → **U** (unsure — use sparingly; when torn between
  S and N, judge the mechanism: high-energy exposure present → S)

A person standing one step away from a dropped load is SIF-potential even
though nothing hit them. A paper cut is non-SIF even if the report is long.

## The 7 Life-Saving Rules (tag all that apply when you press S)

Rule tags are optional but encouraged — one checkbox per rule that is
**actually present** in the described exposure.

| Rule | Tag when… | Example |
|---|---|---|
| **Line of Fire** | person in the path of moving/released energy: struck-by, caught-in/between, collapsing material | Worker standing between a backing loader and a stack; pipe rolls off a rack toward a man's legs. |
| **Working at Height** | work above ground/floor level where a fall is possible (ladder, roof, scaffold, platform edge) | Fitter bolts up a flange from an extension ladder, no tie-off point above him. |
| **Driving** | vehicle/mobile-equipment movement with people or collision exposure | Yard truck reverses toward a loading bay while a spotter walks behind it. |
| **Energy Isolation** | work on/near live energy without proven isolation: electrical, stored pressure, gravity, motion | Electrician opens a 440V panel on a "tripped" breaker that was never locked out. |
| **Hot Work** | welding/cutting/grinding/open flame, especially near flammables | Welder grinding over a drum of solvent rags; sparks drop into the bund. |
| **Safe Mechanical Lifting** | cranes/hoists/rigging/suspended loads; people under or near the load path | Rigger guides a swinging 2-ton skid by hand, standing under the boom radius. |
| **Confined Space** | entry into tanks, vessels, pits, manholes, silos; atmosphere or engulfment risk | Operator climbs into a manhole to check a valve; no gas test done before entry. |

(Tag style follows IOGP Report 459 Life-Saving Rules. Tag only what the text
describes — a keyword alone is not an exposure; see edge cases.)

## Edge cases

- **Drills / exercises / simulations → N.** "During the fire drill, the
  muster point was blocked" is not a real exposure.
- **Negation is real.** "No one was in the drop zone" or "the guard was in
  place and held" → the barrier held → usually N. Read the whole sentence;
  do not tag on a single word.
- **Single passing mention.** One keyword with no described exposure
  ("the crane was parked nearby") is not that rule's exposure. Judge what
  actually happened.
- **`[OUTCOME]` blanks hide what happened to the person.** Do not try to
  guess the injury; judge the mechanism described before/around the blank.
- **First 20 items are the calibration pilot** — identical for all four
  labelers. We review these together before the main round.

## Blind protocol (hard rules)

1. **Do not discuss any item** with other labelers until the export is
   frozen. Your disagreements are data — they get measured (Fleiss' κ) and
   adjudicated later against this spec, not negotiated live.
2. **No external lookups of report text.** Do not search phrases from a
   report to find the original record — that unblinds you.
3. One judgment per report; **no going back** after saving.
4. Label only on your own port/app instance; your file is yours.

Practical: ~150 items each ≈ 1.5–2 hours. Keys: **S** / **N** / **U**,
**Enter** to save a SIF label. Close and reopen the app any time — it
resumes where you stopped.
