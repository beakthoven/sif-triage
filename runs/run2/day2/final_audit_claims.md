# FINAL AUDIT — HONEST-CLAIMS LENS (PS 26165, Phase 3 gate)

- **Date:** 2026-09-09 · **Lens:** honest-claims auditor (fresh-eyes swarm, 1 of 6)
- **Scope:** HANDOFF.md §B.6 never-say list · runs/run2/ARCHITECTURE.md claim boundary · README.md · dashboard UI copy (src + built dist) · docs/deck/deck.md · artifacts/demo/script_90s.md · app/ API-facing copy. Every finding below was re-verified against a primary artifact or the live stack (`:8177` probed read-only: `GET /api/health`, `GET /api/rules` only).
- **Verdict up front:** the claims discipline is fundamentally intact — no accuracy language, no "SIF DETECTED", no red card, PTW/Bypassing declared, baselines slide correctly discloses tfidf n.s. **No SEV1.** Two SEV2 sentence-level fixes (phantom spans in the demo script; the causal masking claim) plus a cluster of SEV3 wording/fact fixes. All fixes are one-line edits; none touches code logic.

---

## A. Verified CLEAN (checked, evidence cited)

1. **No "X% accuracy" / prediction framing anywhere user-visible.** Grep of `dashboard/src`, `dashboard/dist/assets/*.js`, `docs/deck/deck.md`, `README.md`, `app/`: zero "% accuracy" claims; the only "accuracy" column is the internal baselines comparison table (deck slide 9), which is labeled as a derived-label proxy sample with the gold set named as arbiter. Band copy is `▲ HIGH REVIEW PRIORITY` (amber `bg-primary`, `dashboard/src/components/band-badge.tsx:21`); score is labeled "triage score" (`phrasebook.ts:23`); footer is "Model proposes, HSE disposes" (`phrasebook.ts:19-22`).
2. **Never-say #2 ("learned from 106k reports like OIL's") — inverted correctly.** Deck slide 6 (`docs/deck/deck.md:106-118`) labels OSHA "US proxy data — NOT OIL data", ASRS "cross-industry proxy", synthetic "disclosed, never pooled", and states "No real OIL data exists in this project."
3. **Never-say #3 (LLM circularity) — clean.** κ is human-vs-human Fleiss' (deck slide 8, `spec/drafts/protocol_draft.md:109`); contamination separation documented (deck appendix, protocol B6).
4. **20% citation — corrected on every ship surface.** Deck slide 3 (`deck.md:44-47`) says "~20% of recordable injuries … (BST/Mercer ORC 2011; Martin & Black 2015)" with an explicit speaker warning against the "20–25% of near-miss reports" misquote; README.md:105-107 and ARCHITECTURE.md:125 match. (One residual instance in HANDOFF.md — see C4.)
5. **PTW / Bypassing declared, never faked.** Live `GET /api/rules` returns `"work_authorisation","display":"Work Authorisation (Permit to Work)","in_scope":false,"threshold":null` and `"bypassing_safety_controls",…,"in_scope":false`; UI renders "Declared out-of-scope (never scored)" (`triage-card.tsx:121-125`); deck slide 11 carries the honesty line.
6. **"Beats zero-shot" wording — exactly defensible.** Deck slide 9 (`deck.md:184-200`): regex "fine-tune wins, p ≈ 1e-68"; zero-shot "**fine-tune wins, p = 0.0018**"; TF-IDF "n.s. (p = 0.122) — **disclosed**". Re-verified from `runs/run2/day2/ship_eval/mcnemar_6model.json`: zeroshot↔ft-v2-st p_holm = 0.0018 ✓; tfidf↔ft-v2-st p_holm = 0.1224 ✓; regex↔ft-v2-st p_holm = 6.4e-68 ✓. No "beats all baselines" claim exists anywhere. The 1,083× latency ratio is arithmetically exact (13.0 s/row ÷ ~12 ms) ✓.
7. **Labeler blindness (hard constraint).** `gold/labeler_app.py` serves only `masked_text` + `event_title` (lines 10-12, 101-103, 169-170); `gold/compute_gold_metrics.py:31` — "The queue is BLIND: no stratum, no model output." No path from `artifacts/gold/model_scores.jsonl` to the labeling UI.
8. **Deck numbers spot-verified against primary artifacts:** P 0.8000/R 0.9748/F1 0.8788 ✓ (ship_decision.md §1); flag rate 78.3% = 13,877/17,731 ✓; demo flag rate 71.0% = 3,584/5,048 ✓; p95 19.7 ms ✓ (KB §10); 37.3 reports/s bulk ✓ (demo_final_state.md §1); int8 artifact 152 MB ✓ (151,989,330 B); near-dup index 70,398 ✓ (`wc -l artifacts/embeddings/corpus_ids.jsonl`); training 4.19 + 1.11 GPU-h ✓ (training_report.md:64-66, retrain_report.md:32); money-beat 65/65 + 31 pre-seed = 96, min 0.7601 ✓ (demo_final_state.md §1).
9. **Explanation layer claim-safe.** Templates say "flagged for HSE review" / "below the review threshold" (`app/explain.py:106-109`); the LLM system prompt forbids prediction/prevention language (`explain.py:71`); quoted spans are exact-substring validated with score-preservation checks.
10. **Offline placeholder honesty.** API-down path shows "API unreachable — offline placeholder, not a score" (`phrasebook.ts:55-58`); density view refuses to swap in mock numbers on live failure (`density.tsx:166-170`).

---

## B. SEV2 findings (fix before slides freeze / rehearsal)

### B1. Demo script Beat 1 narrates evidence spans that do not render on the live card
- **Where:** `artifacts/demo/script_90s.md:45-46` — *"(Card: amber HIGH band, triage score, LoF bar dominant, spans on "fell past the drill floor" / "near two roughnecks".)"* and the SAY line "shows you exactly why, in the report's own words" (line 43-44).
- **Evidence:** live browser verification recorded zero spans on `contrast-red` (`runs/run2/day2/demo_final_state.md:24` — Spans "— (see §5 O1)"); root cause in §8.1 (ibid. line 75): the v2 span head never crosses the 0.5 token threshold on demo texts (max ~0.37) and the frozen spec keyword LF deliberately excludes "fell"/"dropped" → the keyword fallback finds nothing → no highlight. The expectation "fell past the drill floor" survives only in the demo-pack annotation (`artifacts/demo/demo_corpus.jsonl`, `contrast-red.expected.spans_highlight`), not in the product.
- **Why SEV2:** on stage the narrator points at highlighted text that isn't there — a live, visible claims-reality mismatch in the opening (money) beat.
- **Fix (pick one, tonight):**
  - **(a) Narration fix (zero code, safest):** replace the SAY sentence with: *"Nobody is hurt. The system flags it HIGH review priority, puts Line of Fire at the top of the rule bar, and — because our frozen keyword list deliberately excludes falling-object words — shows you the score with no invented highlight rather than a wrong one. Highlights fire where the evidence vocabulary is explicit, like this next card."* Then move the span moment to `wc-baghjan-3` (verified live span `Welding`, demo_final_state §2 card 7).
  - **(b) Spec fix (needs the frozen-spec adjudication already flagged in demo_final_state §8.1):** add a falling-object family to the LoF keyword LF, regenerate highlights, re-run `selfcheck_demo_pack.py`. Do NOT hack the app mirror.
  - Either way, delete the parenthetical span list from Beat 1 unless it matches the rehearsal screenshot pixel-for-pixel.

### B2. The masking claim asserts a causal effect the ablation does not support
- **Where:** `docs/deck/deck.md:140-141` (slide 7) — *"Outcome masking: outcome/severity words are token-neutralized ([OUTCOME]) in positives AND negatives, so the model reads **mechanism, not injury lottery**."* Same sentence in `artifacts/demo/script_90s.md:126-127` (Beat 7 bonus line).
- **Evidence:** D11 (`DECISION_LOG.md:20`) ruled this inference invalid — mechanism text is a near-deterministic proxy for outcome within strata (P(amputation) 0.007–0.82 across fixed EventTitle strata); the ablation is **robustness evidence, not "mechanism not outcome" proof** (ARCHITECTURE.md:128; protocol_draft.md:36). Measured: masked ≈ unmasked on val (ΔAUC +0.0001, KB §10); masked 0.8819 vs unmasked 0.8708 on the 1,500-sample test (DECISION_LOG:84). "So the model reads mechanism" is exactly the overclaim the adjudication banned.
- **Fix (exact replacement, deck slide 7):** *"Outcome masking: outcome/severity words are token-neutralized ([OUTCOME]) in positives AND negatives — a hygiene control so outcome vocabulary is unavailable as a shortcut at training time. Masked vs unmasked ablation: ΔAUC ≈ 0.00 on val, +0.011 on test — robustness evidence, not proof of mechanism-reading."*
- **Fix (script Beat 7 bonus line):** *"we mask outcome words at training time so the model can't shortcut through injury vocabulary — the masked/unmasked ablation is in the deck as robustness evidence."*

---

## C. SEV3 findings (fix same pass; cheap)

### C1. "Runs air-gapped: demo verified with the network physically unplugged" — unverified past-tense claim
- **Where:** `docs/deck/deck.md:221` (slide 10, the "honest claims" slide — worst possible slide for an unverified claim).
- **Evidence:** no record of a physical-unplug test exists (`grep -i 'unplug|ethernet|external request'` over `runs/run2/day1/e2e_report.md` and `runs/run2/day2/demo_final_state.md` → nothing; the e2e report's offline test is API-down simulation). The unplug is a *planned* T-30min checklist item (`script_90s.md:24`: "Playwright offline run confirmed zero external requests").
- **Fix:** either perform the unplug test at tomorrow's rehearsal and keep the line, or reword now: *"Runs air-gapped by design — zero external requests in the demo path; physical-unplug rehearsal on the checklist."* Do not ship the past-tense version unverified.

### C2. Slide 7's "span token-F1 0.9709" hides the dead-span-head reality
- **Where:** `docs/deck/deck.md:133-134` (slide 7, under "verified numbers").
- **Evidence:** KB §11 (`runs/run2/kb/KNOWLEDGE_BASE.md:122`): "Span head is effectively dead at runtime (max token prob ~0.3, fires on punctuation; **val token-F1 0.995 does not reproduce**) → the D2 keyword-attribution fallback is the de-facto live path." Quoting 0.9709 val token-F1 without that context invites the Q&A kill-shot "show me a learned span on this card" — the honest answer is keyword anchoring. Slide 8's gold placeholders (substring-validity + keyword-anchor precision, `deck.md:167-169`) are already correctly scoped; slide 7 must match.
- **Fix (exact replacement):** *"Val (derived labels, saturated — disclosed as such): AUC 0.9969 · rules macro-F1 0.9645. Span head: weak-supervision agreement 0.97 on val — at runtime the span head stays under threshold and highlights ship via the keyword-attribution fallback (substring-validity 100%, self-validated); gold span quality is measured against the shipped path."*
- **Doc hygiene (optional, one line):** ARCHITECTURE.md:87 still reads "evidence spans (span head; …)" — amend to "(span head with keyword-attribution fallback; fallback is the de-facto live path — KB §11)".

### C3. "It reads exposure, not keywords" slogan is contestable on our own slide 9
- **Where:** `artifacts/demo/script_90s.md:54-55` (Beat 2: "It reads exposure, not keywords. That is the difference between triage and a word matcher.") and `docs/deck/deck.md:255` (slide 12).
- **Why:** slide 9 itself discloses TF-IDF (a word-count model) is statistically indistinguishable from the fine-tune (p = 0.122), and the visible highlight layer *is* keyword anchoring (B2/C2). A sharp judge can turn the slogan against us in one move.
- **Fix (exact replacement, both places):** *"Same spanner. Same height. Only the exposure changed — and the score followed the exposure: 0.93 to 0.01."* (Both numbers verified live — demo_final_state §2 cards 1-2. This claims observed behavior, not mechanism.)

### C4. Surviving "20–25% of reports" misquote in HANDOFF.md §A.1
- **Where:** `HANDOFF.md:29` — *"leading operators flag the ~20–25% of reports with genuine fatal potential"* (inside the quoted mission context).
- **Why not higher:** HANDOFF is a historical internal doc and ARCHITECTURE.md:125 + deck slide 3 carry the correction; but it is the first file every agent/deck-author reads, and DECISION_LOG SEV1-12 exists precisely because this phrasing propagates.
- **Fix (one inline annotation):** append after the sentence: `[CORRECTED 2026-09-08: the sources say ~20% of *recordable injuries* (BST/Mercer ORC 2011; Martin & Black 2015) — see ARCHITECTURE.md claim boundary. Never quote the 20–25%-of-reports form.]`

### C5. "SIF rate" column labels in the live UI
- **Where:** `dashboard/src/views/density.tsx:243` (table head "SIF rate", rendered "x per 100") and `dashboard/src/views/patterns.tsx:13,93`.
- **Why:** the number is the model's *flag* rate, not a rate of serious injuries — "SIF rate" on a ranked table reads as "this site has a 100% serious-injury rate" (the money-beat cell literally shows rate 1.0000). One ambiguous word away from a prediction claim.
- **Fix:** rename to "Flag rate" (header) / "flagged per 100" (unit). Two-line copy change in each file + rebuild (`cd dashboard && npm run build`).

### C6. Synthetic demo data is not labeled synthetic on the demo screen
- **Where:** the live dashboard shows 5,048 seeded reports under real OIL installation names (Kathalguri GCS, Moran GGS-1, Baghjan EPS, Duliajan) with the header chip `LIVE · onnx:masked-v2/… · 5048 reports` (`App.tsx:117`) and no synthetic marker; the six ingested "Baghjan EPS" rows are dated 2026-09-07 (`density.tsx:24-63`). Script Beat 5 says "Five thousand historical register rows" (`script_90s.md:95`) — "historical" implies real records.
- **Why not higher:** provenance IS disclosed on deck slide 6 ("No real OIL data exists in this project"), the ingest confirm dialog says "demo batch" (`phrasebook.ts:28`), the cards carry `provenance.kind: "synthetic"` internally, and the near-dup banner story partially covers it. But §B.6 says "never present mock/synthetic data as real **without labels**", and the screen is what judges photograph.
- **Fix (two parts):** (a) script Beat 5 line → *"Five thousand register-style rows — synthetic stand-ins for the Excel files every installation keeps."* (b) optional UI: append "· synthetic demo data" to the footer string in `phrasebook.ts:19-22`, or a small chip next to the LIVE badge. One-string change + rebuild.

### C7. Slide 11: "37-string QA'd phrasebook" — wrong count
- **Where:** `docs/deck/deck.md:241`. **Measured:** 33 keys in `dashboard/src/lib/phrasebook.ts` (script-counted). **Fix:** "33-string" (or "~30-string" to match ARCHITECTURE.md:104).

### C8. Script header stale on the CPU clamp
- **Where:** `artifacts/demo/script_90s.md:4` — "p95 ≈ 10–120 ms depending on clamp". **Evidence:** clamp RESOLVED 2026-09-08 (KB §8, CPU_CLAMP_REPORT.md); measured p95 19.7 ms (KB §10); live card latencies 30–233 ms incl. explanation fetch (demo_final_state §2). **Fix:** "live-classify only single pastes (measured p95 19.7 ms classify-only; ~35 ms with cached explanation)".

### C9. Slide 5 source line misattributes the synthetic count
- `docs/deck/deck.md:98-100` cites `synthetic_qa_report.md §11.2` for "9,687 synthetic" — that report's figure is 6,684 (its scope was the v1 merge, line 15). The number 9,687 is correct for the ship model (9,187 v3 pool per KB §9 + 500 first-aid negatives per retrain_report.md:5; 61,378 + 9,687 = 71,065 ✓). Source lines are deleted in the render, so this is paper-trail hygiene: re-point to `retrain_report.md` + KB §9.

### C10. Slide 3's premise sentence sits in tension with its own citation
- `docs/deck/deck.md:48-50`: "the same high-energy mechanisms … show up in near-miss and minor-injury reports **long before** the serious event." Martin & Black's finding (cited one bullet above) is that low-severity incidents do *not* reliably share causes with SIFs; the temporal "long before" claim is uncited. **Fix:** reframe as the tested hypothesis: *"Our working hypothesis — the one the gold set tests: high-energy mechanisms leave readable traces in near-miss and minor-injury reports before the serious event."*

### C11. Completeness notes (not overclaims)
- `docs/deck/deck.md:253` references `docs/deck/demo_card.md` — file does not exist (only `deck.md` in `docs/deck/`).
- README.md:15 and :91 still carry `<!-- TODO -->` placeholders (architecture diagram, full claims table) against the acceptance-bar item "README with architecture diagram + honest-claims section" (ARCHITECTURE.md:144).

---

## D. What was explicitly NOT found (negative results, for the record)

- No "detects SIF" / "SIF DETECTED" / "% accuracy" / "predicts fatalities" string in any ship surface (src, dist, deck, script, README, app). The only "detected" strings are Sentinel-gate sentences describing regex gates ("'No injury' phrasing detected", "Drill or exercise language detected") — gate-language, not capability claims. The app title "SIF-Precursor Detection Engine" mirrors the PS's own title; the subtitle/footer carry the triage framing — acceptable.
- No red card semantics anywhere: bands are HIGH/MODERATE/LOW REVIEW PRIORITY on amber/slate; override buttons are equal-weight Confirm / Not-SIF.
- No "beats all baselines" or undisclosed tfidf margin.
- No model output reachable from the labeling path; no gold-label content touched by this audit (ports 8001-8004 and `artifacts/gold/labels*/` untouched; only read-only GETs against :8177).
- No synthetic row presented as real in the *data pipeline* artifacts — provenance fields are clean throughout; the gap is UI-visible labeling only (C6).

## E. Fix cost summary

All 11 actionable items are one-line to one-paragraph edits in 5 files (`docs/deck/deck.md`, `artifacts/demo/script_90s.md`, `dashboard/src/lib/phrasebook.ts`, `dashboard/src/views/density.tsx`, `dashboard/src/views/patterns.tsx`) + optional HANDOFF/ARCHITECTURE annotations + one dashboard rebuild. Nothing requires retraining, re-measurement, or code-logic changes. Total effort < 1 hour. B1 must land before tomorrow's rehearsal; B2/C1 before slides freeze.

<<SCORES {"ps":"26165","role":"honest-claims-auditor","go_no_go":8,"severity":3,"feasibility":9,"data_risk":7}>>
