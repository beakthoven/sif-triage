#!/usr/bin/env bash
# make_tarball.sh — build the USB demo tarball (bare-metal, offline target).
#
# Ships ONLY the demo runtime: app code, prebuilt dashboard, model artifacts
# (INT8 ship variant), the MiniLM near-dup runtime (vendored ONNX + precomputed
# corpus index), precomputed pattern stats, frozen label spec, run.sh, wheels
# for offline pip install. EXCLUDES data/ and runs/ raw research,
# dev/training code, .venv, and git history (artifacts/ and *.onnx are
# gitignored — this tarball is the transport for the model). The fp32 export
# stays repo-side: run.sh (app resolution order) prefers sif_multitask_int8.onnx,
# so shipping it would add ~599M of dead weight.
#
# Usage:
#   packaging/make_tarball.sh                build (fails if model missing)
#   packaging/make_tarball.sh --allow-mock   build without the ONNX (dev only)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ALLOW_MOCK=0
[ "${1:-}" = "--allow-mock" ] && ALLOW_MOCK=1

say() { printf '[make_tarball] %s\n' "$*"; }
die() { printf '[make_tarball] ERROR: %s\n' "$*" >&2; exit 1; }

# --- same artifact contract as run.sh --------------------------------------
if ! compgen -G "artifacts/models/*/*.onnx" >/dev/null && [ ! -f app/artifacts/model.onnx ]; then
    [ "$ALLOW_MOCK" -eq 1 ] || die "no ONNX artifact under artifacts/models/*/ — refusing to ship a mock demo.
  Retrieve the export-gated artifact from Kaggle first. Dev-only bypass: --allow-mock"
    say "WARNING: building WITHOUT the ONNX model (--allow-mock) — not demo-ready"
fi

[ -f dashboard/dist/index.html ] || die "dashboard/dist missing — run: cd dashboard && npm ci && npm run build"
[ -d packaging/wheels ] || die "packaging/wheels missing — run:
  .venv/bin/pip download -r requirements.txt -d packaging/wheels --only-binary=:all:"
[ -f artifacts/embeddings/minilm/model.onnx ] || die "artifacts/embeddings/minilm/model.onnx missing —
  the near-dup embedder (app/config.py:embed_model_dir) needs the vendored MiniLM ONNX"
[ -f artifacts/embeddings/corpus_embeddings_fp16.npy ] || die "corpus index missing under artifacts/embeddings/ —
  the near-dup banner needs corpus_embeddings_fp16.npy + corpus_ids.jsonl (app/storage.py)"

STAMP="$(date +%Y%m%d)"
OUT="packaging/sif-demo-usb-${STAMP}.tar.gz"

tar -czf "$OUT" \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='app/runtime.db*' \
    --exclude='artifacts/models/masked-v2/sif_multitask_fp32.onnx' \
    --exclude='artifacts/models/masked-v2/sif_multitask_fp32.onnx.data' \
    app \
    dashboard/dist \
    artifacts/models/masked-v2 \
    artifacts/embeddings/minilm \
    artifacts/embeddings/corpus_embeddings_fp16.npy \
    artifacts/embeddings/corpus_ids.jsonl \
    artifacts/patterns \
    spec/label_spec.yaml \
    requirements.txt \
    run.sh \
    README.md \
    packaging/manifest.md \
    packaging/install.sh \
    packaging/selfcheck.sh \
    packaging/wheels

say "wrote $OUT ($(du -sh "$OUT" | cut -f1))"
say "$(tar -tzf "$OUT" | wc -l) entries"
say "contents:"
tar -tzf "$OUT" | awk -F/ '{print $1"/"$2}' | sort -u | sed 's/^/  /'
