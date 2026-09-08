"""Batched ONNX scorer for the SIF multi-task artifacts (no torch/HF needed).

Replicates the training-time eval path (artifacts/models/*-v1/train.py
build_features + collate): tokenizers-lib encode with special tokens,
truncation to 128 total tokens, pad to each batch's own max length.

Decision semantics (load-bearing): the frozen operating point in
thresholds.json was tuned on RAW sigmoid probabilities
(train.py evaluate_arrays: p = sigmoid(logit); operating_point(y, p)).
The runtime displays the calibrated score sigmoid(logit / T). Applying the
frozen threshold to calibrated scores via the monotonic map
thr_cal = sigmoid(logit(thr) / T) is the IDENTICAL decision; self_check()
asserts this. Temperature here comes from thresholds.json (same value as
metrics.json).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
MODELS = REPO / "artifacts" / "models"
SEQ_LEN = 128  # ARCHITECTURE: p99=112 tokens on corpus
RULES = ["line_of_fire", "working_at_height", "driving", "energy_isolation",
         "hot_work", "safe_mechanical_lifting", "confined_space"]


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def logit(p):
    return math.log(p / (1.0 - p))


class Scorer:
    """One ONNX session (int8 default) + the dir's tokenizer/thresholds."""

    def __init__(self, model_dir: Path, quant: str = "int8", threads: int = 8):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.model_dir = Path(model_dir)
        self.quant = quant
        self.onnx_path = self.model_dir / f"sif_multitask_{quant}.onnx"
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(self.onnx_path), opts, providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(
            str(self.model_dir / "tokenizer" / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=SEQ_LEN)
        t = json.loads((self.model_dir / "thresholds.json").read_text())
        self.sif_threshold = float(t["sif_threshold"])
        self.temperature = float(t["temperature"])
        self.rule_thresholds = t["rule_thresholds"]
        # Temperature-mapped frozen threshold for calibrated scores.
        self.sif_threshold_cal = float(
            sigmoid(np.array([logit(self.sif_threshold) / self.temperature]))[0])

    def encode_batch(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        encs = self.tokenizer.encode_batch(texts, add_special_tokens=True)
        width = max(len(e.ids) for e in encs)
        pad = self.tokenizer.token_to_id("[PAD]")
        ids = np.full((len(encs), width), pad, dtype=np.int64)
        mask = np.zeros((len(encs), width), dtype=np.int64)
        for i, e in enumerate(encs):
            ids[i, : len(e.ids)] = e.ids
            mask[i, : len(e.ids)] = 1
        return ids, mask

    def logits(self, texts: list[str], batch: int = 32) -> tuple[np.ndarray, np.ndarray]:
        """Returns (sif_logits [n], rule_logits [n,7]). Span head skipped
        (not needed for SIF/rule decisions; span path is exercised by the
        RealOnnxClassifier self-checks)."""
        sif, rules = [], []
        for i in range(0, len(texts), batch):
            ids, mask = self.encode_batch(texts[i : i + batch])
            s, r = self.session.run(
                ["sif_logit", "rule_logits"],
                {"input_ids": ids, "attention_mask": mask})
            sif.append(s.astype(np.float64))
            rules.append(r.astype(np.float64))
        return np.concatenate(sif), np.concatenate(rules)

    def decide(self, sif_logits: np.ndarray) -> np.ndarray:
        """Frozen operating point, temperature-first form: calibrated score
        sigmoid(z/T) >= sigmoid(logit(thr)/T). Identical to raw
        sigmoid(z) >= thr (asserted in self_check)."""
        return sigmoid(sif_logits / self.temperature) >= self.sif_threshold_cal

    def decide_rules(self, rule_logits: np.ndarray) -> list[list[str]]:
        probs = sigmoid(rule_logits)
        thr = np.array([self.rule_thresholds[r] for r in RULES])
        return [[RULES[j] for j in range(len(RULES)) if row[j] >= thr[j]]
                for row in probs]


def self_check():
    """Threshold-map identity + tokenizer special tokens. Fails loudly."""
    s = Scorer(MODELS / "masked-v1", quant="int8", threads=1)
    z = np.linspace(-30, 20, 5001)
    raw = sigmoid(z) >= s.sif_threshold
    cal = sigmoid(z / s.temperature) >= s.sif_threshold_cal
    assert (raw == cal).all(), "temperature-mapped threshold != raw decision"
    e = s.tokenizer.encode("grinding sparks near fuel drum", add_special_tokens=True)
    assert e.ids[0] == s.tokenizer.token_to_id("[CLS]")
    assert e.ids[-1] == s.tokenizer.token_to_id("[SEP]")
    long_ids = s.tokenizer.encode("word " * 500, add_special_tokens=True).ids
    assert len(long_ids) == SEQ_LEN, f"truncation broken: {len(long_ids)}"
    print(f"self-check OK: thr={s.sif_threshold:.6g} -> thr_cal={s.sif_threshold_cal:.6g} "
          f"(T={s.temperature:.4f}); tokenizer CLS/SEP/truncation@128 OK")
    return True


if __name__ == "__main__":
    sys.exit(0 if self_check() else 1)
