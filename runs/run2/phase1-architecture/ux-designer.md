# Phase 1 — UX Designer (demo-first, non-technical judges)
Attack surface: everything judges see/feel. Date 2026-09-08. VERIFIED = measured by me today; INFERRED otherwise.

## 1. Findings (with numbers)

- **Display: 2944×1840 HiDPI panel, Wayland/GNOME 50** (VERIFIED, xrandr). Projectors are 1920×1080/1024×768; HiDPI dev text looks ~1.5× denser than projected. Design + rehearse at **1920×1080 @100% zoom**, re-check at 1024×768.
- **WCAG contrast, computed (VERIFIED):** amber-400 #FBBF24 on navy #0B1220 = **11.2:1 (AAA)**; slate-50 on navy 17.9:1; red-500 on navy only 4.98:1; red-600 on white 4.83:1. Amber-on-navy is the most projector-robust accent; red is marginal under washout.
- **Latency (bar §E):** classify <100ms p95 → card feels instant (add 250ms skeleton so it reads *working*, not broken); ingest ≥500 reports/s → **5k demo ingest ≈10s** — a natural progress-bar beat before re-rank (INFERRED pacing from measured target).
- **Live LLM now 3.7–4.4 tok/s (C3, VERIFIED):** unusable in the 90s loop; precompute doctrine holds; a designed "live assistant" encore state is mandatory. CPU clamp also slows ONNX/ingest ~6× (INFERRED) — nothing in the 90s path may depend on >1s compute.
- **React 19 / node 26 verified (P0-7/P0-9):** shadcn/ui + Tailwind viable; pattern view needs no chart lib at all.

## 2. Risks, ranked

**SEV1-1 (project-killer): framing leak in the UI.** Part C/§B.8 says "red SIF card". Rendered naively (red + "SIF DETECTED" + % score), the screen itself becomes a fatality-prediction claim — violating §A.5 doctrine 1 and §B.6 in front of HSE judges. The UI is where the triage doctrine is won or lost.

**SEV2-1:** gray states styled like errors (red toasts, "failed" copy) — reads as broken model, not engineered humility.
**SEV2-2:** pattern-mining as sankey/network graph — bureaucrats can't parse it in 10s.
**SEV2-3:** density table with no visible re-rank moment — the "I want this" beat dies.
**SEV2-4:** Hindi toggle implying full Hindi NLP (4B Hindi is weak, §B.4) → hostile Q&A exposure.
**SEV3:** dark/light projector mismatch; non-tabular numerals jitter during count-up; missing reduced-motion fallback.

## 3. Recommendations per architecture element

**MODIFY — "red SIF card" → high-vis amber "review priority" card.** Amber = industrial PPE semantics (*attention*, not *death*), AAA contrast, colorblind-safe vs slate (no red/green pairing anywhere). Signature: diagonal hazard-tape stripe (repeating-linear-gradient 45° amber/navy) on card headers — instantly recognizable in every screenshot, pure CSS, zero cost. Score shown as **BAND** (HIGH/MODERATE/LOW review priority) with the calibrated number small and labeled "triage score", never "%" alone. Copy: "Flagged for HSE review", never "detected".

Money-shot card (View 1, THE screenshot):
```
┌─▟▟ HIGH REVIEW PRIORITY ▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟▟┐
│ Band HIGH · triage score 0.87 · 38ms                  │
│ Rule: ⚡ LINE OF FIRE 0.91   (2nd: Working at Height) │
│ "…dropped a spanner from the derrick, falling         │
│  ▓▓above the occupied drill floor▓▓, landing ▓▓1 m    │
│  from the floorman▓▓…"      ← verbatim spans, amber   │
│ [✓ Confirm SIF-potential] [✗ Not SIF-potential]       │
│ Your decision becomes a training label.               │
└───────────────────────────────────────────────────────┘
```
Override buttons bottom-right of card, equal visual weight, one click — "model proposes, HSE disposes" as the literal footer line.

**ADOPT — 4 gray gate-states**, each a named "Sentinel gate" feature card (slate, icon, one plain sentence, "routed to review — never auto-cleared"): (1) 🛈 Low confidence (<τ); (2) ↔ Negation guard ("'no injury' phrasing"); (3) 🌐 Language gate (Hindi detected → translated → scored, shown as pipeline); (4) ⧉ Near-dup banner ("matches a training record — memory, not generalization"). Uniform template = looks like one engineered guardrail system, four honest behaviors.

**ADOPT — density ranking as ranked table + FLIP re-rank animation** (600ms, count-up deltas ▲2/▼1). Recharts heatmap as a secondary toggle only. The bureaucrat beat: ingest progress bar (~10s) → rows visibly re-sort → "Baghjan EPS just climbed to #1."

**MODIFY — pattern mining: NO sankey.** Top-5 plain-language pattern cards: "LINE OF FIRE × drill floor × missing barricade — 14 reports / 30 days". One sentence, one count. Non-technical-proof.

**ADOPT — metrics slide: 4 numbers, 96–120px tabular numerals, one per quadrant** (recall@P=.80 + CI; κ; 31ms local p95; span exact-match). Dark navy, amber numerals.

**Design system:** dark navy #0B1220 primary, light fallback rehearsed. IBM Plex Sans (industrial register) + Plex Mono tabular-nums for numbers; base 18px, min 16px; min target 44px. Hindi: **ADOPT phrasebook, scope = UI chrome only** (EN/हिं toggle top-right); report text stays original + "translation available" badge — never imply Hindi model competence. A11y: every state icon+text (never color-only), focus rings, keyboard-walkable demo path, `prefers-reduced-motion` → static swap instead of FLIP.

## 4. Verdict

**GO, with the SEV1 framing fix mandatory before any dashboard code.** Architecture's five dashboard elements all survive; the two changes (amber/band framing, plain-sentence patterns) are cheap and doctrine-critical.
