"""Runtime configuration. Defaults are demo-safe; everything overridable via
SIF_-prefixed env vars. pydantic-settings does the parsing (A5: replaces the
hand-rolled bool/float os.environ coercion; backend-stack-decision §4)."""
from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SIF_", frozen=True, extra="ignore", populate_by_name=True
    )

    db_path: Path = APP_DIR / "runtime.db"
    model_path: Path = APP_DIR / "artifacts" / "model.onnx"
    # Near-dup embedding index (MiniLM, artifacts/embeddings/).
    embed_model_dir: Path = REPO_ROOT / "artifacts" / "embeddings" / "minilm"
    embed_index_dir: Path = REPO_ROOT / "artifacts" / "embeddings"
    host: str = "127.0.0.1"
    port: int = 8177
    # SQLite busy_timeout (ms) paces each lock acquisition in the write path;
    # app/storage.py _write adds the bounded retry on top.
    db_busy_timeout_ms: int = 5000
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
    # LLM attempts (demo-reliability switch). Default is now 0 (A5 flip): the
    # reworder adds no information by construction, stalls 17.5 s when Ollama
    # is down [measured], and its cache hit rate measured 0% — the template
    # is the product and the LLM is opt-in.
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    # Legacy env name kept via alias (was read directly from os.environ).
    explain_timeout_s: float = Field(
        default=8.0,
        validation_alias=AliasChoices("SIF_EXPLAIN_TIMEOUT", "SIF_EXPLAIN_TIMEOUT_S"),
    )
    explain_llm: bool = False