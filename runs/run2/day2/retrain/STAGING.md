# Day-2 staging record (masked-v2 retrain, corpus v4)

## Goal
Retrain masked config on `train_final_v4.jsonl` (71,065 rows = v3 70,565 + 500 first-aid
synthetic negatives, fixing D21 first-aid false-positive) → `artifacts/models/masked-v2/`.

## Staged files (catbox, sha256-verified in-kernel)
| file | sha256 (full) | catbox URL | status |
|---|---|---|---|
| corpus/train.jsonl (= artifacts/corpus/train_final_v4.jsonl, 71,065 rows, 92,533,325 B) | 62aac55c2962e7a13f0a937fc8d34c418a3d476449b629811b831580071094d4 | https://files.catbox.moe/8e982r.jsonl | live (206 verified) |
| corpus/val.jsonl (6,820 rows; REUSED from day-1) | 0b2e8db9e4afc558ca3bb9d60ca4c39a552e1a68a0a833555dfe3146d4b3e6ad | https://files.catbox.moe/huo0bw.jsonl | live (206) |
| corpus/test.jsonl (17,731 rows; REUSED from day-1; staged only, NOT evaluated) | 9e912f100d7cce799a6b2ed6e9b560f19b56c6cec39aec2da388216a5fba37ff | https://files.catbox.moe/fwsohf.jsonl | live (206) |
| train.py (REUSED = repo file, ALL 5 day-1 bugfixes incl. sif_label schema) | 62fa606b03f0fb104acb128a5f3d0d7eb2b11a7c971a5470351740f6fc6da3b6 | https://files.catbox.moe/71ci5r.py | live (206) |
| model.py (REUSED, frozen) | 6027f4109436e1d58277bfa1fffc358c3c85278c65b3b6868f7b899d061312e3 | https://files.catbox.moe/0auh5g.py | live (206) |
| label_spec.yaml (REUSED) | 96114b0961bc4365d7bb48c217654bc37904411fee12732839694641861b409a | https://files.catbox.moe/y8df0c.yaml | live (206) |

## train.py bugfix check (task requirement)
Repo `training/train.py` sha256 = `62fa606b…` = the FINAL day-1 staged version
(catbox 71ci5r.py) containing all 5 bugfixes: (1) `sif_label` fallback in
`normalize_row` (line ~170, "BUGFIX (Day-1)" comment present), (2) per-batch fp32
parity running-max, (3) `--resume` recompute path, (4) stale `.onnx.data` unlink,
(5) span parity over real tokens only. **No local patch applied.**

## Differences vs day-1 staging
Only `corpus/train.jsonl` changed (v1 68,062 → v4 71,065 rows). Everything else is
byte-identical reuse of day-1 catbox blobs (verified live via HTTP range probe 206).

## Kernel
- `train_masked_v4.py` (this dir), forked from `runs/run2/day1/kernels/train_masked_v3.py`;
  only the FILES entry for `corpus/train.jsonl` differs (URL + sha).
- Recipe frozen: config=masked, 3 epochs, batch 32, seq 128, lr 2e-5, fp16 autocast.
- machineShape NvidiaTeslaT4; P100/cu126 auto-detect fallback retained.
- SaveAndRunAll, internet enabled (needed for catbox fetch + pins).
