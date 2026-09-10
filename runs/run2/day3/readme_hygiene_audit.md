# README + Repo Hygiene — Final Audit (ship-v1.0 gate)

- **Auditor:** final validation swarm, README/hygiene seat (agent-314)
- **Date:** 2026-09-10, machine unclamped, demo stack live on :8177
- **Scope:** read-only except `README.md` (edited in place, fixes below). No git mutations.
- **Verdict: PASS with fixes applied.** README is now consistent with the final locked numbers (P 0.976 / R 0.836 / κ 0.513) and a stranger can run the project top-to-bottom. No secrets anywhere in repo or history. Three hygiene nits (SEV3, need git mutations → out of my edit scope, listed in §4). One **SEV2 demo-ops finding**: the live :8177 stack is NOT in pre-state right now — the pre-state restore must be re-run tomorrow morning (§5).

## 1. README — verified accurate (no change needed)

| Claim | Evidence |
|---|---|
| Architecture mermaid diagram present, dev/runtime split | README.md L15–35; matches ARCHITECTURE.md + DECISION_LOG D5/D12/D18 |
| Derived-test op point P 0.8000 · R 0.9748 · F1 0.8788, n=17,731 | exact match vs `artifacts/models/masked-v2/metrics.json` → `operating_point_test_tuned` (0.8000288 / 0.9748002 / 0.8788095) |
| McNemar vs zeroshot qwen3:8b p = 0.0018; vs TF-IDF p = 0.122 n.s. | KB §11 (runs/run2/kb/KNOWLEDGE_BASE.md) |
| Near-dup: cosine 0.91, 70,398-vector MiniLM index, p95 3.8 ms | KB §9 |
| Gold composition 300 OSHA (incl. 150 oil-gas) + 100 ASRS + 100 synthetic, 20 pilot | `artifacts/gold/gold_items.jsonl` strata counted: 300/100/100, 20 pilot; `sample_manifest.json` oil_gas_sampled=150, double_design 90+30+30 |
| System requirements: Python 3.14 | actual: CPython 3.14.6 (system + .venv) |
| Offline/USB packaging paragraph | `packaging/make_tarball.sh`, `install.sh`, `selfcheck.sh`, `manifest.md` all exist; selfcheck 2-clean-cycles claim matches `runs/run2/day2/demo_final_state.md` |
| Claim boundary / what-this-is-not section | present, consistent with triage-not-prediction doctrine (D14) |

## 2. README — stale, FIXED in place (only file edited)

| # | Was | Now | Source of truth |
|---|---|---|---|
| 1 | Quickstart led with `./run.sh`; first-time setup came after — a stranger on a fresh clone hit the preflight error first | First-time setup (venv + `npm ci && npm run build`) moved above `run.sh`; system requirements lead the section | run.sh preflight order (L78–82) |
| 2 | Latency row: p50 11.9 / p95 19.7 / p99 40.2 ms — **masked-v1** numbers, superseded | p50 11.4 / **p95 17.7** / p99 20.5 ms (masked-v2 int8 ship path, model-only) | `runs/run2/day2/latency_v2_final.md` headline table |
| 3 | Bulk ingest: 37.3 reports/s, 135.3 s | **45.6 reports/s** (5,050-row CSV → 5,048 accepted, 110.8 s) | same doc, row 6 (post-BLAS-fix remeasure) |
| 4 | Adversarial suite 17/17 | **18/18** | `tests/adversarial_suite.py` CASES counted via AST = 18; CHECKPOINTS Sep 9 21:05 + T-6h gate both say 18/18 |
| 5 | Gold row described the *plan* ("690 judgments…") and omitted the arbiter's verdict | New row **"Blind human gold — FINAL (2026-09-10)"**: real-pooled n=318 **P 0.976 [0.948, 0.989] · R 0.836 [0.788, 0.874] · F1 0.900**, κ 0.513 ± 0.066 (130 doubles), ASRS R 0.00 OOD disclosed, synthetic P 0.347 never pooled, 93 pending adjudication, links `artifacts/gold/gold_metrics_final.md` | `artifacts/gold/gold_metrics_final.{json,md}`, `agreement_final.json` |
| 6 | Op-point row: "blind human gold set is the arbiter" (future tense) | "the blind human gold verdict is the next row" | the arbiter has ruled |
| 7 | Mermaid named 7 sentinel gates; 9 ship | "9 sentinel gates: confidence · negation · language · near-dup · drill · codes · well-control · long-input · chunked-low-score" | `app/gates.py`: 9 `gate_*` functions (well_control_watch added Sep 9 21:05, chunked_low_score = D29) |
| 8 | Honest-claims preamble cited KB §10/§11 only | §10–12 + latency_v2_final.md | gold results are KB §12 |

## 3. Quickstart — verified working in order

- `./run.sh` executed live: preflight found the model (`artifacts/models/masked-v2/sif_multitask_int8.onnx`), detected the running uvicorn (pid 227391, started via run.sh), printed "already running" and exited 0 — idempotent, no state touched. `GET /api/health` → `{"status":"ok","classifier":"RealOnnxClassifier","model_version":"onnx:masked-v2/sif_multitask_int8.onnx"}`.
- First-time-setup products all present: `.venv/bin/python` (3.14.6), `dashboard/dist/index.html` (built), model artifact (152 MB int8). `node v26.4.0` / `npm 12.0.2`, `dashboard/package.json` has `build: tsc -b && vite build`, `requirements.txt` present. `npm ci` / `pip install` not re-run (network + churn risk on demo eve; products verified instead).
- `--stop` semantics read and confirmed pidfile-scoped (only kills what run.sh started; external ollama never killed). Not executed — stack must stay up.

## 4. Repo hygiene

**Secrets: CLEAN.** Scanned working tree (excluding .git/.venv/node_modules) AND full `git log -p --all` for: `sk-[A-Za-z0-9]{20,}` (DashScope format), `hf_*`, `ghp_*`/`gho_*`, `AIza*`, `sk-ant*`, `AKIA*`, plus `api_key|secret|password|bearer` in history. Zero key material. Only `sk-` tokens in history are innocuous prose ("sk-matrix", "sk-SIH26047"). "DashScope" appears only as provider name in CHECKPOINTS.md. `gold/llm_panel*.py`, `adjudication_panel.py`, `app/config.py` contain no key handling. Sole tracked env file `dashboard/.env.production` is intentionally empty (`VITE_API_BASE=` with rationale comment — SEV1-2 fix D26). **The DashScope key was never committed.**

**.gitignore coverage:** `.venv/` ✓, `artifacts/` ✓, `node_modules/` ✓, `dist/` ✓, `.run/` ✓, `app/runtime.db` ✓, tarballs ✓, wheels ✓.

Findings (all SEV3; need `git rm --cached`/`.gitignore` edits — outside my README-only mandate, no action taken):

1. **SQLite sidecars tracked.** `app/runtime.db-shm` and `app/runtime.db-wal` are tracked (committed in a850e42) and show modified in `git status` right now. `.gitignore` covers `app/runtime.db` but not the `-wal`/`-shm` siblings. Fix: add `*.db-wal` / `*.db-shm` (or `app/runtime.db*`) and `git rm --cached` both.
2. **`.playwright-mcp/` committed: 133 tracked files** of browser-tool session dumps (page-*.yml, console-*.log), plus 3 new untracked today. Fix: gitignore the dir + `git rm -r --cached .playwright-mcp`.
3. **Root strays tracked:** `audit_beat1_contrast_red.png`, `money_beat_before.png`, `snap_green1.md` — audit-wave screenshot leftovers at repo root (their siblings live properly in `runs/run2/day2/`). Fix: delete or move under `runs/`.
4. Not findings, for the record: `runs/run2/day2/explain_cache_fix/*.db` are intentional evidence snapshots of the cache-poisoning fix — keep. `CPU_CLAMP_REPORT.md`, `HANDOFF.md` at root are referenced by runbooks — keep. `/tmp` references in tracked docs: only RESUME.md's cloudflared step (see §5). `_fix_*.py` under artifacts/ are gitignored ✓.

## 5. Runbooks for tomorrow morning

**`gold/RUNBOOK_HUMANS.md` — accurate for the session it describes; the session is DONE.** All referenced scripts exist and are runnable (`start_labeling.sh`, `export_labels.py`, `adjudicate.py`, `compute_gold_metrics.py`, `simulate_labeling.py`, `RUBRIC.md`). Labeling servers on 8001–8004 still up (left running per instructions). Divergences vs current state, none blocking: (a) the adjudication section describes a human session that was superseded by the D30 LLM panel (documented in DECISION_LOG D30); (b) its after-session commands reference the `_all4` files — those still exist and run, but the FINAL compute used `labels_merged_final.jsonl` / `agreement_final.json` → `gold_metrics_final.*` (post C-relabel). As a historical protocol record it is correct; nothing tomorrow depends on it.

**`runs/run2/RESUME.md` — STALE; do not hand to anyone as-is.** Written for the Sep 8→9 freeze. For tomorrow: (a) step 1 (start labeling) is obsolete — gold is complete; (b) step 2 references `/tmp/cloudflared` — **file no longer exists** (moved to `~/.local/bin` per CHECKPOINTS Sep 9 08:00; tunnels unneeded anyway); (c) step 3 `./run.sh` works (verified §3) **but RESUME omits the critical pre-state restore** — see below.

**SEV2 — live stack is NOT in pre-state (briefing said it was).** Measured now: health `n_reports=5051` (was 5050 minutes earlier — the DB is being written live, presumably by fellow auditors), density #1 = **Kathalguri GCS n=213** — that is the POST-money-beat state. The documented pre-state is 4,548 reports with Kathalguri **#2** (n=88) behind Moran GGS-1 (98). I verified `artifacts/demo/demo_pre.db` reproduces it exactly (4,548 reports/predictions/embeddings, 0 overrides; density replay at the ship threshold: #1 Moran 98/98, #2 Kathalguri 88/88 — byte-for-byte the post-restore acceptance in `runs/run2/day3/final_packaging.md` §3). **Tomorrow-morning mandatory sequence** (procedure verified, exists only in final_packaging.md:55 — RESUME.md lacks it):

```bash
./run.sh --stop
rm -f app/runtime.db-shm app/runtime.db-wal
cp artifacts/demo/demo_pre.db app/runtime.db
./run.sh        # expect health n_reports=4548; density #1 Moran GGS-1, #2 Kathalguri GCS
```

Plus the CPU-clamp one-liner from `CPU_CLAMP_REPORT.md` (platform_profile kick) as the first morning check.

## 6. Bottom line

- README: **ship** — quickstart runnable in order, claims table now carries the final gold verdict, diagram and doctrine intact.
- Secrets: **none**, in tree or history.
- Hygiene: 3 SEV3 cleanups deferred to whoever owns git mutations (sidecar ignore, .playwright-mcp purge, root strays).
- Demo ops: **run the pre-state restore tomorrow morning** — the live DB has drifted past the money beat.
