# DEMO CARD — presenter's one-page cheat sheet (SIH 26165)

Ship config: **masked-v2 INT8, single-text**, op cal 0.658108 · stack: `./run.sh` →
`http://127.0.0.1:8177/` · pre-stage 4,548 reports (the live 500-row ingest takes it
to 5,048 — that is the POST-demo state) · health verified 2026-09-10.
Card texts: `artifacts/demo/demo_corpus.jsonl` (13 cards, teammate copy-pastes —
no live typing). Full script: `artifacts/demo/script_90s.md`.
Scores below are the **verified live v2 numbers** (demo_final_state.md §2) — say these,
not the old mock ones.

## Pre-stage (T-30 min)

- [ ] Laptop on AC, battery 100% · WiFi OFF in settings · ethernet connected (for the unplug)
- [ ] `./run.sh` → health shows `RealOnnxClassifier`, `masked-v2`, `n_reports: 4548`
      (`curl -s http://127.0.0.1:8177/api/health`) — **4,548 is the correct PRE-state**;
      5,048 means the money beat is already spent (restore `artifacts/demo/demo_pre.db`).
- [ ] If health shows `MockClassifier` — STOP. Do not demo. (See recovery.)
- [ ] Tabs pinned: dashboard feed · density view · metrics slide · browser 1920×1080 @100%
- [ ] demo_corpus.jsonl open on teammate machine · recording USB in pocket

## The 90 seconds

| Time | Beat | Action | Say (compressed) | Verified number to point at |
|---|---|---|---|---|
| 0:00–0:07 | HOOK | nothing | "Baghjan burned five months. The warnings weren't missing — they were buried." | — |
| 0:07–0:19 | RED card | paste `contrast-red` | "A wrench falls past the drill floor — HIGH review priority, Line of Fire on top; no invented highlight on this card (frozen keywords exclude falling-object words) — highlights fire where the vocabulary is explicit." | score **0.93**, LoF bar **0.85** |
| 0:19–0:28 | GREEN card | paste `contrast-green` | "Same spanner, floor cleared — it leaves it alone. Only the exposure changed — and the score followed the exposure: 0.93 to 0.01." | score **0.01** |
| 0:28–0:38 | Gray states | paste `gray-negation`, then `gray-drill` | "Two honest answers: negation guard refuses to auto-green; drills are training, not precursors." | both → GRAY cards |
| 0:38–0:47 | Well-control + हिं | paste `wc-baghjan-1`; flash `wc-baghjan-3` span tile; flash `hinglish` | "Well-cellar entry during wait-on-cement — the barrier tag catches what the 7 rules can't. On explicit vocabulary the highlight fires in the report's own words. Hindi UI; the engine grays Hindi text instead of mis-scoring it." | wc-1 **0.90**, CS 0.94, WC tag; wc-3 **0.98**, span `Welding` |
| 0:47–0:53 | **THE UNPLUG** | **pull the ethernet cable**, refresh | "That was the network. Everything runs on this laptop. Your data never leaves your fence." | page reloads from 127.0.0.1 |
| 0:53–1:06 | Bulk + pattern | upload the 500-row CSV live; show pattern cards | "Five hundred register rows ingested live and scored. Patterns read structured facets — n and confidence intervals, no LLM guessing." | **accepted 500/500 live, ~15 s** |
| 1:06–1:15 | **RE-RANK (money beat)** | density view | "Kathalguri GCS × DG exhaust-duct inspection — was #2 with 88, now #1, every report flagged. That is where your next inspection goes." | site **#1, 213/213 flagged, rate 1.0**; cell **96/96**, min score 0.760 vs 0.658 threshold |
| 1:15–1:24 | Near-dup | paste `verbatim-osha` | "A row straight out of the file we ingested — it catches its own memory. That's why our eval is a temporal hard split." | banner: cosine **1.000** |
| 1:24–1:30 | CLOSE | metrics slide | "Recall 0.836 on blind human gold, kappa, latency — every number measured on this machine in 72 hours. Model proposes, HSE disposes. Questions." | R **0.836** [0.788, 0.874] / p95 **17.7 ms** |

## Fallback lines (memorize)

- Card lands gray when it shouldn't: **"Even our own demo row goes to a human when the
  model is unsure — that's the humility system working, not failing."**
- contrast-green flags HIGH: **"This is why every flag carries a human override"** —
  click Not-SIF; the override beat *becomes* the demo.
- Spans missing on a card (spec-keyword gap is a known, adjudicated limitation):
  **"No spec keyword, no highlight — we never show garbage."**
- mega-report shows 3/7 rule bars (not 7): **"These are probabilities, not assertions —
  three cross threshold, you see all seven."**
- Any throughput question: **"The measured live number is 45.6 reports/s end-to-end
  (model-only classify p95 17.7 ms)."** Never quote 500/s.
- Judge pastes their own report: **GO unconditionally** — every failure mode ends in a
  designed gray card.

## Encore rows (only if asked)

| They ask | Paste | Point |
|---|---|---|
| Long reports? | `long-report` | CHUNKED badge, sliding-window, HIGH **0.75**, 233 ms |
| Everything at once? | `mega-report` | WC tag + multi-rule bars, **0.98** |
| Terse codes? | `codes-only` | "LOTO not applied" accepted via codes path, **0.07** LOW |
| First-aid case? | `first-aid-green` | **0.26 LOW** — the v1 model red-flagged this (0.96); v2 fixed it with data, not a demo dodge |
| Baghjan? | `wc-baghjan-2/3` | rehearsed framing only — NEVER "would have prevented" |

## Recovery commands (second teammate owns these)

```bash
./run.sh --stop && ./run.sh          # full restart (pidfiles in .run/)
curl -s http://127.0.0.1:8177/api/health   # must say RealOnnxClassifier + masked-v2
tail -n 50 .run/uvicorn.log           # API log
tail -n 50 .run/ollama.log            # rewording LLM log
SIF_MODEL_PATH=artifacts/models/masked-v1 ./run.sh   # one-env-var fallback model
SIF_MODEL_QUANT=fp32 ./run.sh         # fp32 fallback (slower; NOT decision-identical)
OLLAMA_NUM_PARALLEL=6 nohup ollama serve &           # if explanations fall to template
```

- Explanations silently fall back to deterministic templates — **never broken on stage**,
  so ollama is optional.
- Browser weirdness after unplug: hard-refresh the pinned tab (`Ctrl+Shift+R`); do NOT
  re-plug.
- Total failure twice in rehearsal → the precomputed recording + screenshots
  (`runs/run2/day1/e2e/screenshots/final_*.png`) become primary; live rig becomes encore.

## Hard rules (from the script, non-negotiable)

1. Never "SIF detected", never "prediction", never "% accuracy" — "flagged for review",
   "triage", "triage score".
2. Never quote an unmeasured number. Measured set: p95 17.7 ms model-only (e2e 56 ms) ·
   45.6/s ingest · near-dup p95 3.8 ms.
3. Never live-translate; never live-LLM in the 90 s path.
4. Re-pasting a demo row fires the near-dup banner **by design** — narrate it, don't
   apologize.
5. The demo DB is demo data (synthetic OIL register + one verbatim OSHA row) — if asked,
   say so.
