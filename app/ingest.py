"""CSV/JSON ingestion with alias-based column mapping + pydantic validation.

One canonical mapping + alias dict (fullstack-architect §3): narrative /
description / report text variants -> text; date/site/activity/contractor ->
optional, NULL when absent. No arbitrary-mapping UI.
"""
from __future__ import annotations

import csv
import io
import json as jsonlib
from typing import Any

from pydantic import ValidationError

from .schemas import IngestError, IngestResult, ReportIn

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "text": ("text", "narrative", "description", "report", "incident_description",
             "details", "observation", "body"),
    "date": ("date", "report_date", "incident_date", "event_date"),
    "site": ("site", "location", "field", "installation", "plant"),
    "activity": ("activity", "task", "operation", "work_activity"),
    "contractor": ("contractor", "company", "employer", "vendor"),
}


def map_columns(row: dict[str, Any], override: dict[str, str] | None = None) -> dict[str, Any]:
    """Map a raw record to canonical ReportIn fields.

    override (from the request's column_mapping) wins over the alias table.
    Unknown columns are ignored; missing optional fields become None.
    """
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    out: dict[str, Any] = {}
    for canon, aliases in COLUMN_ALIASES.items():
        value = None
        if override and canon in override and override[canon] in row:
            value = row[override[canon]]
        else:
            for alias in aliases:
                if alias in lowered:
                    value = lowered[alias]
                    break
        if isinstance(value, str):
            value = value.strip() or None
        out[canon] = value
    return out


def parse_csv(content: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(content))
    return [dict(r) for r in reader]


def parse_records(records: list[dict[str, Any]] | None = None, csv_text: str | None = None) -> list[dict[str, Any]]:
    if records is not None:
        return records
    if csv_text is not None:
        return parse_csv(csv_text)
    raise ValueError("one of 'records' or 'csv' must be provided")


def validate_rows(
    raw_rows: list[dict[str, Any]],
    source: str,
    column_mapping: dict[str, str] | None = None,
) -> tuple[list[ReportIn], list[IngestError]]:
    accepted: list[ReportIn] = []
    errors: list[IngestError] = []
    for i, raw in enumerate(raw_rows):
        try:
            mapped = map_columns(raw, column_mapping)
            report = ReportIn(**mapped, source=source)
            if not report.text or not report.text.strip():
                raise ValueError("missing text column (aliases: " + ", ".join(COLUMN_ALIASES["text"]) + ")")
            accepted.append(report)
        except (ValidationError, ValueError) as exc:
            msg = "; ".join(
                f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg')}"
                for e in (exc.errors() if isinstance(exc, ValidationError) else [{"loc": ["row"], "msg": str(exc)}])
            )
            errors.append(IngestError(row=i, error=msg))
    return accepted, errors


def dumps_jsonl(rows: list[dict[str, Any]]) -> str:
    return "\n".join(jsonlib.dumps(r) for r in rows)
