#!/usr/bin/env bash
# install.sh — target-side setup from the USB tarball. Runs fully OFFLINE:
# all Python deps install from the bundled packaging/wheels (pip --no-index).
#
# Usage (from the extracted tarball root):
#   packaging/install.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYBIN="${PYTHON:-python3}"
say() { printf '[install] %s\n' "$*"; }
die() { printf '[install] ERROR: %s\n' "$*" >&2; exit 1; }

command -v "$PYBIN" >/dev/null 2>&1 || die "python3 not found — install Python 3.14 from the OS media"
# Bundled wheels carry cp314 binaries (plus abi3) — the interpreter minor
# version must match the build interpreter exactly, not just be "new enough".
"$PYBIN" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 14) else 1)' \
    || die "Python 3.14 required — bundled wheels are cp314 (found: $("$PYBIN" --version 2>&1)).
  Rebuild wheels for your interpreter: pip download -r requirements.txt -d packaging/wheels --only-binary=:all:"

if [ ! -x .venv/bin/python ]; then
    say "creating .venv"
    "$PYBIN" -m venv .venv
fi

say "installing runtime deps from bundled wheels (offline, --no-index)"
.venv/bin/pip install --no-index --find-links=packaging/wheels -r requirements.txt

say "verifying import contract"
.venv/bin/python -c "import fastapi, uvicorn, onnxruntime, tokenizers, numpy, threadpoolctl, structlog, prometheus_client, pydantic_settings; print('  imports ok')"

if ! compgen -G "artifacts/models/*/*.onnx" >/dev/null && [ ! -f app/artifacts/model.onnx ]; then
    say "WARNING: no ONNX model artifact in this bundle — run.sh will need --allow-mock"
else
    say "model artifact present"
fi

say "done. Start the demo with:  ./run.sh"
