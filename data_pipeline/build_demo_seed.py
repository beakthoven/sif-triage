"""Build the de-saturated demo seed (workstream B1) — novel, negative-dominant
register corpus for the demo database.

Why: the old demo DB was seeded from the TRAINING CORPUS (bulk_ingest_5k.csv =
3k synthetic + 2k masked OSHA), so the model scored its own training rows:
flag_rate 0.7095, median 0.958, 59.7% near-dup banners (measured on
artifacts/demo/demo_pre.db 2026-09-25). Triage value = zero.

What this generator produces (deterministic, seeded):
  artifacts/demo/demo_seed_v3.jsonl  — labeled rows (text + facets + sif label
                                       + kind + provenance) for the PRE state
  artifacts/demo/demo_seed_v3.csv    — same rows as the bulk-ingest CSV
  artifacts/demo/ingest_500_v3.jsonl — labeled rows for the LIVE-INGEST beat
  artifacts/demo/live_ingest_500_v3.csv — its CSV form (uploaded via the demo UI)

Mix (domain-realistic negative-dominant register, ~18.25% labeled precursors):
  pre state 4,548 rows = 3,670 routine/admin (~80.7%)
                       + 800 novel precursors (~17.6%)
                       +  30 planted Kathalguri GCS confined-space cluster
                       +   48 deliberately-memorised corpus rows (~1.1%, unlabeled)
  live ingest   500 rows = 343 routine +  40 planted cluster + 117 precursors

Novelty contract: every routine/precursor/planted text is WRITTEN HERE, never
copied from the training corpus. The build embeds every novel row (MiniLM,
artifacts/embeddings/minilm) and regenerates any row whose max cosine against
the 70,398-row base corpus index OR against the other seed rows is >=
REJECT_COSINE (0.905, margin under the 0.91 banner threshold). Only the
deliberately-memorised subset is allowed to match the corpus — that is the
"memory, not generalisation" feature, kept small (~1%) and source-marked.

Run:  .venv/bin/python data_pipeline/build_demo_seed.py            # build + QA
      .venv/bin/python data_pipeline/build_demo_seed.py --skip-qa  # corpus only
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = REPO_ROOT / "artifacts" / "demo"
OLD_BULK_CSV = DEMO_DIR / "bulk_ingest_5k.csv"
RAW_OSHA_CSV = REPO_ROOT / "data" / "January2015toNovember2025.csv"
BASE_INDEX = REPO_ROOT / "artifacts" / "embeddings" / "corpus_embeddings_fp16.npy"

CSV_COLUMNS = ["text", "date", "site", "activity", "contractor", "barrier", "register"]

SEED = 26165
REJECT_COSINE = 0.905    # margin below the 0.91 near-dup banner threshold
SURPLUS = 1.12           # generate 12% extra candidates per bucket
MAX_ATTEMPTS = 8

# --- slot pools -------------------------------------------------------------
SITES = [
    "Duliajan GGS-2", "Duliajan GGS-4", "Naharkatiya EPS", "Moran GGS-1",
    "Jorajan", "Baghjan EPS", "Kathalguri GCS", "Dikom", "Tengakhat",
    "Makum", "Borholla", "Kumchai", "Amguri", "Galeki", "Geleky",
    "Sapkhaiti", "Disangmukh", "Khoraghat", "Workover Rig #3",
    "Workover Rig #5", "Workover Rig #7", "Drilling Rig OIL-19",
    "Workshop Duliajan", "Central Store Duliajan", "Tank Farm Tengakhat",
    "Lakwa",
]
ROLES = [
    "the duty fitter", "a contract roustabout", "the floor crew", "one roustabout",
    "the shift HSE officer", "a helper", "the welder", "the derrickman", "the driller",
    "the junior engineer", "the camp supervisor", "the driver", "the storekeeper",
    "a paint crew worker", "the electrical technician", "the gauger",
    "the pump attendant", "one floorman", "the safety steward", "the crane operator",
]
SMALL_N = ["two", "three", "four", "six", "nine", "twelve"]
TIMES = [
    "around 06:40 hrs", "in the morning shift", "during the day shift",
    "around 14:15 hrs", "in the evening shift", "during night shift",
    "around 21:40 hrs", "at shift change",
]

PRECURSOR_ACTIVITIES = [
    "pipe handling", "derrick work", "scaffolding erection", "welding on substructure",
    "gas cutting", "vessel entry", "tank cleaning", "crane lifting", "vehicle reversing",
    "christmas tree valve greasing", "catwalk operations", "rig floor operations",
    "well cellar entry", "pressure testing", "grinding on pipe rack", "painting at height",
    "tower loading", "sludge pit cleaning", "heat exchanger bundle pulling",
    "compressor maintenance", "manifold valve overhaul", "separator internals inspection",
    "drum decanting", "manifold valve overhaul", "pump bearing change",
]

DATES: list[str] = []
CONTRACTORS = [
    "Brahmaputra Field Services", "Duliajan Mechanical Works",
    "Upper Assam Industrial Services", "North East Rigging Co.",
    "Oilfield Support Partners", "Dibrugarh Plant Maintenance",
    "Assam Site Logistics", "Eastern Safety & Engineering",
    "Tengakhat Equipment Services", "Brahmaputra Fabrication Works",
]


def _contractor(rng: random.Random) -> str:
    return rng.choice(CONTRACTORS)


def _date_pool() -> list[str]:
    """Working days across the last quarter (Apr-Sep 2026), ISO strings."""
    out: list[str] = []
    rng = random.Random(9)
    d = date(2026, 4, 6)
    while d <= date(2026, 9, 24):
        if d.weekday() < 6:  # Mon-Sat register
            out.append(d.isoformat())
        d += timedelta(days=1)
    rng.shuffle(out)
    return out


# Generic one-sentence nuggets — 1 drawn at random per row so repeated
# openers diverge in content, not just in site slots.
NUGGETS = [
    "The used absorbents were bagged, tagged and entered in the waste ledger.",
    "The walkway was left clear end to end after the round.",
    "The checklist was countersigned by the area in-charge before close of round.",
    "Tags were rewritten where the print had faded.",
    "One leaking jerry can was emptied, rinsed and returned to the chemical store with a fresh label.",
    "The notice board was updated with the week's rota.",
    "The duty register carries the completion time and the countersignature.",
    "The grass verge along the approach was trimmed and the clippings carted away.",
    "Standing water near the low patch was pumped out and the ground re-graded.",
    "The scrap bay was squared up and the scrap register brought up to date.",
    "Drip trays under the set were swapped and cleaned with fresh absorbent.",
    "The contract gang squared the pallet rows at the {area}.",
    "The periphery lights were tested at {time}.",
    "Fresh absorbent pads replaced the oil-stained ones near the {area}.",
    "The supporting indents were filed without delay.",
    "The agency supervisor accompanied the round and noted the same points.",
    "Photographs were attached to the register page as usual.",
    "The week's rota was posted on the board after the round.",
    "Nothing further was pending on the item at close of round.",
    "The housekeeping star board was updated with the finding.",
    "The store keeper filed the supporting indents the same afternoon.",
    "Follow-up items from the last round were re-verified during the same walk.",
]

# Near-miss follow-up nuggets for the precursor register (same purpose).
PREC_NUGGETS = [
    "The job was stopped and re-permitted after the correction was in place.",
    "A follow-up entry was raised on the corrective item the same day.",
    "The crew was re-briefed at the evening TBT with both shifts present.",
    "The permit issuer amended the permit conditions before the restart.",
    "The register entry was read out at the area review the same week.",
    "Stores issued the replacement parts and the item was closed the same week.",
    "The HSE officer verified the rectification before the next job started.",
    "Photographs of the defect were attached to the register page.",
    "The contractor supervisor signed the re-brief record.",
    "The affected equipment was tagged and returned to service after checks.",
]
AREAS = [
    "workshop", "stores approach", "pipe yard", "camp mess", "control room",
    "DG house", "substation bay", "chemical shed", "water tank compound",
    "main gate", "laydown area", "workshop annexe", "canteen block",
    "washroom block", "change room", "lab annexe", "fuel bay", "scrap bay",
    "truck parking", "pump deck", "mud tank farm", "compressor deck",
]

# ---------------------------------------------------------------------------
# NEGATIVE-DOMINANT register (~80%) — routine observations, housekeeping,
# inspections, training, admin. Written fresh; phrasing avoids negation
# cue~outcome-stem pairs so the review queue stays proportional.
# Each row = opener + detail (+ optional tail) so repeated openings diverge.
# ---------------------------------------------------------------------------

NEG_BUCKETS: list[tuple[str, list[str], list[str], int]] = [
    # (kind, activities, opener templates, target n)
    ("housekeeping", ["housekeeping round", "yard cleaning", "camp upkeep"], [
        "Housekeeping round of {site} covered the workshop, stores approach and the drain behind the camp mess. Cut pipe ends and empty paint drums were shifted to the scrap bay and the walkway was left clear end to end.",
        "Evening housekeeping walk at {site}: pallets stacked square at the pipe yard, drip trays under the generator set swapped and cleaned, and the grass verge along the approach road trimmed by the contract gang.",
        "Morning housekeeping round at {site}: absorbent pads near the lube-oil shelf replaced, one leaking jerry can emptied and returned to the chemical store with a fresh label, and the walkway swept.",
        "Camp upkeep inspection at {site} found the mess hall, washrooms and the drying room in order; the laundry line area was cleared of scrap wood and the pathway gravelled where mud had pooled after the rains.",
        "Weekly housekeeping check of the change room and boot rack at {site}: boots dried and arranged, lockers in order, and the notice board updated with the week's muster and canteen menu.",
        "{role} and two helpers completed the {site} yard clean-up. Used cable drums were stacked on sleepers and the old concrete wash-out near the water tank was broken up and carted away.",
        "After yesterday's heavy shower, the {site} team pumped standing water out of the low patch near the DG exhaust side and re-graded the ground, leaving the walk to the muster point dry.",
        "Housekeeping sweep of the {site} control room and the panel back-verification lane: cable spares re-racked, floor cable trays dusted and the fire-plan copy re-laminated on the exit door.",
        "End-of-month housekeeping at the {site} chemical shed: empty drums segregated to the scrap bay, pallet rows squared and the bund wall joint repointed where seepage had stained it.",
    ], 520),
    ("inspection", ["fire extinguisher inspection", "ladder inspection", "permit-to-work audit",
                    "substation round", "pipeline marker inspection", "eye-wash station check",
                    "DG house check", "chemical store check", "wind sock inspection",
                    "vehicle documents check"], [
        "Monthly fire-extinguisher inspection at {site}: all units in date, pressure needles in the green, seals intact and mounting brackets firm. Two units were given a shake-and-tag refresh and the checklist countersigned.",
        "Ladder inspection round at {site} this morning. Step ladders and the extension ladder were checked rung by rung; feet, stiles and ropes found sound. Items re-tagged and returned to the racks.",
        "Permit-to-work audit at {site}: {n} live permits reviewed against the register. Closures signed the same day, gas-test entries present, and cold-work permits matched the isolation certificates on file.",
        "Substation round at {site} with the electrical supervisor: panel lamps, earth strips and the rubber matting checked, door interlocks found working, and the logbook updated with meter readings.",
        "Cathodic protection check along the {site} flowline markers: test posts accessible, terminal boxes dry, readings logged within the expected band. Marker posts repainted where fading had set in.",
        "Pipeline marker inspection between {site} and the approach road: marker posts upright and legible, one repainted and two boundary stones re-set after the monsoon wash.",
        "Eye-wash station and first-aid box check at {site}: bottles sealed and in date, sterile pads and crepe rolls restocked, and the injury register cross-checked against the treatment log with nil findings.",
        "DG house check at {site}: exhaust muffler lagging sound, fuel day tank level logged, drip tray dry and the hourly log filled in by the operator without gaps for the whole week.",
        "Chemical store check at {site} with the stores in-charge: drums palletised and labelled, MSDS folder current, spill kit seals intact and the inventory tally matched the bin cards.",
        "Wind sock and helipad marking inspection at {site}: sock seam stitched where a tear had started, netting re-tied and the perimeter lights tested by {role}.",
        "Weekly vehicle documents check at the {site} gate: PUC certificates, insurance slips and driver licences verified for the water bowser and two crew vans, stickers renewed on the spot.",
        "Fire-pump churn test at {site} taken during the quiet window: discharge pressure recorded on the test line, jockey pump cut-in verified and the log signed by {role}.",
    ], 560),
    ("training", ["safety induction", "toolbox talk", "fire drill", "mock drill",
                  "PPE issue", "evening review meeting", "spill-kit training"], [
        "HSE induction completed for {n} new contract hands posted to {site}. Roll call taken, identity cards issued, muster point walked, and acknowledgement sheets signed and filed.",
        "Toolbox talk conducted at {site} before the shift change: hand safety while handling cast-iron fittings, hydration during the afternoon peak, and the correct way to flag a passing vehicle near the gate.",
        "Half-day session on portable fire extinguishers held at {site} for {n} staff. Two hands practised the PASS technique on the training unit and every attendee signed the attendance sheet.",
        "Mock drill conducted at the {site} camp at {time}. Assembly took {n} minutes against the target of five; two muster-point signs repositioned afterward and the headcount procedure found otherwise satisfactory.",
        "Fire drill held at {site} with the camp staff. Hose reel unwound and re-racked, muster list verified name by name, and two blocked exits from the store room cleared on the spot.",
        "PPE issue session at {site}: safety shoes and helmets handed to the new contract gang, sizes recorded, old helmets collected for disposal, and the issue register countersigned by the store keeper.",
        "Evening review meeting at {site}: yesterday's register entries read out in the local language, last week's follow-up items closed one by one, and next week's inspection rota posted on the board.",
        "Spill-kit use training arranged at {site} for the canteen and diesel-store staff; absorbent granules, drain covers and disposal bags demonstrated on the training drum, and every attendee took a turn.",
        "Toolbox talk on ladder discipline held at {site} before the {time} job: three-point contact, footing the ladder, and never carrying tools in hand while climbing — attendance sheet signed by all hands.",
    ], 420),
    ("admin", ["register update", "document control", "muster reconciliation",
               "stock reconciliation", "leave record update", "contractor documentation review",
               "HSE performance summary"], [
        "Register update at {site}: this week's near-miss and observation pages reconciled with the daily diary, page numbering verified and pending signatures collected from the shift in-charge.",
        "Document control round at {site}: revision sheets of the emergency response plan replaced on the notice boards, superseded copies withdrawn, and the master index updated in the HSE folder.",
        "Gate pass and muster reconciliation at {site} for the day shift: visitor badges collected, contractor attendance matched against the agency list, and the night-shift relief confirmed.",
        "Stock reconciliation of the HSE store at {site}: gloves, goggles and ear plugs counted against the ledger, {n} shortage lines raised on the indent and fresh stock requisitioned.",
        "Leave record update at {site}: two hands back from sanctioned leave joined the day shift after the usual briefing, and the duty roster for the week was recopied and posted at the control room.",
        "Contractor documentation review at {site}: agency insurance, workmen compensation cover and medical fitness certificates for the fresh intake checked and filed; one expired fitness card flagged to the agency for renewal.",
        "Monthly HSE performance summary compiled for {site}: register counts, training man-hours, drill log and permit statistics transferred to the standard format and submitted to the area office.",
        "PTW register audit at {site}: closed permits filed month-wise, outstanding cold-work permits followed up with the issuing authority and the register page re-numbered where sheets had been inserted.",
        "Stores issue notes for {site} tallied against the HSE indent: {n} items received against the month's indent and the balance requisitioned from the central store.",
    ], 470),
    ("maintenance", ["preventive maintenance", "vehicle servicing", "valve greasing round",
                     "pump vibration scan", "instrument air dryer service", "wheel nut check"], [
        "Preventive maintenance of the air compressor at {site} completed per schedule: oil and filters changed, belt tension set, unloader checked and the run test taken with gauge readings recorded in the PM card.",
        "Planned servicing of the water bowser at the {site} workshop: filters replaced, brakes adjusted and the hand-brake lever travel brought within spec; vehicle returned to duty after the supervisor signed the job card.",
        "Weekly greasing round on the {site} manifold valves completed with the grease gun; handles moved freely, gland leaks absent, and the valve tags repainted where numbers had faded.",
        "Scheduled vibration and temperature scan of the {site} pumps taken by the rotating equipment engineer; values logged in the trend sheet and the next due date stamped on the equipment card.",
        "Instrument air dryer desiccant change done at {site} during the low-demand window; dew point meter readings recorded before and after, and the changeover logged in the panel book.",
        "Tyre inflation station check and wheel-nut torque verification for the site tippers at {site}: torque marks re-painted and the torque wrench calibration sticker confirmed valid.",
        "Level gauge glass on the {site} water tank cleaned and re-seated during the routine PM; reading cross-checked with the dip tape and the PM card closed by {role}.",
        "Planned filter change on the {site} DG set completed between load transfers: air, lube and fuel filters replaced, leak-off lines blown clear and the unit returned to standby after a clean run.",
    ], 520),
    ("positive", ["good practice noted", "housekeeping appreciation", "yard walk"], [
        "Good practice noted at {site}: {role} stopped to re-seat a wobbly ladder against the pipe rack before the routine lamp change, and had a colleague foot the ladder until the job finished.",
        "Appreciation entry for the {site} housekeeping gang: the compressor deck was found clean and drip-free on an unannounced look, and the used absorbents were already bagged and labelled.",
        "During the yard walk at {site}, the crane operator chalked the load-radius line on the ground before the afternoon pipe lift; the practice has been adopted for all other lifts this week.",
        "{role} at {site} voluntarily replaced two cracked wheel chocks of the diesel pump set with hardwood chocks cut to size and painted yellow, before anyone raised it.",
        "The {site} canteen team introduced colour-coded chopping boards and a daily sink-sanitiser log on their own initiative after last month's hygiene briefing; arrangement verified during today's round.",
        "Night-shift crew at {site} painted the pedestrian walkway stripes up to the substation gate during a lean hour; the marking is now continuous from the office to the change room.",
        "The {site} stores keeper re-labelled every rack bin in the tool crib in Hindi and Assamese alongside English so that new contract hands could return tools without help; noted with appreciation.",
        "During the {site} yard walk, the gang placed warning cones around the fresh oil stain near the loading bay while the absorbent was fetched, keeping the path open on the far side.",
    ], 430),
    ("first_aid", ["first-aid register entry", "minor injury treatment"], [
        "While lifting a drum of thread compound on to the pallet at {site}, a helper's glove caught the drum edge and he got a shallow scratch on the back of his hand. Cleaned with saline and a sterile strip applied from the first-aid box; he resumed duty at once and the entry was made in the first-aid register.",
        "A fitter at {site} brushed against the freshly painted railing while passing and got a smear of paint on his forearm skin, which was mildly irritated. Washed with soap and water at the washroom and he continued the shift normally.",
        "During sample bottle washing at the {site} lab annexe, a laboratory attendant's finger pricked on a chipped bottle rim. Cleaned and a plaster applied from the first-aid box; the chip was cleared and the bottle culled.",
        "A kitchen helper at the {site} camp slipped on the wet verandah step and landed on the seat; examined by the site medic, contusion only, given a cold compress and rested for the remainder of the shift.",
        "While tightening the clamp on the cooling water line at {site}, the fitter's spanner slipped and grazed his knuckle. Washed, antiseptic applied and a bandage put; he completed the job and closed the permit as usual.",
        "Dust from the bagging operation near the {site} silo irritated a packer's eye; he rinsed at the eye-wash station for two minutes, felt fine afterward, and returned to the light duty he was assigned.",
        "While carrying the gas cylinder trolley across the {site} yard, the helper's heel clipped the kerb and he stumbled without falling; checked and cleared by the medic, and the trolley route was re-marked away from the kerb.",
        "A welder at {site} reported mild flash glare from an adjacent arc during the shift; eye drops from the first-aid box gave relief within the hour and he continued with the shade-5 screen corrected for tomorrow.",
    ], 430),
    ("logistics", ["camp logistics", "weather log", "radio check round",
                   "canteen hygiene round", "sample dispatch"], [
        "Water tanker schedule for the {site} camp rearranged after the supply dip yesterday; two extra trips added for the canteen tank and the residents informed at dinner muster.",
        "Weather log entry for {site}: steady drizzle since the previous evening, approach road graded by the dozer in the forenoon and the camp path gravel topped up; movement normal through the day.",
        "Radio check round at {site} completed with all stations reporting clear; one spare battery issued to the pigging team after their handset showed low charge.",
        "Monthly canteen hygiene round at {site} found the kitchen, deep freezer temperature log and the drinking water cooler all in order; the cook house roof patch completed the same afternoon.",
        "Sample dispatch arranged from {site} to the central lab: {n} sample bottles packed in the crate with cushioning, chain-of-custody slips signed and the taxi receipt filed.",
        "Landscaping gang trimmed the hedges along the {site} approach and cleared the storm drain grates ahead of the week's forecast rain; clippings carted to the compost bay inside the campus.",
        "Drinking water quality check at the {site} camp completed with the lab kit; residual chlorine within the specified band at both coolers and the log countersigned by the camp supervisor.",
        "The fortnightly muster board refresh at {site} was completed with the new contract names added, photo cards reprinted for the two fresh hands and the old board archived.",
    ], 320),
]

# ---------------------------------------------------------------------------
# PRECURSOR register (~20%) — genuine barrier-failure near-misses, written
# fresh. Physical mechanisms + barrier-absence language; a slice is
# procedural-only (the model's honest weak slice per the measured probe).
# ---------------------------------------------------------------------------

PREC_LOF = [
    "During pipe handling at {site} during {act}, a single joint slipped off the ramp chocks and rolled towards the catwalk where two helpers were guiding the string. Nobody below had a clear escape; the area had not been cordoned and the tag line was not rigged. Job stopped and re-planned with the barricade in place.",
    "A tong jaw pin disconnected while making up at {site} during {act} and the swinging tong arm passed within an arm's length of {role}, who had stepped inside the swing radius to guide the rubber. The driller stopped the rotation in time; the radius was repainted and the crew briefed after the job.",
    "While hoisting the BOP test stumps at {site}, the load swung as the crane slewed and passed directly over the walkway where {role} was standing. The path was not barricaded and no banksman controlled the lift. Crane stopped, area barricaded and the lift plan re-briefed before resuming.",
    "A hammer wrench slipped from the monkey board during {act} at {site} and fell to the main deck close beside a floorman who was setting the slips below. Tools were not tethered and the deck below had not been cleared. Floor cleared and all hand tools above the floor placed on tethers the same day.",
    "While breaking out drill collars at {site} during {act}, the tong backup arm kicked and the crew standing on the release side had to jump clear. The tong snub line was worn and the area below the swing had not been roped off. Snub line replaced from store and the swing radius taped before the next connection.",
    "Elevator latch at {site} was found half engaged as the stand was picked up during {act}; the stand dropped about a metre before the slips caught. The floorman below had moved under it to clear thread protectors. Latch spring replaced, function tested thrice and the pre-job check sheet amended.",
    "While rolling casing from the V-door ramp at {site}, one joint ran off the ramp boards towards the pipestacker, who jumped aside. Chocks on the ramp had been removed earlier and were not put back after the previous run. Chocks re-fitted and ramp control re-briefed to both shifts.",
    "A bundle of drill pipe lifted by the yard crane at {site} shifted as the sling eye slipped off the hook guard during {act}; two tag-line men were inside the load radius when it shifted. Lift paused, sling re-seated with a shackle and the radius roped before continuing.",
    "The grating panel being lowered at {site} swung on its tag line as the wind gusted and passed close to the head of {role} on the stair landing below. The landing below had not been closed and the tag line was held by one hand only. Panel re-lashed with two strops and the descent path closed for the rest of the job.",
]
PREC_HEIGHT = [
    "While shifting the derrick ladder platform at {site}, a scaffold plank over the landing bay was found unsupported at one end with a painter standing on it. He was called down immediately, the plank re-clamped and the scaffold re-tagged before work resumed.",
    "At {site} during {act}, a roustabout unbuckled his harness to cross behind the water tank on the second landing, leaving the anchorage for about three paces. The scaffold handrail on that side was already removed for the cable pull. He was brought down, the gap barricaded and the anchor point marked with a yellow line.",
    "During handrail replacement on the produced-water tank top at {site}, the crew worked off the tank shell with only one lanyard for two men; the second anchorage eye had not been fitted. Job paused, a drop-through anchor installed and both harnesses clipped independently before continuing.",
    "The mast climbing irons at {site} were in use with one leg of the safety catch bent during {act}; the derrickman reported it midway and came down. The bent catch was replaced from the rig store and the irons load-tested before the next climb.",
    "A scaffold tag at {site} showed the weekly inspection overdue by nine days, yet the painter was working from the third lift for the {act} job. The painter descended, the scaffold re-inspected and re-tagged, and the overdue entries reviewed with the scaffold supervisor.",
    "While closing the tank hatch from the top of the separation vessel at {site}, the crew used a leaned ladder with no footing at the base during {act}. The ladder slid an inch on the wet crown; it was lashed to the rail and the footing nailed before anyone else went up.",
    "During the {act} at {site}, a technician knelt on the tank roof sheet beside a rotten purlin which flexed audibly under his weight. He was moved off, the sheet boarded over and the roof route re-marked from the access ladder to the hatch.",
    "The cages of the {site} personnel basket were found with two rivets sheared during pre-lift checks before the {act}; the basket was stood down, the cage replaced and a load test witnessed before it flew again.",
    "A painter at {site} continued spray work from the third lift after dark with the scaffold platform edge boards missing on the river side; the gap was noticed by the night supervisor and the platform edge was boarded and hand-railed before the next shift.",
]
PREC_ENERGY = [
    "Before the pump bearing change at {site}, the electrician pulled the breaker but the local isolator beside the motor was left in ON and the fuses were not withdrawn. The fitter had already reached toward the coupling when the panel lamp showed live feed; job stopped, isolator opened, fuses withdrawn and the isolation certificate re-issued.",
    "During the {act} at {site}, the crew opened the filter housing believing the line was depressurised; the downstream block valve was found passing and residual pressure escaped through the vent. The line was bled through the drain and both block valves chained before the job was redone.",
    "The {site} workshop gang began grinding a bracket off the skid with the drive-belt guard interlock bypassed by a previous crew; the grinder spun when air was restored without warning. Interlock restored and the bypass link removed and returned to the control room.",
    "While replacing the {site} chemical dosing pump, the crew isolated the discharge but left the suction valve open and the pump foot valve passing; the casing stayed liquid-full and hot. Job paused, suction isolated and locked, and the drain confirmed dry before the casing was opened.",
    "During generator overhaul at {site}, the starting battery was left connected while the crew worked inside the alternator shroud; a dropped spanner across the terminals sparked at the post. Battery disconnected and the terminals covered; the job restarted with the isolation extended.",
    "The {site} heater treat burner was relit by the operator without venting the firebox first; a soft puff came through the sight port as the pilot opened. He closed the pilot, vented the box for the full purge period and relit successfully on the second attempt.",
    "While pulling the {site} centrifugal pump for {act}, the crew found the suction valve hand wheel loose on the stem and the valve still passing; the line drained slowly into the open casing throughout. Line double-blocked and the valve stem repacked before the internals were touched.",
    "The blinding spool at {site} was removed with the line not confirmed zero: the drain valve was choked with scale and the bleed continued slowly while the flange bolts were cracked. Bolts backed off, drain cleared through the pump-out and the spool removed with the residual drained to the closed drain.",
]
PREC_HOTWORK = [
    "Gas cutting of a worn manifold spool at {site} started before the gas detector cleared the line for residual hydrocarbons; the second reading on the wing side drifted above the working limit midway. Cutting stopped, line purged and steamed and the job re-cleared before the torch went back on.",
    "During {act} at {site}, welding sparks showered past the plywood screen onto the drip tray holding oily rags below; a smoulder started and was doused with sand within moments. Screen extended to full deck height, tray emptied and the fire watch posted for the rest of the job.",
    "The {site} welding job on the water injection header proceeded while the fire extinguisher had been carried to the adjacent job and not returned; a spark ember fell into the dry grass below the flange and was stamped out by the helper. Extinguisher restored to the work front and the fire-watch brief repeated.",
    "Hot work on the {site} wash tank internal coil was taken up while the adjacent tank was being filled from the same header; the wind carried a light film of vapour across the dike wall. Job suspended till the fill completed, gas test repeated in the wind shadow and the permit amended with the standby condition.",
    "While cutting the {site} flowline for the {act}, the crew found the upstream blank still sweating oil through a worn gasket; drips fell onto the tarpaulin near the cutting bench. Cut stopped, line flushed and the gasket renewed before cutting resumed with fresh tarpaulin.",
    "The oxy-acetylene set at {site} was used with a leaking hose connection noticed only when the flame pulsed during the {act}; the cylinder valve was closed and the set withdrawn from service. Spare hoses from store were fitted and the leak-tested set returned to service the next day.",
    "Welding on the {site} produced-water caisson walkway began with the flammable-store shade downwind only fifteen metres away and the gas test taken before the wind swung; the detector man called a reading rise at the job front. Job paused, wind shift noted on the permit and the work front shifted to the lee of the skid.",
]
PREC_CONFINED = [
    "The standby man posted at the {site} separator manway for the {act} left his post for about four minutes to fetch water; the entrant inside continued scraping. He was called out on the radio and both came up; the entry re-planned with a relief standby before the cleaning continued.",
    "Before tank cleaning at {site}, the crew opened the bottom manway but skipped the gas test of the mid-height pocket; the portable detector carried inside read elevated at the second level. Entrant withdrew, the tank was vented another hour and the reading repeated before entry.",
    "During the {act} at {site}, the blower duct collapsed away from the manway flange and airflow to the bottom stopped; the entrant noticed the change in air feel and stepped out. Duct re-clamped and a second blower lined up before re-entry.",
    "The {site} pit cleaning crew extended their entry beyond the permit window by about forty minutes without informing the issuer; the register was corrected on discovery and both men accounted safe at the exit log. Permit extension discipline re-briefed to the cleaning gang the same evening.",
    "While sludge pumping at the {site} skimmer pit, the entrant's harness snap hook was found unclipped from the retrieval line when the top man checked mid-entry. Hook reset and the lifeline re-tensioned; the entry continued with the top man counting hooks at each changeover.",
    "The {site} vessel entry for {act} started while the upstream line was still being drained through an open bypass; the level gauge on the vessel showed a creeping rise during the entry. Entry paused, bypass closed and blanked, and the vessel drained and re-tested before the crew went back in.",
    "The log sheet at the {site} degasser tank entry showed the second hourly gas reading missed for the last hour of the job; the reading lapse was discovered at sign-off. The crew was recalled and the permit closed with the lapse recorded and re-briefed at the next TBT.",
]
PREC_DRIVING = [
    "The water bowser reversing into the {site} chemical pad had no spotter for the first two metres; a stores helper stepping out from the drum rack raised his hand and the driver stopped half a metre short. Spotter posted and the reverse alarm checked, found weak and replaced.",
    "During the morning crew change at {site}, a pickup overtook on the inside of the yard bend while the duty van was backing; the two vehicles passed within a hand span near the culvert. Yard speed discipline re-briefed and the backing route coned off for the shift.",
    "The {site} crew van had its rear view mirror cracked and one stop lamp dead when it was assigned for the {act}; the driver reported it at hand-over and the vehicle was swapped. Mirror replaced and the bulb changed before the van returned to the duty roster.",
    "While the {site} dozer pushed cuttings near the drain culvert, a labourer walked behind the track to pick up his glove; the operator saw the shadow in the mirror and stopped. Walk-behind ground rules re-briefed and the culvert approach roped for the remaining push.",
    "The tipper at {site} descended the tank farm ramp with the body raised by a few inches; the driver noticed at the gate hump and lowered it. Nothing fell, and the latch was found worn; it was replaced and the ramp inspection added to the weekly round.",
    "The tanker driver at {site} parked across the emergency gate to take his meal, blocking the fire tender route for about twenty minutes; he was moved on and the no-parking hatching was repainted the same day.",
]
PREC_LIFTING = [
    "The crane lift of the pump skid at {site} began with a cut web sling that had been dye-penetrant rejected last month; the rigger on the load spotted the cut tail during the first hoist and called the lift off. The rejected sling was found still hanging on the crane hook rail, removed and cut up.",
    "During the {act} at {site}, the shackle pin of the spreader worked half out as the load yawed; the banksman paused the lift, the pin re-moused with wire and the shackle replaced outright before the skid landed.",
    "The {site} truck-mounted crane lifted a casing bundle with the boom over the live flowline because the laydown area was waterlogged; a tag-line man stood under the boom throughout. Lift stopped, the bundle re-staged away from the line and the under-boom area taped before restarting.",
    "While lifting the {site} heat exchanger head for {act}, the load tilted when one shackle was found cross-threaded; the banksman steadied it and set it down on the sleepers. The cross-threaded shackle was scrapped and the rigging kit re-inspected piece by piece.",
    "The counterweight matting under the {site} crane had settled after the rain and one outrigger pad floated free during the morning lift. The lift was stopped, mats re-packed with plates and the crane re-levelled before the load was re-hoisted.",
    "The lifting beam of the {site} gantry was used with one shackle half moused and the other missing its split pin during the {act}; the crane captain caught it on the trial hoist. Beam lowered, split pin fitted from store and the trial hoist repeated before the load moved.",
]
PREC_WELLCONTROL = [
    "While pulling the lower packer at {site} during the {act}, the well began to flow lightly with the rams open; the driller closed the annular, stopped the trip and circulated. Full control regained on the chiksan; pit gains were nil and the trip resumed after the flow check.",
    "During the {act} at {site}, a trip tank gain of about {n} barrels was noticed by the derrickman over the last hour; flow check taken and the well shut in. The kick was circulated out on the choke with the rams closed; losses were nil and the well was reported stable afterward.",
    "The {site} BOP ram was found not holding pressure during the weekly function test; pressure fell from the test value within a minute. The ram element was changed out and the function test repeated clean before the drilling programme continued.",
    "While the {act} was on at {site}, the annulus pressure crept up slowly with the pumps staged down; the supervisor noticed the trend on the panel chart. The well was flowed back and the gain checked, and the packer below was found passing; the job was re-planned with a back-pressure valve in string.",
    "The {site} choke line flange showed a slow weep of drilling fluid during the flow check after the {act}; bolts were found less than hand-tight. Line depressurised, gasket renewed, bolts re-torqued in sequence and the flange re-tested before the well was reopened.",
    "During the {act} at {site}, the driller noticed the standpipe pressure oscillating with the pit level drifting; the flow check confirmed the well was slightly live. The annular was closed, the kick circulated and the mud weight raised by the programmed step before resuming.",
]

# Bucket layout: (rule, opener templates, target n, site pool, activity pool).
# Site/activity pools keep the facets semantically coherent — a heater-treat
# burner is never "at the workshop", a trip-tank gain never during a bundle pull.
RIG_SITES = [
    "Workover Rig #3", "Workover Rig #5", "Workover Rig #7", "Drilling Rig OIL-19",
    "Jorajan", "Lakwa", "Dikom", "Borholla", "Kumchai", "Moran GGS-1",
]
PLANT_SITES = [
    "Duliajan GGS-2", "Duliajan GGS-4", "Naharkatiya EPS", "Moran GGS-1",
    "Baghjan EPS", "Kathalguri GCS", "Tank Farm Tengakhat", "Geleky", "Amguri",
]
WORKSHOP_SITES = ["Workshop Duliajan", "Central Store Duliajan", "Tank Farm Tengakhat"]
RIG_ACTS = [
    "pipe handling", "derrick work", "catwalk operations", "rig floor operations",
    "tower loading", "crane lifting", "scaffolding erection", "grinding on pipe rack",
]
HEIGHT_ACTS = [
    "painting at height", "scaffolding erection", "tower loading", "tank cleaning",
    "derrick work", "crane lifting",
]
MAINT_ACTS = [
    "compressor maintenance", "pump bearing change", "manifold valve overhaul",
    "separator internals inspection", "heat exchanger bundle pulling", "pressure testing",
]
HOT_ACTS = [
    "welding on substructure", "gas cutting", "grinding on pipe rack",
    "manifold valve overhaul", "flowline hot tap",
]
CONFINED_ACTS = [
    "vessel entry", "tank cleaning", "sludge pit cleaning", "separator internals inspection",
]
LIFT_ACTS = [
    "crane lifting", "tower loading", "heat exchanger bundle pulling", "pipe handling",
]
WC_ACTS = [
    "pressure testing", "christmas tree valve greasing", "manifold valve overhaul",
    "workover string pull", "wellhead maintenance", "flow check",
]

PREC_BUCKETS = [
    ("line_of_fire", PREC_LOF, 125, RIG_SITES + PLANT_SITES, RIG_ACTS),
    ("working_at_height", PREC_HEIGHT, 115, RIG_SITES + PLANT_SITES, HEIGHT_ACTS),
    ("energy_isolation", PREC_ENERGY, 105, WORKSHOP_SITES + PLANT_SITES + RIG_SITES, MAINT_ACTS),
    ("hot_work", PREC_HOTWORK, 90, WORKSHOP_SITES + PLANT_SITES + RIG_SITES, HOT_ACTS),
    ("confined_space", PREC_CONFINED, 90, PLANT_SITES, CONFINED_ACTS),
    ("driving", PREC_DRIVING, 80, SITES, [
        "vehicle reversing", "crew van movement", "material transport", "tanker offloading",
        "yard shuttle", "waste disposal run",
    ]),
    ("safe_mechanical_lifting", PREC_LIFTING, 90,
     RIG_SITES + WORKSHOP_SITES + PLANT_SITES, LIFT_ACTS),
    ("well_control", PREC_WELLCONTROL, 105,
     ["Workover Rig #3", "Workover Rig #5", "Workover Rig #7", "Drilling Rig OIL-19",
      "Baghjan EPS", "Kathalguri GCS", "Jorajan", "Lakwa"], WC_ACTS),
]

# ---------------------------------------------------------------------------
# Planted Kathalguri GCS cluster — the money-beat hot cell (DG exhaust duct
# confined-space near-misses). B1 scale: 30 rows pre-state + 40 in the ingest
# file, each a HAND-WRITTEN vignette. Measured on this box: two rows sharing
# one sentence construction land 0.98 cosine — slot swaps cannot be separated;
# distinct sentence structures stay below 0.85. The pre-state set and the
# ingest set are DISJOINT vignettes, so the money-beat ingest banners nothing
# against the pre-state cluster (the build QA asserts this). Sizes shrunk from
# the old 88/125 because that design was 76% mutual near-dups (measured).
# ---------------------------------------------------------------------------

PLANT_VIGNETTES = [
    "During the DG exhaust duct entry at Kathalguri GCS, the air line feeding the entrant got pinched under a trolley wheel and flow dropped till he tapped the duct wall for help.",
    "The standby man posted at the duct mouth walked off to shift a ladder, leaving the man inside the exhaust duct without a watcher for four minutes.",
    "Gas testing before the duct entry covered only the manway mouth; the deep pocket past the silencer baffle was never sampled and the detector read high when the crew was halfway in.",
    "Combustion air for the duct cleaning job was still on recirculation from the night test; the fresh-air take-in stayed shut and the entrant reported stale air within minutes.",
    "Halfway through the exhaust-duct desooting the work light failed; the entrant kept scraping in the dark until the standby shouted him out.",
    "A blank on the neighbouring exhaust run was passing at its gasket; duct pressure crept during the entry until the crew felt the cover lift and withdrew.",
    "The harness lifeline of the entrant was hooked to a duct clamp already marked for replacement; the anchor would have pulled free if he had slipped at the duct mouth.",
    "The standby's gas detector was still on the calibration default from last month's check, so its alarm would have sat silent through a real exceedance.",
    "The manway cover dog was only finger-tight; a cough of pressure lifted the cover while the crew was inside and they came out at once.",
    "The entry permit window expired forty minutes before the crew logged out; the lapse surfaced at sign-off and the permit was closed with the overrun recorded.",
    "The retrieval tripod was rigged out of reach of the manway, so the lifeline ran at an angle along the duct shell instead of plumb over the entrant.",
    "The second hourly gas reading of the permit was skipped while the cleaning continued; the gap was discovered when the log was checked at the exit.",
    "Airflow to the far end of the duct stopped when the blower duct slipped off the manway flange; the entrant felt the change and stepped out on his own.",
    "The radio check with the standby was never made at the halfway point of the entry as the permit required; the lapse was caught in the evening review.",
    "A ladder rung inside the duct was found cracked when the entrant descended for his break; the rung was replaced before the next entry.",
    "The duct fan guard was missing its bolt and the fan casing rattled through the entry; the job was paused and the guard refitted.",
    "Water from the wash-down hose pooled at the low end of the duct and crept toward the entrant's footing; he moved out while the drain was opened.",
    "The escape bottle carried by the entrant was out of test date; the entry was paused and a tested set issued from the store.",
    "The standby man doubled as the top-man for the paint crew next door; both roles lapsed for a quarter of an hour before the supervisor noticed.",
    "The duct interior temperature was never logged before the entry although the line had carried hot gas till the previous evening.",
    "The communication plan between the entrant and the standby relied on shouting alone after the duct radio's battery died mid-job.",
    "The cleaning crew extended the entry past the agreed man-hour limit without a fresh permit; the register was corrected when the overrun was noticed.",
    "The bail-out line inside the duct was fouled behind a baffle bracket and would not pay out during the trial pull before the job.",
    "The entrant's headlamp strap was cut and taped; it failed at the far end of the duct and he finished the section by feel.",
    "Spent rag bundles were left inside the duct from the previous shift and the fresh crew stepped on them without a tool-box word about the obstruction.",
    "The blower run-hour meter was disconnected and the ventilation log was filled from estimate rather than reading during the whole duct job.",
    "The rescuer's harness was found still hanging on the tripod hook when the entry began; it was rigged properly only after the issuer walked the set-up again.",
    "Two different cleaning crews signed the same permit for consecutive shifts without the handover walk the permit required.",
    "The duct exit hatch chain was seized with rust and the emergency egress path was tried only after the entry had begun; it took two men to open it.",
    "A spare duct section stored across the manway blocked the stretcher carry path; it was shifted only after the pre-entry walk picked it up.",
    "The oxygen meter was zeroed in fresh air but its pump filter was choked with dust and the readings through the entry lagged badly.",
    "The standby's whistle was left in the control room and the entry ran for an hour with the agreed sound signal unavailable.",
    "Wall scale knocked down by the cleaning piled at the duct elbow and the entrant's air line snagged on the pile while he backed out.",
    "The lighting cable for the duct job was run through standing water at the manway; the electrician re-routed it before the entry went ahead.",
    "The pre-entry briefing skipped the rescue plan walk-through because the same crew had run the job the previous quarter.",
    "The duct drain valve was left cracked open and vapour from the adjacent line drifted into the working pocket during the cleaning.",
    "The entrant's radio was set to the wrong channel and the standby could not raise him for six minutes until the top man climbed down to check.",
    "Duct supports were found with one hanger bolt missing when the job opened; the crew worked under the sagging span until the fitter added a clamp.",
    "The cleaning gang used a solvent drum inside the duct without the permit's chemical addendum being raised for it.",
    "The escape set's cylinder gauge read a quarter full at the pre-entry check; the set was swapped and the gauge needle later found stuck.",
    "The duct's internal ladder platform bolt was sheared and the platform tilted when the entrant stepped on it at the second section.",
    "The standby's log showed no entries for the middle hour of the entry although the permit required ten-minute checks.",
    "A plastic sheet taped over the manway for dust control cut the airflow sharply until the top man noticed the drumming and pulled it off.",
    "The confined-space signboard at the duct mouth had fallen face-down and a passing fitter nearly opened the cover while the crew was inside.",
    "The entrant carried on scraping after his detector's low-battery chirp began; the standby heard the tone and called him out before the cell died.",
    "The winch wire was kinked from the last job and the supervisor stood the retrieval arrangement down until a new wire was rigged.",
    "The duct job ran straight through the midday heat with the second entrant waiting in an unshaded queue at the manway for his turn.",
    "The air-line manifold valves for the duct job were found half-turned from the previous shift; the flow meter read low until they were reset.",
    "The entrant's overalls caught on a baffle edge and tore at the knee as he crawled past the second bend; the burr was filed off after the job.",
    "The duct entry went ahead with one standby covering two manways on adjacent units after the second permit was signed.",
    "The exhaust stack damper was found half closed during the entry; the draft inside changed and the crew stepped out while it was opened fully.",
    "The rescue basket was stored two units away from the duct; it was moved to the manway only after the pre-job audit flagged the distance.",
    "The manway hinge pin worked loose during the entry and the cover dropped on its hinge; nobody was under it and the pin was replaced before reopening.",
    "The permit's isolation list omitted the steam tracing line to the duct shell; the tracing was found warm at the mid-job check and isolated.",
    "The bottom drain of the duct was plugged with sludge and the wash water rose past the marked safe depth before pumping began.",
    "The second gas test of the entry was taken with the detector held at the manway mouth instead of at the working pocket depth as the method sheet required.",
    "The standby man was reading the log sheet with his back to the manway for long stretches; the supervisor repositioned him facing the opening.",
    "The entrant's boot caught on a seized duct damper linkage and he fell against the duct wall inside; the linkage was freed and lubricated afterwards.",
    "The communication whistle agreed in the rescue plan was never issued to the entrant; the point was corrected at the next entry's briefing.",
    "The duct fan was powered from the temporary board without an RCD-tested lead; the electrician re-terminated the supply before the next shift.",
    "The fresh-air take-in was parked downwind of the DG exhaust outlet itself; the smell of exhaust inside the duct was the first sign and the position was changed.",
    "The cleaning crew's drinking water was kept inside the duct run where line heat warmed it well past drinkable during the morning.",
    "The standby arrangement lapsed during the tea break with the entrant still inside; the relief man arrived late and the gap was recorded in the register.",
    "The pre-entry count of tools taken inside was skipped; at sign-out one spanner was unaccounted for until a second sweep of the duct found it.",
    "The duct's flare-side damper was not chained shut as the isolation certificate listed; it was found free to move during the job and chained on the spot.",
    "The entrant's dust mask straps were cut short and he entered without the respirator the method sheet called for at the desooting stage.",
    "The gas detector's sampling tube cracked at the manway fitting and drew ambient air; the true pocket readings were only taken after the tube was replaced.",
    "The permit board at the DG house still showed the previous day's duct entry as open when the new crew arrived for their shift.",
    "The duct job's emergency contact numbers listed the night supervisor who had rotated out two weeks earlier.",
    "The entrant went in with the tripod legs standing on loose gravel; the base shifted when the lifeline loaded and the whole set-up was re-matted.",
    "The sludge pump inside the duct ran dry and overheated; its burnt smell filled the pocket and the crew stepped out till the pump was changed.",
    "The permit required a second entrant for the elbow section; the solo entrant was withdrawn and the pairing restored before the section was cleaned.",
    "The duct internal temperature at the far pocket measured thirty-nine degrees before entry; the job was rescheduled to the early shift with cooler ambient.",
    "The standby's torch died twenty minutes into the night entry and he kept watch by the area floodlight until a spare was fetched from the office.",
    "The manway's captive bolt hung by a thread and the cover sat unbalanced over the opening through the whole first hour of cleaning.",
    "The duct cleaning crew skipped the pre-entry attendance count at the board and the discrepancy showed only at the muster drill next morning.",
    "The lifeline's fall arrester was fitted upside down and would not lock during the trial tug; it was re-rigged and function tested before entry.",
    "The air mover was positioned to blow across the manway instead of into it; the entrant reported no through-draft and it was repositioned.",
    "The permit closed at 15:30 but the final headcount and gas clearance were signed only at 16:10 after the crew had already left the duct area.",
    "The duct mouth barrier tape was down when the standby returned from a break and a labourer had to be stopped from stepping in with tools.",
    "The second-shift crew found the first shift's tools still racked inside the duct with no log entry accounting for them at handover.",
    "The duct job's rescue plan called for a second tripod that was never rigged; the issuer corrected the arrangement before the first entry.",
    "The internal ladder's bottom step was slick with oil from a dripping gland and the entrant slipped on re-entry until it was cleaned and a drip tray set.",
]

# Split: pre-state takes vignettes [0, PLANT_PRE_N), the ingest beat takes
# [PLANT_PRE_N, PLANT_PRE_N + PLANT_INGEST_N), the rest are QA spares that
# replace any rejected row. Disjoint sets keep the money-beat ingest
# banner-free against the pre-state cluster (asserted by the build QA).
PLANT_PRE_N = 30
PLANT_INGEST_N = 40


def _planted_row(rng: random.Random, k: int, dates: list[str]) -> dict:
    """One planted row; k indexes the vignette list. k >= PRE+INGEST draws a
    spare vignette (the QA-reject replacement pool)."""
    idx = (k % len(PLANT_VIGNETTES) if k < PLANT_PRE_N + PLANT_INGEST_N else
           PLANT_PRE_N + PLANT_INGEST_N + (k % (len(PLANT_VIGNETTES) - PLANT_PRE_N - PLANT_INGEST_N)))
    d = rng.choice(dates) if dates else "2026-06-01"
    return {
        "text": PLANT_VIGNETTES[idx].format(date=d),
        "date": d, "site": "Kathalguri GCS", "activity": "DG exhaust duct inspection",
        "contractor": _contractor(rng), "barrier": "confined space entry control",
        "register": "near_miss", "sif_potential": 1,
        "kind": "planted_kathalguri", "origin": "written-novel",
    }

# INGEST-ONLY opener pools — structurally different constructions from the
# seed pools above. Measured: rows sharing a sentence land 0.98 cosine, so the
# live-ingest file MUST not draw from the seed openers or the money-beat batch
# would banner against the pre-state (the very saturation B1 removes).
ING_NEG_OPENERS = {
    "housekeeping": [
        "At {site}, {role} spent the {time} on the {area} clean-up and reported it complete.",
        "{site} housekeeping note, {time}: the {area} was taken up first and finished to standard.",
        "The weekly clean-up at {site} started from the {area} and worked toward the gate.",
        "During the {time} round at {site}, the housekeeping of the {area} was taken up in full.",
        "Housekeeping of the {area} at {site} was completed by {role} before the shift closed.",
    ],
    "inspection": [
        "The periodic check at {site} was walked through at {time} with the checklist item by item.",
        "{role} completed the scheduled check at {site} covering the {area} equipment.",
        "Inspection round at {site}, {time}: the {area} items were verified one by one.",
        "At {site} the routine verification of the {area} was carried out against the checklist.",
        "The scheduled statutory check at {site} was closed out during the {time}.",
    ],
    "training": [
        "A training hour was held at {site} with {n} hands attending from both shifts.",
        "{role} conducted the learning session at {site} around {time}.",
        "The {site} crew gathered for the scheduled session and walked the topic end to end.",
        "Learning session at {site} for {n} attendees; the practical part was demonstrated live.",
    ],
    "admin": [
        "Clerical round at {site} during the {time}: the registers were reconciled page by page.",
        "{role} closed out the paperwork at {site} and filed the outstanding sheets.",
        "The {site} office completed its weekly documentation sweep without any carry-over.",
        "Records at {site} were brought up to date in the {time} window.",
    ],
    "maintenance": [
        "The planned job on the {area} equipment at {site} was taken up at {time} as scheduled.",
        "{role} executed the periodic upkeep of the {site} unit without any deviation.",
        "Maintenance window at {site}, {time}: the machine was taken up and returned to service.",
        "The scheduled upkeep of the {area} set at {site} was closed within the planned window.",
    ],
    "positive": [
        "A good catch was recorded at {site} when {role} fixed the {area} arrangement unprompted.",
        "{role} at {site} went a step beyond the roster during the {time} round.",
        "The {area} team at {site} improved the arrangement on their own initiative.",
        "Initiative noted at {site} during the {time}: the crew upgraded the {area} setup.",
    ],
    "first_aid": [
        "A minor injury entry from {site} at {time}: {role} took a knock and was seen at the first-aid room.",
        "The first-aid room at {site} recorded one dressing during the {time}.",
        "{role} reported to the {site} first-aid point after a small mishap at the {area}.",
        "One dressing case at {site} in the {time}; the hand returned to duty the same shift.",
    ],
    "logistics": [
        "Camp services note from {site} covering the {time}: supplies and transport were normalised.",
        "{role} arranged the camp logistics at {site} during the {time}.",
        "Support services at {site} were re-organised in the {time} window.",
        "The {site} support round at {time} settled the pending camp items.",
    ],
}

# Ingest-only precursor openers — same mechanisms, different constructions.
ING_PREC_OPENERS = {
    "line_of_fire": [
        "At {site} during {act}, {role} had to leap back when the load swung into the path that was never closed off for the job.",
        "{act} at {site}: a tool parted loose overhead and landed inside an uncleared working radius where {role} had been standing a moment earlier.",
        "While {act} was running at {site}, the swing path took {role}'s position because the area below had not been cleared and the line was not tagged.",
        "{role} was brushed by a swinging attachment at {site} during {act}; the exclusion zone had not been roped and the spotter had left the radius.",
    ],
    "working_at_height": [
        "{role} was found working off an untagged lift at {site} during {act}; the tag had lapsed and the platform edge boards were missing on one side.",
        "During {act} at {site}, a hand climbed past the anchor changeover without re-clipping; the gap over the open side was about three paces.",
        "The access route at {site} for {act} crossed an unsheeted roof bay; the flex underfoot was noticed only when a crew member stepped across it.",
        "At {site}, {role} unclipped to reposition during {act} and stayed off the anchor for several paces along a rail-less edge.",
    ],
    "energy_isolation": [
        "At {site} the {act} crew opened up believing the line was dead; the downstream valve was found passing and the vent carried residual pressure.",
        "The {act} at {site} began with one isolation only; the second source was still live and was found by the lamp test, {role} stepping clear in time.",
        "Isolation for the {act} at {site} missed the local isolator; the panel lamp showed feed when {role} reached toward the coupling.",
        "The {act} crew at {site} opened the casing while the suction side was still live through a foot valve; the drain ran hot the whole time.",
    ],
    "hot_work": [
        "Cutting at {site} for the {act} started on a line that still held product; the wing-side reading rose midway and the torch was dropped from service.",
        "During the {act} at {site}, sparks rained past a partial screen onto an oily tray and a smoulder had to be beaten down with sand.",
        "The {act} front at {site} had lost its fire extinguisher to a neighbouring job when an ember dropped into dry grass below the joint.",
        "{role} lit the {act} job at {site} with the adjacent tank on fill; a vapour film crossed the dike on the wind and the permit was stood down.",
    ],
    "confined_space": [
        "The {act} entry at {site} ran with the standby off his post; {role} inside worked alone until the radio call brought both men up.",
        "At {site} the {act} crew skipped the mid-height gas pocket; the detector read elevated at the second level and the entrant withdrew.",
        "The {act} blower at {site} lost its duct clamp and airflow to the bottom stopped; the change in air feel brought the entrant out on his own.",
        "The {act} permit at {site} was overrun by about forty minutes without an extension; the lapse was caught at sign-off and re-briefed.",
    ],
    "driving": [
        "The bowser reversing to the {act} pad at {site} had no spotter for the first metres; {role} flagged it down half a metre short.",
        "During the {act} at {site}, a pickup overtook on the inside of the yard bend while the duty van was backing through the culvert line.",
        "{role} reported the {act} van at {site} with a cracked mirror and a dead stop lamp; the vehicle was swapped before duty.",
        "The dozer pushing near the {act} culvert at {site} had a walker behind the track; the operator caught the shadow in the mirror and stopped.",
    ],
    "safe_mechanical_lifting": [
        "The {act} lift at {site} began on a sling that had been rejected weeks earlier; the rigger caught the cut tail at the first hoist.",
        "During the {act} at {site}, the spreader shackle pin walked half out as the load yawed; the banksman held it and the shackle was scrapped.",
        "The {act} crane at {site} swung its boom across the live line because the laydown was waterlogged; a tag-line man stayed under the boom.",
        "One shackle of the {act} rigging at {site} was cross-threaded; the load yawed, was steadied and set down, and the kit was re-inspected piece by piece.",
    ],
    "well_control": [
        "While the {act} was running at {site}, the driller saw the annular needed; the well was shut in and the kick circulated clean on the choke.",
        "A trip-tank gain at {site} during the {act} was caught by {role}; the flow check was taken and the well controlled on the choke line.",
        "The weekly function test at {site} found the {act} ram not holding; the element was changed out and the test repeated clean.",
        "The annulus pressure crept at {site} with the pumps staged down during the {act}; the packer below was found passing and the plan revised.",
    ],
}


def _planted_rows(rng: random.Random, n: int, start_i: int, dates: list[str]) -> list[dict]:
    rows: list[dict] = []
    for i in range(n):
        k = i + start_i
        row = _planted_row(rng, k, dates)
        # regen walks forward through the spare vignettes so a QA-rejected row
        # is replaced by a genuinely different hand-written text
        row["_regen"] = (lambda kk: lambda r: _planted_row(
            r, PLANT_PRE_N + PLANT_INGEST_N + kk, DATES))(k)
        row["_attempts"] = 1
        rows.append(row)
    return rows
# ---------------------------------------------------------------------------
# Deliberately-memorised subset: 34 OSHA test rows, now restored from the
# raw Final Narrative column, plus 14 already-unmasked synthetic corpus rows.
# ---------------------------------------------------------------------------

VERBATIM_OSHA_SNIPPET = "swing scaffold, preparing to install terracotta tile"


def _normal_text(text: str) -> str:
    return " ".join(text.split())


def _raw_osha_index() -> dict[str, list[dict[str, str]]]:
    from data_pipeline.masking import mask_text

    index: dict[str, list[dict[str, str]]] = {}
    with RAW_OSHA_CSV.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            raw = row.get("Final Narrative") or ""
            key = _normal_text(mask_text(raw))
            index.setdefault(key, []).append(row)
    return index


def _raw_osha_narrative(row: dict[str, str], index: dict[str, list[dict[str, str]]]) -> str:
    matches = index.get(_normal_text(row["text"]), [])
    if len(matches) > 1:
        matches = [source for source in matches
                   if source.get("Employer") == row.get("contractor")]
    if len(matches) != 1:
        raise ValueError(
            f"expected one raw OSHA narrative for {row.get('contractor')!r} / "
            f"{row['date']!r}; found {len(matches)}"
        )
    return matches[0].get("Final Narrative") or ""


def _memorised_rows(rng: random.Random) -> list[dict]:
    rows = list(csv.DictReader(OLD_BULK_CSV.open(encoding="utf-8", newline="")))
    raw_index = _raw_osha_index()
    verbatim = [r for r in rows if VERBATIM_OSHA_SNIPPET in r["text"]]
    osha_pool = [r for r in rows if r["contractor"] and not r["site"]]
    syn_pool = [r for r in rows if r["site"] and r["register"] == "near_miss"]
    rng.shuffle(osha_pool)
    rng.shuffle(syn_pool)
    picked: list[dict] = []
    for r in verbatim:
        picked.append({
            "text": _raw_osha_narrative(r, raw_index), "date": r["date"] or "", "site": "",
            "activity": "", "contractor": "", "barrier": "",
            "register": "memorised_osha", "sif_potential": None,
            "kind": "memorised_osha", "origin": "raw-final-narrative-osha-test-row (demo beat 7)",
        })
    for r in osha_pool[:33]:
        picked.append({
            "text": _raw_osha_narrative(r, raw_index), "date": r["date"] or "", "site": "",
            "activity": "", "contractor": "", "barrier": "",
            "register": "memorised_osha", "sif_potential": None,
            "kind": "memorised_osha", "origin": "raw-final-narrative-osha-test-row",
        })
    for r in syn_pool[:14]:
        picked.append({
            "text": r["text"], "date": rng.choice(DATES), "site": r["site"],
            "activity": r["activity"], "contractor": _contractor(rng), "barrier": r["barrier"],
            "register": "memorised_synthetic", "sif_potential": None,
            "kind": "memorised_synthetic", "origin": "verbatim-training-corpus-row",
        })
    return picked

# ---------------------------------------------------------------------------
# Generation with near-dup QA. Every novel row carries a regen closure so the
# QA pass can regenerate a rejected row with fresh slots until its max cosine
# (vs the 70,398-row corpus index and vs every other novel row) clears.
# ---------------------------------------------------------------------------
import sys as _sys

if str(REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(REPO_ROOT))


def _fmt(t: str, rng: random.Random, site: str) -> str:
    """Fill {slots}; unknown keys fall back to neutral fillers, never KeyError."""
    fill = {
        "site": site, "role": rng.choice(ROLES), "n": rng.choice(SMALL_N),
        "act": rng.choice(PRECURSOR_ACTIVITIES), "time": rng.choice(TIMES),
        "area": rng.choice(AREAS),
        "date": rng.choice(DATES) if DATES else "today",
    }
    out: list[str] = []
    i = 0
    while i < len(t):
        if t[i] == "{":
            j = t.index("}", i)
            out.append(fill.get(t[i + 1:j], "the routine"))
            i = j + 1
        else:
            out.append(t[i]); i += 1
    return "".join(out)


def _regen_factory(kind: str, rule: str, pool: list[str], acts: list[str],
                   is_prec: bool, sites: list[str] | None = None):
    def regen(rng: random.Random) -> dict:
        site = rng.choice(sites or SITES)
        date = rng.choice(DATES)
        act = rng.choice(acts) if is_prec else acts[0]
        text = _fmt(rng.choice(pool), rng, site)
        if not is_prec and rng.random() < 0.9:  # nugget diversifies repeats
            text += " " + _fmt(rng.choice(NUGGETS), rng, site)
        elif is_prec and rng.random() < 0.8:
            text += " " + rng.choice(PREC_NUGGETS)
        return {
            "text": text, "date": date, "site": site, "activity": act,
            "contractor": _contractor(rng), "barrier": rule.replace("_", " ") if is_prec else "",
            "register": "near_miss" if is_prec else "routine",
            "sif_potential": 1 if is_prec else 0,
            "kind": f"precursor_{rule}" if is_prec else kind,
            "origin": "written-novel",
        }
    return regen


def _tag(regen, rng: random.Random, group: str) -> dict:
    row = regen(rng)
    row["_regen"] = regen
    row["_attempts"] = 1
    row["_group"] = group
    return row


def build_rows(rng: random.Random) -> tuple[list[dict], list[dict]]:
    """(pre_candidates, ingest_candidates) — novel rows carry '_regen'."""
    pre: list[dict] = []
    for kind, acts, pool, n in NEG_BUCKETS:
        pre += [_tag(_regen_factory(kind, kind, pool, acts, False), rng, "pre")
                for _ in range(int(n * SURPLUS))]
    for rule, pool, n, psites, pacts in PREC_BUCKETS:
        pre.extend(_tag(_regen_factory(f"precursor_{rule}", rule, pool,
                                       pacts, True, psites), rng, "pre")
                   for _ in range(int(n * SURPLUS)))
    pre.extend(_planted_rows(rng, PLANT_PRE_N, 0, DATES))
    for r in pre:
        r.setdefault("_group", "pre")
    pre.extend(_memorised_rows(rng))

    ingest: list[dict] = []
    for kind, acts, pool, _n in NEG_BUCKETS:
        ingest += [_tag(_regen_factory(kind, kind, ING_NEG_OPENERS[kind], acts,
                                       False), rng, "ingest")
                   for _ in range(43)]
    ingest.extend(_planted_rows(rng, PLANT_INGEST_N, PLANT_PRE_N, DATES))
    for r in ingest:
        r.setdefault("_group", "ingest")
    for rule, pool, _n, psites, pacts in PREC_BUCKETS:
        ingest += [_tag(_regen_factory(f"precursor_{rule}", rule,
                                       ING_PREC_OPENERS[rule], pacts, True,
                                       psites), rng, "ingest")
                   for _ in range(15)]
    return pre, ingest


def _max_cosines(vecs: np.ndarray, base: np.ndarray, chunk: int = 256):
    """Per-row max cosine vs the base corpus index and vs every OTHER row."""
    n = vecs.shape[0]
    base_max = np.zeros(n, dtype=np.float32)
    for b in range(0, n, chunk):
        base_max[b:b + chunk] = (base @ vecs[b:b + chunk].T).max(axis=0)
    mutual = vecs @ vecs.T
    np.fill_diagonal(mutual, -1.0)
    return base_max, mutual.max(axis=1)


def _near_dup_qa(rows: list[dict]) -> tuple[list[dict], dict]:
    """Two targeted gates (NOT a global mutual-cosine gate — rows of one bulk
    POST never see each other in the phase-1 gates, so within-seed similarity
    never banners at build time; the honest 're-paste memory rate' is reported
    instead):
      1. every novel row vs the 70,398-row corpus index (< REJECT_COSINE);
      2. ingest-novel rows vs (base index + surviving seed rows) — the money-
         beat batch must banner nothing against the pre-state.
    Memorised rows are exempt (they must match) but their corpus cosine is
    reported. Regenerates offenders with fresh text; drops after MAX_ATTEMPTS.
    Returns (survivors, report)."""
    from app.embedder import embed_texts

    base = np.load(BASE_INDEX, mmap_mode="r").astype(np.float32)
    seed_rows = [r for r in rows if r.get("origin") == "written-novel" and r["_group"] == "pre"]
    ing_rows = [r for r in rows if r.get("origin") == "written-novel" and r["_group"] == "ingest"]
    memo = [r for r in rows if r.get("origin") != "written-novel"]
    report = {"regenerated": 0, "dropped": 0, "worst_vs_corpus": 0.0,
              "worst_ingest_vs_seed": 0.0, "repaste_rate": 0.0,
              "memo_banner_count": 0, "memo_n": len(memo)}

    def settle(batch: list[dict], pool: np.ndarray | None) -> tuple[list[dict], np.ndarray]:
        """Regen/drop rows of one batch until max cosine vs (base + pool) clears."""
        vecs = embed_texts([r["text"] for r in batch])

        def worst() -> np.ndarray:
            bm = np.zeros(len(vecs), dtype=np.float32)
            for b in range(0, len(vecs), 512):
                bm[b:b + 512] = (base @ vecs[b:b + 512].T).max(axis=0)
            if pool is not None and pool.shape[0]:
                pm = (vecs @ pool.T).max(axis=1)
            else:
                pm = np.zeros(len(vecs), dtype=np.float32)
            return np.maximum(bm, np.maximum(pm, 0.0) if pool is None else pm)

        for _ in range(MAX_ATTEMPTS):
            w = worst()
            bad = np.flatnonzero(w >= REJECT_COSINE)
            if bad.size == 0:
                break
            changed = []
            for i in bad:
                row = batch[i]
                if row.get("_attempts", 0) >= MAX_ATTEMPTS:
                    continue
                fresh = row["_regen"](rng_global)
                fresh["_regen"], fresh["_attempts"] = row["_regen"], row["_attempts"] + 1
                batch[i] = fresh
                changed.append(i)
                report["regenerated"] += 1
            for i in changed:
                vecs[i] = embed_texts([batch[i]["text"]])[0]
            w = worst()
            keep = [i for i in range(len(batch))
                    if not (w[i] >= REJECT_COSINE and batch[i].get("_attempts", 0) >= MAX_ATTEMPTS)]
            report["dropped"] += len(batch) - len(keep)
            batch = [batch[i] for i in keep]
            vecs = vecs[keep]
        w = worst()
        survivors = [r for r, x in zip(batch, w) if x < REJECT_COSINE]
        report["dropped"] += len(batch) - len(survivors)
        vecs = embed_texts([r["text"] for r in survivors]) if survivors else np.zeros((0, 384), np.float32)
        return survivors, vecs

    seed_ok, sv = settle(seed_rows, None)
    if sv.shape[0]:
        report["worst_vs_corpus"] = round(float((base @ sv.T).max()), 4)
        # honest feature metric: re-pasting any seed row would banner off the
        # stored session tier this often (mutual near-twin rate of the register)
        mut = sv @ sv.T
        np.fill_diagonal(mut, -1.0)
        report["repaste_rate"] = round(float((mut.max(axis=1) >= 0.91).mean()), 4)
    ing_ok, iv = settle(ing_rows, sv)
    pool_all = np.concatenate([base, sv], axis=0) if sv.shape[0] else base
    if iv.shape[0]:
        worst_ing = np.maximum((iv @ base.T).max(axis=1),
                               (iv @ sv.T).max(axis=1) if sv.shape[0] else 0.0)
        report["worst_ingest_vs_seed"] = round(float(worst_ing.max()), 4)
    memo = [r for r in rows if r.get("origin") != "written-novel"]
    if memo:
        mvecs = np.stack([embed_texts([r["text"]])[0] for r in memo])
        memo_worst = (base @ mvecs.T).max(axis=0)
        report["memo_banner_count"] = int((memo_worst >= 0.91).sum())
        report["memo_worst"] = round(float(memo_worst.max()), 4)
    return seed_ok + ing_ok, report


TARGETS_PRE = {**{b[0]: b[3] for b in NEG_BUCKETS},
               **{f"precursor_{r}": n for r, _, n, _, _ in PREC_BUCKETS},
               "planted_kathalguri": PLANT_PRE_N}
INGEST_TARGET = 500


def _slice_to_targets(rows: list[dict], targets: dict[str, int]) -> tuple[list[dict], list[str]]:
    """Keep the first `targets[kind]` rows per bucket; report shortfalls."""
    counts: dict[str, int] = {}
    kept: list[dict] = []
    short: list[str] = []
    for r in rows:
        k = r["kind"]
        tgt = targets.get(k)
        if tgt is None:  # memorised rows: keep all
            kept.append(r)
            continue
        c = counts.get(k, 0)
        if c < tgt:
            kept.append(r)
        counts[k] = c + 1
    for k, tgt in targets.items():
        if counts.get(k, 0) < tgt:
            short.append(f"{k}: {counts.get(k, 0)}/{tgt}")
    return kept, short


def _dedup(rows: list[dict]) -> tuple[list[dict], int]:
    seen: set[str] = set()
    out: list[dict] = []
    dups = 0
    for r in rows:
        key = " ".join(r["text"].split())
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        out.append(r)
    return out, dups


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: "" if r.get(k) is None else r.get(k, "")
                        for k in CSV_COLUMNS})


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({k: v for k, v in r.items() if not k.startswith("_")},
                                ensure_ascii=False) + "\n")


def _assert_no_outcome(rows: list[dict]) -> None:
    leaked = [i for i, row in enumerate(rows, 1) if "[OUTCOME]" in row["text"]]
    if leaked:
        raise AssertionError(f"[OUTCOME] present in {len(leaked)} row(s), first rows: {leaked[:5]}")
    print(f"[OUTCOME] assertion: PASS (0/{len(rows)} row texts contain token)")


def main() -> int:
    global DATES, rng_global
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip-qa", action="store_true", help="skip the embedding QA pass")
    args = ap.parse_args()

    DATES = _date_pool()
    rng_global = random.Random(SEED)

    pre, ingest = build_rows(rng_global)
    if not args.skip_qa:
        survivors, report = _near_dup_qa(pre + ingest)
        pre = ([r for r in survivors if r["_group"] == "pre"]
               + [r for r in pre if r.get("origin") != "written-novel"])
        ingest = ([r for r in ingest if r.get("origin") != "written-novel"]
                  + [r for r in survivors if r["_group"] == "ingest"])
    else:
        report = {}

    pre, pre_dups = _dedup(pre)
    pre_seen = {" ".join(r["text"].split()) for r in pre}
    ingest, ing_dups = _dedup(ingest)
    ingest = [r for r in ingest if " ".join(r["text"].split()) not in pre_seen]

    pre_rows, short_pre = _slice_to_targets(pre, TARGETS_PRE)
    ingest_rows, short_ing = _slice_to_targets(ingest, {"planted_kathalguri": PLANT_INGEST_N})
    # trim to exactly the live-ingest target (drop surplus neg/prec from the end)
    n_planted_ing = sum(1 for r in ingest_rows if r["kind"] == "planted_kathalguri")
    while len(ingest_rows) > INGEST_TARGET:
        drop = next((i for i in range(len(ingest_rows) - 1, -1, -1)
                     if ingest_rows[i]["kind"] != "planted_kathalguri"), None)
        if drop is None:
            break
        ingest_rows.pop(drop)
    for r in pre_rows + ingest_rows:
        r.pop("_regen", None)
        r.pop("_attempts", None)
        r.pop("_group", None)

    _assert_no_outcome(pre_rows + ingest_rows)
    _write_jsonl(DEMO_DIR / "demo_seed_v3.jsonl", pre_rows)
    _write_csv(DEMO_DIR / "demo_seed_v3.csv", pre_rows)
    _write_jsonl(DEMO_DIR / "ingest_500_v3.jsonl", ingest_rows)
    _write_csv(DEMO_DIR / "live_ingest_500_v3.csv", ingest_rows)

    n_neg = sum(1 for r in pre_rows if r["sif_potential"] == 0)
    n_prec = sum(1 for r in pre_rows if r["sif_potential"] == 1)
    n_memo = sum(1 for r in pre_rows if r["origin"] != "written-novel")
    print(f"pre rows: {len(pre_rows)} (routine {n_neg}, precursors {n_prec}, memorised {n_memo})")
    print(f"ingest rows: {len(ingest_rows)}")
    print(f"exact-duplicate rows dropped: pre {pre_dups}, ingest {ing_dups}")
    if short_pre:
        print(f"bucket shortfalls (QA drops) PRE: {short_pre}")
    if short_ing:
        print(f"bucket shortfalls (QA drops) INGEST: {short_ing}")
    if report:
        print(f"QA: regenerated {report['regenerated']}, dropped {report['dropped']}")
        print(f"QA worst cosine vs 70,398-row corpus index: {report['worst_vs_corpus']:.4f}")
        print(f"QA worst ingest-vs-seed cosine: {report['worst_ingest_vs_seed']:.4f}")
        print(f"QA re-paste memory rate (seed rows whose top-1 twin >= 0.91): {report['repaste_rate']:.4f}")
        print(f"QA memorised rows matching corpus (>=0.91): {report['memo_banner_count']}/{report['memo_n']}"
              + (f" (worst {report['memo_worst']:.4f})" if "memo_worst" in report else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
