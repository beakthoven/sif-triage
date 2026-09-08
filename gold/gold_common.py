"""Shared constants for the gold-set tooling (sampler, labeler app, export).

RULES mirrors data_pipeline/oiics_maps.RULES exactly. oiics_maps is not
imported here because it requires pandas; the gold toolchain is pure stdlib
so it runs identically under system python3 and .venv. sample_gold.py's
self-check asserts parity against oiics_maps when pandas is available.
"""

RULES = (
    "line_of_fire",
    "working_at_height",
    "driving",
    "energy_isolation",
    "hot_work",
    "safe_mechanical_lifting",
    "confined_space",
)

# Human-facing names, IOGP Report 459 Life-Saving Rules style.
RULE_TITLES = {
    "line_of_fire": "Line of Fire",
    "working_at_height": "Working at Height",
    "driving": "Driving",
    "energy_isolation": "Energy Isolation",
    "hot_work": "Hot Work",
    "safe_mechanical_lifting": "Safe Mechanical Lifting",
    "confined_space": "Confined Space",
}

LABELS = ("sif", "non_sif", "unsure")

LABELER_IDS = ("labeler_a", "labeler_b", "labeler_c", "labeler_d")

SEED = 42
