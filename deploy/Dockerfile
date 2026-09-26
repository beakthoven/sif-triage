# SIF Precursor Triage — runtime container (SIH 2026 PS 26165).
#
# Serves the FastAPI app + the built React dashboard with the real INT8
# classifier. Weights are NOT baked into the image: on cold start the
# entrypoint downloads the runtime bundle (~312 MB: INT8 model + tokenizer,
# MiniLM embedder + corpus index, pristine demo DB) from a private Hugging
# Face dataset, then seeds a fresh SQLite register. See deploy/DEPLOY.md.
#
# Works unchanged on Hugging Face Spaces (free CPU basic: 2 vCPU / 16 GB,
# listens on 0.0.0.0:${PORT:-7860}), on any Docker host, and behind any
# reverse proxy. Build from the REPO ROOT:
#   docker build -f deploy/Dockerfile -t sif-triage .

FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt huggingface_hub

COPY app/ app/
COPY dashboard/dist/ dashboard/dist/
COPY deploy/entrypoint.sh deploy/fetch_bundle.py /app/

RUN mkdir -p /app-data && chown -R user:user /app-data /app

ENV BUNDLE_DIR=/app-data/bundle \
    SIF_DB_PATH=/app-data/runtime.db \
    SIF_MODEL_PATH=/app-data/bundle/masked-v2/sif_multitask_int8.onnx \
    SIF_EMBED_MODEL_DIR=/app-data/bundle/embeddings/minilm \
    SIF_EMBED_INDEX_DIR=/app-data/bundle/embeddings \
    SIF_EXPLAIN_LLM=0 \
    PYTHONUNBUFFERED=1

USER user
EXPOSE 7860

HEALTHCHECK --interval=60s --timeout=15s --start-period=180s \
    CMD curl -fsS http://127.0.0.1:7860/api/health || exit 1

ENTRYPOINT ["bash", "/app/entrypoint.sh"]
