"""Classifier protocol + deterministic mock + real ONNX runtime.

The mock is CONTRACT-IDENTICAL to the real model: same PredictionOut shape,
same span-validity invariant (text[start:end] == span.text, checked before
every response). Scores are seeded by sha256(text) so the same report always
gets the same prediction — regression tests and the demo rehearsal depend on it.

RealOnnxClassifier runs the ModernBERT INT8/FP32 multi-task artifact
(heads: sif_logit, rule_logits[7], span_logits — see export_gate_report.md).
onnxruntime/tokenizers are imported lazily so the API still boots with zero
ML deps when no artifact is present (falls back to the mock).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Protocol

import numpy as np

from .schemas import RULE_DISPLAY, RULE_KEYS, EvidenceSpan, PredictionOut

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]

# SEV1-1 (post-review): the ONNX rule_logits head emits columns in TRAINING
# order — artifacts/models/masked-v1/train.py RULES, verbatim — NOT the
# alphabetical RULE_KEYS the zip previously used (6/7 rules displayed under
# the wrong name). onnx_classifier_check asserts this tuple against
# train.py's RULES so a retrain with a different order fails loudly.
RULE_HEAD_ORDER: tuple[str, ...] = (
    "line_of_fire", "working_at_height", "driving", "energy_isolation",
    "hot_work", "safe_mechanical_lifting", "confined_space",
)

# Keyword-attribution span fallback (D2): the frozen spec/label_spec.yaml
# keyword_lfs, mirrored from train.py's KEYWORD_LFS (working_at_height is
# code-only by spec -> never anchors), plus '\bloto\b' — the corpus acronym
# the spec only spells out as lock-out ("LOTO not applied" must still
# highlight). Used when the span head yields nothing usable (post-review
# SEV2: span garbage).
_KEYWORD_LFS: dict[str, tuple[str, ...]] = {
    "confined_space": (
        r"\bconfined space\b", r"\bmanhole\b", r"\btank entry\b",
        r"\bvessel entry\b",
        r"\benter(?:ed|ing) (?:the |a )?(?:tank|vessel|silo|vault|pit|bin|hopper)\b",
        r"\binside (?:the |a )?(?:tank|vessel|silo)\b",
    ),
    "energy_isolation": (
        r"\block\s?out\b", r"\btag\s?out\b", r"\blockout\b", r"\btagout\b",
        r"\bloto\b", r"\benergized\b", r"\bde-?energiz", r"\bstored energy\b",
        r"\barc flash\b", r"\bunexpectedly (?:started|activated|energized)",
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
_KEYWORD_LF_RES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE) for pats in _KEYWORD_LFS.values() for p in pats
)

# Post-review SEV2-6: no cap -> one 200k-char paste = 501 windows = 15.9s.
# Inputs are truncated to the first 10k chars (~2.4k tokens, <1s) and the
# long_input gate badges the cap — graceful degrade, never a hang.
MAX_INPUT_CHARS = 10_000

# Span-usability filters (post-review SEV2): drop fragments/punctuation-only
# spans and pure-stopword spans before anything reaches the highlight layer.
_ALPHA_RE = re.compile(r"[A-Za-z]")
_SPAN_STOPWORDS = frozenset(
    "the a an and or of to in on at by was were is it its with without no not "
    "during per this that from for all next be been as are had has have he "
    "she his her their our we they hrs am pm".split()
)

# Keyword anchors the mock uses to place evidence spans. Mirrors the weak-
# supervision anchors the real span head is trained from (DECISION_LOG D2).
_SPAN_ANCHORS: dict[str, tuple[str, ...]] = {
    "energy_isolation": ("loto", "lock-out", "lockout", "isolation", "de-energized", "energized"),
    "hot_work": ("hot work", "welding", "grinding", "grinder", "sparks", "cutting"),
    "working_at_height": ("height", "harness", "scaffold", "ladder", "fall arrest"),
    "confined_space": ("confined space", "vessel entry", "tank entry", "manhole"),
    "line_of_fire": ("line of fire", "dropped object", "suspended load", "struck", "pinch"),
    "safe_mechanical_lifting": ("lifting", "crane", "rigging", "sling", "hoist"),
    "driving": ("driving", "vehicle", "speeding", "seat belt", "journey"),
}

# FROZEN spec/label_spec.yaml wellcontrol_keywords (D23: app list synced to
# the spec — christmas tree / h2s / wellhead / workover etc. were missing;
# mirrored here like gates.py mirrors the masking stems, not imported).
# Bare "kick" deliberately excluded (collides with violence titles).
_WELL_CONTROL_RES = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bblowout\b",
        r"\bblow-out\b",
        r"\bblowout preventer\b",
        r"\bwell control\b",
        r"\bwell-control\b",
        r"\bbop\b",
        r"\bworkover\b",
        r"\bchristmas tree\b",
        r"\bh2s\b",
        r"\bhydrogen sul[fp]hide\b",
        r"\bgas migration\b",
        r"\blost circulation\b",
        r"\bsnubbing\b",
        r"\bcoiled tubing\b",
        r"\bwellhead\b",
    )
)


def has_well_control(text: str) -> bool:
    """Deterministic well-control/barrier tag (ARCHITECTURE: keyword/code
    rules, cheap) — shared by mock and real classifier."""
    return any(p.search(text) for p in _WELL_CONTROL_RES)


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def pseudo_embed(text: str, dim: int = 384) -> np.ndarray:
    """Deterministic hashed word/char-n-gram embedding (L2-normalized).

    Fallback for the real MiniLM embedder (app/embedder.py HashedEmbedder),
    used only when the vendored MiniLM ONNX is absent. The production
    near-dup path embeds with all-MiniLM-L6-v2.
    """
    vec = np.zeros(dim, dtype=np.float32)
    low = text.lower()
    tokens = re.findall(r"[a-z0-9]+", low)
    feats = list(tokens)
    for tok in tokens:
        feats.extend(tok[i : i + 3] for i in range(max(0, len(tok) - 2)))
    for feat in feats:
        h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if h[4] & 1 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


def validate_spans(text: str, spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    """Server-side invariant from the architecture: only spans with
    text[start:end] == span.text may ever leave the API."""
    return [s for s in spans if 0 <= s.start < s.end <= len(text) and text[s.start : s.end] == s.text]


class Classifier(Protocol):
    model_version: str

    def predict(self, text: str) -> PredictionOut:
        ...

    def classify_batch(self, texts: list[str], batch_size: int = 32) -> list[PredictionOut]:
        ...


def flag_threshold(clf: Classifier) -> float:
    """The classifier's SIF flag cutoff on the calibrated score scale.

    RealOnnxClassifier loads it from operating_point_test_tuned in the model
    dir's metrics.json (the D19 test-tuned point; the vacuous val-frozen
    point is never wired to runtime decisions); the mock and any artifact
    without a tuned operating point fall back to 0.5.
    """
    return float(getattr(clf, "sif_flag_threshold", 0.5))


class MockClassifier:
    supports_exact_batch = True  # deterministic pure function of the text

    def __init__(self, model_version: str = "mock-0.1.0") -> None:
        self.model_version = model_version
        self.sif_flag_threshold = 0.5  # a-priori cutoff; no artifact to tune from

    def classify_batch(self, texts: list[str], batch_size: int = 32) -> list[PredictionOut]:
        return [self.predict(t) for t in texts]

    def predict(self, text: str) -> PredictionOut:
        text = text[:MAX_INPUT_CHARS]  # same graceful cap as the real path (SEV2-6)
        rng = np.random.default_rng(_seed(text))
        # Beta(2,5) skews low — realistic triage distribution (~20% flag rate).
        sif_score = float(rng.beta(2.0, 5.0))
        rule_probs = {k: float(rng.beta(1.5, 6.0)) for k in RULE_KEYS}
        # Anchor hits nudge the matching rule up so the mock looks coherent.
        low = text.lower()
        for rule, anchors in _SPAN_ANCHORS.items():
            if any(a in low for a in anchors):
                rule_probs[rule] = min(1.0, rule_probs[rule] + 0.35)
        well_control = has_well_control(text)
        spans = validate_spans(text, self._make_spans(text, rng))
        return PredictionOut(
            sif_score=round(sif_score, 4),
            rule_probs={k: round(v, 4) for k, v in rule_probs.items()},
            well_control=well_control,
            evidence_spans=spans,
            gate_states=[],  # filled in by the route layer after gates run
            model_version=self.model_version,
        )

    def _make_spans(self, text: str, rng: np.random.Generator) -> list[EvidenceSpan]:
        spans: list[EvidenceSpan] = []
        low = text.lower()
        for anchors in _SPAN_ANCHORS.values():
            for anchor in anchors:
                i = low.find(anchor)
                if i >= 0:
                    spans.append(EvidenceSpan(start=i, end=i + len(anchor), text=text[i : i + len(anchor)]))
                    break
        if not spans and text.strip():
            # No anchor: take a deterministic word-window substring.
            words = list(re.finditer(r"\S+", text))
            if words:
                i = int(rng.integers(0, len(words)))
                m = words[i]
                spans.append(EvidenceSpan(start=m.start(), end=m.end(), text=text[m.start() : m.end()]))
        return spans[:5]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


class RealOnnxClassifier:
    """ModernBERT multi-task ONNX artifact (sif / 7-rule / token-span heads).

    Loads only when a real .onnx exists. model_path may be the .onnx file or
    a directory holding the artifacts; quant preference comes from
    SIF_MODEL_QUANT ("int8" default, "fp32" to override). onnxruntime and
    tokenizers are imported lazily so the API runs with zero ML deps until
    the artifact drops in.
    """

    SEQ_LEN = 128            # verified p99=112 tokens on corpus (ARCHITECTURE)
    # Post-review SEV1-2 (positional dead zone): the CLS-pooled head discounts
    # hazards far from the window start — stride 96 left a sustained
    # ~56-92-token dead zone of decisively-wrong scores (min 0.13; order-swap
    # flipped decisions). Stride 64 doubles window-start diversity (a hazard
    # at token N is re-read near-initial at N-64); measured on the reviewer's
    # position scan (app/tests/postreview_fix_check.py): decisive-safe
    # valleys (<0.4) 12 -> 5, worst case 0.13 -> 0.25, and residual
    # sub-threshold scores now cluster at 0.25-0.70 — mostly inside the
    # confidence gray band (routed to review) instead of silently green.
    # The residual positional discount is INHERENT to CLS pooling —
    # documented, accepted; a full fix needs a window-initial second pass.
    STRIDE = 64
    MAX_INPUT_CHARS = MAX_INPUT_CHARS  # module-level cap, shared with gates
    SPAN_THRESHOLD = 0.5     # token-prob cutoff for evidence spans
    TOP_SPANS = 3
    # Ordered candidates per quant preference; first hit wins, then falls
    # back to the other precision — a real model of either kind beats mock.
    _INT8_NAMES = ("sif_multitask_int8.onnx", "model_int8.onnx")
    _FP32_NAMES = ("sif_multitask_fp32.onnx", "model_fp32.onnx")

    def __init__(self, model_path: Path, tokenizer_path: Path | None = None,
                 quant: str | None = None) -> None:
        self.model_path = Path(model_path)
        self._onnx_path = self._resolve_onnx(self.model_path, quant or os.environ.get("SIF_MODEL_QUANT", "int8"))
        self.quant = "int8" if "int8" in self._onnx_path.name else "fp32"
        self._tokenizer_path = self._resolve_tokenizer(self._onnx_path.parent, tokenizer_path)
        self.temperature = self._load_temperature(self._onnx_path.parent)
        self.sif_flag_threshold = self._load_flag_threshold(self._onnx_path.parent, self.temperature)
        self.rule_thresholds = self._load_rule_thresholds(self._onnx_path.parent)
        # Post-review SEV2-5: per-rule F1-tuned thresholds live in the
        # artifact's metrics.json; the app hardcoded 0.5 for every rule. One
        # classifier per process, so updating the shared RULE_DISPLAY table
        # at load is safe and fixes both consumers (/api/rules display and
        # the explanation template's "rules implicated" line).
        for rule, thr in self.rule_thresholds.items():
            if rule in RULE_DISPLAY and RULE_DISPLAY[rule]["in_scope"]:
                RULE_DISPLAY[rule]["threshold"] = thr

        import onnxruntime as ort  # lazy by design
        from tokenizers import Tokenizer  # noqa: F401 — lazy by design

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 8  # measured optimum; 16 is worse (HT contention)
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(
            str(self._onnx_path), opts, providers=["CPUExecutionProvider"])
        self._tokenizer = Tokenizer.from_file(str(self._tokenizer_path))
        self._cls_id = self._tokenizer.token_to_id("[CLS]")
        self._sep_id = self._tokenizer.token_to_id("[SEP]")
        self._pad_id = self._tokenizer.token_to_id("[PAD]")
        self.model_version = f"onnx:{self._onnx_path.parent.name}/{self._onnx_path.name}"
        self.dropped_spans = 0
        # int8 dynamic quantization computes activation scales PER TENSOR:
        # batchmates shift each other's logits (measured Δ≈1.2-1.9 on bulk
        # rows; padding alone Δ≈0.65). fp32 is exactly pad- and batchmate-
        # invariant (measured Δ=0). Batched inference is therefore only
        # exact (== the single-row path) on fp32 — the ingest route checks
        # this flag before using classify_batch (D25).
        self.supports_exact_batch = self.quant == "fp32"

    # ---- artifact resolution -------------------------------------------------

    @classmethod
    def _resolve_onnx(cls, model_path: Path, quant: str) -> Path:
        if model_path.is_file():
            if model_path.suffix == ".onnx":
                return model_path
            raise FileNotFoundError(f"not an ONNX file: {model_path}")
        if model_path.is_dir():
            first, second = (cls._INT8_NAMES, cls._FP32_NAMES) if quant != "fp32" else (cls._FP32_NAMES, cls._INT8_NAMES)
            for name in first + second + ("model.onnx",):
                cand = model_path / name
                if cand.exists():
                    return cand
            candidates = sorted(p for p in model_path.glob("*.onnx")
                                if not p.name.endswith(".onnx.data"))
            if candidates:
                return candidates[0]
        raise FileNotFoundError(f"ONNX artifact not found: {model_path}")

    @staticmethod
    def _resolve_tokenizer(model_dir: Path, tokenizer_path: Path | None) -> Path:
        candidates = [
            tokenizer_path,
            Path(os.environ["SIF_TOKENIZER_PATH"]) if os.environ.get("SIF_TOKENIZER_PATH") else None,
            model_dir / "tokenizer.json",
            model_dir / "tokenizer" / "tokenizer.json",
            REPO_ROOT / "artifacts" / "models" / "tokenizer" / "tokenizer.json",
        ]
        for cand in candidates:
            if cand is not None:
                cand = Path(cand)
                if cand.is_dir():
                    cand = cand / "tokenizer.json"
                if cand.exists():
                    return cand
        raise FileNotFoundError(
            "tokenizer.json not found (checked model dir, SIF_TOKENIZER_PATH, "
            "artifacts/models/tokenizer)")

    @staticmethod
    def _load_temperature(model_dir: Path) -> float:
        """Temperature-scaling hook: read T from metrics.json next to the
        model when present (calibration lands with the trained artifact),
        else 1.0 (identity)."""
        metrics = model_dir / "metrics.json"
        if not metrics.exists():
            return 1.0
        try:
            data = json.loads(metrics.read_text())
            cal = data.get("calibration", {}) if isinstance(data, dict) else {}
            t = data.get("temperature") or data.get("sif_temperature") or cal.get("temperature")
            t = float(t) if t else 1.0
            return t if t > 0 else 1.0
        except (ValueError, OSError, TypeError):
            log.warning("metrics.json unreadable; temperature=1.0")
            return 1.0

    @staticmethod
    def _load_flag_threshold(model_dir: Path, temperature: float) -> float:
        """SIF flag cutoff on the CALIBRATED score scale (what predict emits).

        D19: metrics.json may carry operating_point_test_tuned (re-tuned on
        the derived test split) — prefer it when present. The val-frozen
        sif.operating_point is deliberately NOT a fallback: it is vacuous
        at natural prevalence (flags ~everything, D19), so the fallback is
        the a-priori 0.5. The tuned threshold is stored on the raw-sigmoid
        scale (train.py convention) and mapped through the temperature —
        the identical-decision transform asserted in onnx_score.self_check.
        """
        metrics = model_dir / "metrics.json"
        if not metrics.exists():
            return 0.5
        try:
            data = json.loads(metrics.read_text())
            tuned = data.get("operating_point_test_tuned") if isinstance(data, dict) else None
            if not (isinstance(tuned, dict) and tuned.get("threshold")):
                return 0.5
            raw = float(tuned["threshold"])
            if not 0.0 < raw < 1.0:
                return 0.5
            t = temperature if temperature > 0 else 1.0
            return float(_sigmoid(np.array([np.log(raw / (1.0 - raw)) / t]))[0])
        except (ValueError, OSError, TypeError):
            log.warning("metrics.json operating point unreadable; flag threshold=0.5")
            return 0.5

    @staticmethod
    def _load_rule_thresholds(model_dir: Path) -> dict[str, float]:
        """Per-rule display thresholds from the artifact's metrics.json
        (rules.{rule}.threshold — F1-optimal per rule, raw-sigmoid scale;
        rule probs are not temperature-scaled, so no mapping is needed).
        Missing/unreadable entries keep the a-priori 0.5 in RULE_DISPLAY."""
        metrics = model_dir / "metrics.json"
        if not metrics.exists():
            return {}
        try:
            data = json.loads(metrics.read_text())
            rules = data.get("rules", {}) if isinstance(data, dict) else {}
            out: dict[str, float] = {}
            for rule in RULE_KEYS:
                thr = rules.get(rule, {}).get("threshold") if isinstance(rules.get(rule), dict) else None
                if thr is None:
                    continue
                thr = float(thr)
                if 0.0 < thr < 1.0:
                    out[rule] = thr
            return out
        except (ValueError, OSError, TypeError):
            log.warning("metrics.json rule thresholds unreadable; per-rule threshold=0.5")
            return {}

    # ---- inference -----------------------------------------------------------

    def predict(self, text: str) -> PredictionOut:
        # Single = batch of one, so the interactive and bulk paths can never
        # drift apart (D25).
        return self.classify_batch([text])[0]

    def classify_batch(self, texts: list[str], batch_size: int = 32) -> list[PredictionOut]:
        """Batched inference (D25 bulk-ingest SLA, fp32 only). Every text's
        sliding windows are flattened into shared session.run calls of
        <= batch_size rows, then max-pooled per text — identical semantics
        to predict(). Inputs are capped at MAX_INPUT_CHARS (SEV2-6)."""
        if not texts:
            return []
        capped = [t[: self.MAX_INPUT_CHARS] for t in texts]
        encs = [self._tokenizer.encode(t, add_special_tokens=False) for t in capped]
        flat: list[tuple[int, tuple[int, int], list[int]]] = []  # (text_idx, window, body ids)
        for ti, enc in enumerate(encs):
            for start, end in self._windows(len(enc.ids)):
                flat.append((ti, (start, end), enc.ids[start:end]))
        # D27 (post-review SEV2-1): int8 per-tensor dynamic quantization lets
        # batchmates shift each other's logits (measured Δ up to 0.26 prob
        # WITHIN one chunked predict), so every window of an int8 model runs
        # as its own single-row call — the canonical single-text math. fp32
        # is exactly batch-invariant and keeps the wide batches.
        groups = ([[r] for r in flat] if not self.supports_exact_batch
                  else [flat[off : off + batch_size] for off in range(0, len(flat), batch_size)])
        sif_parts: list[np.ndarray] = []
        rule_parts: list[np.ndarray] = []
        span_rows: list[np.ndarray] = []  # variable token width per chunk — keep row-wise
        for group in groups:
            input_ids, attention_mask = self._pad_rows([r for _, _, r in group])
            sif_l, rule_l, span_l = self._session.run(
                ["sif_logit", "rule_logits", "span_logits"],
                {"input_ids": input_ids, "attention_mask": attention_mask},
            )
            sif_parts.append(sif_l)
            rule_parts.append(rule_l)
            span_rows.extend(span_l)
        sif_logits = np.concatenate(sif_parts, axis=0)
        rule_logits = np.concatenate(rule_parts, axis=0)
        rows_by_text: list[list[int]] = [[] for _ in capped]
        for row_idx, (ti, _, _) in enumerate(flat):
            rows_by_text[ti].append(row_idx)
        outs: list[PredictionOut] = []
        for ti, text in enumerate(capped):
            rows = rows_by_text[ti]
            windows = [flat[r][1] for r in rows]
            # Max-pool per-head scores across windows (logit / T is monotonic
            # in the logit, so pooling probabilities after scaling is
            # equivalent).
            sif_probs = _sigmoid(sif_logits[rows].astype(np.float64) / self.temperature)
            sif_score = float(np.max(sif_probs))
            rule_probs = np.max(_sigmoid(rule_logits[rows].astype(np.float64)), axis=0)
            # Post-review SEV2-7: span candidates merge across ALL windows
            # (not just the argmax-SIF window) before the top-3 cut.
            spans = self._extract_spans(
                text, encs[ti].offsets,
                [(flat[r][1], span_rows[r]) for r in rows])
            outs.append(PredictionOut(
                sif_score=round(sif_score, 4),
                # SEV1-1: rule_logits columns are in TRAINING order
                # (RULE_HEAD_ORDER), not alphabetical RULE_KEYS.
                rule_probs={k: round(float(p), 4) for k, p in zip(RULE_HEAD_ORDER, rule_probs)},
                well_control=has_well_control(text),
                evidence_spans=spans,
                gate_states=[],  # filled in by the route layer after gates run
                model_version=self.model_version,
                chunked=len(windows) > 1,
            ))
        return outs

    def _windows(self, n_body: int) -> list[tuple[int, int]]:
        """(start, end) body-token slices. Single window when the text fits;
        else sliding window seq=128 (126 body + CLS/SEP), stride=64, with the
        tail guaranteed covered."""
        body = self.SEQ_LEN - 2
        if n_body <= body:
            return [(0, n_body)]
        out = [(i, min(i + body, n_body)) for i in range(0, n_body, self.STRIDE)]
        if out[-1][1] < n_body:
            out.append((n_body - body, n_body))
        return out

    def _pad_rows(self, rows: list[list[int]]) -> tuple[np.ndarray, np.ndarray]:
        """Pad a list of body-token-id rows (one sliding window each) into a
        CLS/SEP-wrapped batch with attention mask."""
        width = max(len(r) for r in rows) + 2
        ids = np.full((len(rows), width), self._pad_id, dtype=np.int64)
        mask = np.zeros((len(rows), width), dtype=np.int64)
        for row, body in enumerate(rows):
            n = len(body)
            ids[row, 0] = self._cls_id
            ids[row, 1 : n + 1] = body
            ids[row, n + 1] = self._sep_id
            mask[row, : n + 2] = 1
        return ids, mask

    def _extract_spans(self, text: str, offsets: list[tuple[int, int]],
                       rows: list[tuple[tuple[int, int], np.ndarray]]) -> list[EvidenceSpan]:
        """Span-head candidates from EVERY window -> merge -> usability
        filter -> top-3 by mean prob. Fallback when the head yields nothing
        usable: keyword-attribution over the frozen spec keyword LFs (D2),
        scored by the head's mean token prob over the matched chars.

        Usability filter (post-review SEV2 — the real head's spans were
        punctuation/fragments): drop spans <3 chars, without any alphabetic
        char, or made only of stopwords; strip edge whitespace (ByteLevel
        leading-space artifacts); merge runs separated only by a short
        punctuation/whitespace gap; drop spans contained in a higher-scored
        span. Char offsets come from the offset_mapping, then the invariant
        text[start:end] == span.text is re-checked before anything leaves."""
        char_prob = np.zeros(len(text), dtype=np.float64)
        candidates: list[tuple[float, int, int]] = []  # (mean prob, c0, c1)
        for (start, end), span_logits_row in rows:
            n = end - start
            probs = _sigmoid(span_logits_row[1 : n + 1].astype(np.float64))
            hot: list[int] = []
            for j in range(n):
                o0, o1 = offsets[start + j]
                if o1 <= o0:
                    continue
                char_prob[o0:o1] = np.maximum(char_prob[o0:o1], probs[j])
                if probs[j] > self.SPAN_THRESHOLD:
                    hot.append(j)
            runs: list[list[int]] = []
            for j in hot:
                if runs:
                    prev = runs[-1]
                    gap = text[offsets[start + prev[-1]][1] : offsets[start + j][0]]
                    if j == prev[-1] + 1 or (len(gap) <= 3 and not _ALPHA_RE.search(gap)):
                        prev.append(j)
                        continue
                runs.append([j])
            for run in runs:
                g0, g1 = start + run[0], start + run[-1]
                c0, c1 = offsets[g0][0], offsets[g1][1]
                if 0 <= c0 < c1 <= len(text):
                    candidates.append((float(np.mean(probs[run[0] : run[-1] + 1])), c0, c1))
        usable = self._usable_spans(text, candidates)
        if not usable and len(text.strip()) >= 3:
            kw: list[tuple[float, int, int]] = []
            for rx in _KEYWORD_LF_RES:
                for m in rx.finditer(text):
                    mean = float(char_prob[m.start() : m.end()].mean())
                    kw.append((mean, m.start(), m.end()))
            usable = self._usable_spans(text, kw)
        usable.sort(key=lambda c: (-c[0], c[1]))
        spans: list[EvidenceSpan] = []
        for _, c0, c1 in usable:
            if any(c0 >= s.start and c1 <= s.end for s in spans):
                continue  # contained in a higher-scored span already chosen
            spans.append(EvidenceSpan(start=c0, end=c1, text=text[c0:c1]))
            if len(spans) == self.TOP_SPANS:
                break
        valid = validate_spans(text, spans)
        self.dropped_spans += len(spans) - len(valid)
        if len(valid) < len(spans):
            log.warning("dropped %d invalid span(s); total dropped=%d",
                        len(spans) - len(valid), self.dropped_spans)
        return valid

    @staticmethod
    def _usable_spans(text: str, candidates: list[tuple[float, int, int]]) -> list[tuple[float, int, int]]:
        """Drop fragment/punctuation/stopword-only spans; strip edge
        whitespace with the offsets adjusted to match."""
        out: list[tuple[float, int, int]] = []
        for score, c0, c1 in candidates:
            while c0 < c1 and text[c0].isspace():
                c0 += 1
            while c1 > c0 and text[c1 - 1].isspace():
                c1 -= 1
            frag = text[c0:c1]
            if len(frag) < 3 or not _ALPHA_RE.search(frag):
                continue
            words = re.findall(r"[A-Za-z]+", frag.lower())
            if words and all(w in _SPAN_STOPWORDS for w in words):
                continue
            out.append((score, c0, c1))
        return out


def build_classifier(model_path: Path, mock_version: str) -> Classifier:
    """Prefer a real artifact at SIF_MODEL_PATH (int8 by default; set
    SIF_MODEL_QUANT=fp32 to override). Fall back to the deterministic mock
    only when no artifact/tokenizer exists or the ML deps are absent —
    a corrupt model dir fails loudly, never silently mocks."""
    try:
        return RealOnnxClassifier(model_path)
    except (FileNotFoundError, ImportError):
        return MockClassifier(model_version=mock_version)
