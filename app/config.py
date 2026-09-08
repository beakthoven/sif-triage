"""Runtime configuration. Defaults are demo-safe; everything overridable via env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent

# Short safety codes that legitimately appear in very short reports.
# A report consisting of little more than one of these must NOT be eaten
# by the min-length validator (SEV1 register #7).
DEFAULT_SHORT_CODES = (
    "LOTO",  # lock-out/tag-out (energy isolation)
    "PTW",   # permit to work
    "H2S",   # hydrogen sulfide
    "PPE",
    "JSA",   # job safety analysis
    "TBT",   # toolbox talk
    "WAH",   # work at height
    "BOP",   # blowout preventer
    "MOC",   # management of change
    "ERP",   # emergency response plan
)


@dataclass(frozen=True)
class Settings:
    db_path: Path = field(
        default_factory=lambda: Path(os.environ.get("SIF_DB_PATH", APP_DIR / "runtime.db"))
    )
    model_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("SIF_MODEL_PATH", APP_DIR / "artifacts" / "model.onnx")
        )
    )
    host: str = os.environ.get("SIF_HOST", "127.0.0.1")
    port: int = int(os.environ.get("SIF_PORT", "8177"))
    min_text_length: int = 20
    short_codes: tuple[str, ...] = DEFAULT_SHORT_CODES
    # Confidence gray band: scores inside are routed to the review queue.
    gray_band_low: float = 0.40
    gray_band_high: float = 0.60
    # Near-dup banner threshold for the stub n-gram cosine index.
    # TODO(real-index): re-derive from the measured MiniLM embedding curve
    # (ARCHITECTURE runtime section) once MiniLM embeddings ship.
    near_dup_threshold: float = 0.90
    embed_dim: int = 384
    model_version: str = "mock-0.1.0"
    api_version: str = "0.1.0"
