# RUNBOOK — Human Gold Labeling Session (tonight, 20:00 IST)

PS 26165 · gold set v1.0 (frozen) · `artifacts/gold/gold_items.jsonl` (500 rows)
Spec: `spec/label_spec.yaml` `gold.labeling` · Rubric (READ FIRST): `gold/RUBRIC.md`

**Cast:** 4 labelers (a, b, c, d) + 1 admin (can be one of the four, admin duties
are before/after labeling only). **Time budget:** ~3.5–4 h wall clock,
~690 judgments total (6–8 person-hours, per decision D7).

**Queues:** each labeler gets 169–177 items = the SAME 20-item calibration pilot
first, then their own ~150-item shuffled queue. Nobody sees anyone else's labels.
The app shows ONLY the masked report text + title. There is no stratum, no id
beyond the opaque `G0xxx`, no model output. There is nothing to peek at — by design.

---

## Blind protocol (hard rules — verbatim from RUBRIC.md, these bind all night)

1. **Do not discuss any item** with other labelers until the export is
   frozen. Your disagreements are data — they get measured (Fleiss' κ) and
   adjudicated later against this spec, not negotiated live.
2. **No external lookups of report text.** Do not search phrases from a
   report to find the original record — that unblinds you.
3. One judgment per report; **no going back** after saving.
4. Label only on your own port/app instance; your file is yours.

The ONE exception to rule 1 is the scheduled pilot calibration discussion
(20:40 below) — pilot items only, main-queue items never.

---

## Setup (admin, 19:50)

```bash
cd /home/dakkshesh/sih26-round2
./gold/start_labeling.sh          # starts all four, prints URLs + progress
./gold/start_labeling.sh --status # anytime health check
```

Manual alternative (4 terminals, one per labeler):

```bash
.venv/bin/python gold/labeler_app.py --labeler a --port 8001   # terminal 1
.venv/bin/python gold/labeler_app.py --labeler b --port 8002   # terminal 2
.venv/bin/python gold/labeler_app.py --labeler c --port 8003   # terminal 3
.venv/bin/python gold/labeler_app.py --labeler d --port 8004   # terminal 4
```

Each labeler opens THEIR url and only theirs:

| Labeler | URL |
|---|---|
| a | http://127.0.0.1:8001/ |
| b | http://127.0.0.1:8002/ |
| c | http://127.0.0.1:8003/ |
| d | http://127.0.0.1:8004/ |

Keys: **S** = SIF-potential (then optionally tick Life-Saving Rules + one-phrase
reason, **Enter** saves) · **N** = non-SIF (saves immediately) · **U** = unsure
(saves immediately).

---

## Schedule

| Time (IST) | What | Details |
|---|---|---|
| 20:00–20:15 | Read `gold/RUBRIC.md` | Everyone, end to end, in silence. Questions about the *rubric* are allowed now; questions about *items* never are. |
| 20:15–20:40 | **Pilot: label the first 20 items** | Marked `[calibration pilot]`. Same 20 for everyone. NO discussion while labeling. ~60 s/item. |
| 20:40–21:05 | **Calibration discussion** (pilot only) | Admin runs `.venv/bin/python gold/export_labels.py` and reads out the `n=4 raters` line (pilot agreement). Then align on — see below. |
| 21:05–22:05 | Main block 1 | ~70 items. No talking about items. |
| 22:05–22:15 | Break | Step away from the screen. |
| 22:15–23:00 | Main block 2 | ~60 items. |
| 23:00–23:10 | Break | |
| 23:10–23:45 | Finish remainder + buffer | Anyone done early: do NOT discuss, do not hover over others' screens. |
| 23:45 | **Admin: export + freeze** | Commands below. After this, labels are frozen — adjudication is a separate later step per spec. |

### Calibration discussion — what to align on (20:40)

Walk the pilot items where the group split. For each, resolve by **citing the
rubric**, not by voting. Align on interpretation, not on answers:

- **The one question:** could this have plausibly killed or permanently injured
  someone if circumstances were slightly different? Judge exposure, never outcome.
- **Drills/exercises → N.** **Negation is real** ("the guard held") → usually N.
- **Passing mention ≠ exposure** — tag only what the text describes happening.
- **`[OUTCOME]` blanks:** don't guess the injury; judge the mechanism around the blank.
- **U discipline:** U is allowed and honest — use it when you genuinely cannot
  tell. Don't force S/N. But when torn between S and N, judge the mechanism:
  high-energy exposure present → S.
- **Rule tags:** optional but encouraged; only rules whose exposure is actually
  in the text.

### Pace

Target **60–80 items/hour (45–60 s/item)**. The main queue is ~150 items ≈
2–2.5 h. If you notice yourself taking >90 s per item consistently, take 5
minutes — fatigue labels are noise, and noise is what the doubles measure.

---

## Admin: export + expected outputs (23:45)

```bash
.venv/bin/python gold/export_labels.py             # merge + Fleiss' κ + bootstrap SE
.venv/bin/python gold/export_labels.py --self-test # kappa implementation check (must print PASS)
```

Expected outputs:

| File | Expect |
|---|---|
| `artifacts/gold/labels/labeler_{a,b,c,d}.jsonl` | one line per judgment; 169–177 lines each |
| `artifacts/gold/labels_merged.jsonl` | 500 rows (one per gold_id) with all labels + agree flag |
| `artifacts/gold/agreement.json` | `double_labeled` subset (~130 items, n=2 raters): Fleiss' κ ± bootstrap SE; `n_raters_4` (20 pilot items) reported separately |

Interpreting κ (guidance, not spec): ≥0.6 = solid human agreement, proceed;
0.4–0.6 = usable but schedule the adjudication session promptly; <0.4 = flag to
eval lead before any model-vs-human comparison. Raw agreement % is in the same
file. **After export, labels are frozen** — no edits; disagreements go to
adjudication citing the frozen spec (spec: "3rd labeler cites frozen spec").

---

## When things go wrong (all verified in the dry run)

- **Accidentally closed the browser / app crashed / laptop slept:** reopen your
  URL or restart with the same command — the app resumes at your first
  unlabeled item. Progress is never lost (append-only files).
- **"cannot bind … already running" on startup:** an instance is already up on
  that port. Open its URL (that IS your session), or `./gold/start_labeling.sh
  --stop` then start again.
- **Mis-save (fat-fingered N instead of S):** no going back in the app — write
  down the `G0xxx` id + approximate time, tell the admin. Admin fixes that one
  JSONL line BEFORE the 23:45 export (export keeps the latest record per item).
- **App feels stuck:** progress check `./gold/start_labeling.sh --status` shows
  `done/total` per labeler without exposing any content.
- **Tempted to google a report phrase:** don't — that's rule 2, and it's the
  load-bearing rule for the whole eval's credibility.

## Reset / dry-run tooling (admin only, NOT tonight)

`gold/simulate_labeling.py` replays a full 4-labeler session + adversarial ops
cases against throwaway ports; `--reset` wipes all label files. Already run and
reset — tonight starts clean. Do not run it after humans have labeled (it
refuses unless `--force`).
