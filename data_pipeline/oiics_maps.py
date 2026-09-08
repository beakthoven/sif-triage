"""Dual era-conditional OIICS prefix maps + SIF-positive definition (label-spec component A).

PS 26165 (OIL India). Implements DECISION_LOG D9 (dual era-conditional maps ONLY —
the 2024 OIICS v2.01 break is a full code RENUMBERING, parent-code rollup is
mathematically impossible) and D15 (SIF-positive definition frozen here).

Eras: v1 = 2015-2023 (OIICS v1 titles), v2 = 2024-2025 (OIICS v2.01 renumbered).
Every map below was derived from, and is verified against,
data/January2015toNovember2025.csv by the __main__ self-check.

stdlib + pandas only.
"""

from __future__ import annotations

import re
import sys

import pandas as pd

CSV_PATH = "data/January2015toNovember2025.csv"

ERA_V1 = "v1"  # 2015-2023
ERA_V2 = "v2"  # 2024-2025 (OIICS v2.01 renumbering)
ERA_V2_START = pd.Timestamp("2024-01-01")

RULES = (
    "line_of_fire",
    "working_at_height",
    "driving",
    "energy_isolation",
    "hot_work",
    "safe_mechanical_lifting",
    "confined_space",
)

# ---------------------------------------------------------------------------
# (1) Dual era-conditional code-prefix -> rule maps.
# Prefix = first 2 chars of the digit-only Event code. Verified renumberings:
#   62x: v1 struck-by falling object -> v2 animal bites        (LoF -> unmapped)
#   43x: v1 fall to lower level      -> v2 fall on same level  (WaH -> unmapped)
#   41x: v1 slip without fall        -> v2 fall to lower level (unmapped -> WaH)
#   64x: v1 caught-in running equip  -> v2 struck-by falling   (LoF -> LoF)
#   65x: v1 collapsing structure     -> v2 running powered eqp (LoF -> LoF)
#   66x: v1 rubbed/abraded           -> v2 caught/wedged       (unmapped -> LoF)
#   44x/45x: v1 jump / PFAS-arrested fall -> eliminated in v2
#   31x/32x: fire <-> explosion SWAPPED across eras (both stay hot_work)
#   22x-25x: transportation sub-codes shifted (all stay driving; 2x is
#            transportation incidents in BOTH eras, so 20-27 is era-stable)
# ---------------------------------------------------------------------------

_CODE_MAP_V1 = {
    "62": "line_of_fire",  # struck by falling/swinging object
    "63": "line_of_fire",  # struck against
    "64": "line_of_fire",  # caught in/compressed by equipment
    "65": "line_of_fire",  # collapsing structure / trench cave-in
    "43": "working_at_height",  # fall to lower level
    "44": "working_at_height",  # jump to lower level (eliminated in v2)
    "45": "working_at_height",  # fall curtailed by PFAS — a height fall occurred
    "20": "driving", "21": "driving", "22": "driving", "23": "driving",
    "24": "driving", "25": "driving", "26": "driving", "27": "driving",
    "31": "hot_work",  # fires / ignition (v1)
    "32": "hot_work",  # explosions (v1)
    "51": "energy_isolation",  # direct/indirect electrical exposure
    "56": "confined_space",  # oxygen deficiency
}

_CODE_MAP_V2 = {
    "63": "line_of_fire",  # collapse, engulfment (v2)
    "64": "line_of_fire",  # struck by falling object (v2)
    "65": "line_of_fire",  # struck by / caught in running powered equipment
    "66": "line_of_fire",  # caught/wedged between, struck by rolling objects
    "41": "working_at_height",  # fall to lower level (v2)
    "20": "driving", "21": "driving", "22": "driving", "23": "driving",
    "24": "driving", "25": "driving", "26": "driving", "27": "driving",
    "31": "hot_work",  # explosions (v2 — swapped with 32 vs v1)
    "32": "hot_work",  # fires / flash fire (v2)
    "51": "energy_isolation",
    "56": "confined_space",  # oxygen displacement / drowning-submersion
}

CODE_RULE_MAPS = {ERA_V1: _CODE_MAP_V1, ERA_V2: _CODE_MAP_V2}

# Prefixes whose RULE ASSIGNMENT changes across eras (mapped<->unmapped or
# rule switch). Era keying is what handles the collision; this frozenset is
# the explicit, asserted register of those collisions.
RENUMBERED_CROSSRULE = frozenset({"41", "43", "44", "45", "62", "66"})
# Prefixes re-titled across eras but landing on the SAME rule.
RENUMBERED_SAME_RULE = frozenset(
    {"22", "23", "24", "25", "31", "32", "63", "64", "65"}
)

# Expected dominant EventTitle per (era, prefix) — regex on the era's top
# value_count. The self-check verifies every claim; if any fails, a
# renumbering has drifted and the maps must not be trusted.
TITLE_ASSERTIONS = {
    (ERA_V1, "43"): r"fall to lower level",
    (ERA_V2, "43"): r"fall on same level",
    (ERA_V1, "41"): r"slip",
    (ERA_V2, "41"): r"fall to lower level",
    (ERA_V1, "44"): r"jump to lower level",
    (ERA_V1, "45"): r"fall arrest",
    (ERA_V1, "62"): r"struck|slipping or swinging object",
    (ERA_V2, "62"): r"animal bite|bite or sting",
    (ERA_V1, "63"): r"struck against",
    (ERA_V2, "63"): r"collapse|engulfment",
    (ERA_V1, "64"): r"caught in|compressed|pinched",
    (ERA_V2, "64"): r"struck by.*falling",
    (ERA_V1, "65"): r"collapsing|cave-in",
    (ERA_V2, "65"): r"running powered equipment",
    (ERA_V1, "66"): r"rubbed|abraded",
    (ERA_V2, "66"): r"caught|wedged|struck by rolling|held or wielded",
    (ERA_V1, "31"): r"ignition|fire",
    (ERA_V2, "31"): r"explosion",
    (ERA_V1, "32"): r"explosion",
    (ERA_V2, "32"): r"fire",
    (ERA_V1, "56"): r"oxygen",
    (ERA_V2, "56"): r"oxygen|drowning|submersion",
    (ERA_V1, "51"): r"electric",
    (ERA_V2, "51"): r"electric",
    (ERA_V2, "42"): r"stepping between levels",  # deliberately unmapped
    (ERA_V1, "42"): r"fall on same level",  # low-energy negative pool, unmapped
}

# ---------------------------------------------------------------------------
# (2) Narrative/SourceTitle keyword labeling functions (multi-hot).
# WaH has no keyword LF (codes carry it; "fell from" is too noisy).
# ---------------------------------------------------------------------------

KEYWORD_LFS = {
    "confined_space": (
        r"\bconfined space\b", r"\bmanhole\b", r"\btank entry\b", r"\bvessel entry\b",
        r"\benter(?:ed|ing) (?:the |a )?(?:tank|vessel|silo|vault|pit|bin|hopper)\b",
        r"\binside (?:the |a )?(?:tank|vessel|silo)\b",
    ),
    "energy_isolation": (
        r"\block\s?out\b", r"\btag\s?out\b", r"\blockout\b", r"\btagout\b",
        r"\benergized\b", r"\bde-?energiz", r"\bstored energy\b", r"\barc flash\b",
        r"\bunexpectedly (?:started|activated|energized)",
    ),
    "hot_work": (
        r"\bhot work\b", r"\bweld", r"\btorch\b", r"\bgrind",
        r"\bcutting (?:torch|metal|steel)", r"\bspark",
    ),
    "safe_mechanical_lifting": (
        r"\bcrane\b", r"\brigging\b", r"\bhoist", r"\bsuspended load\b",
        r"\boverhead load\b", r"\bsling\b", r"\bdropped load\b",
    ),
    "driving": (r"\bfork\s?lift\b", r"\bskid steer\b"),
    "line_of_fire": (
        r"\bstruck by\b", r"\bcaught (?:in|between)\b", r"\bcrushed\b",
        r"\bpinch", r"\bran over\b",
    ),
}
KEYWORD_LFS = {r: tuple(re.compile(p, re.I) for p in pats) for r, pats in KEYWORD_LFS.items()}

# Primary-rule precedence: keyword matches beat code matches; tie order is
# rarest-first so specific rules are not swamped by line_of_fire (48.6%).
PRIMARY_TIE_ORDER = (
    "confined_space",
    "energy_isolation",
    "safe_mechanical_lifting",
    "hot_work",
    "driving",
    "working_at_height",
    "line_of_fire",
)

# ---------------------------------------------------------------------------
# Well-control / barrier tag (Baghjan-class events the 9 personal-safety
# rules do not cover). Deterministic keyword tag on narrative + SourceTitle.
# Bare "kick" deliberately excluded (collides with "kicking" violence titles).
# ---------------------------------------------------------------------------

WELLCONTROL_PATTERNS = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bblowout\b", r"\bblow-out\b", r"\bblowout preventer\b",
        r"\bwell control\b", r"\bwell-control\b", r"\bbop\b",
        r"\bworkover\b", r"\bchristmas tree\b", r"\bh2s\b",
        r"\bhydrogen sul[fp]hide\b", r"\bgas migration\b",
        r"\blost circulation\b", r"\bsnubbing\b", r"\bcoiled tubing\b",
        r"\bwellhead\b",
    )
)

# ---------------------------------------------------------------------------
# (3) SIF-positive definition candidates (era-conditional prefix sets) and
# the FROZEN pick. Measured positive rates on this corpus (see __main__):
#   A_strict  (legacy 5-mechanism, era-translated): 60.40% v1 / 55.57% v2
#   B_middle  (high-energy mechanism codes):        65.52% v1 / 64.21% v2
#   C_broad   (all 7-rule code prefixes):           74.32% v1 / 73.50% v2
#   D_keyword (rule union incl. narrative LFs):     75.87% overall (not a
#             prefix set — not freezable as frozensets, not deterministic
#             from codes alone)
# Cautionary anchors reproduced by the self-check: the legacy v1 prefix set
# applied era-blind gives 55.43% overall but only 30.73% on 2024-25 — that
# silent collapse is why the definition must be era-conditional.
# FROZEN = B_middle: strict high-energy mechanism codes (contact 6x,
# fall-from-height 4x, fire/explosion 31/32, electrical 51), era-consistent
# in meaning (1.3pp era gap vs A's 4.8pp), code-only/deterministic, the
# defensible middle of the 55-76% swing (D15).
# ---------------------------------------------------------------------------

SIF_CANDIDATES = {
    "A_strict": {
        ERA_V1: frozenset({"43", "62", "64", "51", "32"}),
        ERA_V2: frozenset({"41", "64", "65", "51", "31"}),
    },
    "B_middle": {
        ERA_V1: frozenset({"31", "32", "43", "44", "45", "51", "62", "63", "64", "65"}),
        ERA_V2: frozenset({"31", "32", "41", "51", "63", "64", "65", "66"}),
    },
    "C_broad": {
        ERA_V1: frozenset(
            {"31", "32", "43", "44", "45", "51", "56", "62", "63", "64", "65",
             "20", "21", "22", "23", "24", "25", "26", "27"}
        ),
        ERA_V2: frozenset(
            {"31", "32", "41", "51", "56", "63", "64", "65", "66",
             "20", "21", "22", "23", "24", "25", "26", "27"}
        ),
    },
}

# FROZEN SIF-positive definition (D15) — do not edit without re-running the
# self-check and updating spec/drafts/maps_draft.md.
SIF_DEFINITION = "B_middle"
SIF_PREFIXES = SIF_CANDIDATES[SIF_DEFINITION]

# Legacy era-blind set kept ONLY as the self-check's reproduction anchor.
_LEGACY_V1_PREFIXES = frozenset({"62", "64", "43", "51", "32"})


def era_of(event_date: pd.Timestamp) -> str:
    return ERA_V2 if event_date >= ERA_V2_START else ERA_V1


def prefix_of(event_code: str) -> str:
    return str(event_code).strip()[:2]


def code_rule(prefix: str, era: str) -> str | None:
    return CODE_RULE_MAPS[era].get(prefix)


def keyword_rules(text: str) -> frozenset:
    text = text.lower()
    return frozenset(r for r, pats in KEYWORD_LFS.items() if any(p.search(text) for p in pats))


def rules_for(event_code: str, text: str, era: str) -> frozenset:
    """Multi-hot rule set for one row (code rule + keyword LFs)."""
    matched = set(keyword_rules(text))
    r = code_rule(prefix_of(event_code), era)
    if r:
        matched.add(r)
    return frozenset(matched)


def primary_rule(event_code: str, text: str, era: str) -> str | None:
    """Deterministic primary: keyword-matched rules first, rare-first tie order."""
    kw = keyword_rules(text)
    code = code_rule(prefix_of(event_code), era)
    for r in PRIMARY_TIE_ORDER:
        if r in kw:
            return r
    if code:
        return code
    return None


def is_sif(event_code: str, era: str) -> bool:
    return prefix_of(event_code) in SIF_PREFIXES[era]


def is_well_control(text: str) -> bool:
    return any(p.search(text) for p in WELLCONTROL_PATTERNS)


def label_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized labeling: era, prefix, sif, rules (frozenset), primary_rule,
    well_control. Expects raw CSV columns Event, EventTitle, SourceTitle,
    Final Narrative, EventDate (%m/%d/%Y)."""
    out = df.copy()
    out["EventDate"] = pd.to_datetime(out["EventDate"], format="%m/%d/%Y")
    out["era"] = (out["EventDate"] >= ERA_V2_START).map({True: ERA_V2, False: ERA_V1})
    out["oiics_prefix"] = out["Event"].astype(str).str.strip().str[:2]
    text = (out["Final Narrative"].fillna("") + " " + out["SourceTitle"].fillna("")).str.lower()

    out["sif"] = [
        p in SIF_PREFIXES[e] for p, e in zip(out["oiics_prefix"], out["era"])
    ]

    code_hit = {
        r: pd.Series(False, index=out.index) for r in RULES
    }
    for era, mapping in CODE_RULE_MAPS.items():
        em = out["era"] == era
        for prefix, rule in mapping.items():
            code_hit[rule] |= em & (out["oiics_prefix"] == prefix)
    kw_hit = {
        r: text.str.contains("|".join(p.pattern for p in pats), regex=True)
        for r, pats in KEYWORD_LFS.items()
    }

    out["rules"] = [
        frozenset(r for r in RULES if code_hit[r].iat[i] or (r in kw_hit and kw_hit[r].iat[i]))
        for i in range(len(out))
    ]
    kw_any = {r: kw_hit.get(r, pd.Series(False, index=out.index)) for r in PRIMARY_TIE_ORDER}
    primary = pd.Series(None, index=out.index, dtype=object)
    assigned = pd.Series(False, index=out.index)
    for r in PRIMARY_TIE_ORDER:  # keyword matches first, rare-first
        m = kw_any[r] & ~assigned
        primary[m] = r
        assigned |= kw_any[r]
    for r in PRIMARY_TIE_ORDER:  # then code-only matches, same tie order
        m = code_hit[r] & ~assigned
        primary[m] = r
        assigned |= code_hit[r]
    out["primary_rule"] = primary

    out["well_control"] = text.str.contains(
        "|".join(p.pattern for p in WELLCONTROL_PATTERNS), regex=True
    )
    return out


def measure_sif_candidates(df: pd.DataFrame) -> dict:
    """Positive rate per candidate per era. df must have era + oiics_prefix."""
    rates = {}
    for name, maps in SIF_CANDIDATES.items():
        rates[name] = {
            era: float(df.loc[df["era"] == era, "oiics_prefix"].isin(maps[era]).mean())
            for era in (ERA_V1, ERA_V2)
        }
    return rates


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _self_check() -> int:
    df = pd.read_csv(CSV_PATH, dtype=str)
    _check(len(df) == 105_996, f"row count drifted: {len(df)}")
    labeled = label_frame(df)

    # --- era coverage -------------------------------------------------------
    eras = set(labeled["era"].unique())
    _check(eras == {ERA_V1, ERA_V2}, f"both eras must be present, got {eras}")
    n_v1 = int((labeled["era"] == ERA_V1).sum())
    n_v2 = int((labeled["era"] == ERA_V2).sum())
    _check((n_v1, n_v2) == (88_250, 17_746), f"era sizes drifted: {n_v1}/{n_v2}")

    # --- map sanity: no intra-era prefix collision, no stale codes ----------
    for era, mapping in CODE_RULE_MAPS.items():
        _check(len(mapping) == len(set(mapping)), f"{era}: duplicate prefix keys")
        _check(set(mapping.values()) <= set(RULES), f"{era}: unknown rule in map")
        data_prefixes = set(labeled.loc[labeled["era"] == era, "oiics_prefix"].unique())
        stale = set(mapping) - data_prefixes
        _check(not stale, f"{era}: mapped prefixes absent from data: {stale}")

    # --- cross-era collision register --------------------------------------
    # Every prefix whose rule assignment (incl. mapped<->unmapped) differs
    # across eras must be in the explicitly documented renumbered register.
    all_prefixes = sorted(set(labeled["oiics_prefix"].unique()))
    crossrule = set()
    for p in all_prefixes:
        if _CODE_MAP_V1.get(p) != _CODE_MAP_V2.get(p):
            crossrule.add(p)
    _check(
        crossrule <= RENUMBERED_CROSSRULE,
        f"undocumented cross-era rule collision: {crossrule - RENUMBERED_CROSSRULE}",
    )
    # Register self-consistency: same-rule re-titles must be same-rule.
    for p in RENUMBERED_SAME_RULE:
        _check(
            _CODE_MAP_V1.get(p) is not None and _CODE_MAP_V1.get(p) == _CODE_MAP_V2.get(p),
            f"RENUMBERED_SAME_RULE member {p} is not same-rule across eras",
        )
    # Transportation family: 2x must be transportation incidents in BOTH eras
    # (sub-codes shifted, family did not — this is what makes 20-27 era-stable).
    transport_title = re.compile(
        r"vehicle|aircraft|rail|roadway|transport|pedal cycle|parachut|animal", re.I
    )
    for p in {"20", "21", "22", "23", "24", "25", "26", "27"}:
        for era in (ERA_V1, ERA_V2):
            sub = labeled[(labeled["era"] == era) & (labeled["oiics_prefix"] == p)]
            _check(not sub.empty, f"{era} {p}x: no rows")
            top_title = sub["EventTitle"].str.strip().value_counts().index[0]
            _check(
                transport_title.search(top_title),
                f"{era} {p}x left transportation family: {top_title!r}",
            )

    # --- verify every prefix->title claim against value_counts --------------
    for (era, prefix), pattern in TITLE_ASSERTIONS.items():
        sub = labeled[(labeled["era"] == era) & (labeled["oiics_prefix"] == prefix)]
        if era == ERA_V2 and prefix in {"44", "45"}:
            _check(sub.empty, f"v2 {prefix}x should be eliminated, found {len(sub)}")
            continue
        _check(not sub.empty, f"{era} {prefix}x: no rows to verify title")
        top_title = sub["EventTitle"].str.strip().value_counts().index[0]
        _check(
            re.search(pattern, top_title, re.I),
            f"{era} {prefix}x title drifted: top={top_title!r}, expected /{pattern}/",
        )

    # --- SIF candidates + frozen definition ---------------------------------
    rates = measure_sif_candidates(labeled)
    print("SIF-positive candidates (positive rate per era):")
    for name, r in rates.items():
        print(f"  {name:9s} v1={r[ERA_V1] * 100:5.2f}%  v2={r[ERA_V2] * 100:5.2f}%")
    # reproduction anchors (phase-0 measurements)
    legacy_overall = float(labeled["oiics_prefix"].isin(_LEGACY_V1_PREFIXES).mean())
    legacy_v2 = float(
        labeled.loc[labeled["era"] == ERA_V2, "oiics_prefix"].isin(_LEGACY_V1_PREFIXES).mean()
    )
    print(f"  legacy era-blind v1-set: overall={legacy_overall * 100:.2f}%  v2-only={legacy_v2 * 100:.2f}%")
    _check(abs(legacy_overall - 0.5543) < 0.005, "legacy 55.4% anchor not reproduced")
    _check(abs(legacy_v2 - 0.3073) < 0.005, "legacy v2 30.7% degradation anchor not reproduced")
    _check(abs(rates["B_middle"][ERA_V1] - 0.6552) < 0.005, "B v1 rate drifted")
    _check(abs(rates["B_middle"][ERA_V2] - 0.6421) < 0.005, "B v2 rate drifted")
    # era-consistency argument: B's era gap must stay small and beat A's
    gaps = {n: abs(r[ERA_V1] - r[ERA_V2]) for n, r in rates.items()}
    _check(gaps["B_middle"] < 0.02, f"B era gap too wide: {gaps['B_middle']:.4f}")
    _check(gaps["B_middle"] < gaps["A_strict"], f"B no longer beats A on era-consistency: {gaps}")

    _check(isinstance(SIF_PREFIXES[ERA_V1], frozenset) and isinstance(SIF_PREFIXES[ERA_V2], frozenset),
           "SIF_PREFIXES must be frozen frozensets")
    _check(SIF_PREFIXES == SIF_CANDIDATES[SIF_DEFINITION], "frozen set != declared definition")
    high_energy = {"line_of_fire", "working_at_height", "hot_work", "energy_isolation"}
    for era in (ERA_V1, ERA_V2):
        _check(
            all(CODE_RULE_MAPS[era].get(p) in high_energy for p in SIF_PREFIXES[era]),
            f"{era}: SIF prefix outside high-energy mechanism rules",
        )

    # --- label distribution --------------------------------------------------
    print("\nSIF label (frozen B_middle):")
    for era in (ERA_V1, ERA_V2):
        e = labeled["era"] == era
        print(f"  {era}: positive={labeled.loc[e, 'sif'].mean() * 100:5.2f}%  "
              f"n={int(labeled.loc[e, 'sif'].sum())}/{int(e.sum())}")
    print(f"  overall: positive={labeled['sif'].mean() * 100:.2f}%  n={int(labeled['sif'].sum())}")

    print("\nRule distribution (multi-hot):")
    for era in (ERA_V1, ERA_V2, "all"):
        e = labeled["era"] == era if era != "all" else pd.Series(True, index=labeled.index)
        row = {}
        for r in RULES:
            row[r] = float(labeled.loc[e, "rules"].apply(lambda s: r in s).mean() * 100)
        unmatched = float(labeled.loc[e, "rules"].apply(len).eq(0).mean() * 100)
        multi = float(labeled.loc[e, "rules"].apply(len).ge(2).mean() * 100)
        print(f"  {era:3s} " + " ".join(f"{r}={v:5.2f}%" for r, v in row.items())
              + f"  unmatched={unmatched:5.2f}%  multi-rule={multi:5.2f}%")

    _check(labeled["rules"].apply(lambda s: s <= set(RULES)).all(), "rule outside RULES")
    prim = labeled["primary_rule"]
    _check((prim.isna() == labeled["rules"].eq(frozenset())).all(),
           "primary_rule null iff no rules matched")
    _check(prim.dropna().isin(RULES).all(), "primary_rule outside RULES")

    wc = labeled["well_control"]
    print(f"\nWell-control/barrier tag: n={int(wc.sum())} ({wc.mean() * 100:.3f}%)  "
          f"v1={int((wc & (labeled['era'] == ERA_V1)).sum())} v2={int((wc & (labeled['era'] == ERA_V2)).sum())}")
    _check(wc.sum() > 100, "well-control tag suspiciously rare — patterns broken?")

    print("\nSELF-CHECK PASSED: dual era maps verified against data, no unhandled "
          "prefix collision, SIF definition frozen at B_middle.")
    return 0


if __name__ == "__main__":
    sys.exit(_self_check())
