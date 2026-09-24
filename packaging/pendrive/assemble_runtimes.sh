#!/usr/bin/env bash
# assemble_runtimes.sh — build the portable Linux + Windows runtimes onto the stick.
# Run after bg_downloads.sh completes (needs dl/linux-py314.tar.gz,
# dl/win-py314-embed.zip, dl/win-wheels/).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$(dirname "$0")"
PIP="$REPO/.venv/bin/pip"

say() { printf '[assemble] %s\n' "$*"; }
die() { printf '[assemble] ERROR: %s\n' "$*" >&2; exit 1; }

# --- Linux: python-build-standalone + offline wheels -------------------------
[ -f dl/linux-py314.tar.gz ] || die "dl/linux-py314.tar.gz missing"
rm -rf staging/runtime-linux
mkdir -p staging/runtime-linux
tar -xzf dl/linux-py314.tar.gz -C staging/runtime-linux   # creates python/
LPY=staging/runtime-linux/python/bin/python3
[ -x "$LPY" ] || die "linux python extract broken"
"$LPY" -m pip install --quiet --no-index --find-links "$REPO/packaging/wheels" \
    -r "$REPO/requirements.txt"
"$LPY" -c "import fastapi, uvicorn, onnxruntime, tokenizers, numpy, pandas, pyarrow, threadpoolctl, pydantic; print('linux runtime imports OK')"
find staging/runtime-linux -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
find staging/runtime-linux -name '*.pyc' -delete
tar -czf stick/runtimes/linux-py314.tar.gz -C staging/runtime-linux python
say "linux runtime: $(du -h stick/runtimes/linux-py314.tar.gz | cut -f1)"

# --- Windows: embeddable python + preinstalled site-packages -----------------
[ -f dl/win-py314-embed.zip ] || die "dl/win-py314-embed.zip missing"
[ -d dl/win-wheels ] || die "dl/win-wheels missing"
rm -rf staging/runtime-win
mkdir -p staging/runtime-win/python
python3 -m zipfile -e dl/win-py314-embed.zip staging/runtime-win/python/
WPYDIR=staging/runtime-win/python
"$PIP" install --quiet --no-index --find-links dl/win-wheels \
    -r dl/requirements-win.txt \
    --target "$WPYDIR/Lib/site-packages" \
    --platform win_amd64 --python-version 3.14 --implementation cp --abi cp314 \
    --only-binary=:all:
# ._pth: make Lib/site-packages importable (embeddable python isolates by default)
PTH="$(ls "$WPYDIR"/python*._pth | head -1)"
ZBASE="$(basename "$PTH" ._pth)"
printf '%s.zip\n.\nLib/site-packages\nimport site\n' "$ZBASE" > "$PTH"
# sanity: pydantic/onnxruntime landed as win_amd64 binaries
ls "$WPYDIR/Lib/site-packages/onnxruntime/capi/"*.pyd >/dev/null || die "onnxruntime win binaries missing"
ls "$WPYDIR/Lib/site-packages/pydantic_core/"*.pyd >/dev/null || die "pydantic_core win binaries missing"
rm -f "$WPYDIR/Lib/site-packages/bin/"* 2>/dev/null || true
rmdir "$WPYDIR/Lib/site-packages/bin" 2>/dev/null || true
( cd staging/runtime-win && python3 - <<'PY'
import zipfile, pathlib
root = pathlib.Path("python")
out = pathlib.Path("../../stick/runtimes/win-py314.zip")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in sorted(root.rglob("*")):
        if p.is_file():
            z.write(p, p.as_posix())
print(f"win runtime: {out.stat().st_size/1e6:.0f} MB")
PY
)
say "done"
