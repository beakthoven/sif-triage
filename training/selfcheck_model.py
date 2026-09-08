#!/usr/bin/env python3
"""Self-check for training/model.py. Run: python3 training/selfcheck_model.py

Two modes, picked automatically:
  - no torch installed (local dev box): py_compile + AST structural asserts
    (forward returns the three head keys; build_model factory exists).
  - torch+transformers installed (Kaggle): monkeypatches AutoModel to a tiny
    random ModernBERT and exercises the real build_model() + forward shapes.
"""
import ast, py_compile, sys
from pathlib import Path

MODEL_PY = Path(__file__).with_name("model.py")


def check_ast():
    py_compile.compile(str(MODEL_PY), doraise=True)
    tree = ast.parse(MODEL_PY.read_text())
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "SIFMultiTaskModel")
    fwd = next(n for n in cls.body
               if isinstance(n, ast.FunctionDef) and n.name == "forward")
    ret = next(n for n in ast.walk(fwd) if isinstance(n, ast.Return))
    keys = {k.value for k in ret.value.keys}
    assert keys == {"sif_logit", "rule_logits", "span_logits"}, keys
    fns = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "build_model" in fns, fns
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.While,)), "dynamic control flow"
    print("AST self-check OK: forward returns {sif_logit, rule_logits, "
          "span_logits}; build_model present; compiles clean")


def check_forward():
    import torch
    from transformers import ModernBertConfig, ModernBertModel
    import model as m

    tiny = ModernBertModel(ModernBertConfig(
        vocab_size=256, hidden_size=32, num_hidden_layers=2,
        num_attention_heads=2, intermediate_size=64, max_position_embeddings=64))
    orig = m.AutoModel.from_pretrained
    m.AutoModel.from_pretrained = lambda *a, **k: tiny
    try:
        net = m.build_model()
    finally:
        m.AutoModel.from_pretrained = orig

    ids = torch.randint(0, 256, (4, 17))
    mask = torch.ones(4, 17, dtype=torch.long)
    net.eval()
    with torch.no_grad():
        out = net(ids, mask)
    assert set(out) == set(m.OUTPUT_KEYS), out.keys()
    assert out["sif_logit"].shape == (4,), out["sif_logit"].shape
    assert out["rule_logits"].shape == (4, m.NUM_RULES), out["rule_logits"].shape
    assert out["span_logits"].shape == (4, 17), out["span_logits"].shape
    assert all(torch.isfinite(v).all() for v in out.values())
    print("forward self-check OK: shapes (4,), (4,7), (4,17), all finite")


if __name__ == "__main__":
    sys.path.insert(0, str(MODEL_PY.parent))
    check_ast()
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        print("torch/transformers absent — forward check deferred to Kaggle gate")
    else:
        check_forward()
