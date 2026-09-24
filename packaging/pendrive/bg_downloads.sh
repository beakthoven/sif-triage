#!/usr/bin/env bash
# BG1: download portable runtimes + windows wheels
set -euo pipefail
cd "$(dirname "$0")"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-3.14.7%2B20260901-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
[ -f dl/linux-py314.tar.gz ] || curl -fL --retry 3 -o dl/linux-py314.tar.gz "$PY_URL"
echo "linux python: $(du -h dl/linux-py314.tar.gz | cut -f1)"
# windows embeddable python — find latest 3.14.x on python.org
EMBED_URL="$(curl -s https://www.python.org/ftp/python/ | grep -oE '3\.14\.[0-9]+' | sort -Vu | tail -1)"
EMBED_URL="https://www.python.org/ftp/python/${EMBED_URL}/python-${EMBED_URL}-embed-amd64.zip"
echo "win embed: $EMBED_URL"
[ -f dl/win-py314-embed.zip ] || curl -fL --retry 3 -o dl/win-py314-embed.zip "$EMBED_URL"
echo "win embed: $(du -h dl/win-py314-embed.zip | cut -f1)"
# windows wheels (uvicorn WITHOUT [standard]: uvloop has no win build)
cat > dl/requirements-win.txt <<'REQ'
fastapi
uvicorn
pydantic>=2
numpy>=2
threadpoolctl>=3
onnxruntime>=1.23
tokenizers
pandas>=2
pyarrow
REQ
/home/dakkshesh/sih26-round2/.venv/bin/pip download -r dl/requirements-win.txt -d dl/win-wheels \
  --only-binary=:all: --platform win_amd64 --python-version 3.14 \
  --implementation cp --abi cp314 --quiet
echo "win wheels: $(ls dl/win-wheels | wc -l) files, $(du -sh dl/win-wheels | cut -f1)"
