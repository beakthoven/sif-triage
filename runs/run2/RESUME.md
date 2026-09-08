# RESUME CARD — frozen night of Sep 8 → resume Sep 9

Everything is stopped and committed. Nothing was lost. Labels are append-only files on disk (`artifacts/gold/labels/`); tunnels died with the machine (new URLs on resume — send teammates the new links).

## Bring everything back (from /home/dakkshesh/sih26-round2)

```bash
# 1. Labeling servers (LAN + localhost). Add HOST=0.0.0.0 for LAN teammates:
HOST=0.0.0.0 bash gold/start_labeling.sh
bash gold/start_labeling.sh --status     # check
bash gold/start_labeling.sh --stop       # stop

# 2. Public tunnels for remote teammates (URLs CHANGE every restart — resend links):
cd /tmp && for p in 8001 8002 8003 8004; do
  (setsid nohup ./cloudflared tunnel --url http://127.0.0.1:$p --protocol http2 --no-autoupdate > /tmp/tunnel_$p.log 2>&1 &)
done; sleep 15
grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/tunnel_800{1,2,3,4}.log

# 3. Demo stack (model + dashboard + ollama, one command):
cd /home/dakkshesh/sih26-round2 && ./run.sh        # then open http://localhost:8177
```

## State at freeze (Sep 8, 23:59 IST — T-39h to the Sep 10 15:00 deadline)

- **Ship model**: masked-v2 int8 (artifacts/models/masked-v2/); threshold raw 0.746401 (auto-loads). Val AUC 0.9969; derived-test P 0.800/R 0.975/F1 0.879; latency p95 19.7ms; ingest 37/s.
- **Baselines done**: regex 0.475 / tfidf 0.872 / zeroshot-qwen3:8b 0.854 / ft 0.880 (McNemar Holm-corrected).
- **Gold set**: 500 items sampled + pre-scored with v2 (fingerprinted cache). Labeling app validated (30/30 dry-run). Partial progress preserved on disk.
- **Demo**: 13/13 cards verified live; USB tarball rebuilt (775MB); all SEV1 review findings fixed.
- **Cron sentinels armed**: Sep 9 08:00 (T-31h), Sep 9 20:00 (T-19h gold gate), Sep 10 09:00 (T-6h), Sep 10 13:00 (T-2h rehearsal).

## Remaining work (in order)

1. **Gold labeling** (humans; the critical path) → then I run `gold/compute_gold_metrics.py` (one command; score cache is warm).
2. Fresh-eyes validation swarm vs PS text + acceptance bar (Phase 3 gate).
3. Deck + Q&A content (never-say sentences in runs/run2/ARCHITECTURE.md; honest-claims).
4. Final packaging + offline rehearsal (ethernet unplugged), fallback recording.
5. Optional: domain-expert synthetic review.

## If something's wrong after resume

- `./run.sh` self-checks and prints what's missing. `packaging/selfcheck.sh` verifies the USB build.
- CPU clamp watch: if things feel slow, run the one-liner in `CPU_CLAMP_REPORT.md` (expect ~22 tok/s; ~4 tok/s = clamp is back → check AC adapter).
- Knowledge base: `runs/run2/kb/KNOWLEDGE_BASE.md`; decision log: `runs/run2/DECISION_LOG.md`; timeline: `runs/run2/CHECKPOINTS.md`.
