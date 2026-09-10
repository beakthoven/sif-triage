# Final packaging + fallback recording — 2026-09-10 (day 3, pre-15:00 IST)

Machine unclamped. Stack: `./run.sh` → uvicorn 127.0.0.1:8177 + ollama 127.0.0.1:11434,
RealOnnxClassifier `masked-v2/sif_multitask_int8.onnx`. All work done on the live stack,
then restored to PRE-STATE.

## 1. USB tarball

- `dashboard/dist` freshness: fresh `npm run build` (vite, 184 ms) produced **byte-identical
  hashes** to the existing dist — `index-CSs9oXmp.js` sha256 `38156130…cc3337a`,
  `index-CSfiQMt9.css` `7f75211a…0b53a133`, `index.html` `a8934fa9…4bf8ed`. Today's
  dashboard (light redesign) is what ships.
- Built: `packaging/make_tarball.sh` → **`packaging/sif-demo-usb-20260910.tar.gz`**
  - size: **775,426,622 bytes (740M)**, 172 entries
  - sha256: **`3c5690d774649db9f96b3f7875d572c405063fbd3d66f0ebfaa8ec8f31b005d9`**
  - payload verified inside: `artifacts/models/masked-v2/sif_multitask_int8.onnx`,
    `masked-v2/thresholds.json` + `manifest.json`, today's `dashboard/dist`
    (`assets/index-CSs9oXmp.js`, `live_ingest_500.csv`), `app/`, `artifacts/patterns`,
    `spec/label_spec.yaml`, `requirements.txt`, `run.sh`, `packaging/{install,selfcheck,manifest}.*`,
    `packaging/wheels`. No `--allow-mock` (real ONNX found, no warning emitted).
  - previous build `sif-demo-usb-20260908.tar.gz` left in place as history; the 0910
    build is the ship candidate.

## 2. Selfcheck

`packaging/selfcheck.sh` → **SELFCHECK PASS (2 clean cycles)**, real model (no mock flag —
ONNX artifact detected):

| cycle | startup (start→health 200) | classifier | classify | dashboard | stop |
|---|---|---|---|---|---|
| 1 | 1.556 s | RealOnnxClassifier | sif_score 0.2025, spans valid, well_control on | index.html + `/assets/index-CSs9oXmp.js` 200 | port free, pidfiles cleaned |
| 2 | 1.559 s | RealOnnxClassifier | same contract pass | same | same |

Span invariant `text[start:end]==span.text` held on both cycles.

## 3. Fallback recording

- **`artifacts/demo/fallback_recording.webm`** — 1920×1080 VP8, **91.0 s**, 8,994,067 bytes.
  ffprobe-verified (non-zero duration, plays).
- Harness: `runs/run2/day3/fallback_record.cjs` (headless Chromium via
  `NODE_PATH=/home/dakkshesh/.npm/_npx/86170c4cd1c5da32/node_modules` — that playwright
  1.63.0-alpha matches the installed chromium_headless_shell-1243; the older
  `/home/dakkshesh/sih/dashboard/node_modules` playwright 1.62.1 expects build 1234 and
  does NOT launch). Recorded in one tight headless pass (MCP-interactive recording was
  tried first and discarded: real-time MCP pacing produced a 42-min video).
- Beat log (wall s): 5.7 feed settle · 13.2 green LOW (0.01) · 21.6 red HIGH (0.93, LoF 0.85,
  WC chip) · 25.2 density pre-state (Kathalguri #2, 88/88) · 33.2 ingest progress ·
  49.2 **money beat** ("accepted 500/500 · Kathalguri GCS just climbed to #1", 213/213 +1,
  Moran 105/105 −1) · 57.5 verbatim-OSHA near-dup banner ("Matches a training record —
  memory, not generalization", cosine=1.000 row 4798) · 64.0 gray drill GATE card ·
  74.1 explanation expander ("Why this score?", LLM-phrased cached) · 83.1 patterns
  Site×Activity→Activity×Barrier toggle · 91.1 review tab (Awaiting HSE disposition).
  Every beat frame-verified with ffmpeg extractions.
- **Pre-state restored after recording**: `./run.sh --stop`, `rm -f app/runtime.db-shm/-wal`,
  `cp artifacts/demo/demo_pre.db app/runtime.db`, `./run.sh` → health `n_reports=4548`,
  density #1 Moran GGS-1 98/98, #2 Kathalguri GCS 88/88. Confirmed.

## 4. Offline simulation audit

(a) **Sockets**: `ss -tnp | grep -E 'uvicorn|python|ollama'` → zero established connections
from demo processes. Listeners: uvicorn pid 206964 bound **127.0.0.1:8177 only**; ollama
pid 206923 bound **127.0.0.1:11434 only**. (The 0.0.0.0:8001-8004 python listeners are the
gold `labeler_app.py` instances — workstation tooling, not part of run.sh or the tarball;
pid 5765 is an unrelated uv-cached MCP python, loopback only.)

(b) **Same-origin assets**: `/` references exactly two network assets —
`/assets/index-CSfiQMt9.css` and `/assets/index-CSs9oXmp.js` — both 200 from 127.0.0.1:8177.
Favicon is an inline data URI. CSS font URLs are all `url(/assets/*.woff2)` (vendored IBM
Plex). The only external-origin string in the JS bundle is `https://react.dev` (React's
static error-doc URL, never fetched). No googleapis/gstatic/cdn references.

(c) **No-DNS / bogus-proxy function test** (http_proxy=https_proxy=http://127.0.0.1:9,
NO_PROXY loopback, IP literals only): `/api/health` ok (RealOnnxClassifier, masked-v2);
`/api/classify` → sif_score 0.2025, well_control=true; ollama `/api/version` → 0.32.5;
`/api/density` → top Moran GGS-1 98. A control request to `http://nonexistent.invalid/`
fails with 000 as expected — proving loopback needs no DNS and the bogus proxy is inert
for the demo path.

**Remaining for the 13:00 physical-unplug rehearsal**: actual NIC-flap behaviour of the
pinned Chrome tab (SEV3-1 — hard-refresh Ctrl+Shift+R if the tab stalls; do not re-plug),
WiFi-off + ethernet-unplug theatre, and a live ollama rewording pass on the demo laptop
(curl-level ollama health verified here; the browser path is template-fallback-safe
regardless). Nothing in the demo stack initiates outbound connections.
