#!/usr/bin/env bash
# BG2: ollama qwen3:4b sidecar — manifest + only the blobs it references
set -euo pipefail
cd "$(dirname "$0")"
MODELS="$HOME/.ollama/models"
MANIFEST="manifests/registry.ollama.ai/library/qwen3/4b"
python3 - "$MODELS" <<'PY'
import json, sys, pathlib
models = pathlib.Path(sys.argv[1])
man = json.loads((models/"manifests/registry.ollama.ai/library/qwen3/4b").read_text())
digests = [l["digest"] for l in man["layers"]] + [man["config"]["digest"]]
files = ["manifests/registry.ollama.ai/library/qwen3/4b"]
for d in digests:
    algo, h = d.split(":", 1)
    p = models/"blobs"/f"{algo}-{h}"
    assert p.exists(), f"missing blob {p}"
    files.append(f"blobs/{algo}-{h}")
pathlib.Path("dl/ollama_files.txt").write_text("\n".join(files))
print(f"{len(files)} files")
PY
[ -f staging/ollama-qwen3-4b.tar.gz ] || tar -czf staging/ollama-qwen3-4b.tar.gz -C "$MODELS" -T dl/ollama_files.txt
echo "ollama sidecar: $(du -h staging/ollama-qwen3-4b.tar.gz | cut -f1)"
