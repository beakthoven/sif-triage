"""Pydantic API contract. These models are the wire format — the real ONNX
classifier must satisfy them exactly when it replaces the mock."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# IOGP Life-Saving Rules. 7 learnable (model heads); Work Authorisation (PTW)
# and Bypassing Safety Controls are DECLARED OUT OF SCOPE (<0.1% detectable in
# the corpus — shown in the UI as declared-out-of-scope, never faked).
RULE_KEYS: tuple[str, ...] = (
    "confined_space",
    "driving",
    "energy_isolation",
    "hot_work",
    "line_of_fire",
    "safe_mechanical_lifting",
    "working_at_height",
)

OUT_OF_SCOPE_RULES: tuple[str, ...] = (
    "work_authorisation",      # IOGP rule 8, officially "Work Authorisation"
    "bypassing_safety_controls",
)

RULE_DISPLAY: dict[str, dict[str, Any]] = {
    "confined_space": {"display": "Confined Space", "in_scope": True, "threshold": 0.5},
    "driving": {"display": "Driving", "in_scope": True, "threshold": 0.5},
    "energy_isolation": {"display": "Energy Isolation", "in_scope": True, "threshold": 0.5},
    "hot_work": {"display": "Hot Work", "in_scope": True, "threshold": 0.5},
    "line_of_fire": {"display": "Line of Fire", "in_scope": True, "threshold": 0.5},
    "safe_mechanical_lifting": {"display": "Safe Mechanical Lifting", "in_scope": True, "threshold": 0.5},
    "working_at_height": {"display": "Working at Height", "in_scope": True, "threshold": 0.5},
    "work_authorisation": {
        "display": "Work Authorisation (Permit to Work)",
        "in_scope": False,
        "threshold": None,
    },
    "bypassing_safety_controls": {
        "display": "Bypassing Safety Controls",
        "in_scope": False,
        "threshold": None,
    },
}


class ReportIn(BaseModel):
    text: str = Field(min_length=1)
    date: str | None = None
    site: str | None = None
    activity: str | None = None
    contractor: str | None = None
    source: str = "api"


class EvidenceSpan(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str


class GateState(BaseModel):
    name: str
    triggered: bool
    detail: str = ""


class PredictionOut(BaseModel):
    sif_score: float = Field(ge=0.0, le=1.0)
    rule_probs: dict[str, float]
    well_control: bool
    evidence_spans: list[EvidenceSpan]
    gate_states: list[GateState]
    model_version: str


class StoredReport(BaseModel):
    id: int
    report: ReportIn
    prediction: PredictionOut | None = None
    created_at: str


class IngestError(BaseModel):
    row: int
    error: str


class IngestResult(BaseModel):
    received: int
    accepted: int
    rejected: int
    report_ids: list[int]
    errors: list[IngestError]


class IngestRequest(BaseModel):
    """One of records / csv must be present. column_mapping overrides the
    built-in alias table: canonical_key -> source column name."""
    records: list[dict[str, Any]] | None = None
    csv: str | None = None
    column_mapping: dict[str, str] | None = None
    source: str = "upload"


class OverrideIn(BaseModel):
    report_id: int
    field: str  # "sif_label", a rule key, or "well_control"
    old_value: str | None = None
    new_value: str
    labeler: str = "hse_reviewer"
    rationale: str | None = None
    source: Literal["override", "blind_gold"] = "override"


class StoredOverride(OverrideIn):
    id: int
    created_at: str


class DensityRow(BaseModel):
    key: str
    n_reports: int
    n_flagged: int
    sif_rate: float
    mean_score: float


class PatternRow(BaseModel):
    """Lift-ranked activity x site co-occurrence with honest stats
    (n + Wilson CI). Structured facets only — no runtime LLM tagging."""
    activity: str
    site: str
    n: int
    sif_rate: float
    lift: float
    ci_low: float
    ci_high: float


class RuleInfo(BaseModel):
    key: str
    display: str
    in_scope: bool
    threshold: float | None = None


class HealthOut(BaseModel):
    status: str
    api_version: str
    model_version: str
    classifier: str
    n_reports: int
    n_overrides: int


class MetricsSummary(BaseModel):
    n_reports: int
    n_flagged: int
    flag_rate: float
    mean_score: float
    n_overrides: int
    gate_trigger_counts: dict[str, int]
    model_version: str
    classifier: str
