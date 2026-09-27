"""Pydantic API contract. These models are the wire format — the real ONNX
classifier must satisfy them exactly when it replaces the mock."""
from __future__ import annotations

import re
from datetime import date
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
    text: str = Field(min_length=1, max_length=100_000)
    date: str | None = None
    site: str | None = None
    activity: str | None = None
    contractor: str | None = None
    source: str = "api"

    @model_validator(mode="after")
    def _validate_date(self) -> "ReportIn":
        if self.date is not None:
            try:
                if len(self.date) != 10 or date.fromisoformat(self.date).isoformat() != self.date:
                    raise ValueError
            except ValueError as exc:
                raise ValueError("date must be a valid YYYY-MM-DD date") from exc
        return self


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
    # --- self-consistency ensemble (D1 reliability; classifier.py) -----------
    # sif_score is the MEAN over n_variants deterministic surface variants of
    # the outcome-masked text (variant 0 = the report as submitted), so one
    # reviewer phrasing cannot flip the verdict by itself
    # (docs/discovery/60-orchestrator-novel-probe.md Result 3/5).
    # score_spread: population sd of variant_scores — how much the model's
    #   reading depends on surface phrasing.
    # verdict_stability: fraction of variants whose flag verdict agrees with
    #   the mean-score verdict (1.0 = unanimous).
    # Reliability only: a low spread can still be a WRONG consensus — the
    # spread is exposed so gates can gray unstable verdicts, not to assert
    # correctness. All defaulted so predictions stored before this change
    # still parse (storage.py rebuilds PredictionOut from columns).
    score_spread: float = Field(default=0.0, ge=0.0, le=1.0)
    n_variants: int = Field(default=1, ge=1)
    variant_scores: list[float] = Field(default_factory=list)
    verdict_stability: float = Field(default=1.0, ge=0.0, le=1.0)
    # --- server-owned operating point (CLASSIFIER-BAND; classifier.py) -------
    # band: HIGH >= the artifact's tuned flag threshold, MODERATE >= the gray
    # band floor, LOW otherwise — computed by the classifier (band_for) from
    # the SAME rounded score that is reported as sif_score. The threshold and
    # gray-band bounds ride along so the UI can STATE the operating point it
    # was banded against. All defaulted so predictions stored before this
    # change still parse (storage.py rebuilds PredictionOut from columns);
    # band None = "scored under an operating point this response cannot vouch
    # for" — the UI must show that honestly, never invent a band.
    band: Literal["HIGH", "MODERATE", "LOW"] | None = None
    flag_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    gray_band_low: float | None = Field(default=None, ge=0.0, le=1.0)
    gray_band_high: float | None = Field(default=None, ge=0.0, le=1.0)
    # Annotation-only text cues; never affect routing or scoring. Recomputed
    # from report text on classify and stored-report reads, never persisted.
    rule_cue_hits: dict[str, bool] | None = None
    # Filled only by POST /classify?explain=1 (never by the classifier itself,
    # never persisted) — None on plain classify calls.
    explanation: ExplanationOut | None = None
    # Filled only by POST /classify?persist=1 — the real stored report id, so
    # the UI's paste row can attach overrides (POST /review) instead of
    # 404-ing on an optimistic placeholder (audit F4). None on stateless calls
    # and never persisted (the row id already keys the predictions table).
    report_id: int | None = None


class ClusterOut(BaseModel):
    exemplar_id: int
    member_ids: list[int]
    n: int
    reviewed_member_ids: list[int]
    max_cos: float


class ClustersOut(BaseModel):
    threshold: float
    n_scored: int
    n_skipped: int
    dim: int
    n_clusters: int
    n_members: int
    clusters: list[ClusterOut]


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


ActionStatus = Literal["open", "in_progress", "closed"]


class ActionCreate(BaseModel):
    model_config = {"extra": "forbid"}

    report_id: int
    override_id: int
    owner: str = Field(min_length=1)
    due_date: str | None = None
    status: ActionStatus = "open"

    @model_validator(mode="after")
    def _validate_due_date(self) -> "ActionCreate":
        if self.due_date is not None:
            _check_iso_date(self.due_date)
        return self


class ActionPatch(BaseModel):
    model_config = {"extra": "forbid"}

    owner: str | None = Field(default=None, min_length=1)
    due_date: str | None = None
    status: ActionStatus | None = None

    @model_validator(mode="after")
    def _validate_due_date(self) -> "ActionPatch":
        if self.due_date is not None:
            _check_iso_date(self.due_date)
        return self


def _check_iso_date(value: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("due_date must be YYYY-MM-DD")
    date.fromisoformat(value)


class ActionOut(BaseModel):
    id: int
    report_id: int
    override_id: int
    owner: str
    due_date: str | None
    status: ActionStatus
    created_at: str
    updated_at: str


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
    ece: float | None = None
    brier: float | None = None
    calibration_n: int | None = None
    calibration_split: str | None = None
    # Server-owned decision threshold so no client ever hardcodes one again
    # (the analytics slice shipped a stale 0.658 copy after the ensemble
    # re-tune moved the served point to 0.5647).
    flag_threshold: float | None = None
    gray_band_low: float | None = None
    gray_band_high: float | None = None
