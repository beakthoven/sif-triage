# SIF-Precursor Detection Engine — the whole project, explained for the team

*Read this and you'll understand everything about our project. No technical background needed. ~10 minutes.*

---

## 1. The problem we picked (SIH 2026, Problem Statement 26165)

**Oil India Limited** asked for this: their workers write thousands of safety reports — "unsafe acts", "unsafe conditions", "near-misses" — things like *"a wrench fell from the derrick and just missed a worker"* or *"gas smell near the pump, turned out to be nothing."*

Today, humans read these reports by hand, once a month, in big batches. Hidden inside them are the **warning signs of future fatal accidents**. Research on industrial disasters shows that roughly **1 in 5 recordable injuries shares the same "shape" as fatal accidents** — the famous safety paradox: the reports that look small can be the ones that matter most. Companies like OIL want to catch the dangerous ~20% early, before "almost" becomes a funeral.

The problem statement asks for an AI that reads these free-text reports and automatically:
1. Says whether each report has **serious-injury-or-fatality (SIF) potential**,
2. Tags which **Life-Saving Rule** it relates to (an industry-standard list from IOGP — Energy Isolation, Hot Work, Line of Fire, etc.),
3. Shows **which sites and activities keep producing dangerous patterns**, on a dashboard.

---

## 2. What we built (in one minute)

A **triage tool for safety reports** — like a spam filter, but for danger. It runs entirely on a laptop, with no internet needed (important for oil-field data privacy).

You paste or upload reports → in under a second each, the system:
- Flags the report as **"High review priority"** (amber) or **safe** (green), and if it's unsure or confused, it honestly shows a **gray "needs a human"** card instead of guessing;
- **Highlights the exact words** that made it worried (e.g. *"grinding"*, *"sparks"*, *"no fire watch"*);
- Names the matching **Life-Saving Rule(s)**;
- Ranks **sites and activities by danger density** on a dashboard, and lists recurring patterns (like *"line-of-fire incidents at the drill floor when barricades are missing"*).

Most important design choice: **the AI never has the final word.** Every flagged report goes to a human review queue — *"Model proposes, HSE disposes."* When the human corrects it, that correction is saved as a future teaching example. And if you paste something weird (a drill report, a sarcastic note, Hindi text, a 2-word message, or a copy of a training record), the system says so instead of pretending to understand it.

---

## 3. How it works (the 60-second version)

See `diagrams/01_how_it_works.html` for the picture version.

```
Worker writes report → 10 automatic safety checks → AI model scores it
      → amber "review this" / gray "ask a human" / quiet green
      → safety officer confirms or corrects → correction becomes training data
```

---

## 4. The journey — what actually happened, in order

**Day 0 — Choosing the problem.** Before this project, an earlier AI-assisted research program screened all 226 SIH problem statements through rounds of adversarial debate (170+ AI agents arguing for/against each candidate). PS 26165 won because it had the best mix of: real data available, a buildable AI core, no trick requirements, and a demo that can impress anyone.

**Day 1 morning — Trust nothing, verify everything.** We re-measured every "fact" from the research before building on it. This caught real traps: the training GPUs were misconfigured (fixed with the right settings), the injury dataset's coding system silently changes meaning in 2024 (a full renumbering — would have poisoned the model), and the laptop's CPU was secretly speed-capped (fixed with a power-profile reset).

**Day 1 — Data.** We built the training set from three sources:
- **105,996 real US workplace injury reports** (OSHA — public US government data),
- **47,723 real pilot near-miss reports** (NASA's aviation database — the only big collection of real "almost went wrong" text in the world),
- **9,687 AI-written practice reports** in Oil India's style (Duliajan, GGS stations, workover rigs, monsoon, contractor Hindi-English) — because OIL's real reports are confidential, we had to create realistic stand-ins, then ran quality gates on them (duplicate checks, leak checks, "does an AI detector catch these?" checks).

Two key tricks: we **hid the outcome words** ("fracture", "hospital") from the AI during training so it learns the *mechanism* ("fell from height") not the *injury lottery* — and we built the labels from **official injury codes**, not from anyone's opinion.

**Day 1 afternoon — Training.** The model trained on Kaggle's free cloud GPUs (2× NVIDIA T4) in about an hour. Then we compressed it to a fast 151MB form (ONNX int8) that runs on a normal laptop CPU in ~20 milliseconds per report.

**Day 1 evening — The attack squad.** We ran an adversarial review: AI agents whose only job was to break the system. They found real bugs — rules showing under the wrong names, the database corrupting under two simultaneous users, explanations caching error text. All fixed, all re-verified.

**Day 2 — The honesty exam.** This is the part we're proudest of. The team **hand-labeled 500 reports without ever seeing the AI's answers** (a "blind gold set" — the rubric everyone used is in `gold/RUBRIC.md`). Two people independently labeled 130 of the same reports so we could measure human agreement. One labeler's work failed our quality checks (measured: 2 seconds per report — impossible to read that fast) — we documented it and had the queue re-labeled carefully. *That's* how you get numbers you can defend.

**Day 3 — Proof.** The adversarial suite passed 18/18 cases plus #10b with `RealOnnxClassifier` on 2026-09-26 (`tests/adversarial_suite.py`). A network-unplug demo beat is described in the earlier rehearsal material (`docs/deck/qa_prep.md`, audit snapshot 2026-09-25); treat it as a dated historical rehearsal, not a current verification claim.

---

## 5. The current architecture (what the machine actually runs)

See `diagrams/02_system_architecture.html` for the picture. In plain terms:

| Piece | What it is | What it does |
|---|---|---|
| **Website (React)** | The dashboard you see | Paste reports, see priority cards, rankings, patterns, review queue |
| **Backend (FastAPI)** | The waiter/traffic controller | Takes requests, runs checks, talks to everything |
| **AI Model (ModernBERT)** | The brain — 149M-parameter language model we fine-tuned | Reads a report → danger score + rule tags + evidence highlights, in ~20ms |
| **Database (SQLite)** | A file on disk | Stores reports, scores, and every human override |
| **Local LLM (Qwen3-8B via Ollama)** | A bigger local language model | Writes the plain-English "why this score" explanations (with a plain template as backup if it's busy) |
| **Duplicate detector (MiniLM)** | A small similarity model | Catches when someone pastes a report the system has already seen ("that's memory, not skill") |
| **Training (Kaggle GPUs)** | Cloud, used only while building | Trained the model on public + synthetic data — never sees real OIL data |

**The privacy line:** everything in the demo runs on the laptop itself. The cloud was used only to *train* the model on public/practice data. Only the trained model file crosses over.

---

## 6. The model — what we trained and what it learned

See `diagrams/03_model_journey.html` for the picture.

**What it is:** ModernBERT — a language-understanding model (like a smaller, faster cousin of the models behind chatbots, specialized for *reading and classifying* rather than chatting). We took the general pre-trained version and **fine-tuned** it on our 71,065-report training set.

**What it learned to do, in one look:** given a report, output three things at once — a danger score (0 to 1), a probability for each of the 7 learnable Life-Saving Rules, and the exact evidence words.

**What it was fed:** the three data sources from §4 (real US injuries + real aviation near-misses + OIL-style practice reports), with outcome words masked.

**How it was tested (the honest way):** at the historical single-text threshold 0.658108, the blind pooled-consensus human-gold evaluation had n=318 and 89.9% positive prevalence:
- **Precision 0.976 [0.948, 0.989]**; **recall 0.836 [0.788, 0.874]**
- These high-prevalence results do not transfer to deployment traffic or represent the current serving N=4 ensemble. Source: [`artifacts/gold/gold_metrics_final.md`](../artifacts/gold/gold_metrics_final.md).
- At the current threshold 0.5647, a single-text re-evaluation (not the N=4 ensemble; OSHA gold overlaps the threshold-tuning temporal split) reports precision 0.972 [0.943, 0.986] and recall 0.843 [0.796, 0.880]. Source: [`artifacts/gold/gold_metrics_current_point_20260926.md`](../artifacts/gold/gold_metrics_current_point_20260926.md). This is not a fully held-out result.
- Human agreement was measured separately on a double-labeled subset; it is not a model-validity guarantee.
- It **beats an 8-billion-parameter LLM** (Qwen3-8B zero-shot) on the same test — while running **1,000× faster and free, offline**

**What it honestly can't do (we say this out loud):** it can't judge two of the nine Life-Saving Rules from injury text (Permit to Work and Bypassing Safety Controls are paperwork violations — invisible in the text), it doesn't understand aviation language (out of its territory), and it never predicts accidents — it prioritizes human attention. That distinction is deliberate and it's our answer to the toughest judge question.

---

## 7. If a teammate gets asked a question on stage

| If someone asks… | The one-line answer |
|---|---|
| "What does it do?" | "It reads safety near-miss reports and puts the dangerous ones at the top of the pile for a human officer." |
| "Is it predicting accidents?" | "No — it triages. It flags reports with fatal-accident-shaped mechanisms so humans look at them first." |
| "Where's the data from?" | "Public US injury reports + NASA near-misses + clearly-labeled AI-generated practice reports in OIL's style. OIL's real reports stay private." |
| "How did it perform on the blind human-gold sample?" | "At the historical single-text threshold 0.658108, blind pooled consensus n=318 (89.9% positive prevalence) had precision 0.976 [0.948, 0.989] and recall 0.836 [0.788, 0.874]. That is not the serving N=4 ensemble or a deployment estimate. At the current threshold 0.5647, a single-text re-evaluation reports P 0.972 [0.943, 0.986], R 0.843 [0.796, 0.880]; its OSHA cases overlap tuning data, so it is not fully held out. Sources: `artifacts/gold/gold_metrics_final.md` and `artifacts/gold/gold_metrics_current_point_20260926.md`." |
| "Does it need internet?" | "No — watch: *unplugs cable*. Everything runs on this laptop." |
| "What if it's wrong?" | "It says 'I'm not sure' and routes to a human — and every human correction becomes new training data." |

---

## 8. Glossary (the only jargon you'll hear)

- **SIF** — Serious Injury or Fatality. **SIF-precursor** — a report describing conditions that *could have* killed someone.
- **IOGP Life-Saving Rules** — the international oil-industry's 9 rules for the activities that kill people most often.
- **Fine-tuning** — taking a general AI model and continuing its training on our specific task.
- **Gold set** — the 500 reports humans labeled blind, used only for final testing.
- **ONNX / int8** — a compressed, fast form of the model that runs on ordinary laptops.
- **Triage** — sorting by urgency, like a hospital emergency room. Not prediction.

*Everything in this document is backed by measurements and files in the project repo (`runs/run2/` has the full audit trail).*
