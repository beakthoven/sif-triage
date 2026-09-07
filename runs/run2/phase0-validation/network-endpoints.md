# Phase 0 Validation — Network + Data Endpoints (PS 26165)

Date probed: 2026-09-08 (probe server headers show 2026-09-07/08 UTC). All measurements made live from this machine with `curl` unless noted. MEASURED = observed this session; nothing below is INFERRED unless flagged.

## Findings

| # | Endpoint / Claim | Result | Latency | Verdict |
|---|---|---|---|---|
| 1a | https://www.osha.gov/severe-injury-reports (dashboard) | HTTP 200, 106,888 B page | 2.09 s | VERIFIED — live |
| 1b | Zip HEAD `.../January2015toNovember2025.zip` | HTTP 200, content-length **16,224,511**, last-modified **2026-08-07 15:04:26 GMT**, CloudFront hit, etag `6a75f3fa-f790ff` | — | VERIFIED — current dataset served |
| 1c | Zip GET (full 16 MB download) | HTTP 200, 16,224,511 B @ ~1.31 MB/s; md5 `380ad54957d83409f3a13fc56c02c96d` | 12.40 s | VERIFIED — md5 **byte-identical** to local `data/osha_sir.zip` (same md5; sha256 `a3f7f434…846bb0` both) |
| 1d | Zip contents vs on-disk CSV | Zip contains `January2015toNovember2025.csv` (57,403,269 B); extracted md5 `5ddc52f0f0fccc6716596027a46ce5f1` == md5 of `data/January2015toNovember2025.csv`; CSV = 106,488 lines (106,487 data rows + header) | — | VERIFIED — local CSV == live dataset |
| 2 | huggingface.co + API | `huggingface.co` HTTP 200 (0.59 s); `/api/models/bert-base-uncased` 307→200 after redirect (0.51 s) | <1 s | VERIFIED — site + API responsive |
| 3 | pypi.org | `pypi.org` HTTP 200 (0.14 s); `/pypi/requests/json` HTTP 200 (0.75 s) | <1 s | VERIFIED |
| 4 | registry.ollama.ai | `/v2/` root → HTTP 404 (0.92 s) — **normal**, Ollama serves no OCI root index; real pull path `/v2/library/llama3.2/manifests/3b` → **HTTP 200** with `ollama-content-digest: a80c4f17…` | <1 s | VERIFIED (with correction to probing method) — `ollama pull` will work; root-404 is expected, not an outage |
| 5 | hub.docker.com | homepage HTTP 200 (1.00 s); Hub API `/v2/repositories/library/python/tags/3.12` HTTP 200 (0.35 s) | ~1 s | VERIFIED — registry reachable, pulls will work at packaging time |
| 6 | github.com egress | `github.com` HTTP 200 (1.10 s); `api.github.com` HTTP 200 (0.10 s) | ~1 s | VERIFIED — general egress OK |

## Handoff warning re-checked

HANDOFF.md warns "government APIs died mid-run twice before." INFERRED/unverifiable as history from here, but TODAY OSHA is fully up and the full 16 MB re-download completed in 12.4 s, so even a mid-run death is cheap to recover (whole dataset, not an API with rate limits). No flakiness observed in any probe this session; all latencies ≤ ~2.1 s.

## Commands used

- `curl -sS -o /dev/null -w ... -A 'Mozilla/5.0' https://www.osha.gov/severe-injury-reports`
- `curl -sSI https://www.osha.gov/sites/default/files/January2015toNovember2025.zip`
- `curl -sS -o /tmp/osha_sir_dl.zip ... <zip URL>` + `md5sum`/`sha256sum` vs `data/osha_sir.zip`
- `unzip -l`, `unzip -p data/osha_sir.zip | md5sum` vs `md5sum data/January2015toNovember2025.csv`; `wc -l`
- `curl -o /dev/null -w '%{http_code} %{time_total}'` against huggingface.co (+API), pypi.org (+JSON API), registry.ollama.ai (`/v2/` and `/v2/library/llama3.2/manifests/3b`), hub.docker.com (+v2 API), github.com (+api.github.com)

## Summary

6/6 endpoint groups VERIFIED. Zero FAILED load-bearing claims. The only correction is methodological: Ollama's `/v2/` root 404 would look like a failure if probed naively — the manifest endpoint is the correct liveness check, and it returns 200.
