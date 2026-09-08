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
    "H2S",   # hydrogen sulfide (well-control, label_spec)
    "BOP",   # blowout preventer (well-control, label_spec)
    "WOC",   # wait on cement
    "GGS",   # gas gathering station
    "EPS",   # electrical power station
    "PPE",
    "ESD",   # emergency shutdown
    "PSV",   # pressure safety valve
    "TBT",   # toolbox talk
    "JSA",   # job safety analysis
    "N2",    # nitrogen
    "O2",    # oxygen
    "LEL",   # lower explosive limit
    "WAH",   # work at height
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
    # Near-dup embedding index (MiniLM, artifacts/embeddings/).
    embed_model_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("SIF_EMBED_MODEL_DIR", REPO_ROOT / "artifacts" / "embeddings" / "minilm")
        )
    )
    embed_index_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("SIF_EMBED_INDEX_DIR", REPO_ROOT / "artifacts" / "embeddings")
        )
    )
    host: str = os.environ.get("SIF_HOST", "127.0.0.1")
    port: int = int(os.environ.get("SIF_PORT", "8177"))
    min_text_length: int = 20
    short_codes: tuple[str, ...] = DEFAULT_SHORT_CODES
    # Confidence gray band: scores inside are routed to the review queue.
    gray_band_low: float = 0.40
    gray_band_high: float = 0.60
    # Near-dup banner threshold for the MiniLM cosine index — MEASURED from
    # the embedding curve (artifacts/embeddings/threshold_report.md):
    # max threshold with recall>=0.95 on exact-dup+near-twin pairs (0.9541)
    # and FPR=0 on 500 random distinct pairs; also clears the same-employer
    # template-pair max (0.9065) that 0.905 would not.
    near_dup_threshold: float = 0.91
    embed_dim: int = 384
    # Language gate: non-ASCII character ratio above this -> gray + badge.
    non_ascii_ratio: float = 0.15
    # Long-input info badge: word count above this -> 'chunked' badge.
    long_input_words: int = 120
    model_version: str = "mock-0.1.0"
    api_version: str = "0.1.0"
    # Optional Ollama rewording for explanations (app/explain.py). The
    # deterministic template always ships; SIF_EXPLAIN_LLM=0 disables live
    # LLM attempts (demo-reliability switch).
    ollama_url: str = os.environ.get("SIF_OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.environ.get("SIF_OLLAMA_MODEL", "qwen3:4b")
    explain_timeout_s: float = float(os.environ.get("SIF_EXPLAIN_TIMEOUT", "8"))
    explain_llm: bool = os.environ.get("SIF_EXPLAIN_LLM", "1").lower() not in ("0", "false", "no")
