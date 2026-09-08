#!/usr/bin/env python3
"""Multi-task ModernBERT model for SIF-precursor detection (PS 26165).

Backbone: answerdotai/ModernBERT-base (attn_implementation="sdpa" — no FA2
on sm_60/sm_75, per DECISION_LOG D1). Three heads per ARCHITECTURE v2:
  sif_logit   (B,)    SIF binary flag, plain BCE
  rule_logits (B, 7)  7 IOGP life-saving rules, multi-label BCE
  span_logits (B, T)  token-level evidence spans, weakly supervised (D2)

Forward returns a plain dict. Export-friendly by construction: fixed head
shapes, first-token pooling, no data-dependent control flow. The Kaggle
export gate wraps forward into a tuple-returning module for
torch.onnx.export; this file stays deployment-agnostic.
"""
import torch
import torch.nn as nn
from transformers import AutoModel

BACKBONE = "answerdotai/ModernBERT-base"
NUM_RULES = 7

OUTPUT_KEYS = ("sif_logit", "rule_logits", "span_logits")


class SIFMultiTaskModel(nn.Module):
    def __init__(self, backbone_name=BACKBONE, num_rules=NUM_RULES,
                 dropout=0.1, attn_implementation="sdpa"):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(
            backbone_name, attn_implementation=attn_implementation)
        hidden = self.backbone.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.sif_head = nn.Linear(hidden, 1)
        self.rule_head = nn.Linear(hidden, num_rules)
        self.span_head = nn.Linear(hidden, 1)

    def forward(self, input_ids, attention_mask):
        hidden = self.backbone(
            input_ids=input_ids, attention_mask=attention_mask
        ).last_hidden_state
        hidden = self.dropout(hidden)
        pooled = hidden[:, 0]
        return {
            "sif_logit": self.sif_head(pooled).squeeze(-1),
            "rule_logits": self.rule_head(pooled),
            "span_logits": self.span_head(hidden).squeeze(-1),
        }


def build_model(backbone_name=BACKBONE, num_rules=NUM_RULES, dropout=0.1,
                attn_implementation="sdpa"):
    return SIFMultiTaskModel(backbone_name, num_rules, dropout,
                             attn_implementation)
