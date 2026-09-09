#!/usr/bin/env python3
"""Human-vs-LLM-panel agreement analysis (reported-only, post-hoc).

Reads: artifacts/gold/llm_panel_<model>.jsonl (blind cloud panel ratings)
       artifacts/gold/labels_merged_all4.jsonl (human labels — read AFTER
       panels are complete; the panel never saw these).
Writes: runs/run2/day2/llm_panel_agreement.md + .json
"""
import json, pathlib, collections

REPO = pathlib.Path(__file__).resolve().parents[3]
G = REPO / "artifacts/gold"

def load_panel(model):
    p = G / f"llm_panel_{model.replace('/', '_')}.jsonl"
    if not p.exists(): return None
    return {json.loads(l)["gold_id"]: json.loads(l) for l in open(p)}

def main():
    items = {json.loads(l)["gold_id"]: json.loads(l) for l in open(G / "gold_items.jsonl")}
    merged = [json.loads(l) for l in open(G / "labels_merged_all4.jsonl")]
    # human consensus per item (unanimity; disputed/unsure tracked separately)
    by_item = {r["gold_id"]: {k: v["label"] for k, v in r.get("labels", {}).items()}
               for r in merged}
    consensus = {}
    for g, votes in by_item.items():
        vs = set(votes.values())
        consensus[g] = next(iter(vs)) if len(vs) == 1 and "unsure" not in vs else "disputed"
    models = [m.name.replace("llm_panel_", "").replace(".jsonl", "") for m in G.glob("llm_panel_*.jsonl")]
    out = {"models": models, "per_model": {}, "panel_majority": {}}
    panel_votes = collections.defaultdict(dict)
    for m in models:
        panel = load_panel(m)
        agree = tot = 0; agree_cons = tot_cons = 0
        for g, r in panel.items():
            if r["sif_pred"] is None or g not in consensus: continue
            pred = "sif" if r["sif_pred"] else "non_sif"
            panel_votes[g][m] = pred
            hum = consensus[g]
            if hum == "disputed": continue
            tot_cons += 1; agree_cons += (pred == hum)
        out["per_model"][m] = {"n": tot_cons,
                               "agreement_vs_human_consensus": round(agree_cons / tot_cons, 4) if tot_cons else None}
    # panel majority per item (across models)
    maj = {}
    for g, vs in panel_votes.items():
        ns = sum(1 for v in vs.values() if v == "sif")
        maj[g] = "sif" if ns * 2 > len(vs) else ("non_sif" if ns * 2 < len(vs) else "tie")
    agree = tot = 0; per_stratum = collections.defaultdict(lambda: [0, 0])
    for g, m in maj.items():
        if m == "tie" or g not in consensus or consensus[g] == "disputed": continue
        tot += 1; agree += (m == consensus[g])
        strat = items[g]["source_stratum"]
        per_stratum[strat][0] += (m == consensus[g]); per_stratum[strat][1] += 1
    out["panel_majority"] = {"n": tot, "agreement": round(agree / tot, 4) if tot else None,
                             "per_stratum": {k: {"agree": v[0], "n": v[1],
                                                 "pct": round(v[0] / v[1], 4) if v[1] else None}
                                             for k, v in per_stratum.items()}}
    (G / "llm_panel_agreement.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main()
