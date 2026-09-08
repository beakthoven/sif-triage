"""Pydantic API contract. These models are the wire format — the real ONNX
classifier must satisfy them exactly when it replaces the mock."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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
    # threshold = a-priori 0.5 fallback; RealOnnxClassifier overwrites the
    # in-scope entries at load with the artifact's per-rule F1-tuned
    # thresholds from metrics.json (post-review SEV2-5).
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
    # Advisory disposition: badge = annotate only, gray = review queue,
    # block = reserved (no gate blocks today; gates never block ingestion).
    action: Literal["badge", "gray", "block"] = "badge"


class ExplanationOut(BaseModel):
    """Human explanation for a prediction. The template is deterministic and
    always present; `reworded` is the optional Ollama rewording (None when
    the LLM is down or its output failed validation — see app/explain.py)."""
    template: str
    reworded: str | None = None
    spans_quoted: list[str] = Field(default_factory=list)
    source: Literal["template", "ollama"] = "template"
    cached: bool = False
    model_version: str = ""


class PredictionOut(BaseModel):
    sif_score: float = Field(ge=0.0, le=1.0)
    rule_probs: dict[str, float]
    well_control: bool
    evidence_spans: list[EvidenceSpan]
    gate_states: list[GateState]
    model_version: str
    # True when the input overflowed seq_len and the sliding-window path ran
    # (max-pooled head scores, best-window spans). False for the mock.
    chunked: bool = False
    # Filled only by POST /classify?explain=1 (never by the classifier itself,
    # never persisted) — None on plain classify calls.
    explanation: ExplanationOut | None = None


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
    # Rows dropped as exact duplicates (whitespace-normalized text hash) —
    # within the batch itself or already stored by an earlier request (SEV2-2).
    skipped_duplicates: int = 0
    # True when this payload was ingested before, byte-identical, and the
    # stored result is being replayed (nothing was re-classified or re-stored).
    idempotent_replay: bool = False


class IngestRequest(BaseModel):
    """One of records / csv must be present. column_mapping overrides the
    built-in alias table: canonical_key -> source column name."""
    records: list[dict[str, Any]] | None = None
    csv: str | None = None
    column_mapping: dict[str, str] | None = None
    source: str = "upload"


class OverrideIn(BaseModel):
    report_id: int
    field: str  # 'sif_label', 'rules', or 'notes' (enforced on writes — see OverrideWrite)
    old_value: str | None = None
    new_value: str
    labeler: str = "hse_reviewer"
    rationale: str | None = None
    source: Literal["override", "blind_gold"] = "override"


# Future-gold vocabulary (SEV2-3): the write endpoint validates against these
# instead of accepting free text. sif_label values match the dashboard's
# confirm / not-SIF decisions; rules values are comma-separated rule keys.
OVERRIDE_FIELDS: tuple[str, ...] = ("sif_label", "rules", "notes")
SIF_LABEL_VALUES: tuple[str, ...] = ("sif_potential", "not_sif_potential")


class OverrideWrite(OverrideIn):
    """Strict write contract for POST /review (SEV2-3): enumerated field +
    per-field value vocabulary. Reads stay lenient (StoredOverride) so rows
    written before this contract remain readable."""
    field: Literal["sif_label", "rules", "notes"]

    @model_validator(mode="after")
    def _check_value_vocabulary(self) -> "OverrideWrite":
        if self.field == "sif_label" and self.new_value not in SIF_LABEL_VALUES:
            raise ValueError(
                f"sif_label new_value must be one of {SIF_LABEL_VALUES}, got {self.new_value!r}"
            )
        if self.field == "rules":
            keys = [k.strip() for k in self.new_value.split(",") if k.strip()]
            valid = set(RULE_KEYS) | set(OUT_OF_SCOPE_RULES)
            unknown = [k for k in keys if k not in valid]
            if not keys or unknown:
                raise ValueError(
                    f"rules new_value must be comma-separated rule keys from {sorted(valid)},"
                    f" got {self.new_value!r}"
                )
        if self.field == "notes" and not self.new_value.strip():
            raise ValueError("notes new_value must be non-empty")
        return self


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
    """Lift-ranked co-occurrence with honest stats (n + Wilson CI).
    kind=site_activity: site×activity cell. kind=activity_barrier:
    activity×barrier cell (site is null). rule = dominant IOGP rule tag.
    Structured facets only — no runtime LLM tagging."""
    activity: str
    n: int
    sif_rate: float
    lift: float
    ci_low: float
    ci_high: float
    site: str | None = None
    barrier: str | None = None
    rule: str | None = None
    kind: str = "site_activity"


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
