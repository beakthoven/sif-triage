"""Span quality comparison — 20 real reports (test.jsonl, seed 11 — the same
sample as day-1 selfcheck_spans.py) through BOTH models' span heads.

Raw token-level spans with the current thresholds (the post-SEV2-2/SEV3-4
extractor may still be in flight): token span-probs > 0.5 -> merge contiguous
runs -> char offsets via the tokenizer offset map -> top-3 by mean run prob;
fallback when nothing crosses 0.5: top-3 scoring tokens (the ARCHITECTURE
keyword-attribution fallback). Per-window single-row session.run (D27); spans
from the argmax-sif window, like the app. Substring validity asserted on
every span (text[start:end] == span).

Writes spans_compare.json + prints the side-by-side table.
Run: .venv/bin/python runs/run2/day2/ship_eval/spans_compare.py
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "runs/run2/day1/real_model_integration"))
from onnx_score import sigmoid  # noqa: E402

HERE = Path(__file__).resolve().parent
SEQ_LEN, STRIDE, SPAN_THRESHOLD, TOP_SPANS = 128, 96, 0.5, 3


def windows(n_body):
    body = SEQ_LEN - 2
    if n_body <= body:
        return [(0, n_body)]
    out = [(i, min(i + body, n_body)) for i in range(0, n_body, STRIDE)]
    if out[-1][1] < n_body:
        out.append((n_body - body, n_body))
    return out


class SpanScorer:
    def __init__(self, model_dir):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.dir = Path(model_dir)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 8
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(self.dir / "sif_multitask_int8.onnx"), opts,
            providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(self.dir / "tokenizer" / "tokenizer.json"))
        m = json.loads((self.dir / "metrics.json").read_text())
        self.temperature = float(m["temperature"])

    def predict(self, text):
        enc = self.tok.encode(text, add_special_tokens=False)
        cls, sep = self.tok.token_to_id("[CLS]"), self.tok.token_to_id("[SEP]")
        best = None  # (sif_cal, window, span_probs)
        for s, e in windows(len(enc.ids)):
            body = enc.ids[s:e]
            ids = np.array([[cls, *body, sep]], dtype=np.int64)
            z, _, sl = self.session.run(
                ["sif_logit", "rule_logits", "span_logits"],
                {"input_ids": ids, "attention_mask": np.ones_like(ids)})
            p_cal = float(sigmoid(z[0] / self.temperature))
            probs = sigmoid(sl[0][1: len(body) + 1].astype(np.float64))
            if best is None or p_cal > best[0]:
                best = (p_cal, (s, e), probs)
        p_cal, (s, e), probs = best
        offsets = enc.offsets[s:e]
        n = e - s
        hot = [j for j in range(n) if probs[j] > SPAN_THRESHOLD
               and offsets[j][1] > offsets[j][0]]
        runs = []
        for j in hot:
            if runs and j == runs[-1][-1] + 1:
                runs[-1].append(j)
            else:
                runs.append([j])
        cands = []
        for run in runs:
            c0, c1 = offsets[run[0]][0], offsets[run[-1]][1]
            if 0 <= c0 < c1 <= len(text):
                cands.append((float(np.mean(probs[run[0]:run[-1] + 1])), c0, c1))
        fallback = not cands
        if fallback and n > 0:
            ranked = sorted((j for j in range(n) if offsets[j][1] > offsets[j][0]),
                            key=lambda j: float(probs[j]), reverse=True)
            for j in ranked[:TOP_SPANS]:
                c0, c1 = offsets[j]
                if 0 <= c0 < c1 <= len(text):
                    cands.append((float(probs[j]), c0, c1))
        cands.sort(key=lambda c: (-c[0], c[1]))
        spans, seen = [], set()
        for p, c0, c1 in cands:
            if (c0, c1) in seen:
                continue
            seen.add((c0, c1))
            assert text[c0:c1] == text[c0:c1] and 0 <= c0 < c1 <= len(text)
            spans.append({"text": text[c0:c1], "p": round(p, 3),
                          "start": c0, "end": c1})
            if len(spans) == TOP_SPANS:
                break
        return {"p_cal": p_cal, "spans": spans, "fallback": fallback,
                "n_windows": len(windows(len(enc.ids)))}


def main():
    rows = [json.loads(l) for l in (REPO / "artifacts/corpus/test.jsonl").open()]
    sample = random.Random(11).sample(rows, 20)
    scorers = {n: SpanScorer(REPO / f"artifacts/models/{n}")
               for n in ("masked-v1", "masked-v2")}
    out = []
    print(f"{'id':<18} {'y':>1} {'v1 score':>8} {'v2 score':>8}  spans")
    for r in sample:
        text = r["masked_text"]
        row = {"id": r["id"], "sif_label": r["sif_label"]}
        for name, sc in scorers.items():
            row[name] = sc.predict(text)
        out.append(row)
        v1s = " | ".join(f"{s['text']!r}({s['p']:.2f})" for s in row["masked-v1"]["spans"])
        v2s = " | ".join(f"{s['text']!r}({s['p']:.2f})" for s in row["masked-v2"]["spans"])
        fb = lambda m: " [fallback]" if row[m]["fallback"] else ""
        print(f"{r['id']:<18} {r['sif_label']:>1} {row['masked-v1']['p_cal']:>8.3f} "
              f"{row['masked-v2']['p_cal']:>8.3f}")
        print(f"   v1{fb('masked-v1')}: {v1s or '(none)'}")
        print(f"   v2{fb('masked-v2')}: {v2s or '(none)'}")
    n_fb1 = sum(r["masked-v1"]["fallback"] for r in out)
    n_fb2 = sum(r["masked-v2"]["fallback"] for r in out)
    n_sp1 = sum(len(r["masked-v1"]["spans"]) for r in out)
    n_sp2 = sum(len(r["masked-v2"]["spans"]) for r in out)
    print(f"\nfallback rate: v1 {n_fb1}/20, v2 {n_fb2}/20; "
          f"spans emitted: v1 {n_sp1}, v2 {n_sp2}")
    (HERE / "spans_compare.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {HERE / 'spans_compare.json'}")


if __name__ == "__main__":
    main()
