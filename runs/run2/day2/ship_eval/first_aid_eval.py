"""THE FIRST-AID TEST — masked-v1 vs masked-v2 on the D21 false-positive class.

Three text groups, all expected non-SIF (low-energy, first-aid-only):
  A. demo        — the demo first-aid-green card (verbatim; v1 scored it
                   0.964 int8 / 0.980 fp32 -> HIGH FP, D21/F1).
  B. train50     — 50 rows sampled (seed 21) from artifacts/synthetic/clean_v4/
                   fa_a.jsonl. CONTAMINATION CAVEAT: all 500 fa_a rows are in
                   train_final_v4.jsonl = masked-v2's training data. Low v2
                   scores here prove exposure, not generalization.
  C. unseen20    — 20 first-aid paraphrases written by this agent on
                   2026-09-08 (below, inline). Same register family and
                   treatment vocabulary, different mechanisms/sites/phrasing;
                   never seen by either model's training data. THIS is the
                   honest FP-fix test.

Scored with both models, int8, single-text batch=1 (D27 ship path). Decision
= p_raw >= the model's own test-tuned operating point (v1: 0.821855 D27;
v2: from artifacts/models/masked-v2/metrics.json operating_point_test_tuned,
written by tune_op_v2.py — run that first).

Writes first_aid_results.json + prints the verdict table.
Run: .venv/bin/python runs/run2/day2/ship_eval/first_aid_eval.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "day1" / "real_model_integration"))
from onnx_score import REPO, Scorer, sigmoid  # noqa: E402

HERE = Path(__file__).resolve().parent

# 20 UNSEEN first-aid paraphrases (agent-written, 2026-09-08). Register:
# site/role/name + minor mechanism + first-aid treatment + resumed duty.
UNSEEN20 = [
    "While dressing panel wiring at GGS-1 Lakwa in the morning shift, Electrician Rupam felt a prick on his index finger from a trimmed cable-tie tail. The tiny cut was washed, antiseptic applied and an adhesive bandage fixed at the first-aid room. He returned to the panel and finished the dressing job.",
    "During housekeeping sweeping of the compressor house at EPS Gelakey, dust blew into the left eye of Attendant Diganta. The medic flushed the eye at the eye-wash point for ten minutes and the irritation settled. He was back on his round within the hour.",
    "Near the fence line of Well M-207 Tengakhat during the forenoon inspection, a wasp stung Helper Bitu on the left forearm. A cold compress was kept and soothing cream applied at the dispensary; he was observed for half an hour and resumed normal duty.",
    "Checking steam traps behind the heater treater at CTF Kathalguri, Operator Niren got a light scald on the wrist from a condensate drip. The spot was held under cool running water for fifteen minutes and burn gel applied. He completed the trap survey with gloves on.",
    "While hooking a chain block at Tinsukia pipe yard, Rigger Palash pinched the skin of his right palm in the hook latch. An ice pack was kept for twenty minutes and the redness eased. Slings and hooks were re-checked before the next lift and he stayed on the job.",
    "New safety boots gave Fitter Girish a blister on the heel during the morning rounds at Dikom EPS. The first aider cleaned the spot and fixed a blister plaster; spare broken-in boots were issued from the store. He finished his shift walking normally.",
    "Climbing the skid stairs at GGS-4 Narayanpur, Technician Madhab bumped his knee against a flange edge. An ice pack was applied at the first-aid room; he walked without a limp and resumed the valve greasing round.",
    "Handling an old flange gasket at the Duliajan workshop, Welder Tapan picked up a fine metal sliver in his fingertip. The medic removed it with tweezers, dabbed antiseptic and dressed the finger lightly. He resumed fit-up work after the break.",
    "The wrench slipped off a grease-nipple cap at Well NHK-455 and Mechanic Hemanta grazed his knuckle. The graze was washed, Savlon applied and a light gauze fixed. A ring-type spanner was taken for the remaining nipples and the greasing was completed.",
    "While washing the mud pump liner at rig RJ-9, coolant splashed onto the forearm of Floorman Kishore. The arm was rinsed at the eyewash-cum-shower for fifteen minutes; the skin showed no redness afterwards. He went back to the pump house for the next liner.",
    "Closing a sticky valve handwheel at Moran GCS, Operator Bapan nipped the skin between thumb and finger in the wheel spokes. A cold pack was kept for fifteen minutes and movement stayed normal. The handwheel was reported for greasing and he continued the line-up.",
    "Preparing the pig receiver at EPS Balimara, Technician Pranjal grazed his elbow on a grating edge. The abrasion was cleaned and a light dressing applied at the first-aid post. He resumed the receiver checklist with sleeves buttoned.",
    "During grinding with a full face shield and screen at Kathaloni workshop, a warm chip landed on the boot tongue of Welder Dipu and left a small red spot on the ankle skin. Cool water was poured for ten minutes and soothing cream applied. He finished the bevel after changing to spats.",
    "Touch-up painting of the walkway rail at GGS-2 Chabua left a paint splash on the forehead of Painter Uttam. The splash was wiped off and the skin washed with soap; no irritation followed. He completed the railing with a fresh rag tied at the brim.",
    "After lifting a 12 kg chemical sack onto the dosing skid at CTF Duliajan, Technician Romen felt a twinge in the lower back. The medic examined him, advised a warm compress and light duty for the rest of the shift; two-man lift was briefed for the remaining sacks. He was normal the next morning.",
    "Shifting a wooden pallet at the Baghjan material yard, Store hand Pabitra took a thin splinter under a fingernail. The splinter was taken out at the first-aid room and the finger dressed. Gloves were worn for the rest of the pallet shifting.",
    "Pulling instrument cable along the tray at Well G-88 Gelakey, Technician Utpal scratched his forearm on a tray edge. The scratch was cleaned and an adhesive dressing fixed. A rag was wrapped on the sharp edge and the cable pull was completed.",
    "Stacking cement bags at the rig RJ-14 go-down, dust irritated the right eye of Helper Nabajit. The eye was flushed at the wash station for ten minutes and the grit came out. He resumed stacking with a dust mask and goggles.",
    "Walking the dyke inspection line at Naharkatiya tank farm, a bee stung Operator Kamaleswar on the neck. The sting was scraped out, ice kept for twenty minutes and he was watched for half an hour at the dispensary. He completed the dyke round before dusk.",
    "While closing a drum lid at the Duliajan lube store, Store keeper Dipankar jammed his little finger between the lid and the rim. The finger was soaked in cold water for twenty minutes; the nail stayed intact and movement was normal. A wooden wedge was kept on the drum afterwards.",
]

V1_OP = 0.821855  # D27 single-text-tuned, artifacts/models/masked-v1/metrics.json


def load_op(model_dir):
    m = json.loads((model_dir / "metrics.json").read_text())
    op = m.get("operating_point_test_tuned")
    if not op or not op.get("threshold"):
        raise SystemExit(f"{model_dir}/metrics.json has no "
                         "operating_point_test_tuned — run tune_op_v2.py first")
    return float(op["threshold"]), float(m["temperature"])


def main() -> int:
    cards = [json.loads(l) for l in (REPO / "artifacts/demo/demo_corpus.jsonl").open()]
    demo = next(c for c in cards if c["demo_id"] == "first-aid-green")

    fa = [json.loads(l) for l in (REPO / "artifacts/synthetic/clean_v4/fa_a.jsonl").open()]
    train50 = random.Random(21).sample(fa, 50)

    v2_dir = REPO / "artifacts/models/masked-v2"
    v2_op, v2_T = load_op(v2_dir)
    sc1 = Scorer(REPO / "artifacts/models/masked-v1", quant="int8", threads=8)
    sc2 = Scorer(v2_dir, quant="int8", threads=8)
    assert abs(sc1.temperature - 1.683972954750061) < 1e-9
    assert abs(v2_T - sc2.temperature) < 1e-9

    groups = (["demo", demo["text"]],
              *[["train50", r["text"]] for r in train50],
              *[["unseen20", t] for t in UNSEEN20])
    rows = []
    for group, text in groups:
        z1, _ = sc1.logits([text], batch=1)
        z2, _ = sc2.logits([text], batch=1)
        p1, p2 = float(sigmoid(z1[0])), float(sigmoid(z2[0]))
        rows.append({
            "group": group, "text": text[:110],
            "v1_p_raw": p1, "v1_p_cal": float(sigmoid(z1[0] / sc1.temperature)),
            "v1_flag": p1 >= V1_OP,
            "v2_p_raw": p2, "v2_p_cal": float(sigmoid(z2[0] / sc2.temperature)),
            "v2_flag": p2 >= v2_op,
        })

    out = {
        "ops": {"v1_threshold_raw": V1_OP, "v2_threshold_raw": v2_op},
        "scoring": "int8 single-text batch=1 (D27 ship path)",
        "contamination": "train50 rows are IN masked-v2 training data "
                         "(train_final_v4.jsonl) — v2-low there is exposure, "
                         "not generalization; unseen20 is the honest test",
        "rows": rows,
    }
    summary = {}
    for group in ("demo", "train50", "unseen20"):
        g = [r for r in rows if r["group"] == group]
        summary[group] = {
            "n": len(g),
            "v1_flagged": sum(r["v1_flag"] for r in g),
            "v2_flagged": sum(r["v2_flag"] for r in g),
            "v1_p_raw_mean": sum(r["v1_p_raw"] for r in g) / len(g),
            "v2_p_raw_mean": sum(r["v2_p_raw"] for r in g) / len(g),
            "v1_p_raw_max": max(r["v1_p_raw"] for r in g),
            "v2_p_raw_max": max(r["v2_p_raw"] for r in g),
        }
    out["summary"] = summary
    (HERE / "first_aid_results.json").write_text(json.dumps(out, indent=1) + "\n")

    print(f"ops: v1 raw>={V1_OP} | v2 raw>={v2_op:.6g}")
    print(f"{'group':<9} {'n':>3} {'v1 flags':>8} {'v2 flags':>8} "
          f"{'v1 p mean/max':>18} {'v2 p mean/max':>18}")
    for group, s in summary.items():
        print(f"{group:<9} {s['n']:>3} {s['v1_flagged']:>8} {s['v2_flagged']:>8} "
              f"{s['v1_p_raw_mean']:>9.4f}/{s['v1_p_raw_max']:.4f} "
              f"{s['v2_p_raw_mean']:>9.4f}/{s['v2_p_raw_max']:.4f}")
    d = rows[0]
    print(f"\ndemo card: v1 p_raw={d['v1_p_raw']:.4f} "
          f"({'FLAG' if d['v1_flag'] else 'low'}) -> v2 p_raw={d['v2_p_raw']:.4f} "
          f"({'FLAG' if d['v2_flag'] else 'low'})")
    print("\nunseen20 per-text:")
    for i, r in enumerate([r for r in rows if r['group'] == 'unseen20']):
        print(f"  u{i+1:02d} v1={r['v1_p_raw']:.4f}{'*FLAG' if r['v1_flag'] else '':6s} "
              f"v2={r['v2_p_raw']:.4f}{'*FLAG' if r['v2_flag'] else '':6s} {r['text'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
