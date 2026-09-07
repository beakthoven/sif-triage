# CPU Power Clamp — Investigation Report

**Status: RESOLVED (verified 2026-09-08, this session).** Kept for the record and in case it recurs.

## Symptom (as found during Phase 0/1 validation, 2026-09-08)

Under load, ALL 16 logical cores clamped to ~0.85 GHz and stayed there:
- qwen3:4b generation: **3.7–4.4 tok/s** (vs 22.9 tok/s historical on this machine)
- ONNX int8 ModernBERT p95 latency: **244 ms** (vs ~35–75 ms estimated unthrottled)
- Temperature at clamp time: only **41.5 °C** — NOT thermal throttling
- Governor/EPP already `performance` — not a governor misconfiguration
- Signature = platform-level power limit (e.g. running on battery / weak AC source / low-power platform profile), not thermal, not software governor

## Verification of the fix (this session, measurements)

| Probe | Clamped (earlier today) | Now |
|---|---|---|
| Idle freqs | all cores 0.62–0.85 GHz | 0.62 GHz idle downclock + cores boosting to 5.04 GHz |
| 10s all-core burn (16 threads) | all 16 cores pinned 0.85 GHz | 8 cores @ ~3.25 GHz + 8 cores @ ~4.7 GHz |
| qwen3:4b gen / prompt tok/s | 3.7–4.4 / 21–28 | **22.7 / 157.7** (matches historical 22.9 / 146.8) |
| `platform_profile` | performance (but clamped anyway) | performance |
| AC / battery | — | ACAD online=1, BAT1 Full |
| amd_pstate | active | active, boost=1, max 5.09 GHz |

Verdict: the pathological clamp is gone; behavior is normal idle-downclock + boost-under-load.

## Watch item: temperature

Synthetic all-core burn pushed a thermal zone to **99 °C** while holding 3.25/4.7 GHz — fine for bursts, but sustained max-load work (bulk ingest benchmarks, long ONNX runs) may approach thermal limits. If freq dips under sustained load are seen later, check temps FIRST before suspecting the platform clamp: `cat /sys/class/thermal/thermal_zone*/temp`.

## If it recurs — diagnostic checklist

1. **Check AC source first (most likely cause):** `cat /sys/class/power_supply/AC*/online` and battery status. USB-C sources: `cat /sys/class/power_supply/ucsi-source-psy-USB*/online`. A weak/under-wattage USB-C charger or battery-only operation is the classic trigger for an all-core ~0.85 GHz platform cap on Ryzen AI laptops.
2. **Platform profile:** `cat /sys/firmware/acpi/platform_profile` (choices: low-power balanced performance). Force: `echo performance | sudo tee /sys/firmware/acpi/platform_profile`.
3. **amd_pstate:** `cat /sys/devices/system/cpu/amd_pstate/status` (want `active`); boost: `cat /sys/devices/system/cpu/cpufreq/boost` (want 1).
4. **Rule out thermal:** sample `scaling_cur_freq` across cores AND thermal zone temps during a 10s burn (`for i in $(seq 16); do (timeout 10 bash -c 'while :; do :; done' &); done`). All cores pinned at one low freq + low temp = platform limit. High temp + declining freq = thermal.
5. **Power daemons:** `systemctl status power-profiles-daemon thermald 2>/dev/null` — check which profile daemon is active and what it set (`powerprofilesctl get`).
6. **Firmware:** BIOS/UEFI update + check for "battery extender"/"quiet on battery" style settings; check Windows dual-boot power settings if applicable (some firmware honors last-OS settings).
7. **Verify fix with the two numbers that matter:** ollama gen tok/s (~22–23 expected, qwen3:4b) and ONNX classify p95 (<100 ms target, re-measured Day 3).

## One-liner health check (run any time)

```bash
curl -s http://localhost:11434/api/generate -d '{"model":"qwen3:4b","prompt":"Say hello.","stream":false,"options":{"num_predict":40,"temperature":0}}' \
 | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['eval_count']/(d['eval_duration']/1e9):.1f} tok/s\")"
# ~20+ tok/s = healthy; ~4 tok/s = clamp is back
```
