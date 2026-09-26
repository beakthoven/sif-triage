#!/usr/bin/env bash
# Stage (and optionally upload) the runtime bundle for container cold starts.
#
#   BUNDLE_REPO=<hf-user>/sif-runtime-bundle bash deploy/upload-bundle.sh
#       → stages to a temp dir, then uploads to the PRIVATE HF dataset
#         BUNDLE_REPO (hf CLI; HF_TOKEN env or `hf auth login` first).
#
#   bash deploy/upload-bundle.sh --stage-only <dir>
#       → stage only, no upload. Used by local container verification
#         (docker run -v <dir>:/app-data/bundle …) and by inspection.
#
# Bundle layout (consumed by deploy/entrypoint.sh + the container envs):
#   masked-v2/sif_multitask_int8.onnx  masked-v2/tokenizer/  masked-v2/metrics.json
#   masked-v2/thresholds.json  masked-v2/manifest.json
#   embeddings/corpus_embeddings_fp16.npy  embeddings/corpus_ids.jsonl
#   embeddings/corpus_index_meta.json  embeddings/minilm/
#   demo_pre.db  bundle_manifest.txt
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="$REPO_ROOT/artifacts/models/masked-v2"
EMBED_DIR="$REPO_ROOT/artifacts/embeddings"

STAGE_ONLY=0
STAGE_DIR=""
if [ "${1:-}" = "--stage-only" ]; then
    STAGE_ONLY=1
    STAGE_DIR="${2:?--stage-only needs a target directory}"
    mkdir -p "$STAGE_DIR"
fi

need() { [ -e "$1" ] || { echo "upload-bundle: missing $1" >&2; exit 1; }; }
for f in \
    "$MODEL_DIR/sif_multitask_int8.onnx" \
    "$MODEL_DIR/tokenizer/tokenizer.json" \
    "$MODEL_DIR/metrics.json" \
    "$MODEL_DIR/thresholds.json" \
    "$EMBED_DIR/corpus_embeddings_fp16.npy" \
    "$EMBED_DIR/corpus_ids.jsonl" \
    "$EMBED_DIR/corpus_index_meta.json" \
    "$EMBED_DIR/minilm/model.onnx" \
    "$REPO_ROOT/artifacts/demo/demo_pre.db"; do
    need "$f"
done

if [ "$STAGE_ONLY" = "1" ]; then
    STAGE="$STAGE_DIR"
else
    STAGE="$(mktemp -d /tmp/sif-bundle-XXXXXX)"
fi
rm -rf "$STAGE"/*
mkdir -p "$STAGE/masked-v2" "$STAGE/embeddings"

cp "$MODEL_DIR/sif_multitask_int8.onnx" "$STAGE/masked-v2/"
cp -r "$MODEL_DIR/tokenizer" "$STAGE/masked-v2/"
for f in metrics.json thresholds.json manifest.json; do
    [ -f "$MODEL_DIR/$f" ] && cp "$MODEL_DIR/$f" "$STAGE/masked-v2/"
done
cp "$EMBED_DIR"/corpus_embeddings_fp16.npy "$EMBED_DIR"/corpus_ids.jsonl \
   "$EMBED_DIR"/corpus_index_meta.json "$STAGE/embeddings/"
cp -r "$EMBED_DIR/minilm" "$STAGE/embeddings/"
cp "$REPO_ROOT/artifacts/demo/demo_pre.db" "$STAGE/"

( cd "$STAGE" && find . -type f ! -name bundle_manifest.txt \
    | sed 's|^\./||' | sort ) > "$STAGE/bundle_manifest.txt"

TOTAL="$(du -sh "$STAGE" | cut -f1)"
echo "staged bundle at $STAGE ($TOTAL, $(wc -l < "$STAGE/bundle_manifest.txt") files)"

if [ "$STAGE_ONLY" = "1" ]; then
    echo "stage-only mode: skipping upload"
    exit 0
fi

command -v hf >/dev/null 2>&1 || {
    echo "upload-bundle: the hf CLI is required (pip install -U 'huggingface_hub[cli]')" >&2
    exit 1
}
hf upload "${BUNDLE_REPO:?set BUNDLE_REPO=<hf-user>/sif-runtime-bundle}" \
    "$STAGE" . --repo-type dataset
echo "uploaded to dataset ${BUNDLE_REPO} (keep it PRIVATE — it carries the model weights)"
