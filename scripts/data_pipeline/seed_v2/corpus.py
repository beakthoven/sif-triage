"""Corpus of ~70 negative-dominant register-style demo texts + template library.

Categories: housekeeping, inspection, training, admin, and a small
genuine-precursor set for the flag-rate target (~10-20%).

Every string here is hand-authored for the demo and must NOT appear verbatim
in data/*.json (build_demo_seed_v2.py --verify enforces this).
"""
from __future__ import annotations

import random
from typing import Literal

Category = Literal["precursor", "housekeeping", "inspection", "training", "admin"]

TEMPLATES: dict[Category, list[str]] = {
    "precursor": [
        "Scaffold plank at the second landing of unit {unit} was observed with visible cracks; work was halted and area barricaded",
        "Two workers were seen riding a forklift pallet inside the {area} warehouse during shift handover",
        "Gas detector reading {ppm} ppm H2S near the sour-water drain before valve tightening; job stopped pending re-test",
        "Crane hook latch missing during beam shift at laydown yard; lift aborted by supervisor",
        "Live electrical panel found open with exposed bus bars in the {area} substation; no LOTO applied",
        "Worker on the tank roof ignored harness anchoring requirement while walking near the unprotected edge",
        "Welder's colleague sustained flash burn to forearm due to missing fire-watch during hot-work permit job",
        "Chemical splash from caustic line during hose disconnect; operator taken to dispensary with eye irritation",
        "Hand injury reported while clearing jam at the bagging conveyor without stopping the drive first",
        "Confined-space entry at pit No.{n} started before gas test results were recorded on the entry permit",
        "Cable tray fell from height near the switchgear room while two contract staff were pulling cables overhead",
        "Pressure gauge on the air compressor receiver was found reading zero though the line was live",
        "Fallen cylinder caused a crush hazard near the gas cutting station; no securing chain in use",
        "Excavation wall at depth of 6 ft was unsupported near the water pipeline trench",
        "Forklift operator was using a mobile phone while reversing with load near the {area} gate",
    ],
    "housekeeping": [
        "Housekeeping round conducted in the {area} block; water bottles and used gloves cleared from the walkway",
        "Loose cable near the office corridor taped down and route marked with yellow tape as part of daily walkdown",
        "Spent grinding wheels and metal scrap bins in the workshop segregated and removed by the contract party",
        "Dust accumulation on the control-room window sills cleaned; no trip hazard noted",
        "Empty drums near the chemical store re-stacked upright and banded as per weekly housekeeping schedule",
        "Water spillage near the canteen entrance mopped and caution board placed until dry",
        "Tool-box left open at the fitter's bench closed; spanners returned to shadow board",
        "Fire extinguisher inspection tags on the corridor units found current and legible during walkdown",
        "Scrap wooden pallets stacked near the dispatch bay were cleared to make the forklift aisle wider",
        "Loose packing material near the loading ramp collected and binned; walkway restored",
        "Paint tins in the maintenance store re-arranged on the rack with lids tightened",
        "Garden waste near the admin block gate cleared by the horticulture contract staff",
        "Oily rags from the lube store placed in the designated closed metal bin",
        "Cleaning schedule for the changing-room lockers updated and displayed on the notice board",
        "Broken chair at the security cabin replaced with a new one; old one removed",
    ],
    "inspection": [
        "Monthly pressure-vessel inspection completed for the air receiver in the {area} utility block; no defect raised",
        "Leg-of-harness pre-use check done by rigger crew before the day's lifting activity; all tags valid",
        "Routine walkdown of the effluent treatment plant carried out; all valves found in the correct line-up",
        "Third-party certification of the 10-ton chain pulley block verified current with the vendor",
        "Weekly ladder inspection completed for all extension ladders in the {area} store; inspection cards updated",
        "Calibration sticker on the torque wrench used for flange tightening verified within validity",
        "Fire-and-gas detector functional check completed for detector FD-{n}; response time recorded within limits",
        "Earthing continuity check done for the fuel-unloading bay; readings recorded in the register",
        "Monthly review of permit-to-work compliance conducted; 100% closure of the previous week's permits confirmed",
        "Inspection of the portable eyewash station near the acid unloading area done; water quality and flow found satisfactory",
        "Quarterly thermography scan of the LT panel completed; no hotspots above the action threshold",
        "Safety-valve pop-up test on the steam header carried out in presence of the station incharge; set pressure verified",
        "Insulation-resistance test on the {unit} motor completed and recorded in the maintenance log",
        "Rigging hardware (shackles, D-shackles, slings) colour-code inspection done for the month",
        "Breathing-apparatus cylinder pressure and hydro-test validity checked for the rescue team set",
    ],
    "training": [
        "Induction training on permit-to-work conducted for 12 newly-joined contract workers at the {area} training centre",
        "Tool-box talk on manual handling delivered to the packing shift before the day's activity",
        "Fire-extinguisher hands-on drill conducted for the admin block staff; 18 participants",
        "Refresher training on hazard reporting completed for the operations crew of {unit}",
        "First-aid and CPR refresher completed for 6 shift ward boys at the occupational health centre",
        "Confined-space entry awareness session held for the maintenance supervisors",
        "Crane operator competency revalidation completed for the two licensed operators in the {area} yard",
        "Mock drill on chemical-spill response carried out with the emergency response team; debrief held",
        "Behaviour-based safety observation programme kick-off session attended by 22 workmen",
        "E-learning module on electrical safety completed by all instrument technicians this quarter",
        "Scaffolding erection and inspection training organised for the contract scaffolding crew",
        "Defensive-driving training for the heavy-vehicle drivers conducted at the transport yard",
        "Tool-box talk on heat-stress management delivered during the summer shift",
        "Gas-tester competency assessment completed for the four certified testers",
        "Emergency-assembly-point mock muster conducted at {area}; head-count reconciliation matched",
    ],
    "admin": [
        "Revised shift roster for the {area} operations team circulated to all concerned for the coming month",
        "Minutes of the weekly safety committee meeting circulated; action items assigned to respective owners",
        "Statutory register 11 (lifting tools) updated with the latest inspection findings and signatures",
        "Purchase requisition raised for replacement of worn-out hand gloves for the packing section",
        "Attendance reconciliation for the contract workmen completed for the fortnight",
        "Review meeting held on pending audit observations from the internal HSE audit",
        "Notice board updated with the revised emergency contact list for the {area} block",
        "Quarterly HSE performance report prepared and submitted to the plant head",
        "Annual medical check-up schedule communicated to all employees above 45 years",
        "Digital sign-off of the last month's toolbox-talk records completed in the HSE portal",
        "Vendor evaluation for the housekeeping contract completed for the quarter",
        "Courier received for statutory calibration of the radiation survey meter; logged and handed over",
        "Updated fire-load calculation worksheet for the finished-goods warehouse compiled",
        "Budget proposal for replacement of welding screens prepared for management approval",
        "Visitor-entry badges for the audit team arranged with security in-charge",
    ],
}

SLOTS = {
    "unit": ["DTR", " heater", " boiler", " compressors", " well-pad-7", " tank farm", " GCP", " main-flare"],
    "area": ["process", "tank-farm", "workshop", "warehouse", "utility", "admin", "dispatch", "laydown"],
    "ppm": ["11", "14", "18", "22", "26", "31"],
    "n": ["2", "3", "4", "5", "6", "7", "8"],
}


def _fill(template: str, rng: random.Random) -> str:
    out = template
    for key, options in SLOTS.items():
        placeholder = "{" + key + "}"
        if placeholder in out:
            out = out.replace(placeholder, rng.choice(options))
    return out


def build_corpus(seed: int = 20260930) -> list[tuple[str, Category, str, str]]:
    """Return (description, category, area, activity) rows.

    Mix targets ~16% genuine precursors (positive-dominant), ~84% register-style
    negatives, matching the demo DB's desired flag-rate band (<20%).
    """
    rng = random.Random(seed)
    rows: list[tuple[str, Category, str, str]] = []
    area_map = {
        "precursor": "process",
        "housekeeping": "workshop",
        "inspection": "process",
        "training": "admin",
        "admin": "admin",
    }
    activity_map = {
        "precursor": "maintenance / operations",
        "housekeeping": "housekeeping / walkdown",
        "inspection": "inspection / walkdown",
        "training": "training / toolbox-talk",
        "admin": "administrative",
    }
    plan: list[Category] = []
    # ~16 precursors out of ~100
    plan += ["precursor"] * 16
    for cat, count in [
        ("housekeeping", 20),
        ("inspection", 22),
        ("training", 22),
        ("admin", 20),
    ]:
        plan += [cat] * count
    rng.shuffle(plan)
    for cat in plan:
        template = rng.choice(TEMPLATES[cat])
        text = _fill(template, rng)
        rows.append((text, cat, area_map[cat], activity_map[cat]))
    return rows
