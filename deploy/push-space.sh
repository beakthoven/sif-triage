#!/usr/bin/env bash
# Stage and upload the Space payload (app code, dashboard, Dockerfile,
# entrypoint) to the Hugging Face Space repo. Run AFTER upload-bundle.sh.
#
#   SPACE_REPO=<hf-user>/sif-triage bash deploy/push-space.sh
#
# hf CLI required (pip install -U 'huggingface_hub[cli]'); auth via HF_TOKEN
# env or `hf auth login`. The bundle itself is NOT pushed here — the Space
# downloads it at cold start from the private dataset (BUNDLE_REPO secret).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v hf >/dev/null 2>&1 || {
    echo "push-space: the hf CLI is required (pip install -U 'huggingface_hub[cli]')" >&2
    exit 1
}

STAGE="$(mktemp -d /tmp/sif-space-XXXXXX)"
mkdir -p "$STAGE/app" "$STAGE/dashboard"

cp "$REPO_ROOT/deploy/space-README.md" "$STAGE/README.md"
cp "$REPO_ROOT/deploy/Dockerfile" "$REPO_ROOT/deploy/entrypoint.sh" \
   "$REPO_ROOT/deploy/fetch_bundle.py" "$REPO_ROOT/requirements.txt" "$STAGE/"

rsync -a \
    --exclude '__pycache__' \
    --exclude '*.db' --exclude '*.db-*' \
    --exclude 'tests' \
    "$REPO_ROOT/app/" "$STAGE/app/"
rsync -a "$REPO_ROOT/dashboard/dist/" "$STAGE/dashboard/dist/"

echo "staged Space payload at $STAGE ($(du -sh "$STAGE" | cut -f1))"
hf upload "${SPACE_REPO:?set SPACE_REPO=<hf-user>/sif-triage}" \
    "$STAGE" . --repo-type space
echo "pushed to Space ${SPACE_REPO} — set its secrets next (deploy/DEPLOY.md step 5)"
